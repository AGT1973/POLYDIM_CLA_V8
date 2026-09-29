import os

log_file = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\auditoria_externa\05_LOG_RAW_TESTS.txt"
consolidated = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\auditoria_externa\V806_CODIGO_FUENTE_CONSOLIDADO.txt"

if os.path.exists(log_file) and os.path.exists(consolidated):
    with open(consolidated, "a", encoding="utf-8") as out:
        out.write("\n=================================================================\n")
        out.write("EVIDENCIA EMPÍRICA: LOG CRUDO DE LA EJECUCIÓN (EXIT CODE 0)\n")
        out.write("=================================================================\n\n")
        with open(log_file, "r", encoding="utf-8") as f:
            out.write(f.read())
        out.write("\n\n// FIN DEL REPORTE DE CONSOLIDACIÓN V806\n")
    print("Log anexado al consolidado.")
else:
    print("Faltan archivos.")
