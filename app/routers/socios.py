from fastapi import APIRouter
from sqlalchemy import or_, select

from app import enums as E
from app.database import DB
from app.errors import ConflictoError, ReglaNegocioError
from app.models import Socio
from app.schemas import SocioCreate, SocioEstadoIn, SocioOut, SocioUpdate
from app.services.common import obtener

router = APIRouter(prefix="/socios", tags=["Socios"])


def _verificar_dni_libre(db, dni: str, excluir_id: int | None = None):
    stmt = select(Socio.id).where(Socio.dni == dni)
    if excluir_id:
        stmt = stmt.where(Socio.id != excluir_id)
    if db.scalar(stmt):
        raise ConflictoError(f"Ya existe un socio con DNI {dni}.")


@router.post("", response_model=SocioOut, status_code=201, summary="Registrar socio")
def registrar_socio(data: SocioCreate, db: DB):
    _verificar_dni_libre(db, data.dni)
    socio = Socio(**data.model_dump())
    db.add(socio)
    db.commit()
    return socio


@router.get("", response_model=list[SocioOut], summary="Consultar socios")
def listar_socios(db: DB, q: str | None = None, estado: str | None = None):
    stmt = select(Socio).order_by(Socio.apellido, Socio.nombre)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Socio.nombre.ilike(like), Socio.apellido.ilike(like), Socio.dni.ilike(like)))
    if estado:
        try:
            stmt = stmt.where(Socio.estado_id == E.EstadoSocio[estado.upper()])
        except KeyError:
            raise ReglaNegocioError("estado debe ser HABILITADO o INHABILITADO.")
    return db.scalars(stmt).all()


@router.get("/{socio_id}", response_model=SocioOut)
def obtener_socio(socio_id: int, db: DB):
    return obtener(db, Socio, socio_id, "Socio")


@router.put("/{socio_id}", response_model=SocioOut, summary="Modificar socio")
def modificar_socio(socio_id: int, data: SocioUpdate, db: DB):
    socio = obtener(db, Socio, socio_id, "Socio")
    cambios = data.model_dump(exclude_unset=True)
    if cambios.get("dni"):
        _verificar_dni_libre(db, cambios["dni"], socio_id)
    for campo, valor in cambios.items():
        setattr(socio, campo, valor)
    db.commit()
    return socio


@router.patch("/{socio_id}/estado", response_model=SocioOut, summary="Habilitar / inhabilitar socio")
def cambiar_estado_socio(socio_id: int, data: SocioEstadoIn, db: DB):
    socio = obtener(db, Socio, socio_id, "Socio")
    socio.estado_id = E.EstadoSocio[data.estado]
    db.commit()
    return socio
