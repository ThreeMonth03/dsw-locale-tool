# depositar production Compose integration

This is a third Compose file for the `depositar-prod` branch of
`depositar/dsw-deployment`. It does not replace or fork the official DSW server and client
images. The only added container is an explicitly invoked, one-shot locale installer with no
published ports.

The merged Compose model was validated against deployment commit
[`8ab70a2`](https://github.com/depositar/dsw-deployment/commit/8ab70a279d2ac672dae3fa79f85dd80bb743d482).

## 1. Verify the DSW minor version

Check the real production `.env`, not only `example.env`:

```console
grep '^DSW_VERSION=' .env
```

The currently published installer contains locale coordinate
`depositar:zh_Hant:4.32.0` and is intended for the DSW 4.32 release line. Do not run it against
DSW 4.29 or another minor version. The `depositar-prod` branch's `example.env` still says
`DSW_VERSION=4.29`, so the deployed value must be confirmed before proceeding.

If production is not on 4.32, either upgrade DSW first or prepare and publish a locale from the
matching `sync/vX.Y` branch.

## 2. Store a dedicated DSW API key

Create an API key with an expiry date for a dedicated deployment account. In DSW 4.32, an API
key inherits its user's permissions; it does not have independent scopes.

Save only the token in the deployment directory:

```console
mkdir -p secrets
chmod 700 secrets
$EDITOR secrets/dsw_locale_api_key
chmod 600 secrets/dsw_locale_api_key
```

Add `/secrets/` to the deployment repo's `.gitignore`. Never commit this file or pass the token
as a command-line argument.

## 3. Validate the merged Compose model

Run from the `dsw-deployment` directory and replace the final path with the location of this
file:

```console
docker compose \
  --profile locale-maintenance \
  --env-file .env \
  --file docker-compose.yml \
  --file docker-compose.prod.yml \
  --file ../dsw-locale-tool/examples/depositar-production/docker-compose.locale.yml \
  config --quiet
```

The override joins only `dsw_internal`, where the production override already exposes the
`server` service as `server:3000`. It adds no host port, database volume, or restart loop.

## 4. Install or update the locale

The installer is behind the `locale-maintenance` profile, so routine `docker compose up -d`
does not run it. Explicitly target it after the DSW server is up:

```console
docker compose \
  --env-file .env \
  --file docker-compose.yml \
  --file docker-compose.prod.yml \
  --file ../dsw-locale-tool/examples/depositar-production/docker-compose.locale.yml \
  pull locale-installer

docker compose \
  --env-file .env \
  --file docker-compose.yml \
  --file docker-compose.prod.yml \
  --file ../dsw-locale-tool/examples/depositar-production/docker-compose.locale.yml \
  run --rm --no-deps locale-installer
```

A successful first installation prints `created: true`, `enabled: true`, and
`defaultLocale: true`. Rerunning the same coordinate prints `created: false` and safely
re-enables it.

To select another immutable release without editing the override, add this to production
`.env`:

```dotenv
DSW_LOCALE_INSTALLER_IMAGE=ghcr.io/threemonth03/dsw-locale-installer:4.32.0
```

For the exact verified initial image, a digest pin is also available:

```dotenv
DSW_LOCALE_INSTALLER_IMAGE=ghcr.io/threemonth03/dsw-locale-installer:4.32.0@sha256:e32c3dc290b6682276cf1ba94f74148c735e68595d2045f97226471adffe9594
```

## 5. Verify and recover

1. Confirm the command exits with status 0.
2. Open **Administration → Locales** and confirm the locale is enabled and marked default.
3. Open a private browser window and inspect login, dashboard, and questionnaire UI text.
4. Keep the previous locale installed. To roll back, select it as the default in DSW; the
   installer never deletes another locale.

Changing translation content requires a new `locale_version` and installer tag. Do not rebuild
or overwrite an already published version. When the repos move to the `depositar` organization,
only `DSW_LOCALE_INSTALLER_IMAGE` needs to change.
