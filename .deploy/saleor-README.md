# Saleor on the Velmor host

Deploys Saleor API, one Celery worker (with embedded beat), and the dashboard.
Images: `ghcr.io/saleor/saleor:3.22.66` (API + worker),
`ghcr.io/saleor/saleor-dashboard:3.22.42` (dashboard patch tags differ from core).
Reuses `velmor-postgres` and `velmor-redis`. Does not modify `/opt/pikupo` or Caddy.

## Limits (design D11)

| Container | Memory | Host bind |
|-----------|--------|-----------|
| velmor-saleor-api | 768M | 127.0.0.1:8001 |
| velmor-saleor-worker | 384M | none |
| velmor-saleor-dashboard | 256M | 127.0.0.1:9000 |

Postgres DB name: `saleor` (user `velmor`). Redis index: `1`.

## First-time setup on the server

```bash
# As root on 78.111.89.46
cd /opt/velmor
# Place docker-compose.saleor.yml and saleor.env (mode 600) here.
# Prefer: bash deploy-saleor.sh   (creates DB, env if missing, up, migrate, staff, app)

# Manual path:
# 1) Create DB (once)
docker exec -i velmor-postgres \
  psql -U velmor -d postgres -c "SELECT 1 FROM pg_database WHERE datname='saleor'" \
  | grep -q 1 || docker exec -i velmor-postgres \
  psql -U velmor -d postgres -c "CREATE DATABASE saleor OWNER velmor;"

# 2) Start
docker compose -p velmor-saleor -f docker-compose.saleor.yml --env-file saleor.env up -d

# 3) Migrate
docker compose -p velmor-saleor -f docker-compose.saleor.yml --env-file saleor.env \
  run --rm --no-deps saleor-api python manage.py migrate --noinput

# 4) Staff user (non-interactive)
docker compose -p velmor-saleor -f docker-compose.saleor.yml --env-file saleor.env \
  run --rm --no-deps saleor-api python manage.py shell -c \
  "from django.contrib.auth import get_user_model; U=get_user_model(); e='admin@example.com';
U.objects.filter(email=e).exists() or U.objects.create_superuser(e, password='CHANGE_ME')"

# 5) App token for the publication bridge (store the printed auth token offline)
docker compose -p velmor-saleor -f docker-compose.saleor.yml --env-file saleor.env \
  run --rm --no-deps saleor-api python manage.py create_app "Velmor" \
  --permission MANAGE_PRODUCTS --permission MANAGE_PRODUCT_TYPES_AND_ATTRIBUTES \
  --permission MANAGE_CHANNELS --activate
```

Internal GraphQL URL for Velmor services: `http://127.0.0.1:8001/graphql/`

## Smoke checks

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8001/health/
curl -s -X POST http://127.0.0.1:8001/graphql/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ shop { name } }"}'
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}'
```

## Stop Saleor only (leave Forkly / Velmor infra)

```bash
cd /opt/velmor
docker compose -p velmor-saleor -f docker-compose.saleor.yml --env-file saleor.env stop
```

Do not run `docker compose down -v` against the shared postgres/redis project.
