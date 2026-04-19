#!/usr/bin/env python3
import json, subprocess, time

BASE = 'https://oburscuforring.beget.app'
HH_TOKEN = 'USERK2LG6I3D4C3JH9BJ6IO6BJVBM5OONJDARBHTO9PBJE277OIMIAOVJCC9PMDL'
TEST_NID = '5169546644'

with open('/tmp/n8n_cookie.txt') as f:
    lines = f.readlines()
cookie_val = next((l.strip().split()[-1] for l in lines if 'n8n-auth' in l), '')
print('Cookie:', cookie_val[:15] + '...')

def n8n(method, path, data=None):
    cmd = ['curl', '-s', '-b', f'n8n-auth={cookie_val}',
           '-H', 'Content-Type: application/json',
           '-X', method, f'{BASE}/rest/{path}']
    if data:
        cmd += ['-d', json.dumps(data, ensure_ascii=False)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        print(f'  JSON parse error: {r.stdout[:200]}')
        return {}

def hh(path):
    r = subprocess.run(['curl', '-s', f'https://api.hh.ru/{path}',
        '-H', f'Authorization: Bearer {HH_TOKEN}',
        '-H', 'HH-User-Agent: HR-Assistant/1.0 (n@extravert.bz)'],
        capture_output=True, text=True)
    return json.loads(r.stdout)

# === Fix main workflow ===
print('\n=== Step 1: Fix main workflow ===')
wf = n8n('GET', 'workflows/4LXW8oTh168CnTqy').get('data', {})
nodes = wf.get('nodes', [])

# Disable HH.RU message-sending nodes (dry test - no messages to candidates)
DISABLE = {
    'C4 \u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0432\u0435\u0436\u043b\u0438\u0432\u044b\u0439 \u043e\u0442\u043a\u0430\u0437',  # C4
    'C5 \u0421\u0442\u0430\u0442\u0443\u0441: \u041e\u0442\u043a\u0430\u0437',  # C5
    'C7 \u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043f\u0435\u0440\u0432\u044b\u0439 \u0432\u043e\u043f\u0440\u043e\u0441',  # C7
    'C8 \u0421\u0442\u0430\u0442\u0443\u0441: \u0412 \u0440\u0430\u0441\u0441\u043c\u043e\u0442\u0440\u0435\u043d\u0438\u0438',  # C8
}

for n in nodes:
    nm = n.get('name', '')
    url = str(n.get('parameters', {}).get('url', ''))
    if nm in DISABLE:
        n['disabled'] = True
        print(f'  DISABLED: {nm}')
    if 'E2' in nm and 'negotiations?' in url and '/response?' not in url:
        n['parameters']['url'] = url.replace('/negotiations?', '/negotiations/response?')
        print(f'  FIXED E2 URL: {n["parameters"]["url"][:70]}')

print('Patching main workflow...')
result = n8n('PATCH', 'workflows/4LXW8oTh168CnTqy', wf)
vid = result.get('data', result).get('versionId', '?')[:8]
print(f'  versionId: {vid}')

# === Check poller workflow ===
print('\n=== Step 2: Check poller ===')
pf = n8n('GET', 'workflows/swW1Www0gmme6Yvi').get('data', {})
for n in pf.get('nodes', []):
    url = str(n.get('parameters', {}).get('url', ''))
    if 'hh.ru' in url:
        print(f'  {n["name"]}: {url[:80]}')

# === Check negotiation ===
print(f'\n=== Step 3: Check nid {TEST_NID} ===')
neg = hh(f'negotiations/{TEST_NID}')
if 'id' in neg:
    vac = neg.get('vacancy', {})
    res = neg.get('resume', {}) or {}
    print(f'  state: {neg.get("state", {}).get("id")}')
    print(f'  vacancy: {vac.get("id")} - {vac.get("name", "?")[:50]}')
    print(f'  applicant: {res.get("last_name","")} {res.get("first_name","")}')
else:
    print(f'  ERROR: {list(neg.keys())}')

# === Fire webhook ===
print('\n=== Step 4: Fire webhook ===')
cmd = ['curl', '-s', '-X', 'POST',
       '-H', 'Content-Type: application/json',
       '-d', json.dumps({'type': 'NEW_NEGOTIATION', 'object': {'id': TEST_NID}}),
       f'{BASE}/webhook/hh-events']
r2 = subprocess.run(cmd, capture_output=True, text=True)
print(f'  response: {r2.stdout[:200]}')

print('\nWaiting 30s for execution...')
time.sleep(30)

# === Check executions ===
print('\n=== Step 5: Execution results ===')
execs = n8n('GET', 'executions?workflowId=4LXW8oTh168CnTqy&limit=3')
for ex in execs.get('data', []):
    print(f'  id={ex.get("id")} status={ex.get("status")} mode={ex.get("mode")} finished={ex.get("finished")}')
    # Get execution detail
    detail = n8n('GET', f'executions/{ex.get("id")}')
    dd = detail.get('data', detail)
    data_obj = dd.get('data', {})
    result_data = data_obj.get('resultData', {})
    run_data = result_data.get('runData', {})
    if run_data:
        print(f'  Nodes executed: {list(run_data.keys())}')
    break  # only check the latest

print('\nDONE')
