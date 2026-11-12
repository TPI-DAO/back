from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import enums as E
from app.errors import NoEncontradoError, ReglaNegocioError
from app.models import Ejemplar, Prestamo, Reserva, Sede

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


def sede_tiene_ejemplar_utilizable(db: Session, sede_id: int, libro_id: int) -> bool:
    utilizable = (*ESTADOS_EJEMPLAR_NO_OPERATIVOS, E.EstadoEjemplar.DANADO)
    return bool(
        db.scalar(
            select(func.count())
            .select_from(Ejemplar)
            .where(
                Ejemplar.sede_id == sede_id,
                Ejemplar.libro_id == libro_id,
                Ejemplar.estado_id.notin_(utilizable),
            )
        )
    )


def restaurar_reserva_cumplida(db: Session, prestamo: Prestamo) -> Reserva | None:
    """Devuelve a ACTIVA la reserva que consumió un préstamo que no llegó a entregarse.

    Solo aplica si el socio no tiene ya una reserva activa del mismo libro/sede y existe
    una reserva CUMPLIDA anterior a la solicitud del préstamo (la que se consumió).
    """
    ya_activa = db.scalar(
        select(Reserva.id).where(
            Reserva.socio_id == prestamo.socio_id,
            Reserva.libro_id == prestamo.libro_id,
            Reserva.sede_id == prestamo.sede_origen_id,
            Reserva.estado_id == E.EstadoReserva.ACTIVA,
        )
    )
    if ya_activa:
        return None
    reserva = db.scalar(
        select(Reserva)
        .where(
            Reserva.socio_id == prestamo.socio_id,
            Reserva.libro_id == prestamo.libro_id,
            Reserva.sede_id == prestamo.sede_origen_id,
            Reserva.estado_id == E.EstadoReserva.CUMPLIDA,
            Reserva.fecha <= prestamo.fecha_solicitud,
        )
        .order_by(Reserva.id.desc())
    )
    if reserva is not None:
        reserva.estado_id = E.EstadoReserva.ACTIVA
    return reserva
