from decimal import Decimal

import pytest

from app import enums as E
from app.errors import TransicionInvalidaError
from app.patterns.multa_strategy import MultaDiaria, MultaEscalonada, obtener_estrategia
from app.patterns.remito_state import estado_de


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
