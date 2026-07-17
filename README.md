# DSW Locale Tool

`dsw-locale-tool` builds and previews local DSW UI translations on top of the official
[`wizard-locales`](https://github.com/ds-wizard/wizard-locales) catalogs.

Translation content and automation are kept in separate repositories:

- [dsw-ui-locales-zh_Hant](https://github.com/ThreeMonth03/dsw-ui-locales-zh_Hant) contains
  the human-editable Markdown translation forms.
- This repository contains synchronization, validation, packaging, preview, and deployment tools.

Start with the [documentation](https://www.threemonth03.com/dsw-locale-tool/). Translators do not
need to install this project or edit code.

## Development

```console
make install-dev
make check
```

## Common commands

```console
dsw-locale sync-upstream --config translation-config.yml --version v4.32 --output .
dsw-locale refresh-tree --root .
dsw-locale audit --root . --report-dir reports
dsw-locale build-source --config translation-config.yml --version v4.32 --root . --output build/locale
```

See the [CLI reference](docs/commands.md) for every command.
