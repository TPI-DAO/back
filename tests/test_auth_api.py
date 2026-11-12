import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.seed import seed_admin, seed_catalogos

ADMIN = {"username": "admin", "password": "admin1234"}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        seed_catalogos(db)
        seed_admin(db)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post("/auth/token", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _crear_socio_y_usuario(client: TestClient, admin: dict) -> None:
    response = client.post(
        "/socios", json={"dni": "12345678", "nombre": "Ana", "apellido": "Test"}, headers=admin
    )
    assert response.status_code == 201, response.text
    response = client.post(
        "/auth/usuarios",
        json={
            "username": "ana",
            "email": "ana@test.com",
            "password": "ana12345",
            "rol": "SOCIO",
            "socio_id": response.json()["id"],
        },
        headers=admin,
    )
    assert response.status_code == 201, response.text


def test_login_incorrecto_devuelve_401(client):
    response = client.post("/auth/token", data={"username": "admin", "password": "mala"})
    assert response.status_code == 401


def test_admin_accede_a_todos_los_modulos(client):
    headers = _login(client, **ADMIN)
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["rol"] == "ADMIN"
    assert client.get("/sedes", headers=headers).status_code == 200
    assert client.get("/remitos", headers=headers).status_code == 200
    assert client.get("/reportes/prestamos-activos-y-en-transito", headers=headers).status_code == 200


def test_socio_solo_accede_a_sus_propios_datos(client):
    admin = _login(client, **ADMIN)
    _crear_socio_y_usuario(client, admin)
    socio = _login(client, "ana", "ana12345")

    assert client.get("/socios", headers=socio).status_code == 403
    assert client.get("/remitos", headers=socio).status_code == 403
    assert client.get("/reportes/prestamos-activos-y-en-transito", headers=socio).status_code == 403
    assert client.get("/socios/me", headers=socio).status_code == 200
    assert client.get("/prestamos", headers=socio).status_code == 200
    assert client.get("/disponibilidad", headers=socio).status_code == 200

    ajeno = client.post(
        "/prestamos",
        json={"socio_id": 999, "libro_id": 1, "sede_origen_id": 1, "sede_destino_id": 1},
        headers=socio,
    )
    assert ajeno.status_code == 403


def test_admin_puede_crear_usuarios_y_desactivarlos(client):
    admin = _login(client, **ADMIN)
    _crear_socio_y_usuario(client, admin)
    usuarios = client.get("/auth/usuarios", headers=admin).json()
    ana = next(u for u in usuarios if u["username"] == "ana")

    response = client.patch(
        f"/auth/usuarios/{ana['id']}/estado", json={"activo": False}, headers=admin
    )
    assert response.status_code == 200
    assert response.json()["activo"] is False

    response = client.post("/auth/token", data={"username": "ana", "password": "ana12345"})
    assert response.status_code == 401
