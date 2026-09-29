import urllib.request
import json
url = "https://openrouter.ai/api/v1/models"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    models = json.loads(response.read().decode())['data']
    print("Cerebras / Llama models:", [m['id'] for m in models if 'llama-3.1' in m['id'].lower() or 'llama3.1' in m['id'].lower() or 'cerebras' in m['id'].lower()])
