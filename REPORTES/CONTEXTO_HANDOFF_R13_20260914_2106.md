# POLYDIM - CONTEXTO HANDOFF REGLA 13
**Fecha:** 2026-09-14 21:06 ART
**Sesion Origen:** 6c541d3f-d888-4af3-8e47-265a0721a966
**Razon:** Token explosion. Ingesta masiva de 6+ auditorias Red Team de multiples IAs.

---

## 1. ESTADO ACTUAL DEL PROYECTO

### Version Actual: V722 (en disco, sin modificar)
- **Ubicacion:** `E:\POLYDIM_EINSOF\ENTREGA_2026_09_14_V722\`
- **Archivos fuente:** `pmtp_kernel.cpp.txt`, `pmtp_kernel.rs.txt`, `pmtp_triton_kernel.py`, `pmtp_monolito.py`, `readme_first.md`
- **Binarios compilados:** `pmtp_kernel_cpp.dll`, `pmtp_kernel_rs.dll` (Windows x86_64)
- **Extras:** `pmtp_ffi_kernel.dart`, `build.bat`

### Regla 19: **ACTIVA (VETO DE CODIGO)**
- El agente NO debe modificar ni generar codigo fuente hasta que el usuario diga explicitamente: "finish rule 19", "start", "generate code", o "rearm all".
- Solo se permite escribir reportes Markdown en `E:\POLYDIM_EINSOF\REPORTES\`.

### Veredicto Unanime de Todas las IAs: **VETO**
- La matematica del nucleo (Cayley + Geodesica) es solida.
- La implementacion del silicio tiene 8 errores criticos verificados.

---

## 2. LOS 8 ERRORES CRITICOS CONSOLIDADOS (Consenso 6+ IAs)

### C1. Suicidio CSR (C++ - ScopedSIMDMode)
- `_mm_setcsr((old_csr | 0x8040) & ~0x3F)` DESENMASCARA excepciones FPU.
- **Fix:** `| 0x3F` para enmascarar.

### C2. Falsa Alineacion 64B (C++ - `__builtin_assume_aligned`)
- NumPy da 16B/32B, no 64B. Genera SIGSEGV con `vmovaps`.
- **Fix:** Eliminar assume_aligned(64) o usar loads no-alineados.

### C3. Kahan SIMD Ilusorio (C++ y Rust)
- Loop-carried dependency bloquea vectorizacion. Puertos AVX ociosos.
- **Fix:** `#pragma omp simd reduction(+:sum)` con acumuladores FP64.

### C4. Contrato 4 es Vaporware (C++ y Rust)
- `PmtpHeader` y `PmtpControl` definidos pero NUNCA usados en funciones.
- Rust NO tiene `PmtpHeader`, `repr(C, align(64))`, ni `spin_loop()`.
- **Fix:** Implementar o eliminar del readme.

### C5. Falso Zero-Copy / Memmove (Python)
- `ctypes.memmove(ps, psn, D_DIM*4)` x1000 = 40MB de copias inutiles.
- **Fix:** In-Place real (3 pasadas) o ping-pong de punteros.

### C6. Test Harness con Falsos Positivos (Python)
- Sin `check=True` en `subprocess.run` -> compilacion falla silenciosamente.
- `print("PASSED")` se ejecuta aunque no haya DLL.
- **Fix:** `subprocess.run(..., check=True)` + fail-hard.

### C7. JIT Triton Roto (Python/GPU)
- `tl.sqrt` recibe un `float` de Python, no un tensor Triton.
- `total_sum.item()` fuerza sync GPU->CPU por iteracion.
- **Fix:** Calcular `inv_norm` en host, pasar como escalar.

### C8. Incompatibilidad ARM / Multi-GPU
- `<x86intrin.h>` y `_mm_setcsr` no existen en ARM.
- Triton es vendor-locked a NVIDIA CUDA.
- **Fix:** Preprocesador condicional x86/ARM. `torch.compile` como universal.

---

## 3. HALLAZGOS GRAVES ADICIONALES

