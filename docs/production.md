# Production 部署

Production 繼續使用官方 `wizard-server` 與 `wizard-client` images。補翻內容由一次性
`locale-installer` 經 DSW API 匯入，不 fork frontend，也不掛載 PO 檔。

## 初次加入

將 [`production/compose.locale.yml`](https://github.com/ThreeMonth03/dsw-locale-tool/blob/main/production/compose.locale.yml)
複製到 `dsw-deployment` 根目錄。這份 fragment 已對齊 `depositar-prod` 的 `server` service
與內部 `3000` port。建立專用 DSW 部署帳號及 API key，將 key 寫入不進 Git 的檔案：

```text
secrets/dsw_locale_api_key
```

API key 會繼承帳號權限，因此部署帳號只授予 locale 管理所需角色。Production installer
只使用 API key；不設定 demo 帳號或密碼認證。

先檢查合併後的 Compose，再執行 installer：

```console
docker compose -f docker-compose.yml -f compose.locale.yml config --quiet
docker compose -f docker-compose.yml -f compose.locale.yml pull locale-installer
docker compose -f docker-compose.yml -f compose.locale.yml up locale-installer
```

Installer 會自行等待 server ready，匯入 image 內的 locale ZIP、啟用該版本並設為預設；
成功後 exit code 為 0。它以非 root 使用者執行，root filesystem 為唯讀，沒有 Linux
capabilities，且只能讀取 Compose secret。Fragment 與現有 `depositar-prod` server 一樣
明確使用 `linux/amd64`。

## 更新補翻

目前可直接使用的 immutable tags：

| DSW line | Installer image |
| --- | --- |
| 4.29 | `ghcr.io/threemonth03/dsw-locale-installer:4.29.0` |
| 4.30 | `ghcr.io/threemonth03/dsw-locale-installer:4.30.1` |
| 4.31 | `ghcr.io/threemonth03/dsw-locale-installer:4.31.1` |
| 4.32 | `ghcr.io/threemonth03/dsw-locale-installer:4.32.1` |

後續翻譯 release 只需要修改 `compose.locale.yml` 的 `image:` 一行，例如由 `4.32.1`
改成 `4.32.2`，再重跑上面的 pull 與 up。Tag 不覆寫；同一 locale coordinate 重跑時，
installer 會直接啟用既有版本，不重複匯入。

Tool repo 每日從 `translation-config.yml` 動態列出所有 `active` 與 `maintenance` branches，
並發布尚不存在的 tags。新 Weblate release line 經 maintenance 建 branch 後會自動加入；
翻譯尚未準備發版時可先累積，準備發布時提高該 branch 的 `locale_version`。

## 驗證與回復

- Installer 輸出應包含 `enabled: true` 與 `defaultLocale: true`。
- 用無痕視窗重開 DSW，避免舊 session 的 locale cache。
- 回復時把 `image:` 改回上一個 immutable tag，再執行 installer；流程不刪除其他 locale。
- GHCR package 目前可匿名 pull；未來移到 depositar 後，只需更換同一行的 image owner。
