import os
import re
import shutil

base = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC\auditoria_externa"
src = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V805_IPC"

# ---------------------------------------------------------------------------
# FIX V807 - causa raiz del Hallazgo 1 de la auditoria:
# La version anterior de este script ESCRIBIA A MANO el texto de
# 05_LOGS_Y_CERTIFICACIONES_TESTS.md, incluyendo la linea:
#     "- Anillo SPSC Wait-Free (62,000 eventos/seg)"
# ese numero no salia de ningun test: era un string literal. El log crudo
# real (05_LOG_RAW_TESTS.txt) decia 54322 eventos/seg. Ahora este script
# PARSEA el log crudo real y genera el resumen desde ahi. Si el log no
# existe o no matchea, el script FALLA (no genera una certificacion con
# huecos) en vez de rellenar con un numero inventado.
# ---------------------------------------------------------------------------

RAW_LOG_NAME = "05_LOG_RAW_TESTS.txt"

PATTERNS = {
    "spsc_throughput": re.compile(r"Throughput SPSC:\s*([\d.]+)\s*eventos/seg"),
    "dsu_nodes_built": re.compile(r"Construyendo topolog.a lineal en cadena de V=([\d,]+) nodos"),
    "dsu_nodes_evaluated": re.compile(r"Cadena lineal de (\d+) nodos evaluada"),
    "ortho_error": re.compile(r"Error de ortogonalidad final:\s*([\d.eE+-]+)"),
}


def parse_raw_log(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    parsed = {}
    for key, pat in PATTERNS.items():
        m = pat.search(text)
        parsed[key] = m.group(1) if m else None
    return parsed


def build_certification_text(parsed):
    missing = [k for k, v in parsed.items() if v is None]
    if missing:
        raise RuntimeError(
            "No se pudieron extraer del log crudo los campos: %s. "
            "Me niego a generar una certificacion con numeros inventados "
            "para rellenar el hueco (ese fue exactamente el bug V806)." % missing
        )

    nodes_built = parsed["dsu_nodes_built"].replace(",", "")
    nodes_eval = parsed["dsu_nodes_evaluated"]
    warning = ""
    if nodes_built != nodes_eval:
        warning = (
            "\n> ADVERTENCIA AUTOMATICA: el log anuncia construir V=%s "
            "nodos pero solo evalua %s. Esta discrepancia se deja explicita "
            "en vez de ocultarla; corregir el test o el mensaje antes de "
            "certificar 'ultra escala' en el titulo.\n" % (nodes_built, nodes_eval)
        )

    return (
        "# RESULTADOS EMPIRICOS (extraidos automaticamente de %s, no escritos a mano)\n"
        "- Anillo SPSC Wait-Free: %s eventos/seg (medido, no redondeado a una cifra de marketing)\n"
        "- DSU Iterativo Rust: construccion anunciada V=%s, evaluacion real V=%s\n"
        "%s"
        "- Stiefel Shifted CholQR: error de ortogonalidad final = %s\n"
        % (
            RAW_LOG_NAME,
            parsed["spsc_throughput"],
            nodes_built,
            nodes_eval,
            warning,
            parsed["ortho_error"],
        )
    )


def main():
    raw_log_path = os.path.join(base, RAW_LOG_NAME)
    parsed = parse_raw_log(raw_log_path)
    cert_text = build_certification_text(parsed)

    with open(os.path.join(base, "05_LOGS_Y_CERTIFICACIONES_TESTS.md"), "w", encoding="utf-8") as f:
        f.write(cert_text)

    os.rename(
        os.path.join(base, "00_PROPOSITO_Y_FUNDAMENTOS_POLYDIM.md"),
        os.path.join(base, "01_TEORIA_SIMPLIFICADA.md"),
    )
    os.rename(
        os.path.join(base, "01_INSTRUCCIONES_PARA_IAS_EVALUADORAS.md"),
        os.path.join(base, "03_INSTRUCCIONES_PROMPT_IA.md"),
    )
    os.rename(
        os.path.join(base, "02_RESOLUCION_BRECHAS.md"),
        os.path.join(base, "04_REPORTE_DE_BRECHAS_Y_FIXES.md"),
    )

    with open(os.path.join(base, "02_SILICON_CONTRACT.md"), "w", encoding="utf-8") as f:
        f.write("# SILICON CONTRACT & REGLAS ASINTOTICAS\n")
        f.write("1. Agnosticismo de Hardware: el codigo interroga dinamicamente TPU/CUDA/XPU/OpenMP.\n")
        f.write("2. Zero-Copy IPC: uso exclusivo de memoria compartida PMTP para movimiento masivo.\n")
        f.write("3. Todo dato en 05_LOGS_Y_CERTIFICACIONES_TESTS.md sale de un parseo automatico "
                "de 05_LOG_RAW_TESTS.txt. Ningun numero se escribe a mano en este generador.\n")

    pruebas_dir = os.path.join(base, "pruebas_unitarias")
    os.makedirs(pruebas_dir, exist_ok=True)
    shutil.copy2(
        os.path.join(src, "test_v805_ipc_suite.py"),
        os.path.join(pruebas_dir, "test_v805_ipc_suite.py"),
    )
    print("Estructura SOTA generada (V807: numeros trazables al log crudo).")


if __name__ == "__main__":
    main()
