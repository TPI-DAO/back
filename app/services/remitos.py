from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enums as E
from app.config import settings
from app.errors import ConflictoError, ReglaNegocioError
from app.models import REMITO_SEQ, Ejemplar, HistorialRemito, Prestamo, Remito
from app.patterns.remito_state import estado_de
from app.services.common import (
    ESTADO_EJEMPLAR_POR_FISICO,
    exigir_sede_activa,
    obtener,
    restaurar_reserva_cumplida,
    sede_tiene_ejemplar_utilizable,
)
from app.utils import utcnow


def registrar_historial(
    db: Session, remito: Remito, anterior: int | None, nuevo: int, observacion: str | None = None
) -> None:
    db.add(
        HistorialRemito(
            remito_id=remito.id,
            fecha=utcnow(),
            estado_anterior=E.EstadoRemito(anterior).name if anterior else None,
            estado_nuevo=E.EstadoRemito(nuevo).name,
            observacion=observacion,
        )
    )


def crear_remito(
    db: Session,
    *,
    prestamo: Prestamo,
    tipo: E.TipoRemito,
    origen_id: int,
    destino_id: int,
    observacion: str | None = None,
) -> Remito:
    numero = db.scalar(select(REMITO_SEQ.next_value()))
    remito = Remito(
        numero=f"REM-{numero:06d}",
        tipo=tipo.value,
        prestamo_id=prestamo.id,
        ejemplar_id=prestamo.ejemplar_id,
        sede_origen_id=origen_id,
        sede_destino_id=destino_id,
        estado_id=E.EstadoRemito.EMPAQUETADO,
        fecha_empaquetado=utcnow(),
    )
    db.add(remito)
    db.flush()
    registrar_historial(db, remito, None, E.EstadoRemito.EMPAQUETADO, observacion or "Ejemplar empaquetado y remito generado")
    return remito


def generar_remito_envio(db: Session, prestamo_id: int, observacion: str | None) -> Remito:
    prestamo = obtener(db, Prestamo, prestamo_id, "Préstamo")
    if not prestamo.interbibliotecario:
        raise ReglaNegocioError("Los préstamos locales no requieren remito.")
    if prestamo.estado_id != E.EstadoPrestamo.SOLICITADO:
        raise ReglaNegocioError(
            f"Solo se puede generar remito para préstamos SOLICITADO (estado actual: {prestamo.estado})."
        )
    existente = db.scalar(
        select(Remito.id).where(
            Remito.prestamo_id == prestamo.id,
            Remito.tipo == E.TipoRemito.ENVIO.value,
            Remito.estado_id != E.EstadoRemito.CANCELADO,
        )
    )
    if existente:
        raise ConflictoError("El préstamo ya tiene un remito de envío vigente.")
    exigir_sede_activa(prestamo.sede_origen, "origen")
    exigir_sede_activa(prestamo.sede_destino, "destino")
    remito = crear_remito(
        db,
        prestamo=prestamo,
        tipo=E.TipoRemito.ENVIO,
        origen_id=prestamo.sede_origen_id,
        destino_id=prestamo.sede_destino_id,
        observacion=observacion,
    )
    db.commit()
    return remito


def cancelar_remito_empaquetado(db: Session, prestamo: Prestamo) -> None:
    remito = db.scalar(
        select(Remito).where(
            Remito.prestamo_id == prestamo.id,
            Remito.tipo == E.TipoRemito.ENVIO.value,
            Remito.estado_id == E.EstadoRemito.EMPAQUETADO,
        )
    )
    if remito:
        anterior = remito.estado_id
        remito.estado_id = estado_de(anterior).cancelar()
        registrar_historial(db, remito, anterior, remito.estado_id, "Préstamo cancelado")


def despachar(db: Session, remito_id: int, observacion: str | None) -> Remito:
    remito = obtener(db, Remito, remito_id, "Remito")
    anterior = remito.estado_id
    nuevo = estado_de(anterior).despachar()
    exigir_sede_activa(remito.sede_origen, "origen")
    exigir_sede_activa(remito.sede_destino, "destino")
    remito.estado_id = nuevo
    remito.fecha_salida = utcnow()
    ejemplar = obtener(db, Ejemplar, remito.ejemplar_id, "Ejemplar", bloquear=True)
    ejemplar.estado_id = E.EstadoEjemplar.EN_TRANSITO
    if remito.tipo == E.TipoRemito.ENVIO.value:
        remito.prestamo.estado_id = E.EstadoPrestamo.EN_TRANSITO
    registrar_historial(db, remito, anterior, nuevo, observacion or "Despachado")
    db.commit()
    return remito


def recibir(db: Session, remito_id: int, estado_fisico: E.EstadoFisico, observacion: str | None) -> Remito:
    remito = obtener(db, Remito, remito_id, "Remito")
    anterior = remito.estado_id
    estado = estado_de(anterior)
    perdido = estado_fisico in (E.EstadoFisico.EXTRAVIADO, E.EstadoFisico.DESTRUIDO)
    nuevo = estado.marcar_incidencia() if perdido else estado.recibir()

    remito.estado_id = nuevo
    remito.fecha_llegada = utcnow()
    remito.estado_fisico_recepcion = estado_fisico.value
    ejemplar = obtener(db, Ejemplar, remito.ejemplar_id, "Ejemplar", bloquear=True)
    prestamo = remito.prestamo

    if remito.tipo == E.TipoRemito.ENVIO.value:
        if estado_fisico == E.EstadoFisico.BUENO:
            ahora = utcnow()
            ejemplar.estado_id = E.EstadoEjemplar.PRESTADO
            prestamo.estado_id = E.EstadoPrestamo.ACTIVO
            prestamo.fecha_prestamo = ahora
            prestamo.fecha_vencimiento = date.today() + timedelta(days=settings.dias_prestamo)
        else:
            ejemplar.estado_id = ESTADO_EJEMPLAR_POR_FISICO[estado_fisico]
            prestamo.estado_id = E.EstadoPrestamo.CANCELADO
            if sede_tiene_ejemplar_utilizable(db, prestamo.sede_origen_id, prestamo.libro_id):
                restaurar_reserva_cumplida(db, prestamo)
    else:  # RETORNO a la sede dueña
        if estado_fisico != E.EstadoFisico.BUENO:
            ejemplar.estado_id = ESTADO_EJEMPLAR_POR_FISICO[estado_fisico]
        else:
            dev = prestamo.devolucion
            fisico_dev = E.EstadoFisico(dev.estado_fisico) if dev else E.EstadoFisico.BUENO
            ejemplar.estado_id = ESTADO_EJEMPLAR_POR_FISICO[fisico_dev]

    registrar_historial(db, remito, anterior, nuevo, observacion or f"Recibido ({estado_fisico.value})")
    db.commit()
    return remito
