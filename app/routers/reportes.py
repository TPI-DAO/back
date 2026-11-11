from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import desc, extract, func, or_, select
from sqlalchemy.orm import joinedload

from app import enums as E
from app.config import settings
from app.database import DB
from app.models import Devolucion, Ejemplar, Libro, Prestamo, Remito, Sede, Socio
from app.patterns.multa_strategy import obtener_estrategia
from app.services.disponibilidad import consultar_disponibilidad
from app.utils import utcnow

router = APIRouter(prefix="/reportes", tags=["Reportes"])


def _rango(col, desde: date | None, hasta: date | None) -> list:
    conds = []
    if desde:
        conds.append(col >= datetime.combine(desde, time.min, tzinfo=timezone.utc))
    if hasta:
        conds.append(col < datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=timezone.utc))
    return conds


@router.get("/prestamos-activos-y-en-transito", summary="1. Préstamos activos y material en tránsito")
def prestamos_activos_y_en_transito(db: DB, sede_id: int | None = None):
    q = (
        select(Prestamo)
        .options(
            joinedload(Prestamo.socio),
            joinedload(Prestamo.libro),
            joinedload(Prestamo.sede_origen),
            joinedload(Prestamo.sede_destino),
        )
        .where(Prestamo.estado_id.in_([E.EstadoPrestamo.ACTIVO, E.EstadoPrestamo.VENCIDO]))
        .order_by(Prestamo.fecha_vencimiento)
    )
    rq = (
        select(Remito)
        .options(
            joinedload(Remito.ejemplar).joinedload(Ejemplar.libro),
            joinedload(Remito.sede_origen),
            joinedload(Remito.sede_destino),
        )
        .where(Remito.estado_id == E.EstadoRemito.DESPACHADO)
        .order_by(Remito.fecha_salida)
    )
    if sede_id:
        q = q.where(or_(Prestamo.sede_origen_id == sede_id, Prestamo.sede_destino_id == sede_id))
        rq = rq.where(or_(Remito.sede_origen_id == sede_id, Remito.sede_destino_id == sede_id))
    prestamos = db.scalars(q).unique().all()
    remitos = db.scalars(rq).unique().all()
    ahora = utcnow()
    return {
        "totales": {"prestamos_activos": len(prestamos), "material_en_transito": len(remitos)},
        "prestamos_activos": [
            {
                "prestamo_id": p.id,
                "estado": p.estado,
                "socio": f"{p.socio.apellido}, {p.socio.nombre}",
                "libro": p.libro.titulo,
                "sede_origen": p.sede_origen.nombre,
                "sede_destino": p.sede_destino.nombre,
                "interbibliotecario": p.interbibliotecario,
                "fecha_vencimiento": p.fecha_vencimiento,
            }
            for p in prestamos
        ],
        "material_en_transito": [
            {
                "remito": r.numero,
                "tipo": r.tipo,
                "libro": r.ejemplar.libro.titulo,
                "codigo_inventario": r.ejemplar.codigo_inventario,
                "sede_origen": r.sede_origen.nombre,
                "sede_destino": r.sede_destino.nombre,
                "fecha_salida": r.fecha_salida,
                "horas_en_transito": round((ahora - r.fecha_salida).total_seconds() / 3600, 2),
            }
            for r in remitos
        ],
    }


