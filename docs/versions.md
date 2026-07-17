# DSW version policy

Each DSW minor release listed by the official
[Weblate projects](https://localize.ds-wizard.org/projects/) has a matching `sync/vX.Y` branch.

| Official state | Local state | Automation |
| --- | --- | --- |
| Weblate project is open | `active` | Synchronize, preview, build, and publish |
| Weblate project is locked | `maintenance` | Synchronize, preview, build, and publish |
| Release is intentionally retired | `retired` | Excluded from maintained matrices |

A locked Weblate project remains maintainable locally. Release branches are not archived merely
because a newer DSW version exists.

The scheduled maintenance workflow discovers new Weblate versions, waits until the matching
`wizard-locales` branch exists, adds the release metadata, creates its version branch, synchronizes
the official baseline, and generates blank translation forms. Existing translations are never
copied to a new release by similarity. Merge automation propagates only into existing blank forms
with the same complete source identity.

`locale_version` identifies an immutable locale package. Merge automation advances its patch version
whenever effective translation content changes. `recommended_app_version` identifies the target DSW
release and is independent from the locale patch version.
