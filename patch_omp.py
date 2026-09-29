kernel_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\kernel_cpp_v808_1.cpp"
with open(kernel_path, "r") as f:
    kernel_code = f.read()

kernel_code = kernel_code.replace("schedule(static) collapse(2)", "schedule(static)")

with open(kernel_path, "w") as f:
    f.write(kernel_code)
print("Removed collapse(2)")
