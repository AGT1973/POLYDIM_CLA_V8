import os

files_to_pack = [
    "src/ipc/polydim_ipc_v805.cpp",
    "src/ipc/polydim_crypto_v805.cpp",
    "src/math/polydim_stiefel_v805.cpp",
    "src/polydim_monolith.rs",
    "polydim_hw_dispatcher.py",
    "polydim_bindings_v805.py"
]

with open("v805_full_prompt.txt", "w", encoding="utf-8") as out:
    out.write("CONTEXT: POLYDIM V805 ARCHITECTURE FULL SOURCE CODE\n")
    out.write("TASK: Perform a ruthless Red Team adversarial audit on this codebase. Check for IPC deadlocks, memory safety, numeric drift, and cryptography flaws.\n\n")
    for fpath in files_to_pack:
        out.write(f"--- FILE: {fpath} ---\n")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                out.write(f.read())
        except Exception as e:
            out.write(f"ERROR READING FILE: {e}\n")
        out.write("\n\n")
print("v805_full_prompt.txt created.")
