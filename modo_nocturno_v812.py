import asyncio
import aiohttp
import os

FILES = [
    'E:/POLYDIM_EINSOF/src/kernel_cpp_v810.cpp',
    'E:/POLYDIM_EINSOF/src/kernel_rust_v811.rs',
    'E:/POLYDIM_EINSOF/src/ipc_futex_v811.cpp',
    'E:/POLYDIM_EINSOF/src/pmtp_rcu_v810.cpp',
    'E:/POLYDIM_EINSOF/src/polydim_solver_abi_v808_1.h',
    'E:/POLYDIM_EINSOF/src/test_v811_ipc_suite.py'
]
REPORT_PATH = 'E:/POLYDIM_EINSOF/ENTREGA_2026_09_27_V811/REPORTE_SOTA_NOCTURNO.md'
OR_KEY = '[REDACTED_OPENROUTER_KEY]'
GEM_KEY = '[REDACTED_GEMINI_KEY]'

def get_code_chunks():
    chunks = []
    current_chunk = ''
    for f in FILES:
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
            if len(current_chunk) + len(content) > 25000:
                chunks.append(current_chunk)
                current_chunk = ''
            current_chunk += f'\n--- {os.path.basename(f)} ---\n{content}\n'
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

async def call_openrouter(session, model_name, model_id, chunks):
    headers = {'Authorization': f'Bearer {OR_KEY}', 'Content-Type': 'application/json'}
    full_resp = []
    for i, chunk in enumerate(chunks):
        prompt = f'[BULLDOG RED TEAM] Analiza linea a linea este chunk {i+1}/{len(chunks)} buscando errores asintoticos, NaN, deadlocks. RESTRICCIONES: Devuelve confirmacion de revision.\n\n{chunk}'
        payload = {'model': model_id, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 2000}
        try:
            async with session.post('https://openrouter.ai/api/v1/chat/completions', headers=headers, json=payload, timeout=600) as resp:
                data = await resp.json()
                if 'choices' in data:
                    full_resp.append(data['choices'][0]['message']['content'])
                else:
                    full_resp.append(f'Error chunk {i+1}: {str(data)}')
        except Exception as e:
            full_resp.append(f'Network error chunk {i+1}: {e}')
        await asyncio.sleep(2)
    return '\n\n'.join(full_resp)

async def call_gemini(session, chunks):
    full_resp = []
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEM_KEY}'
    for i, chunk in enumerate(chunks):
        prompt = f'[BULLDOG RED TEAM] Analiza linea a linea este chunk {i+1}/{len(chunks)} buscando errores asintoticos, NaN, deadlocks. RESTRICCIONES: Devuelve confirmacion de revision.\n\n{chunk}'
        payload = {'contents': [{'parts':[{'text': prompt}]}]}
        try:
            async with session.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=600) as resp:
                data = await resp.json()
                if 'candidates' in data:
                    full_resp.append(data['candidates'][0]['content']['parts'][0]['text'])
                else:
                    full_resp.append(f'Error chunk {i+1}: {str(data)}')
        except Exception as e:
            full_resp.append(f'Network error chunk {i+1}: {e}')
        await asyncio.sleep(2)
    return '\n\n'.join(full_resp)

async def main():
    chunks = get_code_chunks()
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write('# POLYDIM TRIBUNAL DE ENJAMBRE - REPORTE NOCTURNO V812\n\n')
    async with aiohttp.ClientSession() as session:
        tasks = [
            ('DeepSeek', call_openrouter(session, 'DeepSeek', 'deepseek/deepseek-chat', chunks)),
            ('Qwen 72B', call_openrouter(session, 'Qwen', 'qwen/qwen-2.5-72b-instruct', chunks)),
            ('GPT-4o-Mini', call_openrouter(session, 'GPT-4o-Mini', 'openai/gpt-4o-mini', chunks)),
            ('Gemini', call_gemini(session, chunks))
        ]
        for name, task in tasks:
            result = await task
            with open(REPORT_PATH, 'a', encoding='utf-8') as f:
                f.write(f'## REPORTE DE {name}\n\n{result}\n\n---\n\n')

if __name__ == '__main__':
    asyncio.run(main())
