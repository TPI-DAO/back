from fastapi import APIRouter
from sqlalchemy import select

from app import enums as E
from app.database import DB
from app.errors import ReglaNegocioError
from app.models import Reserva
from app.schemas import ReservaCreate, ReservaOut
from app.services import reservas as svc
from app.services.common import obtener

router = APIRouter(prefix="/reservas", tags=["Reservas"])


@router.post("", response_model=ReservaOut, status_code=201, summary="Registrar reserva")
def registrar_reserva(data: ReservaCreate, db: DB):
    return svc.crear_reserva(db, data.socio_id, data.libro_id, data.sede_id)


@router.get("", response_model=list[ReservaOut], summary="Consultar reservas")
def listar_reservas(
    db: DB,
    socio_id: int | None = None,
    libro_id: int | None = None,
    sede_id: int | None = None,
    estado: str | None = None,
):
    stmt = select(Reserva).order_by(Reserva.id.desc())
    if socio_id:
        stmt = stmt.where(Reserva.socio_id == socio_id)
    if libro_id:
        stmt = stmt.where(Reserva.libro_id == libro_id)
    if sede_id:
        stmt = stmt.where(Reserva.sede_id == sede_id)
    if estado:
        try:
            stmt = stmt.where(Reserva.estado_id == E.EstadoReserva[estado.upper()])
        except KeyError:
            raise ReglaNegocioError("estado debe ser ACTIVA, CUMPLIDA o CANCELADA.")
    return db.scalars(stmt).all()


@router.get("/{reserva_id}", response_model=ReservaOut)
def obtener_reserva(reserva_id: int, db: DB):
    return obtener(db, Reserva, reserva_id, "Reserva")


@router.post("/{reserva_id}/cancelar", response_model=ReservaOut, summary="Cancelar reserva")
def cancelar_reserva(reserva_id: int, db: DB):
    return svc.cancelar_reserva(db, reserva_id)
