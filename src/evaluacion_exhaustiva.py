import os

RESP_DIR = r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_28_V812\respuestas'
files = ['chatgpt.md', 'claude.md', 'deepseek.md', 'gemini.md', 'kimi.md', 'qwen.md', 'z_ai.md']

print('=== EXTRACCION Y EVALUACION EXHAUSTIVA DE PROPUESTAS ===\n')

for f in files:
    path = os.path.join(RESP_DIR, f)
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
        lines = file.readlines()
    
    print(f'>>> ANALISIS DETALLADO: {f} ({len(lines)} lineas)')
    
    current_section = ''
    proposals = []
    for line in lines:
        if line.startswith('#'):
            current_section = line.strip()
        if '```' in line or 'Fix' in line or 'Sugerencia' in line or 'Reemplazar' in line:
            if current_section and current_section not in proposals:
                proposals.append(current_section)
                
    for p in proposals[:8]:
        print(f'    [Propuesta/Seccion] {p}')
    print('--------------------------------------------------')
