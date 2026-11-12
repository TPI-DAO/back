import jwt
import pytest
from fastapi.testclient import TestClient

from app import enums as E
from app.config import settings
from app.errors import PermisoDenegadoError
from app.main import app
from app.models import Usuario
from app.security import (
    crear_token,
    hashear_password,
    require_admin,
    require_admin_o_socio,
    verificar_password,
)


def _usuario(rol: str) -> Usuario:
    return Usuario(
        id=1,
        username="usuario",
        email="usuario@test.com",
        password_hash="x",
        rol=rol,
        activo=True,
    )


def test_hash_y_verificacion_de_password():
    hashed = hashear_password("secreto123")
    assert hashed != "secreto123"
    assert verificar_password("secreto123", hashed)
    assert not verificar_password("otra-clave", hashed)
    assert not verificar_password("secreto123", "hash-invalido")


def test_token_incluye_rol_y_expiracion():
    token = crear_token(_usuario(E.RolUsuario.ADMIN.value))
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "1"
    assert payload["rol"] == "ADMIN"
    assert "exp" in payload


def test_require_admin_permite_admin_y_rechaza_socio():
    assert require_admin(_usuario(E.RolUsuario.ADMIN.value)).rol == "ADMIN"
    with pytest.raises(PermisoDenegadoError):
        require_admin(_usuario(E.RolUsuario.SOCIO.value))


def test_require_admin_o_socio_permite_ambos_roles():
    for rol in (E.RolUsuario.ADMIN, E.RolUsuario.SOCIO):
        assert require_admin_o_socio(_usuario(rol.value)).rol == rol.value


def test_openapi_se_genera_correctamente():
    assert app.openapi()["info"]["title"]


def test_me_sin_token_devuelve_401():
    response = TestClient(app).get("/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "path",
    [
        "/sedes",
        "/socios",
        "/prestamos",
        "/reservas",
        "/devoluciones",
        "/remitos",
        "/reportes/prestamos-activos-y-en-transito",
    ],
)
def test_endpoints_protegidos_sin_token_devuelven_401(path):
    assert TestClient(app).get(path).status_code == 401


def test_health_es_publico():
    assert TestClient(app).get("/health").status_code == 200
