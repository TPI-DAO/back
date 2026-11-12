from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.database import DB
from app.errors import ConflictoError, ReglaNegocioError
from app.models import Autor, Editorial, Ejemplar, Genero, Libro, Usuario
from app.schemas import (
    AutorOut,
    EditorialIn,
    EditorialOut,
    GeneroOut,
    LibroCreate,
    LibroOut,
    LibroUpdate,
    NombreIn,
)
from app.security import CurrentUser, require_admin
from app.services.common import obtener


def _router_catalogo(prefix: str, tag: str, Modelo, campo: str, In, Out) -> APIRouter:
    r = APIRouter(prefix=prefix, tags=[tag])
    columna = getattr(Modelo, campo)

    def _verificar(db, valor: str, excluir_id: int | None = None):
        stmt = select(Modelo.id).where(func.lower(columna) == valor.lower())
        if excluir_id:
            stmt = stmt.where(Modelo.id != excluir_id)
        if db.scalar(stmt):
            raise ConflictoError(f"'{valor}' ya existe en {tag}.")

    @r.get("", response_model=list[Out])
    def listar(db: DB, _usuario: CurrentUser):
        return db.scalars(select(Modelo).order_by(columna)).all()

    @r.post("", response_model=Out, status_code=201)
    def crear(data: In, db: DB, _admin: Usuario = Depends(require_admin)):
        valor = getattr(data, campo)
        _verificar(db, valor)
        obj = Modelo(**{campo: valor})
        db.add(obj)
        db.commit()
        return obj

    @r.get("/{id_}", response_model=Out)
    def ver(id_: int, db: DB, _usuario: CurrentUser):
        return obtener(db, Modelo, id_, tag)

    @r.put("/{id_}", response_model=Out)
    def modificar(id_: int, data: In, db: DB, _admin: Usuario = Depends(require_admin)):
        obj = obtener(db, Modelo, id_, tag)
        valor = getattr(data, campo)
        _verificar(db, valor, id_)
        setattr(obj, campo, valor)
        db.commit()
        return obj

    return r


generos_router = _router_catalogo("/generos", "Géneros", Genero, "nombre", NombreIn, GeneroOut)
autores_router = _router_catalogo("/autores", "Autores", Autor, "nombre", NombreIn, AutorOut)
editoriales_router = _router_catalogo("/editoriales", "Editoriales", Editorial, "descripcion", EditorialIn, EditorialOut)

libros_router = APIRouter(prefix="/libros", tags=["Catálogo de libros"])


def _normalizar_isbn(isbn: str) -> str:
    return isbn.replace("-", "").replace(" ", "").upper()


def _verificar_fks(db, genero_id, autor_id, editorial_id):
    if genero_id is not None:
        obtener(db, Genero, genero_id, "Género")
    if autor_id is not None:
        obtener(db, Autor, autor_id, "Autor")
    if editorial_id is not None:
        obtener(db, Editorial, editorial_id, "Editorial")


def _verificar_isbn_libre(db, isbn: str, excluir_id: int | None = None):
    stmt = select(Libro.id).where(Libro.isbn == isbn)
    if excluir_id:
        stmt = stmt.where(Libro.id != excluir_id)
    if db.scalar(stmt):
        raise ConflictoError(f"Ya existe un libro con ISBN {isbn}.")


@libros_router.post("", response_model=LibroOut, status_code=201, summary="Registrar libro")
def registrar_libro(data: LibroCreate, db: DB, _admin: Usuario = Depends(require_admin)):
    isbn = _normalizar_isbn(data.isbn)
    _verificar_isbn_libre(db, isbn)
    _verificar_fks(db, data.genero_id, data.autor_id, data.editorial_id)
    libro = Libro(**{**data.model_dump(), "isbn": isbn})
    db.add(libro)
    db.commit()
    return libro


@libros_router.get("", response_model=list[LibroOut], summary="Consultar libros")
def listar_libros(
    db: DB,
    _usuario: CurrentUser,
    q: str | None = None,
    autor_id: int | None = None,
    genero_id: int | None = None,
    editorial_id: int | None = None,
):
    stmt = select(Libro).order_by(Libro.titulo)
    if q:
        stmt = stmt.where(Libro.titulo.ilike(f"%{q}%"))
    if autor_id:
        stmt = stmt.where(Libro.autor_id == autor_id)
    if genero_id:
        stmt = stmt.where(Libro.genero_id == genero_id)
    if editorial_id:
        stmt = stmt.where(Libro.editorial_id == editorial_id)
    return db.scalars(stmt).all()


@libros_router.get("/{libro_id}", response_model=LibroOut)
def obtener_libro(libro_id: int, db: DB, _usuario: CurrentUser):
    return obtener(db, Libro, libro_id, "Libro")


@libros_router.put("/{libro_id}", response_model=LibroOut, summary="Modificar libro")
def modificar_libro(
    libro_id: int, data: LibroUpdate, db: DB, _admin: Usuario = Depends(require_admin)
):
    libro = obtener(db, Libro, libro_id, "Libro")
    cambios = data.model_dump(exclude_unset=True)
    if cambios.get("isbn"):
        cambios["isbn"] = _normalizar_isbn(cambios["isbn"])
        _verificar_isbn_libre(db, cambios["isbn"], libro_id)
    _verificar_fks(db, cambios.get("genero_id"), cambios.get("autor_id"), cambios.get("editorial_id"))
    for campo, valor in cambios.items():
        setattr(libro, campo, valor)
    db.commit()
    return libro


@libros_router.delete("/{libro_id}", status_code=204, summary="Eliminar libro")
def eliminar_libro(libro_id: int, db: DB, _admin: Usuario = Depends(require_admin)):
    libro = obtener(db, Libro, libro_id, "Libro")
    if db.scalar(select(func.count()).select_from(Ejemplar).where(Ejemplar.libro_id == libro_id)):
        raise ReglaNegocioError("No se puede eliminar un libro que tiene ejemplares registrados.")
    db.delete(libro)
    db.commit()
