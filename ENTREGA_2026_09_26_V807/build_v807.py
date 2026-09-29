import os
import sys
import subprocess

def main():
    print("=================================================")
    print("🔨 Compilando POLYDIM V807 Definitiva...")
    print("=================================================")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    # 1. Compile C++ Modules
    cpp_files = [
        "src/ipc/polydim_ipc_v805.cpp", 
        "src/ipc/polydim_crypto_v805.cpp", 
        "src/math/polydim_stiefel_v805.cpp", 
        "src/polydim_monolith.cpp"
    ]
    
    gxx_path = r"E:\winlibs_gcc14_zip\mingw64\bin\g++.exe"
    cmd_cpp = [
        gxx_path,
        "-shared", "-o", "polydim_cpp_v807.dll",
        "-I", "include",
        "-I", r"E:\POLYDIM_EINSOF\include",
        "-O3", "-march=native", "-fopenmp", 
        "-static-libstdc++", "-static-libgcc"
    ] + cpp_files + ["-lsynchronization", "-lbcrypt"]
    
    print("Ejecutando compilación C++:")
    print(" ".join(cmd_cpp))
    res_cpp = subprocess.run(cmd_cpp, capture_output=True, text=True)
    if res_cpp.returncode != 0:
        print("❌ C++ Build Failed:")
        print(res_cpp.stderr)
        sys.exit(1)
    print("✅ C++ Build OK -> polydim_cpp_v807.dll generado con éxito.")

    # 2. Compile Rust Monolith
    rustc_path = r"C:\Users\eluithi\.cargo\bin\rustc.exe"
    cmd_rust = [
        rustc_path,
        "--crate-type", "cdylib",
        "-O", "-C", "opt-level=3",
        "-o", "polydim_rust_v807.dll",
        "src/polydim_monolith.rs"
    ]
    print("\nEjecutando compilación Rust:")
    print(" ".join(cmd_rust))
    res_rust = subprocess.run(cmd_rust, capture_output=True, text=True)
    if res_rust.returncode != 0:
        print("❌ Rust Build Failed:")
        print(res_rust.stderr)
        sys.exit(1)
    print("✅ Rust Build OK -> polydim_rust_v807.dll generado con éxito.")

    print("\n=================================================")
    print("🎉 COMPILACIÓN V807 COMPLETADA EXITOSAMENTE")
    print("=================================================")

if __name__ == '__main__':
    main()
