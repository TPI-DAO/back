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
    """Datos de ejemplo (solo si la base no tiene sedes)."""
    if db.scalar(select(M.Sede.id).limit(1)):
        return
    sedes = [
        M.Sede(nombre="Sede Central", direccion="Av. Colón 100, Córdoba", correo="central@biblio.test", telefono="351-4000001", horarios="Lun-Vie 8-20"),
        M.Sede(nombre="Sede Norte", direccion="Av. Monseñor Pablo Cabrera 2500, Córdoba", correo="norte@biblio.test", telefono="351-4000002", horarios="Lun-Vie 9-18"),
        M.Sede(nombre="Sede Sur", direccion="Av. Fuerza Aérea 3000, Córdoba", correo="sur@biblio.test", telefono="351-4000003", horarios="Lun-Sab 9-17"),
    ]
    socios = [
        M.Socio(dni="30111222", nombre="Ana", apellido="García", telefono="351-1111111"),
        M.Socio(dni="31222333", nombre="Luis", apellido="Pérez", telefono="351-2222222"),
        M.Socio(dni="32333444", nombre="María", apellido="López", telefono="351-3333333"),
    ]
    generos = [M.Genero(nombre="Novela"), M.Genero(nombre="Ciencia"), M.Genero(nombre="Informática")]
    autores = [M.Autor(nombre="Jorge Luis Borges"), M.Autor(nombre="Carl Sagan"), M.Autor(nombre="Robert C. Martin")]
    editoriales = [M.Editorial(descripcion="Sudamericana"), M.Editorial(descripcion="Planeta"), M.Editorial(descripcion="Prentice Hall")]
    db.add_all(sedes + socios + generos + autores + editoriales)
    db.flush()
    libros = [
        M.Libro(titulo="Ficciones", isbn="9788420633121", genero_id=generos[0].id, autor_id=autores[0].id, editorial_id=editoriales[0].id),
        M.Libro(titulo="Cosmos", isbn="9788408175186", genero_id=generos[1].id, autor_id=autores[1].id, editorial_id=editoriales[1].id),
        M.Libro(titulo="Clean Code", isbn="9780132350884", genero_id=generos[2].id, autor_id=autores[2].id, editorial_id=editoriales[2].id),
    ]
    db.add_all(libros)
    db.flush()
    for i, libro in enumerate(libros):
        for sede in (sedes[i % 3], sedes[(i + 1) % 3]):
            for _ in range(2):
                ej = M.Ejemplar(libro_id=libro.id, sede_id=sede.id)
                db.add(ej)
                db.flush()
                ej.codigo_inventario = f"EJ-{ej.id:06d}"
    db.commit()
