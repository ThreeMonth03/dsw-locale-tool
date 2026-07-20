# DSW UI locale workflow

This project fills gaps in the official DSW UI locale and turns the result into a locale package
that can be previewed or installed through the DSW API. It does not require a private Weblate
instance or a long-lived frontend fork.

:::{admonition} Choose where to start
:class: tip

- To translate UI text, open the {doc}`translator guide <translators>`.
- To review a translation in a real DSW interface, open the {doc}`preview guide <preview>`.
- To operate a browsable review-only DSW, open the {doc}`sandbox guide <review-sandbox>`.
- To operate synchronization or releases, open the {doc}`maintainer guide <maintainers>`.
- To install a released locale, open the {doc}`production guide <production>`.
:::

```{toctree}
:maxdepth: 2
:hidden:

architecture
translators
preview
review-sandbox
versions
maintainers
production
commands
```

## How a translation reaches DSW

1. Official Weblate catalogs are synchronized into a version branch.
2. Missing or fuzzy source strings become blank Markdown translation forms.
3. A contributor fills the Traditional Chinese block in one or more forms.
4. CI validates placeholders, builds the locale, and renders a disposable DSW preview.
5. An isolated public sandbox can expose approved translated pages for interactive review.
6. A versioned installer image imports the approved locale through the DSW API.

Preview also reports visible English that is absent from the official POT. These findings identify
upstream extraction gaps; they are not added to the local locale package.

Each DSW minor release has its own `sync/vX.Y` branch, so source strings never move between
versions by guesswork.
