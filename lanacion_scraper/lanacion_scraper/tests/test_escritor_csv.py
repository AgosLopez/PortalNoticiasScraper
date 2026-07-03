import csv
import tempfile
from pathlib import Path

import pytest

from modelos.esquema import Autor, Noticia, ResultadoArticulo, Tema, Verificacion
from salida.escritor_csv import EscritorCSV, MEDIO_ID, MEDIO_NOMBRE


def _hacer_resultado(noticia_id: str = "abc123", titulo: str = "Test") -> ResultadoArticulo:
    return ResultadoArticulo(
        noticia=Noticia(
            noticia_id=noticia_id,
            url=f"https://www.lanacion.com.ar/politica/titulo-{noticia_id}-nid02072026/",
            titulo=titulo,
            cuerpo="Cuerpo de la nota de prueba para verificar el escritor CSV.",
            fecha_publicacion="2026-07-02T09:00:00.000Z",
            fecha_modificacion="2026-07-02T10:00:00.000Z",
            seccion="politica",
            imagen_portada="https://www.lanacion.com.ar/resizer/v2/foto.jpg",
        ),
        autores=[
            Autor(autor_id="autor1", nombre="Paula Rossi"),
            Autor(autor_id="autor2", nombre="Jaime Rosemberg"),
        ],
        temas=[
            Tema(tema_id="tema1", nombre="Javier Milei"),
        ],
        verificaciones=[
            Verificacion(
                verificacion_id="verif1",
                texto="El ministro afirmó que la medida es correcta según fuentes.",
                tipo="cita",
                verificado=False,
                fuente_citada="fuentes",
            ),
        ],
    )


@pytest.fixture
def directorio_temporal():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_crea_medios_csv(directorio_temporal):
    EscritorCSV(directorio_temporal)
    assert (Path(directorio_temporal) / "medios.csv").exists()


def test_medios_csv_contiene_lanacion(directorio_temporal):
    EscritorCSV(directorio_temporal)
    with open(Path(directorio_temporal) / "medios.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert any(fila["medio_id"] == MEDIO_ID for fila in filas)
    assert any(fila["nombre"] == MEDIO_NOMBRE for fila in filas)


def test_medio_id_es_lanacion(directorio_temporal):
    EscritorCSV(directorio_temporal)
    with open(Path(directorio_temporal) / "medios.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert filas[0]["medio_id"] == "lanacion"


def test_guardar_crea_todos_los_csvs(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado())
    archivos = [
        "noticias.csv", "autores.csv", "temas.csv", "verificaciones.csv",
        "rel_publica.csv", "rel_escrito_por.csv", "rel_menciona.csv", "rel_verifica.csv",
    ]
    for archivo in archivos:
        assert (Path(directorio_temporal) / archivo).exists(), f"Falta {archivo}"


def test_noticias_csv_contiene_datos(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado("id001", "Título de prueba"))
    with open(Path(directorio_temporal) / "noticias.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 1
    assert filas[0]["noticia_id"] == "id001"
    assert filas[0]["titulo"] == "Título de prueba"


def test_rel_publica_apunta_a_lanacion(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado())
    with open(Path(directorio_temporal) / "rel_publica.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert filas[0]["medio_id"] == "lanacion"


def test_autores_guardados_correctamente(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado())
    with open(Path(directorio_temporal) / "autores.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    nombres = [f["nombre"] for f in filas]
    assert "Paula Rossi" in nombres
    assert "Jaime Rosemberg" in nombres


def test_no_duplica_noticia(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    resultado = _hacer_resultado("dup001")
    escritor.guardar(resultado)
    escritor.guardar(resultado)
    with open(Path(directorio_temporal) / "noticias.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 1


def test_no_duplica_autor(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado("nota001"))
    escritor.guardar(_hacer_resultado("nota002"))
    with open(Path(directorio_temporal) / "autores.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    ids = [f["autor_id"] for f in filas]
    assert len(ids) == len(set(ids))


def test_rel_escrito_por_si_se_duplica_por_noticia(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado("nota001"))
    escritor.guardar(_hacer_resultado("nota002"))
    with open(Path(directorio_temporal) / "rel_escrito_por.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 4  # 2 noticias × 2 autores


def test_reanuda_sin_duplicar(directorio_temporal):
    escritor1 = EscritorCSV(directorio_temporal)
    escritor1.guardar(_hacer_resultado("nota_previa"))
    escritor2 = EscritorCSV(directorio_temporal)
    escritor2.guardar(_hacer_resultado("nota_previa"))
    with open(Path(directorio_temporal) / "noticias.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 1
