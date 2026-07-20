# Ephemeral DSW preview stack

This Compose file is for CI screenshots only. It creates disposable PostgreSQL and MinIO
volumes, binds the DSW server and client to localhost, and reads a generated
`runtime/application.yml`. The screenshot workflow covers the main pages plus project settings,
sharing, comments, Documents, project files, file upload and deletion, organization and
authentication settings, and OpenID configuration.

```console
dsw-locale preview-config --output preview/runtime/application.yml
DSW_VERSION=X.Y DSW_CLIENT_IMAGE=datastewardshipwizard/wizard-client:X.Y \
  docker compose -f preview/docker-compose.yml up -d
```

If ports 3000 or 8080 are already used, keep the three URLs aligned:

```console
dsw-locale preview-config \
  --output preview/runtime/application.yml \
  --client-url http://localhost:8180/wizard
DSW_VERSION=X.Y DSW_CLIENT_IMAGE=datastewardshipwizard/wizard-client:X.Y \
  DSW_SERVER_PORT=3100 DSW_CLIENT_PORT=8180 \
  docker compose -f preview/docker-compose.yml up -d
```

Always remove its data after use:

```console
docker compose -f preview/docker-compose.yml down --volumes
```

It intentionally uses DSW's fresh-database demonstration account. Never expose this stack to
a shared network or reuse its configuration for production.
