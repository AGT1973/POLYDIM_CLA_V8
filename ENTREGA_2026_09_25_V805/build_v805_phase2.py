import os
import subprocess

def main():
    print("Building POLYDIM V805 Phase 2...")
    
    # 1. Compile C++ Modules (IPC, Crypto, Monolith)
    cpp_files = ["src/ipc/polydim_ipc_v805.cpp", "src/ipc/polydim_crypto_v805.cpp", "src/polydim_monolith.cpp"]
    cmd_cpp = [
        r"E:\winlibs_gcc14_zip\mingw64\bin\g++.exe",
        "-shared", "-o", "polydim_cpp_v805.dll",
        "-I", r"E:\POLYDIM_EINSOF\include",
        "-O3", "-march=native", "-fopenmp", 
        "-static-libstdc++", "-static-libgcc"
    ] + cpp_files + ["-lsynchronization", "-lbcrypt"]
    
    print(" ".join(cmd_cpp))
    res = subprocess.run(cmd_cpp, capture_output=True, text=True)
    if res.returncode != 0:
        print("C++ Build Failed:")
        print(res.stderr)
        return
    print("C++ Build OK.")

    # 2. Compile Rust Monolith
    cmd_rust = [
        r"C:\Users\eluithi\.cargo\bin\rustc.exe",
        "--crate-type", "cdylib",
        "-O", "-C", "opt-level=3",
        "-o", "polydim_rust_v805.dll",
        "src/polydim_monolith.rs"
    ]
    print(" ".join(cmd_rust))
    res_rust = subprocess.run(cmd_rust, capture_output=True, text=True)
    if res_rust.returncode != 0:
        print("Rust Build Failed:")
        print(res_rust.stderr)
        return
    print("Rust Build OK.")

if __name__ == '__main__':
    main()
