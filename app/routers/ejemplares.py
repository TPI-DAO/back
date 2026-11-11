from fastapi import APIRouter
from sqlalchemy import select

from app import enums as E
from app.database import DB
from app.errors import ConflictoError, ReglaNegocioError
from app.models import Ejemplar, Libro, Sede
from app.schemas import EjemplarCreate, EjemplarOut, EjemplarUpdate
from app.services.common import exigir_sede_activa, obtener

router = APIRouter(prefix="/ejemplares", tags=["Ejemplares"])


def _verificar_codigo_libre(db, codigo: str, excluir_id: int | None = None):
    stmt = select(Ejemplar.id).where(Ejemplar.codigo_inventario == codigo)
    if excluir_id:
        stmt = stmt.where(Ejemplar.id != excluir_id)
    if db.scalar(stmt):
        raise ConflictoError(f"Ya existe un ejemplar con código de inventario {codigo}.")


@router.post("", response_model=EjemplarOut, status_code=201, summary="Registrar ejemplar")
def registrar_ejemplar(data: EjemplarCreate, db: DB):
    obtener(db, Libro, data.libro_id, "Libro")
    sede = obtener(db, Sede, data.sede_id, "Sede")
    exigir_sede_activa(sede)
    if data.codigo_inventario:
        _verificar_codigo_libre(db, data.codigo_inventario)
    ejemplar = Ejemplar(
        libro_id=data.libro_id, sede_id=data.sede_id, codigo_inventario=data.codigo_inventario
    )
    db.add(ejemplar)
    db.flush()
    if not ejemplar.codigo_inventario:
        ejemplar.codigo_inventario = f"EJ-{ejemplar.id:06d}"
    db.commit()
    return ejemplar


@router.get("", response_model=list[EjemplarOut], summary="Consultar ejemplares")
def listar_ejemplares(
    db: DB,
    libro_id: int | None = None,
    sede_id: int | None = None,
    estado: str | None = None,
):
    stmt = select(Ejemplar).order_by(Ejemplar.id)
    if libro_id:
        stmt = stmt.where(Ejemplar.libro_id == libro_id)
    if sede_id:
        stmt = stmt.where(Ejemplar.sede_id == sede_id)
    if estado:
        try:
            stmt = stmt.where(Ejemplar.estado_id == E.EstadoEjemplar[estado.upper()])
        except KeyError:
            raise ReglaNegocioError(
                "estado inválido. Valores: " + ", ".join(e.name for e in E.EstadoEjemplar)
            )
    return db.scalars(stmt).all()


@router.get("/{ejemplar_id}", response_model=EjemplarOut)
def obtener_ejemplar(ejemplar_id: int, db: DB):
    return obtener(db, Ejemplar, ejemplar_id, "Ejemplar")


@router.put("/{ejemplar_id}", response_model=EjemplarOut, summary="Modificar ejemplar")
def modificar_ejemplar(ejemplar_id: int, data: EjemplarUpdate, db: DB):
    ejemplar = obtener(db, Ejemplar, ejemplar_id, "Ejemplar", bloquear=True)
    cambios = data.model_dump(exclude_unset=True)
    if ejemplar.estado_id not in (E.EstadoEjemplar.DISPONIBLE, E.EstadoEjemplar.DANADO):
        raise ReglaNegocioError(
            f"Solo se pueden modificar ejemplares DISPONIBLE o DANADO (estado actual: {ejemplar.estado})."
        )
    if cambios.get("sede_id"):
        exigir_sede_activa(obtener(db, Sede, cambios["sede_id"], "Sede"))
    if cambios.get("codigo_inventario"):
        _verificar_codigo_libre(db, cambios["codigo_inventario"], ejemplar_id)
    if "estado" in cambios and cambios["estado"]:
        ejemplar.estado_id = E.EstadoEjemplar[cambios.pop("estado")]
    else:
        cambios.pop("estado", None)
    for campo, valor in cambios.items():
        setattr(ejemplar, campo, valor)
    db.commit()
    return ejemplar


@router.post("/{ejemplar_id}/baja", response_model=EjemplarOut, summary="Dar de baja ejemplar")
def dar_de_baja(ejemplar_id: int, db: DB):
    ejemplar = obtener(db, Ejemplar, ejemplar_id, "Ejemplar", bloquear=True)
    if ejemplar.estado_id not in (E.EstadoEjemplar.DISPONIBLE, E.EstadoEjemplar.DANADO):
        raise ReglaNegocioError(
            f"No se puede dar de baja un ejemplar en estado {ejemplar.estado}."
        )
    ejemplar.estado_id = E.EstadoEjemplar.BAJA
    db.commit()
    return ejemplar
