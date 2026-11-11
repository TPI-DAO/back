from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import enums as E
from app.models import Ejemplar, Libro, Reserva, Sede
from app.services.common import ESTADOS_EJEMPLAR_NO_OPERATIVOS


def consultar_disponibilidad(
    db: Session,
    *,
    libro_id: int | None = None,
    sede_id: int | None = None,
    titulo: str | None = None,
    solo_disponibles: bool = False,
) -> list[dict]:
    en_transito = [E.EstadoEjemplar.EN_TRANSITO, E.EstadoEjemplar.PENDIENTE_RETORNO]
    stmt = (
        select(
            Libro.id.label("libro_id"),
            Libro.titulo,
            Libro.isbn,
            Sede.id.label("sede_id"),
            Sede.nombre.label("sede"),
            func.count(Ejemplar.id).label("total"),
            func.count(Ejemplar.id).filter(Ejemplar.estado_id == E.EstadoEjemplar.DISPONIBLE).label("disponibles"),
            func.count(Ejemplar.id).filter(Ejemplar.estado_id == E.EstadoEjemplar.PRESTADO).label("prestados"),
            func.count(Ejemplar.id).filter(Ejemplar.estado_id.in_(en_transito)).label("en_transito"),
        )
        .select_from(Libro)
        .join(Ejemplar, Ejemplar.libro_id == Libro.id)
        .join(Sede, Sede.id == Ejemplar.sede_id)
        .where(Ejemplar.estado_id.notin_(ESTADOS_EJEMPLAR_NO_OPERATIVOS))
        .group_by(Libro.id, Libro.titulo, Libro.isbn, Sede.id, Sede.nombre)
        .order_by(Sede.nombre, Libro.titulo)
    )
    if libro_id:
        stmt = stmt.where(Libro.id == libro_id)
    if sede_id:
        stmt = stmt.where(Sede.id == sede_id)
    if titulo:
        stmt = stmt.where(Libro.titulo.ilike(f"%{titulo}%"))

    reservas = {
        (r.libro_id, r.sede_id): r.n
        for r in db.execute(
            select(Reserva.libro_id, Reserva.sede_id, func.count(Reserva.id).label("n"))
            .where(Reserva.estado_id == E.EstadoReserva.ACTIVA)
            .group_by(Reserva.libro_id, Reserva.sede_id)
        )
    }
    filas = []
    for r in db.execute(stmt):
        res = reservas.get((r.libro_id, r.sede_id), 0)
        fila = {
            "libro_id": r.libro_id,
            "titulo": r.titulo,
            "isbn": r.isbn,
            "sede_id": r.sede_id,
            "sede": r.sede,
            "total_ejemplares": r.total,
            "disponibles": r.disponibles,
            "prestados": r.prestados,
            "en_transito": r.en_transito,
            "reservas_activas": res,
            "disponibles_netos": max(0, r.disponibles - res),
        }
        if solo_disponibles and fila["disponibles_netos"] == 0:
            continue
        filas.append(fila)
    return filas
