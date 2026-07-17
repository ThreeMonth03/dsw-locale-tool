# Translator guide

Translations are contributed in
[dsw-ui-locales-zh_Hant](https://github.com/ThreeMonth03/dsw-ui-locales-zh_Hant). You do not need
Python, Docker, gettext, or access to this tool repository.

## Translate an existing form

1. Open the branch matching the DSW version, such as `sync/v4.32`.
2. Open `translations/README.md` and choose a source string.
3. Select the pencil icon to edit the file in GitHub.
4. Enter Traditional Chinese only inside the `Translation (zh_Hant)` block.
5. Propose the change as a pull request to the same version branch.

Keep placeholders such as `%s`, `${name}`, or `{count}` unchanged. Do not edit the English source,
the hidden metadata, headings, or fence markers. CI reports a precise error if the form structure or
a placeholder is incorrect.

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
the runtime English-text report. The preview does not connect to production data.

When the pull request is merged, completed translations are copied into matching blank forms on the
other maintained release branches. This happens only when the complete source identity is unchanged;
existing translations are never replaced.
CI also advances the immutable locale package version; translators do not edit release metadata.
