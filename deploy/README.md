# Deploy — venues.h1756.es

Public demo instance on the H1756 VPS (Coolify 4 + Traefik, wildcard
`*.h1756.es`). Same operating pattern as `votes-es`: labeled containers on
the `coolify` network, no published ports, TLS by the Coolify proxy.

## What runs

| Container | Image | Limits | Notes |
|---|---|---|---|
| `venues-api` | `venue-access-api:<sha>` | 384 MB, 0.5 CPU | FastAPI, read-only FS, synthetic dataset baked in |
| `venues-web` | `venue-access-web:<sha>` | 384 MB, 0.5 CPU | Next.js standalone, read-only FS |

Routing: `Host(venues.h1756.es) && PathPrefix(/api/)` → api, everything else
→ web, HTTP → HTTPS redirect, HSTS/nosniff/frame-deny headers.

**Data**: the public instance serves the synthetic demo dataset
(`venue-access demo`, deterministic seed) because the real aggregated
dataset is `CODE_PUBLISHABLE_DATASET_INTERNAL_ONLY` (ADR 007). There is no
volume and nothing to back up: rebuilding the image recreates the data.
Serving real data publicly requires clearing `publication_rights.yml` first.

## Release

Requires Docker locally, the `h1756-vps1` SSH alias and a clean git tree.

```bash
deploy/release.sh build     # builds both targets tagged with the git SHA + smoke test
deploy/release.sh ship      # docker save | ssh docker load; uploads compose.yml
deploy/release.sh up        # docker compose up -d --wait on the VPS
deploy/release.sh verify    # external checks: web, /about, /api/v1/ready, redirect
```

Before the first `up`, confirm on the VPS that nothing else claims the host:
`sudo docker ps --format '{{.Names}} {{.Labels}}' | grep venues.h1756.es`.

## Rollback

```bash
ssh h1756-vps1 'sudo docker images venue-access-api'   # list available tags
deploy/release.sh rollback <previous-sha>
```

Keep the previous tag's images on the VPS until the new release is verified;
remove older ones with `sudo docker image rm venue-access-{api,web}:<old-sha>`.
Never `docker volume prune` on the shared host.

## Budget

Measured locally on 2026-10-08 (read-only containers behind a proxy): RSS at
rest api 72 MiB, web 59 MiB; image sizes api 414 MB, web 210 MB. The VPS has
8 GB shared with Coolify and other projects; the limits above cap the worst
case at 768 MB.
