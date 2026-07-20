# Repository design

The workflow uses two repositories with one responsibility each.

| Repository | Contents | Primary users |
| --- | --- | --- |
| `dsw-ui-locales-zh_Hant` | Markdown translation forms, glossary, and official baseline | Translators |
| `dsw-locale-tool` | Validation, packaging, preview, and deployment automation | Maintainers and CI |

## Translation branch contents

Every `sync/vX.Y` branch contains:

| Path | Purpose | Human-edited |
| --- | --- | --- |
| `upstream/` | Exact POT, PO, and metadata from official `wizard-locales` | No |
| `translations/` | One Markdown form for every official gap and local runtime-only string | Translation block only |
| `translation-config.yml` | Locale and DSW release metadata | Maintainers only |
| `glossary/` | Preferred Traditional Chinese terminology | Yes |

PO files are build artifacts, not translation sources. The builder starts from the official PO and
applies completed Markdown forms in memory. Empty forms remain visible as work without changing the
package.

When official Weblate supplies the same translation, synchronization removes the local form. When
an already translated source changes or disappears, synchronization stops for review instead of
copying the translation to a different source.

## Runtime-only UI text

Browser preview can find English UI text that is absent from the official POT. A confirmed string
uses the same Markdown form with a `runtime-only` identity. Synchronization converts it to a normal
form when the source later appears upstream.

Some text is absent because the frontend renders a literal string instead of calling gettext. The
tool repository holds strict, version-bounded source transforms for those cases. A transform changes
only the localization call; Traditional Chinese remains in the translation form. CI refuses a
transform when the exact upstream source has changed.

## Installation model

DSW serves locale content from the server. The locale installer imports a locale ZIP through the DSW
API. The official server image remains unchanged. Deployments use the official client unless the
matching release needs a source transform; in that case only the client image is replaced.

```text
browser -> official or localizable client -> wizard-server -> installed locale
                                                         ^
                                                         |
                                                 one-shot installer
```
