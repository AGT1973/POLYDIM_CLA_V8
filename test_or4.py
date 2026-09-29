import urllib.request
import json
url = "https://openrouter.ai/api/v1/models"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    models = json.loads(response.read().decode())['data']
    print("xAI models:", [m['id'] for m in models if 'x-ai' in m['id']])
    print("Moonshot models:", [m['id'] for m in models if 'moonshot' in m['id']])
