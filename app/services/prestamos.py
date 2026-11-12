from datetime import date, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import enums as E
from app.config import settings
from app.errors import ConflictoError, ReglaNegocioError
from app.models import Ejemplar, Libro, Prestamo, Reserva, Sede, Socio
from app.services import remitos as remitos_svc
from app.services.common import (
    ESTADOS_PRESTAMO_ABIERTOS,
    exigir_sede_activa,
    obtener,
    restaurar_reserva_cumplida,
)
from app.utils import utcnow


def solicitar_prestamo(
    db: Session, socio_id: int, libro_id: int, sede_origen_id: int, sede_destino_id: int
) -> Prestamo:
    socio = obtener(db, Socio, socio_id, "Socio")
    if socio.estado_id != E.EstadoSocio.HABILITADO:
        raise ReglaNegocioError("El socio está inhabilitado y no puede recibir préstamos.")
    obtener(db, Libro, libro_id, "Libro")
    origen = obtener(db, Sede, sede_origen_id, "Sede origen")
    destino = obtener(db, Sede, sede_destino_id, "Sede destino")
    exigir_sede_activa(origen, "origen")
    exigir_sede_activa(destino, "destino")

    hoy = date.today()
    vencidos = db.scalar(
        select(func.count())
        .select_from(Prestamo)
        .where(
            Prestamo.socio_id == socio_id,
            Prestamo.estado_id.in_([E.EstadoPrestamo.ACTIVO, E.EstadoPrestamo.VENCIDO]),
            Prestamo.fecha_vencimiento < hoy,
        )
    )
    if vencidos:
        raise ReglaNegocioError("El socio tiene préstamos vencidos sin devolver.")

    abiertos = db.scalars(
        select(Prestamo).where(
            Prestamo.socio_id == socio_id, Prestamo.estado_id.in_(ESTADOS_PRESTAMO_ABIERTOS)
        )
    ).all()
    if len(abiertos) >= settings.max_prestamos_por_socio:
        raise ReglaNegocioError(
            f"El socio alcanzó el máximo de {settings.max_prestamos_por_socio} préstamos abiertos."
        )
    if any(p.libro_id == libro_id for p in abiertos):
        raise ConflictoError("El socio ya tiene un préstamo abierto de este libro.")

    # Solo ejemplares que pertenezcan a la sede de origen y estén disponibles
    base = select(Ejemplar).where(
        Ejemplar.libro_id == libro_id,
        Ejemplar.sede_id == origen.id,
        Ejemplar.estado_id == E.EstadoEjemplar.DISPONIBLE,
    )
    n_disp = db.scalar(select(func.count()).select_from(base.subquery()))
    if not n_disp:
        raise ReglaNegocioError("No hay ejemplares disponibles de ese libro en la sede de origen.")

    reserva_propia = db.scalars(
        select(Reserva).where(
            Reserva.socio_id == socio_id,
            Reserva.libro_id == libro_id,
            Reserva.sede_id == origen.id,
            Reserva.estado_id == E.EstadoReserva.ACTIVA,
        )
    ).first()
    if not reserva_propia:
        ajenas = db.scalar(
            select(func.count())
            .select_from(Reserva)
            .where(
                Reserva.libro_id == libro_id,
                Reserva.sede_id == origen.id,
                Reserva.estado_id == E.EstadoReserva.ACTIVA,
                Reserva.socio_id != socio_id,
            )
        )
        if n_disp <= ajenas:
            raise ReglaNegocioError(
                "Los ejemplares disponibles están comprometidos por reservas de otros socios."
            )

    ejemplar = db.scalars(base.order_by(Ejemplar.id).limit(1).with_for_update()).first()
    prestamo = Prestamo(
        socio_id=socio_id,
        libro_id=libro_id,
        ejemplar_id=ejemplar.id,
        sede_origen_id=origen.id,
        sede_destino_id=destino.id,
    )
    if origen.id == destino.id:  # préstamo local: se entrega en el acto
        prestamo.estado_id = E.EstadoPrestamo.ACTIVO
        prestamo.fecha_prestamo = utcnow()
        prestamo.fecha_vencimiento = hoy + timedelta(days=settings.dias_prestamo)
        ejemplar.estado_id = E.EstadoEjemplar.PRESTADO
    else:  # interbibliotecario: queda a la espera del remito
        prestamo.estado_id = E.EstadoPrestamo.SOLICITADO
        ejemplar.estado_id = E.EstadoEjemplar.RESERVADO
    if reserva_propia:
        reserva_propia.estado_id = E.EstadoReserva.CUMPLIDA

    db.add(prestamo)
    db.commit()
    return prestamo


def cancelar_prestamo(db: Session, prestamo_id: int) -> Prestamo:
    prestamo = obtener(db, Prestamo, prestamo_id, "Préstamo")
    if prestamo.estado_id != E.EstadoPrestamo.SOLICITADO:
        raise ConflictoError(
            f"Solo se pueden cancelar préstamos SOLICITADO (estado actual: {prestamo.estado})."
        )
    remitos_svc.cancelar_remito_empaquetado(db, prestamo)
    ejemplar = obtener(db, Ejemplar, prestamo.ejemplar_id, "Ejemplar", bloquear=True)
    ejemplar.estado_id = E.EstadoEjemplar.DISPONIBLE
    prestamo.estado_id = E.EstadoPrestamo.CANCELADO
    restaurar_reserva_cumplida(db, prestamo)
    db.commit()
    return prestamo


def controlar_vencimientos(db: Session) -> int:
    """Marca como VENCIDO los préstamos ACTIVO cuya fecha de vencimiento ya pasó."""
    res = db.execute(
        update(Prestamo)
        .where(
            Prestamo.estado_id == E.EstadoPrestamo.ACTIVO,
            Prestamo.fecha_vencimiento < date.today(),
        )
        .values(estado_id=E.EstadoPrestamo.VENCIDO)
    )
    db.commit()
    return res.rowcount
