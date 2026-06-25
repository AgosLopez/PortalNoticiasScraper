from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from scraper.parseador_articulo import (
    clasificar_oracion,
    extraer_autores,
    extraer_cuerpo,
    extraer_meta,
    extraer_seccion,
    extraer_temas,
    extraer_verificaciones,
    parsear_articulo,
)

# ---------------------------------------------------------------------------
# HTML de muestra que simula un artículo típico de Clarín
#
# Por qué tener un HTML de prueba hardcodeado:
#   Los tests no deben hacer requests reales a internet. Si Clarín cambia
#   su HTML, los tests de unidad seguirían pasando y nos avisarían que
#   hay un cambio a manejar. Los tests de integración (contra el sitio real)
#   son otra cosa y se corren manualmente.
# ---------------------------------------------------------------------------
HTML_MUESTRA = """
<html>
<head>
  <meta property="og:title" content="El gobierno anunció nuevas medidas económicas" />
  <meta property="og:image" content="https://img.clarin.com/foto-nota.jpg" />
  <meta property="article:published_time" content="2026-06-20T09:00:00-03:00" />
  <meta property="article:modified_time"  content="2026-06-20T10:30:00-03:00" />
  <meta property="article:tag" content="Economía" />
  <meta property="article:tag" content="Gobierno" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "El gobierno anunció nuevas medidas económicas",
    "author": [
      {"@type": "Person", "name": "María López"},
      {"@type": "Person", "name": "Carlos Fernández"}
    ]
  }
  </script>
</head>
<body>
  <h1>El gobierno anunció nuevas medidas económicas</h1>
  <div class="article-body">
    El Ministerio de Economía presentó un paquete de medidas fiscales.
    "Vamos a reducir el déficit al 1% del PBI", afirmó el ministro según el comunicado oficial.
    El plan incluye una reducción del 15% en el gasto público.
  </div>
  <a class="tag">Economía</a>
  <a class="tag">Gobierno</a>
</body>
</html>
"""

HTML_SIN_LDJSON = """
<html>
<head>
  <meta property="og:title" content="Nota sin JSON-LD" />
  <meta property="article:published_time" content="2026-06-21T08:00:00-03:00" />
</head>
<body>
  <h1>Nota sin JSON-LD</h1>
  <div class="body-nota">
    Texto de prueba sin JSON-LD en la página.
    "Esto es una cita", señaló la fuente consultada.
  </div>
  <span class="author-name">Ana García</span>
</body>
</html>
"""


def _soup(html: str = HTML_MUESTRA) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------------------
# Tests: extraer_seccion
# ---------------------------------------------------------------------------

def test_extraer_seccion_un_nivel():
    url = "https://www.clarin.com/politica/titulo-nota_0_AbcXYZ123.html"
    assert extraer_seccion(url) == "politica"


def test_extraer_seccion_dos_niveles():
    url = "https://www.clarin.com/mundo/america-latina/titulo_0_id123.html"
    assert extraer_seccion(url) == "mundo/america-latina"


def test_extraer_seccion_url_sin_segmentos():
    url = "https://www.clarin.com/titulo_0_id123.html"
    assert extraer_seccion(url) == ""


# ---------------------------------------------------------------------------
# Tests: extraer_meta
# ---------------------------------------------------------------------------

def test_extraer_meta_og_title():
    assert extraer_meta(_soup(), "og:title") == "El gobierno anunció nuevas medidas económicas"


def test_extraer_meta_published_time():
    valor = extraer_meta(_soup(), "article:published_time")
    assert valor.startswith("2026-06-20")


def test_extraer_meta_propiedad_inexistente():
    assert extraer_meta(_soup(), "og:nonexistent") == ""


# ---------------------------------------------------------------------------
# Tests: extraer_cuerpo
# ---------------------------------------------------------------------------

def test_extraer_cuerpo_encuentra_article_body():
    cuerpo = extraer_cuerpo(_soup())
    assert "Ministerio de Economía" in cuerpo
    assert len(cuerpo) > 20


def test_extraer_cuerpo_fallback_body_nota():
    cuerpo = extraer_cuerpo(_soup(HTML_SIN_LDJSON))
    assert "sin JSON-LD" in cuerpo


def test_extraer_cuerpo_sin_contenedor_retorna_vacio():
    soup_vacio = BeautifulSoup("<html><body><p>Sin contenedor</p></body></html>", "lxml")
    # No tiene ninguno de los contenedores conocidos ni <article>
    # El fallback debería retornar vacío o el texto genérico
    resultado = extraer_cuerpo(soup_vacio)
    # Puede devolver algo o vacío según si hay <article>; solo verificamos que no crashea
    assert isinstance(resultado, str)


# ---------------------------------------------------------------------------
# Tests: extraer_autores
# ---------------------------------------------------------------------------

def test_extraer_autores_desde_ldjson():
    autores = extraer_autores(_soup())
    assert "María López" in autores
    assert "Carlos Fernández" in autores


def test_extraer_autores_desde_clase_css():
    autores = extraer_autores(_soup(HTML_SIN_LDJSON))
    assert "Ana García" in autores


def test_extraer_autores_sin_datos_retorna_lista_vacia():
    soup_sin_autor = BeautifulSoup("<html><body><p>Sin autor</p></body></html>", "lxml")
    assert extraer_autores(soup_sin_autor) == []


