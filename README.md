# Backend

Para iniciar la API y PostgreSQL de demostración local:

```bash
docker compose up --build
```

La API queda en `http://127.0.0.1:8000` y Swagger en `http://127.0.0.1:8000/docs`.
Docker publica la API y PostgreSQL en `127.0.0.1`. Para ejecutar la interfaz,
consulta `../front/README.md`.

Al iniciar se crean las tablas, los catálogos y el administrador inicial:
`admin` / `admin1234`. La API utiliza autenticación JWT y roles `ADMIN` y `SOCIO`.
Los datos de demostración se cargan únicamente si no hay sedes existentes.

Las variables opcionales y sus valores locales están en `.env.example`. Para
personalizarlas, copiá ese archivo a `.env` antes de iniciar Docker Compose.
Para detener los servicios conservando la base de datos: `docker compose down`.
Si el puerto 5432 está ocupado, configurá `POSTGRES_PORT=5433` en `.env`.
Para ejecutar Python fuera de Docker, ajustá también el puerto de `DATABASE_URL`.
La API dentro de Docker continúa conectándose a `db:5432`.

## Datos para gráficos de reportes

Para agregar actividad de demostración a una base existente, sin borrar sus datos:

```bash
docker compose exec -T api python -m app.seed_reportes
```

Agrega libros y socios identificados como demo, ejemplares en las sedes activas,
y préstamos activos, vencidos y en tránsito con sus remitos e historial.
La carga es transaccional y no se repite si ya fue ejecutada.

## Pruebas

```bash
uv sync --locked
uv run pytest
```
