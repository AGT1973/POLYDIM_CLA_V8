import os

auditoria_dir = r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_24_V800\auditoria_externa'

header = """# 📜 POLYDIM V800 — DOSSIER MONOLÍTICO INTEGRAL DE CÓDIGO FUENTE
**Versión:** POLYDIM V800 (Industrial Release)  
**Fecha:** 2026-09-25  
**Propósito:** Dossier de código completo en un único archivo para auditoría externa por Alumnos, Subagentes y Red Teams (ChatGPT, Claude, DeepSeek, Kimi, Gemini).  
**Certificación:** 7/7 Tests Pass — Exit Code 0 en Silicio Físico (3 Pasadas Consecutivas).  

---

## 📑 ÍNDICE DE ARCHIVOS INCLUIDOS

1. [src/kernel_cpp_v800.cpp](#1-srckernel_cpp_v800cpp---kernel-c-monolítico)
2. [src/kernel_rust_v800.rs](#2-srckernel_rust_v800rs---guardián-topológico)
3. [src/polydim_triton_kernel_v800.py](#3-srcpolydim_triton_kernel_v800py---kernel-triton-gpu)
4. [src/polydim_v800_monolito.py](#4-srcpolydim_v800_monolitopy---orquestador-monolítico-python)
5. [tests/test_v800_redteam_adversarial.py](#5-teststest_v800_redteam_adversarialpy---suite-adversarial-red-team)

---

"""

cpp_code = open(os.path.join(auditoria_dir, 'kernel_cpp_v800.cpp.txt'), 'r', encoding='utf-8').read()
rs_code = open(os.path.join(auditoria_dir, 'kernel_rust_v800.rs.txt'), 'r', encoding='utf-8').read()
triton_code = open(os.path.join(auditoria_dir, 'polydim_triton_kernel_v800.py'), 'r', encoding='utf-8').read()
mono_code = open(os.path.join(auditoria_dir, 'polydim_v800_monolito.py'), 'r', encoding='utf-8').read()
test_code = open(os.path.join(auditoria_dir, 'test_v800_redteam_adversarial.py'), 'r', encoding='utf-8').read()

content = header + f"""## 1. src/kernel_cpp_v800.cpp - Kernel C++ Monolítico
```cpp
{cpp_code}
```

---

## 2. src/kernel_rust_v800.rs - Guardián Topológico Rust
```rust
{rs_code}
```

---

## 3. src/polydim_triton_kernel_v800.py - Kernel Triton GPU
```python
{triton_code}
```

---

## 4. src/polydim_v800_monolito.py - Orquestador Monolítico Python
```python
{mono_code}
```

---

## 5. tests/test_v800_redteam_adversarial.py - Suite Adversarial Red Team
```python
{test_code}
```
"""

with open(os.path.join(auditoria_dir, '02_ALL_SOURCE_SCRIPTS_MONOLITH.md'), 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated 02_ALL_SOURCE_SCRIPTS_MONOLITH.md to V800")
