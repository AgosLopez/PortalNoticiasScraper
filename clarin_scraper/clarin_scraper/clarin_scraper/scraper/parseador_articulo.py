import json
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from modelos.esquema import Autor, Noticia, ResultadoArticulo, Tema, Verificacion, generar_id

# ---------------------------------------------------------------------------
# Verbos que en castellano introducen una cita o declaración.
# Se usan para clasificar oraciones en la sección de Verificaciones.
# ---------------------------------------------------------------------------
VERBOS_DECLARACION = {
    "dijo", "afirmó", "señaló", "indicó", "según", "sostuvo",
    "declaró", "aseguró", "manifestó", "informó", "expresó",
    "confirmó", "negó", "advirtió", "destacó", "remarcó",
}

# ---------------------------------------------------------------------------
# Headers HTTP que simulan un navegador real.
# Sin esto, muchos servidores devuelven 403 o contenido reducido.
# ---------------------------------------------------------------------------
CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

LONGITUD_MAXIMA_TEMA = 40


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE SECCIÓN
# ---------------------------------------------------------------------------

def extraer_seccion(url: str) -> str:
    """
    Deduce la sección a partir de la URL.

    Clarín usa URLs del estilo:
      /politica/titulo-nota_0_id.html        → "politica"
      /mundo/region/titulo_0_id.html         → "mundo/region"

    Estrategia: tomamos los segmentos de la ruta hasta que aparezca
    uno que contenga guión-bajo seguido de dígitos (el slug de la nota).
    """
    segmentos = urlparse(url).path.strip("/").split("/")
    resultado = []
    for seg in segmentos:
        # El segmento final de una nota de Clarín tiene forma "titulo_0_id.html"
        if re.search(r"_\d+_\w+\.html$", seg):
            break
        resultado.append(seg)
    return "/".join(resultado[:2]) if len(resultado) >= 2 else resultado[0] if resultado else ""


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE METADATOS (<meta> tags)
# ---------------------------------------------------------------------------

def extraer_meta(soup: BeautifulSoup, propiedad: str) -> str:
    """
    Busca una etiqueta <meta property="X"> o <meta name="X"> y devuelve
    su atributo content.

    Por qué meta tags: los medios grandes implementan Open Graph (og:*)
    y metadatos de artículo (article:*) que son más confiables que
    parsear el HTML visual, porque están pensados para ser consumidos
    por máquinas (redes sociales, agregadores, bots).
    """
    etiqueta = soup.find("meta", property=propiedad) or soup.find(
        "meta", attrs={"name": propiedad}
    )
    return etiqueta.get("content", "") if etiqueta else ""


# ---------------------------------------------------------------------------
# EXTRACCIÓN DEL CUERPO
# ---------------------------------------------------------------------------

def extraer_cuerpo(soup: BeautifulSoup) -> str:
    """
    Extrae el texto del cuerpo de la nota.

    Clarín usa varias clases según el tipo de artículo y la versión
    del frontend. Probamos en orden de especificidad, con <article>
    como fallback genérico.

    Por qué eliminamos script/style/figure/aside:
      Esos tags traen código JS, estilos inline, pies de foto y
      recuadros que ensucian el texto. Un get_text() directo
      mezclaría el contenido editorial con basura técnica.
    """
    contenedor = (
        soup.find("div", class_="article-body")
        or soup.find("div", class_="body-nota")
        or soup.find("div", attrs={"data-type": "text"})
        or soup.find("div", class_="article__body")
        or soup.find("section", class_="article-body")
        or soup.find("article")
        or soup.find("div", attrs={"itemprop": "articleBody"})
    )
    if not contenedor:
        return ""
    for tag in contenedor.find_all(["script", "style", "figure", "aside", "nav"]):
        tag.decompose()
    return contenedor.get_text(separator=" ").strip()


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE AUTORES
# ---------------------------------------------------------------------------

