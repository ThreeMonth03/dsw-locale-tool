# Production installation

Production continues to use official DSW server and client images. A one-shot locale installer
imports the packaged translation through the DSW API.

## Add the installer

Copy
[`production/compose.locale.yml`](https://github.com/ThreeMonth03/dsw-locale-tool/blob/main/production/compose.locale.yml)
next to the deployment's `docker-compose.yml`. Create a dedicated DSW deployment account, generate
an API key with the required locale-management permission, and store it outside Git at:

```text
secrets/dsw_locale_api_key
```

Set the installer `image:` to the immutable locale version published for the deployment's DSW minor
release. Validate and run the merged Compose configuration:

```console
docker compose -f docker-compose.yml -f compose.locale.yml config --quiet
docker compose -f docker-compose.yml -f compose.locale.yml pull locale-installer
docker compose -f docker-compose.yml -f compose.locale.yml up locale-installer
```

The installer waits for the server, imports the locale if necessary, enables it, sets it as the
default, and exits. A successful result reports `enabled: true` and `defaultLocale: true`.

## Update or roll back

Change only the installer image tag to another immutable release, then run the pull and up commands
again. Reusing a tag is idempotent. Rolling back does not delete other installed locales.

Use a fresh browser session after changing the default locale so an existing session does not retain
its previous locale selection.
