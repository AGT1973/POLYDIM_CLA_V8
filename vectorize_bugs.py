import os
import glob
import re
from collections import defaultdict

def extract_bug_coordinates():
    base_dir = r"E:\POLYDIM_EINSOF\ENTREGA_2026_09_26_V808\respuestas"
    md_files = glob.glob(os.path.join(base_dir, "*.md")) + glob.glob(os.path.join(base_dir, "kimi", "*.md"))
    
    # Bug coordinates: dict of File -> List of unique issues
    bug_map = defaultdict(set)
    
    # Keywords indicating a severe error
    keywords = ["UB", "undefined behavior", "nan", "inf", "race", "deadlock", "leak", "align", "ffi", "pointer", "segfault", "OOB", "bounds", "stiefel", "cayley", "rcu", "waitonaddress"]
    
    total_bytes = 0
    
    for fpath in md_files:
        model_name = os.path.basename(fpath).split(".")[0]
        total_bytes += os.path.getsize(fpath)
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        current_file_context = "GENERAL"
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Context tracking
            if ".rs" in line_lower or ".cpp" in line_lower or ".py" in line_lower or ".h" in line_lower:
                m = re.search(r'([a-zA-Z0-9_]+\.(rs|cpp|py|h))', line)
                if m:
                    current_file_context = m.group(1)
            
            # Extract bullet points or numbered lists that seem like bug reports
            if line.strip().startswith("-") or re.match(r'^\d+\.', line.strip()):
                if any(k in line_lower for k in keywords):
                    # Clean up the line
                    issue = line.strip()
                    if len(issue) > 15:
                        bug_map[current_file_context].add(f"[{model_name}] {issue[:200]}")
                        
    print(f"Ingestion Complete. Processed {len(md_files)} files ({total_bytes / 1024:.2f} KB).")
    print("Vector Mapping (Unique Error Coordinates by File):")
    
    total_bugs = 0
    for target_file, issues in bug_map.items():
        print(f"\nTARGET: {target_file} ({len(issues)} vectors)")
        for iss in list(issues)[:10]: # show first 10 for brevity in 1D chat
            print(f"  -> {iss}")
        if len(issues) > 10:
            print(f"  ... (+ {len(issues)-10} more vectors mapped in RAM)")
        total_bugs += len(issues)
        
    print(f"\nTotal unique vector coordinates extracted: {total_bugs}")

if __name__ == "__main__":
    extract_bug_coordinates()
