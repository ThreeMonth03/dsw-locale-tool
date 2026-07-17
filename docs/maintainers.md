# 維護者流程

維護者負責把自然語言 Issue 轉成內容變更；翻譯者不必接觸 tool repo。

對 `sync/vX.Y` 提出的 PR 由 translation repo 的 `pull_request_target` workflow 呼叫本 repo
唯一的 reusable validator。Workflow 只使用 read permission，從 default branch 載入可信
設定，並分開 checkout base 與 contributor head；不執行 contributor 提交的程式或
GitHub Actions。驗證包含變更範圍、config、audit、build 與 package。

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

同步產生的 `upstream/` 與 `upstream.lock.yml` 必須一起 review、commit。Preview、package
及 publish 不會自行重新同步，避免同一個翻譯 commit 在不同時間使用不同 baseline。

優先檢查：

- `extras_now_upstream`：字串已進官方 POT，應移出 `extras`。
- `redundant_overrides`：官方已有相同譯文，應刪除本地 override。
- `misplaced_overrides`：來源字串消失或層級放錯。
- placeholder mismatch：必須修正，否則 CI 阻擋 package。

## 版本規則

- 維護版本以 Weblate projects 清單為準，不取決於目前 production 使用哪一版。
- Weblate unlocked 對應 `active`；locked 對應 `maintenance`，兩者都維持可同步與可發版。
- 一個 DSW minor line 對應一個 `sync/vX.Y` branch。
- `upstream_ref` 鎖定相同 minor line；`upstream.lock.yml` 記錄實際 commit SHA。
- 每個對外發布的 locale package 必須有新的 `locale_version`；相同 coordinate 的 installer
  會視為已安裝而略過重新匯入。
- `recommended_app_version` 表示目標 DSW 版本，不拿 locale patch number 代替 DSW 版本。

例如 v4.32 第一次本地發版可為 `4.32.0`；同一 DSW line 更新翻譯時升為 `4.32.1`，並以
相同版本標記 installer image。切換至 DSW 4.33 時新增 `sync/v4.33`，不把 4.33 的 POT
混進 4.32 branch。

## 發布

Preview 通過後，到 **Actions → Publish locale installer image**，選擇已確認的版本 branch
或 commit SHA 與 `config_version`。Workflow 會從 build 後的 `locale.json.version` 自動產生
image tag，驗證 committed baseline、audit、打包，再同時發佈 GHCR image 與 ZIP/audit
artifacts。若 GHCR 已有同名 tag，workflow 會拒絕覆寫；更新翻譯前必須先增加該 branch
的 `locale_version`。production 不應使用浮動的 `latest` tag。

## GitHub Pages 首次啟用

文件 workflow 會在 `main` 更新時建置並部署本指南。Repository 管理者第一次需到
**Settings → Pages → Build and deployment → Source** 選擇 **GitHub Actions**；之後文件
更新不需手動發布。repo 搬到 depositar 時，記得同步修改 `docs/conf.py` 的 source URL
與 README 中的 Pages 網址。
