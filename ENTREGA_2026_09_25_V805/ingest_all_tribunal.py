import os

respuestas_dir = r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\respuestas'
out_master_raw = os.path.join(respuestas_dir, 'INGESTA_TRIBUNAL_COMPLETO_V807_RAW.md')

sources = [
    ('CLAUDE', os.path.join(respuestas_dir, 'Claude')),
    ('CHATGPT', os.path.join(respuestas_dir, 'chatgpt')),
    ('KIMI', os.path.join(respuestas_dir, 'kimi')),
    ('DEEPSEEK', os.path.join(respuestas_dir, 'deepseek.md')),
    ('GEMINI', os.path.join(respuestas_dir, 'gemini.md')),
    ('QWEN', os.path.join(respuestas_dir, 'qwen.md')),
    ('Z_AI', os.path.join(respuestas_dir, 'z_ai.md'))
]

with open(out_master_raw, 'w', encoding='utf-8') as out:
    out.write('# INGESTA BRUTA CONSOLIDADA DEL TRIBUNAL MULTI-AI (V807 FASE 0)\n\n')
    out.write('Consolidación absoluta de 7 fuentes (Claude, ChatGPT, Kimi, DeepSeek, Gemini, Qwen, Z.ai) bajo la Regla 19.\n\n')
    
    for name, path in sources:
        out.write(f'\n\n=================================================================\n')
        out.write(f'# FUENTE: {name}\n')
        out.write(f'=================================================================\n\n')
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    out.write(f.read())
            except Exception as e:
                out.write(f'ERROR LEYENDO {name}: {e}\n')
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, respuestas_dir)
                    out.write(f'\n\n--- ARCHIVO: {rel} ---\n\n')
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                            out.write(f.read())
                    except Exception as e:
                        out.write(f'ERROR: {e}\n')

print('Master Raw generado:', out_master_raw, 'Tamaño:', os.path.getsize(out_master_raw))
