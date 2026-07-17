# CI 翻譯預覽

Preview workflow 會在 GitHub-hosted runner 建立一次性的 PostgreSQL、MinIO、官方
`wizard-server` 與 `wizard-client`，匯入本次 locale package，再用瀏覽器擷取畫面。完成後
整組 containers 與 volumes 都會刪除。

## 執行方式

到 tool repo 的 **Actions → Render DSW locale preview → Run workflow**，填入：

| 欄位 | 範例 | 意義 |
| --- | --- | --- |
| `translation_repository` | `ThreeMonth03/dsw-ui-locales-zh_Hant` | 內容 repo |
| `translation_ref` | `sync/v4.32` 或 commit SHA | 要驗證的翻譯版本 |
| `config_version` | `v4.32` | `translation-config.yml` 的版本 key |
| `dsw_image_tag` | `4.32` | 官方 server/client image tag |
| `knowledge_model_url` | KM JSON 的 raw URL | 建立真實 questionnaire；留空則略過 |

建議 review PR 時使用 commit SHA，結果才不會因 branch 後續更新而改變。`config_version`、
DSW image tag 與 branch 的 minor line 應一致。

## 產物與判讀

無論畫面擷取成功或失敗，workflow 都會盡量上傳：

- `preview-artifact/*.png`：真實瀏覽器畫面。
- `preview-artifact/docker-compose.log`：失敗診斷資訊。
- `reports/audit.md` 與 `audit.json`：漏翻與分層報告。
- `dist/locale.zip`：同一次測試使用的可匯入 package。

預設測試 KM 的題目可能是英文，這不代表 UI locale 失效。判斷 questionnaire 時要看
按鈕、狀態、選單及系統訊息；若要同時展示中文問卷內容，把 `knowledge_model_url` 換成
已翻譯 KM 的固定 commit raw URL。

## 本機重現（維護者）

一般翻譯者不需要執行本段。維護者若要診斷 CI，可參考 `preview/README.md` 生成暫時設定，
再依序執行 `install-dsw`、`seed-project` 與 `capture-preview`。此 stack 使用公開 demo 密碼，
不得暴露至共享網路或沿用到 production。
