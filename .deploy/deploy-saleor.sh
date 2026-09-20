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
  SECRET_KEY="$(openssl rand -hex 48)"
  SUPER_PASS="$(openssl rand -hex 16)"
  RSA_PEM="$(openssl genrsa 2048 2>/dev/null | awk '{printf "%s\\n", $0}')"
  umask 077
  cat > "${ENV_FILE}" <<EOF
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=127.0.0.1,localhost
ALLOWED_CLIENT_HOSTS=127.0.0.1,localhost,http://127.0.0.1:9000
PUBLIC_URL=http://127.0.0.1:8001/
DEFAULT_FROM_EMAIL=noreply@localhost
DEFAULT_CHANNEL_SLUG=default-channel
DEFAULT_COUNTRY=US
DEFAULT_CURRENCY=USD
DATABASE_URL=postgres://velmor:${POSTGRES_PASSWORD}@postgres:5432/saleor
CACHE_URL=redis://redis:6379/1
CELERY_BROKER_URL=redis://redis:6379/1
RSA_PRIVATE_KEY=${RSA_PEM}
SALEOR_DASHBOARD_API_URL=http://127.0.0.1:8001/graphql/
SALEOR_SUPERUSER_EMAIL=admin@velmor.local
SALEOR_SUPERUSER_PASSWORD=${SUPER_PASS}
EOF
  chmod 600 "${ENV_FILE}"
  echo "wrote ${ENV_FILE} (mode 600); staff password printed once below"
  echo "SALEOR_SUPERUSER_PASSWORD=${SUPER_PASS}"
else
  echo "reusing existing ${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
fi

# shellcheck disable=SC1091
set -a
source "${ENV_FILE}"
set +a

COMPOSE=(docker compose -p "${PROJECT}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}")

echo "== pull + up =="
"${COMPOSE[@]}" pull
"${COMPOSE[@]}" up -d

echo "== migrate =="
"${COMPOSE[@]}" run --rm --no-deps saleor-api python manage.py migrate --noinput

echo "== staff user =="
EMAIL="${SALEOR_SUPERUSER_EMAIL:-admin@velmor.local}"
PASS="${SALEOR_SUPERUSER_PASSWORD:?SALEOR_SUPERUSER_PASSWORD missing in saleor.env}"
"${COMPOSE[@]}" run --rm --no-deps -e DJANGO_SUPERUSER_PASSWORD="${PASS}" saleor-api \
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
sleep 5
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
