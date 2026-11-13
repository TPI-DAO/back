# Backend

Para iniciar la API y PostgreSQL de demostración local:

```bash
docker compose up --build
```

La API queda en `http://127.0.0.1:8000` y Swagger en `http://127.0.0.1:8000/docs`. La API no
implementa autenticación y Docker publica ambos puertos únicamente en `127.0.0.1`; no expongas esta
configuración en una red pública. Para ejecutar la interfaz, consulta `front/README.md`.