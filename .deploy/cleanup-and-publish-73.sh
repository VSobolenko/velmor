#!/usr/bin/env bash
set -euo pipefail
cd /opt/velmor/app
TOKEN=$(grep '^SALEOR_APP_TOKEN=' packages/api/.env.dev | cut -d= -f2-)

python3 - <<'PY'
import json, re, urllib.request

text = open('/opt/velmor/app/packages/api/.env.dev', encoding='utf-8').read()
auth = re.search(r'^SALEOR_APP_TOKEN=(.+)$', text, re.M).group(1).strip()

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
        payload = json.load(resp)
    if payload.get('errors'):
        raise SystemExit(payload['errors'])
    return payload

deleted = 0
after = None
while True:
    variables = {'first': 100}
    after_clause = ''
    if after:
        variables['after'] = after
        after_clause = ', after: $after'
        query = f'''
          query($first: Int!, $after: String) {{
            products(first: $first{after_clause}) {{
              pageInfo {{ hasNextPage endCursor }}
              edges {{ node {{ id slug }} }}
            }}
          }}
        '''
    else:
        query = '''
          query($first: Int!) {
            products(first: $first) {
              pageInfo { hasNextPage endCursor }
              edges { node { id slug } }
            }
          }
        '''
    data = gql(query, variables)['data']['products']
    for edge in data['edges']:
        node = edge['node']
        if not node['slug'].startswith('good-'):
            continue
        result = gql(
            '''
            mutation($id: ID!) {
              productDelete(id: $id) {
                errors { message field code }
              }
            }
            ''',
            {'id': node['id']},
        )
        errs = result['data']['productDelete']['errors']
        if errs:
            raise SystemExit(f"delete {node['slug']}: {errs}")
        print('deleted', node['slug'])
        deleted += 1
    if not data['pageInfo']['hasNextPage']:
        break
    after = data['pageInfo']['endCursor']
print(f'deleted_total={deleted}')
PY

docker exec velmor-postgres psql -U velmor -d velmor -c "TRUNCATE catalogue_entries;"

: > /tmp/velmor-publish-73.log
export PATH="$HOME/.local/bin:$PATH"
nohup /tmp/run-publish-73.sh > /tmp/run-publish-73.out 2>&1 &
echo "started PID=$!"
