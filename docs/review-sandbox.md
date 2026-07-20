# Browsable translation review

The review sandbox is a real translated DSW backed only by disposable sample data. It lets a
reviewer navigate approved pages and inspect wording in context without access to a production DSW.

Two deployment modes use the same route policy and gateway:

| Mode | Best for | Availability |
| --- | --- | --- |
| GitHub live preview | Reviewing a translation pull request | Temporary random HTTPS URL |
| Docker host | A maintained shared review environment | Stable maintainer-provided URL |

The screenshot preview remains available as a build artifact after CI finishes. A live preview is
for interactive review while its workflow job is running.

## GitHub live preview

The reusable `live-preview.yml` workflow runs the entire sandbox on a GitHub-hosted runner and
publishes it through a unique Cloudflare Quick Tunnel. It does not require a server, DNS record,
certificate, or shared tunnel name.

Each run:

1. validates and packages one exact translation revision;
2. selects the official client for that DSW release;
3. downloads and verifies the translated Knowledge Model and document template for that release;
4. starts a private DSW, database, and object store;
5. exposes only the review gateway through a random HTTPS URL;
6. adds the URL and release metadata to the translation pull request;
7. removes all containers and data when the review ends.

The default lifetime is 30 minutes without browser activity, with an absolute maximum of 180
minutes. Opening a page and interacting with the interface sends a rate-limited activity signal to
the gateway. A new commit cancels the old run and creates a fresh preview, so concurrent pull
requests never share a URL or DSW instance.

The translation repository should call the reusable workflow only after its trusted pull-request
validation succeeds. Grant `contents: read` and `pull-requests: write`; no repository secret is
required.

## Safety boundary

Only the review gateway binds a host port. The DSW client, DSW server, PostgreSQL, and object storage
remain on an internal Docker network and have no public ports.

The gateway applies these rules before a request reaches DSW:

- Approved UI routes and static client assets are readable.
- API `GET`, `HEAD`, and `OPTIONS` requests are allowed for rendering pages.
- `POST /wizard-api/tokens` is allowed so a reviewer can sign in.
- Other API writes and all WebSocket upgrades return HTTP 403.
- UI routes absent from `review/pages.yml` return HTTP 404.

The browser displays a permanent review banner and disables links to unapproved routes. This is
navigation guidance; the gateway remains the security boundary. Use only public review content
because authenticated read requests can expose all data in the isolated DSW.

## Run on a Docker host

A stable review environment needs Docker Engine with the Compose plugin, a TLS reverse proxy, and
one loopback port for each concurrently running sandbox. Clone this repository on the host and
obtain:

- the locale ZIP built from the translation branch;
- the translated Knowledge Model and document template bundles configured for the DSW release;
- the official DSW client image matching the locale release;
- a published [`dsw-review-tool` image from
  GHCR](https://github.com/ThreeMonth03/dsw-locale-tool/pkgs/container/dsw-review-tool).

No production database, DSW configuration, Docker network, API key, or user account is used.

Copy `review/example.env` to a host-only environment file and fill every setting. The origin, port,
Compose project, and runtime directory must be unique for sandboxes that run concurrently.
`DSW_VERSION`, `DSW_CLIENT_IMAGE`, and the locale bundle must describe the same DSW release.

Route the public HTTPS hostname to `127.0.0.1:DSW_REVIEW_PORT`. Do not proxy directly to the DSW
client or server containers.

Start or replace the sandbox:

```console
./review/up.sh /path/to/review.env
```

The launcher removes the previous disposable data for that Compose project, creates fresh secrets,
installs the locale, imports both translated content bundles, creates a project, and verifies that
reads work while writes and WebSockets fail closed.

Remove the sandbox and its disposable volumes:

```console
./review/down.sh /path/to/review.env
```

The scripts also accept configuration supplied entirely through environment variables, which is
how the GitHub live-preview workflow runs them.
