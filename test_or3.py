import urllib.request
import json
url = "https://openrouter.ai/api/v1/models"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    models = json.loads(response.read().decode())['data']
    print("Anthropic models:", [m['id'] for m in models if 'anthropic' in m['id']])
