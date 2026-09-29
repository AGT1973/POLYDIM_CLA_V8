import os

files = [
    ("C++ Core (IPC)", "src/ipc/polydim_ipc_v805.cpp"),
    ("C++ Core (Crypto)", "src/ipc/polydim_crypto_v805.cpp"),
    ("C++ Core (Math)", "src/math/polydim_stiefel_v805.cpp"),
    ("C++ Core (Monolith)", "src/polydim_monolith.cpp"),
    ("Rust FFI (Monolith)", "src/polydim_monolith.rs"),
    ("Python (Dispatcher)", "polydim_hw_dispatcher.py"),
    ("Python (Bindings)", "polydim_bindings_v805.py")
]

out_path = os.path.join("auditoria_externa", "V806_CODIGO_FUENTE_CONSOLIDADO.txt")

with open(out_path, "w", encoding="utf-8") as out:
    out.write("=================================================================\n")
    out.write("POLYDIM V806 - KERNEL UNIFICADO PARA TRIBUNAL DE EVALUACIÓN\n")
    out.write("=================================================================\n\n")
    for title, fpath in files:
        out.write(f"\n// =========================================\n")
        out.write(f"// ARCHIVO: {fpath} ({title})\n")
        out.write(f"// =========================================\n")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                out.write(f.read())
        except Exception as e:
            out.write(f"ERROR: {e}\n")
        out.write("\n")
print("Código consolidado.")
