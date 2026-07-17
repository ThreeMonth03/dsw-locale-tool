# Production 部署

Production 不需要 fork DSW frontend，也不需架設本地 Weblate。維持官方
`wizard-server`／`wizard-client` images，再加入一個執行完即退出的 locale installer
service。之後每次發版只更新 installer 的 immutable image tag。

:::{warning}
目前已發布的 `4.32.0` installer 只適用 DSW 4.32 release line。`depositar-prod` branch 的
`example.env` 仍寫 `DSW_VERSION=4.29`；執行前必須檢查真正 production `.env`。若仍是
4.29，應先升級 DSW，或另行建立相符的 `sync/v4.29` locale，不可直接匯入 4.32 package。
:::

## 建議：第三個 Compose override

針對 `depositar/dsw-deployment` 的 `depositar-prod` branch，使用 repo 內可直接複製的
[`docker-compose.locale.yml`](../examples/depositar-production/docker-compose.locale.yml)。它
沿用既有 `server` service 與 `dsw_internal` network，不修改、fork 或取代原來兩份
Compose。

先把 API key 存成 deployment host 上的 `./secrets/dsw_locale_api_key`，並將 `/secrets/`
加入 deployment repo 的 `.gitignore`。完整建立、權限、驗證與復原步驟見
[`depositar production Compose integration`](https://github.com/ThreeMonth03/dsw-locale-tool/blob/main/examples/depositar-production/README.md)。

等價的核心 service 如下：

```yaml
services:
  locale-installer:
    image: "${DSW_LOCALE_INSTALLER_IMAGE:-ghcr.io/threemonth03/dsw-locale-installer:4.32.0}"
    platform: linux/amd64
    profiles:
      - locale-maintenance
    restart: "no"
    depends_on:
      server:
        condition: service_started
    environment:
      DSW_API_URL: http://server:3000/wizard-api
      DSW_API_KEY_FILE: /run/secrets/dsw_locale_api_key
    secrets:
      - dsw_locale_api_key
    networks:
      - dsw_internal

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
2. 修改 `.env` 的 `DSW_LOCALE_INSTALLER_IMAGE` tag。
3. 以第三個 override 明確執行一次；routine `up -d` 不會因 profile 而啟動它：

   ```console
   docker compose \
     --env-file .env \
     --file docker-compose.yml \
     --file docker-compose.prod.yml \
     --file ../dsw-locale-tool/examples/depositar-production/docker-compose.locale.yml \
     pull locale-installer

   docker compose \
     --env-file .env \
     --file docker-compose.yml \
     --file docker-compose.prod.yml \
     --file ../dsw-locale-tool/examples/depositar-production/docker-compose.locale.yml \
     run --rm --no-deps locale-installer
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
