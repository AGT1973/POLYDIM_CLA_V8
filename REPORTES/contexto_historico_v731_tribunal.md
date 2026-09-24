# CONTEXTO HISTÓRICO — SESIÓN V731 → V732 INDUSTRIAL
*Generado: 2026-09-15T20:03 | Para: Nueva conversación de código*

## 1. Estado Actual
- **Fase:** REGLA 19 COMPLETADA. Código bloqueado. Esperando `"finish rule 19"` / `"start"` para generar V732.
- **Reporte consolidado:** `E:\POLYDIM_EINSOF\REPORTES\ingesta_v731_tribunal_ais.md`
- **Respuestas crudas del tribunal:** `E:\POLYDIM_EINSOF\ENTREGA_2026_09_15_V731_DUAL\respuestas\` (claude.md, deepseek.md, gemini.md, qwen.md, z_ai.md, chatgpt.md). Kimi caído.

## 2. Código Fuente Actual (V731 — DEFECTUOSO, NO USAR COMO BASE)
- `E:\POLYDIM_EINSOF\ENTREGA_2026_09_15_V731_DUAL\polydim_v731_monolito.py`
- `E:\POLYDIM_EINSOF\ENTREGA_2026_09_15_V731_DUAL\kernel_cpp_v731.cpp.txt`
- `E:\POLYDIM_EINSOF\ENTREGA_2026_09_15_V731_DUAL\kernel_rust_v731.rs.txt`
- `E:\POLYDIM_EINSOF\ENTREGA_2026_09_15_V731_DUAL\polydim_triton_kernel_v731.py`
- `E:\POLYDIM_EINSOF\ENTREGA_2026_09_15_V731_DUAL\readme_first.md`

## 3. Veredicto Unánime del Tribunal (7 IAs, 0 disidencias)

### Fallas Críticas Matemáticas
1. **Paradoja Involutiva:** XOR (x⊕n⊕n=x) y Householder (H²=I) con operando fijo y N=50 (par) → No-Op silencioso.
2. **Bit-63 Congelado:** `np.random.randint(0, 2**63-1)` nunca activa MSB → 1/64 del espacio inmóvil → explica drift 1.576e-02.
3. **Colapso Mantisa:** Sumar 10^7 f32 destruye precisión. Requiere f64 o Kahan.
4. **Betti-1 Falso:** `check_betti1_f32` calcula norma L2, no homología. Renombrar.

### Fallas Críticas de Arquitectura
1. **Orquestador Fantasma:** Monolito Python JAMÁS llama a Triton, C++ ni Rust. Todo NumPy/PyTorch puro.
2. **README Desconectado:** Benchmarks etiquetados con tecnología no ejecutada. D reducido a 10k en CPU.
3. **Zero-Copy Ficticio:** `import mmap` sin uso.
4. **GPU descarta resultado:** `return tensor` devuelve el numpy original, no el t_tensor procesado en VRAM.

### Hallazgo SOTA de Z_AI (El más letal)
- BSC con ruido fresco destruye TODA información mutua en 1 iteración (I(x;y)=0). Iteraciones 2-50 son decorativas.
- Isometría correcta del hipercubo: x → π(x) ⊕ c (permutación fija + máscara fija). Drift = 0 exacto.
- Norma L2 sola es necesaria pero NO suficiente para isometría. Verificar preservación de productos internos por pares.

## 4. Hoja de Ruta V732 INDUSTRIAL (A EJECUTAR EN NUEVA SESIÓN)

### Archivos a Crear (Regla 17: Max 5 + tests + build)
1. **`kernel_cpp_v732.cpp`** — PRNG in-register por hilo (XorShift64), reducción double, funciones de un solo paso (host controla iteraciones con datos frescos). `#pragma omp simd`.
2. **`polydim_triton_kernel_v732.py`** — Kernel Fused-In-Place. `dot_ptr` en VRAM (cero `.item()`). Normalización de v con epsilon.
3. **`kernel_rust_v732.rs`** — `check_l2_norm_f32` (renombrado), blindaje null/alineación, acumulación f64. `check_hamming_weight` sin cambios.
4. **`polydim_v732_monolito.py`** — Puente FFI real (`ctypes.CDLL`), Backend Registry (NumPy/C++/Triton), semillas fijas, benchmark reproducible, isometría BSC correcta (permutación + máscara fija).
5. **`readme_first.md`** — Solo afirmaciones respaldadas por código ejecutable. Métricas definidas antes de medir. Sin poesía.
6. **`test_invariants.py`** — Tests: equivalencia backends, isometría por pares, vector nulo, bit-63 activo, Householder preserva norma.
7. **`build.sh` / `Cargo.toml`** — Build reproducible.

### Principios de Diseño Obligatorios
- **REFERENCE ≠ OPTIMIZED ≠ BENCHMARK ≠ VALIDATOR** (ChatGPT)
- **Cada función hace UN solo paso; el host decide cuántas veces llamarla** (Claude)
- **El ruido nace y muere en L1/registros, nunca cruza Python→C++** (Qwen/Gemini)
- **Isometría BSC = permutación de coordenadas + máscara fija, NO ruido aleatorio desechable** (Z_AI)
- **Drift definido formalmente ANTES de medir** (ChatGPT)
- **Semillas, N≥10 corridas, mediana+IQR** (Z_AI)

## 5. Hardware Local
- CPU: Sin AVX-512 confirmado
- GPU: CUDA False (sin GPU local)
- Compiladores: `g++` y `cl.exe` no en PATH directo. Usar `E:\POLYDIM_EINSOF\vcvars64.bat` para MSVC.
- Python: Disponible. NumPy, psutil instalados. PyTorch instalado (sin CUDA).
- Rust: Verificar disponibilidad de `rustc`.

## 6. Reglas Activas Relevantes
- **Regla 10:** No benchmark sin script+CSV que lo genere.
- **Regla 16:** Código asumido ROTO hasta prueba asintótica empírica (D≥10^6).
- **Regla 17:** Doble extensión semántica (.rs.txt, .cpp.txt) para entrega.
- **Regla 19:** COMPLETADA. Liberar con "start" / "finish rule 19".
- **Regla 20:** Blood Tokens. Cero desperdicio. Cada entrega debe ser correcta la primera vez.

## 7. Archivos de Referencia
- Constitución / Rules: `C:\Users\eluithi\.gemini\config\AGENTS.md`
- Skills POLYDIM: `e:\.agents\skills\polydim_core\SKILL.md`
- Memoria Permanente: `C:\Users\eluithi\.gemini\config\PERMANENT_MEMORY.md`
- Contexto Histórico Previo: `E:\POLYDIM_EINSOF\REPORTES\contexto_historico.md`
