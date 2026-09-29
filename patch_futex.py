futex_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\ipc_futex_v808_1.cpp"
with open(futex_path, "r") as f:
    futex_code = f.read()

if "<atomic>" not in futex_code:
    futex_code = "#include <atomic>\n#include <cstdint>\n" + futex_code
    with open(futex_path, "w") as f:
        f.write(futex_code)
    print("Patched ipc_futex")
