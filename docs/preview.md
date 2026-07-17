# CI translation preview

The preview workflow starts disposable official DSW containers, imports the proposed locale, opens
the interface in a browser, and uploads screenshots. The runner removes the containers and data when
the job ends.

## Render one version

Open **Actions → Render DSW locale preview → Run workflow** in the tool repository and provide:

| Input | Example |
| --- | --- |
| Translation repository | `ThreeMonth03/dsw-ui-locales-zh_Hant` |
| Translation ref | `sync/v4.32` or a reviewed commit SHA |
| Config version | `v4.32` |
| DSW image tag | `4.32` |
| Knowledge Model URL | Optional raw KM JSON URL |

Use a commit SHA when reviewing a pull request so the result cannot change with the branch.

## Preview artifacts

The workflow uploads:

- Browser screenshots for the visited DSW routes.
- `runtime.md` and `runtime.json` with visible English UI findings.
- `audit.md` and `audit.json` with catalog coverage and validation findings.
- The exact locale ZIP used by the preview.
- Container logs when startup or capture fails.

Runtime findings distinguish official missing strings, translated strings that still render in
English, and strings absent from the official POT. Knowledge Model and user content supplied to the
preview are excluded from UI findings by their values, not by hiding the questionnaire page.

The maintained-release workflow runs the same checks for every `active` and `maintenance` version
defined in `translation-config.yml`.
