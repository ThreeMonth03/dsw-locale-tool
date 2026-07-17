# 維護流程

## 日常補翻

1. 翻譯者透過內容 repo 的 Issue 表單回報 UI 英文。
2. 維護者在對應 `sync/vX.Y` 判斷 msgid 是否存在於 POT。
3. 存在則加入 `overrides`；不存在但可重現則加入 `extras`。
4. CI 執行 audit、合併與官方 packager。
5. preview CI 匯入 package 到暫時 DSW，回傳畫面供翻譯者確認。

Preview 屬於後續瀏覽器層；locale package 的產生不依賴 production database，也不需
把 preview 程式放進翻譯 repo。

## 同步官方翻譯

`sync-upstream` 以設定中的 release branch 做 shallow clone，只更新 `upstream/`，並寫入
含 commit SHA 的 `upstream.lock.yml`。同步後應先看 audit：

- `extras_now_upstream` 表示 workaround 已進入 POT。
- `redundant_overrides` 表示 Weblate 已有相同譯文。
- `misplaced_overrides` 表示分類錯誤或來源字串已移除。
- placeholder mismatch 必須在打包前修正。

## Production

Production 應使用 CI 產生的 ZIP artifact。第一階段先以 DSW locale import/update API
匯入，這比 fork 整個 frontend image 更小且容易跟 minor version 對應；若確認某些字串
無法透過 locale package 覆蓋，再把 frontend image overlay 當成獨立 fallback。

