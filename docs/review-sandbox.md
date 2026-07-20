# Public review sandbox

The review sandbox is a real translated DSW interface backed only by disposable sample data. It is
intended for translators who need to move through pages, open local dialogs, and inspect wording in
context without receiving access to a production DSW.

The sandbox is different from the CI screenshot artifact:

| Preview | Where it runs | Result |
| --- | --- | --- |
| CI screenshot preview | Temporary GitHub Actions runner | Downloadable screenshots and reports |
| Public review sandbox | Maintainer-controlled Docker host | Browsable DSW pages at a stable URL |

A GitHub-hosted runner cannot keep a web service running after a job finishes. CI may prepare and
deploy a sandbox, but the containers must live on a persistent host.

## Safety boundary

Only the review gateway binds a host port. The DSW client, DSW server, PostgreSQL, and object storage
remain on an internal Docker network and have no host ports.

The gateway applies these rules before a request reaches DSW:

- Approved UI routes and static client assets are readable.
- API `GET`, `HEAD`, and `OPTIONS` requests are allowed for rendering pages.
- `POST /wizard-api/tokens` is allowed so a reviewer can sign in.
- Other API writes and all WebSocket upgrades return HTTP 403.
- UI routes absent from `review/pages.yml` return HTTP 404.

The browser also displays a permanent review banner and disables links to unapproved routes. This is
navigation guidance; the gateway remains the security boundary. Use only synthetic Knowledge Model
and project content because authenticated read requests can expose all data in this isolated DSW.

## Host requirements

The host needs Docker Engine with the Compose plugin, a TLS reverse proxy, and one loopback port for
each release line. Clone this repository on the host and obtain:

- The locale ZIP built from the translation branch being reviewed.
- A sample Knowledge Model JSON package.
- The localizable DSW client image selected by the locale workflow.
- A published [`dsw-review-tool` image from
  GHCR](https://github.com/ThreeMonth03/dsw-locale-tool/pkgs/container/dsw-review-tool).

No production database, DSW configuration, Docker network, API key, or user account is used.

## Configure one release line

Copy `review/example.env` to a host-only environment file and replace every placeholder. Keep the
four identifiers unique for each concurrently running release:

| Setting | Must be unique per release |
| --- | --- |
| `DSW_REVIEW_ORIGIN` | Yes; use a dedicated HTTPS hostname |
| `DSW_REVIEW_PORT` | Yes; the gateway binds this port on `127.0.0.1` |
| `DSW_REVIEW_PROJECT_NAME` | Yes; isolates Docker networks and volumes |
| `DSW_REVIEW_RUNTIME_DIR` | Yes; place it below `review/runtime/` |

`DSW_VERSION`, `DSW_CLIENT_IMAGE`, and the locale bundle must describe the same DSW release line.
Use an immutable `dsw-review-tool:git-<commit>` image when reproducibility matters. The `main` tag is
available for hosts that intentionally follow the current reviewed tool release.

The reviewer account must match the bootstrap account in the fresh official DSW image. Its
credentials are shown on the sandbox landing page. They grant access only to synthetic data, and
the gateway blocks application writes.

## Add TLS routing

Route one public hostname to the release's loopback port. A minimal Nginx virtual host has this
shape; certificate management is host-specific:

```nginx
server {
    listen 443 ssl;
    server_name <review-hostname>;

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_pass http://127.0.0.1:<loopback-port>;
    }
}
```

Do not proxy directly to the DSW client or server containers.

## Start and replace a sandbox

Pass the host-only environment file to the launcher:

```console
./review/up.sh /path/to/review-release.env
```

The launcher validates Compose, removes the previous disposable data for that release, generates a
fresh DSW secret and RSA key, installs the locale, imports the sample Knowledge Model, creates a
project, starts the gateway, and verifies that reads work while writes and WebSockets fail closed.

Open `DSW_REVIEW_ORIGIN` after the command succeeds. The landing page shows the reviewer account and
links to every approved page.

To replace the review after a translation merge, update the locale ZIP path and any image references
in the same environment file, then run `up.sh` again. To remove one release and all of its disposable
database and object-storage volumes:

```console
./review/down.sh /path/to/review-release.env
```

## Connect translation CI

Keep translation work in the translation repository. A deployment job only needs to deliver the
verified locale ZIP and sample Knowledge Model to the host, update the matching environment file,
and run `review/up.sh`. This can use a narrowly scoped SSH account or a self-hosted runner on the
review host.

Use one stable environment per maintained release branch. A pull request may use another unique
hostname, port, Compose project, and runtime directory when an ephemeral public review is needed.
Deleting that environment with `down.sh` removes its data. Host credentials, DNS, and TLS settings
stay outside both repositories.
