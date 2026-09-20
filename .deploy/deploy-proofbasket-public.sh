#!/usr/bin/env bash
# Host-side helper for task 7.2 (public HTTPS Proofbasket via additive Caddy).
# Run on the VPS as root after the app tree at /opt/velmor/app is synced.
set -euo pipefail

APP=/opt/velmor/app
PIKUPO=/opt/pikupo/backend
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BLOCKS_SRC="${APP}/.deploy/caddy-velmor-blocks.caddy"
CADDYFILE="${PIKUPO}/Caddyfile.prod"
BACKUP="${PIKUPO}/Caddyfile.prod.bak.${STAMP}"

echo "== backup Caddyfile.prod =="
cp -a "${CADDYFILE}" "${BACKUP}"
echo "backup: ${BACKUP}"

if ! grep -q 'shop.78-111-89-46.sslip.io' "${CADDYFILE}"; then
  echo "== append Proofbasket site blocks =="
  printf '\n' >> "${CADDYFILE}"
  cat "${BLOCKS_SRC}" >> "${CADDYFILE}"
else
  echo "shop block already present; skip append"
fi

COMPOSE_FILE="${PIKUPO}/docker-compose.yml"
if ! grep -q 'host.docker.internal:host-gateway' "${COMPOSE_FILE}"; then
  echo "== add caddy extra_hosts =="
  python3 - <<'PY'
from pathlib import Path
path = Path("/opt/pikupo/backend/docker-compose.yml")
text = path.read_text()
needle = "  caddy:\n"
if "host.docker.internal:host-gateway" in text:
    raise SystemExit(0)
idx = text.find(needle)
if idx < 0:
    raise SystemExit("caddy service not found")
# Insert extra_hosts immediately after the service key line.
insert = (
    "  caddy:\n"
    "    extra_hosts:\n"
    '      - "host.docker.internal:host-gateway"\n'
)
text = text[:idx] + insert + text[idx + len(needle) :]
path.write_text(text)
print("patched docker-compose.yml caddy.extra_hosts")
PY
  (cd "${PIKUPO}" && docker compose up -d caddy)
else
  echo "extra_hosts already present"
fi

echo "== validate =="
(cd "${PIKUPO}" && docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile)

echo "== reload =="
(cd "${PIKUPO}" && docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile)

echo "done; backup=${BACKUP}"
