from unittest.mock import MagicMock

from scraper.crawleador_seccion import obtener_urls_seccion


def _hacer_enlace(href: str) -> MagicMock:
    enlace = MagicMock()
    enlace.get_attribute.return_value = href
    return enlace


# URLs válidas de La Nación (con -nidDDMMYYYY al final)
URLS_VALIDAS = [
    "https://www.lanacion.com.ar/politica/titulo-nota-nid02072026/",
    "https://www.lanacion.com.ar/economia/campo/otro-titulo-nid01072026/",
    "https://www.lanacion.com.ar/deportes/futbol/nota-mundial-nid30062026/",
]

# URLs inválidas: secciones, temas, autores, otros dominios
URLS_INVALIDAS = [
    "https://www.lanacion.com.ar/politica/",           # sección, no artículo
    "https://www.lanacion.com.ar/tema/milei-tid67207/", # página de tema
    "https://www.lanacion.com.ar/autor/Carlos Pagni/",  # página de autor
    "https://www.lanacion.com.ar/suscriptores/",        # página especial
    "https://canchallena.lanacion.com.ar/futbol/",      # subdominio distinto
    "https://otro-sitio.com/nota-nid02072026/",         # dominio externo
]


def test_filtra_urls_que_no_son_articulos():
    driver = MagicMock()
    driver.find_elements.return_value = [
        _hacer_enlace(u) for u in URLS_VALIDAS + URLS_INVALIDAS
    ]
    driver.execute_script.side_effect = [500, None, 500]

    urls = obtener_urls_seccion(driver, "/politica/", max_articulos=10, delay_scroll=0)

    for u in URLS_VALIDAS:
        assert u in urls
    for u in URLS_INVALIDAS:
        assert u not in urls


def test_respeta_maximo_de_articulos():
    urls_validas = [
        f"https://www.lanacion.com.ar/politica/nota-{i}-nid0207202{i % 10}/"
        for i in range(30)
    ]
    driver = MagicMock()
    driver.find_elements.return_value = [_hacer_enlace(u) for u in urls_validas]
    driver.execute_script.side_effect = [500, None, 500]

    urls = obtener_urls_seccion(driver, "/politica/", max_articulos=5, delay_scroll=0)
    assert len(urls) <= 5


def test_para_cuando_no_hay_mas_contenido():
    driver = MagicMock()
    driver.find_elements.return_value = [
        _hacer_enlace("https://www.lanacion.com.ar/politica/unica-nota-nid02072026/"),
    ]
    driver.execute_script.side_effect = [300, None, 300]

    obtener_urls_seccion(driver, "/politica/", max_articulos=100, delay_scroll=0)
    assert driver.execute_script.call_count == 3


def test_construye_url_con_barra_inicial():
    driver = MagicMock()
    driver.find_elements.return_value = []
    driver.execute_script.side_effect = [0, None, 0]

    obtener_urls_seccion(driver, "/politica/", max_articulos=1, delay_scroll=0)
    driver.get.assert_called_once_with("https://www.lanacion.com.ar/politica/")


def test_construye_url_sin_barra_inicial():
    driver = MagicMock()
    driver.find_elements.return_value = []
    driver.execute_script.side_effect = [0, None, 0]

    obtener_urls_seccion(driver, "economia", max_articulos=1, delay_scroll=0)
    driver.get.assert_called_once_with("https://www.lanacion.com.ar/economia")


def test_normaliza_urls_sin_trailing_slash():
    """LN a veces sirve links sin barra final; el crawler debe normalizarlos."""
    driver = MagicMock()
    # URL sin trailing slash
    driver.find_elements.return_value = [
        _hacer_enlace("https://www.lanacion.com.ar/politica/titulo-nid02072026"),
    ]
    driver.execute_script.side_effect = [500, None, 500]

    urls = obtener_urls_seccion(driver, "/politica/", max_articulos=10, delay_scroll=0)
    # Debe aparecer con trailing slash normalizado
    assert "https://www.lanacion.com.ar/politica/titulo-nid02072026/" in urls


def test_deduplicacion_de_urls():
    url_repetida = "https://www.lanacion.com.ar/politica/nota-repetida-nid02072026/"
    driver = MagicMock()
    driver.find_elements.return_value = [_hacer_enlace(url_repetida)] * 10
    driver.execute_script.side_effect = [500, None, 500]

    urls = obtener_urls_seccion(driver, "/politica/", max_articulos=50, delay_scroll=0)
    assert urls.count(url_repetida) == 1
