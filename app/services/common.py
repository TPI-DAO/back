from sqlalchemy.orm import Session

from app import enums as E
from app.errors import NoEncontradoError, ReglaNegocioError
from app.models import Sede

ESTADOS_PRESTAMO_ABIERTOS = (
    E.EstadoPrestamo.SOLICITADO,
    E.EstadoPrestamo.EN_TRANSITO,
    E.EstadoPrestamo.ACTIVO,
    E.EstadoPrestamo.VENCIDO,
)

ESTADO_EJEMPLAR_POR_FISICO = {
    E.EstadoFisico.BUENO: E.EstadoEjemplar.DISPONIBLE,
    E.EstadoFisico.DANADO: E.EstadoEjemplar.DANADO,
    E.EstadoFisico.EXTRAVIADO: E.EstadoEjemplar.EXTRAVIADO,
    E.EstadoFisico.DESTRUIDO: E.EstadoEjemplar.DESTRUIDO,
}

ESTADOS_EJEMPLAR_NO_OPERATIVOS = (
    E.EstadoEjemplar.BAJA,
    E.EstadoEjemplar.DESTRUIDO,
    E.EstadoEjemplar.EXTRAVIADO,
)


def obtener(db: Session, modelo, id_: int, nombre: str, bloquear: bool = False):
    obj = db.get(modelo, id_, with_for_update=bloquear)
    if obj is None:
        raise NoEncontradoError(f"{nombre} {id_} no encontrado.")
    return obj


def exigir_sede_activa(sede: Sede, rol: str = "") -> None:
    if sede.estado_id != E.EstadoSede.ACTIVA:
        detalle = f" de {rol}" if rol else ""
        raise ReglaNegocioError(
            f"La sede{detalle} '{sede.nombre}' está dada de baja: no admite préstamos, reservas ni envíos."
        )
