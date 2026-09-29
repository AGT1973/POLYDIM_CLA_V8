import os
import re
import json
from collections import defaultdict

resp_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_27_V810\respuestas"
out_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_27_V810\auditoria_externa"

ai_files = {
    "ChatGPT": "chatgpt.md",
    "Claude": "claude.md",
    "DeepSeek": "deepseek.md",
    "Gemini": "gemini.md",
    "Kimi": "kimi.md",
    "Qwen": "qwen.md",
    "GLM_Z_AI": "z_ai.md"
}

reports = {}
for ai_name, fname in ai_files.items():
    fpath = os.path.join(resp_dir, fname)
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reports[ai_name] = f.read()
    else:
        reports[ai_name] = ""

print(f"Archivos cargados: {len(reports)} IAs")
for name, content in reports.items():
    print(f" - {name:<10}: {len(content):>7} caracteres, {content.count(chr(10)):>5} líneas")

# Categorías de análisis sistemático
categories = {
    "IPC_FUTEX": ["futex", "waitonaddress", "wakebyaddress", "manual-reset", "auto-reset", "event", "livelock", "underflow"],
    "PMTP_RCU": ["rcu", "banked", "writer_active", "owner_pid", "active_bank", "prev_bank", "drain", "lease", "reap", "zombie"],
    "STIEFEL_SOLVER": ["stiefel", "cholqr", "cayley", "smw", "twosum", "dsyrk", "ortho", "tangent", "retraction", "tikhonov"],
    "RUST_BFT_BETTI": ["betti", "dsu", "frechet", "weiszfeld", "quorum", "byzantine", "disjointset", "3a", "tau"],
    "QUANTUM_CLIFFORD": ["clifford", "solovay", "ross-selinger", "gridsynth", "pi/4", "rus", "fidelity", "quantize"],
    "CUDA_AFFOREST": ["afforest", "cuda", "gconn", "dlpack", "cpu_find", "cpu_unite", "openmp", "hardwareprobe"],
    "ABI_FFI_ALIGN": ["abi", "pack", "align", "sizeof", "uaf", "cstring", "thread_local", "catch_unwind", "128", "64"]
}

analysis_matrix = defaultdict(lambda: defaultdict(list))

for ai_name, text in reports.items():
    paras = text.split("\n\n")
    for p in paras:
        p_lower = p.lower()
        for cat, keywords in categories.items():
            matches = [k for k in keywords if k in p_lower]
            if len(matches) >= 2: # Al menos 2 palabras clave coincidentes
                # Limpiar texto
                clean_p = p.strip()
                if len(clean_p) > 100:
                    analysis_matrix[cat][ai_name].append(clean_p)

summary_lines = []
summary_lines.append("# MATRIZ DE INGESTA VECTORIAL Y AUDITORÍA MULTI-IA — POLYDIM V810")
summary_lines.append(f"Ingesta de 7 modelos de frontera: ChatGPT, Claude, DeepSeek, Gemini, Kimi, Qwen, GLM (Z-AI).\n")

for cat, ai_data in analysis_matrix.items():
    summary_lines.append(f"## MÓDULO: {cat}")
    summary_lines.append(f"Total IAs con hallazgos específicos: {len(ai_data)} / 7\n")
    for ai_name, excerpts in ai_data.items():
        summary_lines.append(f"### Hallazgos de {ai_name} ({len(excerpts)} fragmentos analíticos):")
        # Mostrar los 2 fragmentos más relevantes
        for ex in excerpts[:2]:
            first_line = ex.split("\n")[0]
            summary_lines.append(f"- **Extracto:** {first_line[:120]}...")
            # Detectar si propone parche
            if "```" in ex:
                summary_lines.append("  *(Incluye propuesta de código/patch)*")
        summary_lines.append("")
    summary_lines.append("--------------------------------------------------------------------------------\n")

out_summary_path = os.path.join(out_dir, "06_INGESTA_MULTI_IA_ANALISIS_CRUZADO.md")
with open(out_summary_path, "w", encoding="utf-8") as f:
    f.write("\n".join(summary_lines))

print(f"\n✅ Matriz de análisis cruzado guardada en: {out_summary_path}")
