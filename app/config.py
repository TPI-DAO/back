from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://biblioteca:biblioteca@localhost:5432/biblioteca"
    dias_prestamo: int = 14
    max_prestamos_por_socio: int = 3
    multa_estrategia: str = "diaria"  # diaria | escalonada
    multa_monto_dia: Decimal = Decimal("50")
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    seed_demo_data: bool = True


settings = Settings()
