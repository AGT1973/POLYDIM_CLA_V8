"""
POLYDIM Unified Scheduler — Reemplaza TODOS los crons de Antigravity.
Corre via Windows Task Scheduler, sobrevive reinicios.

Tareas:
  1. Mail: Lee POLYDIM.CLA@GMAIL.COM, descarga a AGENT_INBOX/
  2. Git: Sync + push con escaneo anti-leak (Regla 14)
  3. Watchdog Teoría: Detecta cambios prácticos → INBOX_TEORIA.md

Instalación (PowerShell admin, UNA sola vez):
  schtasks /create /tn "POLYDIM_Unified_Cron" /tr "python E:\\POLYDIM_EINSOF\\polydim_unified_cron.py" /sc MINUTE /mo 30 /f
  
Desinstalación:
  schtasks /delete /tn "POLYDIM_Unified_Cron" /f

Log: E:\\POLYDIM_EINSOF\\.cron_log.txt
"""
import os
import sys
import json
import hashlib
import subprocess
import re
import base64
import traceback
from datetime import datetime, timezone
from pathlib import Path

# ===========================
# CONFIGURACIÓN GLOBAL
# ===========================
LOG_FILE = Path(r"E:\POLYDIM_EINSOF\.cron_log.txt")
THEORY_DIR = Path(r"E:\POLYDIM-THEORICAL")
WORKSPACE = Path(r"E:\POLYDIM_EINSOF")
EMAIL_DIR = Path(r"E:\email_AGY")
INBOX_TEORIA = THEORY_DIR / "INBOX_TEORIA.md"
WATCHDOG_STATE = THEORY_DIR / ".watchdog_state.json"

# Mail config
MAIL_SECRETS = EMAIL_DIR / ".secrets"
MAIL_VAULTS = ["account_a2a", "account_sota", "account_cursos", "account_clone"]
MAIL_INBOX = EMAIL_DIR / "AGENT_INBOX"
MAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Git config
GIT_CWD = str(WORKSPACE)
# Tokens construidos dinamicamente para evitar falsos positivos al escanearse a si mismo
LEAK_TOKENS = [
    b"".join([b"gh", b"p_"]),
    b"".join([b"sk-", b"ant"]),
    b"".join([b"sk-", b"proj"]),
    b"".join([b"sk-", b"or-"]),
    b"".join([b"sk-", b"dSPn"]),
    b"".join([b"gs", b"k_"]),
    b"".join([b"h", b"f_"]),
    b"".join([b"aq.", b"ab8"]),
    b"".join([b"pass", b"word"]),
    b"".join([b"api_keys_", b"pool"]),
    b"".join([b"KG", b"AT_"])
]

# Watchdog config
WATCH_EXTENSIONS = {".py", ".cpp", ".rs", ".h", ".toml", ".log"}
THEORY_KEYWORDS = [
    "drift", "torn_read", "betti", "neumaier", "rodrigues", "cayley",
    "pmtp", "seqlock", "epsilon", "norm", "convergence", "bug", "fix",
    "benchmark", "certified", "subnormal", "ftz", "arm64", "tpu",
    "tikhonov", "antipodal", "mix", "fixpoint",
]


def log(msg: str):
    """Append to persistent log file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    print(line, end="")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)


# ===========================
# TAREA 1: MAIL
# ===========================
def task_mail():
    """Lee correos no leídos de todas las cuentas configuradas en email_AGY."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        log("MAIL: google-api-python-client no instalado. Saltando.")
        return 0

    total_count = 0
    MAIL_INBOX.mkdir(parents=True, exist_ok=True)

    for vault in MAIL_VAULTS:
        token_path = MAIL_SECRETS / vault / "token.json"
        if not token_path.exists():
            continue

        try:
            creds = Credentials.from_authorized_user_file(str(token_path), MAIL_SCOPES)
            service = build('gmail', 'v1', credentials=creds)

            results = service.users().messages().list(
                userId='me', labelIds=['INBOX', 'UNREAD']
            ).execute()
            messages = results.get('messages', [])

            if not messages:
                continue

            log(f"MAIL [{vault}]: {len(messages)} correos nuevos detectados.")

            for msg_ptr in messages:
                msg_id = msg_ptr['id']
                try:
                    msg = service.users().messages().get(
                        userId='me', id=msg_id, format='full'
                    ).execute()

                    headers = msg.get('payload', {}).get('headers', [])
                    subject = next(
                        (h['value'] for h in headers if h['name'] == 'Subject'),
                        'Sin_Asunto'
                    )
                    sender = next(
                        (h['value'] for h in headers if h['name'] == 'From'),
                        'Desconocido'
                    )
                    date_str = next(
                        (h['value'] for h in headers if h['name'] == 'Date'),
                        str(datetime.now())
                    )

                    body = _extract_text(msg.get('payload', {}))
                    clean_subj = re.sub(r'[^a-zA-Z0-9_\-]', '_', subject)[:50]
                    file_name = f"TASK_{vault}_{msg_id}_{clean_subj}.md"
                    file_path = MAIL_INBOX / file_name

                    content = f"""# TAREA / INGESTA A2A
**Cuenta:** {vault}
**ID:** {msg_id}
**De:** {sender}
**Fecha:** {date_str}
**Asunto:** {subject}

---
## PAYLOAD:
{body}
"""
                    file_path.write_text(content, encoding='utf-8')

                    # Marcar como leído
                    service.users().messages().modify(
                        userId='me', id=msg_id,
                        body={'removeLabelIds': ['UNREAD']}
                    ).execute()
                    total_count += 1
                except Exception as msg_e:
                    log(f"MAIL [{vault}]: Error procesando msg {msg_id}: {msg_e}")
        except Exception as e:
            log(f"MAIL [{vault}]: Error de conexión: {e}")

    if total_count > 0:
        log(f"MAIL: {total_count} correos procesados a {MAIL_INBOX}")
    else:
        log("MAIL: Sin correos nuevos.")
    return total_count


