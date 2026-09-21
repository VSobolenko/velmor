#!/usr/bin/env bash
set -euo pipefail
cd /opt/velmor/app
git fetch /root/velmor-73c.bundle feat/add-storefront-commerce:refs/heads/deploy-73c
git checkout deploy-73c -- .
git log -1 --oneline deploy-73c
sed -i 's/\r$//' /tmp/run-publish-73.sh
chmod +x /tmp/run-publish-73.sh
# truncate prior log so counts are clean
: > /tmp/velmor-publish-73.log
nohup /tmp/run-publish-73.sh > /tmp/run-publish-73.out 2>&1 &
echo "started PID=$!"
