import os
import re

respuestas_dir = r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\respuestas'

files = {
    'DeepSeek': os.path.join(respuestas_dir, 'deepseek.md'),
    'Gemini': os.path.join(respuestas_dir, 'gemini.md'),
    'Qwen': os.path.join(respuestas_dir, 'qwen.md'),
    'Z_ai': os.path.join(respuestas_dir, 'z_ai.md'),
    'Kimi': os.path.join(respuestas_dir, 'kimi', 'kimi.md'),
}

for name, path in files.items():
    if os.path.exists(path):
        print(f'=== {name} (Tamaño: {os.path.getsize(path)} bytes) ===')
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            head = ''.join(lines[:25])
            print(head)
            print('-----------------------------------------')
