# DSW Locale Tool

Synchronize Traditional Chinese DSW UI translations with the official Weblate catalogs.

Translators fill Markdown forms in
[dsw-ui-locales-zh_Hant](https://github.com/ThreeMonth03/dsw-ui-locales-zh_Hant).
This repository provides version discovery, catalog synchronization, contribution checks,
and controlled Weblate submissions. It does not build or deploy DSW.

Read the [documentation](https://www.threemonth03.com/dsw-locale-tool/).

## Development

```console
make install-dev
make check
```

## Workflow

1. Synchronize official PO/POT files and generate forms for empty translations.
2. Review translation PRs using the existing wording as the terminology baseline.
3. Prepare a small submission with **Submit translations to Weblate**.
4. Inspect the report, then explicitly apply the same plan hash.
5. Review fuzzy translations on official Weblate; synchronization reads back their status.

No Weblate token is needed for download, validation, or dry-run PO export.
