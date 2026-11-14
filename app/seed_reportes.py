"""Carga adicional y explícita para visualizar reportes en una base existente.

Ejecutar: docker compose exec -T api python -m app.seed_reportes
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enums as E
from app import models as M
from app.database import SessionLocal
from app.utils import utcnow


ISBN_DEMO = "DEMO-REPORTES-01"


def seed_reportes(db: Session) -> bool:
    """Agrega un lote atómico, sin modificar datos existentes ni repetirlo."""
    if db.scalar(select(M.Libro.id).where(M.Libro.isbn == ISBN_DEMO)):
        return False

    sedes = list(db.scalars(select(M.Sede).where(
        M.Sede.estado_id == E.EstadoSede.ACTIVA
    ).order_by(M.Sede.id).limit(3)))
    if len(sedes) < 2:
        raise ValueError("Se necesitan al menos dos sedes activas para cargar los reportes.")

    genero = db.scalars(select(M.Genero).order_by(M.Genero.id)).first()
    autor = db.scalars(select(M.Autor).order_by(M.Autor.id)).first()
    editorial = db.scalars(select(M.Editorial).order_by(M.Editorial.id)).first()
    if not all((genero, autor, editorial)):
        raise ValueError("Se necesitan género, autor y editorial en el catálogo.")

    libros = [
        M.Libro(
            titulo=f"{titulo} (demo reportes)",
            isbn=f"DEMO-REPORTES-{index + 1:02d}",
            genero_id=genero.id,
            autor_id=autor.id,
            editorial_id=editorial.id,
        )
        for index, titulo in enumerate([
            "Arquitectura de aplicaciones", "Patrones de diseño",
            "Bases de datos", "Programación orientada a objetos",
        ])
    ]
    nombres = ["Lucía", "Mateo", "Valentina", "Joaquín", "Camila",
               "Nicolás", "Martina", "Tomás", "Julieta"]
    socios = [
        M.Socio(dni=f"DEMO-RPT-{index + 1:02d}", nombre=nombre, apellido="Demo Reportes")
        for index, nombre in enumerate(nombres)
    ]
    db.add_all(libros + socios)
    db.flush()

    ejemplares = {}
    for libro_index, libro in enumerate(libros):
        for sede_index, sede in enumerate(sedes):
            copias = []
            for copia in range(3 + sede_index):
                ejemplar = M.Ejemplar(
                    libro_id=libro.id,
                    sede_id=sede.id,
                    codigo_inventario=f"DEMO-RPT-{libro_index}-{sede_index}-{copia}",
                    estado_id=E.EstadoEjemplar.DISPONIBLE,
                )
                db.add(ejemplar)
                copias.append(ejemplar)
            ejemplares[libro_index, sede_index] = copias
    db.flush()

    ahora = utcnow()
    for index, libro_index in enumerate([0, 0, 0, 0, 1, 1, 2, 2, 3]):
        origen_index = index % len(sedes)
        origen = sedes[origen_index]
        destino = sedes[(origen_index + 1) % len(sedes)]
        ejemplar = next(e for e in ejemplares[libro_index, origen_index]
                        if e.estado_id == E.EstadoEjemplar.DISPONIBLE)
        en_transito = index % 3 == 2
        vencido = index % 3 == 1
        solicitud = ahora - timedelta(days=25 + index if vencido else 3 + index)
        salida = solicitud + timedelta(hours=4)
        llegada = salida + timedelta(days=1)
        prestamo = M.Prestamo(
            socio_id=socios[index].id,
            libro_id=libros[libro_index].id,
            ejemplar_id=ejemplar.id,
            sede_origen_id=origen.id,
            sede_destino_id=destino.id,
            estado_id=(E.EstadoPrestamo.EN_TRANSITO if en_transito else
                       E.EstadoPrestamo.VENCIDO if vencido else E.EstadoPrestamo.ACTIVO),
            fecha_solicitud=solicitud,
            fecha_prestamo=None if en_transito else llegada,
            fecha_vencimiento=(None if en_transito else
                               date.today() + timedelta(days=-(index + 1) if vencido else 7)),
        )
        ejemplar.estado_id = (E.EstadoEjemplar.EN_TRANSITO if en_transito
                              else E.EstadoEjemplar.PRESTADO)
        db.add(prestamo)
        db.flush()
        remito = M.Remito(
            numero=f"DEMO-RPT-{index + 1:03d}",
            tipo=E.TipoRemito.ENVIO.value,
            prestamo_id=prestamo.id,
            ejemplar_id=ejemplar.id,
            sede_origen_id=origen.id,
            sede_destino_id=destino.id,
            estado_id=E.EstadoRemito.DESPACHADO if en_transito else E.EstadoRemito.RECIBIDO,
            fecha_empaquetado=solicitud + timedelta(hours=2),
            fecha_salida=salida,
            fecha_llegada=None if en_transito else llegada,
            estado_fisico_recepcion=None if en_transito else E.EstadoFisico.BUENO.value,
        )
        db.add(remito)
        db.flush()
        eventos = [("EMPAQUETADO", remito.fecha_empaquetado), ("DESPACHADO", salida)]
        if not en_transito:
            eventos.append(("RECIBIDO", llegada))
        anterior = None
        for estado, fecha in eventos:
            db.add(M.HistorialRemito(
                remito_id=remito.id, fecha=fecha, estado_anterior=anterior,
                estado_nuevo=estado, observacion="Datos de demostración para reportes",
            ))
            anterior = estado
    db.flush()
    return True


if __name__ == "__main__":
    with SessionLocal.begin() as db:
        creado = seed_reportes(db)
    print("Datos de reportes cargados: 4 libros, 9 socios, 9 préstamos y 9 remitos."
          if creado else "Los datos demo de reportes ya estaban cargados; no se duplicaron.")
