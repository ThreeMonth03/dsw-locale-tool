# 架構

## 兩個 repo

`dsw-ui-locales-zh_Hant` 面向翻譯者，保存設定、詞彙表與少量本地差異；
`dsw-locale-tool` 面向維護者與 CI，負責可重現的建置。

一個版本 branch 的內容分為三層：

| 層 | 來源 | 人工修改 |
| --- | --- | --- |
| `upstream/` | 官方 `ds-wizard/wizard-locales` | 禁止 |
| `overrides/` | 官方 POT 已有，但需本地補譯或覆蓋 | 可以 |
| `extras/` | UI 可重現，但官方 POT 沒有 | 可以 |

合併順序為 `upstream < overrides < extras`。打包時另外從
`translation-config.yml` 產生 `locale.json`，因此不會沿用上游 branch 內過期的版本欄位。

## 為什麼保留 extras

Weblate 只能翻譯已進入 POT 的 msgid。若 UI 執行時使用了 POT 沒收錄的英文，單純比較
Weblate 完成率無法發現它；這些字串先由 Issue／runtime preview 證明，再以 `extras`
提供翻譯。每次同步後 audit 都會確認它是否已被上游收錄，避免 workaround 永久累積。

