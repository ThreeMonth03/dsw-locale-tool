# For translators

Choose the matching `sync/vX.Y` branch in the translation repository.
Open `translations/README.md` and fill only an empty translation block.
The generated index does not need to be edited; synchronization updates it.

Use existing Traditional Chinese translations as the terminology baseline.
Consult the glossary when existing usage does not settle the wording.
Keep placeholders, Markdown links, and source context intact.

Existing translations are maintained, not frozen. Propose a focused correction when someone
reports a problem; leave unrelated wording unchanged.

CI checks source identity and placeholders. It does not host a DSW preview or change Weblate.
A maintainer submits reviewed drafts as fuzzy translations for review on official Weblate.
For text missing from the official POT, report the extraction gap upstream.
