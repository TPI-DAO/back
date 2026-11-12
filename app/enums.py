from enum import Enum, IntEnum


class EstadoSede(IntEnum):
    ACTIVA = 1
    BAJA = 2


class EstadoSocio(IntEnum):
    HABILITADO = 1
    INHABILITADO = 2


class EstadoEjemplar(IntEnum):
    DISPONIBLE = 1
    RESERVADO = 2          # apartado para un préstamo interbibliotecario solicitado
    PRESTADO = 3
    EN_TRANSITO = 4
    PENDIENTE_RETORNO = 5  # devuelto por el socio en sede destino, falta enviarlo a su sede
    DANADO = 6
    EXTRAVIADO = 7
    DESTRUIDO = 8
    BAJA = 9


class EstadoReserva(IntEnum):
    ACTIVA = 1
    CUMPLIDA = 2
    CANCELADA = 3


class EstadoPrestamo(IntEnum):
    SOLICITADO = 1
    EN_TRANSITO = 2
    ACTIVO = 3
    VENCIDO = 4
    DEVUELTO = 5
    CANCELADO = 6


class EstadoRemito(IntEnum):
    EMPAQUETADO = 1
    DESPACHADO = 2
    RECIBIDO = 3
    INCIDENCIA = 4
    CANCELADO = 5


class TipoRemito(str, Enum):
    ENVIO = "ENVIO"      # sede origen -> sede destino (socio)
    RETORNO = "RETORNO"  # sede destino -> sede origen (dueña del ejemplar)


class EstadoFisico(str, Enum):
    BUENO = "BUENO"
    DANADO = "DANADO"
    EXTRAVIADO = "EXTRAVIADO"
    DESTRUIDO = "DESTRUIDO"


class RolUsuario(str, Enum):
    ADMIN = "ADMIN"   # personal de la biblioteca: gestión completa
    SOCIO = "SOCIO"   # cliente/lector: consulta y gestiona sus propios datos
