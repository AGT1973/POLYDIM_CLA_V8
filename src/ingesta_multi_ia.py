import os
import re

RESP_DIR = r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_28_V812\respuestas'

files = [
    'chatgpt.md',
    'claude.md',
    'deepseek.md',
    'gemini.md',
    'kimi.md',
    'qwen.md',
    'z_ai.md'
]

print('=== ANALISIS E INGESTA VECTORIAL MULTI-IA REGLA 19 ===\n')

for fname in files:
    fpath = os.path.join(RESP_DIR, fname)
    if not os.path.exists(fpath):
        print(f'[-] {fname} no encontrado.')
        continue
    
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
        lines = text.splitlines()
        
    print(f'[*] Archivo: {fname} ({len(lines)} lineas, {len(text)} bytes)')
    
    # Extract headings and summary conclusions
    findings = []
    for line in lines:
        if line.startswith('#') or 'ERROR' in line.upper() or 'BUG' in line.upper() or 'VULNERABILIDAD' in line.upper() or 'CRITIC' in line.upper() or 'ASINTOTIC' in line.upper():
            if len(line.strip()) > 5 and len(line.strip()) < 120:
                findings.append(line.strip())
                
    print(f'    -> Encabezados y marcadores clave detectados: {len(findings)}')
    for f_item in findings[:10]:
        print(f'       {f_item}')
    print('--------------------------------------------------\n')
