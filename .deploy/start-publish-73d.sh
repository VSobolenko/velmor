#!/usr/bin/env bash
# Delete orphan Digital-good products from a prior partial publish, then run 7.3.
set -euo pipefail
cd /opt/velmor/app
git fetch /root/velmor-73d.bundle feat/add-storefront-commerce:refs/heads/deploy-73d
git checkout deploy-73d -- .
git log -1 --oneline deploy-73d

TOKEN=$(grep '^SALEOR_APP_TOKEN=' packages/api/.env.dev | cut -d= -f2-)

python3 - <<'PY'
import json, urllib.request

token = open('/opt/velmor/app/packages/api/.env.dev').read()
import re
m = re.search(r'^SALEOR_APP_TOKEN=(.+)$', token, re.M)
assert m
auth = m.group(1).strip()

def gql(query, variables=None):
    body = json.dumps({'query': query, 'variables': variables or {}}).encode()
    req = urllib.request.Request(
        'http://127.0.0.1:8001/graphql/',
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {auth}',
        },
        method='POST',
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)

# Page through products and delete those with our good- prefix.
deleted = 0
while True:
    data = gql('''
      query {
        products(first: 50, filter: {search: "good-openverse"}) {
          edges { node { id slug } }
        }
      }
    ''')
    edges = data['data']['products']['edges']
    if not edges:
        break
    for edge in edges:
        node = edge['node']
        if not node['slug'].startswith('good-'):
            continue
        result = gql(
            '''
            mutation($id: ID!) {
              productDelete(id: $id) {
                product { id }
                errors { message }
              }
            }
            ''',
            {'id': node['id']},
        )
        errs = result['data']['productDelete']['errors']
        if errs:
            raise SystemExit(f"delete failed for {node['slug']}: {errs}")
        deleted += 1
        print(f"deleted {node['slug']}")
print(f"deleted_total={deleted}")
PY

docker exec velmor-postgres psql -U velmor -d velmor -c "TRUNCATE catalogue_entries;"

sed -i 's/\r$//' /tmp/run-publish-73.sh
chmod +x /tmp/run-publish-73.sh
: > /tmp/velmor-publish-73.log
nohup /tmp/run-publish-73.sh > /tmp/run-publish-73.out 2>&1 &
echo "started PID=$!"
