from fastapi import APIRouter
from sqlalchemy import select

from app.database import DB
from app.models import Devolucion
from app.schemas import DevolucionCreate, DevolucionOut
from app.services import devoluciones as svc
from app.services.common import obtener

router = APIRouter(prefix="/devoluciones", tags=["Devoluciones"])


@router.post("", response_model=DevolucionOut, status_code=201, summary="Registrar devolución y estado físico")
def registrar_devolucion(data: DevolucionCreate, db: DB):
    """Calcula la multa si hay atraso. Si el préstamo era interbibliotecario genera el remito de retorno."""
    return svc.registrar_devolucion(db, data.prestamo_id, data.estado_fisico, data.observacion)


@router.get("", response_model=list[DevolucionOut])
def listar_devoluciones(db: DB, prestamo_id: int | None = None):
    stmt = select(Devolucion).order_by(Devolucion.id.desc())
    if prestamo_id:
        stmt = stmt.where(Devolucion.prestamo_id == prestamo_id)
    return db.scalars(stmt).all()


@router.get("/{devolucion_id}", response_model=DevolucionOut)
def obtener_devolucion(devolucion_id: int, db: DB):
    return obtener(db, Devolucion, devolucion_id, "Devolución")
