import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app import models  # noqa: F401  (registra las tablas en Base.metadata)
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.errors import AppError
from app.routers import (
    auth,
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
from app.security import require_admin
from app.seed import seed_admin, seed_catalogos, seed_demo

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
        seed_admin(db)
        if settings.seed_demo_data:
            seed_demo(db)
    yield


app = FastAPI(
    title="Biblioteca - Préstamos Interbibliotecarios",
    description="TP Integrador DAO 2026 - Grupo 5. Gestión de sedes, socios, catálogo, préstamos, reservas, remitos y devoluciones.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origen.strip() for origen in settings.cors_origins.split(",") if origen.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.mensaje},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": "La operación viola una restricción de integridad (duplicado o referencia inexistente)."},
    )


app.include_router(auth.router)
for modulo in (sedes, socios, ejemplares, reservas, prestamos, devoluciones, disponibilidad):
    app.include_router(modulo.router)
app.include_router(remitos.router, dependencies=[Depends(require_admin)])
app.include_router(reportes.router, dependencies=[Depends(require_admin)])
for r in (catalogo.libros_router, catalogo.generos_router, catalogo.autores_router, catalogo.editoriales_router):
    app.include_router(r)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}
