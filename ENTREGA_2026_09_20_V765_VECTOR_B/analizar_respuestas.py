import os
import re
from collections import defaultdict

folder = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V764\respuestas"
files = sorted([f for f in os.listdir(folder) if f.endswith(".md")])

corpus = {}
for f in files:
    path = os.path.join(folder, f)
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        corpus[f] = fp.read()

categories = {
    "PMTP_Triple_Buffer": [r"triple[\s\-_]*buffer", r"SPSC", r"torn\s+read", r"wait[\s\-_]*free", r"atomic<uint8_t>"],
    "Stiefel_Tangente_Cayley": [r"tangent", r"sym\(X\^T\s*G\)", r"G_proj", r"Stiefel", r"Cayley", r"Sherman[\s\-_]*Morrison"],
    "Neumaier_TwoSum_Associativity": [r"Neumaier", r"TwoSum", r"fast[\s\-_]*math", r"reasociaci", r"associative"],
    "FFI_ABI_Alignment": [r"ABI", r"alignas", r"padding", r"ctypes", r"VerifyReport", r"struct\s+align"],
    "Triton_GPU_Kernel": [r"Triton", r"CUDA", r"FP64", r"tl\.dot", r"stream"],
    "Dart_Bridge": [r"Dart", r"calloc", r"NativeHeap", r"lookupFunction"],
    "Rust_CatchUnwind_Invariants": [r"catch_unwind", r"panic", r"Betti", r"Higham", r"is_subnormal"],
    "Aliasing_BadAlloc_Terminate": [r"bad_alloc", r"terminate", r"overlaps", r"aliasing", r"__restrict__"]
}

matrix = defaultdict(dict)
for cat, patterns in categories.items():
    for fname, text in corpus.items():
        hits = 0
        for p in patterns:
            hits += len(re.findall(p, text, re.IGNORECASE))
        matrix[cat][fname] = hits

labels = [f.replace(".md", "") for f in files]
col_w = 32
hdr = "Categoria".ljust(col_w) + " | " + " | ".join([l.rjust(10) for l in labels])
print("=== MATRIZ DE CONSENSO MULTI-IA (8 MODELOS / 821 KB) ===\n")
print(hdr)
print("-" * len(hdr))
for cat, counts in matrix.items():
    row = cat.ljust(col_w) + " | " + " | ".join([str(counts.get(f, 0)).rjust(10) for f in files])
    print(row)
