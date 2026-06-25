from unittest.mock import MagicMock

from scraper.crawleador_seccion import obtener_urls_seccion


def _hacer_enlace(href: str) -> MagicMock:
    """Crea un mock de un elemento <a> de Selenium con un href dado."""
    enlace = MagicMock()
    enlace.get_attribute.return_value = href
    return enlace


# ---------------------------------------------------------------------------
# URLs de prueba: válidas e inválidas
# ---------------------------------------------------------------------------

URLS_VALIDAS = [
    "https://www.clarin.com/politica/titulo-nota_0_AbcXYZ123.html",
    "https://www.clarin.com/mundo/america/otro-titulo_0_Def456.html",
]

URLS_INVALIDAS = [
    "https://www.clarin.com/suscripciones/",
    "https://www.clarin.com/",
    "https://www.clarin.com/noticias/",       # sección, no artículo
    "https://otro-dominio.com/nota_0_x.html", # dominio externo
]


def test_filtra_urls_que_no_son_articulos():
    """Solo deben quedar las URLs que matcheen el patrón de artículo de Clarín."""
    driver = MagicMock()
    driver.find_elements.return_value = [
        _hacer_enlace(u) for u in URLS_VALIDAS + URLS_INVALIDAS
    ]
    # execute_script: primera llamada devuelve altura, segunda None (scroll), tercera misma altura
    driver.execute_script.side_effect = [500, None, 500]

    urls = obtener_urls_seccion(driver, "/politica/", max_articulos=10, delay_scroll=0)

    for u in URLS_VALIDAS:
        assert u in urls
    for u in URLS_INVALIDAS:
        assert u not in urls


def test_respeta_maximo_de_articulos():
    """No debe devolver más URLs que max_articulos."""
    urls_validas = [
        f"https://www.clarin.com/politica/nota-{i}_0_id{i}.html"
        for i in range(30)
    ]
    driver = MagicMock()
    driver.find_elements.return_value = [_hacer_enlace(u) for u in urls_validas]
    driver.execute_script.side_effect = [500, None, 500]

    urls = obtener_urls_seccion(driver, "/politica/", max_articulos=5, delay_scroll=0)

    assert len(urls) <= 5


def test_para_cuando_altura_no_cambia():
    """
    Si la altura de la página no cambia después del scroll, significa que
    no hay más contenido para cargar. El crawleador debe detenerse.
    """
    driver = MagicMock()
    driver.find_elements.return_value = [
        _hacer_enlace("https://www.clarin.com/politica/unica-nota_0_abc.html"),
    ]
    # Altura igual antes y después del scroll → no hay más contenido
    driver.execute_script.side_effect = [300, None, 300]

    obtener_urls_seccion(driver, "/politica/", max_articulos=100, delay_scroll=0)

    # Solo debería haber ejecutado: get_height, scroll, get_height (3 calls)
    assert driver.execute_script.call_count == 3


def test_construye_url_con_barra_inicial():
    """La sección "/politica/" debe expandirse a la URL completa de Clarín."""
    driver = MagicMock()
    driver.find_elements.return_value = []
    driver.execute_script.side_effect = [0, None, 0]

    obtener_urls_seccion(driver, "/politica/", max_articulos=1, delay_scroll=0)

    driver.get.assert_called_once_with("https://www.clarin.com/politica/")


def test_construye_url_sin_barra_inicial():
    """La sección "economia" (sin barra) también debe expandirse correctamente."""
    driver = MagicMock()
    driver.find_elements.return_value = []
    driver.execute_script.side_effect = [0, None, 0]

    obtener_urls_seccion(driver, "economia", max_articulos=1, delay_scroll=0)

    driver.get.assert_called_once_with("https://www.clarin.com/economia")


def test_deduplicacion_de_urls():
    """Si el mismo artículo aparece en múltiples <a> de la página, solo se cuenta una vez."""
    url_repetida = "https://www.clarin.com/politica/nota-repetida_0_xyz.html"
    driver = MagicMock()
    driver.find_elements.return_value = [_hacer_enlace(url_repetida)] * 10
    driver.execute_script.side_effect = [500, None, 500]

    urls = obtener_urls_seccion(driver, "/politica/", max_articulos=50, delay_scroll=0)

    assert urls.count(url_repetida) == 1
