from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from sqlalchemy import func, select

from app import enums as E
from app.config import settings
from app.database import DB
from app.errors import NoAutenticadoError, PermisoDenegadoError
from app.models import Usuario

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("contraseña-invalida")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hashear_password(password: str) -> str:
    return password_hash.hash(password)


def verificar_password(password: str, hash_guardado: str) -> bool:
    try:
        return password_hash.verify(password, hash_guardado)
    except UnknownHashError:
        return False


def autenticar(db: DB, username: str, password: str) -> Usuario:
    usuario = db.scalar(
        select(Usuario).where(func.lower(Usuario.username) == username.strip().lower())
    )
    if usuario is None:
        verificar_password(password, DUMMY_HASH)
        raise NoAutenticadoError("Usuario o contraseña incorrectos.")
    if not usuario.activo or not verificar_password(password, usuario.password_hash):
        raise NoAutenticadoError("Usuario o contraseña incorrectos.")
    return usuario


def crear_token(usuario: Usuario) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "rol": usuario.rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DB) -> Usuario:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        sub = payload.get("sub")
        if sub is None:
            raise NoAutenticadoError("Token inválido.")
        usuario = db.get(Usuario, int(sub))
    except (InvalidTokenError, ValueError):
        raise NoAutenticadoError("Token inválido o expirado.") from None
    if usuario is None or not usuario.activo:
        raise NoAutenticadoError("Usuario inexistente o inactivo.")
    return usuario


CurrentUser = Annotated[Usuario, Depends(get_current_user)]


def require_roles(*roles: E.RolUsuario):
    permitidos = {rol.value for rol in roles}

    def dependency(usuario: CurrentUser) -> Usuario:
        if usuario.rol not in permitidos:
            raise PermisoDenegadoError(
                f"Acceso denegado. Roles permitidos: {', '.join(sorted(permitidos))}."
            )
        return usuario

    return dependency


require_admin = require_roles(E.RolUsuario.ADMIN)
require_admin_o_socio = require_roles(E.RolUsuario.ADMIN, E.RolUsuario.SOCIO)


def exigir_socio_propio(usuario: Usuario, socio_id: int) -> None:
    if not usuario.es_admin and usuario.socio_id != socio_id:
        raise PermisoDenegadoError("Solo puede acceder a sus propios préstamos, reservas y devoluciones.")


def socio_id_de(usuario: Usuario) -> int:
    if usuario.socio_id is None:
        raise PermisoDenegadoError("El usuario autenticado no tiene un socio asociado.")
    return usuario.socio_id
