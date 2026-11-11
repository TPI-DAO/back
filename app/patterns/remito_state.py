"""Patrón STATE aplicado al ciclo de vida del remito.

Cada estado es un objeto que sabe qué acciones admite y a qué estado lleva.
Estados: EMPAQUETADO -> DESPACHADO -> RECIBIDO | INCIDENCIA ; EMPAQUETADO -> CANCELADO.
RECIBIDO, INCIDENCIA y CANCELADO son terminales.
"""
from abc import ABC

from app import enums as E
from app.errors import TransicionInvalidaError


class EstadoRemitoState(ABC):
    estado: E.EstadoRemito

    def _rechazar(self, accion: str):
        raise TransicionInvalidaError(
            f"No se puede {accion} un remito en estado {self.estado.name}."
        )

    def despachar(self) -> E.EstadoRemito:
        self._rechazar("despachar")

    def recibir(self) -> E.EstadoRemito:
        self._rechazar("recibir")

    def marcar_incidencia(self) -> E.EstadoRemito:
        self._rechazar("registrar una incidencia en")

    def cancelar(self) -> E.EstadoRemito:
        self._rechazar("cancelar")


class Empaquetado(EstadoRemitoState):
    estado = E.EstadoRemito.EMPAQUETADO

    def despachar(self):
        return E.EstadoRemito.DESPACHADO

    def cancelar(self):
        return E.EstadoRemito.CANCELADO


class Despachado(EstadoRemitoState):
    estado = E.EstadoRemito.DESPACHADO

    def recibir(self):
        return E.EstadoRemito.RECIBIDO

    def marcar_incidencia(self):
        return E.EstadoRemito.INCIDENCIA


class Recibido(EstadoRemitoState):
    estado = E.EstadoRemito.RECIBIDO


class Incidencia(EstadoRemitoState):
    estado = E.EstadoRemito.INCIDENCIA


class Cancelado(EstadoRemitoState):
    estado = E.EstadoRemito.CANCELADO


_ESTADOS = {s.estado: s for s in (Empaquetado(), Despachado(), Recibido(), Incidencia(), Cancelado())}


def estado_de(valor: int) -> EstadoRemitoState:
    return _ESTADOS[E.EstadoRemito(valor)]
