# ClarinScraper

Scraper de noticias del diario **Clarín** para el proyecto de investigación de fake news. Produce los mismos CSVs que el scraper de Infobae, permitiendo unificar ambos datasets en la misma base de datos Neo4j.

## Estructura del proyecto

```
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
```

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

Desde el directorio `clarin_scraper/`:

```bash
# Artículo individual
python main.py --url https://www.clarin.com/politica/titulo_0_id.html

# Sección completa (50 artículos por defecto)
python main.py --seccion /politica/

# Opciones avanzadas
python main.py --seccion /economia/ --max 100 --salida mis_datos --delay 3.0
```

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

```bash
cd clarin_scraper
pytest tests/ -v
```

## Secciones disponibles en Clarín

Algunas secciones útiles para crawlear:

- `/politica/`
- `/economia/`
- `/mundo/`
- `/sociedad/`
- `/deportes/`
- `/tecnologia/`
- `/opinion/`
