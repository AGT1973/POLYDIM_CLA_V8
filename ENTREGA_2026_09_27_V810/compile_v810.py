import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

gxx_path = r"E:\winlibs_gcc14_zip\mingw64\bin\g++.exe"
rustc_path = r"C:\Users\eluithi\.cargo\bin\rustc.exe"

print("=================================================================")
print("🔨 COMPILACIÓN CRUZADA POLYDIM V810 (GCC 14 + RUSTC + CUDA)")
print("=================================================================")

# 1. C++ Kernel
print("\n[1/3] Compilando C++ polydim_cpp_v810.dll...")
cpp_files = ["kernel_cpp_v810.cpp", "pmtp_rcu_v810.cpp", "ipc_futex_v810.cpp"]
cmd_cpp = [
    gxx_path, "-shared", "-o", "polydim_cpp_v810.dll",
    "-I.", "-Iinclude", "-I", r"E:\POLYDIM_EINSOF\include",
    "-O3", "-march=native", "-fopenmp",
    "-static-libstdc++", "-static-libgcc"
] + cpp_files + ["-lsynchronization", "-lbcrypt"]

res_cpp = subprocess.run(cmd_cpp, capture_output=True, text=True)
if res_cpp.returncode != 0:
    print("❌ C++ Build Failed:")
    print(res_cpp.stderr)
    sys.exit(1)
print("✅ C++ Build OK -> polydim_cpp_v810.dll generado con éxito.")

# 2. Rust Kernel
print("\n[2/3] Compilando Rust polydim_rust_v810.dll...")
cmd_rust = [
    rustc_path, "--crate-type", "cdylib",
    "-O", "-C", "opt-level=3",
    "-o", "polydim_rust_v810.dll",
    "kernel_rust_v810.rs"
]
res_rust = subprocess.run(cmd_rust, capture_output=True, text=True)
if res_rust.returncode != 0:
    print("❌ Rust Build Failed:")
    print(res_rust.stderr)
    sys.exit(1)
print("✅ Rust Build OK -> polydim_rust_v810.dll generado con éxito.")

# 3. GPU / Afforest graph_cuda.dll
print("\n[3/3] Compilando graph_cuda.dll (Afforest / GConn + DLPack)...")
cmd_cuda = [
    gxx_path, "-shared", "-o", "graph_cuda.dll",
    "-I.",
    "-O3", "-march=native", "-fopenmp",
    "-static-libstdc++", "-static-libgcc",
    "graph_cuda.cpp"
]
res_cuda = subprocess.run(cmd_cuda, capture_output=True, text=True)
if res_cuda.returncode != 0:
    print("❌ graph_cuda Build Failed:")
    print(res_cuda.stderr)
    sys.exit(1)
print("✅ graph_cuda Build OK -> graph_cuda.dll generado con éxito.")

print("\n=================================================================")
print("🎉 COMPILACIÓN COMPLETADA EXITOSAMENTE (EXIT CODE 0)")
print("=================================================================")
