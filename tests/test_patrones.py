from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app import enums as E
from app import models as M
from app.database import Base
from app.routers.reportes import prestamos_activos_y_en_transito
from app.seed import seed_catalogos, seed_demo
from app.errors import ReglaNegocioError, TransicionInvalidaError
from app.patterns.multa_strategy import MultaDiaria, MultaEscalonada, obtener_estrategia
from app.patterns.remito_state import estado_de
from app.services.remitos import crear_remito


def test_ciclo_feliz_del_remito():
    s = estado_de(E.EstadoRemito.EMPAQUETADO)
    assert s.despachar() == E.EstadoRemito.DESPACHADO
    s = estado_de(E.EstadoRemito.DESPACHADO)
    assert s.recibir() == E.EstadoRemito.RECIBIDO
    assert s.marcar_incidencia() == E.EstadoRemito.INCIDENCIA


def test_cancelar_solo_desde_empaquetado():
    assert estado_de(E.EstadoRemito.EMPAQUETADO).cancelar() == E.EstadoRemito.CANCELADO
    with pytest.raises(TransicionInvalidaError):
        estado_de(E.EstadoRemito.DESPACHADO).cancelar()


@pytest.mark.parametrize("estado", [E.EstadoRemito.RECIBIDO, E.EstadoRemito.INCIDENCIA, E.EstadoRemito.CANCELADO])
def test_estados_terminales(estado):
    s = estado_de(estado)
    for accion in (s.despachar, s.recibir, s.marcar_incidencia, s.cancelar):
        with pytest.raises(TransicionInvalidaError):
            accion()


def test_no_se_puede_recibir_sin_despachar():
    with pytest.raises(TransicionInvalidaError):
        estado_de(E.EstadoRemito.EMPAQUETADO).recibir()


def test_no_se_crea_remito_de_retorno_hacia_sede_inactiva():
    prestamo = SimpleNamespace(
        sede_origen=SimpleNamespace(estado_id=E.EstadoSede.ACTIVA, nombre="Origen"),
        sede_destino=SimpleNamespace(estado_id=E.EstadoSede.BAJA, nombre="Destino"),
    )

    with pytest.raises(ReglaNegocioError, match="dada de baja"):
        crear_remito(
            None,
            prestamo=prestamo,
            tipo=E.TipoRemito.RETORNO,
            origen_id=2,
            destino_id=1,
        )


def test_multa_diaria():
    assert MultaDiaria(Decimal("50")).calcular(3) == Decimal("150.00")
    assert MultaDiaria(Decimal("50")).calcular(-2) == Decimal("0.00")


def test_multa_escalonada():
    m = MultaEscalonada(Decimal("50"), dias_tramo=7, factor=2)
    assert m.calcular(7) == Decimal("350.00")
    assert m.calcular(9) == Decimal("550.00")


def test_factory_de_estrategias():
    assert isinstance(obtener_estrategia("diaria", Decimal("10")), MultaDiaria)
    assert isinstance(obtener_estrategia("ESCALONADA", Decimal("10")), MultaEscalonada)
    with pytest.raises(ValueError):
        obtener_estrategia("otra", Decimal("10"))


def test_seed_demo_crea_volumen_realista():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        seed_catalogos(db)
        seed_demo(db)

        assert db.scalar(select(func.count(M.Libro.id))) >= 10
        assert db.scalar(select(func.count(M.Reserva.id))) >= 2
        assert db.scalar(select(func.count(M.Prestamo.id))) >= 2
        assert db.scalar(select(func.count(M.Ejemplar.id))) >= 20


def test_reporte_incluye_prestamos_en_transito():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        seed_catalogos(db)

        sede_origen = M.Sede(nombre="Origen", direccion="Dir 1", correo="o@biblio.test", telefono="111", horarios="Lun-Vie")
        sede_destino = M.Sede(nombre="Destino", direccion="Dir 2", correo="d@biblio.test", telefono="222", horarios="Lun-Vie")
        socio = M.Socio(dni="12345678", nombre="Ana", apellido="López", telefono="333")
        genero = M.Genero(nombre="Ficción")
        autor = M.Autor(nombre="Autor Demo")
        editorial = M.Editorial(descripcion="Editorial Demo")
        db.add_all([sede_origen, sede_destino, socio, genero, autor, editorial])
        db.flush()

        libro = M.Libro(titulo="Libro en tránsito", isbn="9780000000001", genero_id=genero.id, autor_id=autor.id, editorial_id=editorial.id)
        db.add(libro)
        db.flush()

        ejemplar = M.Ejemplar(libro_id=libro.id, sede_id=sede_origen.id, estado_id=E.EstadoEjemplar.EN_TRANSITO)
        db.add(ejemplar)
        db.flush()

        prestamo = M.Prestamo(
            socio_id=socio.id,
            libro_id=libro.id,
            ejemplar_id=ejemplar.id,
            sede_origen_id=sede_origen.id,
            sede_destino_id=sede_destino.id,
            estado_id=E.EstadoPrestamo.EN_TRANSITO,
        )
        db.add(prestamo)
        db.flush()

        remito = M.Remito(
            numero="REM-000001",
            tipo=E.TipoRemito.ENVIO.value,
            prestamo_id=prestamo.id,
            ejemplar_id=ejemplar.id,
            sede_origen_id=sede_origen.id,
            sede_destino_id=sede_destino.id,
            estado_id=E.EstadoRemito.DESPACHADO,
            fecha_salida=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        db.add(remito)
        db.commit()

        salida = prestamos_activos_y_en_transito(db)
        assert salida["totales"]["prestamos_activos"] == 1
        assert salida["totales"]["material_en_transito"] == 1
        assert salida["prestamos_activos"][0]["prestamo_id"] == prestamo.id
        assert salida["material_en_transito"][0]["remito"] == "REM-000001"
