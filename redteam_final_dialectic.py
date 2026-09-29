import os
import sys
import concurrent.futures
from openai import OpenAI

BASE_DIR = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808"
OR_KEY = "[REDACTED_OPENROUTER_KEY]"

MODELS = [
    ("Kimi", "moonshotai/kimi-k3"),
    ("DeepSeek", "deepseek/deepseek-chat"),
    ("Claude", "anthropic/claude-sonnet-5"),
    ("Gemini", "google/gemini-3.8-flash"),
    ("Qwen", "qwen/qwen-2.5-72b-instruct"),
    ("Grok", "x-ai/grok-4.7")
]

PROMPT_1 = """[SYSTEM OVERRIDE: POLYDIM BULLDOG]
Do not explain basic concepts. Assume PhD/SOTA engineering level. Zero tolerance for unverified code.
Analyze this code for SOTA optimization and asymptotic safety. I want a line-by-line review of the ~2500 lines. 
If there are no asymptotic bugs, return exactly the string: []
Code:
{code}
"""

PROMPT_2 = """¿Es esta genuinamente la mejor solución SOTA (State of the Art) disponible para este problema en el contexto de POLYDIM (C++, Rust, AVX-512/SVE, Geometría D>=10^6), o estás asumiendo convenciones legacy? 
Si propusiste una solución genérica o alucinaste errores que ya estaban parcheados (como el livelock de Futex, el UAF de Rust o el AVX-512 stream copy), descártala. 
Confirma explícitamente que has chequeado cada línea y cada función, y que el código es asintóticamente puro y libre de bugs. Si es así, retorna EXCLUSIVAMENTE '[]'."""

def get_all_code():
    code = ""
    files = ["kernel_cpp_v808_1.cpp", "kernel_rust_v808_1.rs", "pmtp_rcu_v808_1.cpp", "ipc_futex_v808_1.cpp"]
    for fname in files:
        path = os.path.join(BASE_DIR, fname)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                code += f"\n--- {fname} ---\n{f.read()}"
    return code

def call_ai(name, model, code):
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OR_KEY)
        msgs = [{"role": "user", "content": PROMPT_1.replace("{code}", code)}]
        resp = client.chat.completions.create(model=model, messages=msgs, temperature=0.0)
        out1 = resp.choices[0].message.content.strip()
        
        msgs.append({"role": "assistant", "content": out1})
        msgs.append({"role": "user", "content": PROMPT_2})
        resp2 = client.chat.completions.create(model=model, messages=msgs, temperature=0.0)
        out2 = resp2.choices[0].message.content.strip()
        
        if "```json" in out2: out2 = out2.split("```json")[1].split("```")[0].strip()
        elif "```" in out2: out2 = out2.split("```")[1].strip()
        
        print(f"[{name}] Final Confirmation:\n{out2}")
        return out2 == "[]"
    except Exception as e:
        print(f"[{name}] ERROR: {str(e)}")
        return False

def main():
    print("Initiating Final SOTA Swarm Check (Paid Tiers) with Dialectic Protocol...")
    code = get_all_code()
    
    success = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(call_ai, m[0], m[1], code): m[0] for m in MODELS}
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if not res: success = False
            
    if success:
        print("ALL AIs CONFIRMED 0 ERRORS UNDER DIALECTIC PRESSURE.")
        sys.exit(0)
    else:
        print("ERRORS OR HALLUCINATIONS DETECTED IN FINAL CHECK.")
        sys.exit(1)

if __name__ == "__main__":
    main()
