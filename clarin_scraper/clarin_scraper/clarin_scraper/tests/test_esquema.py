from modelos.esquema import generar_id, Noticia, Autor, Tema, Verificacion, ResultadoArticulo


def test_generar_id_retorna_16_chars():
    assert len(generar_id("cualquier texto")) == 16


def test_generar_id_es_determinista():
    """El mismo texto siempre genera el mismo ID."""
    assert generar_id("texto fijo") == generar_id("texto fijo")


def test_generar_id_textos_distintos_dan_ids_distintos():
    assert generar_id("texto A") != generar_id("texto B")


def test_noticia_dataclass():
    n = Noticia(
        noticia_id="abc",
        url="https://www.clarin.com/nota",
        titulo="Título",
        cuerpo="Cuerpo",
        fecha_publicacion="2026-01-01",
        fecha_modificacion="2026-01-02",
        seccion="politica",
        imagen_portada="https://img.clarin.com/foto.jpg",
    )
    assert n.noticia_id == "abc"
    assert n.seccion == "politica"


def test_resultado_articulo_contiene_listas():
    resultado = ResultadoArticulo(
        noticia=Noticia("id", "url", "titulo", "cuerpo", "", "", "", ""),
        autores=[Autor("a1", "Autor Uno")],
        temas=[Tema("t1", "Política")],
        verificaciones=[Verificacion("v1", "texto", "cita", False, "fuente")],
    )
    assert len(resultado.autores) == 1
    assert len(resultado.temas) == 1
    assert len(resultado.verificaciones) == 1
