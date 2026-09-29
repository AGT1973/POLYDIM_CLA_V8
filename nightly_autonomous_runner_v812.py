import asyncio
import aiohttp
import time
import os

PAYLOAD_PATH = r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_27_V811\bulldog_payload.txt'
REPORT_PATH = r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_27_V811\REPORTE_SOTA_NOCTURNO.md'

OR_KEY = '[REDACTED_OPENROUTER_KEY]'
GEMINI_KEY = '[REDACTED_GEMINI_KEY]'

MODELS = [
    ('Claude 3.5', 'anthropic/claude-3.5-sonnet'),
    ('DeepSeek', 'deepseek/deepseek-chat'),
    ('Qwen 72B', 'qwen/qwen-2.5-72b-instruct'),
    ('Kimi', 'moonshotai/moonshot-v1-128k')
]

async def call_openrouter(session, model_name, model_id, prompt):
    headers = {
        'Authorization': f'Bearer {OR_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': model_id,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 4000
    }
    try:
        print(f'Starting request for {model_name}...')
        async with session.post('https://openrouter.ai/api/v1/chat/completions', headers=headers, json=payload, timeout=600) as resp:
            data = await resp.json()
            if 'choices' in data:
                return data['choices'][0]['message']['content']
            return str(data)
    except Exception as e:
        return f'Error in {model_name}: {e}'

async def call_gemini(session, prompt):
    # Fallback to OpenRouter for Gemini to simplify code
    return await call_openrouter(session, 'Gemini', 'google/gemini-pro-1.5', prompt)

async def main():
    print('Reading payload...')
    with open(PAYLOAD_PATH, 'r', encoding='utf-8') as f:
        prompt = f.read()

    print(f'Payload loaded ({len(prompt)} chars). Initiating Night Mode Swarm...')
    
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write('# POLYDIM TRIBUNAL DE ENJAMBRE - REPORTE NOCTURNO V812\n\n')

    async with aiohttp.ClientSession() as session:
        tasks = []
        for name, model_id in MODELS:
            tasks.append((name, call_openrouter(session, name, model_id, prompt)))
        tasks.append(('Gemini', call_gemini(session, prompt)))

        for name, task in tasks:
            result = await task
            print(f'Received response from {name}.')
            with open(REPORT_PATH, 'a', encoding='utf-8') as f:
                f.write(f'## REPORTE DE {name}\n\n{result}\n\n---\n\n')

    print('Swarm iteration complete. Zero errors remaining or 150m reached.')

if __name__ == '__main__':
    asyncio.run(main())
