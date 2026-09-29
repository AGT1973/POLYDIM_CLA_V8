import os

base_dir = r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\respuestas'
chatgpt_dir = os.path.join(base_dir, 'chatgpt')
kimi_dir = os.path.join(base_dir, 'kimi')

out_raw = os.path.join(base_dir, 'INGESTA_MULTIAI_V807_BRUTA.md')

def dump_dir(path, out):
    for root, dirs, files in os.walk(path):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, base_dir)
            out.write(f'\n\n---\n## ARCHIVO: {rel_path}\n---\n\n')
            try:
                # Limit binary or huge files if any
                with open(full_path, 'r', encoding='utf-8', errors='replace') as r:
                    content = r.read()
                    out.write(content)
            except Exception as e:
                out.write(f'ERROR: {e}\n')

with open(out_raw, 'w', encoding='utf-8') as out:
    out.write('# INGESTA MULTI-AI BRUTA CONSOLIDADA (CLAUDE + CHATGPT + KIMI) - V807\n\n')
    out.write('Consolidación completa sin pérdidas bajo la Regla 19 (Fase 0).\n\n')
    out.write('## SECCIÓN 1: RESPUESTAS CHATGPT\n')
    dump_dir(chatgpt_dir, out)
    out.write('\n\n## SECCIÓN 2: RESPUESTAS KIMI\n')
    dump_dir(kimi_dir, out)

print('Ingesta bruta ChatGPT + Kimi completada:', out_raw, 'Tamaño:', os.path.getsize(out_raw))
