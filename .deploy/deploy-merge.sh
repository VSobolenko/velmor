#!/usr/bin/env bash
# Move the server checkout onto the reconciled history without losing anything.
# The working tree's local modifications are the files that were copied up by hand
# during development; they are superseded by the commits in the bundle, so they are
# stashed rather than discarded - the stash is recoverable if that judgement is wrong.
set -uo pipefail

APP=/opt/velmor/app
cd "$APP"

echo '=== before ==='
git log --oneline -1

echo
echo '=== stash the hand-copied files (including untracked) ==='
git stash push -u -m 'scp-deployed files before rebase-work' 2>&1 | tail -3

echo
echo '=== fetch the bundle ==='
git fetch /root/velmor-2.bundle 'refs/heads/rebase-work:refs/heads/rebase-work' 2>&1 | tail -5

echo
echo '=== checkout ==='
git checkout rebase-work 2>&1 | tail -5
echo "checkout_exit=$?"

echo
echo '=== after ==='
git log --oneline -3
git status --short | head -10

echo
echo '=== env profiles survived? ==='
for f in packages/scout/.env.dev packages/auditor/.env.dev packages/api/.env.dev; do
  if [ -f "$f" ]; then echo "present: $f"; else echo "MISSING: $f"; fi
done

echo
echo '=== confirm the reconciled code is what landed ==='
echo -n 'connector LICENSE_IDS: '; grep -c 'LICENSE_IDS' packages/services/src/connectors/openverse.py
echo -n 'state license_claim:   '; grep -c 'license_claim' packages/auditor/src/state.py
echo -n 'verified_quote:        '; grep -c '_verified_quote' packages/auditor/src/nodes/investigate.py
echo -n 'investigation_failures:'; grep -c 'investigation_failures' packages/auditor/src/state.py
echo -n 'psycopg in pyproject:  '; grep -c 'psycopg' pyproject.toml
echo -n 'storefront app.py:     '; test -f packages/api/src/app.py && echo present || echo MISSING
