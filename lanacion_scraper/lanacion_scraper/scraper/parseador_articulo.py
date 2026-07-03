import json
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from modelos.esquema import Autor, Noticia, ResultadoArticulo, Tema, Verificacion, generar_id

# ---------------------------------------------------------------------------
# Verbos de declaración (mismos que Infobae y Clarín, español rioplatense)
# ---------------------------------------------------------------------------
VERBOS_DECLARACION = {
    "dijo", "afirmó", "señaló", "indicó", "según", "sostuvo",
    "declaró", "aseguró", "manifestó", "informó", "expresó",
    "confirmó", "negó", "advirtió", "destacó", "remarcó",
}

# ---------------------------------------------------------------------------
# Headers HTTP: La Nación también verifica User-Agent
# ---------------------------------------------------------------------------
CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

LONGITUD_MAXIMA_TEMA = 50  # LN tiene temas un poco más largos que Clarín/Infobae


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE SECCIÓN
#
# La Nación usa URLs como:
#   /politica/titulo-nota-nid02072026/          → "politica"
#   /economia/campo/titulo-nid01072026/         → "economia/campo"
#   /deportes/futbol/titulo-nid28062026/        → "deportes/futbol"
#
# Estrategia: tomamos los segmentos de la ruta hasta que encontremos
# el que termina en -nidDDMMYYYY (el slug del artículo).
# ---------------------------------------------------------------------------

def extraer_seccion(url: str) -> str:
    segmentos = urlparse(url).path.strip("/").split("/")
    resultado = []
    for seg in segmentos:
        if re.search(r"-nid\d{8}$", seg):
            break
        resultado.append(seg)
    return "/".join(resultado[:2]) if len(resultado) >= 2 else resultado[0] if resultado else ""


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE METADATOS
# ---------------------------------------------------------------------------

def extraer_meta(soup: BeautifulSoup, propiedad: str) -> str:
    """
    Busca <meta property="X"> o <meta name="X"> y devuelve su content.

    La Nación tiene muy buen soporte de Open Graph y metadatos de artículo,
    lo que los hace muy confiables para título, fechas e imagen.
    """
    etiqueta = soup.find("meta", property=propiedad) or soup.find(
        "meta", attrs={"name": propiedad}
    )
    return etiqueta.get("content", "") if etiqueta else ""


# ---------------------------------------------------------------------------
# EXTRACCIÓN DEL CUERPO
#
# Del HTML real de LN observado:
#   - El cuerpo editorial suele estar en <section class="article-body"> o
#     <div class="article-body"> (sistema Arc Publishing)
#   - También puede aparecer como <div itemprop="articleBody">
#   - Fallback: <article> genérico
# ---------------------------------------------------------------------------

def extraer_cuerpo(soup: BeautifulSoup) -> str:
    contenedor = (
        soup.find("section", class_="article-body")
        or soup.find("div", class_="article-body")
        or soup.find("div", attrs={"itemprop": "articleBody"})
        or soup.find("div", class_="article__body")
        or soup.find("article")
    )
    if not contenedor:
        return ""
    # Limpiar ruido: JS, estilos, figuras, aside, newsletters embebidos
    for tag in contenedor.find_all(["script", "style", "figure", "aside", "nav", "form"]):
        tag.decompose()
    return contenedor.get_text(separator=" ").strip()


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE AUTORES
#
# Lo que vimos en el HTML real de LN:
#
#   1. <meta name="article:author" content="Federico Águila">
#      → la fuente más directa y confiable, está en la cabecera
#
#   2. JSON-LD con "@type": "NewsArticle" y campo "author"
#      → estándar Schema.org, muy confiable
#
#   3. Links /autor/Nombre Apellido/ en el cuerpo del artículo
#      → "Por Federico Águila" con href="/autor/Federico Aguila/"
#
# Orden: meta article:author > JSON-LD > links /autor/
# ---------------------------------------------------------------------------

def _autores_desde_meta(soup: BeautifulSoup) -> list[str]:
    """
    La Nación incluye <meta name="article:author" content="Nombre"> para
    cada autor. Es la fuente más rápida y directa.
    """
    metas = soup.find_all("meta", attrs={"name": "article:author"})
    nombres = [m.get("content", "").strip() for m in metas if m.get("content", "").strip()]
    return nombres


