from datetime import date

from sqlalchemy.orm import Session

from app import enums as E
from app.config import settings
from app.errors import ReglaNegocioError
from app.models import Devolucion, Ejemplar, Prestamo
from app.patterns.multa_strategy import obtener_estrategia
from app.services import remitos as remitos_svc
from app.services.common import ESTADO_EJEMPLAR_POR_FISICO, obtener
from app.utils import utcnow


def registrar_devolucion(
    db: Session, prestamo_id: int, estado_fisico: E.EstadoFisico, observacion: str | None
) -> Devolucion:
    prestamo = obtener(db, Prestamo, prestamo_id, "Préstamo")
    if prestamo.estado_id not in (E.EstadoPrestamo.ACTIVO, E.EstadoPrestamo.VENCIDO):
        raise ReglaNegocioError(
            f"Solo se pueden devolver préstamos ACTIVO o VENCIDO (estado actual: {prestamo.estado})."
        )

    dias_atraso = max(0, (date.today() - prestamo.fecha_vencimiento).days)
    multa = obtener_estrategia(settings.multa_estrategia, settings.multa_monto_dia).calcular(dias_atraso)
    ejemplar = obtener(db, Ejemplar, prestamo.ejemplar_id, "Ejemplar", bloquear=True)

    devolucion = Devolucion(
        prestamo_id=prestamo.id,
        sede_id=prestamo.sede_destino_id,  # donde está el socio
        fecha=utcnow(),
        estado_fisico=estado_fisico.value,
        observacion=observacion,
        dias_atraso=dias_atraso,
        multa=multa,
    )
    db.add(devolucion)
    prestamo.estado_id = E.EstadoPrestamo.DEVUELTO
    prestamo.fecha_devolucion = devolucion.fecha

    perdido = estado_fisico in (E.EstadoFisico.EXTRAVIADO, E.EstadoFisico.DESTRUIDO)
    if perdido or not prestamo.interbibliotecario:
        ejemplar.estado_id = ESTADO_EJEMPLAR_POR_FISICO[estado_fisico]
    else:
        # interbibliotecario: el ejemplar debe volver a su sede dueña mediante un remito de retorno
        ejemplar.estado_id = E.EstadoEjemplar.PENDIENTE_RETORNO
        db.flush()
        remito = remitos_svc.crear_remito(
            db,
            prestamo=prestamo,
            tipo=E.TipoRemito.RETORNO,
            origen_id=prestamo.sede_destino_id,
            destino_id=prestamo.sede_origen_id,
            observacion="Remito de retorno por devolución",
        )
        devolucion.remito_retorno_id = remito.id
    db.commit()
    return devolucion
