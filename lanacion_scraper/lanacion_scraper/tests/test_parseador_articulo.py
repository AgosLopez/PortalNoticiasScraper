from unittest.mock import MagicMock, patch

import pytest
import requests as req
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
# HTML de muestra basado en el HTML REAL de La Nación observado en el fetch.
#
# Características reales confirmadas:
#   - <meta name="article:author" content="Nombre"> para autores
#   - <meta property="article:published_time"> para fechas
#   - <meta property="og:title"> y <meta property="og:image">
#   - Links /tema/nombre-tidXXX/ para temas
#   - Links /autor/Nombre/ para autores (fallback)
#   - JSON-LD con @type NewsArticle
# ---------------------------------------------------------------------------

HTML_MUESTRA = """
<html>
<head>
  <meta property="og:title" content="El gobierno anunció la nueva estructura" />
  <meta property="og:image" content="https://www.lanacion.com.ar/resizer/v2/foto.jpg" />
  <meta property="article:published_time" content="2026-07-02T09:11:04.199Z" />
  <meta property="article:modified_time"  content="2026-07-02T10:30:00.000Z" />
  <meta name="article:author" content="Paula Rossi" />
  <meta name="article:author" content="Jaime Rosemberg" />
  <meta property="article:tag" content="Javier Milei" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "El gobierno anunció la nueva estructura",
    "author": [
      {"@type": "Person", "name": "Paula Rossi"},
      {"@type": "Person", "name": "Jaime Rosemberg"}
    ]
  }
  </script>
</head>
<body>
  <h1>El gobierno anunció la nueva estructura</h1>
  <section class="article-body">
    El Presidente firmó el decreto que fija la nueva estructura del Gobierno.
    "Vamos a trabajar para bajar la inflación al 1% mensual", afirmó el ministro según fuentes oficiales.
    La reducción del gasto público alcanzó el 30% en el primer trimestre del año.
  </section>
  <a href="/autor/Paula Rossi/">Paula Rossi</a>
  <a href="/tema/javier-milei-tid67207/">Javier Milei</a>
  <a href="/tema/diego-santilli-tid50096/">Diego Santilli</a>
</body>
</html>
"""

HTML_SIN_META_AUTOR = """
<html>
<head>
  <meta property="og:title" content="Nota sin meta author" />
  <meta property="article:published_time" content="2026-07-01T08:00:00.000Z" />
</head>
<body>
  <h1>Nota sin meta author</h1>
  <div class="article-body">
    Texto de prueba de la nota sin meta author.
    "Esto es una cita importante", declaró el funcionario.
  </div>
  <a href="/autor/Carlos Pagni/">Carlos Pagni</a>
  <a href="/tema/politica-tid123/">Política</a>
</body>
</html>
"""


def _soup(html: str = HTML_MUESTRA) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------------------
# Tests: extraer_seccion
# (basados en URLs reales de LN observadas)
# ---------------------------------------------------------------------------

def test_extraer_seccion_un_nivel():
    url = "https://www.lanacion.com.ar/politica/titulo-nota-nid02072026/"
    assert extraer_seccion(url) == "politica"


def test_extraer_seccion_dos_niveles():
    url = "https://www.lanacion.com.ar/deportes/futbol/titulo-nota-nid28062026/"
    assert extraer_seccion(url) == "deportes/futbol"


def test_extraer_seccion_economia_campo():
    url = "https://www.lanacion.com.ar/economia/campo/titulo-nid01072026/"
    assert extraer_seccion(url) == "economia/campo"


def test_extraer_seccion_url_sin_segmentos():
    url = "https://www.lanacion.com.ar/titulo-nid02072026/"
    assert extraer_seccion(url) == ""


# ---------------------------------------------------------------------------
# Tests: extraer_meta
# ---------------------------------------------------------------------------

def test_extraer_meta_og_title():
    assert extraer_meta(_soup(), "og:title") == "El gobierno anunció la nueva estructura"


def test_extraer_meta_published_time():
    valor = extraer_meta(_soup(), "article:published_time")
    assert "2026-07-02" in valor


def test_extraer_meta_propiedad_inexistente():
    assert extraer_meta(_soup(), "og:nonexistent") == ""


def test_extraer_meta_og_image():
    url_img = extraer_meta(_soup(), "og:image")
    assert "lanacion.com.ar" in url_img


# ---------------------------------------------------------------------------
# Tests: extraer_cuerpo
# ---------------------------------------------------------------------------

def test_extraer_cuerpo_section_article_body():
    cuerpo = extraer_cuerpo(_soup())
    assert "decreto" in cuerpo
    assert len(cuerpo) > 20


def test_extraer_cuerpo_fallback_div_article_body():
    cuerpo = extraer_cuerpo(_soup(HTML_SIN_META_AUTOR))
    assert "sin meta author" in cuerpo


def test_extraer_cuerpo_sin_contenedor():
    html_sin_cuerpo = "<html><body><p>Sin contenedor</p></body></html>"
    resultado = extraer_cuerpo(BeautifulSoup(html_sin_cuerpo, "lxml"))
    assert isinstance(resultado, str)


# ---------------------------------------------------------------------------
# Tests: extraer_autores
# Caso clave de LN: <meta name="article:author"> es la fuente primaria
# ---------------------------------------------------------------------------

def test_extraer_autores_desde_meta_article_author():
    """La Nación pone los autores en <meta name='article:author'> — fuente primaria."""
    autores = extraer_autores(_soup())
    assert "Paula Rossi" in autores
    assert "Jaime Rosemberg" in autores


