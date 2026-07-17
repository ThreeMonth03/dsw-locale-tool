# DSW 版本治理

本專案不以某一套 production 現在使用的版本決定維護範圍。官方
[Weblate projects](https://localize.ds-wizard.org/projects/) 中列出的每一個 `DSW X.Y`
project，都是本 repo 應維護的 minor line，並對應一個 `sync/vX.Y` branch。

## 狀態如何對齊

| Weblate 狀態 | 本地狀態 | 維護方式 |
| --- | --- | --- |
| project 未鎖定 | `active` | 同步官方翻譯、接受補翻、preview、打包與發版 |
| project locked | `maintenance` | 仍做上述工作；locked 不等於停止支援 |
| project 已不在 Weblate | `retired` | 凍結但保留 branch、lock 與既有 artifacts |

目前 Weblate 列出 DSW 4.29、4.30、4.31 與 4.32；4.29–4.31 為 locked，4.32
仍開放。這份文字只是方便閱讀，實際判定由 CI 每週讀取 Weblate API，因此新增 4.33
時不需等待人員記得更新文件才會被發現。

## 自動偵測版本漂移

`Check Weblate version alignment` workflow 每週與手動執行時只送出一次 Weblate projects
API request，然後比較：

1. Weblate 列出的 DSW minor lines。
2. `translation-config.yml` 的版本與 lifecycle state。
3. Git 中是否有對應的 `sync/vX.Y` branch。

若少了設定、branch，或 locked 狀態與本地 state 不一致，workflow 會失敗並留下 Markdown
及 JSON artifacts。維護者也可在翻譯 repo checkout 中執行：

```console
dsw-locale version-report \
  --config translation-config.yml \
  --repository-root . \
  --report-dir reports/versions \
  --fail-on-drift
```

## 新版本處理方式

CI 發現新的 `vX.Y` 後，維護者新增設定、建立 `sync/vX.Y`、執行一次
`sync-upstream`，再 review 並 commit `upstream/` 與 `upstream.lock.yml`。不同版本只移植
audit 證明仍有效的本地補翻，不直接複製整包 PO。

Build、preview 與 publish 只使用 branch 內已 commit 的 baseline，不在執行時偷偷更新
upstream。這使同一 commit 永遠產生相同翻譯來源；日後 Weblate 更新則以另一筆可 review
的同步 commit 納入。
