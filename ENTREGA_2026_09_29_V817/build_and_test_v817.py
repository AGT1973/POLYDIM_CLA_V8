import os
import shutil
import subprocess
import sys

base_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_29_V817"
os.chdir(base_dir)

print(f"=== Compiling POLYDIM V817 Native Kernels in {base_dir} ===")

# 1. Prepare C++ and Rust sources
cpp_txt = os.path.join(base_dir, "kernel_cpp_v817.cpp.txt")
cpp_src = os.path.join(base_dir, "kernel_cpp_v817.cpp")
shutil.copy(cpp_txt, cpp_src)

rust_txt = os.path.join(base_dir, "kernel_rust_v817.rs.txt")
rust_src = os.path.join(base_dir, "kernel_rust_v817.rs")
shutil.copy(rust_txt, rust_src)

# 2. Compile C++ DLL with WinLibs GCC 14
gpp_exe = r"E:\winlibs_gcc14_zip\mingw64\bin\g++.exe"
cpp_dll = os.path.join(base_dir, "polydim_cpp_v817.dll")
cmd_cpp = [gpp_exe, "-shared", "-O3", "-std=c++20", "-fopenmp", "-mavx", "-msse4.2", "-o", cpp_dll, cpp_src]
print("Running C++ compilation:", " ".join(cmd_cpp))
res_cpp = subprocess.run(cmd_cpp, capture_output=True, text=True)
if res_cpp.returncode != 0:
    print("C++ Compilation Error:", res_cpp.stderr)
    sys.exit(1)
print(f"Compiled C++ DLL: {cpp_dll} ({os.path.getsize(cpp_dll)} bytes)")

# 3. Compile Rust DLL with Rustc
rustc_exe = r"C:\Users\eluithi\.cargo\bin\rustc.exe"
rust_dll = os.path.join(base_dir, "polydim_rust_v817.dll")
cmd_rust = [rustc_exe, "--crate-type", "cdylib", "-C", "opt-level=3", "-C", "panic=unwind", "-o", rust_dll, rust_src]
print("Running Rust compilation:", " ".join(cmd_rust))
res_rust = subprocess.run(cmd_rust, capture_output=True, text=True)
if res_rust.returncode != 0:
    print("Rust Compilation Error:", res_rust.stderr)
    sys.exit(1)
print(f"Compiled Rust DLL: {rust_dll} ({os.path.getsize(rust_dll)} bytes)")

# Copy DLLs to auditoria_externa
audit_dir = os.path.join(base_dir, "auditoria_externa")
shutil.copy(cpp_dll, os.path.join(audit_dir, "polydim_cpp_v817.dll"))
shutil.copy(rust_dll, os.path.join(audit_dir, "polydim_rust_v817.dll"))

# 4. Run test suite and capture logs
test_script = os.path.join(audit_dir, "test_v817_comprehensive_suite.py")
log_file = os.path.join(base_dir, "raw_silicon_test_log_v817.txt")

env = os.environ.copy()
env["PYTHONPATH"] = base_dir + os.pathsep + audit_dir + os.pathsep + env.get("PYTHONPATH", "")

print("Running test suite...")
with open(log_file, "w", encoding="utf-8") as lf:
    res_test = subprocess.run([sys.executable, test_script], cwd=audit_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lf.write(res_test.stdout)
    print(res_test.stdout)

print(f"Test Exit Code: {res_test.returncode}")
print(f"Saved Raw Log to: {log_file}")

# 5. Copy everything to E:\POLYDIM-THEORICAL\KERNELS_NATIVOS_Y_LOGS_V817\
theo_dest = r"E:\POLYDIM-THEORICAL\KERNELS_NATIVOS_Y_LOGS_V817"
os.makedirs(theo_dest, exist_ok=True)

files_to_sync = [
    "kernel_cpp_v817.cpp.txt",
    "kernel_rust_v817.rs.txt",
    "polydim_triton_kernel_v817.py",
    "polydim_v817_monolito.py",
    "readme_first.md",
    "raw_silicon_test_log_v817.txt",
    "polydim_cpp_v817.dll",
    "polydim_rust_v817.dll"
]

for fname in files_to_sync:
    src_path = os.path.join(base_dir, fname)
    if os.path.exists(src_path):
        dst_path = os.path.join(theo_dest, fname)
        shutil.copy(src_path, dst_path)
        print(f"Synced to Theory Repo: {fname} ({os.path.getsize(dst_path)} bytes)")

print("\n=== ALL V817 KERNELS AND LOGS SUCCESSFULLY BUILT AND PERSISTED ===")
