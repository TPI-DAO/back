"""Patrón STRATEGY aplicado al cálculo de multas por atraso.

La estrategia se elige por configuración (MULTA_ESTRATEGIA) sin tocar el servicio de devoluciones.
"""
from abc import ABC, abstractmethod
from decimal import Decimal

_CENTAVOS = Decimal("0.01")


class EstrategiaMulta(ABC):
    @abstractmethod
    def calcular(self, dias_atraso: int) -> Decimal: ...


class MultaDiaria(EstrategiaMulta):
    """monto fijo por cada día de atraso."""

    def __init__(self, monto_dia: Decimal):
        self.monto_dia = Decimal(monto_dia)

    def calcular(self, dias_atraso: int) -> Decimal:
        return (self.monto_dia * max(dias_atraso, 0)).quantize(_CENTAVOS)


class MultaEscalonada(EstrategiaMulta):
    """monto base los primeros `dias_tramo` días; luego se multiplica por `factor`."""

    def __init__(self, monto_dia: Decimal, dias_tramo: int = 7, factor: int = 2):
        self.monto_dia = Decimal(monto_dia)
        self.dias_tramo = dias_tramo
        self.factor = factor

    def calcular(self, dias_atraso: int) -> Decimal:
        dias = max(dias_atraso, 0)
        primeros = min(dias, self.dias_tramo)
        resto = dias - primeros
        total = self.monto_dia * primeros + self.monto_dia * self.factor * resto
        return total.quantize(_CENTAVOS)


def obtener_estrategia(nombre: str, monto_dia: Decimal) -> EstrategiaMulta:
    estrategias = {"diaria": MultaDiaria, "escalonada": MultaEscalonada}
    try:
        return estrategias[nombre.lower()](monto_dia)
    except KeyError:
        raise ValueError(f"Estrategia de multa desconocida: {nombre}") from None
