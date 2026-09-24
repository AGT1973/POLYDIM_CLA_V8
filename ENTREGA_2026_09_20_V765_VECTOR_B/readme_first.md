# 🧬 POLYDIM V76X (MPELEIDES HARDENED & AUDITED RELEASE)
**Programación Cognitiva, Isometría Hiperdimensional $S^{D-1}$ y Retracción Stiefel Cayley-SMW**
*Entrega Consolidada y Resolución de Auditoría Externa Multi-IA (A1–A12)*

---

## 📜 1. GUÍA RÁPIDA DE LA ENTREGA

Esta carpeta (`E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V76x\`) contiene el código de producción completo, auditado y verificado físicamente contra los 12 hallazgos de la auditoría externa multi-IA de septiembre de 2026.

### Estructura de Archivos:
1. **`readme_first.md`**: Este documento maestro.
2. **`kernel_cpp_v762.cpp.txt` / `src/polydim_kernel.cpp`**: Kernel C++ nativo con Triple Búfer SPMC, Gram triangular $2K \times 2K$, reordenamiento Axpy L1 y canario de autodiagnóstico.
3. **`kernel_rust_v762.rs.txt` / `rust/src/lib.rs`**: Guardián de invariantes en Rust 2024 con cota constante $64\epsilon_{\text{mach}} = 1.42 \times 10^{-14} \le 2.10 \times 10^{-14}$.
4. **`polydim_ffi_v762.dart` / `dart/polydim_ffi.dart`**: Puente Dart FFI con medición real mediante `Stopwatch` ($4.27\text{ ms}$ en $D=10^6$) y liberación de memoria nativa.
5. **`polydim_triton_kernel_v762.py`**: Kernel GPU Triton para proyección en esfera de alta dimensión.
6. **`polydim_v762_monolito.py`**: Orquestador en memoria compartida Zero-Copy PMTP.
7. **`include/polydim.h`**: Contrato público en C/C++ con política de precisión estricta.
8. **`auditoria_externa/`**: Dossier completo con las auditorías de Claude, Perplexity, DeepSeek, ChatGPT, Kimi, Qwen, Gemini, Z-AI y el reporte crítico consolidado.

---

## ⚡ 2. CÓMO COMPILAR Y EJECUTAR LAS PRUEBAS

### En Linux / WSL2:
```bash
./ci.sh          # Ejecuta C++ (26 pruebas) + Rust (8 pruebas) + Dart FFI + Benchmarks
make verify      # Verifica sólo C++ incluyendo la prueba canario contra -ffast-math
```

### En Windows (MinGW GCC 14 o MSVC):
```powershell
# Compilación C++ con MinGW GCC 14
E:\winlibs_gcc14_zip\mingw64\bin\g++.exe -O3 -shared -fPIC -fno-fast-math -ffp-contract=off -fopenmp -Iinclude src/polydim_kernel.cpp -o libpolydim.dll

# Ejecución de la suite de pruebas C++
E:\winlibs_gcc14_zip\mingw64\bin\g++.exe -O3 -fno-fast-math -ffp-contract=off -fopenmp -Iinclude tests/test_suite.cpp src/polydim_kernel.cpp -o test_suite.exe
.\test_suite.exe
```

---

## 📊 3. RESUMEN DE LA RESOLUCIÓN DE LOS 12 HALLAZGOS (A1–A12)

- **A1 (PMTP Concurrencia):** Triple búfer SPMC con ticket por ranura. Medido: **0 desgarros no detectados en 218,417 lecturas** y cero inanición del lector.
- **A2 (Compuerta de Ortonormalidad):** `POLYDIM_ERR_BASIS_NOT_ORTHONORMAL` $(-9)$ activo. Detecta bases con deriva desde $10^{-8}$.
- **A3 (Validación de Escalares):** `require_finite(theta/tau)` $\to$ `POLYDIM_ERR_INVALID_SCALAR` $(-8)$.
- **A4 (Punto fuera de Variedad):** `POLYDIM_ERR_POINT_OFF_MANIFOLD` $(-10)$ + `polydim_project_sphere_f64`.
- **A5 (Cota Rust Constante):** Cota fija $64\epsilon = 1.42 \times 10^{-14} \le 2.10 \times 10^{-14}$ independiente de $D$.
- **A6 (FTZ/DAZ):** `POLYDIM_ENABLE_FTZ=0` por defecto (IEEE-754 estricto). Subnormales contados como telemetría.
- **A7 (Rust 2024 & Panic):** `#[unsafe(no_mangle)]`, `panic = "unwind"` y reporte inicializado en todas las salidas.
- **A8 (Betti-1 Real):** Homología simplicial desacoplada de la norma 1D y ligada al motor Sparse VR DSU ($N \ge 1000$).
- **A9 (Pivoteo Relativo):** $\text{pivot\_thr} = \text{tol.pivot\_rel} \cdot \|M\|_\infty \cdot 2K$.
- **A10 (OpenMP Bounds):** `num_threads(nthreads)` explícito en toda región indexada por hilo.
- **A11 (Canario Anti-Reasociación):** `polydim_selftest_compensation()` detecta e invalida compilaciones con `-ffast-math`.
- **A12 (Dart FFI):** Puente funcional con asignación `calloc`, ejecución real ($4.27\text{ ms}$ en $D=10^6$) y `finally free`.

---

## 🏛️ 4. CERTIFICACIÓN EMPÍRICA Y RENDIMIENTO

| Dimensión $(D, K)$ | V761 Original | V762 Hardened | OpenBLAS (Ref) | Factor vs V761 | Deriva $\|Y^\top Y - I\|$ |
|---|---|---|---|---|---|
| **$4096, 16$** | $19.18\text{ ms}$ | **$0.89\text{ ms}$** | $1.77\text{ ms}$ | **$21.5\times$ más rápido** | $6.66 \times 10^{-16}$ |
| **$16384, 32$** | $32.03\text{ ms}$ | **$9.68\text{ ms}$** | $14.99\text{ ms}$ | **$3.3\times$ más rápido** | $8.88 \times 10^{-16}$ |
| **$16384, 128$** | $458.16\text{ ms}$ | **$152.30\text{ ms}$** | $124.24\text{ ms}$ | **$3.0\times$ más rápido** | $8.88 \times 10^{-16}$ |
| **$65536, 64$** | $408.58\text{ ms}$ | **$143.19\text{ ms}$** | $190.38\text{ ms}$ | **$2.9\times$ más rápido** | $1.11 \times 10^{-15}$ |
| **Esfera $D=10^6$** | $3.38\text{ ms}$ | **$4.25\text{ ms}$** | — | $+25\%$ (compuertas activas) | **$0.00 \times 10^{00}$** |
