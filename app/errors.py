class AppError(Exception):
    status_code = 400

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoEncontradoError(AppError):
    status_code = 404


class ConflictoError(AppError):
    status_code = 409


class ReglaNegocioError(AppError):
    status_code = 422


class TransicionInvalidaError(ConflictoError):
    pass
