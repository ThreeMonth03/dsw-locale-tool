# Repository design

The workflow uses two repositories with one responsibility each.

| Repository | Contents | Primary users |
| --- | --- | --- |
| `dsw-ui-locales-zh_Hant` | Markdown translation forms, glossary, and official baseline | Translators |
| `dsw-locale-tool` | Validation, packaging, preview, and deployment automation | Maintainers and CI |

The tool repository also owns the public review gateway and route policy. Translation contributors
still edit only Markdown forms in the translation repository.

## Translation branch contents

Every `sync/vX.Y` branch contains:

| Path | Purpose | Human-edited |
| --- | --- | --- |
| `upstream/` | Exact POT, PO, and metadata from official `wizard-locales` | No |
| `translations/` | One Markdown form for every official translation gap | Translation block only |
| `translation-config.yml` | Locale and DSW release metadata | Maintainers only |
| `glossary/` | Preferred Traditional Chinese terminology | Yes |

PO files are build artifacts, not translation sources. The builder starts from the official PO and
applies completed Markdown forms in memory. Empty forms remain visible as work without changing the
package.

When official Weblate supplies the same translation, synchronization removes the local form. When
an already translated source changes or disappears, synchronization stops for review instead of
copying the translation to a different source.

## Installation model

DSW serves locale content from the server. The locale installer imports a locale ZIP through the DSW
API. The official server and client images remain unchanged.

```text
browser -> official client -> official wizard-server -> installed locale
                                                   ^
                                                   |
                                           one-shot installer
```

The review deployment is separate from production:

```text
reviewer -> read-only gateway -> isolated client and server -> disposable sample data
```

Its allowed page list comes from the same manifest used by screenshot capture. The gateway blocks
mutations independently of browser controls.
