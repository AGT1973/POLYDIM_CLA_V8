import os
import shutil
from pathlib import Path
from polydim_unified_cron import summarize_email, log

def desagotar():
    inbox_dir = Path(r"E:\email_AGY\AGENT_INBOX")
    historico_dir = Path(r"E:\email_AGY\_HISTORICO_MAIL")
    consolidado = Path(r"E:\email_AGY\INBOX_CONSOLIDADO.md")
    
    historico_dir.mkdir(parents=True, exist_ok=True)
    
    if not inbox_dir.exists():
        print("Inbox no existe.")
        return
        
    md_files = list(inbox_dir.glob("*.md"))
    print(f"Encontrados {len(md_files)} archivos para procesar.")
    
    for md_file in md_files:
        content = md_file.read_text(encoding='utf-8', errors='ignore')
        
        # Extraer basic info para el resumen
        lines = content.split('\n')
        sender = "Desconocido"
        subject = "Sin Asunto"
        date_str = "Desconocida"
        vault = "Desconocida"
        payload = ""
        
        in_payload = False
        for line in lines:
            if line.startswith("**De:**"): sender = line.split("**De:**")[1].strip()
            elif line.startswith("**Asunto:**"): subject = line.split("**Asunto:**")[1].strip()
            elif line.startswith("**Fecha:**"): date_str = line.split("**Fecha:**")[1].strip()
            elif line.startswith("**Cuenta:**"): vault = line.split("**Cuenta:**")[1].strip()
            elif line.startswith("## PAYLOAD:"): in_payload = True
            elif in_payload: payload += line + "\n"
            
        summary = summarize_email(subject, sender, payload)
        print(f"Procesado: {md_file.name} -> {summary}")
        
        with open(consolidado, "a", encoding="utf-8") as f:
            f.write(f"- **{date_str} | {vault} | {sender}**: {summary} (Ref: `{md_file.name}`)\n")
            
        # Move file
        shutil.move(str(md_file), str(historico_dir / md_file.name))
        
    print("Desagote completo.")

if __name__ == '__main__':
    desagotar()
