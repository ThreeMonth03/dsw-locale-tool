# Maintainer guide

Routine work happens through GitHub Actions in the translation repository. Local commands are
available for investigation and release preparation.

## Synchronize a release branch

```console
dsw-locale sync-upstream \
  --config translation-config.yml \
  --version v4.32 \
  --output .

dsw-locale refresh-tree --root .
dsw-locale audit \
  --root . \
  --report-dir reports \
  --fail-on placeholders \
  --fail-on structure
```

Commit `upstream/` and `translations/` together. `refresh-tree` adds forms for new gaps, removes
blank forms that official Weblate has completed, and removes local translations that are now
identical to official translations.

An audit may report missing translations without failing: those entries are the work queue.
Structure and placeholder findings must be resolved before packaging.

## Prepare a translation release

1. Confirm that the translation PR targets the correct `sync/vX.Y` branch.
2. Review the audit and preview artifacts.
3. Increase that branch's `locale_version` if the effective locale has changed.
4. Run **Publish locale installer image** with the reviewed branch or commit.

The publisher creates an immutable GHCR image tag from `locale.json.version`. Existing tags are not
overwritten.

## Add runtime-only text

Only add runtime-only text after a preview or reproducible UI path confirms that it is interface
text and the exact source is absent from the matching POT. Keep the issue or preview link in the pull
request. The next synchronization will convert the form automatically if the source enters the
official catalog.

```console
dsw-locale add-runtime \
  --root . \
  --component wizard \
  --source "English text observed in DSW" \
  --translation "在 DSW 中看到的英文文字"
```