@router.get("/prestamos-vencidos-y-multas", summary="2. Préstamos vencidos y multas acumuladas")
def prestamos_vencidos_y_multas(db: DB):
    hoy = date.today()
    estrategia = obtener_estrategia(settings.multa_estrategia, settings.multa_monto_dia)
    vencidos = db.scalars(
        select(Prestamo)
        .options(joinedload(Prestamo.socio), joinedload(Prestamo.libro), joinedload(Prestamo.sede_destino))
        .where(
            Prestamo.estado_id.in_([E.EstadoPrestamo.ACTIVO, E.EstadoPrestamo.VENCIDO]),
            Prestamo.fecha_vencimiento < hoy,
        )
        .order_by(Prestamo.fecha_vencimiento)
    ).unique().all()

    cobradas = {
        socio_id: monto
        for socio_id, monto in db.execute(
            select(Prestamo.socio_id, func.sum(Devolucion.multa))
            .join(Prestamo, Prestamo.id == Devolucion.prestamo_id)
            .group_by(Prestamo.socio_id)
        )
    }
    total_registrado = db.scalar(select(func.coalesce(func.sum(Devolucion.multa), 0)))

    items, por_socio = [], {}
    for p in vencidos:
        dias = (hoy - p.fecha_vencimiento).days
        multa = estrategia.calcular(dias)
        items.append(
            {
                "prestamo_id": p.id,
                "socio_id": p.socio_id,
                "socio": f"{p.socio.apellido}, {p.socio.nombre}",
                "libro": p.libro.titulo,
                "sede_destino": p.sede_destino.nombre,
                "fecha_vencimiento": p.fecha_vencimiento,
                "dias_atraso": dias,
                "multa_proyectada": multa,
            }
        )
        s = por_socio.setdefault(
            p.socio_id,
            {
                "socio_id": p.socio_id,
                "socio": f"{p.socio.apellido}, {p.socio.nombre}",
                "prestamos_vencidos": 0,
                "multa_pendiente": 0,
                "multa_registrada_en_devoluciones": cobradas.get(p.socio_id, 0),
            },
        )
        s["prestamos_vencidos"] += 1
        s["multa_pendiente"] += multa
    for s in por_socio.values():
        s["multa_acumulada"] = s["multa_pendiente"] + s["multa_registrada_en_devoluciones"]
    return {
        "estrategia_multa": settings.multa_estrategia,
        "total_prestamos_vencidos": len(items),
        "multa_pendiente_total": sum(i["multa_proyectada"] for i in items),
        "multa_registrada_total": total_registrado,
        "por_socio": sorted(por_socio.values(), key=lambda x: -x["multa_acumulada"]),
        "prestamos": items,
    }


@router.get("/libros-mas-solicitados", summary="3. Libros más solicitados para préstamos inter-sedes")
def libros_mas_solicitados(
    db: DB, limit: int = 10, desde: date | None = None, hasta: date | None = None
):
    stmt = (
        select(
            Libro.id.label("libro_id"),
            Libro.titulo,
            Libro.isbn,
            func.count(Prestamo.id).label("solicitudes"),
            func.count(func.distinct(Prestamo.sede_destino_id)).label("sedes_destino_distintas"),
            func.count(func.distinct(Prestamo.socio_id)).label("socios_distintos"),
        )
        .join(Prestamo, Prestamo.libro_id == Libro.id)
        .where(
            Prestamo.sede_origen_id != Prestamo.sede_destino_id,
            Prestamo.estado_id != E.EstadoPrestamo.CANCELADO,
            *_rango(Prestamo.fecha_solicitud, desde, hasta),
        )
        .group_by(Libro.id, Libro.titulo, Libro.isbn)
        .order_by(desc("solicitudes"), Libro.titulo)
        .limit(limit)
    )
    return [dict(r._mapping) for r in db.execute(stmt)]


@router.get("/disponibilidad-por-sede", summary="4. Disponibilidad de catálogo por sede")
def disponibilidad_por_sede(db: DB, sede_id: int | None = None):
    filas = consultar_disponibilidad(db, sede_id=sede_id)
    sedes: dict[int, dict] = {}
    for f in filas:
        s = sedes.setdefault(
            f["sede_id"],
            {"sede_id": f["sede_id"], "sede": f["sede"], "total_ejemplares": 0, "disponibles": 0, "libros": []},
        )
        s["total_ejemplares"] += f["total_ejemplares"]
        s["disponibles"] += f["disponibles"]
        s["libros"].append(
            {k: f[k] for k in ("libro_id", "titulo", "isbn", "total_ejemplares", "disponibles", "prestados", "en_transito", "reservas_activas", "disponibles_netos")}
        )
    for s in sedes.values():
        s["titulos_distintos"] = len(s["libros"])
        s["porcentaje_disponible"] = (
            round(s["disponibles"] / s["total_ejemplares"] * 100, 2) if s["total_ejemplares"] else 0
        )
    return list(sedes.values())


