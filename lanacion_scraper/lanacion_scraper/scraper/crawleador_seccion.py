import re
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL_BASE = "https://www.lanacion.com.ar"

# Patrón de URLs de artículos de La Nación.
#
# La Nación usa el sufijo -nid + fecha (DDMMYYYY) como identificador único:
#   https://www.lanacion.com.ar/politica/titulo-nota-nid02072026/
#   https://www.lanacion.com.ar/economia/campo/titulo-largo-nid01072026/
#
# Ese -nidDDMMYYYY al final es la firma característica del CMS Arc Publishing
# que usa LA NACION. Lo distingue de secciones (/politica/), temas (/tema/...),
# autores (/autor/...) y páginas especiales (/suscriptores/, /revistas/, etc.)
PATRON_ARTICULO = re.compile(
    r"https://www\.lanacion\.com\.ar/[a-z0-9\-/]+-nid\d{8}/$"
)


def obtener_urls_seccion(
    driver: webdriver.Chrome,
    seccion: str,
    max_articulos: int = 50,
    delay_scroll: float = 2.0,
) -> list[str]:
    """
    Navega a una sección de La Nación y recolecta URLs de artículos
    mediante scroll infinito.

    La Nación (igual que Clarín e Infobae) usa infinite scroll en sus
    páginas de sección: no hay paginación, el contenido se carga
    dinámicamente con JS a medida que el usuario baja.

    Args:
        driver:        instancia Chrome headless ya inicializada
        seccion:       ruta de sección, ej. "/politica/" o "/economia/"
        max_articulos: cuántas URLs queremos como máximo
        delay_scroll:  segundos de espera entre scrolls para que cargue el JS

    Returns:
        Lista de URLs únicas de artículos, hasta max_articulos.
    """
    url_seccion = (
        f"{URL_BASE}{seccion}" if seccion.startswith("/")
        else f"{URL_BASE}/{seccion}"
    )
    driver.get(url_seccion)
    time.sleep(delay_scroll)

    urls_encontradas: set[str] = set()

    while len(urls_encontradas) < max_articulos:
        enlaces = driver.find_elements(By.TAG_NAME, "a")
        for enlace in enlaces:
            href = enlace.get_attribute("href") or ""
            # Normalizar: agregar barra final si falta (LN a veces omite trailing slash)
            if not href.endswith("/"):
                href = href + "/"
            if PATRON_ARTICULO.match(href):
                urls_encontradas.add(href)

        if len(urls_encontradas) >= max_articulos:
            break

        altura_anterior = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(delay_scroll)
        altura_nueva = driver.execute_script("return document.body.scrollHeight")

        if altura_nueva == altura_anterior:
            break

    return list(urls_encontradas)[:max_articulos]
