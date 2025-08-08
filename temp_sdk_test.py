import json, sys
from openai import OpenAI
key = open('.env','r',encoding='utf-8',errors='ignore').read().split('OPENAI_API_KEY=',1)[1].splitlines()[0].strip()
client = OpenAI(api_key=key)
try:
    resp = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role':'user','content':'Say hi in one word.'}],
        temperature=0.2,
        max_tokens=10,
    )
    print('OK', json.dumps({'id':resp.id,'model':resp.model,'len':len(resp.choices)}))
except Exception as e:
    print('ERR', type(e).__name__, getattr(e,'status_code',None), getattr(e,'code',None), str(e))
