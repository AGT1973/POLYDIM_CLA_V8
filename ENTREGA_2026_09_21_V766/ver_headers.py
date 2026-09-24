import os

folder = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V764\respuestas"
files = sorted([f for f in os.listdir(folder) if f.endswith(".md")])

for f in files:
    path = os.path.join(folder, f)
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        lines = fp.readlines()
    print(f"\n=======================================================")
    print(f"ARCHIVO: {f} (Total lineas: {len(lines)})")
    print(f"=======================================================")
    headers = [line.strip() for line in lines if line.strip().startswith("#")]
    for h in headers[:12]:
        print(f"  {h}")
