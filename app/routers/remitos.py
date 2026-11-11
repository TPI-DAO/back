from fastapi import APIRouter
from sqlalchemy import or_, select

from app import enums as E
from app.database import DB
from app.errors import NoEncontradoError, ReglaNegocioError
from app.models import Remito
from app.schemas import DespacharIn, RecibirIn, RemitoCreate, RemitoOut, TrazabilidadOut
from app.services import remitos as svc
from app.services.common import obtener

router = APIRouter(prefix="/remitos", tags=["Remitos"])


@router.post("", response_model=RemitoOut, status_code=201, summary="Generar remito para envío interbibliotecario")
def generar_remito(data: RemitoCreate, db: DB):
    return svc.generar_remito_envio(db, data.prestamo_id, data.observacion)


@router.get("", response_model=list[RemitoOut], summary="Consultar remitos")
def listar_remitos(
    db: DB,
    estado: str | None = None,
    tipo: str | None = None,
    sede_id: int | None = None,
    prestamo_id: int | None = None,
):
    stmt = select(Remito).order_by(Remito.id.desc())
    if estado:
        try:
            stmt = stmt.where(Remito.estado_id == E.EstadoRemito[estado.upper()])
        except KeyError:
            raise ReglaNegocioError("estado inválido. Valores: " + ", ".join(e.name for e in E.EstadoRemito))
    if tipo:
        stmt = stmt.where(Remito.tipo == tipo.upper())
    if sede_id:
        stmt = stmt.where(or_(Remito.sede_origen_id == sede_id, Remito.sede_destino_id == sede_id))
    if prestamo_id:
        stmt = stmt.where(Remito.prestamo_id == prestamo_id)
    return db.scalars(stmt).all()


@router.get("/numero/{numero}/trazabilidad", response_model=TrazabilidadOut, summary="Trazabilidad por nº de remito")
def trazabilidad_por_numero(numero: str, db: DB):
    remito = db.scalar(select(Remito).where(Remito.numero == numero.upper()))
    if remito is None:
        raise NoEncontradoError(f"Remito {numero} no encontrado.")
    return TrazabilidadOut(remito=remito, historial=remito.historial)


@router.get("/{remito_id}", response_model=RemitoOut)
def obtener_remito(remito_id: int, db: DB):
    return obtener(db, Remito, remito_id, "Remito")


@router.get("/{remito_id}/trazabilidad", response_model=TrazabilidadOut, summary="Consultar trazabilidad del remito")
def trazabilidad(remito_id: int, db: DB):
    remito = obtener(db, Remito, remito_id, "Remito")
    return TrazabilidadOut(remito=remito, historial=remito.historial)


@router.post("/{remito_id}/despachar", response_model=RemitoOut, summary="Despachar remito")
def despachar(remito_id: int, db: DB, data: DespacharIn | None = None):
    return svc.despachar(db, remito_id, data.observacion if data else None)


@router.post("/{remito_id}/recibir", response_model=RemitoOut, summary="Recibir remito (con estado físico)")
def recibir(remito_id: int, data: RecibirIn, db: DB):
    return svc.recibir(db, remito_id, data.estado_fisico, data.observacion)
