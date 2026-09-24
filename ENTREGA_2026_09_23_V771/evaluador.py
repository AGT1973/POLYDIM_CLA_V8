import urllib.request
import json
import os

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
URL = "https://openrouter.ai/api/v1/chat/completions"

try:
    with open("ingesta_bruta.md", "r", encoding="utf-8") as f:
        content = f.read()
except FileNotFoundError:
    print("ingesta_bruta.md no encontrado.")
    exit(1)

prompt = """
ACTÚA COMO ORQUESTADOR RED TEAM (BULLDOG CRITIC) DE POLYDIM.
Aquí tienes la INGESTA BRUTA de 5 IA diferentes evaluando la versión V771 de la arquitectura matemática y el código FFI/C++/Rust.

TU MISIÓN:
1. Consolidar toda la información.
2. Identificar y deduplicar las vulnerabilidades (P0, P1, P2) y propuestas SOTA encontradas por las 5 IAs.
3. Detectar activamente y purgar "alucinaciones" (soluciones que violen las aserciones matemáticas de POLYDIM, como romper S^(D-1), colapsos 1D, o bloqueos del GIL).
4. Generar un VECTOR DE INGESTA EVALUADA estructurado, conciso y directo (Cero adulaciones, lenguaje técnico y asintótico).

ENTREGA en Markdown:
- Top P0s (Críticos: Cayley-SMW, Rodrigues, Deriva Topológica)
- Top P1s (Concurrencia, ABA, Memoria, FFI)
- Mejoras SOTA validadas.
"""

payload = {
    "model": "google/gemini-2.5-pro",
    "messages": [
        {"role": "system", "content": "You are Antigravity Bulldog Red Team Orchestrator. Output in Spanish."},
        {"role": "user", "content": prompt + "\n\nCONTENIDO:\n" + content}
    ],
    "temperature": 0.1
}

headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json',
    'HTTP-Referer': 'https://polydim.org',
    'X-Title': 'POLYDIM'
}

req = urllib.request.Request(URL, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')

try:
    print("Iniciando vectorización con OpenRouter...")
    with urllib.request.urlopen(req) as response:
        resp_body = response.read().decode('utf-8')
        res_data = json.loads(resp_body)
        if 'choices' not in res_data:
            print("Error from OpenRouter:", resp_body)
        else:
            eval_text = res_data['choices'][0]['message']['content']
            with open("VECTOR_INGESTA_EVALUADA_V771.md", "w", encoding="utf-8") as out_f:
                out_f.write(eval_text)
            print("Vectorización evaluada exitosamente en VECTOR_INGESTA_EVALUADA_V771.md")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
except Exception as e:
    print("Error llamando a OpenRouter API:", str(e))
