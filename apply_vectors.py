import os
import re

BASE_DIR = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808"

# 1. kernel_cpp_v808_1.cpp: Fix _mm_sfence() and alignment check
cpp_file = os.path.join(BASE_DIR, "kernel_cpp_v808_1.cpp")
with open(cpp_file, "r", encoding="utf-8") as f:
    cpp_code = f.read()

# Replace _mm_sfence() with portable atomic fence
cpp_code = cpp_code.replace("#include <xmmintrin.h>", "#include <atomic>")
cpp_code = cpp_code.replace("_mm_sfence();", "std::atomic_thread_fence(std::memory_order_seq_cst);")

# 2. pmtp_rcu_v808_1.cpp: write_bank bounds check
rcu_file = os.path.join(BASE_DIR, "pmtp_rcu_v808_1.cpp")
with open(rcu_file, "r", encoding="utf-8") as f:
    rcu_code = f.read()

if "if (write_bank >= 3) return;" not in rcu_code:
    rcu_code = rcu_code.replace("void pmtp_banked_slot_commit_writer(uint8_t write_bank) {", "void pmtp_banked_slot_commit_writer(uint8_t write_bank) {\n    if (write_bank >= 3) return; // RED TEAM FIX: Bounds check")

with open(cpp_file, "w", encoding="utf-8") as f:
    f.write(cpp_code)

with open(rcu_file, "w", encoding="utf-8") as f:
    f.write(rcu_code)

# 3. Rust slice bounds / zero edge check
rust_file = os.path.join(BASE_DIR, "kernel_rust_v808_1.rs")
with open(rust_file, "r", encoding="utf-8") as f:
    rust_code = f.read()

if "if num_edges == 0 { return 0.0; }" not in rust_code:
    rust_code = rust_code.replace("pub unsafe extern \"C\" fn polydim_rust_betti_dual_guard", "pub unsafe extern \"C\" fn polydim_rust_betti_dual_guard")
    # Actually just add it after the signature
    rust_code = re.sub(r'(pub unsafe extern "C" fn polydim_rust_betti_dual_guard[^\{]*\{)', r'\1\n    if num_edges == 0 { return 0.0; } // RED TEAM FIX: Zero slice protection', rust_code)

with open(rust_file, "w", encoding="utf-8") as f:
    f.write(rust_code)

print("Vectors applied.")
