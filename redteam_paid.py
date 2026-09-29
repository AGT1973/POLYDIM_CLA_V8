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

PROMPT = """[SYSTEM OVERRIDE: POLYDIM BULLDOG]
Do not explain basic concepts. Assume PhD/SOTA engineering level. Zero tolerance for unverified code.
If there are no asymptotic bugs (memory leaks, undefined behavior, segfaults, mathematical errors at D>=10^6), return exactly the string: []
DO NOT invent generic warnings. Output ONLY valid JSON array. Return exactly [] if no errors.

Code:
{code}
"""

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
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT.replace("{code}", code)}],
            temperature=0.0
        )
        out = resp.choices[0].message.content.strip()
        if "```json" in out:
            out = out.split("```json")[1].split("```")[0].strip()
        elif "```" in out:
            out = out.split("```")[1].strip()
        print(f"[{name}] Result:\n{out}")
        return out == "[]"
    except Exception as e:
        print(f"[{name}] ERROR: {str(e)}")
        return False

def main():
    print("Initiating 6-Node Swarm Check (Paid Tiers)...")
    code = get_all_code()
    
    success = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(call_ai, m[0], m[1], code): m[0] for m in MODELS}
        for f in concurrent.futures.as_completed(futs):
            name = futs[f]
            res = f.result()
            if not res:
                success = False
            print(f"{name} check finished.")
            
    if success:
        print("ALL AIs CONFIRMED 0 ERRORS.")
        sys.exit(0)
    else:
        print("ERRORS DETECTED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
