"""Modelo de datos.

Correspondencia con el modelo original (TP DAO .sql):
  Genero, Autor, Editorial, Libros, Sedes, Socios, Reservas, Prestamo -> mismas entidades
  Estado_Sedes, EstadoSocio, EstadoReserva, EstadoPrestamo           -> tablas de estados (cat.)
  EstadoLibro                                                        -> estado_ejemplares
  LibroxSede (id_libro, id_sede, estado)                             -> ejemplares (PK propia: una sede
                                                                        puede tener varios ejemplares)
  DetallePrestamo (fecha_salida, fecha_llegada, estado)              -> remitos
  EstadoDetalle                                                      -> estado_remitos
  HistorialPrestamo (id_remito, fecha, observacion)                  -> historial_remitos
Se agregan: devoluciones (devolución + estado físico + multa) y las FK en el sentido correcto.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import enums as E
from app.database import Base
from app.utils import utcnow


# ---------------------------------------------------------------- catálogos de estados
class _CatalogoMixin:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    descripcion: Mapped[str] = mapped_column(String(50), unique=True)


class CatEstadoSede(_CatalogoMixin, Base):
    __tablename__ = "estado_sedes"


class CatEstadoSocio(_CatalogoMixin, Base):
    __tablename__ = "estado_socios"


class CatEstadoEjemplar(_CatalogoMixin, Base):
    __tablename__ = "estado_ejemplares"


class CatEstadoReserva(_CatalogoMixin, Base):
    __tablename__ = "estado_reservas"


class CatEstadoPrestamo(_CatalogoMixin, Base):
    __tablename__ = "estado_prestamos"


class CatEstadoRemito(_CatalogoMixin, Base):
    __tablename__ = "estado_remitos"


# ---------------------------------------------------------------- catálogo bibliográfico
class Genero(Base):
    __tablename__ = "generos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), unique=True)


class Autor(Base):
    __tablename__ = "autores"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), unique=True)


class Editorial(Base):
    __tablename__ = "editoriales"
    id: Mapped[int] = mapped_column(primary_key=True)
    descripcion: Mapped[str] = mapped_column(String(255), unique=True)


class Libro(Base):
    __tablename__ = "libros"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(255))
    isbn: Mapped[str] = mapped_column(String(20), unique=True)
    genero_id: Mapped[int] = mapped_column(ForeignKey("generos.id"))
    autor_id: Mapped[int] = mapped_column(ForeignKey("autores.id"))
    editorial_id: Mapped[int] = mapped_column(ForeignKey("editoriales.id"))

    genero: Mapped[Genero] = relationship()
    autor: Mapped[Autor] = relationship()
    editorial: Mapped[Editorial] = relationship()
    ejemplares: Mapped[list[Ejemplar]] = relationship(back_populates="libro")


# ---------------------------------------------------------------- sedes y socios
class Sede(Base):
    __tablename__ = "sedes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), unique=True)
    direccion: Mapped[str] = mapped_column(String(255))
    correo: Mapped[str | None] = mapped_column(String(255))
    telefono: Mapped[str | None] = mapped_column(String(50))
    horarios: Mapped[str | None] = mapped_column(String(255))
    estado_id: Mapped[int] = mapped_column(
        ForeignKey("estado_sedes.id"), default=E.EstadoSede.ACTIVA
    )

    @property
    def estado(self) -> str:
        return E.EstadoSede(self.estado_id).name


class Socio(Base):
    __tablename__ = "socios"
    id: Mapped[int] = mapped_column(primary_key=True)
    dni: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(255))
    apellido: Mapped[str] = mapped_column(String(255))
    telefono: Mapped[str | None] = mapped_column(String(50))
    estado_id: Mapped[int] = mapped_column(
        ForeignKey("estado_socios.id"), default=E.EstadoSocio.HABILITADO
    )
    fecha_alta: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def estado(self) -> str:
        return E.EstadoSocio(self.estado_id).name


# ---------------------------------------------------------------- ejemplares
class Ejemplar(Base):
    __tablename__ = "ejemplares"
    __table_args__ = (Index("ix_ejemplares_libro_sede", "libro_id", "sede_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    libro_id: Mapped[int] = mapped_column(ForeignKey("libros.id"))
    sede_id: Mapped[int] = mapped_column(ForeignKey("sedes.id"))  # sede a la que pertenece
    codigo_inventario: Mapped[str | None] = mapped_column(String(50), unique=True)
    estado_id: Mapped[int] = mapped_column(
        ForeignKey("estado_ejemplares.id"), default=E.EstadoEjemplar.DISPONIBLE
    )
    fecha_alta: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    libro: Mapped[Libro] = relationship(back_populates="ejemplares")
    sede: Mapped[Sede] = relationship()

    @property
    def estado(self) -> str:
        return E.EstadoEjemplar(self.estado_id).name


# ---------------------------------------------------------------- reservas
class Reserva(Base):
    __tablename__ = "reservas"
    id: Mapped[int] = mapped_column(primary_key=True)
    socio_id: Mapped[int] = mapped_column(ForeignKey("socios.id"))
    libro_id: Mapped[int] = mapped_column(ForeignKey("libros.id"))
    sede_id: Mapped[int] = mapped_column(ForeignKey("sedes.id"))  # sede cuyo stock se reserva
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    estado_id: Mapped[int] = mapped_column(
        ForeignKey("estado_reservas.id"), default=E.EstadoReserva.ACTIVA
    )

    @property
    def estado(self) -> str:
        return E.EstadoReserva(self.estado_id).name


# ---------------------------------------------------------------- préstamos
class Prestamo(Base):
    __tablename__ = "prestamos"
    id: Mapped[int] = mapped_column(primary_key=True)
    socio_id: Mapped[int] = mapped_column(ForeignKey("socios.id"))
    libro_id: Mapped[int] = mapped_column(ForeignKey("libros.id"))
    ejemplar_id: Mapped[int] = mapped_column(ForeignKey("ejemplares.id"))
    sede_origen_id: Mapped[int] = mapped_column(ForeignKey("sedes.id"))
    sede_destino_id: Mapped[int] = mapped_column(ForeignKey("sedes.id"))
    estado_id: Mapped[int] = mapped_column(
        ForeignKey("estado_prestamos.id"), default=E.EstadoPrestamo.SOLICITADO
    )
    fecha_solicitud: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    fecha_prestamo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    fecha_devolucion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    socio: Mapped[Socio] = relationship()
    libro: Mapped[Libro] = relationship()
    ejemplar: Mapped[Ejemplar] = relationship()
    sede_origen: Mapped[Sede] = relationship(foreign_keys=[sede_origen_id])
    sede_destino: Mapped[Sede] = relationship(foreign_keys=[sede_destino_id])
    remitos: Mapped[list[Remito]] = relationship(back_populates="prestamo", order_by="Remito.id")
    devolucion: Mapped[Devolucion | None] = relationship(back_populates="prestamo", uselist=False)

    @property
    def estado(self) -> str:
        return E.EstadoPrestamo(self.estado_id).name

    @property
    def interbibliotecario(self) -> bool:
        return self.sede_origen_id != self.sede_destino_id


# ---------------------------------------------------------------- remitos
REMITO_SEQ = Sequence("remito_numero_seq", metadata=Base.metadata)


class Remito(Base):
    __tablename__ = "remitos"
    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)
    tipo: Mapped[str] = mapped_column(String(10))
    prestamo_id: Mapped[int] = mapped_column(ForeignKey("prestamos.id"))
    ejemplar_id: Mapped[int] = mapped_column(ForeignKey("ejemplares.id"))
    sede_origen_id: Mapped[int] = mapped_column(ForeignKey("sedes.id"))
    sede_destino_id: Mapped[int] = mapped_column(ForeignKey("sedes.id"))
    estado_id: Mapped[int] = mapped_column(
        ForeignKey("estado_remitos.id"), default=E.EstadoRemito.EMPAQUETADO
    )
    fecha_empaquetado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    fecha_salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_llegada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado_fisico_recepcion: Mapped[str | None] = mapped_column(String(20))

    prestamo: Mapped[Prestamo] = relationship(back_populates="remitos")
    ejemplar: Mapped[Ejemplar] = relationship()
    sede_origen: Mapped[Sede] = relationship(foreign_keys=[sede_origen_id])
    sede_destino: Mapped[Sede] = relationship(foreign_keys=[sede_destino_id])
    historial: Mapped[list[HistorialRemito]] = relationship(
        back_populates="remito", order_by="HistorialRemito.id"
    )

    @property
    def estado(self) -> str:
        return E.EstadoRemito(self.estado_id).name


class HistorialRemito(Base):
    __tablename__ = "historial_remitos"
    id: Mapped[int] = mapped_column(primary_key=True)
    remito_id: Mapped[int] = mapped_column(ForeignKey("remitos.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    estado_anterior: Mapped[str | None] = mapped_column(String(20))
    estado_nuevo: Mapped[str] = mapped_column(String(20))
    observacion: Mapped[str | None] = mapped_column(String(255))

    remito: Mapped[Remito] = relationship(back_populates="historial")


# ---------------------------------------------------------------- devoluciones
class Devolucion(Base):
    __tablename__ = "devoluciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    prestamo_id: Mapped[int] = mapped_column(ForeignKey("prestamos.id"), unique=True)
    sede_id: Mapped[int] = mapped_column(ForeignKey("sedes.id"))  # sede donde se devolvió
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    estado_fisico: Mapped[str] = mapped_column(String(20))
    observacion: Mapped[str | None] = mapped_column(String(255))
    dias_atraso: Mapped[int] = mapped_column(default=0)
    multa: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    remito_retorno_id: Mapped[int | None] = mapped_column(ForeignKey("remitos.id"))

    prestamo: Mapped[Prestamo] = relationship(back_populates="devolucion")
