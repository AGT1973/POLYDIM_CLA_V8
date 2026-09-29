"""
Sanitize and Sync Repository (Anti-Leak & GitHub Sync)
=====================================================
1. Escanea todos los archivos rastreados y no rastreados en E:\\POLYDIM_EINSOF.
2. Purga y reemplaza cualquier API key o token real por [REDACTED_API_KEY].
3. Previene el bloqueo de GitHub Push Protection y destraba el remote main.
"""

import os
import re
import subprocess
from pathlib import Path

WORKSPACE = Path(r"E:\POLYDIM_EINSOF")

# Patrones regex de API keys y tokens reales a censurar
LEAK_PATTERNS = [
    (r"sk-ant-api03-[a-zA-Z0-9_\-]+", "[REDACTED_ANTHROPIC_KEY]"),
    (r"sk-or-v1-[a-zA-Z0-9_\-]+", "[REDACTED_OPENROUTER_KEY]"),
    (r"sk-proj-[a-zA-Z0-9_\-]+", "[REDACTED_OPENAI_KEY]"),
    (r"sk-dSPn[a-zA-Z0-9_\-]+", "[REDACTED_KIMI_KEY]"),
    (r"sk-zIrS[a-zA-Z0-9_\-]+", "[REDACTED_KIMI_KEY]"),
    (r"csk-[a-zA-Z0-9_\-]+", "[REDACTED_CEREBRAS_KEY]"),
    (r"gsk_[a-zA-Z0-9_\-]+", "[REDACTED_GROQ_KEY]"),
    (r"hf_[a-zA-Z0-9_\-]+", "[REDACTED_HF_KEY]"),
    (r"AQ\.Ab8RN6[a-zA-Z0-9_\-]+", "[REDACTED_GEMINI_KEY]"),
    (r"KGAT_[a-zA-Z0-9_\-]+", "[REDACTED_KAGGLE_KEY]"),
    (r"ghp_[a-zA-Z0-9_\-]+", "[REDACTED_GITHUB_PAT]")
]

EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", "target", "target2", "build"}
TARGET_EXTENSIONS = {".md", ".py", ".json", ".csv", ".rs", ".cpp", ".h", ".txt", ".bat", ".ps1"}

def sanitize_files():
    total_sanitized = 0
    matches_found = []

    for root, dirs, files in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            file_path = Path(root) / f
            if file_path.suffix.lower() not in TARGET_EXTENSIONS:
                continue
            
            # No sanitizar este script a sí mismo para no romper los regex
            if file_path.name == "sanitize_and_sync.py":
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                modified_content = content
                file_modified = False

                for pattern, replacement in LEAK_PATTERNS:
                    found = re.findall(pattern, modified_content)
                    if found:
                        matches_found.extend(found)
                        modified_content = re.sub(pattern, replacement, modified_content)
                        file_modified = True

                if file_modified:
                    file_path.write_text(modified_content, encoding="utf-8")
                    total_sanitized += 1
                    print(f" -> Sanitizado: {file_path.relative_to(WORKSPACE)}")

            except Exception as e:
                print(f"Error procesando {file_path.name}: {e}")

    print(f"\nRESUMEN SANITIZACIÓN:")
    print(f" -> Archivos modificados: {total_sanitized}")
    print(f" -> Tokens/Keys purgados: {len(matches_found)}")
    return total_sanitized

def sync_git():
    print("\n--- INICIANDO GIT SYNC ---")
    
    # 1. Fetch de origin
    subprocess.run(["git", "fetch", "origin"], cwd=WORKSPACE)
    
    # 2. Add
    subprocess.run(["git", "add", "-A"], cwd=WORKSPACE)
    
    # 3. Status
    st = subprocess.run(["git", "status", "--short"], cwd=WORKSPACE, capture_output=True, text=True)
    print("Estado actual:\n" + st.stdout[:500])
    
    # 4. Commit si hay cambios
    if st.stdout.strip():
        subprocess.run(["git", "commit", "-m", "Auto-sync and sanitize leaks [POLYDIM V8]"], cwd=WORKSPACE)

    # 5. Push con rebase o force-with-lease según corresponda a rama main
    print("Sincronizando con origin main...")
    push_res = subprocess.run(["git", "push", "origin", "master:main"], cwd=WORKSPACE, capture_output=True, text=True)
    if push_res.returncode == 0:
        print("✅ PUSH EXITOSO a origin:main")
    else:
        print(f"Push normal falló ({push_res.stderr[:200]}). Intentando pull con rebase...")
        pull_res = subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=WORKSPACE, capture_output=True, text=True)
        print("Pull rebase output:", pull_res.stdout[:300], pull_res.stderr[:300])
        
        push_retry = subprocess.run(["git", "push", "origin", "master:main"], cwd=WORKSPACE, capture_output=True, text=True)
        if push_retry.returncode == 0:
            print("✅ PUSH EXITOSO tras rebase.")
        else:
            print("❌ Push error:", push_retry.stderr)

if __name__ == "__main__":
    sanitize_files()
    sync_git()
