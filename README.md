# DSW Locale Tool

`dsw-locale-tool` 管理 DSW UI 語系的本地補翻層。它不取代 Weblate；它把官方
`wizard-locales` 當成 baseline，再套用本地覆蓋與上游 POT 尚未收錄的字串。

翻譯內容與程式碼刻意分開：

- 本 repo：同步、稽核、合併、打包與 CI。
- `dsw-ui-locales-zh_Hant`：翻譯設定、詞彙表、`overrides` 與 `extras`。

## 開發

```console
make install-dev
make check
```

## CLI

```console
dsw-locale validate-config ../dsw-ui-locales-zh_Hant/translation-config.yml
dsw-locale sync-upstream --config translation-config.yml --version v4.32
dsw-locale audit --root . --report-dir reports
dsw-locale build-source --config translation-config.yml --version v4.32 --root . --output build/locale
```

完整流程與 branch 規則見 [文件](docs/index.md)。

