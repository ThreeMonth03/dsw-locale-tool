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
`upstream/upstream.lock.yml` 記錄同步時的完整 commit SHA；build、preview 與 publish
都驗證此 lock 並使用已 commit 的 baseline，不在建置途中重新抓取可變內容。

## 為什麼保留 extras

Weblate 只能翻譯已進入 POT 的 msgid。若 UI 執行時使用了 POT 沒收錄的英文，單純比較
Weblate 完成率無法發現它；這些字串先由 Issue／runtime preview 證明，再以 `extras`
提供翻譯。每次同步後 audit 都會確認它是否已被上游收錄，避免 workaround 永久累積。

Runtime preview 從可見 DOM text、placeholder、label 與 title 擷取英文，再和同一
version branch 的 POT 與有效 locale 比對。KM 與 user content 來自明確的 JSON／API
值，不用「略過 questionnaire 整區」來壓低誤報。

## 為什麼不是換掉 wizard-client image

DSW 瀏覽器端會向 server 取得目前 locale 的內容；locale 是匯入 server 後保存的應用資料，
不是把 PO 檔複製進靜態前端 image 就會生效。因此 production 的發布單位是 locale ZIP，
installer image 只是負責把 ZIP 經由 API 匯入、啟用並設為預設語系。

```text
wizard-client ── /locales/current/content ──> wizard-server ──> locale storage
                                              ^
                                              |
                                      one-shot installer
```

這讓官方 `wizard-client` 與 `wizard-server` 仍可使用相同 DSW tag，也不需要維護 frontend
fork。只有證明某段文字完全不經 locale API 時，才另開 frontend patch；不把例外塞進本流程。

## 信任邊界

- Preview 使用一次性 database、MinIO 與 DSW demo 帳號，只綁定 runner 的 localhost。
- Production installer 優先使用專用部署帳號的 DSW API key，不帶瀏覽器或 database 權限。
- 翻譯 repo 不執行 contributor 提交的程式碼；自動化集中在 tool repo。
- 只有 tool repo 的 reusable maintenance workflow 使用 translation repo 授予的 write
  token；translation repo 只保留排程、權限與 workflow reference。
- 同步只做普通 fast-forward push；排程期間若有人同時更新 branch，push 會失敗並
  留下報告，不 force-push 或覆寫人工變更。