- **G1:** Claims AVX2/AVX-512 falsos (0 instrucciones ymm/zmm sin `-march=native`).
- **G2:** FTZ/DAZ en Rust inexistente (nunca toca CSR).
- **G3:** Sin asercion Betti-1 real (solo chequeo de norma tautologico).
- **G4:** `gc` importado pero nunca `gc.disable()` en bucle critico.
- **G5:** Cayley es O(3N) no O(N) como dice readme.
- **G6:** Divergencia semantica NaN entre CPU (rechaza) y GPU (silencia a 0).
- **G7:** Sin `ctypes.argtypes` -> `dim` se convierte como `c_int` (32-bit).
- **G8:** Compilador macOS: falta ruta `clang++` en orquestador.

---

## 4. ARQUITECTURA SOTA CONVERGENTE (Lo que debe implementarse)

### CPU (C++ y Rust):
1. FPU condicional: `#if __x86_64__` (MXCSR) / `#elif __aarch64__` (FPCR bit 24)
2. Cayley 3-Pass In-Place real: Escalares -> Vector+Norma -> Normalizacion
3. FP64 acumulacion con `#pragma omp simd reduction` (no Kahan)
4. Null guards en todas las funciones `extern "C"`
5. Epsilon clamping: `clamp(-1+1e-15, 1-1e-15)` para acos geodesico

### GPU (Python/Triton):
1. `@torch.compile(mode="reduce-overhead", fullgraph=True)` como ruta universal
2. Fallback PyTorch puro para versiones antiguas
3. `inv_norm` precalculado en host, sin `tl.sqrt` sobre escalares Python
4. Cero `.item()` / `.any()` en hot path (eliminan pipeline GPU)

### Orquestador (Python):
1. `subprocess.run(..., check=True)` -> fail-hard
2. `gc.disable()` / `gc.enable()` alrededor del bucle nativo
3. `ctypes.argtypes` explicitos con `ctypes.c_size_t` para dim
4. Deteccion de OS/Arch: Windows(cl) / Linux(g++) / macOS(clang++)
5. In-Place real o ping-pong de punteros (cero memmove)

### Portabilidad SOTA (Pendiente de investigacion):
1. **wgpu (Rust + WebGPU):** Alternativa universal para GPU compute (Vulkan/Metal/DX12)
2. **Double-Single (Two-Sum):** Emulacion FP64 en hardware FP32 para GPUs moviles
3. **Google Highway / SIMDe:** Dispatch SIMD runtime en lugar de `-march=native`
4. **CI Matrix:** Testar en x86+ARM, Linux+Win+Mac, NVIDIA+AMD+Apple

---

## 5. REPORTES GENERADOS EN DISCO

Todos en `E:\POLYDIM_EINSOF\REPORTES\`:

| Archivo | Contenido |
|---------|-----------|
| `INGESTA_REDTEAM_V723_20260914.md` | Errores V722->V723 (CSR, Kahan, FP64) |
| `INGESTA_REDTEAM_V950_20260914.md` | 3-Pass Zero-Copy, torch.compile |
| `INGESTA_REDTEAM_V723_3_20260914.md` | Test harness falsos positivos, f64 probing |
| `INGESTA_REDTEAM_PORTABILIDAD_GLOBAL_20260914.md` | SIMDe/Highway, CI Matrix, RDMA multi-vendor |
| `INGESTA_REDTEAM_RUST_WEBGPU_SOTA_20260914.md` | wgpu, WGSL subgroups, Double-Single |
| `INGESTA_REDTEAM_KIMI_V950_20260914.md` | Consolidacion Kimi V800/V950, falacias V722 |

---

## 6. INSTRUCCIONES PARA LA NUEVA SESION

1. **Pegar este archivo completo** como primer mensaje en la nueva conversacion.
2. **Indicar al agente:** "Lee `E:\POLYDIM_EINSOF\REPORTES\` para contexto completo."
3. **El codigo fuente actual esta en:** `E:\POLYDIM_EINSOF\ENTREGA_2026_09_14_V722\`
4. **Regla 19 sigue ACTIVA** hasta que digas "finish rule 19" o "generate code".
5. **Cuando levantes Regla 19:** El agente debe aplicar los 8 parches consolidados y generar V800/V950 final.

---

**FIN DEL CONTEXTO. SESION ANTERIOR CERRADA POR REGLA 13.**
