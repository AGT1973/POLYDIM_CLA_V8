import urllib.request
import json
url = "https://openrouter.ai/api/v1/models"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    models = json.loads(response.read().decode())['data']
    print("Gemini models:", [m['id'] for m in models if 'gemini' in m['id']])
    print("Claude models:", [m['id'] for m in models if 'claude-3' in m['id']])
