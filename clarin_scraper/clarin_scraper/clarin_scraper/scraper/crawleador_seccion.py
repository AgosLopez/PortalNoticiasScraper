import re
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

URL_BASE = "https://www.clarin.com"

# Patrón de URLs de artículos de Clarín.
# Ejemplos válidos:
#   https://www.clarin.com/politica/nota-ejemplo_0_abcXYZ123.html
#   https://www.clarin.com/mundo/titulo-largo_0_xyz.html
#   https://www.clarin.com/economia/tema/subtema/titulo_0_id.html
#
# El sufijo numérico + guión-bajo + id alfanumérico + .html
# es la firma característica de Clarín. El \w+ al final captura
# el ID único que usan para identificar la nota en su CMS.
PATRON_ARTICULO = re.compile(
    r"https://www\.clarin\.com/[a-z0-9\-/]+_\d+_\w+\.html"
)


def obtener_urls_seccion(
    driver: webdriver.Chrome,
    seccion: str,
    max_articulos: int = 50,
    delay_scroll: float = 2.0,
) -> list[str]:
    """
    Navega a una sección de Clarín y recolecta URLs de artículos haciendo
    scroll automático hacia abajo hasta llenar el cupo o agotar el contenido.

    Por qué scroll en vez de paginación:
      Clarín (como muchos medios modernos) usa "infinite scroll": no hay
      botón de "página 2", sino que el servidor carga más notas a medida
      que el usuario baja. Selenium simula ese comportamiento.

    Args:
        driver:        instancia de Chrome headless ya inicializada
        seccion:       ruta de sección, ej. "/politica/" o "/economia/"
        max_articulos: cuántas URLs queremos como máximo
        delay_scroll:  segundos de espera tras cada scroll (da tiempo al
                       JavaScript de la página a cargar el nuevo contenido)

    Returns:
        Lista de URLs únicas de artículos, hasta max_articulos.
    """
    # Construir URL completa, tolerando que llegue con o sin barra inicial
    url_seccion = (
        f"{URL_BASE}{seccion}" if seccion.startswith("/")
        else f"{URL_BASE}/{seccion}"
    )
    driver.get(url_seccion)
    time.sleep(delay_scroll)

    urls_encontradas: set[str] = set()

    while len(urls_encontradas) < max_articulos:
        # Recorrer todos los <a href="..."> de la página y filtrar los que
        # coincidan con el patrón de artículo de Clarín
        enlaces = driver.find_elements(By.TAG_NAME, "a")
        for enlace in enlaces:
            href = enlace.get_attribute("href") or ""
            if PATRON_ARTICULO.match(href):
                urls_encontradas.add(href)

        if len(urls_encontradas) >= max_articulos:
            break

        # Scroll: guardar altura actual, bajar hasta el fondo, esperar,
        # medir de nuevo. Si la altura no cambió → no hay más contenido.
        altura_anterior = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(delay_scroll)
        altura_nueva = driver.execute_script("return document.body.scrollHeight")

        if altura_nueva == altura_anterior:
            break

    return list(urls_encontradas)[:max_articulos]
