# PortalNoticiasScraper 🗞️

Este repositorio contiene un conjunto de scrapers automatizados diseñados para extraer, procesar y almacenar artículos de los principales portales de noticias argentinos de forma estructurada para el proyecto de investigación acerca de una plataforma inteligente para la detección de tendencias emergentes y desinformación.

Actualmente, el proyecto cuenta con dos módulos principales:
*   **clarin_scraper**: Módulo enfocado en la extracción de contenido del diario Clarín.
*   **lanacion_scraper**: Módulo modular y testeado enfocado en la extracción de contenido del diario La Nación.

---
        
## 🚀 Estructura del Módulo `clarin_scraper`

clarin_scraper/
├── main.py                        # Punto de entrada CLI
├── requirements.txt
├── modelos/
│   └── esquema.py                 # Dataclasses compartidos (idénticos a Infobae)
├── scraper/
│   ├── driver.py                  # Factory de Chrome headless (Selenium)
│   ├── crawleador_seccion.py      # Recolector de URLs por sección (scroll infinito)
│   └── parseador_articulo.py      # Parser de artículos individuales
├── salida/
│   └── escritor_csv.py            # Escritura incremental a CSVs
└── tests/
    ├── test_esquema.py
    ├── test_crawleador_seccion.py
    ├── test_parseador_articulo.py
    └── test_escritor_csv.py

## 🚀 Estructura del Módulo `lanacion_scraper`

lanacion_scraper/
└── lanacion_scraper/              # Código fuente del módulo
    ├── main.py                    # Punto de entrada principal para ejecutar el scraper
    ├── requirements.txt           # Dependencias específicas de La Nación
    ├── modelos/                   # Estructuras de datos
    │   └── esquema.py             # Definición de esquemas de datos del portal
    ├── scraper/                   # Componentes del motor de scraping
    │   ├── driver.py              # Configuración y manejo del navegador
    │   ├── crawleador_seccion.py  # Lógica para recorrer secciones de La Nación
    │   └── parseador_articulo.py  # Extracción de contenido interno de notas
    ├── salida/                    # Gestión de archivos resultantes
    │   └── escritor_csv.py        # Módulo de exportación de datos a formato CSV
    └── tests/                     # Suite de pruebas automatizadas
        ├── test_crawleador_seccion.py
        ├── test_escritor_csv.py  
        ├── test_esquema.py      
        └── test_parseador_articulo.py


## Instalación
pip install -r requirements.txt

## Uso

Desde el directorio `clarin_scraper/`:

# Artículo individual
python main.py --url https://www.clarin.com/politica/titulo_0_id.html

# Sección completa (50 artículos por defecto)
python main.py --seccion /politica/

# Opciones avanzadas
python main.py --seccion /economia/ --max 100 --salida mis_datos --delay 3.0

## CSVs generados

| Archivo              | Nodo/Relación Neo4j               |
|----------------------|-----------------------------------|
| medios.csv           | `(:Medio)`                        |
| noticias.csv         | `(:Noticia)`                      |
| autores.csv          | `(:Autor)`                        |
| temas.csv            | `(:Tema)`                         |
| verificaciones.csv   | `(:Verificacion)`                 |
| rel_publica.csv      | `(Medio)-[:PUBLICA]->(Noticia)`   |
| rel_escrito_por.csv  | `(Noticia)-[:ESCRITO_POR]->(Autor)` |
| rel_menciona.csv     | `(Noticia)-[:MENCIONA]->(Tema)`   |
| rel_verifica.csv     | `(Verificacion)-[:VERIFICA]->(Noticia)` |

## Compatibilidad con el scraper de Infobae

Los CSVs tienen **exactamente los mismos campos** que los del scraper de Infobae. La única diferencia es que `medios.csv` tiene `medio_id = "clarin"` en vez de `"infobae"`. Esto permite cargar ambos datasets en Neo4j y que las noticias de cada medio queden correctamente atribuidas a su nodo `Medio`.

## Tests

cd clarin_scraper
pytest tests/ -v

## Secciones disponibles en Clarín

Algunas secciones útiles para crawlear:

- `/politica/`
- `/economia/`
- `/mundo/`
- `/sociedad/`
- `/deportes/`
- `/tecnologia/`
- `/opinion/`
