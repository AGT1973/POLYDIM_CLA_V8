import os, re, json

folder = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V764\respuestas"
files = sorted([f for f in os.listdir(folder) if f.endswith(".md")])

findings = {}

for f in files:
    with open(os.path.join(folder, f), "r", encoding="utf-8", errors="ignore") as fp:
        text = fp.read()
    
    # Extraer secciones marcadas como P0, P1, Brecha, Error, Fallo
    blocks = re.findall(r'(#{1,4}\s*(?:P0|P1|BRECHA|FALLO|ERROR|HALLAZGO|Brecha|Fallo|Error|Hallazgo|H\d+)[^\n]*\n(?:[^\n]+\n){1,15})', text)
    findings[f] = blocks[:8]

print("=== SÍNTESIS DE HALLAZGOS POR MODELO ===")
for f, blist in findings.items():
    print(f"\n--- {f} ({len(blist)} bloques clave) ---")
    for b in blist[:4]:
        lines = b.strip().splitlines()
        print(f" * {lines[0]}")
        if len(lines) > 1:
            print(f"   > {lines[1][:100]}")
