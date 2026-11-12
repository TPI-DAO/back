from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select

from app import enums as E
from app.config import settings
from app.database import DB
from app.errors import ConflictoError, ReglaNegocioError
from app.models import Socio, Usuario
from app.schemas import (
    PasswordUpdate,
    TokenOut,
    UsuarioCreate,
    UsuarioEstadoIn,
    UsuarioOut,
)
from app.security import (
    CurrentUser,
    autenticar,
    crear_token,
    hashear_password,
    require_admin,
    verificar_password,
)
from app.services.common import obtener

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/token", response_model=TokenOut, summary="Iniciar sesión (OAuth2 password flow)")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    usuario = autenticar(db, form.username, form.password)
    return TokenOut(
        access_token=crear_token(usuario),
        username=usuario.username,
        rol=usuario.rol,
        socio_id=usuario.socio_id,
        expira_en_minutos=settings.access_token_minutes,
    )


@router.get("/me", response_model=UsuarioOut, summary="Datos del usuario autenticado")
def me(usuario: CurrentUser):
    return usuario


@router.post("/me/password", status_code=204, summary="Cambiar la propia contraseña")
def cambiar_password(data: PasswordUpdate, usuario: CurrentUser, db: DB):
    if not verificar_password(data.password_actual, usuario.password_hash):
        raise ReglaNegocioError("La contraseña actual no es correcta.")
    usuario.password_hash = hashear_password(data.password_nueva)
    db.commit()


@router.get("/usuarios", response_model=list[UsuarioOut], summary="Listar usuarios (admin)")
def listar_usuarios(db: DB, _admin: Usuario = Depends(require_admin)):
    return db.scalars(select(Usuario).order_by(Usuario.id)).all()


@router.post("/usuarios", response_model=UsuarioOut, status_code=201, summary="Crear usuario (admin)")
def crear_usuario(data: UsuarioCreate, db: DB, _admin: Usuario = Depends(require_admin)):
    username = data.username.strip()
    email = data.email.strip().lower()
    if db.scalar(select(Usuario.id).where(func.lower(Usuario.username) == username.lower())):
        raise ConflictoError(f"Ya existe el usuario '{username}'.")
    if db.scalar(select(Usuario.id).where(func.lower(Usuario.email) == email)):
        raise ConflictoError(f"Ya existe un usuario con el email {email}.")

    socio = None
    if data.rol == E.RolUsuario.SOCIO.value:
        if data.socio_id is None:
            raise ReglaNegocioError("Los usuarios SOCIO deben estar asociados a un socio.")
        socio = obtener(db, Socio, data.socio_id, "Socio")
        if db.scalar(select(Usuario.id).where(Usuario.socio_id == socio.id)):
            raise ConflictoError("Ese socio ya tiene una cuenta de usuario.")
    elif data.socio_id is not None:
        raise ReglaNegocioError("Solo los usuarios SOCIO pueden tener un socio asociado.")

    usuario = Usuario(
        username=username,
        email=email,
        password_hash=hashear_password(data.password),
        rol=data.rol,
        socio_id=socio.id if socio else None,
    )
    db.add(usuario)
    db.commit()
    return usuario


@router.patch(
    "/usuarios/{usuario_id}/estado",
    response_model=UsuarioOut,
    summary="Activar / desactivar usuario (admin)",
)
def cambiar_estado_usuario(
    usuario_id: int,
    data: UsuarioEstadoIn,
    db: DB,
    _admin: Usuario = Depends(require_admin),
):
    usuario = obtener(db, Usuario, usuario_id, "Usuario")
    if usuario.username == settings.admin_username and not data.activo:
        raise ReglaNegocioError("No se puede desactivar el usuario administrador principal.")
    usuario.activo = data.activo
    db.commit()
    return usuario
