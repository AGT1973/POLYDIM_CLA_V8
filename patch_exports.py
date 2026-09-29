def patch_exports(filename):
    with open(filename, "r", encoding="utf-8") as f:
        code = f.read()
    code = code.replace('extern "C" int32_t', 'extern "C" __declspec(dllexport) int32_t')
    code = code.replace('extern "C" void', 'extern "C" __declspec(dllexport) void')
    with open(filename, "w", encoding="utf-8") as f:
        f.write(code)

patch_exports(r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\pmtp_rcu_v808_1.cpp")
patch_exports(r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\ipc_futex_v808_1.cpp")
print("Patched dllexport.")
