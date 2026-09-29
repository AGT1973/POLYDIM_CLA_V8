import os
import sys
import concurrent.futures
from openai import OpenAI

BASE_DIR = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808"
OR_KEY = "[REDACTED_OPENROUTER_KEY]"

MODELS = [
    ("DeepSeek", "deepseek/deepseek-chat"),
    ("Qwen", "qwen/qwen-2.5-72b-instruct"),
    ("Claude_Sonnet_5", "anthropic/claude-sonnet-5")
]

PROMPT_1 = """[SYSTEM OVERRIDE: POLYDIM BULLDOG]
Do not explain basic concepts. Assume PhD/SOTA engineering level. Zero tolerance for unverified code.
Analyze this code for SOTA optimization and asymptotic safety. If no errors, output []. 
Code:
{code}
"""

PROMPT_SOTA_CHALLENGE = """¿Es esta genuinamente la mejor solución SOTA (State of the Art) disponible para este problema en el contexto de POLYDIM (C++, Rust, AVX-512/SVE, Geometría D>=10^6), o estás asumiendo convenciones legacy? 
Si propusiste una solución genérica, descártala. Dame la verdad técnica más agresiva y optimizada posible, operando al límite del silicio (cache-lines, false sharing, SIMD, lock-free RCU). Si tu código anterior tenía alucinaciones matemáticas, retráctate ahora mismo."""

def get_all_code():
    code = ""
    files = ["kernel_cpp_v808_1.cpp", "kernel_rust_v808_1.rs", "pmtp_rcu_v808_1.cpp", "ipc_futex_v808_1.cpp"]
    for fname in files:
        path = os.path.join(BASE_DIR, fname)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                code += f"\n--- {fname} ---\n{f.read()}"
    return code

def call_ai_dialectic(name, model, code):
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OR_KEY)
        
        # Turn 1
        msgs = [{"role": "user", "content": PROMPT_1.replace("{code}", code)}]
        resp1 = client.chat.completions.create(model=model, messages=msgs, temperature=0.0)
        out1 = resp1.choices[0].message.content.strip()
        
        # Turn 2: SOTA Challenge
        msgs.append({"role": "assistant", "content": out1})
        msgs.append({"role": "user", "content": PROMPT_SOTA_CHALLENGE})
        
        resp2 = client.chat.completions.create(model=model, messages=msgs, temperature=0.0)
        out2 = resp2.choices[0].message.content.strip()
        
        out_path = os.path.join(BASE_DIR, f"dialectic_{name}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# {name} - Turn 1\n{out1}\n\n# {name} - Turn 2 (SOTA Challenge)\n{out2}")
            
        print(f"[{name}] Dialectic completed.")
    except Exception as e:
        print(f"[{name}] ERROR: {str(e)}")

def main():
    print("Initiating SOTA Dialectic Challenge...")
    code = get_all_code()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(call_ai_dialectic, m[0], m[1], code) for m in MODELS]
        concurrent.futures.wait(futs)
        
    print("Dialectic complete. Files written.")

if __name__ == "__main__":
    main()
