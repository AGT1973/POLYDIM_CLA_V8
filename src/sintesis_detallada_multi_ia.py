import os

RESP_DIR = r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_28_V812\respuestas'

files = {
    'ChatGPT': 'chatgpt.md',
    'Claude': 'claude.md',
    'DeepSeek': 'deepseek.md',
    'Gemini': 'gemini.md',
    'Kimi': 'kimi.md',
    'Qwen': 'qwen.md'
}

synthesis = {}

for name, fname in files.items():
    fpath = os.path.join(RESP_DIR, fname)
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    critiques = []
    for chunk in content.split('###'):
        if any(w in chunk.upper() for w in ['ERROR', 'CRITIC', 'VULNERABILIDAD', 'BUG', 'PASS 1', 'PASS 2', 'PASS 3']):
            first_line = chunk.strip().splitlines()[0] if chunk.strip().splitlines() else ''
            critiques.append(first_line)
    synthesis[name] = critiques

print('=== MATRIZ DE CRITICAS MULTI-IA REGLA 19 ===\n')
for name, crit_list in synthesis.items():
    print(f'[{name}] Hallazgos clave ({len(crit_list)} secciones):')
    for c in crit_list[:6]:
        print(f'  - {c}')
    print()
