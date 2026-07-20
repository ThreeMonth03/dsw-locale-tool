# CLI reference

## Translation content

Validate repository configuration:

```console
dsw-locale validate-config translation-config.yml
```

Synchronize one official release baseline and regenerate its Markdown forms:

```console
VERSION_KEY=vX.Y
dsw-locale sync-upstream --config translation-config.yml --version "$VERSION_KEY" --output .
dsw-locale refresh-tree --root .
```

Create JSON and Markdown audit reports:

```console
dsw-locale audit \
  --root . \
  --report-dir reports \
  --fail-on placeholders \
  --fail-on structure
```

Validate the scope and locale version of a translation pull request:

```console
dsw-locale validate-pr --base-root base --head-root locale --branch "sync/$VERSION_KEY"
```

Create a form for confirmed UI text that is absent from the official POT:

```console
dsw-locale add-runtime \
  --root . \
  --component wizard \
  --source "English text observed in DSW" \
  --translation "在 DSW 中看到的英文文字"
```

Fill blank forms from another release only when their complete source identity matches:

```console
dsw-locale propagate \
  --source-root ../source-release \
  --target-root ../target-release \
  --report-dir reports/propagation
```

## Build and package

```console
dsw-locale build-source \
  --config translation-config.yml \
  --version "$VERSION_KEY" \
  --root . \
  --output build/locale

dsw-locale package --source build/locale --output dist/locale.zip
```

The package command uses the pinned official DSW locale packager.

## Version automation

```console
dsw-locale version-report \
  --config translation-config.yml \
  --repository-root . \
  --report-dir reports/versions \
  --fail-on-drift

dsw-locale reconcile-versions \
  --config translation-config.yml \
  --report-dir reports/maintenance

dsw-locale maintained-matrix --config translation-config.yml
dsw-locale release-info --config translation-config.yml --version "$VERSION_KEY"
dsw-locale bump-release --config translation-config.yml --version "$VERSION_KEY"
```

## Frontend localization

Resolve the immutable client image for an exact DSW application release:

```console
APP_VERSION=X.Y.Z
dsw-locale frontend-reference \
  --manifest frontend/transforms.yml \
  --version "$APP_VERSION"
```

Apply the same strict transforms to a checkout of that upstream release:

```console
dsw-locale localize-frontend \
  --manifest frontend/transforms.yml \
  --version "$APP_VERSION" \
  --source-root ../engine-frontend \
  --report reports/frontend.json
```

Each transform accepts either its exact upstream source or its exact localized result. Any other
source state fails instead of applying a guessed replacement.

## DSW preview and installation

```console
dsw-locale preview-config --output preview/runtime/application.yml

dsw-locale install-dsw \
  --bundle dist/locale.zip \
  --api-url http://wizard-server:3000/wizard-api \
  --api-key-file /run/secrets/dsw_locale_api_key \
  --default-locale

dsw-locale seed-project --knowledge-model preview.km --project-name "Locale Preview"

dsw-locale capture-preview \
  --output preview-artifact \
  --locale-root ../dsw-ui-locales-zh_Hant \
  --review-manifest review/pages.yml \
  --project-uuid "$PROJECT_UUID" \
  --file-project-uuid "$FILE_PROJECT_UUID" \
  --preview-file preview/fixtures/preview.csv \
  --allowed-content-json preview.km \
  --allowed-content-json file-preview.km
```

Seed a private disposable DSW and generate the public review route policy:

```console
dsw-locale prepare-review \
  --locale-bundle dist/locale.zip \
  --knowledge-model preview.km \
  --review-manifest review/pages.yml \
  --output review/runtime/release/site \
  --dsw-version "$DSW_VERSION" \
  --translation-ref "$TRANSLATION_REF" \
  --revision "$TRANSLATION_SHA"
```

Verify a running gateway from its internal Docker network:

```console
dsw-locale verify-review --origin http://gateway:8080
```

Keep an ephemeral review alive until its browser activity or hard lifetime expires:

```console
dsw-locale wait-review \
  --compose-file review/docker-compose.yml \
  --project-name "$COMPOSE_PROJECT" \
  --tunnel-container "$TUNNEL_CONTAINER" \
  --idle-timeout-minutes 30 \
  --hard-timeout-minutes 180
```

The complete host workflow is documented in the {doc}`public review sandbox
<review-sandbox>` guide.

Run `dsw-locale COMMAND --help` for the complete option list.
