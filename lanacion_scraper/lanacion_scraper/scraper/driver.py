from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def crear_driver() -> webdriver.Chrome:
    """
    Crea y devuelve un driver de Chrome en modo headless (sin ventana visible).

    Por qué headless: el servidor donde corra esto no tiene pantalla,
    y además es más eficiente en memoria y CPU.

    Por qué estos flags:
      --no-sandbox          → necesario en entornos Linux sin entorno de escritorio
      --disable-dev-shm-usage → evita que Chrome crashee por falta de memoria compartida
      --disable-gpu         → innecesario en headless, lo dejamos por compatibilidad
      --window-size         → algunos sitios renderizan diferente en pantallas chicas;
                              simular 1920x1080 da resultados más reales
    """
    opciones = Options()
    opciones.add_argument("--headless")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--disable-gpu")
    opciones.add_argument("--window-size=1920,1080")
    opciones.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    servicio = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=servicio, options=opciones)
