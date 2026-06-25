import csv
import tempfile
from pathlib import Path

import pytest

from modelos.esquema import Autor, Noticia, ResultadoArticulo, Tema, Verificacion
from salida.escritor_csv import EscritorCSV, MEDIO_ID, MEDIO_NOMBRE


# ---------------------------------------------------------------------------
# Fixture: resultado de artículo de prueba
# ---------------------------------------------------------------------------

def _hacer_resultado(noticia_id: str = "abc123", titulo: str = "Test") -> ResultadoArticulo:
    return ResultadoArticulo(
        noticia=Noticia(
            noticia_id=noticia_id,
            url=f"https://www.clarin.com/politica/test_{noticia_id}.html",
            titulo=titulo,
            cuerpo="Cuerpo de la nota de prueba para verificar el escritor CSV.",
            fecha_publicacion="2026-06-20T09:00:00-03:00",
            fecha_modificacion="2026-06-20T10:00:00-03:00",
            seccion="politica",
            imagen_portada="https://img.clarin.com/foto.jpg",
        ),
        autores=[
            Autor(autor_id="autor1", nombre="María López"),
            Autor(autor_id="autor2", nombre="Carlos Fernández"),
        ],
        temas=[
            Tema(tema_id="tema1", nombre="Política"),
        ],
        verificaciones=[
            Verificacion(
                verificacion_id="verif1",
                texto="El ministro afirmó que la medida es correcta.",
                tipo="cita",
                verificado=False,
                fuente_citada="",
            ),
        ],
    )


@pytest.fixture
def directorio_temporal():
    """Crea un directorio temporal que se borra al terminar el test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ---------------------------------------------------------------------------
# Tests: creación de archivos
# ---------------------------------------------------------------------------

def test_crea_medios_csv(directorio_temporal):
    EscritorCSV(directorio_temporal)
    assert (Path(directorio_temporal) / "medios.csv").exists()


def test_medios_csv_contiene_clarin(directorio_temporal):
    EscritorCSV(directorio_temporal)
    with open(Path(directorio_temporal) / "medios.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert any(fila["medio_id"] == MEDIO_ID for fila in filas)
    assert any(fila["nombre"] == MEDIO_NOMBRE for fila in filas)


def test_guardar_crea_todos_los_csvs(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado())

    archivos_esperados = [
        "noticias.csv", "autores.csv", "temas.csv", "verificaciones.csv",
        "rel_publica.csv", "rel_escrito_por.csv", "rel_menciona.csv", "rel_verifica.csv",
    ]
    for archivo in archivos_esperados:
        assert (Path(directorio_temporal) / archivo).exists(), f"Falta {archivo}"


# ---------------------------------------------------------------------------
# Tests: contenido correcto
# ---------------------------------------------------------------------------

def test_noticias_csv_contiene_datos(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado("id001", "Título de prueba"))

    with open(Path(directorio_temporal) / "noticias.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 1
    assert filas[0]["noticia_id"] == "id001"
    assert filas[0]["titulo"] == "Título de prueba"


def test_rel_publica_apunta_a_clarin(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado())

    with open(Path(directorio_temporal) / "rel_publica.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert filas[0]["medio_id"] == MEDIO_ID


def test_autores_guardados_correctamente(directorio_temporal):
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado())

    with open(Path(directorio_temporal) / "autores.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    nombres = [f["nombre"] for f in filas]
    assert "María López" in nombres
    assert "Carlos Fernández" in nombres


# ---------------------------------------------------------------------------
# Tests: deduplicación
# ---------------------------------------------------------------------------

def test_no_duplica_noticia(directorio_temporal):
    """Guardar la misma noticia dos veces no debe duplicarla en noticias.csv."""
    escritor = EscritorCSV(directorio_temporal)
    resultado = _hacer_resultado("dup001")
    escritor.guardar(resultado)
    escritor.guardar(resultado)

    with open(Path(directorio_temporal) / "noticias.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 1


def test_no_duplica_autor(directorio_temporal):
    """El mismo autor en dos noticias distintas debe aparecer una sola vez en autores.csv."""
    escritor = EscritorCSV(directorio_temporal)
    r1 = _hacer_resultado("nota001")
    r2 = _hacer_resultado("nota002")
    # Ambas tienen los mismos autores
    escritor.guardar(r1)
    escritor.guardar(r2)

    with open(Path(directorio_temporal) / "autores.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    ids = [f["autor_id"] for f in filas]
    assert len(ids) == len(set(ids)), "Hay autores duplicados en autores.csv"


def test_rel_escrito_por_si_se_duplica_por_noticia(directorio_temporal):
    """Dos noticias con el mismo autor deben generar DOS filas en rel_escrito_por.csv."""
    escritor = EscritorCSV(directorio_temporal)
    escritor.guardar(_hacer_resultado("nota001"))
    escritor.guardar(_hacer_resultado("nota002"))

    with open(Path(directorio_temporal) / "rel_escrito_por.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    # 2 noticias × 2 autores = 4 relaciones
    assert len(filas) == 4


def test_reanuda_sin_duplicar(directorio_temporal):
    """
    Si los CSVs ya existen (de una ejecución anterior), una nueva instancia
    de EscritorCSV debe leer los IDs existentes y no duplicarlos.
    """
    escritor1 = EscritorCSV(directorio_temporal)
    escritor1.guardar(_hacer_resultado("nota_previa"))

    # Nueva instancia, simula reinicio del proceso
    escritor2 = EscritorCSV(directorio_temporal)
    escritor2.guardar(_hacer_resultado("nota_previa"))  # misma noticia

    with open(Path(directorio_temporal) / "noticias.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 1
