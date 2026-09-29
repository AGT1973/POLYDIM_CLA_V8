import os
import shutil

src_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC"
dest_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\auditoria_externa\archivos_fuente"

# Create destination dir
os.makedirs(dest_dir, exist_ok=True)

# Files from V805 to copy
files_to_copy = [
    r"src\ipc\polydim_ipc_v805.cpp",
    r"src\ipc\polydim_ipc_v805.h",
    r"src\ipc\polydim_crypto_v805.cpp",
    r"src\ipc\polydim_crypto_v805.h",
    r"src\math\polydim_stiefel_v805.cpp",
    r"src\math\polydim_stiefel_v805.h",
    r"src\polydim_monolith.cpp",
    r"src\polydim_monolith.rs",
    r"polydim_hw_dispatcher.py",
    r"polydim_bindings_v805.py",
]

for f in files_to_copy:
    full_path = os.path.join(src_dir, f)
    if os.path.exists(full_path):
        filename = os.path.basename(f)
        shutil.copy2(full_path, os.path.join(dest_dir, filename))
    else:
        print(f"File not found: {f}")

# Get the latest Dart FFI file and rename it to match V806
dart_src = r"E:\POLYDIM_EINSOF\_HISTORICO\ENTREGA_2026_09_20_V764\dart\polydim_ffi.dart"
if os.path.exists(dart_src):
    shutil.copy2(dart_src, os.path.join(dest_dir, "polydim_ffi_v806.dart"))
    print("Dart file copied.")
else:
    print("Dart file not found.")

print("All files copied to archivos_fuente.")
