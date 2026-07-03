import csv
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from modelos.esquema import Autor, Noticia, ResultadoArticulo, Tema, Verificacion

MEDIO_ID = "lanacion"
MEDIO_NOMBRE = "La Nación"


class EscritorCSV:
    """
    Idéntico al de Infobae y Clarín, solo cambia MEDIO_ID y MEDIO_NOMBRE.
    Ver escritor_csv.py de Clarín para la documentación completa.
    """

    def __init__(self, directorio_salida: str = "datos") -> None:
        self.directorio = Path(directorio_salida)
        self.directorio.mkdir(parents=True, exist_ok=True)
        self._autores_vistos: set[str] = self._cargar_ids_existentes("autores.csv", "autor_id")
        self._temas_vistos: set[str] = self._cargar_ids_existentes("temas.csv", "tema_id")
        self._noticias_vistas: set[str] = self._cargar_ids_existentes("noticias.csv", "noticia_id")
        self._verificaciones_vistas: set[str] = self._cargar_ids_existentes(
            "verificaciones.csv", "verificacion_id"
        )
        self._inicializar_medios()

    def _cargar_ids_existentes(self, nombre_csv: str, campo_id: str) -> set[str]:
        ruta = self._ruta(nombre_csv)
        if not ruta.exists():
            return set()
        with open(ruta, encoding="utf-8") as f:
            lector = csv.DictReader(f)
            return {fila[campo_id] for fila in lector if campo_id in fila}

    def _ruta(self, nombre: str) -> Path:
        return self.directorio / nombre

    def _es_nuevo(self, nombre: str) -> bool:
        return not self._ruta(nombre).exists()

    @contextmanager
    def _csv(self, nombre: str, campos: list[str]):
        nuevo = self._es_nuevo(nombre)
        with open(self._ruta(nombre), "a", newline="", encoding="utf-8") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=campos)
            if nuevo:
                escritor.writeheader()
            yield escritor

    def _inicializar_medios(self) -> None:
        if self._es_nuevo("medios.csv"):
            with self._csv("medios.csv", ["medio_id", "nombre"]) as escritor:
                escritor.writerow({"medio_id": MEDIO_ID, "nombre": MEDIO_NOMBRE})

    def guardar(self, resultado: ResultadoArticulo) -> None:
        self._guardar_noticia(resultado.noticia)
        self._guardar_rel_publica(resultado.noticia.noticia_id)
        for autor in resultado.autores:
            self._guardar_autor(autor, resultado.noticia.noticia_id)
        for tema in resultado.temas:
            self._guardar_tema(tema, resultado.noticia.noticia_id)
        for verificacion in resultado.verificaciones:
            self._guardar_verificacion(verificacion, resultado.noticia.noticia_id)

    def _guardar_noticia(self, noticia: Noticia) -> None:
        if noticia.noticia_id in self._noticias_vistas:
            return
        self._noticias_vistas.add(noticia.noticia_id)
        campos = [
            "noticia_id", "url", "titulo", "cuerpo",
            "fecha_publicacion", "fecha_modificacion",
            "seccion", "imagen_portada",
        ]
        with self._csv("noticias.csv", campos) as escritor:
            escritor.writerow(asdict(noticia))

    def _guardar_rel_publica(self, noticia_id: str) -> None:
        with self._csv("rel_publica.csv", ["medio_id", "noticia_id"]) as escritor:
            escritor.writerow({"medio_id": MEDIO_ID, "noticia_id": noticia_id})

    def _guardar_autor(self, autor: Autor, noticia_id: str) -> None:
        if autor.autor_id not in self._autores_vistos:
            self._autores_vistos.add(autor.autor_id)
            with self._csv("autores.csv", ["autor_id", "nombre"]) as escritor:
                escritor.writerow(asdict(autor))
        with self._csv("rel_escrito_por.csv", ["noticia_id", "autor_id"]) as escritor:
            escritor.writerow({"noticia_id": noticia_id, "autor_id": autor.autor_id})

    def _guardar_tema(self, tema: Tema, noticia_id: str) -> None:
        if tema.tema_id not in self._temas_vistos:
            self._temas_vistos.add(tema.tema_id)
            with self._csv("temas.csv", ["tema_id", "nombre"]) as escritor:
                escritor.writerow(asdict(tema))
        with self._csv("rel_menciona.csv", ["noticia_id", "tema_id"]) as escritor:
            escritor.writerow({"noticia_id": noticia_id, "tema_id": tema.tema_id})

    def _guardar_verificacion(self, verificacion: Verificacion, noticia_id: str) -> None:
        if verificacion.verificacion_id not in self._verificaciones_vistas:
            self._verificaciones_vistas.add(verificacion.verificacion_id)
            campos = ["verificacion_id", "texto", "tipo", "verificado", "fuente_citada"]
            with self._csv("verificaciones.csv", campos) as escritor:
                escritor.writerow(asdict(verificacion))
        with self._csv("rel_verifica.csv", ["verificacion_id", "noticia_id"]) as escritor:
            escritor.writerow({
                "verificacion_id": verificacion.verificacion_id,
                "noticia_id": noticia_id,
            })
