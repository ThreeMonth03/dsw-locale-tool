# Ephemeral DSW preview stack

This Compose file is for CI screenshots only. It creates disposable PostgreSQL and MinIO
volumes, binds the DSW server and client to localhost, and reads a generated
`runtime/application.yml`.

```console
dsw-locale preview-config --output preview/runtime/application.yml
DSW_VERSION=4.32 docker compose -f preview/docker-compose.yml up -d
```

If ports 3000 or 8080 are already used, keep the three URLs aligned:

```console
dsw-locale preview-config \
  --output preview/runtime/application.yml \
  --client-url http://localhost:8180/wizard
DSW_VERSION=4.32 DSW_SERVER_PORT=3100 DSW_CLIENT_PORT=8180 \
  docker compose -f preview/docker-compose.yml up -d
```

Always remove its data after use:

```console
docker compose -f preview/docker-compose.yml down --volumes
```

It intentionally uses DSW's fresh-database demonstration account. Never expose this stack to
a shared network or reuse its configuration for production.
