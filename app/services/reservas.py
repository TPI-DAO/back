from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import enums as E
from app.errors import ConflictoError, ReglaNegocioError
from app.models import Ejemplar, Libro, Reserva, Sede, Socio
from app.services.common import ESTADOS_EJEMPLAR_NO_OPERATIVOS, exigir_sede_activa, obtener


def crear_reserva(db: Session, socio_id: int, libro_id: int, sede_id: int) -> Reserva:
    socio = obtener(db, Socio, socio_id, "Socio")
    if socio.estado_id != E.EstadoSocio.HABILITADO:
        raise ReglaNegocioError("El socio está inhabilitado y no puede reservar.")
    obtener(db, Libro, libro_id, "Libro")
    sede = obtener(db, Sede, sede_id, "Sede")
    exigir_sede_activa(sede)

    tiene_stock = db.scalar(
        select(func.count())
        .select_from(Ejemplar)
        .where(
            Ejemplar.libro_id == libro_id,
            Ejemplar.sede_id == sede_id,
            Ejemplar.estado_id.notin_(ESTADOS_EJEMPLAR_NO_OPERATIVOS),
        )
    )
    if not tiene_stock:
        raise ReglaNegocioError("La sede no posee ejemplares operativos de ese libro.")

    duplicada = db.scalar(
        select(Reserva.id).where(
            Reserva.socio_id == socio_id,
            Reserva.libro_id == libro_id,
            Reserva.sede_id == sede_id,
            Reserva.estado_id == E.EstadoReserva.ACTIVA,
        )
    )
    if duplicada:
        raise ConflictoError("El socio ya tiene una reserva activa de ese libro en esa sede.")

    reserva = Reserva(socio_id=socio_id, libro_id=libro_id, sede_id=sede_id)
    db.add(reserva)
    db.commit()
    return reserva


def cancelar_reserva(db: Session, reserva_id: int) -> Reserva:
    reserva = obtener(db, Reserva, reserva_id, "Reserva")
    if reserva.estado_id != E.EstadoReserva.ACTIVA:
        raise ConflictoError(f"Solo se pueden cancelar reservas ACTIVA (estado actual: {reserva.estado}).")
    reserva.estado_id = E.EstadoReserva.CANCELADA
    db.commit()
    return reserva
