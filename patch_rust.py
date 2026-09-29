rust_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\kernel_rust_v808_1.rs"
with open(rust_path, "r", encoding="utf-8") as f:
    rust_code = f.read()

# Fix nested comment
rust_code = rust_code.replace("/*    order).", "      order).")

with open(rust_path, "w", encoding="utf-8") as f:
    f.write(rust_code)
print("Patched rust nested comment.")