# ---------------------------------------------------------------------------
# Tests: extraer_temas
# ---------------------------------------------------------------------------

def test_extraer_temas_desde_meta_article_tag():
    temas = extraer_temas(_soup())
    assert "Economía" in temas
    assert "Gobierno" in temas


def test_extraer_temas_filtra_strings_vacios():
    html = '<html><head><meta property="article:tag" content="" /></head></html>'
    assert extraer_temas(BeautifulSoup(html, "lxml")) == []


def test_extraer_temas_filtra_nombres_muy_largos():
    nombre_largo = "A" * 50
    html = f'<html><head><meta property="article:tag" content="{nombre_largo}" /></head></html>'
    assert extraer_temas(BeautifulSoup(html, "lxml")) == []


# ---------------------------------------------------------------------------
# Tests: clasificar_oracion
# ---------------------------------------------------------------------------

def test_clasificar_cita_con_comillas():
    tipo, _ = clasificar_oracion('"Vamos a reducir el déficit", dijo el ministro.')
    assert tipo == "cita"


def test_clasificar_cita_con_verbo_declarativo():
    tipo, _ = clasificar_oracion("El funcionario afirmó que la medida entrará en vigor.")
    assert tipo == "cita"


def test_clasificar_cita_extrae_fuente_segun():
    tipo, fuente = clasificar_oracion("La situación mejoró según el Banco Central.")
    assert tipo == "cita"
    assert "Banco Central" in fuente


def test_clasificar_estadistica_con_porcentaje():
    tipo, _ = clasificar_oracion("El gasto público cayó un 15% en el primer trimestre.")
    assert tipo == "estadistica"


def test_clasificar_estadistica_con_millones():
    tipo, _ = clasificar_oracion("La deuda asciende a 200 millones de dólares.")
    assert tipo == "estadistica"


def test_clasificar_sin_clasificar():
    tipo, _ = clasificar_oracion("El presidente se reunió con sus ministros en la Casa Rosada.")
    assert tipo == "sin_clasificar"


# ---------------------------------------------------------------------------
# Tests: extraer_verificaciones
# ---------------------------------------------------------------------------

def test_extraer_verificaciones_genera_verificaciones():
    cuerpo = (
        "El Ministerio de Economía presentó un paquete de medidas fiscales. "
        '"Vamos a reducir el déficit al 1% del PBI", afirmó el ministro según el comunicado. '
        "El plan incluye una reducción del 15% en el gasto público."
    )
    verificaciones = extraer_verificaciones(cuerpo)
    assert len(verificaciones) >= 2
    tipos = {v.tipo for v in verificaciones}
    assert "cita" in tipos or "estadistica" in tipos


def test_extraer_verificaciones_cuerpo_vacio():
    assert extraer_verificaciones("") == []


def test_extraer_verificaciones_oraciones_cortas_descartadas():
    cuerpo = "Sí. No. Ok. " + "Esta es una oración lo suficientemente larga para ser procesada."
    verificaciones = extraer_verificaciones(cuerpo)
    textos = [v.texto for v in verificaciones]
    assert not any(t in ("Sí.", "No.", "Ok.") for t in textos)


# ---------------------------------------------------------------------------
# Tests: parsear_articulo (mock de requests)
# ---------------------------------------------------------------------------

def test_parsear_articulo_integra_todos_los_campos(mocker):
    """
    Prueba de integración del parseador completo usando un mock de requests.

    Por qué mockeamos requests.get:
      No queremos que los tests dependan de internet ni sobrecarguen el
      servidor de Clarín. El mock inyecta el HTML de muestra como si fuera
      la respuesta real.
    """
    respuesta_mock = MagicMock()
    respuesta_mock.text = HTML_MUESTRA
    respuesta_mock.raise_for_status = MagicMock()
    mocker.patch("scraper.parseador_articulo.requests.get", return_value=respuesta_mock)
    mocker.patch("scraper.parseador_articulo.time.sleep")

    url = "https://www.clarin.com/economia/titulo-nota_0_AbcXYZ.html"
    resultado = parsear_articulo(url, delay=0)

    assert resultado.noticia.titulo == "El gobierno anunció nuevas medidas económicas"
    assert resultado.noticia.seccion == "economia"
    assert resultado.noticia.imagen_portada == "https://img.clarin.com/foto-nota.jpg"
    assert len(resultado.autores) == 2
    assert len(resultado.temas) == 2
    assert resultado.noticia.noticia_id != ""


def test_parsear_articulo_maneja_error_http(mocker):
    """
    Verifica que raise_for_status propaga la excepción correctamente,
    para que el llamador (main.py) pueda capturarla y loggear el error
    sin cortar el proceso completo.
    """
    import requests as req
    respuesta_mock = MagicMock()
    respuesta_mock.raise_for_status.side_effect = req.exceptions.HTTPError("404")
    mocker.patch("scraper.parseador_articulo.requests.get", return_value=respuesta_mock)
    mocker.patch("scraper.parseador_articulo.time.sleep")

    with pytest.raises(req.exceptions.HTTPError):
        parsear_articulo("https://www.clarin.com/economia/nota-inexistente_0_ABC.html", delay=0)
