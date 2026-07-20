# CI translation preview

The preview workflow starts disposable official DSW containers, imports the proposed locale, opens
the interface in a browser, and uploads screenshots. The runner removes the containers and data when
the job ends.

This workflow does not publish a live website. Use the {doc}`public review sandbox
<review-sandbox>` when translators need a browsable DSW after CI has finished.

## Render one version

Open **Actions → Render DSW locale preview → Run workflow** in the tool repository and provide:

| Input | Example |
| --- | --- |
| Translation repository | `ThreeMonth03/dsw-ui-locales-zh_Hant` |
| Translation ref | `sync/v4.32` or a reviewed commit SHA |
| Translation control repository | `ThreeMonth03/dsw-ui-locales-zh_Hant` |
| Translation control ref | `main` |
| Config version | `v4.32` |
| DSW image tag | `4.32` |

Use a commit SHA when reviewing a pull request so the result cannot change with the branch.
The workflow reads preview assets from `translation-config.yml` in the control repository and ref,
downloads the translated Knowledge Model and document template declared for the selected release,
verifies both SHA-256 hashes, and installs them into the preview project. This separation keeps a
contributor's translation commit reviewable without trusting operational configuration from their
fork. Version branches do not duplicate shared asset coordinates.

## Preview artifacts

The workflow uploads:

- Browser screenshots for the visited DSW routes.
- `runtime.md` and `runtime.json` with visible English UI findings.
- `audit.md` and `audit.json` with catalog coverage and validation findings.
- The exact locale ZIP used by the preview.
- Container logs when startup or capture fails.

Runtime findings distinguish official missing strings, translated strings that still render in
English, and strings absent from the official POT. Knowledge Model and document-template content
are excluded from UI findings by their values, not by hiding the questionnaire or documents pages.

The maintained-release workflow runs the same checks for every `active` and `maintenance` version
defined in `translation-config.yml`.

Translation pull requests start this preview automatically after scope, structure, placeholder, and
package validation succeeds. Draft pull requests do not consume preview resources. The translation
repository updates one stable pull-request comment with the run and artifact link.
