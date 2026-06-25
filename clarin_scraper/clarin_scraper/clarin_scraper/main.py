import argparse
import sys
from urllib.parse import urlparse

from salida.escritor_csv import EscritorCSV
from scraper.crawleador_seccion import obtener_urls_seccion
from scraper.driver import crear_driver
from scraper.parseador_articulo import parsear_articulo


# ---------------------------------------------------------------------------
# Validación de dominio
#
# Por qué validar: evitar correr el scraper accidentalmente contra una URL
# de otro sitio y meter datos mezclados en los CSVs.
# ---------------------------------------------------------------------------

def _validar_url_clarin(url: str) -> None:
    dominio = urlparse(url).netloc
    if dominio not in ("www.clarin.com", "clarin.com"):
        raise ValueError(f"URL no pertenece a Clarín: {dominio}")


# ---------------------------------------------------------------------------
# Modos de operación
# ---------------------------------------------------------------------------

def procesar_url(url: str, escritor: EscritorCSV, delay: float) -> None:
    """Parsea un artículo individual y lo guarda en CSV."""
    resultado = parsear_articulo(url, delay=delay)
    escritor.guardar(resultado)
    print(f"OK: {resultado.noticia.titulo[:60]}")


def modo_url(url: str, directorio_salida: str, delay: float) -> None:
    """
    Modo artículo único: útil para probar el scraper con una URL concreta
    o para agregar artículos puntuales a la base de datos.
    """
    _validar_url_clarin(url)
    escritor = EscritorCSV(directorio_salida)
    procesar_url(url, escritor, delay)


def modo_seccion(seccion: str, max_articulos: int, directorio_salida: str, delay: float) -> None:
    """
    Modo sección: crawlea una sección entera de Clarín.

    Flujo:
      1. Levanta Chrome headless con Selenium
      2. Navega a la sección y recolecta URLs haciendo scroll
      3. Por cada URL, parsea el artículo con requests+BeautifulSoup
      4. Guarda en CSV; los errores individuales se loggean pero no
         cortan el proceso (para no perder 49 artículos por culpa de 1)
      5. Cierra el driver en el finally (siempre, incluso si hay error)

    Por qué el driver se cierra en finally:
      Chrome headless queda como proceso zombie si no se cierra
      explícitamente. Con finally garantizamos que se libera aunque
      ocurra una excepción.
    """
    driver = crear_driver()
    escritor = EscritorCSV(directorio_salida)
    try:
        urls = obtener_urls_seccion(driver, seccion, max_articulos)
        print(f"Encontradas {len(urls)} URLs en {seccion}")
        for url in urls:
            try:
                procesar_url(url, escritor, delay)
            except Exception as error:
                print(f"ERROR {url}: {error}", file=sys.stderr)
    finally:
        driver.quit()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Punto de entrada del script.

    Interfaz idéntica a la del scraper de Infobae para que el equipo
    pueda ejecutar ambos con los mismos comandos, solo cambiando el nombre
    del script. Ejemplos:

      # Un artículo puntual:
      python main.py --url https://www.clarin.com/politica/titulo_0_id.html

      # Una sección completa (50 artículos por defecto):
      python main.py --seccion /politica/

      # Sección con más artículos y guardado en otro directorio:
      python main.py --seccion /economia/ --max 100 --salida mis_datos
    """
    parser = argparse.ArgumentParser(
        description="Scraper de Clarín para investigación de fake news"
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--url", type=str, help="URL de un artículo individual")
    grupo.add_argument("--seccion", type=str, help="Sección a crawlear (ej: /politica/)")
    parser.add_argument("--max", type=int, default=50, help="Máximo de artículos en modo sección")
    parser.add_argument("--salida", type=str, default="datos", help="Directorio de salida para CSVs")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay entre requests en segundos")
    args = parser.parse_args()

    if args.url:
        modo_url(args.url, args.salida, args.delay)
    else:
        modo_seccion(args.seccion, args.max, args.salida, args.delay)


if __name__ == "__main__":
    main()