@router.get("/envios-exitosos-e-incidencias", summary="5. Tasa de envíos logísticos exitosos e incidencias")
def envios_exitosos_e_incidencias(db: DB, desde: date | None = None, hasta: date | None = None):
    remitos = db.scalars(
        select(Remito)
        .options(
            joinedload(Remito.ejemplar).joinedload(Ejemplar.libro),
            joinedload(Remito.sede_origen),
            joinedload(Remito.sede_destino),
        )
        .where(
            Remito.estado_id != E.EstadoRemito.CANCELADO,
            *_rango(Remito.fecha_empaquetado, desde, hasta),
        )
    ).unique().all()

    por_estado: dict[str, int] = {}
    for r in remitos:
        por_estado[r.estado] = por_estado.get(r.estado, 0) + 1
    finalizados = [r for r in remitos if r.estado_id in (E.EstadoRemito.RECIBIDO, E.EstadoRemito.INCIDENCIA)]
    exitosos = [
        r for r in finalizados
        if r.estado_id == E.EstadoRemito.RECIBIDO and r.estado_fisico_recepcion == E.EstadoFisico.BUENO.value
    ]
    con_incidencia = [r for r in finalizados if r not in exitosos]
    return {
        "total_remitos": len(remitos),
        "por_estado": por_estado,
        "finalizados": len(finalizados),
        "exitosos": len(exitosos),
        "con_incidencia": len(con_incidencia),
        "tasa_exito_pct": round(len(exitosos) / len(finalizados) * 100, 2) if finalizados else None,
        "tasa_incidencia_pct": round(len(con_incidencia) / len(finalizados) * 100, 2) if finalizados else None,
        "incidencias": [
            {
                "remito": r.numero,
                "tipo": r.tipo,
                "estado_remito": r.estado,
                "estado_fisico": r.estado_fisico_recepcion,
                "libro": r.ejemplar.libro.titulo,
                "sede_origen": r.sede_origen.nombre,
                "sede_destino": r.sede_destino.nombre,
                "fecha_llegada": r.fecha_llegada,
            }
            for r in con_incidencia
        ],
    }


@router.get("/movimiento-ejemplares", summary="6. Movimiento de ejemplares entre sedes")
def movimiento_ejemplares(db: DB, desde: date | None = None, hasta: date | None = None):
    horas = func.avg(extract("epoch", Remito.fecha_llegada - Remito.fecha_salida)) / 3600.0
    filas = db.execute(
        select(
            Remito.sede_origen_id,
            Remito.sede_destino_id,
            func.count(Remito.id).label("envios"),
            func.count(Remito.fecha_llegada).label("recibidos"),
            horas.label("horas_promedio"),
        )
        .where(Remito.fecha_salida.is_not(None), *_rango(Remito.fecha_salida, desde, hasta))
        .group_by(Remito.sede_origen_id, Remito.sede_destino_id)
        .order_by(desc("envios"))
    ).all()
    nombres = {s.id: s.nombre for s in db.scalars(select(Sede))}
    por_sede: dict[int, dict] = {}
    rutas = []
    for f in filas:
        rutas.append(
            {
                "sede_origen": nombres[f.sede_origen_id],
                "sede_destino": nombres[f.sede_destino_id],
                "envios": f.envios,
                "recibidos": f.recibidos,
                "tiempo_promedio_transito_horas": round(float(f.horas_promedio), 2) if f.horas_promedio is not None else None,
            }
        )
        for sid, campo in ((f.sede_origen_id, "enviados"), (f.sede_destino_id, "recibidos")):
            s = por_sede.setdefault(sid, {"sede": nombres[sid], "enviados": 0, "recibidos": 0})
            s[campo] += f.envios if campo == "enviados" else f.recibidos
    return {"rutas": rutas, "resumen_por_sede": list(por_sede.values())}
