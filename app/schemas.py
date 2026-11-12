from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import EstadoFisico


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- catálogos bibliográficos
class NombreIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)


class GeneroOut(ORM):
    id: int
    nombre: str


class AutorOut(ORM):
    id: int
    nombre: str


class EditorialIn(BaseModel):
    descripcion: str = Field(min_length=1, max_length=255)


class EditorialOut(ORM):
    id: int
    descripcion: str


class LibroCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=255)
    isbn: str = Field(min_length=10, max_length=20)
    genero_id: int
    autor_id: int
    editorial_id: int


class LibroUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=255)
    isbn: str | None = Field(default=None, min_length=10, max_length=20)
    genero_id: int | None = None
    autor_id: int | None = None
    editorial_id: int | None = None


class LibroResumen(ORM):
    id: int
    titulo: str
    isbn: str


class LibroOut(ORM):
    id: int
    titulo: str
    isbn: str
    genero: GeneroOut
    autor: AutorOut
    editorial: EditorialOut


# ---- sedes
class SedeCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    direccion: str = Field(min_length=1, max_length=255)
    correo: str | None = None
    telefono: str | None = None
    horarios: str | None = None


class SedeUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    direccion: str | None = Field(default=None, min_length=1, max_length=255)
    correo: str | None = None
    telefono: str | None = None
    horarios: str | None = None


class SedeOut(ORM):
    id: int
    nombre: str
    direccion: str
    correo: str | None
    telefono: str | None
    horarios: str | None
    estado: str


class SedeEstadoIn(BaseModel):
    estado: Literal["ACTIVA", "BAJA"]


# ---- socios
class SocioCreate(BaseModel):
    dni: str = Field(min_length=6, max_length=20)
    nombre: str = Field(min_length=1, max_length=255)
    apellido: str = Field(min_length=1, max_length=255)
    telefono: str | None = None


class SocioUpdate(BaseModel):
    dni: str | None = Field(default=None, min_length=6, max_length=20)
    nombre: str | None = Field(default=None, min_length=1, max_length=255)
    apellido: str | None = Field(default=None, min_length=1, max_length=255)
    telefono: str | None = None


class SocioOut(ORM):
    id: int
    dni: str
    nombre: str
    apellido: str
    telefono: str | None
    estado: str
    fecha_alta: datetime


class SocioEstadoIn(BaseModel):
    estado: Literal["HABILITADO", "INHABILITADO"]


# ---- ejemplares
class EjemplarCreate(BaseModel):
    libro_id: int
    sede_id: int
    codigo_inventario: str | None = Field(default=None, max_length=50)


class EjemplarUpdate(BaseModel):
    sede_id: int | None = None
    codigo_inventario: str | None = Field(default=None, max_length=50)
    estado: Literal["DISPONIBLE", "DANADO"] | None = None


class EjemplarOut(ORM):
    id: int
    codigo_inventario: str | None
    sede_id: int
    estado: str
    fecha_alta: datetime
    libro: LibroResumen


# ---- reservas
class ReservaCreate(BaseModel):
    socio_id: int
    libro_id: int
    sede_id: int


class ReservaOut(ORM):
    id: int
    socio_id: int
    libro_id: int
    sede_id: int
    fecha: datetime
    estado: str


# ---- préstamos
class PrestamoCreate(BaseModel):
    socio_id: int
    libro_id: int
    sede_origen_id: int
    sede_destino_id: int


class PrestamoOut(ORM):
    id: int
    socio_id: int
    libro_id: int
    ejemplar_id: int
    sede_origen_id: int
    sede_destino_id: int
    estado: str
    interbibliotecario: bool
    fecha_solicitud: datetime
    fecha_prestamo: datetime | None
    fecha_vencimiento: date | None
    fecha_devolucion: datetime | None


# ---- remitos
class RemitoCreate(BaseModel):
    prestamo_id: int
    observacion: str | None = Field(default=None, max_length=255)


class DespacharIn(BaseModel):
    observacion: str | None = Field(default=None, max_length=255)


class RecibirIn(BaseModel):
    estado_fisico: EstadoFisico = EstadoFisico.BUENO
    observacion: str | None = Field(default=None, max_length=255)


class RemitoOut(ORM):
    id: int
    numero: str
    tipo: str
    prestamo_id: int
    ejemplar_id: int
    sede_origen_id: int
    sede_destino_id: int
    estado: str
    fecha_empaquetado: datetime
    fecha_salida: datetime | None
    fecha_llegada: datetime | None
    estado_fisico_recepcion: str | None


class HistorialOut(ORM):
    id: int
    fecha: datetime
    estado_anterior: str | None
    estado_nuevo: str
    observacion: str | None


class TrazabilidadOut(BaseModel):
    remito: RemitoOut
    historial: list[HistorialOut]


# ---- devoluciones
class DevolucionCreate(BaseModel):
    prestamo_id: int
    estado_fisico: EstadoFisico = EstadoFisico.BUENO
    observacion: str | None = Field(default=None, max_length=255)


class DevolucionOut(ORM):
    id: int
    prestamo_id: int
    sede_id: int
    fecha: datetime
    estado_fisico: str
    observacion: str | None
    dias_atraso: int
    multa: Decimal
    remito_retorno_id: int | None


# ---- autenticación y usuarios
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    rol: str
    socio_id: int | None
    expira_en_minutos: int


class UsuarioCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    rol: Literal["ADMIN", "SOCIO"] = "SOCIO"
    socio_id: int | None = None


class UsuarioEstadoIn(BaseModel):
    activo: bool


class UsuarioOut(ORM):
    id: int
    username: str
    email: str
    rol: str
    socio_id: int | None
    activo: bool
    fecha_alta: datetime


class PasswordUpdate(BaseModel):
    password_actual: str
    password_nueva: str = Field(min_length=8, max_length=128)
