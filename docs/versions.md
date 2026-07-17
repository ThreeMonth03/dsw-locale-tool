# DSW 版本治理

本專案不以某一套 production 現在使用的版本決定維護範圍。官方
[Weblate projects](https://localize.ds-wizard.org/projects/) 中列出的每一個 `DSW X.Y`
project，都是本 repo 應維護的 minor line，並對應一個 `sync/vX.Y` branch。

## 狀態如何對齊

| Weblate 狀態 | 本地狀態 | 維護方式 |
| --- | --- | --- |
| project 未鎖定 | `active` | 同步官方翻譯、接受補翻、preview、打包與發版 |
| project locked | `maintenance` | 仍做上述工作；locked 不等於停止支援 |
| project 已不在 Weblate | 保留原狀態 | 不自動刪除、archive 或退役，留給維護者判斷 |

內容 repo 目前明確維護 4.29–4.32，這四條線不自動 archive。實際官方清單由
排程讀取 Weblate，文件不複製一份會過期的「目前最新版本」。

## 自動維護

translation repo 的排程 workflow 呼叫 tool repo 唯一的 reusable maintenance
workflow。它使用 translation repo 自己的 `GITHUB_TOKEN`，不需要 PAT 或常駐服務。
每次執行：

1. 讀取 Weblate projects API；若 rate limit、逾時或 HTTP 失敗，改讀同一官方
   Projects 公開頁面。
2. 只有 Weblate 已列出且 `wizard-locales` 已有對應 `vX.Y` branch 時，才把
   新版本加入 config。
3. 從 `main` 建立 `sync/vX.Y`，同步官方 baseline；不猜測舊版 override 在
   新 POT 仍適用，因此不整包複製。
4. 對每個未退役 branch 更新 official baseline，再執行 audit、build 與 package。

已有 branch 若出現 placeholder、結構或 package 錯誤，workflow 不 push 新 baseline；
新 branch 則保留已鎖定的官方 baseline，但不產生可發布結果。兩者都會留下
Actions artifact 與可追蹤 Issue。

## 手動核對

維護者可在翻譯 repo checkout 中執行：

```console
dsw-locale version-report \
  --config translation-config.yml \
  --repository-root . \
  --report-dir reports/versions \
  --fail-on-drift
```

Build、preview 與 publish 只使用 branch 內已 commit 的 baseline，不在執行時偷偷更新
upstream。這使同一 commit 永遠產生相同翻譯來源；日後 Weblate 更新則以另一筆可 review
的同步 commit 納入。
