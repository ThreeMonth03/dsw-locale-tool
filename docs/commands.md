# Command reference

```console
VERSION=vX.Y
dsw-locale reconcile-versions --config translation-config.yml --report-dir reports
dsw-locale sync-upstream --config translation-config.yml --version "$VERSION" --root .
dsw-locale refresh-tree --root .
dsw-locale check --root . --report-dir reports
```

## Prepare an upload without writing to Weblate

```console
dsw-locale submit --config translation-config.yml --version "$VERSION" \
  --root . --report-dir reports/submission --limit 20
```

The report includes skipped conflicts and candidates. Generated `wizard.po` and `mail.po`
contain only the proposed batch, marked fuzzy. The `before-*.po` files are verification backups,
not files to upload.

## Apply

Set `LOCALIZE_API_TOKEN` through your secret manager, inspect a dry run, then repeat the command
with `--apply --expected-plan HASH`, using the hash from the reviewed report. Use `--allow-corrections` only for explicitly reviewed changes to nonempty targets.
Prefer the GitHub workflow when multiple maintainers are working together.

## Validate a pull request

```console
dsw-locale validate-pr --base-root ../base --head-root ../head \
  --branch "$BRANCH" --report-dir reports
```

Only translation forms, the glossary, and contributor Markdown are allowed in a translation PR.
Shared configuration and automation belong in control-branch PRs.
