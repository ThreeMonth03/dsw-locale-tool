# DSW Locale Tool

這套工具把 DSW 官方 Weblate 翻譯與 depositar 的 UI 補翻分層管理，目標是讓翻譯者
只需回報與確認畫面，維護者能重複產生可匯入 DSW 的 locale package。

```{toctree}
:maxdepth: 2

architecture
workflow
commands
```

## 設計界線

- 官方 `wizard-locales` 是 baseline，不直接修改。
- 翻譯 repo 是內容 repo，不包含 Python、Docker 或瀏覽器測試程式碼。
- tool repo 擁有所有同步、檢查、打包與 preview automation。
- 每個 DSW minor version 使用獨立 branch，避免來源字串跨版污染。