def _extract_text(payload):
    """Extrae texto plano del payload Gmail."""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                return base64.urlsafe_b64decode(data).decode('utf-8')
    elif payload.get('mimeType') == 'text/plain':
        data = payload['body'].get('data', '')
        return base64.urlsafe_b64decode(data).decode('utf-8')
    return "[Sin texto plano]"


# ===========================
# TAREA 2: GIT SYNC
# ===========================
def task_git():
    """Git add/commit/push con escaneo anti-leak (Regla 14)."""
    st = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True, cwd=GIT_CWD
    )
    if not st.stdout.strip():
        log("GIT: Repositorio limpio.")
        return

    subprocess.run(["git", "add", "-A"], cwd=GIT_CWD)

    diff = subprocess.run(
        ["git", "diff", "--cached", "--", ":!polydim_unified_cron.py", ":!check_2am_cron.py", ":!sync_and_backup.py"],
        capture_output=True, cwd=GIT_CWD
    )
    diff_bytes = diff.stdout.lower()

    for token in LEAK_TOKENS:
        if token in diff_bytes:
            log(f"GIT: ⚠️ LEAK detectada: '{token.decode()}' — ABORT")
            subprocess.run(["git", "reset", "HEAD"], cwd=GIT_CWD)
            return

    if diff_bytes.strip():
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        subprocess.run(
            ["git", "commit", "-m", f"Auto-sync {ts}"],
            cwd=GIT_CWD
        )
        push = subprocess.run(
            ["git", "push", "origin", "master:main"],
            capture_output=True, text=True, cwd=GIT_CWD
        )
        if push.returncode == 0:
            log("GIT: Push OK.")
        else:
            log(f"GIT: Push falló: {push.stderr[:200]}")
    else:
        log("GIT: Staging vacío tras add.")


# ===========================
# TAREA 3: WATCHDOG TEORÍA
# ===========================
def task_watchdog():
    """Detecta cambios prácticos con relevancia teórica."""
    old_state = {}
    if WATCHDOG_STATE.exists():
        old_state = json.loads(WATCHDOG_STATE.read_text(encoding="utf-8"))

    current = {}
    for ext in WATCH_EXTENSIONS:
        for p in WORKSPACE.rglob(f"*{ext}"):
            parts = p.parts
            if any(s in parts for s in [
                "__pycache__", ".git", "node_modules", "_HISTORICO"
            ]):
                continue
            rel = str(p.relative_to(WORKSPACE))
            try:
                h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
                current[rel] = h
            except (OSError, PermissionError):
                pass

    new_entries = []
    for rel, h in current.items():
        if old_state.get(rel) != h:
            text = rel.lower()
            hits = [kw for kw in THEORY_KEYWORDS if kw in text]
            if hits:
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                change = "new" if rel not in old_state else "modified"
                new_entries.append(
                    f"\n## PENDIENTE: {change} `{rel}`\n"
                    f"- **Fecha:** {now}\n"
                    f"- **Keywords:** {', '.join(hits)}\n"
                    f"- **Fuente:** `E:\\POLYDIM_EINSOF\\{rel}`\n\n---\n"
                )

    if new_entries:
        header = ""
        if not INBOX_TEORIA.exists():
            header = "# INBOX Teoría — Buzón del Watchdog\n\n---\n"
        with open(INBOX_TEORIA, "a", encoding="utf-8") as f:
            if header:
                f.write(header)
            for entry in new_entries:
                f.write(entry)
        log(f"WATCHDOG: {len(new_entries)} cambios teóricos detectados.")
    else:
        log("WATCHDOG: Sin cambios relevantes.")

    WATCHDOG_STATE.write_text(
        json.dumps(current, indent=2), encoding="utf-8"
    )


# ===========================
# MAIN
# ===========================
def main():
    log("=" * 60)
    log("POLYDIM Unified Cron — INICIO")

    try:
        task_mail()
    except Exception as e:
        log(f"MAIL ERROR: {e}")
        traceback.print_exc()

    try:
        task_git()
    except Exception as e:
        log(f"GIT ERROR: {e}")
        traceback.print_exc()

    try:
        task_watchdog()
    except Exception as e:
        log(f"WATCHDOG ERROR: {e}")
        traceback.print_exc()

    log("POLYDIM Unified Cron — FIN")
    log("=" * 60)


if __name__ == "__main__":
    main()
