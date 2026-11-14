from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app import enums as E
from app import models as M
from app.database import Base
from app.seed import seed_catalogos, seed_demo
from app.seed_reportes import seed_reportes


def test_demo_coherente_e_idempotente():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_catalogos(db)
        seed_demo(db)
        conteos = [db.scalar(select(func.count()).select_from(modelo)) for modelo in
                   (M.Sede, M.Libro, M.Ejemplar, M.Prestamo, M.Devolucion)]
        assert all(conteos)

        prestamos = db.scalars(select(M.Prestamo)).all()
        for prestamo in prestamos:
            assert prestamo.libro_id == prestamo.ejemplar.libro_id
            assert prestamo.sede_origen_id == prestamo.ejemplar.sede_id
            if prestamo.estado_id == E.EstadoPrestamo.ACTIVO:
                assert prestamo.ejemplar.estado_id == E.EstadoEjemplar.PRESTADO
            elif prestamo.estado_id == E.EstadoPrestamo.SOLICITADO:
                assert prestamo.ejemplar.estado_id == E.EstadoEjemplar.RESERVADO
                assert prestamo.fecha_vencimiento is None
            elif prestamo.estado_id == E.EstadoPrestamo.DEVUELTO:
                assert prestamo.devolucion is not None
                assert prestamo.ejemplar.estado_id == E.EstadoEjemplar.DISPONIBLE

        ocupados = {p.ejemplar_id for p in prestamos if p.estado_id in
                    (E.EstadoPrestamo.ACTIVO, E.EstadoPrestamo.SOLICITADO)}
        for ejemplar in db.scalars(select(M.Ejemplar)):
            if ejemplar.id not in ocupados:
                assert ejemplar.estado_id == E.EstadoEjemplar.DISPONIBLE

        seed_demo(db)
        assert conteos == [db.scalar(select(func.count()).select_from(modelo)) for modelo in
                           (M.Sede, M.Libro, M.Ejemplar, M.Prestamo, M.Devolucion)]
    engine.dispose()


def test_reportes_agrega_actividad_sin_reemplazar_ni_duplicar():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_catalogos(db)
        seed_demo(db)
        ids_originales = set(db.scalars(select(M.Prestamo.id)))
        assert seed_reportes(db)
        db.commit()
        prestamos = db.scalars(select(M.Prestamo).where(
            M.Prestamo.id.not_in(ids_originales)
        )).all()
        assert len(prestamos) == 9
        for estado in (E.EstadoPrestamo.ACTIVO, E.EstadoPrestamo.VENCIDO,
                       E.EstadoPrestamo.EN_TRANSITO):
            assert sum(p.estado_id == estado for p in prestamos) == 3
        for prestamo in prestamos:
            assert prestamo.libro_id == prestamo.ejemplar.libro_id
            assert prestamo.sede_origen_id == prestamo.ejemplar.sede_id
            assert prestamo.interbibliotecario
            assert len(prestamo.remitos) == 1
            remito = prestamo.remitos[0]
            assert remito.historial[-1].estado_nuevo == remito.estado
            if prestamo.estado_id == E.EstadoPrestamo.EN_TRANSITO:
                assert prestamo.ejemplar.estado_id == E.EstadoEjemplar.EN_TRANSITO
                assert remito.estado_id == E.EstadoRemito.DESPACHADO
                assert prestamo.fecha_vencimiento is None
            else:
                assert prestamo.ejemplar.estado_id == E.EstadoEjemplar.PRESTADO
                assert remito.estado_id == E.EstadoRemito.RECIBIDO
        assert ids_originales.issubset(set(db.scalars(select(M.Prestamo.id))))
        total = db.scalar(select(func.count()).select_from(M.Prestamo))
        assert not seed_reportes(db)
        assert db.scalar(select(func.count()).select_from(M.Prestamo)) == total
    engine.dispose()
