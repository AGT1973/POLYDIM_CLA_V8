import urllib.request
import json

# Cerebras models
url = "https://api.cerebras.ai/v1/models"
req = urllib.request.Request(url, headers={"Authorization": "Bearer [REDACTED_CEREBRAS_KEY]"})
try:
    with urllib.request.urlopen(req) as response:
        models = json.loads(response.read().decode())
        print("Cerebras models:", [m['id'] for m in models['data']])
except Exception as e:
    print("Cerebras ERROR:", e)

# Gemini API test
import urllib.parse
gemini_key = "[REDACTED_GEMINI_KEY]"
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={gemini_key}"
req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"})
data = json.dumps({
    "contents": [{"parts": [{"text": "Reply exactly: []"}]}],
    "generationConfig": {"temperature": 0.0}
})
try:
    with urllib.request.urlopen(req, data=data.encode("utf-8")) as response:
        print("Gemini:", json.loads(response.read().decode())["candidates"][0]["content"]["parts"][0]["text"])
except Exception as e:
    print("Gemini ERROR:", e)

# Anthropic API test
url = "https://api.anthropic.com/v1/messages"
headers = {
    "x-api-key": "[REDACTED_ANTHROPIC_KEY]",
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
}
data = json.dumps({
    "model": "claude-3-5-sonnet-20240620",
    "max_tokens": 100,
    "temperature": 0.0,
    "system": "You output JSON",
    "messages": [{"role": "user", "content": "Reply exactly: []"}]
})
req = urllib.request.Request(url, method="POST", headers=headers, data=data.encode("utf-8"))
try:
    with urllib.request.urlopen(req) as response:
        print("Claude:", json.loads(response.read().decode())["content"][0]["text"])
except Exception as e:
    print("Claude ERROR:", e)

