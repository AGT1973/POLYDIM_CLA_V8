import os

log_file = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\auditoria_externa\05_LOG_RAW_TESTS.txt"
consolidated = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\auditoria_externa\V806_CODIGO_FUENTE_CONSOLIDADO.txt"

# Read UTF-16
with open(log_file, "r", encoding="utf-16") as f:
    log_content = f.read()

# Re-write the log as UTF-8 so humans can read it without weird characters
with open(log_file, "w", encoding="utf-8") as f:
    f.write(log_content)

# Append to consolidated
with open(consolidated, "a", encoding="utf-8") as out:
    out.write("\n=================================================================\n")
    out.write("EVIDENCIA EMPÍRICA: LOG CRUDO DE LA EJECUCIÓN (EXIT CODE 0)\n")
    out.write("=================================================================\n\n")
    out.write(log_content)
    out.write("\n\n// FIN DEL REPORTE DE CONSOLIDACIÓN V806\n")

print("Encoding arreglado y log anexado.")