def _autores_desde_ldjson(soup: BeautifulSoup) -> list[str]:
    """Extrae autores del bloque JSON-LD Schema.org."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            datos = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidatos = datos if isinstance(datos, list) else [datos]
        for item in candidatos:
            if not isinstance(item, dict):
                continue
            if item.get("@type") not in ("NewsArticle", "Article", "ReportageNewsArticle"):
                continue
            autor = item.get("author")
            if not autor:
                continue
            if isinstance(autor, dict):
                autor = [autor]
            nombres = [
                a["name"] for a in autor
                if isinstance(a, dict) and a.get("name")
            ]
            if nombres:
                return nombres
    return []


def _autores_desde_links(soup: BeautifulSoup) -> list[str]:
    """
    La Nación pone links de autor con href="/autor/Nombre Apellido/".
    Filtramos por ese patrón de URL para no agarrar otros links.
    """
    autores = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if re.search(r"/autor/", href) and a.get_text(strip=True):
            nombre = a.get_text(strip=True)
            # Limpiar prefijos como "Por " que a veces aparecen
            nombre = re.sub(r"^Por\s+", "", nombre).strip()
            if nombre:
                autores.append(nombre)
    return list(dict.fromkeys(autores))  # deduplicar preservando orden


def extraer_autores(soup: BeautifulSoup) -> list[str]:
    """
    Intenta las tres estrategias en orden de confiabilidad.
    """
    desde_meta = _autores_desde_meta(soup)
    if desde_meta:
        return desde_meta

    desde_ldjson = _autores_desde_ldjson(soup)
    if desde_ldjson:
        return desde_ldjson

    return _autores_desde_links(soup)


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE TEMAS
#
# Del HTML real de LN vimos:
#   - Links con href="/tema/nombre-tid{número}/" en la sección de temas
#     Ej: /tema/javier-milei-tid67207/ → "Javier Milei"
#         /tema/mundial-2026-tid58285/ → "Mundial 2026"
#   - También <meta property="article:tag"> (Open Graph estándar)
#
# El texto del link es el nombre del tema (capitalizado por LN).
# ---------------------------------------------------------------------------

def _es_tema_valido(nombre: str) -> bool:
    letras = [c for c in nombre if c.isalpha()]
    return bool(letras) and len(nombre) <= LONGITUD_MAXIMA_TEMA


def extraer_temas(soup: BeautifulSoup) -> list[str]:
    """
    Estrategias en orden:
      1. Links /tema/*-tid{n}/ → fuente más específica de LN
      2. <meta property="article:tag"> → Open Graph estándar
      3. <meta name="keywords"> → fallback genérico
    """
    # Estrategia 1: links de temas con patrón propio de LN
    temas_links = []
    for a in soup.find_all("a", href=True):
        if re.search(r"/tema/[^/]+-tid\d+/?$", a.get("href", "")):
            nombre = a.get_text(strip=True)
            if _es_tema_valido(nombre):
                temas_links.append(nombre)
    if temas_links:
        return list(dict.fromkeys(temas_links))  # deduplicar

    # Estrategia 2: meta article:tag
    tags_meta = soup.find_all("meta", property="article:tag")
    if tags_meta:
        return [
            m.get("content", "").strip()
            for m in tags_meta
            if _es_tema_valido(m.get("content", "").strip())
        ]

    # Estrategia 3: keywords
    meta_kw = extraer_meta(soup, "keywords")
    if meta_kw:
        return [k.strip() for k in meta_kw.split(",") if _es_tema_valido(k.strip())]

    return []


# ---------------------------------------------------------------------------
# CLASIFICACIÓN DE ORACIONES Y VERIFICACIONES
# (lógica idéntica a Infobae/Clarín: misma taxonomía para Neo4j)
# ---------------------------------------------------------------------------

def clasificar_oracion(oracion: str) -> tuple[str, str]:
    """
    Clasifica una oración en: "cita", "estadistica", o "sin_clasificar".
    Ver parseador_articulo.py de Clarín para la explicación completa.
    """
    tiene_comillas = any(c in oracion for c in ('"', "\u201c", "\u201d", "\u00ab", "\u00bb"))
    palabras = set(oracion.lower().split())
    tiene_verbo = bool(palabras & VERBOS_DECLARACION)
    tiene_estadistica = bool(
        re.search(r"\d+[\.,]?\d*\s*(%|millones?|miles?|mil\b)", oracion, re.IGNORECASE)
    )

    if tiene_comillas or tiene_verbo:
        fuente = ""
        coincidencia = re.search(r"según\s+([\w\s]+?)(?:[,.]|$)", oracion, re.IGNORECASE)
        if coincidencia:
            fuente = coincidencia.group(1).strip()
        return "cita", fuente

    if tiene_estadistica:
        return "estadistica", ""

    return "sin_clasificar", ""


def extraer_verificaciones(cuerpo: str) -> list[Verificacion]:
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
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def parsear_articulo(url: str, delay: float = 2.0) -> ResultadoArticulo:
    """
    Descarga y parsea un artículo completo de La Nación.

    Mismo enfoque que Clarín/Infobae: requests para el HTML estático
    (el contenido editorial está server-side rendered) y BeautifulSoup
    para el parsing. Selenium solo se necesita en el crawler de secciones
    para el infinite scroll.
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
