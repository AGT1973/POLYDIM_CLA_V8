import os
import subprocess

def main():
    print("Building POLYDIM V805 Phase 4...")
    
    # 1. Compile C++ Modules
    cpp_files = [
        "src/ipc/polydim_ipc_v805.cpp", 
        "src/ipc/polydim_crypto_v805.cpp", 
        "src/math/polydim_stiefel_v805.cpp", 
        "src/polydim_monolith.cpp"
    ]
    cmd_cpp = [
        r"E:\winlibs_gcc14_zip\mingw64\bin\g++.exe",
        "-shared", "-o", "polydim_cpp_v805.dll",
        "-I", r"E:\POLYDIM_EINSOF\include",
        "-O3", "-march=native", "-fopenmp", 
        "-static-libstdc++", "-static-libgcc"
    ] + cpp_files + ["-lsynchronization", "-lbcrypt"]
    
    res = subprocess.run(cmd_cpp, capture_output=True, text=True)
    if res.returncode != 0:
        print("C++ Build Failed:")
        print(res.stderr)
        return
    print("C++ Build OK.")

if __name__ == '__main__':
    main()
