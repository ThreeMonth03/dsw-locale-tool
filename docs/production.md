# Production 部署

Production 不需要 fork DSW frontend，也不需架設本地 Weblate。維持官方
`wizard-server`／`wizard-client` images，再加入一個執行完即退出的 locale installer
service。之後每次發版只更新 installer 的 immutable image tag。

## 一次性的 Compose 變更

以下 service 可加入既有 Compose；service 名稱與 server 內部連接埠請依實際檔案調整：

```yaml
services:
  locale-installer:
    image: ghcr.io/threemonth03/dsw-locale-installer:4.32.0
    restart: "no"
    depends_on:
      wizard-server:
        condition: service_started
    environment:
      DSW_API_URL: http://wizard-server:3000/wizard-api
      DSW_API_KEY_FILE: /run/secrets/dsw_locale_api_key
    secrets:
      - dsw_locale_api_key

secrets:
  dsw_locale_api_key:
    file: ./secrets/dsw_locale_api_key
```

建議為 installer 建立專用部署帳號，再由該帳號建立有到期日的 DSW API key。DSW 4.32
的 API key 會繼承所屬使用者權限，key 本身沒有細部 scope，因此帳號只給目前版本能完成
locale 管理所需的最低角色。不要使用 preview 的 demo 帳號；若環境暫時無法建立 API
key，才以 `DSW_ADMIN_EMAIL` 與 `DSW_ADMIN_PASSWORD` 作為過渡方案。

## 更新語系

1. 發布新 `locale_version` 與同號 installer image，例如 `4.32.1`。
2. 修改 Compose 中 `locale-installer.image` 的 tag。
3. 拉取並執行一次：

   ```console
   docker compose pull locale-installer
   docker compose up locale-installer
   ```

Installer 會等待 server、尋找同一 `organizationId:localeId:version`、必要時匯入 ZIP，最後
啟用並設為預設語系。重跑同一版本不會重複 POST package；若翻譯內容有變，必須升
`locale_version`，不能只重建相同 tag。

## 驗證與回復

- 確認 installer exit code 為 0，輸出含 `enabled: true` 與 `defaultLocale: true`。
- 用無痕視窗重新開啟 DSW，避免舊 session／locale cache 影響判斷。
- 保留上一版 immutable image tag。需要回復時，將上一版 locale 重新設為 default；
  installer 不會刪除其他 locale。
- GHCR repo 搬到 depositar 後只需改 image owner；翻譯內容與 tool history 可照常移轉。

若 production 的 GHCR package 是 private，需先讓 Docker 對 `ghcr.io` 登入，或將該
package 設為 public。API key 應放在不進 Git 的 secret file，並定期輪替。
