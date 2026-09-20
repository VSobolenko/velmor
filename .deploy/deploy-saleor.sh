#!/usr/bin/env bash
# Bootstrap Saleor on /opt/velmor. Idempotent where possible.
# Does not touch /opt/pikupo. Does not start scout/auditor.
set -euo pipefail

ROOT="${VELMOR_ROOT:-/opt/velmor}"
COMPOSE_FILE="${ROOT}/docker-compose.saleor.yml"
ENV_FILE="${ROOT}/saleor.env"
PROJECT="velmor-saleor"

cd "${ROOT}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "missing ${COMPOSE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${ROOT}/.env" ]]; then
  echo "missing ${ROOT}/.env (POSTGRES_PASSWORD)" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${ROOT}/.env"
if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "POSTGRES_PASSWORD unset in ${ROOT}/.env" >&2
  exit 1
fi

echo "== free memory =="
free -m

echo "== create database saleor if missing =="
EXISTS="$(docker exec velmor-postgres psql -U velmor -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='saleor'")"
if [[ "${EXISTS}" != "1" ]]; then
  docker exec velmor-postgres psql -U velmor -d postgres -c \
    "CREATE DATABASE saleor OWNER velmor;"
else
  echo "database saleor already exists"
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "== generating ${ENV_FILE} =="
  umask 077
  POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" python3 - <<'PY'
import os, secrets, subprocess, urllib.parse
from pathlib import Path

root = Path(os.environ.get("VELMOR_ROOT", "/opt/velmor"))
env_path = root / "saleor.env"
pg_pass = os.environ["POSTGRES_PASSWORD"]
secret = secrets.token_hex(48)
super_pass = secrets.token_hex(16)
pem = subprocess.check_output(["openssl", "genrsa", "2048"], stderr=subprocess.DEVNULL).decode()
# One-line PEM with literal \n for django-environ
rsa_one_line = pem.strip().replace("\n", "\\n")
db_url = "postgres://velmor:%s@postgres:5432/saleor" % urllib.parse.quote(pg_pass, safe="")
# Docker Compose expands \n inside double-quoted env values into real newlines.
lines = [
    "SECRET_KEY=%s" % secret,
    "DEBUG=False",
    "ALLOWED_HOSTS=127.0.0.1,localhost",
    "ALLOWED_CLIENT_HOSTS=127.0.0.1,localhost,http://127.0.0.1:9000",
    "PUBLIC_URL=http://127.0.0.1:8001/",
    "DEFAULT_FROM_EMAIL=noreply@localhost",
    "DEFAULT_CHANNEL_SLUG=default-channel",
    "DEFAULT_COUNTRY=US",
    "DEFAULT_CURRENCY=USD",
    "DATABASE_URL=%s" % db_url,
    "CACHE_URL=redis://redis:6379/1",
    "CELERY_BROKER_URL=redis://redis:6379/1",
    'RSA_PRIVATE_KEY="%s"' % rsa_one_line,
    "SALEOR_DASHBOARD_API_URL=http://127.0.0.1:8001/graphql/",
    "SALEOR_SUPERUSER_EMAIL=admin@velmor.local",
    "SALEOR_SUPERUSER_PASSWORD=%s" % super_pass,
]
env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
env_path.chmod(0o600)
print("wrote", env_path, "(mode 600); staff password printed once below")
print("SALEOR_SUPERUSER_PASSWORD=%s" % super_pass)
PY
else
  echo "reusing existing ${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
fi

# Do not source saleor.env (RSA_PRIVATE_KEY breaks bash). Read staff fields only.
EMAIL="$(grep -E '^SALEOR_SUPERUSER_EMAIL=' "${ENV_FILE}" | head -n1 | cut -d= -f2-)"
PASS="$(grep -E '^SALEOR_SUPERUSER_PASSWORD=' "${ENV_FILE}" | head -n1 | cut -d= -f2-)"
if [[ -z "${EMAIL}" || -z "${PASS}" ]]; then
  echo "SALEOR_SUPERUSER_EMAIL/PASSWORD missing in ${ENV_FILE}" >&2
  exit 1
fi

COMPOSE=(docker compose -p "${PROJECT}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}")

echo "== pull + up =="
"${COMPOSE[@]}" pull
"${COMPOSE[@]}" up -d

echo "== migrate =="
"${COMPOSE[@]}" run --rm --no-deps saleor-api python manage.py migrate --noinput

echo "== staff user =="
"${COMPOSE[@]}" run --rm --no-deps saleor-api \
  python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
email = '''${EMAIL}'''
password = '''${PASS}'''
if U.objects.filter(email=email).exists():
    print('staff already exists:', email)
else:
    U.objects.create_superuser(email, password=password)
    print('created staff:', email)
"

echo "== app token (Velmor) =="
APP_OUT="$("${COMPOSE[@]}" run --rm --no-deps saleor-api python manage.py create_app \
  "Velmor" \
  --permission MANAGE_PRODUCTS \
  --permission MANAGE_PRODUCT_TYPES_AND_ATTRIBUTES \
  --permission MANAGE_CHANNELS \
  --activate 2>&1 || true)"
echo "${APP_OUT}"
if echo "${APP_OUT}" | grep -qiE 'already|exist|duplicate|unique'; then
  echo "app may already exist; create_app output above"
fi
echo "token created (or already present); do not paste the auth token into git reports"

echo "== smoke =="
sleep 8
curl -s -o /dev/null -w "health:%{http_code}\n" http://127.0.0.1:8001/health/ || true
curl -s -X POST http://127.0.0.1:8001/graphql/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ __typename shop { name } }"}' || true
echo
echo "== containers =="
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
echo "== memory =="
free -m
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' \
  | grep -E 'NAME|saleor|velmor|backend' || true

echo "done"
