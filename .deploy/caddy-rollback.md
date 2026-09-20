# Caddy rollback (Proofbasket additive blocks)

Restore `/opt/pikupo/backend/Caddyfile.prod` from the sibling
`Caddyfile.prod.bak.YYYYMMDD-HHMMSS` taken before the edit (or delete only the
trailing `shop.78-111-89-46.sslip.io` and `velmor-api.78-111-89-46.sslip.io`
site blocks that were appended), then
`docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile` and
`docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` from
`/opt/pikupo/backend`. If `extra_hosts` was added under the `caddy` service
only, remove that key and recreate the caddy container the same way it was
brought up. Pikupo site blocks above the append stay untouched.
