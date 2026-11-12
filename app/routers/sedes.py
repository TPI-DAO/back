from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update

from app import enums as E
from app.database import DB
from app.errors import ConflictoError, ReglaNegocioError
from app.models import Prestamo, Remito, Reserva, Sede, Usuario
from app.schemas import SedeCreate, SedeEstadoIn, SedeOut, SedeUpdate
from app.security import CurrentUser, require_admin
from app.services.common import ESTADOS_PRESTAMO_ABIERTOS, obtener

router = APIRouter(prefix="/sedes", tags=["Sedes"])


def _verificar_nombre_libre(db, nombre: str, excluir_id: int | None = None):
    stmt = select(Sede.id).where(func.lower(Sede.nombre) == nombre.lower())
    if excluir_id:
        stmt = stmt.where(Sede.id != excluir_id)
    if db.scalar(stmt):
        raise ConflictoError(f"Ya existe una sede llamada '{nombre}'.")


@router.post("", response_model=SedeOut, status_code=201, summary="Registrar sede")
def registrar_sede(data: SedeCreate, db: DB, _admin: Usuario = Depends(require_admin)):
    _verificar_nombre_libre(db, data.nombre)
    sede = Sede(**data.model_dump())
    db.add(sede)
    db.commit()
    return sede


@router.get("", response_model=list[SedeOut], summary="Consultar sedes")
def listar_sedes(db: DB, _usuario: CurrentUser, estado: str | None = None):
    stmt = select(Sede).order_by(Sede.nombre)
    if estado:
        try:
            stmt = stmt.where(Sede.estado_id == E.EstadoSede[estado.upper()])
        except KeyError:
            raise ReglaNegocioError("estado debe ser ACTIVA o BAJA.")
    return db.scalars(stmt).all()


@router.get("/{sede_id}", response_model=SedeOut)
def obtener_sede(sede_id: int, db: DB, _usuario: CurrentUser):
    return obtener(db, Sede, sede_id, "Sede")


@router.put("/{sede_id}", response_model=SedeOut, summary="Modificar sede")
def modificar_sede(sede_id: int, data: SedeUpdate, db: DB, _admin: Usuario = Depends(require_admin)):
    sede = obtener(db, Sede, sede_id, "Sede")
    cambios = data.model_dump(exclude_unset=True)
    if "nombre" in cambios and cambios["nombre"]:
        _verificar_nombre_libre(db, cambios["nombre"], sede_id)
    for campo, valor in cambios.items():
        setattr(sede, campo, valor)
    db.commit()
    return sede


@router.patch("/{sede_id}/estado", response_model=SedeOut, summary="Dar de alta / baja una sede")
def cambiar_estado_sede(
    sede_id: int, data: SedeEstadoIn, db: DB, _admin: Usuario = Depends(require_admin)
):
    sede = obtener(db, Sede, sede_id, "Sede")
    nuevo = E.EstadoSede[data.estado]
    if nuevo == E.EstadoSede.BAJA:
        prestamos = db.scalar(
            select(func.count())
            .select_from(Prestamo)
            .where(
                Prestamo.estado_id.in_(ESTADOS_PRESTAMO_ABIERTOS),
                (Prestamo.sede_origen_id == sede_id) | (Prestamo.sede_destino_id == sede_id),
            )
        )
        remitos = db.scalar(
            select(func.count())
            .select_from(Remito)
            .where(
                Remito.estado_id.in_([E.EstadoRemito.EMPAQUETADO, E.EstadoRemito.DESPACHADO]),
                (Remito.sede_origen_id == sede_id) | (Remito.sede_destino_id == sede_id),
            )
        )
        if prestamos or remitos:
            raise ReglaNegocioError(
                "No se puede dar de baja la sede: tiene préstamos abiertos o remitos en curso."
            )
        db.execute(
            update(Reserva)
            .where(Reserva.sede_id == sede_id, Reserva.estado_id == E.EstadoReserva.ACTIVA)
            .values(estado_id=E.EstadoReserva.CANCELADA)
        )
    sede.estado_id = nuevo
    db.commit()
    return sede
