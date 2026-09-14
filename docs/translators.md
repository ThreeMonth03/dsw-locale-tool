# Translator guide

Translations are contributed in
[dsw-ui-locales-zh_Hant](https://github.com/ThreeMonth03/dsw-ui-locales-zh_Hant). You do not need
Python, Docker, gettext, or access to this tool repository.

## Translate an existing form

1. Open the branch matching the DSW version, such as `sync/v4.32`.
2. Open `translations/README.md` and choose an empty translation form.
3. Select the pencil icon to edit the file in GitHub.
4. Enter Traditional Chinese only inside its empty `Translation (zh_Hant)` block.
5. Propose the change as a pull request to the same version branch.

Keep placeholders such as `%s`, `${name}`, or `{count}` unchanged. Do not edit the English source,
the hidden metadata, headings, or fence markers. CI reports a precise error if the form structure or
a placeholder is incorrect.

Only fields blank in the PR base may be changed. Reviewers may revise those new
translations within the same PR, but must not rewrite existing translations.
Nonempty official PO translations are also protected, including fuzzy entries
whose Markdown forms appear empty. Do not clear review flags. Report a suspected
problem in existing text separately for a maintainer's decision.

CI enforces this rule for translation PRs and cross-version propagation. Official
Weblate synchronization continues independently; it is not a contributor edit.

## Report text that has no form

Use the translation repository's
[issue forms](https://github.com/ThreeMonth03/dsw-ui-locales-zh_Hant/issues/new/choose) and include:

1. The DSW version.
2. The page or navigation path.
3. The complete English text, including punctuation and placeholders.
4. A screenshot and reproduction steps.
5. A suggested translation, if available.

Questionnaire content belongs to the Knowledge Model locale, and exported document text belongs to
the Document Template. This repository handles DSW interface controls, navigation, and system
messages.

## Review the result

After validation succeeds, CI renders every non-draft translation pull request in a disposable DSW
installation. A bot comment links to the run. Open its preview artifact to inspect screenshots and
the runtime English-text report. The screenshots include project settings, sharing, comments, and
the project deletion confirmation. They also cover Documents, project files, file upload and delete
dialogs, organization and authentication settings, and both OpenID configuration forms. The preview
does not connect to production data.

When the pull request is merged, completed translations are copied into matching blank forms on the
other maintained release branches. This happens only when the complete source identity is unchanged;
existing translations are never replaced.
CI also advances the immutable locale package version; translators do not edit release metadata.
