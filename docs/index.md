# DSW UI 繁體中文補翻指南

這套流程把 DSW 官方 Weblate 翻譯與 depositar 的 UI 補翻分層管理。翻譯者不需要碰
Python、Docker 或 GitHub Actions：只要回報英文原文、畫面位置與建議譯文；維護者再由
CI 產生可檢查的真實 DSW 畫面與可部署的 locale installer。

:::{admonition} 我應該從哪裡開始？
:class: tip

- **發現英文或翻譯不自然**：閱讀 {doc}`translators`。
- **想看翻譯套進 DSW 的結果**：閱讀 {doc}`preview`。
- **想知道維護哪些 DSW 版本**：閱讀 {doc}`versions`。
- **負責同步、分類或發版**：閱讀 {doc}`maintainers`。
- **負責 production Compose**：閱讀 {doc}`production`。
:::

```{toctree}
:maxdepth: 2
:hidden:

architecture
translators
preview
versions
maintainers
production
commands
```

## 最短流程

1. 翻譯者在內容 repo 建立 Issue，不需修改任何程式碼。
2. 維護者把譯文放進對應版本的 `overrides/` 或 `extras/`。
3. Preview workflow 啟動一次性的 DSW，匯入語系並上傳畫面 artifact。
4. 確認後發佈 installer image；production 只需更新 image tag。

## Repo 分工

- [dsw-ui-locales-zh_Hant](https://github.com/ThreeMonth03/dsw-ui-locales-zh_Hant)：
  面向翻譯者的內容 repo；Issue、詞彙表與各版補翻都在這裡。
- [dsw-locale-tool](https://github.com/ThreeMonth03/dsw-locale-tool)：
  面向維護者的工具 repo；同步、audit、打包、preview 與 installer 都在這裡。
- 官方 `ds-wizard/wizard-locales`：唯讀 baseline，既有 Weblate 翻譯會持續同步。

每個 DSW minor version 使用獨立 branch，避免來源字串跨版本污染。這是 workaround，
不是 Weblate 的替代品；適合所有 DSW 使用者的修正仍應回饋官方。
