#!/usr/bin/env bash
set -euo pipefail
for port in 3000 8080; do
  iptables -C INPUT -p tcp --dport "$port" -s 127.0.0.1 -j ACCEPT 2>/dev/null \
    || iptables -I INPUT -p tcp --dport "$port" -s 127.0.0.1 -j ACCEPT
  iptables -C INPUT -p tcp --dport "$port" -s 172.16.0.0/12 -j ACCEPT 2>/dev/null \
    || iptables -I INPUT -p tcp --dport "$port" -s 172.16.0.0/12 -j ACCEPT
  iptables -C INPUT -p tcp --dport "$port" -j DROP 2>/dev/null \
    || iptables -A INPUT -p tcp --dport "$port" -j DROP
done
echo '=== rules ==='
iptables -S INPUT | grep -E '3000|8080'
echo '=== checks ==='
curl -s -o /dev/null -w 'loop3000=%{http_code}\n' --max-time 3 http://127.0.0.1:3000/
curl -s -o /dev/null -w 'caddy_shop=%{http_code}\n' --max-time 15 https://shop.78-111-89-46.sslip.io/
curl -s -o /dev/null -w 'caddy_api=%{http_code}\n' --max-time 15 https://velmor-api.78-111-89-46.sslip.io/health
