# 翻譯者：不用寫程式也能貢獻

翻譯者的入口是
[dsw-ui-locales-zh_Hant Issues](https://github.com/ThreeMonth03/dsw-ui-locales-zh_Hant/issues/new/choose)，
不是本工具 repo。你不需要 fork repo、編輯 PO、執行指令或閱讀 CI 設定。

## 回報漏翻

選擇「回報英文漏翻」，填入：

1. DSW 版本；不確定可選「不確定」。
2. 畫面位置或網址，例如「Projects → Questionnaire → Settings」。
3. 完整英文原文，保留大小寫、標點、換行及 `%s`、`{{name}}` 等 placeholder。
4. 截圖與重現步驟；需要特定角色或資料時請一併說明。
5. 建議繁體中文譯文；不確定可以留空討論。

如果畫面已是中文但用詞不正確，改用「修正現有翻譯」表單。

## 什麼屬於這個 repo

請先判斷英文來自哪一層：

| 畫面文字來源 | 應該去哪裡修 |
| --- | --- |
| 按鈕、導覽、錯誤訊息、管理介面 | UI locale（本流程） |
| 問卷題目、提示、選項 | Knowledge Model 翻譯 repo |
| 匯出文件的標題與固定文字 | Document Template 翻譯 repo |
| 使用者自己輸入的專案名稱或回答 | 不翻譯 |

不確定也可以照常提報；維護者會分類，不會要求回報者先理解 DSW 原始碼。

## 如何確認成果

維護者更新譯文後，會執行 Preview workflow。完成約需數分鐘，Issue 或 PR 會附上該次
workflow run；在 run 的 **Artifacts** 下載 `dsw-locale-preview-vX.Y`，直接查看：

- `login.png`：登入頁。
- `dashboard.png`：登入後首頁。
- `projects.png`：專案列表。
- `questionnaire.png`：實際問卷頁；只有控制項屬於 UI locale，題目內容取決於測試 KM。
- `locales.png`：管理員看到的 locale 狀態。

確認時請回覆「可接受」或指出仍有問題的畫面與文字。CI 是一次性渲染，不是公開服務，
不會接觸 production database。
