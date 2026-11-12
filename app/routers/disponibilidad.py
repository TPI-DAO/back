from fastapi import APIRouter

from app.database import DB
from app.security import CurrentUser
from app.services.disponibilidad import consultar_disponibilidad

router = APIRouter(prefix="/disponibilidad", tags=["Disponibilidad"])


@router.get("", summary="Consultar disponibilidad de libros por sede")
def disponibilidad(
    db: DB,
    _usuario: CurrentUser,
    libro_id: int | None = None,
    sede_id: int | None = None,
    titulo: str | None = None,
    solo_disponibles: bool = False,
):
    """`disponibles_netos` descuenta las reservas activas sobre ese libro en esa sede."""
    return consultar_disponibilidad(
        db, libro_id=libro_id, sede_id=sede_id, titulo=titulo, solo_disponibles=solo_disponibles
    )