def _autores_desde_ldjson(soup: BeautifulSoup) -> list[str]:
    """
    Intenta extraer autores del bloque JSON-LD (<script type="application/ld+json">).

    JSON-LD es el estándar de Schema.org para datos estructurados.
    Es la fuente más confiable porque es explícita y estructurada,
    a diferencia del HTML visual que puede cambiar con cualquier
    rediseño del sitio.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            datos = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # JSON-LD puede ser un objeto o una lista; normalizamos a lista
        if isinstance(datos, list):
            candidatos = datos
        else:
            candidatos = [datos]

        for item in candidatos:
            if not isinstance(item, dict):
                continue
            tipo = item.get("@type", "")
            # Clarín puede usar NewsArticle, Article, o ReportageNewsArticle
            if tipo not in ("NewsArticle", "Article", "ReportageNewsArticle"):
                continue
            autor = item.get("author")
            if not autor:
                continue
            if isinstance(autor, dict):
                autor = [autor]
            nombres = [
                a["name"]
                for a in autor
                if isinstance(a, dict) and a.get("name")
            ]
            if nombres:
                return nombres

    return []


def extraer_autores(soup: BeautifulSoup) -> list[str]:
    """
    Extrae la lista de nombres de autores. Prueba tres estrategias en orden:
      1. JSON-LD (más confiable, estructurado)
      2. Clases CSS conocidas de Clarín
      3. Atributo rel="author" (estándar HTML)
    """
    desde_ldjson = _autores_desde_ldjson(soup)
    if desde_ldjson:
        return desde_ldjson

    # Clarín usa distintas clases según el template
    selectores = [
        ("span", "author-name"),
        ("a",    "author-name"),
        ("span", "article__author"),
        ("a",    "article__author"),
        ("span", "firma"),
        ("div",  "article-author"),
    ]
    for tag, clase in selectores:
        etiquetas = soup.find_all(tag, class_=clase)
        if etiquetas:
            return [e.get_text(strip=True) for e in etiquetas if e.get_text(strip=True)]

    # Fallback: rel="author" es un atributo HTML estándar
    etiquetas_rel = soup.find_all("a", rel="author")
    if etiquetas_rel:
        return [e.get_text(strip=True) for e in etiquetas_rel if e.get_text(strip=True)]

    return []


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE TEMAS / TAGS
# ---------------------------------------------------------------------------

def _es_tema_valido(nombre: str) -> bool:
    """
    Filtra temas que son basura: strings vacíos, solo mayúsculas
    (suelen ser IDs internos), o demasiado largos para ser un tag real.
    """
    letras = [c for c in nombre if c.isalpha()]
    return (
        bool(letras)
        and len(nombre) <= LONGITUD_MAXIMA_TEMA
        and not all(c.isupper() for c in letras)
    )


def extraer_temas(soup: BeautifulSoup) -> list[str]:
    """
    Extrae las etiquetas temáticas de la nota. Prueba en orden:
      1. <meta property="article:tag"> → estándar Open Graph
      2. Links/spans con clases de tags de Clarín
      3. <meta name="keywords"> → fallback genérico
    """
    tags_meta = soup.find_all("meta", property="article:tag")
    if tags_meta:
        return [
            m.get("content", "").strip()
            for m in tags_meta
            if _es_tema_valido(m.get("content", "").strip())
        ]

    selectores = [
        ("a",    "tag"),
        ("a",    "tag-link"),
        ("a",    "article__tag"),
        ("span", "tag"),
        ("li",   "tag"),
    ]
    for tag_html, clase in selectores:
        etiquetas = soup.find_all(tag_html, class_=clase)
        if etiquetas:
            return [
                e.get_text(strip=True)
                for e in etiquetas
                if _es_tema_valido(e.get_text(strip=True))
            ]

    meta_kw = extraer_meta(soup, "keywords")
    if meta_kw:
        return [k.strip() for k in meta_kw.split(",") if _es_tema_valido(k.strip())]

    return []


# ---------------------------------------------------------------------------
# CLASIFICACIÓN DE ORACIONES (para el módulo de Verificaciones)
# ---------------------------------------------------------------------------

def clasificar_oracion(oracion: str) -> tuple[str, str]:
    """
    Clasifica una oración en tres categorías relevantes para fact-checking:

      "cita"         → la oración reproduce (con comillas) o reporta
                       (con verbo declarativo) lo que dijo alguien.
                       Incluye la fuente si puede extraerse.

      "estadistica"  → la oración contiene una cifra o porcentaje que
                       podría ser verificable numéricamente.

      "sin_clasificar" → oración narrativa sin elementos verificables obvios.

    Esta clasificación es la base del grafo de verificación en Neo4j:
    permite linkear noticias → citas → fuentes citadas.
    """
    tiene_comillas = any(c in oracion for c in ('"', "\u201c", "\u201d", "\u00ab", "\u00bb"))
    palabras = set(oracion.lower().split())
    tiene_verbo = bool(palabras & VERBOS_DECLARACION)
    tiene_estadistica = bool(
        re.search(r"\d+[\.,]?\d*\s*(%|millones?|miles?|mil\b|mil\s)", oracion, re.IGNORECASE)
    )

    if tiene_comillas or tiene_verbo:
        fuente = ""
        coincidencia = re.search(
            r"según\s+([\w\s]+?)(?:[,.]|$)", oracion, re.IGNORECASE
        )
        if coincidencia:
            fuente = coincidencia.group(1).strip()
        return "cita", fuente

    if tiene_estadistica:
        return "estadistica", ""

    return "sin_clasificar", ""


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE VERIFICACIONES
# ---------------------------------------------------------------------------

def extraer_verificaciones(cuerpo: str) -> list[Verificacion]:
    """
    Divide el cuerpo en oraciones y clasifica cada una.

    Por qué esto existe: el proyecto de investigación apunta a
    detectar fake news. Cada oración con una cita o estadística
    es un nodo potencialmente verificable en Neo4j.

    Oraciones muy cortas (< 30 chars) se descartan porque suelen
    ser artefactos del parser (subtítulos, bullets, etc.).
    """
    if not cuerpo:
        return []
    oraciones = re.split(r"(?<=[.!?])\s+", cuerpo)
    verificaciones = []
    for oracion in oraciones:
        oracion = oracion.strip()
        if len(oracion) < 30:
            continue
        tipo, fuente = clasificar_oracion(oracion)
        verificaciones.append(
            Verificacion(
                verificacion_id=generar_id(oracion),
                texto=oracion,
                tipo=tipo,
                verificado=False,
                fuente_citada=fuente,
            )
        )
    return verificaciones


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL: PARSEAR UN ARTÍCULO
# ---------------------------------------------------------------------------

def parsear_articulo(url: str, delay: float = 2.0) -> ResultadoArticulo:
    """
    Descarga y parsea un artículo completo de Clarín.

    Flujo:
      1. sleep(delay) → ser respetuosos con el servidor, no bombardearlo
      2. requests.get → descarga el HTML con headers de navegador real
      3. BeautifulSoup → parsea el HTML en un árbol navegable
      4. Extraemos todos los campos y construimos los dataclasses del esquema

    Por qué requests y no Selenium aquí:
      Selenium levanta un navegador completo (con JS), lo cual es lento
      y consume mucha memoria. Para el parseo de artículos individuales
      alcanza con el HTML estático que devuelve el servidor, porque
      Clarín (al igual que Infobae) renderiza el contenido editorial
      en el HTML inicial (server-side rendering).
      Selenium solo se usa en el crawleador de secciones, donde el
      infinite scroll requiere ejecutar JavaScript.

    Args:
        url:   URL completa del artículo
        delay: segundos de espera antes de hacer el request

    Returns:
        ResultadoArticulo con todos los datos del artículo listos para
        ser guardados en CSV y luego volcados a Neo4j.
    """
    time.sleep(delay)
    respuesta = requests.get(url, headers=CABECERAS, timeout=15)
    respuesta.raise_for_status()
    soup = BeautifulSoup(respuesta.text, "lxml")

    h1 = soup.find("h1")
    titulo = extraer_meta(soup, "og:title") or (h1.get_text(strip=True) if h1 else "")

    noticia_id = generar_id(url)
    cuerpo = extraer_cuerpo(soup)

    noticia = Noticia(
        noticia_id=noticia_id,
        url=url,
        titulo=titulo,
        cuerpo=cuerpo,
        fecha_publicacion=extraer_meta(soup, "article:published_time"),
        fecha_modificacion=extraer_meta(soup, "article:modified_time"),
        seccion=extraer_seccion(url),
        imagen_portada=extraer_meta(soup, "og:image"),
    )

    autores = [
        Autor(autor_id=generar_id(nombre), nombre=nombre)
        for nombre in extraer_autores(soup)
    ]
    temas = [
        Tema(tema_id=generar_id(nombre), nombre=nombre)
        for nombre in extraer_temas(soup)
    ]
    verificaciones = extraer_verificaciones(cuerpo)

    return ResultadoArticulo(
        noticia=noticia,
        autores=autores,
        temas=temas,
        verificaciones=verificaciones,
    )