def test_extraer_autores_multiples_desde_meta():
    """Dos <meta name='article:author'> distintos deben dar dos autores."""
    autores = extraer_autores(_soup())
    assert len(autores) == 2


def test_extraer_autores_desde_links_cuando_no_hay_meta():
    """Sin meta, cae al fallback de links /autor/."""
    autores = extraer_autores(_soup(HTML_SIN_META_AUTOR))
    assert "Carlos Pagni" in autores


def test_extraer_autores_sin_datos():
    html_sin_autor = "<html><body><p>Sin autor</p></body></html>"
    assert extraer_autores(BeautifulSoup(html_sin_autor, "lxml")) == []


# ---------------------------------------------------------------------------
# Tests: extraer_temas
# Caso clave de LN: links /tema/nombre-tidXXX/ es la fuente primaria
# ---------------------------------------------------------------------------

def test_extraer_temas_desde_links_tid():
    """La Nación usa links /tema/nombre-tidXXX/ como fuente primaria de temas."""
    temas = extraer_temas(_soup())
    assert "Javier Milei" in temas
    assert "Diego Santilli" in temas


def test_extraer_temas_no_incluye_links_no_tema():
    """Links que no sean /tema/...-tid/ no deben aparecer como temas."""
    temas = extraer_temas(_soup())
    assert "Paula Rossi" not in temas  # es /autor/, no /tema/


def test_extraer_temas_fallback_meta_article_tag():
    """Sin links de tema, cae a <meta property='article:tag'>."""
    html = """
    <html><head>
      <meta property="article:tag" content="Economía" />
      <meta property="article:tag" content="FMI" />
    </head><body></body></html>
    """
    temas = extraer_temas(BeautifulSoup(html, "lxml"))
    assert "Economía" in temas
    assert "FMI" in temas


def test_extraer_temas_filtra_nombres_muy_largos():
    nombre_largo = "A" * 60
    html = f'<html><body><a href="/tema/{nombre_largo}-tid999/">{nombre_largo}</a></body></html>'
    assert extraer_temas(BeautifulSoup(html, "lxml")) == []


# ---------------------------------------------------------------------------
# Tests: clasificar_oracion
# ---------------------------------------------------------------------------

def test_clasificar_cita_con_afirmo():
    tipo, _ = clasificar_oracion('"Vamos a bajar la inflación", afirmó el ministro.')
    assert tipo == "cita"


def test_clasificar_cita_extrae_fuente_segun():
    tipo, fuente = clasificar_oracion("La medida fue confirmada según fuentes oficiales.")
    assert tipo == "cita"
    assert "fuentes oficiales" in fuente


def test_clasificar_estadistica_con_porcentaje():
    tipo, _ = clasificar_oracion("El gasto cayó un 30% en el primer trimestre.")
    assert tipo == "estadistica"


def test_clasificar_estadistica_con_millones():
    tipo, _ = clasificar_oracion("El déficit alcanzó los 500 millones de pesos.")
    assert tipo == "estadistica"


def test_clasificar_sin_clasificar():
    tipo, _ = clasificar_oracion("El presidente firmó el decreto en la Casa Rosada.")
    assert tipo == "sin_clasificar"


# ---------------------------------------------------------------------------
# Tests: extraer_verificaciones
# ---------------------------------------------------------------------------

def test_extraer_verificaciones_genera_lista():
    cuerpo = (
        "El Presidente firmó el decreto que fija la nueva estructura del Gobierno. "
        '"Vamos a trabajar para bajar la inflación", afirmó el ministro según fuentes oficiales. '
        "La reducción del gasto público alcanzó el 30% en el primer trimestre del año."
    )
    verificaciones = extraer_verificaciones(cuerpo)
    assert len(verificaciones) >= 2
    tipos = {v.tipo for v in verificaciones}
    assert "cita" in tipos or "estadistica" in tipos


def test_extraer_verificaciones_cuerpo_vacio():
    assert extraer_verificaciones("") == []


# ---------------------------------------------------------------------------
# Tests: parsear_articulo (mock de requests)
# ---------------------------------------------------------------------------

def test_parsear_articulo_integra_todos_los_campos(mocker):
    respuesta_mock = MagicMock()
    respuesta_mock.text = HTML_MUESTRA
    respuesta_mock.raise_for_status = MagicMock()
    mocker.patch("scraper.parseador_articulo.requests.get", return_value=respuesta_mock)
    mocker.patch("scraper.parseador_articulo.time.sleep")

    url = "https://www.lanacion.com.ar/politica/titulo-nota-nid02072026/"
    resultado = parsear_articulo(url, delay=0)

    assert resultado.noticia.titulo == "El gobierno anunció la nueva estructura"
    assert resultado.noticia.seccion == "politica"
    assert "lanacion.com.ar" in resultado.noticia.imagen_portada
    assert len(resultado.autores) == 2
    assert len(resultado.temas) >= 1
    assert resultado.noticia.noticia_id != ""


def test_parsear_articulo_error_http_propaga(mocker):
    respuesta_mock = MagicMock()
    respuesta_mock.raise_for_status.side_effect = req.exceptions.HTTPError("404")
    mocker.patch("scraper.parseador_articulo.requests.get", return_value=respuesta_mock)
    mocker.patch("scraper.parseador_articulo.time.sleep")

    with pytest.raises(req.exceptions.HTTPError):
        parsear_articulo("https://www.lanacion.com.ar/politica/nota-inexistente-nid99999999/", delay=0)
