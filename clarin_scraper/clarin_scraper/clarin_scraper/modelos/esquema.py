import hashlib
from dataclasses import dataclass


def generar_id(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()[:16]


@dataclass
class Noticia:
    noticia_id: str
    url: str
    titulo: str
    cuerpo: str
    fecha_publicacion: str
    fecha_modificacion: str
    seccion: str
    imagen_portada: str


@dataclass
class Autor:
    autor_id: str
    nombre: str


@dataclass
class Tema:
    tema_id: str
    nombre: str


@dataclass
class Verificacion:
    verificacion_id: str
    texto: str
    tipo: str
    verificado: bool
    fuente_citada: str


@dataclass
class ResultadoArticulo:
    noticia: Noticia
    autores: list[Autor]
    temas: list[Tema]
    verificaciones: list[Verificacion]
