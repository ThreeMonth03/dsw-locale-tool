# CI 翻譯預覽

Preview workflow 會在 GitHub-hosted runner 建立一次性的 PostgreSQL、MinIO、官方
`wizard-server` 與 `wizard-client`，匯入本次 locale package，再用瀏覽器擷取畫面。完成後
整組 containers 與 volumes 都會刪除。

## 所有維護版本

**Actions → Preview maintained DSW releases** 每週自動執行，也可以手動觸發。Workflow
從 translation repo `main` 的 `translation-config.yml` 產生 matrix；目前會平行驗證
v4.29–v4.32。`reconcile-versions` 新增 release line 後，下一次執行會自動包含該版本，
不必修改 workflow YAML。

## 單一版本或 PR

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
- `preview-artifact/runtime.md` 與 `runtime.json`：瀏覽器實際看到的英文、DOM
  selector、route 與字串分類。
- `preview-artifact/docker-compose.log`：失敗診斷資訊。
- `reports/audit.md` 與 `audit.json`：漏翻與分層報告。
- `dist/locale.zip`：同一次測試使用的可匯入 package。

Runtime report 將英文分成：

- `runtime_not_in_pot`：畫面可見，但官方 wizard POT 沒有；這是 `extras` 的候選。
- `official_missing`：POT 已有，但有效 locale 仍缺譯或 fuzzy。
- `unexpected_source`：有效 locale 已有譯文，畫面卻仍渲染英文，通常要查字串
  context 或 frontend 取用路徑。
- `allowed_content`：KM、project 名稱、使用者名稱、locale metadata 或產品專名。

Workflow 把本次 KM JSON 的所有字串當作 content，不用整頁 selector 排除
questionnaire，因此問卷區內的按鈕與系統訊息仍會被檢查。這個報告只證明本次有實際
瀏覽的 routes，不宣稱覆蓋整個 DSW UI。

## 本機重現（維護者）

一般翻譯者不需要執行本段。維護者若要診斷 CI，可參考 `preview/README.md` 生成暫時設定，
再依序執行 `install-dsw`、`seed-project` 與 `capture-preview`。`capture-preview` 必須提供
`--locale-root`；若匯入 KM，同時以 `--allowed-content-json` 提供該 JSON。此 stack 使用公開 demo 密碼，
不得暴露至共享網路或沿用到 production。
