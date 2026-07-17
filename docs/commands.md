# 指令

## validate-config

檢查 schema、未知欄位、version branch 名稱與 semantic version：

```console
dsw-locale validate-config translation-config.yml
```

## sync-upstream

將指定 DSW release line 的 POT、PO、metadata 與 README 複製到 `upstream/`：

```console
dsw-locale sync-upstream \
  --config translation-config.yml \
  --version v4.32 \
  --output .
```

## version-report

把 Weblate 官方版本清單與本地設定、版本 branches 比較：

```console
dsw-locale version-report \
  --config translation-config.yml \
  --repository-root . \
  --report-dir reports/versions \
  --fail-on-drift
```

Weblate locked project 應設定為 `maintenance`，未鎖定 project 應為 `active`。此指令先讀
projects API；若 API 遇到 rate limit、逾時或其他 HTTP 錯誤，則從官方 Projects 公開
頁面讀取相同版本與 lock 狀態，並輸出 JSON 與 Markdown 報告。

## audit

同時輸出 `audit.json` 與便於 PR 閱讀的 `audit.md`：

```console
dsw-locale audit \
  --root . \
  --report-dir reports \
  --fail-on placeholders \
  --fail-on structure
```

`missing` 不預設造成失敗，因為報告漏翻正是此工具的工作；placeholder 與錯誤分層則應
阻止 release。

## build-source 與 package

```console
dsw-locale build-source \
  --config translation-config.yml \
  --version v4.32 \
  --root . \
  --output build/locale

dsw-locale package \
  --source build/locale \
  --output dist/dsw_zh_Hant_4.32.0.zip
```

`package` 固定使用 `@ds-wizard/locale-packager@0.3.0`，避免開發機與 CI 產物不同。

## preview-config、install-dsw 與 preview

產生只供一次性 Compose 使用的 DSW 設定：

```console
dsw-locale preview-config \
  --output preview/runtime/application.yml \
  --client-url http://localhost:8080/wizard
```

將 package 匯入 DSW。Production 建議使用 API key file：

```console
dsw-locale install-dsw \
  --bundle dist/locale.zip \
  --api-url http://wizard-server:3000/wizard-api \
  --api-key-file /run/secrets/dsw_locale_api_key \
  --default-locale
```

未提供 API key 時，CLI 會改用 `--email`／`--password` 或相對應環境變數登入。CI preview
另使用 `seed-project` 匯入測試 KM，並以 `capture-preview` 擷取畫面；一般翻譯者不需直接
執行這些指令。
