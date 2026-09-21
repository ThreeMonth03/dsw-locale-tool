# Repository responsibilities

| Repository | Responsibility |
| --- | --- |
| dsw-ui-locales-zh_Hant | Markdown translation forms, terminology, official catalog snapshots |
| dsw-locale-tool | Discovery, synchronization, validation, Weblate submission |

Official Weblate and its linked wizard-locales repository own the source strings.
The tool never extracts strings from frontend code or introduces messages absent from the official POT.

## Data flow

Official catalogs → Markdown contribution → PR checks → controlled Weblate submission → official review.

Every version branch contains `upstream/wizard.po`, `upstream/mail.po`, the corresponding
POT files, and a source commit lock. These snapshots retain official fuzzy flags.
`translations/` contains drafts for empty entries and explicit corrections.

A filled draft is not an approved translation. Submitted drafts are marked fuzzy.
When an official translation matches a draft, synchronization removes the redundant form
without changing Weblate's review state. A different official translation never silently
overwrites a filled local draft.

## Boundaries

There are no DSW images, locale installers, custom locale releases, browser previews,
or production credentials. GitHub Pages hosts instructions only.

Translation PR checks run trusted, commit-pinned tool code with read-only permissions.
Contributor files are parsed as data. Weblate writes are available only through a manually
dispatched workflow on the control branch.
