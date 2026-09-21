# Maintainer guide

## Synchronize

Run **Synchronize official translations** in the translation repository.
The daily workflow discovers official versions, updates catalog snapshots, refreshes Markdown
forms, and checks local contributions before committing. Existing version branches remain maintained.

The workflow also distributes shared instructions and configuration from `main`.
Keep translator edits in version branches and shared policy changes in `main`.

## Submit a translation batch

1. Run **Submit translations to Weblate** from `main`, select a version, and keep `apply` off.
2. Inspect the submission report and delta PO files. The default batch limit is 20.
3. Copy the reviewed plan hash displayed by the workflow.
4. Run again with that `expected_plan` and `apply` enabled.
5. Inspect the verification result and review the fuzzy entries on official Weblate.

The workflow refuses to apply if the exact candidate batch, wording, source identity, or prior
Weblate values differ from the reviewed dry run.
By default, every nonempty official target is protected, including fuzzy translations.
Use `allow_corrections` only for a reviewed correction batch. It does not approve translations.

Create an Actions secret named `LOCALIZE_API_TOKEN` in the translation repository.
Its Weblate account needs permission to edit the selected Traditional Chinese translation.
Never put the token in files, issue comments, or workflow inputs.
Without it, dry runs and all read-only synchronization still work.

## Verification and conflicts

Before each write the tool rechecks source identity, current wording, review state, and API
update timestamp. It writes only the target and fuzzy state of the selected unit.
It reads back the result immediately and after a settling interval, then compares downloaded
PO files for unexpected changes. Reports and preflight backups are uploaded even on failure.

Weblate does not provide an atomic compare-and-set operation here. A concurrent edit between
the last check and write remains possible; coordinate review batches with other editors.
Automatic translation may also modify a fuzzy entry later. Verification is a point-in-time check,
not a guarantee that future Weblate activity will leave it unchanged.

On conflict or verification failure, inspect the report. Successful writes are retained; the
tool never clears translations, retries a failed write automatically, or rolls back a whole file.
Re-run a dry run before deciding what to do next.

## Tool updates

The translation workflows pin both reusable workflows and tool checkouts to one commit.
Test a new tool commit first, then update the pins on the control branch and maintained version
branches. Synchronization distributes contributor documentation and configuration, not workflow
files. New version branches inherit the current control-branch workflows.
Do not use a floating tool branch for privileged jobs.
