import json
import urllib.request
from app.services.chat import ChatService

s = ChatService()
print('API_KEY_MASK', len(s.api_key), s.api_key[:7], s.api_key[-4:])

payload = {
    'model': 'gpt-4o-mini',
    'messages': [{'role':'user','content':'Ping one word.'}],
    'max_tokens': 5,
    'temperature': 0.2,
}
req = urllib.request.Request(
    'https://api.openai.com/v1/chat/completions',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Authorization': f'Bearer {s.api_key}', 'Content-Type': 'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode('utf-8', errors='ignore')
        print('URLOPEN_OK', resp.status, body[:120])
except Exception as e:
    import traceback
    print('URLOPEN_ERR', type(e).__name__, str(e))
    traceback.print_exc()
