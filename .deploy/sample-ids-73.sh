#!/usr/bin/env bash
docker exec velmor-postgres psql -U velmor -d velmor -c "SELECT id, left(title,40) FROM candidates LIMIT 8;"
