# 維護者流程

維護者負責把自然語言 Issue 轉成內容變更；翻譯者不必接觸 tool repo。

## 處理一筆回報

1. 確認目標 DSW minor version，切到內容 repo 的 `sync/vX.Y`。
2. 在官方 POT 搜尋完整 msgid。
3. POT 已有但官方 PO 漏譯或需本地用語：放入 `overrides/`。
4. POT 沒有、但真實 UI 可重現：放入 `extras/`，並在 commit／PR 連回 Issue。
5. 執行 audit；placeholder 或結構錯誤不得發版。
6. 觸發 CI preview，請回報者確認 artifact 畫面。

`upstream/` 永遠由 `sync-upstream` 產生，不接受人工修改。詞彙選擇先更新
`glossary/terms.yml`，再調整翻譯，避免不同版本各自發明用語。

## 同步 Weblate／官方 locale

```console
dsw-locale sync-upstream \
  --config translation-config.yml \
  --version v4.32 \
  --output .

dsw-locale audit --root . --report-dir reports
```

優先檢查：

- `extras_now_upstream`：字串已進官方 POT，應移出 `extras`。
- `redundant_overrides`：官方已有相同譯文，應刪除本地 override。
- `misplaced_overrides`：來源字串消失或層級放錯。
- placeholder mismatch：必須修正，否則 CI 阻擋 package。

## 版本規則

- 一個 DSW minor line 對應一個 `sync/vX.Y` branch。
- `upstream_ref` 鎖定相同 minor line；`upstream.lock.yml` 記錄實際 commit SHA。
- 每個對外發布的 locale package 必須有新的 `locale_version`；相同 coordinate 的 installer
  會視為已安裝而略過重新匯入。
- `recommended_app_version` 表示目標 DSW 版本，不拿 locale patch number 代替 DSW 版本。

例如 v4.32 第一次本地發版可為 `4.32.0`；同一 DSW line 更新翻譯時升為 `4.32.1`，並以
相同版本標記 installer image。切換至 DSW 4.33 時新增 `sync/v4.33`，不把 4.33 的 POT
混進 4.32 branch。

## 發布

Preview 通過後，到 **Actions → Publish locale installer image**，使用已確認的 commit SHA
與 immutable `image_tag`。Workflow 會重新同步、audit、打包，並同時發佈 GHCR image 與
ZIP/audit artifacts。production 不應使用浮動的 `latest` tag。

## GitHub Pages 首次啟用

文件 workflow 會在 `main` 更新時建置並部署本指南。Repository 管理者第一次需到
**Settings → Pages → Build and deployment → Source** 選擇 **GitHub Actions**；之後文件
更新不需手動發布。repo 搬到 depositar 時，記得同步修改 `docs/conf.py` 的 source URL
與 README 中的 Pages 網址。
