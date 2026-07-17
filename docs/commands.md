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

