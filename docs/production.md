# Production installation

Production continues to use the official DSW server. A one-shot locale installer imports the
packaged translation through the DSW API. An optional localizable client image covers confirmed
frontend strings that bypass gettext in the official client.

## Add the installer

Copy
[`production/compose.locale.yml`](https://github.com/ThreeMonth03/dsw-locale-tool/blob/main/production/compose.locale.yml)
next to the deployment's `docker-compose.yml`. Create a dedicated DSW deployment account, generate
an API key with the required locale-management permission, and store it outside Git at:

```text
secrets/dsw_locale_api_key
```

Set `DSW_LOCALE_INSTALLER_IMAGE` in the deployment's Compose environment or `.env` file. Use an
immutable tag from the
[published installer package](https://github.com/ThreeMonth03/dsw-locale-tool/pkgs/container/dsw-locale-installer)
that matches the deployment's DSW minor release:

```text
DSW_LOCALE_INSTALLER_IMAGE=ghcr.io/threemonth03/dsw-locale-installer:<locale-version>
```

Replace `<locale-version>` with the complete published locale version. The Compose fragment rejects
an unset image so it cannot silently install a stale example release. Validate and run the merged
Compose configuration:

```console
docker compose -f docker-compose.yml -f compose.locale.yml config --quiet
docker compose -f docker-compose.yml -f compose.locale.yml pull locale-installer
docker compose -f docker-compose.yml -f compose.locale.yml up locale-installer
```

The installer shares the `server` service's network namespace, so deployments do not need to copy
their internal network names into this fragment.

The installer waits for the server, imports the locale if necessary, enables it, sets it as the
default, and exits. A successful result reports `enabled: true` and `defaultLocale: true`.

## Update or roll back

Change only `DSW_LOCALE_INSTALLER_IMAGE` to another immutable release, then run the pull and up
commands again. Reusing a tag is idempotent. Rolling back does not delete other installed locales.

Use a fresh browser session after changing the default locale so an existing session does not retain
its previous locale selection.

## Replace the client only when required

Preview reports identify translations that still render in English. If the matching DSW release
needs a frontend transform, choose its immutable image from the
[published localizable clients](https://github.com/ThreeMonth03/dsw-locale-tool/pkgs/container/dsw-wizard-client)
and set:

```text
DSW_CLIENT_IMAGE=ghcr.io/threemonth03/dsw-wizard-client:<app-version>-l10n-<patch-set>
```

Add
[`production/compose.client.yml`](https://github.com/ThreeMonth03/dsw-locale-tool/blob/main/production/compose.client.yml)
to the same Compose command:

```console
docker compose \
  -f docker-compose.yml \
  -f compose.locale.yml \
  -f compose.client.yml \
  config --quiet
docker compose \
  -f docker-compose.yml \
  -f compose.client.yml \
  pull client
docker compose \
  -f docker-compose.yml \
  -f compose.client.yml \
  up --detach client
```

The fragment overrides only `client.image`. Remove it when the official client release exposes all
required text to gettext.
