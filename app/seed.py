from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enums as E
from app import models as M


def seed_catalogos(db: Session) -> None:
    """Carga/actualiza las tablas de estados a partir de los enums."""
    pares = [
        (M.CatEstadoSede, E.EstadoSede),
        (M.CatEstadoSocio, E.EstadoSocio),
        (M.CatEstadoEjemplar, E.EstadoEjemplar),
        (M.CatEstadoReserva, E.EstadoReserva),
        (M.CatEstadoPrestamo, E.EstadoPrestamo),
        (M.CatEstadoRemito, E.EstadoRemito),
    ]
    for modelo, enum in pares:
        for miembro in enum:
            db.merge(modelo(id=int(miembro), descripcion=miembro.name))
    db.commit()


def seed_demo(db: Session) -> None:
    """Datos de ejemplo con volumen realista para parecer actividad operacional."""
    if db.scalar(select(M.Sede.id).limit(1)):
        return

    now = datetime.now(timezone.utc)
    sedes = [
        M.Sede(nombre="Sede Central", direccion="Av. Colón 100, Córdoba", correo="central@biblio.test", telefono="351-4000001", horarios="Lun-Vie 8-20"),
        M.Sede(nombre="Sede Norte", direccion="Av. Monseñor Pablo Cabrera 2500, Córdoba", correo="norte@biblio.test", telefono="351-4000002", horarios="Lun-Vie 9-18"),
        M.Sede(nombre="Sede Sur", direccion="Av. Fuerza Aérea 3000, Córdoba", correo="sur@biblio.test", telefono="351-4000003", horarios="Lun-Sab 9-17"),
    ]
    socios = [
        M.Socio(dni="30111222", nombre="Ana", apellido="García", telefono="351-1111111"),
        M.Socio(dni="31222333", nombre="Luis", apellido="Pérez", telefono="351-2222222"),
        M.Socio(dni="32333444", nombre="María", apellido="López", telefono="351-3333333"),
        M.Socio(dni="33444555", nombre="Diego", apellido="Fernández", telefono="351-4444444"),
        M.Socio(dni="34555666", nombre="Sofía", apellido="Molina", telefono="351-5555555"),
        M.Socio(dni="35666777", nombre="Ramón", apellido="Torres", telefono="351-6666666"),
    ]
    generos = [
        M.Genero(nombre="Novela"),
        M.Genero(nombre="Ciencia"),
        M.Genero(nombre="Informática"),
        M.Genero(nombre="Historia"),
        M.Genero(nombre="Fantasía"),
    ]
    autores = [
        M.Autor(nombre="Jorge Luis Borges"),
        M.Autor(nombre="Carl Sagan"),
        M.Autor(nombre="Robert C. Martin"),
        M.Autor(nombre="Isabel Allende"),
        M.Autor(nombre="Frank Herbert"),
        M.Autor(nombre="Ada Lovelace"),
    ]
    editoriales = [
        M.Editorial(descripcion="Sudamericana"),
        M.Editorial(descripcion="Planeta"),
        M.Editorial(descripcion="Prentice Hall"),
        M.Editorial(descripcion="Editorial Universitaria"),
        M.Editorial(descripcion="DeBolsillo"),
    ]

    db.add_all(sedes + socios + generos + autores + editoriales)
    db.flush()

    libros_data = [
        ("Ficciones", "9788420633121", 1, 1, 1),
        ("Cosmos", "9788408175186", 2, 2, 2),
        ("Clean Code", "9780132350884", 3, 3, 3),
        ("La casa de los espíritus", "9788408206325", 1, 4, 2),
        ("Dune", "9788445009101", 5, 5, 5),
        ("Historia de la informática", "9789504345550", 3, 6, 4),
        ("El Aleph", "9788420640494", 1, 1, 1),
        ("Pale Blue Dot", "9788499892789", 2, 2, 5),
        ("The Pragmatic Programmer", "9780201616224", 3, 3, 3),
        ("Eva Luna", "9788408067887", 1, 4, 2),
        ("El mesías de Dune", "9788420675672", 5, 5, 5),
        ("Enigma de las máquinas", "9789504521125", 4, 6, 4),
    ]
    libros = []
    for titulo, isbn, genero_idx, autor_idx, editorial_idx in libros_data:
        libro = M.Libro(
            titulo=titulo,
            isbn=isbn,
            genero_id=generos[genero_idx - 1].id,
            autor_id=autores[autor_idx - 1].id,
            editorial_id=editoriales[editorial_idx - 1].id,
        )
        db.add(libro)
        libros.append(libro)
    db.flush()

    ejemplares = []
    for idx, libro in enumerate(libros):
        for sede_idx, sede in enumerate(sedes):
            cantidad = 2 if (idx + sede_idx) % 3 else 1
            for nro in range(cantidad):
                estado = E.EstadoEjemplar.DISPONIBLE
                if idx % 4 == 0 and nro == 0:
                    estado = E.EstadoEjemplar.RESERVADO
                elif idx % 5 == 0 and sede_idx == 2:
                    estado = E.EstadoEjemplar.PRESTADO
                ejemplar = M.Ejemplar(libro_id=libro.id, sede_id=sede.id, estado_id=estado)
                db.add(ejemplar)
                db.flush()
                ejemplar.codigo_inventario = f"INV-{ejemplar.id:06d}"
                ejemplares.append(ejemplar)
    db.flush()

    reservas = [
        M.Reserva(socio_id=socios[0].id, libro_id=libros[0].id, sede_id=sedes[0].id, estado_id=E.EstadoReserva.ACTIVA, fecha=now - timedelta(days=2)),
        M.Reserva(socio_id=socios[1].id, libro_id=libros[2].id, sede_id=sedes[1].id, estado_id=E.EstadoReserva.ACTIVA, fecha=now - timedelta(days=1)),
        M.Reserva(socio_id=socios[2].id, libro_id=libros[4].id, sede_id=sedes[2].id, estado_id=E.EstadoReserva.CUMPLIDA, fecha=now - timedelta(days=12)),
        M.Reserva(socio_id=socios[3].id, libro_id=libros[6].id, sede_id=sedes[0].id, estado_id=E.EstadoReserva.CANCELADA, fecha=now - timedelta(days=8)),
    ]
    db.add_all(reservas)

    ejemplares_disponibles = [ejemplar for ejemplar in ejemplares if ejemplar.estado_id == E.EstadoEjemplar.DISPONIBLE]
    if len(ejemplares_disponibles) >= 4:
        prestamos = [
            M.Prestamo(
                socio_id=socios[0].id,
                libro_id=libros[0].id,
                ejemplar_id=ejemplares_disponibles[0].id,
                sede_origen_id=sedes[0].id,
                sede_destino_id=sedes[1].id,
                estado_id=E.EstadoPrestamo.ACTIVO,
                fecha_solicitud=now - timedelta(days=8),
                fecha_prestamo=now - timedelta(days=7),
                fecha_vencimiento=date.today() + timedelta(days=6),
            ),
            M.Prestamo(
                socio_id=socios[1].id,
                libro_id=libros[3].id,
                ejemplar_id=ejemplares_disponibles[1].id,
                sede_origen_id=sedes[1].id,
                sede_destino_id=sedes[2].id,
                estado_id=E.EstadoPrestamo.ACTIVO,
                fecha_solicitud=now - timedelta(days=12),
                fecha_prestamo=now - timedelta(days=10),
                fecha_vencimiento=date.today() - timedelta(days=2),
            ),
            M.Prestamo(
                socio_id=socios[2].id,
                libro_id=libros[5].id,
                ejemplar_id=ejemplares_disponibles[2].id,
                sede_origen_id=sedes[2].id,
                sede_destino_id=sedes[0].id,
                estado_id=E.EstadoPrestamo.DEVUELTO,
                fecha_solicitud=now - timedelta(days=25),
                fecha_prestamo=now - timedelta(days=21),
                fecha_vencimiento=date.today() - timedelta(days=3),
                fecha_devolucion=now - timedelta(days=2),
            ),
            M.Prestamo(
                socio_id=socios[4].id,
                libro_id=libros[8].id,
                ejemplar_id=ejemplares_disponibles[3].id,
                sede_origen_id=sedes[0].id,
                sede_destino_id=sedes[2].id,
                estado_id=E.EstadoPrestamo.SOLICITADO,
                fecha_solicitud=now - timedelta(days=1),
                fecha_vencimiento=date.today() + timedelta(days=12),
            ),
        ]
        db.add_all(prestamos)
        db.flush()

        for prestamo, estado_fisico, observacion in [
            (prestamos[2], "BUENO", "Devolución en perfecto estado"),
        ]:
            db.add(
                M.Devolucion(
                    prestamo_id=prestamo.id,
                    sede_id=prestamo.sede_destino_id,
                    fecha=now - timedelta(days=2),
                    estado_fisico=estado_fisico,
                    observacion=observacion,
                    dias_atraso=0,
                    multa=0,
                )
            )

    db.commit()
