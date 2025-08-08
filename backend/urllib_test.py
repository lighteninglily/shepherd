import os, json, urllib.request
# read key from backend/.env
key = ''
with open('.\\.env','r',encoding='utf-8',errors='ignore') as f:
    for line in f:
        if line.startswith('OPENAI_API_KEY='):
            key = line.split('=',1)[1].strip()
            break
print('KEYLEN', len(key), 'TAIL', key[-8:])
# REST call
payload = {
    'model': 'gpt-4o-mini',
    'messages': [{'role':'user','content':'Ping one word.'}],
    'max_tokens': 5,
}
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(
    'https://api.openai.com/v1/chat/completions',
    data=data,
    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    method='POST'
)
try:
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode('utf-8','ignore')
        print('OK', resp.status, body[:200])
except Exception as e:
    import traceback
    print('ERR', type(e).__name__, str(e))
    traceback.print_exc()
