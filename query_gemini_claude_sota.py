import json, urllib.request, os

print("================================================================================")
print("     CONSULTANDO A GEMINI Y CLAUDE CON EL POOL DE CLAVES REGISTRADAS            ")
print("================================================================================")

prompt_sota = """[POLYDIM V753 - DEMAND FOR 10 SOTA ARCHITECTURAL ENHANCEMENTS]
We operate on high-dimensional unit sphere S^{D-1} (D >= 10^7), closed-form Rodrigues Rank-2 geodesic rotations, PMTP Zero-Copy IPC via SEQLock, Neumaier TwoSum compensated arithmetic, and Riemannian Adam with Parallel Transport.

Provide EXACTLY 10 breakthrough SOTA (2025-2026) algorithms, mathematical formulations, or silicon hardware techniques to take POLYDIM to absolute theoretical and industrial maximum:
1. Clifford / Multivector Rotors vs SIMD
2. Fast Randomized Orthonormalization (FWHT + CholQR vs Householder)
3. Sub-microsecond Multi-Node RDMA Wire Protocols
4. Lossless Tangent-Bundle Projection for LLMs (Llama-3/Qwen)
5. Triton / CUDA Error-Free Transformation on Tensor Cores
6. Multi-Agent Shared-Memory Cache Pinning and NUMA Affinity
7. Non-Abelian Gauge Invariance in High Dimension
8. Quantum Unitary Mapping of Rodrigues Rotations
9. Topological Betti-1 Invariant Verification in Hardware
10. Hardware-Aware Pipeline for Cerebras WSE / TPU v3 / NVIDIA H100
"""

# Pool de claves
with open(r"C:\Users\eluithi\.gemini\config\api_keys_pool.json", "r") as f:
    pool = json.load(f)

claude_keys = pool.get("claude_keys", [])
aistudio_keys = pool.get("aistudio_keys", [])

results = {}

# --- A. PROBANDO GEMINI (Google AI Studio) ---
print("\n--- 1. PROBANDO GEMINI 2.5 PRO / FLASH ---")
gemini_models = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]

for key in aistudio_keys:
    for model in gemini_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt_sota}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
        }).encode('utf-8')
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                results["gemini"] = text
                print(f"[OK] Gemini ({model}) respondio exitosamente!")
                break
        except Exception as e:
            # print(f"Gemini {model} error: {e}")
            pass
    if "gemini" in results:
        break

# --- B. PROBANDO CLAUDE ---
print("\n--- 2. PROBANDO CLAUDE 3.5 SONNET / HAIKU ---")
claude_models = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-haiku-20240307"]

for key in claude_keys:
    for model in claude_models:
        payload = json.dumps({
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt_sota}]
        }).encode('utf-8')
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                text = data["content"][0]["text"]
                results["claude"] = text
                print(f"[OK] Claude ({model}) respondio exitosamente!")
                break
        except Exception as e:
            # print(f"Claude {model} error: {e}")
            pass
    if "claude" in results:
        break

# Guardar
out_p = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_18_V753\tribunal_gemini_claude_10_sota.json"
with open(out_p, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\nModelos que respondieron con exito:", list(results.keys()))
print("Guardado en:", out_p)
