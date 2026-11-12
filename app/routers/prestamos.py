from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select

from app import enums as E
from app.database import DB
from app.errors import ReglaNegocioError
from app.models import Prestamo, Usuario
from app.schemas import PrestamoCreate, PrestamoOut
from app.security import (
    CurrentUser,
    exigir_socio_propio,
    require_admin,
    socio_id_de,
)
from app.services import prestamos as svc
from app.services.common import obtener

router = APIRouter(prefix="/prestamos", tags=["Préstamos"])


@router.post("", response_model=PrestamoOut, status_code=201, summary="Registrar solicitud de préstamo")
def solicitar_prestamo(data: PrestamoCreate, db: DB, usuario: CurrentUser):
    """Local si sede origen == sede destino (queda ACTIVO); interbibliotecario si difieren (queda SOLICITADO
    hasta que se genere, despache y reciba el remito)."""
    exigir_socio_propio(usuario, data.socio_id)
    return svc.solicitar_prestamo(db, data.socio_id, data.libro_id, data.sede_origen_id, data.sede_destino_id)


@router.get("", response_model=list[PrestamoOut], summary="Consultar préstamos")
def listar_prestamos(
    db: DB,
    usuario: CurrentUser,
    socio_id: int | None = None,
    sede_id: int | None = None,
    estado: str | None = None,
    interbibliotecario: bool | None = None,
):
    stmt = select(Prestamo).order_by(Prestamo.id.desc())
    if not usuario.es_admin:
        stmt = stmt.where(Prestamo.socio_id == socio_id_de(usuario))
    if socio_id:
        stmt = stmt.where(Prestamo.socio_id == socio_id)
    if sede_id:
        stmt = stmt.where(or_(Prestamo.sede_origen_id == sede_id, Prestamo.sede_destino_id == sede_id))
    if estado:
        try:
            stmt = stmt.where(Prestamo.estado_id == E.EstadoPrestamo[estado.upper()])
        except KeyError:
            raise ReglaNegocioError("estado inválido. Valores: " + ", ".join(e.name for e in E.EstadoPrestamo))
    if interbibliotecario is True:
        stmt = stmt.where(Prestamo.sede_origen_id != Prestamo.sede_destino_id)
    elif interbibliotecario is False:
        stmt = stmt.where(Prestamo.sede_origen_id == Prestamo.sede_destino_id)
    return db.scalars(stmt).all()


@router.get("/vencidos", response_model=list[PrestamoOut], summary="Préstamos con fecha de vencimiento superada")
def listar_vencidos(db: DB, usuario: CurrentUser):
    stmt = select(Prestamo).where(
        Prestamo.estado_id.in_([E.EstadoPrestamo.ACTIVO, E.EstadoPrestamo.VENCIDO]),
        Prestamo.fecha_vencimiento < date.today(),
    )
    if not usuario.es_admin:
        stmt = stmt.where(Prestamo.socio_id == socio_id_de(usuario))
    return db.scalars(stmt.order_by(Prestamo.fecha_vencimiento)).all()


@router.post("/controlar-vencimientos", summary="Controlar fechas de vencimiento")
def controlar_vencimientos(db: DB, _admin: Usuario = Depends(require_admin)):
    """Pasa a VENCIDO todos los préstamos ACTIVO cuya fecha de vencimiento ya pasó."""
    return {"prestamos_marcados_vencidos": svc.controlar_vencimientos(db)}


@router.get("/{prestamo_id}", response_model=PrestamoOut)
def obtener_prestamo(prestamo_id: int, db: DB, usuario: CurrentUser):
    prestamo = obtener(db, Prestamo, prestamo_id, "Préstamo")
    exigir_socio_propio(usuario, prestamo.socio_id)
    return prestamo


@router.post("/{prestamo_id}/cancelar", response_model=PrestamoOut, summary="Cancelar solicitud de préstamo")
def cancelar_prestamo(prestamo_id: int, db: DB, usuario: CurrentUser):
    prestamo = obtener(db, Prestamo, prestamo_id, "Préstamo")
    exigir_socio_propio(usuario, prestamo.socio_id)
    return svc.cancelar_prestamo(db, prestamo_id)
