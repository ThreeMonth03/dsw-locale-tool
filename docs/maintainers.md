# Maintainer guide

Routine work happens through GitHub Actions in the translation repository. Local commands are
available for investigation and release preparation.

## Synchronize a release branch

```console
VERSION_KEY=vX.Y
dsw-locale sync-upstream \
  --config translation-config.yml \
  --version "$VERSION_KEY" \
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

## Cross-version propagation

Merging a translation pull request starts exact propagation for every other maintained release
branch. CI fills a target only when the form already exists, is blank, and has the same component,
source, plural source, and context. Nonempty official PO translations, including
fuzzy entries, are never propagation targets. Each changed target is audited, built, and packaged
before CI commits it. The source and every changed target receive a new immutable locale patch
version automatically. A concurrent branch update causes the push to fail instead of being
overwritten.

This protection applies to automatic propagation, not human review. Existing
translations may be corrected in focused PRs addressing reported issues. Open a
correction PR for each affected version whose existing wording needs to change.

To inspect the same operation locally:

```console
dsw-locale propagate \
  --source-root ../source-release \
  --target-root ../target-release \
  --report-dir reports/propagation
```

## Prepare a translation release

1. Confirm that the translation PR targets the correct `sync/vX.Y` branch.
2. Review the audit and preview artifacts.
3. Merge the translation pull request; CI advances every affected `locale_version`.
4. Run **Publish maintained locale installers** for immediate publication, or wait for its scheduled
   run.

The publisher creates an immutable GHCR image tag from `locale.json.version`. Existing tags are not
overwritten. Before a new tag is pushed, the workflow starts the configured DSW release and runs the
installer three times: a fresh install, an idempotent repeat, and another repeat after the DSW server
restarts. The image is published only when all three checks succeed.

## Review English found outside the catalog

The browser scan reports visible English that does not match the official POT. Confirm that the
finding is interface text rather than Knowledge Model, document template, user, or system content.
Report confirmed extraction gaps upstream; local translation forms remain limited to official
gettext messages.
