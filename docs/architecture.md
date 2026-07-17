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

## Installation model

DSW serves locale content from the server. The production artifact is therefore a locale ZIP, and
the installer image imports that ZIP through the DSW API. Official `wizard-client` and
`wizard-server` images remain unchanged.

```text
browser -> wizard-client -> wizard-server -> installed locale
                                      ^
                                      |
                              one-shot installer
```
