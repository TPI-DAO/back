# Biblioteca – Sistema de Préstamos Interbibliotecarios (Backend)

TP Integrador DAO 2026 · Grupo 5 · FastAPI + PostgreSQL + uv + Docker.

## Ejecutar

```bash
docker compose up --build
```
- API: http://localhost:8000 · Swagger: http://localhost:8000/docs
- Al iniciar se crean las tablas, se cargan los estados y (si `SEED_DEMO_DATA=true`) datos de ejemplo
  (3 sedes, 3 socios, 3 libros con ejemplares).
- Configuración en `.env` (ver `.env.example`).

Local sin Docker: `uv sync && uv run uvicorn app.main:app --reload` (con un Postgres corriendo).
Tests de los patrones: `uv run pytest`.
Opcional: `uv lock` para fijar versiones (el Dockerfile usa `uv.lock` si existe).

## Correspondencia con el modelo del TP

| Modelo original | Implementación |
|---|---|
| Sedes / Estado_Sedes | `sedes` / `estado_sedes` |
| Socios / EstadoSocio | `socios` (+ `dni` único) / `estado_socios` |
| Genero, Autor, Editorial, Libros | igual (+ ISBN único) |
| LibroxSede / EstadoLibro | `ejemplares` (PK propia, varios por sede, `codigo_inventario`) / `estado_ejemplares` |
| Reservas / EstadoReserva | `reservas` / `estado_reservas` |
| Prestamo / EstadoPrestamo | `prestamos` (+ ejemplar, fechas de solicitud, préstamo, vencimiento, devolución) |
| DetallePrestamo / EstadoDetalle | `remitos` / `estado_remitos` (número `REM-000001`, tipo ENVIO/RETORNO) |
| HistorialPrestamo | `historial_remitos` (trazabilidad de cada cambio de estado) |
| — | `devoluciones` (estado físico, días de atraso, multa) |

Las FK del `.sql` original estaban invertidas (p. ej. `Libros.id → LibroxSede.id_libro`); acá se corrigieron.

## Flujo principal

1. `POST /prestamos` – local (origen = destino): queda `ACTIVO`. Interbibliotecario: `SOLICITADO`, ejemplar `RESERVADO`.
2. `POST /remitos` (empaquetar) → `POST /remitos/{id}/despachar` → `POST /remitos/{id}/recibir` (con estado físico).
   Al recibir en buen estado el préstamo pasa a `ACTIVO` y comienza a correr el vencimiento.
3. `POST /devoluciones` – registra estado físico y multa. Si era interbibliotecario genera un remito `RETORNO`
   que vuelve el ejemplar a su sede dueña.
4. `GET /remitos/{id}/trazabilidad` – historial completo del remito.

Ciclo del remito: `EMPAQUETADO → DESPACHADO → RECIBIDO | INCIDENCIA` (`EMPAQUETADO → CANCELADO`).

## Validaciones de negocio implementadas

- No prestar ejemplares no disponibles; solo ejemplares de la sede de origen.
- No prestar a socios inhabilitados (ni con préstamos vencidos; máximo de préstamos abiertos configurable).
- Control de vencimientos (`POST /prestamos/controlar-vencimientos`, `GET /prestamos/vencidos`).
- Trazabilidad del remito en todo el trayecto (`historial_remitos`).
- Sin duplicados: DNI de socio, ISBN, código de inventario, nombre de sede, reserva activa repetida.
- Sin préstamos, reservas ni envíos desde/hacia sedes dadas de baja; no se puede dar de baja una sede con
  préstamos abiertos o remitos en curso.
- Las reservas activas de otros socios restan disponibilidad.

## Patrones de diseño

- **State** – `app/patterns/remito_state.py`: ciclo de vida del remito.
- **Strategy** – `app/patterns/multa_strategy.py`: cálculo de multas (`diaria` / `escalonada`, por config).

## Reportes (`/reportes/...`)

1. `prestamos-activos-y-en-transito`
2. `prestamos-vencidos-y-multas`
3. `libros-mas-solicitados` (filtros `desde`, `hasta`, `limit`)
4. `disponibilidad-por-sede`
5. `envios-exitosos-e-incidencias`
6. `movimiento-ejemplares` (envíos por origen/destino y tiempo promedio de tránsito)

Además: `GET /disponibilidad` (consulta por libro/sede/título).
