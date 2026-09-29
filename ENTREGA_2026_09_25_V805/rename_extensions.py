import os

folder = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\auditoria_externa\archivos_fuente"

for filename in os.listdir(folder):
    fpath = os.path.join(folder, filename)
    if os.path.isfile(fpath):
        if filename.endswith(".py") or filename.endswith(".txt") or filename.endswith(".md"):
            continue # Leave these alone
        else:
            # e.g. polydim_monolith.rs -> polydim_monolith.rs.txt
            new_name = filename + ".txt"
            new_path = os.path.join(folder, new_name)
            os.rename(fpath, new_path)
            print(f"Renamed: {filename} -> {new_name}")

print("Doble extensión semántica aplicada.")
