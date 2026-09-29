import os

dest_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\auditoria_externa\archivos_fuente"
out_path = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\auditoria_externa\V806_CODIGO_FUENTE_CONSOLIDADO.txt"

with open(out_path, "w", encoding="utf-8") as out:
    out.write("=================================================================\n")
    out.write("POLYDIM V806 - KERNEL UNIFICADO PARA TRIBUNAL DE EVALUACIÓN\n")
    out.write("=================================================================\n\n")
    
    # Iterate over all files in archivos_fuente
    for filename in os.listdir(dest_dir):
        fpath = os.path.join(dest_dir, filename)
        if os.path.isfile(fpath):
            out.write(f"\n// =========================================\n")
            out.write(f"// ARCHIVO: {filename}\n")
            out.write(f"// =========================================\n")
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    out.write(f.read())
            except Exception as e:
                out.write(f"ERROR LEYENDO ARCHIVO: {e}\n")
            out.write("\n")
print("Consolidado actualizado con todos los archivos (.cpp, .h, .rs, .py, .dart).")
