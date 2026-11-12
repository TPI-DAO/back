from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.database import DB
from app.models import Devolucion, Prestamo, Usuario
from app.schemas import DevolucionCreate, DevolucionOut
from app.security import CurrentUser, exigir_socio_propio, require_admin, socio_id_de
from app.services import devoluciones as svc
from app.services.common import obtener

router = APIRouter(prefix="/devoluciones", tags=["Devoluciones"])


@router.post("", response_model=DevolucionOut, status_code=201, summary="Registrar devolución y estado físico")
def registrar_devolucion(
    data: DevolucionCreate, db: DB, _admin: Usuario = Depends(require_admin)
):
    """Calcula la multa si hay atraso. Si el préstamo era interbibliotecario genera el remito de retorno."""
    return svc.registrar_devolucion(db, data.prestamo_id, data.estado_fisico, data.observacion)


@router.get("", response_model=list[DevolucionOut])
def listar_devoluciones(db: DB, usuario: CurrentUser, prestamo_id: int | None = None):
    stmt = select(Devolucion).order_by(Devolucion.id.desc())
    if not usuario.es_admin:
        stmt = stmt.join(Prestamo, Prestamo.id == Devolucion.prestamo_id).where(
            Prestamo.socio_id == socio_id_de(usuario)
        )
    if prestamo_id:
        stmt = stmt.where(Devolucion.prestamo_id == prestamo_id)
    return db.scalars(stmt).all()


@router.get("/{devolucion_id}", response_model=DevolucionOut)
def obtener_devolucion(devolucion_id: int, db: DB, usuario: CurrentUser):
    devolucion = obtener(db, Devolucion, devolucion_id, "Devolución")
    exigir_socio_propio(usuario, devolucion.prestamo.socio_id)
    return devolucion
