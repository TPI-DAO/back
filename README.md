# Biblioteca — Backend

## 1. Cómo levantar el proyecto

### Con Docker Compose

**Requisito:** Docker con Compose disponible y el motor de Docker en ejecución.
Ejecutá los comandos desde la raíz de este repositorio (`back/`).

1. Si necesitás personalizar la configuración, creá `.env` a partir de `.env.example`
   antes de iniciar. Los valores por defecto permiten ejecutar la demostración local.

   PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

   Linux / macOS:

   ```bash
   cp .env.example .env
   ```

2. Levantá la API y PostgreSQL:

   ```bash
   docker compose up --build
   ```

3. Abrí los servicios:

   | Servicio | Dirección |
   | --- | --- |
   | API | http://127.0.0.1:8000 |
   | Swagger / documentación interactiva | http://127.0.0.1:8000/docs |
   | Estado de la API | http://127.0.0.1:8000/health |
   | PostgreSQL desde el host | `127.0.0.1:5432` |

4. Iniciá sesión con **`admin` / `admin1234`**. Para usar la aplicación web,
   seguí el [README del frontend](https://github.com/TPI-DAO/front#readme)
   en otra terminal.

Al arrancar se crean las tablas, los catálogos de estados y el administrador inicial
si todavía no existen. Con `SEED_DEMO_DATA=true`, se cargan datos de demostración
solo cuando no hay sedes: 3 sedes, 6 socios, 12 libros, ejemplares, reservas,
préstamos y una devolución. Los socios de demostración no reciben automáticamente
una cuenta de acceso; el administrador puede crearla desde la gestión de usuarios.

Para detener los servicios conservando la base de datos:

```bash
docker compose down
```

Los datos persisten en el volumen `pgdata`. Si el puerto 5432 está ocupado,
configurá `POSTGRES_PORT=5433` en `.env` antes de iniciar. Dentro de Docker,
la API sigue conectándose a `db:5432`.

### API local, fuera de Docker

**Requisitos:** Python 3.12 o superior, `uv` y PostgreSQL disponible.
Podés levantar únicamente la base de datos con:

```bash
docker compose up -d db
```

Creá `.env` como en el paso anterior y ajustá `DATABASE_URL` a tu base de datos.
El valor del ejemplo es:

```dotenv
DATABASE_URL=postgresql+psycopg://biblioteca:biblioteca@localhost:5432/biblioteca
```

Si cambiaste `POSTGRES_PORT`, usá también ese puerto en `DATABASE_URL`.
Luego ejecutá:

```bash
uv sync --locked
uv run uvicorn app.main:app --reload
```

### Agregar datos para los reportes

Con la API de Docker y la base de datos en ejecución:

```bash
docker compose exec -T api python -m app.seed_reportes
```

Si ejecutás la API localmente, usá `uv run python -m app.seed_reportes`.
La carga agrega 4 libros, 9 socios, ejemplares y 9 préstamos con sus remitos e
historial, distribuidos entre activos, vencidos y en tránsito. Requiere al menos
dos sedes activas y un catálogo con género, autor y editorial. Es transaccional,
no borra datos existentes y no se repite si ya fue ejecutada.

## 2. De qué trata el proyecto

Trabajo Práctico Integrador de **Diseño de Aplicaciones (DAO 2026), Grupo 5**.
El sistema administra una biblioteca con múltiples sedes y permite prestar
libros tanto en la sede que posee el ejemplar como entre sedes distintas.

Incluye gestión de sedes, socios, catálogo, ejemplares y usuarios; reservas;
préstamos locales e interbibliotecarios; remitos de envío y retorno;
devoluciones con estado físico y multas; disponibilidad y reportes.

El backend concentra las reglas de negocio, la autorización y la persistencia.
El frontend consume su API HTTP.

## 3. Tecnologías utilizadas

| Tecnología | Uso en el proyecto |
| --- | --- |
| Python 3.12+ | Lenguaje del backend; la imagen Docker utiliza Python 3.12. |
| FastAPI | API HTTP, dependencias, validación de entradas y documentación OpenAPI/Swagger. |
| Uvicorn | Servidor ASGI para ejecutar la API. |
| SQLAlchemy 2 | Mapeo objeto-relacional, consultas, sesiones y transacciones. |
| PostgreSQL 16 | Base de datos relacional utilizada por Docker Compose. |
| Psycopg 3 | Conexión de Python con PostgreSQL. |
| Pydantic / pydantic-settings | Esquemas de entrada/salida y configuración desde variables de entorno y `.env`. |
| PyJWT | Generación y validación de tokens JWT. |
| pwdlib con Argon2 | Hash y verificación de contraseñas. |
| python-multipart | Procesamiento del formulario de inicio de sesión. |
| uv | Gestión de dependencias y entorno virtual; versiones fijadas en `uv.lock`. |
| Docker / Docker Compose | Construcción y ejecución coordinada de la API y PostgreSQL. |
| pytest / HTTPX | Pruebas de patrones, autenticación, API y cargas de demostración. |
| SQLite | Base en memoria para pruebas que no requieren PostgreSQL. |

## 4. Arquitectura y modelo de datos

```text
app/
  main.py       Inicio, registro de rutas y manejo de errores
  config.py     Configuración de la aplicación
  database.py   Engine, sesiones y dependencia de base de datos
  models.py     Entidades y relaciones de SQLAlchemy
  schemas.py    Contratos de entrada y salida
  security.py   Autenticación y autorización
  routers/      Endpoints HTTP por dominio
  services/     Casos de uso y reglas de negocio
  patterns/     State de remitos y Strategy de multas
  seed.py       Catálogos, administrador y datos iniciales
  seed_reportes.py  Actividad adicional de demostración
tests/          Pruebas automatizadas
```

Las operaciones de préstamos, reservas, remitos y devoluciones se organizan
en servicios. Las altas y modificaciones de catálogos también utilizan la sesión
de SQLAlchemy desde sus routers.

### Correspondencia con el modelo del TP

| Concepto del modelo original | Implementación |
| --- | --- |
| Sedes / Estado_Sedes | `sedes` / `estado_sedes` |
| Socios / EstadoSocio | `socios` con DNI único / `estado_socios` |
| Género, Autor, Editorial, Libros | `generos`, `autores`, `editoriales`, `libros` con ISBN único |
| LibroxSede / EstadoLibro | `ejemplares` con identidad propia y código de inventario / `estado_ejemplares` |
| Reservas / EstadoReserva | `reservas` / `estado_reservas` |
| Préstamo / EstadoPrestamo | `prestamos`, asociados a un ejemplar y a las sedes de origen y destino |
| DetallePrestamo / EstadoDetalle | `remitos` de tipo `ENVIO` o `RETORNO` / `estado_remitos` |
| HistorialPrestamo | `historial_remitos`, con cada transición del remito |
| Devolución | `devoluciones`, con condición física, atraso, multa y posible remito de retorno |

Las claves foráneas se definen desde la entidad dependiente hacia la referenciada.
Cada ejemplar representa una copia física y conserva su sede propietaria durante
el circuito interbibliotecario; el traslado se registra mediante los remitos.

## 5. Patrones utilizados

### State: ciclo de vida del remito

Implementado en `app/patterns/remito_state.py`. Cada estado encapsula las
acciones permitidas; una transición inválida genera `TransicionInvalidaError`.

```text
EMPAQUETADO → DESPACHADO → RECIBIDO
     │              └──→ INCIDENCIA
     └──→ CANCELADO
```

`Recibido`, `Incidencia` y `Cancelado` son estados terminales. Los servicios de
remitos consultan estos objetos para despachar, recibir, cancelar o registrar
incidencias, y guardan la transición en el historial.

### Strategy: cálculo de multas

Implementado en `app/patterns/multa_strategy.py`. `EstrategiaMulta` define el
contrato y las implementaciones intercambiables son:

- **MultaDiaria:** monto por día multiplicado por los días de atraso.
- **MultaEscalonada:** monto base durante los primeros 7 días y el doble para
  los días restantes.

La función `obtener_estrategia` selecciona la implementación mediante
`MULTA_ESTRATEGIA`, sin cambiar el servicio de devoluciones. Los importes se
calculan con `Decimal` y se redondean a centavos. Los reportes de multas también
utilizan la estrategia configurada.

### Inyección de dependencias

Las dependencias de FastAPI suministran la sesión de base de datos (`DB`),
el usuario autenticado (`CurrentUser`) y las restricciones de rol (`require_admin`).
Esto centraliza el acceso a esos recursos en los endpoints.

## 6. Transacciones y consistencia

Cada petición que utiliza `DB` recibe una sesión de SQLAlchemy. Los servicios
agrupan los cambios de cada operación y hacen `commit()` al finalizarla.
`flush()` permite obtener identificadores y ejecutar cambios pendientes dentro
de la misma transacción; no confirma la operación.

| Operación | Cambios confirmados en conjunto |
| --- | --- |
| Solicitar préstamo | Alta del préstamo, estado del ejemplar y cumplimiento de la reserva propia, si existe. |
| Cancelar solicitud | Cancelación del préstamo y del remito empaquetado, liberación del ejemplar y restauración de la reserva cuando corresponde. |
| Generar remito | Alta del remito y primer registro de historial. |
| Despachar / recibir | Estado y fechas del remito, estado del ejemplar, cambios del préstamo y registro de historial. |
| Registrar devolución | Alta de devolución y multa, cierre del préstamo, estado del ejemplar y remito de retorno con historial cuando corresponde. |

Si una operación falla antes del commit, los cambios pendientes no se confirman;
la dependencia cierra la sesión al finalizar la petición y descarta la transacción
abierta. La carga adicional de reportes usa `SessionLocal.begin()`, que confirma
al terminar correctamente y hace rollback ante una excepción.

En la selección del ejemplar para un préstamo y en determinadas actualizaciones
se utiliza `SELECT ... FOR UPDATE` para bloquear la fila durante la transacción.
Las claves foráneas y restricciones únicas complementan las validaciones de
negocio. Las violaciones de integridad se responden como HTTP `409`.

El circuito completo de envío y devolución se compone de varias peticiones:
cada acción se confirma por separado, conservando su estado e historial entre pasos.

## 7. Autenticación y roles

- **ADMIN:** gestión del sistema, usuarios, remitos, reportes y registro de devoluciones.
- **SOCIO:** consulta de catálogo y disponibilidad, solicitudes y cancelaciones
  propias, consulta de sus préstamos, reservas y devoluciones.

El administrador inicial se crea con `ADMIN_USERNAME` y `ADMIN_PASSWORD`.
Las cuentas de socios se crean con `POST /auth/usuarios` por un administrador.

Para probar la API desde Swagger, abrí `/docs` y usá **Authorize** con las
credenciales. También podés obtener un token enviando un formulario a
`POST /auth/token`; por ejemplo, desde Bash:

```bash
curl -X POST http://127.0.0.1:8000/auth/token -H "Content-Type: application/x-www-form-urlencoded" -d "username=admin&password=admin1234"
```

La respuesta incluye `access_token`. En las peticiones autenticadas se envía
`Authorization: Bearer <access_token>`. `GET /auth/me` devuelve el usuario actual.
El backend controla tanto el rol como la pertenencia de las operaciones al socio.

## 8. Flujo principal y reglas de negocio

1. **Préstamo local:** `POST /prestamos` con la misma sede de origen y destino.
   Se activa inmediatamente y se calcula el vencimiento.
2. **Préstamo interbibliotecario:** sedes distintas. Queda `SOLICITADO` y el
   ejemplar `RESERVADO`. `POST /remitos` genera el envío empaquetado.
3. **Despacho y recepción:** `POST /remitos/{id}/despachar` pone el material
   en tránsito; `POST /remitos/{id}/recibir` registra el estado físico.
   La recepción en buen estado activa el préstamo e inicia su plazo.
4. **Devolución:** `POST /devoluciones` registra condición física, atraso y multa.
   Si es interbibliotecaria y el ejemplar no fue extraviado ni destruido, genera
   automáticamente el remito de retorno a la sede propietaria.
5. **Trazabilidad:** `GET /remitos/{id}/trazabilidad` o
   `GET /remitos/numero/{numero}/trazabilidad` devuelve el historial.

Validaciones principales:

- Solo se prestan ejemplares disponibles de la sede de origen.
- El socio debe estar habilitado, no tener préstamos vencidos sin devolver,
  respetar el máximo de préstamos abiertos y no repetir un libro ya prestado.
- Las reservas activas de otros socios comprometen disponibilidad.
- Solo se cancelan préstamos `SOLICITADO` y reservas `ACTIVA`.
- No se admiten operaciones de préstamo, reserva o envío con sedes dadas de baja;
  una sede con préstamos abiertos o remitos en curso no puede darse de baja.
- Se controlan duplicados de DNI, ISBN, código de inventario, nombre de sede
  y reservas activas del mismo socio/libro/sede.
- `POST /prestamos/controlar-vencimientos` marca como `VENCIDO` los préstamos
  activos cuyo plazo terminó; `GET /prestamos/vencidos` permite consultarlos.

## 9. Reportes

Los endpoints bajo `/reportes` requieren rol `ADMIN`:

| Endpoint | Información |
| --- | --- |
| `/prestamos-activos-y-en-transito` | Préstamos activos, vencidos y en tránsito, más remitos despachados. |
| `/prestamos-vencidos-y-multas` | Atrasos y multas proyectadas. |
| `/libros-mas-solicitados` | Demanda interbibliotecaria; filtros `desde`, `hasta` y `limit`. |
| `/disponibilidad-por-sede` | Stock y disponibilidad por sede. |
| `/envios-exitosos-e-incidencias` | Resultados del circuito logístico. |
| `/movimiento-ejemplares` | Envíos por origen/destino y tiempo promedio de tránsito. |

Además, `GET /disponibilidad` permite consultar por libro, sede o título.
La interfaz web presenta los primeros cuatro reportes con tablas y gráficos.

## 10. Configuración

Los valores de referencia están en [`.env.example`](.env.example).

| Variable | Uso / valor local |
| --- | --- |
| `DATABASE_URL` | Conexión usada al ejecutar la API fuera de Docker. |
| `POSTGRES_PORT` | Puerto de PostgreSQL publicado en el host; `5432`. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Opciones de Compose; por defecto `biblioteca`. |
| `DIAS_PRESTAMO` | Plazo del préstamo; `14`. |
| `MAX_PRESTAMOS_POR_SOCIO` | Límite de préstamos abiertos; `3`. |
| `MULTA_ESTRATEGIA` | `diaria` o `escalonada`; por defecto `diaria`. |
| `MULTA_MONTO_DIA` | Monto base por día; `50`. |
| `CORS_ORIGINS` | Orígenes separados por coma; permite `localhost` y `127.0.0.1` en puertos 5173 y 3000. |
| `JWT_SECRET`, `JWT_ALGORITHM` | Firma de tokens; algoritmo local `HS256`. |
| `ACCESS_TOKEN_MINUTES` | Vigencia del token; `60`. |
| `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Administrador inicial; `admin`, `admin@biblio.test`, `admin1234`. |
| `SEED_DEMO_DATA` | Habilita la carga inicial de demostración; `true`. |

Compose construye la URL interna de la base a partir de `POSTGRES_USER`,
`POSTGRES_PASSWORD` y `POSTGRES_DB`; no utiliza el host de `DATABASE_URL`.

## 11. Pruebas

Desde la raíz del repositorio, con Python y `uv` instalados:

```bash
uv sync --locked
uv run pytest
```

Las pruebas incluyen autenticación y autorización, endpoints de autenticación,
transiciones de State, cálculos de Strategy, reglas de remitos, reportes y
coherencia e idempotencia de las cargas de demostración. Las pruebas que crean
datos utilizan SQLite en memoria, sin requerir levantar PostgreSQL.
