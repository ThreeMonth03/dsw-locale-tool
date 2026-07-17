# CLI reference

## Translation content

Validate repository configuration:

```console
dsw-locale validate-config translation-config.yml
```

Synchronize one official release baseline and regenerate its Markdown forms:

```console
dsw-locale sync-upstream --config translation-config.yml --version v4.32 --output .
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
dsw-locale validate-pr --base-root base --head-root locale --branch sync/v4.32
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
  --version v4.32 \
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
dsw-locale release-info --config translation-config.yml --version v4.32
dsw-locale bump-release --config translation-config.yml --version v4.32
```

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
  --allowed-content-json preview.km
```

Run `dsw-locale COMMAND --help` for the complete option list.
