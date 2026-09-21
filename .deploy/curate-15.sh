#!/usr/bin/env bash
# Give the API profile the model access curation needs, then curate 15 goods.
#
# The user approved reusing the auditor's model credential for this. The values are copied
# into packages/api/.env.dev, which is gitignored and never committed. Nothing here prints a
# secret value: only the names that were added.
set -u
cd /opt/velmor/app

API_ENV=packages/api/.env.dev
AUD_ENV=packages/auditor/.env.dev

echo '=== carry the model credential into the API profile ==='
for name in OPENAI_API_KEY OPENAI_BASE_URL; do
  if grep -q "^${name}=" "$API_ENV"; then
    echo "  already present: $name"
    continue
  fi
  line=$(grep "^${name}=" "$AUD_ENV")
  if [ -z "$line" ]; then
    echo "  NOT FOUND in the auditor profile: $name"
    exit 1
  fi
  printf '%s\n' "$line" >> "$API_ENV"
  echo "  copied: $name (value not shown)"
done
echo
echo '=== the API profile now declares (names only) ==='
grep -oE '^[A-Z_]+' "$API_ENV" | grep -E 'OPENAI' | sort -u
echo

echo '=== curate 15 goods ==='
export PATH="$HOME/.local/bin:$PATH"
start=$(date +%s)
uv run velmor curate --model openai:deepseek-chat --env dev --limit 15 --apply > /tmp/curate15.log 2>&1
code=$?
echo "exit=$code in $(( $(date +%s) - start ))s"
echo '---- begin output ----'
cat /tmp/curate15.log
echo '---- end output ----'
