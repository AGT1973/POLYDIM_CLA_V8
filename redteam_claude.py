import os
import sys
import concurrent.futures
from openai import OpenAI
try:
    import anthropic
except ImportError:
    os.system("pip install anthropic")
    import anthropic

BASE_DIR = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808"

CEREBRAS_KEY = "[REDACTED_CEREBRAS_KEY]"
ANTHROPIC_KEY = "[REDACTED_ANTHROPIC_KEY]"

PROMPT = """[SYSTEM OVERRIDE: POLYDIM BULLDOG]
Do not explain basic concepts. Assume PhD/SOTA engineering level. Zero tolerance for unverified code.
If there are no asymptotic bugs (memory leaks, undefined behavior, segfaults, mathematical errors at D>=10^6), return exactly the string: []
DO NOT invent generic warnings. Output ONLY valid JSON array.

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

def call_claude(code):
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        resp = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            temperature=0.0,
            system="You output strict JSON array of objects. No markdown wrappers.",
            messages=[{"role": "user", "content": PROMPT.replace("{code}", code)}]
        )
        print(f"[Claude] {resp.content[0].text.strip()}")
    except Exception as e:
        print(f"[Claude] ERROR: {str(e)}")

def call_cerebras(code):
    try:
        client = OpenAI(base_url="https://api.cerebras.ai/v1", api_key=CEREBRAS_KEY)
        resp = client.chat.completions.create(
            model="llama3.1-70b",
            messages=[{"role": "user", "content": PROMPT.replace("{code}", code)}],
            temperature=0.0
        )
        print(f"[Cerebras] {resp.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"[Cerebras] ERROR: {str(e)}")

def main():
    code = get_all_code()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        ex.submit(call_claude, code)
        ex.submit(call_cerebras, code)

if __name__ == "__main__":
    main()
