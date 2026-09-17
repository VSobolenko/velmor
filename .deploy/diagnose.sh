#!/usr/bin/env bash
set -uo pipefail

echo '=== containers (all) ==='
docker ps -a --format '{{.Names}}|{{.Status}}|{{.Image}}'

echo
echo '=== inspect each ==='
for c in $(docker ps -aq); do
  docker inspect -f '{{.Name}} status={{.State.Status}} restarts={{.RestartCount}} oom={{.State.OOMKilled}} exit={{.State.ExitCode}} started={{.State.StartedAt}}' "$c"
done

echo
echo '=== health detail ==='
docker inspect -f '{{.Name}} {{range .State.Health.Status}}{{.}}{{end}}' $(docker ps -aq) 2>/dev/null

echo
echo '=== compose projects ==='
docker compose ls -a 2>&1 | head -20

echo
echo '=== volumes ==='
docker volume ls

echo
echo '=== recent docker events (last 200) ==='
timeout 10 docker events --since 3h --until 0s --filter 'type=container' --format '{{.Time}} {{.Action}} {{.Actor.Attributes.name}}' 2>&1 | tail -60

echo
echo '=== dmesg oom ==='
dmesg -T 2>/dev/null | grep -iE 'oom|killed process' | tail -20 || echo 'no dmesg access or no oom'

echo
echo '=== journal docker (tail) ==='
journalctl -u docker --no-pager --since '3 hours ago' 2>/dev/null | grep -iE 'kill|oom|error|fail|stop|remove' | tail -30 || echo 'no journal'
