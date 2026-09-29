import json
import urllib.request
import urllib.error

API_KEY = "sk-b14e592652244209ae92132b9c7dfcc5"
URL = "https://api.deepseek.com/chat/completions"

prompt = """You are acting as Red Team Lead for high-dimensional geometric computing (POLYDIM, S^(D-1), PMTP Zero-Copy IPC, C++/Rust).
Do not explain basic concepts. Assume PhD/SOTA engineering level. Be mathematically rigorous.
WARNING: Discard standard coding biases. Do not fall into conventional 1D paradigms. DO NOT hallucinate mathematical proofs. Zero tolerance for unverified code.

Analyze the low-level C++ implementation in V808.1:
1. `pmtp_banked_slot_acquire_writer` and `pmtp_banked_slot_commit_writer` using RCU lock-free bank rotation across 3 memory banks.
2. SPSC Ring Buffer with 128-byte cache-aligned cache line padding (`pad_write`, `pad_read`).

Identify any potential race condition, memory ordering anomaly (e.g. acquire vs release semantics across x86 vs ARM64), or cache false sharing edge cases under high thread contention (N=64 threads). Return concise, cold technical analysis with exact memory barrier requirements."""

payload = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "You are a hostile Red Team concurrency auditor. Attack the design."},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.1
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    URL,
    data=data,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": "POLYDIM-Swarm-Auditor/1.0"
    }
)

try:
    print("Sending direct request to DeepSeek API (api.deepseek.com)...", flush=True)
    with urllib.request.urlopen(req, timeout=45) as resp:
        res_text = resp.read().decode("utf-8")
        res_json = json.loads(res_text)
        content = res_json["choices"][0]["message"]["content"]
        print("\n=== DEEPSEEK DIRECT RED TEAM AUDIT VERDICT ===", flush=True)
        print(content, flush=True)
        with open("E:\\POLYDIM_EINSOF\\ENTREGA_2026_09_26_V808\\dialectic_DeepSeek_direct.md", "w", encoding="utf-8") as f:
            f.write(content)
        print("[SUCCESS] Report saved to dialectic_DeepSeek_direct.md", flush=True)
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} - {e.reason}", flush=True)
    print(e.read().decode("utf-8"), flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
