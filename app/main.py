import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app import models  # noqa: F401  (registra las tablas en Base.metadata)
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.errors import AppError
from app.routers import (
    catalogo,
    devoluciones,
    disponibilidad,
    ejemplares,
    prestamos,
    remitos,
    reportes,
    reservas,
    sedes,
    socios,
)
from app.seed import seed_catalogos, seed_demo

log = logging.getLogger("biblioteca")


def _esperar_db(intentos: int = 15, espera: float = 2.0) -> None:
    for i in range(1, intentos + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            log.warning("Base de datos no disponible (intento %s/%s)", i, intentos)
            time.sleep(espera)
    raise RuntimeError("No se pudo conectar a la base de datos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _esperar_db()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_catalogos(db)
        if settings.seed_demo_data:
            seed_demo(db)
    yield


app = FastAPI(
    title="Biblioteca - Préstamos Interbibliotecarios",
    description="TP Integrador DAO 2026 - Grupo 5. Gestión de sedes, socios, catálogo, préstamos, reservas, remitos y devoluciones.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.mensaje})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": "La operación viola una restricción de integridad (duplicado o referencia inexistente)."},
    )


for modulo in (sedes, socios, ejemplares, reservas, prestamos, remitos, devoluciones, disponibilidad, reportes):
    app.include_router(modulo.router)
for r in (catalogo.libros_router, catalogo.generos_router, catalogo.autores_router, catalogo.editoriales_router):
    app.include_router(r)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}
