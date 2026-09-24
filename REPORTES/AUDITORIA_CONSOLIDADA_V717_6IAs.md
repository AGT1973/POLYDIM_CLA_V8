# AUDITORÍA CONSOLIDADA V717 SILICON — 6 IAs (Regla 19)
**Fecha:** 2026-09-14  
**Fuentes:** Claude, DeepSeek, GLM-5.2 (z_ai), Qwen, ChatGPT, Gemini, Kimi  
**Estado:** INGESTA COMPLETA — VETO CODE GENERATION ACTIVO  
**Veredicto unánime de las 6 IAs:** 🔴 **VETO**

---

## 1. MATRIZ DE CONSENSO — ERRORES CONFIRMADOS POR ≥3 IAs

| # | Error | Claude | DeepSeek | Qwen | ChatGPT | Gemini | Kimi | Confirmado |
|---|-------|--------|----------|------|---------|--------|------|------------|
| 1 | **FFI struct mismatch** (C++ 28B / Py 32B / Rust 64B) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **6/6** |
| 2 | **Triton reducción local** (norma por bloque, no global) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **6/6** |
| 3 | **Rust Euler, no Exp Map** (`s += dt*delta` + renorm) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **6/6** |
| 4 | **C++ heap alloc en hot path** (`std::vector` en exp_map) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **6/6** |
| 5 | **`safe_dot_product` retorna float** (trunca FP64→FP32) | ✅ | — | ✅ | ✅ | ✅ | ✅ | **5/6** |
| 6 | **`__declspec` en rama POSIX** (no compila Linux) | ✅ | ✅ | — | ✅ | — | ✅ | **4/6** |
| 7 | **Colapso a [1,0,0...]** en norm<eps (bias topológico) | ✅ | — | ✅ | ✅ | ✅ | — | **4/6** |
| 8 | **FTZ llamado en cada función** (CSR serializante) | ✅ | — | ✅ | ✅ | ✅ | ✅ | **5/6** |
| 9 | **Rust sin FTZ** (subnormales causan stalls) | — | — | ✅ | — | ✅ | ✅ | **3/6** |
| 10 | **Benchmark solo ejecuta Rust** (C++ nunca se testea) | ✅ | — | ✅ | ✅ | ✅ | ✅ | **5/6** |
| 11 | **Triton nunca ejecutado** desde monolito | — | — | — | ✅ | — | ✅ | **2/6** |
| 12 | **Betti-1 inexistente** (prometido, 0 líneas de código) | ✅ | — | ✅ | ✅ | ✅ | ✅ | **5/6** |
| 13 | **gc.disable() ausente** durante DMA/FFI | ✅ | — | — | — | — | ✅ | **2/6** |
| 14 | **Tolerancia 1e-3 oculta drift 4.4e-4** | ✅ | — | — | ✅ | — | ✅ | **3/6** |
| 15 | **Fallback NumPy certifica como "SILICON"** | — | — | ✅ | ✅ | — | ✅ | **3/6** |

---

## 2. HALLAZGOS ÚNICOS (ENCONTRADOS POR SOLO 1-2 IAs)

### Solo ChatGPT (los más profundos — 27 ciclos):
- **ERROR 15**: `align(64)` no aísla `status` atómico — sigue en la misma cache line que `magic/dim/timestamp`. Propone separar en `PmtpHeader` + `PmtpControl` (dos structs de 64B cada uno).
- **ERROR 17**: Spinlock potencialmente infinito sin timeout → priority inversion.
- **ERROR 20**: Aliasing Rust — `slice::from_raw_parts_mut(s)` + `from_raw_parts(w)` con posible overlap = UB.
- **ERROR 22**: `dim * sizeof(float)` overflow sin validación.
- **ERROR 25**: `1e-15` no crea precisión FP64 si los inputs son FP32.
- **ERROR 28**: Geodésica asume vectores normalizados sin verificar.
- **ERROR 29**: `acos` inestable cerca de ±1 → propone `atan2`.
- **ERROR 30**: No verifica que `S_t ∈ S^(D-1)` antes de Exp Map.
- **ERROR 32**: Branch `v_norm < 1e-7` mata dinámicas pequeñas → propone `sinc` Taylor.
- **CICLOS 12-27**: Infraestructura industrial (seeds, cross-backend oracle, error codes enum, long-horizon drift test, `-Wall -Werror`, ABI CI).

### Solo DeepSeek:
- **FMA sin `__FMA__` guard**: El código AVX usa `_mm256_fmadd_pd` que necesita `-mfma`, pero solo chequea `__AVX2__`. En AVX-only no compila.
- **`<linux/mman.h>` faltante**: `MAP_HUGE_2MB` no está en `<sys/mman.h>` → hugepages silenciosamente deshabilitadas.
- **Post-normalization subnormals en AVX path**: Después de dividir por `inv_norm`, el path AVX no re-sanitiza → subnormales se cuelan.
- **`memcpy` vs `memmove`**: Si `S_t == S_next` (aliased) → UB en `memcpy`.

### Solo Kimi:
- **Geodésica estable via norma**: Propone fórmula `dot = 1 - ||u-v||²/2` (error cuadrático, no angular).
- **`fmod(theta, 2π)`**: Para evitar wrap-around en pasos largos.
- **Lock con ownership token**: Previene que un thread ajeno libere un lock que no posee.
- **NaN contagious**: `safe_dot_product64` retorna NaN inmediatamente si encuentra NaN → semántica unificada C++/Rust.
- **Holonomía como test topológico**: Transporte de frame alrededor del octante reproduce π/2 — reemplaza Betti-1 con un test ejecutable.

### Solo Gemini:
- **Cayley transform exacta**: Propone Cayley $(I-\frac{dt}{2}A)^{-1}(I+\frac{dt}{2}A)$ que preserva isometría sin renormalización.
- **`ScopedSIMDMode` RAII**: Guard que restaura MXCSR al destruirse — elimina contaminación FTZ.
- **`_align_ = 64`** en ctypes: Usa `_align_` en vez de `_pack_` para forzar alignment nativo.
- **Triton FP64 en reducción**: `x.to(tl.float64)` para sumas parciales.
- **OpenMP `#pragma omp parallel for reduction`** para D=1M.

### Solo GLM-5.2 (z_ai):
- **AVX-512 vectorizado con Kahan**: `_mm512_fmadd_pd` + compensador vectorizado.
- **`_CMP_ORD_Q` mask branchless**: Sanitización SIMD sin romper pipeline.
- **Trace-rank proxy para Betti-1**: `Tr(S_t S_t^T) ≈ Tr(S_{t+1} S_{t+1}^T)` como invariante topológico lightweight.
- **Atomic Ordering::Acquire en CAS failure path** (ARM/NUMA weak memory).

---

## 3. DETECCIÓN DE ALUCINACIONES / ERRORES EN LAS IAs

| IA | Alucinación detectada | Detalle |
|----|----------------------|---------|
| Qwen | `pack = 1` como error de sintaxis | ❌ FALSO — V717 tiene `_pack_ = 1` correctamente |
| Qwen | `os.path.abspath(file)` sin guiones | ❌ FALSO — El código tiene `__file__` |
| Qwen | `if name == "main":` | ❌ FALSO — El código tiene `__name__` |
| Qwen | Campos con espacios (`"magic "`) | ❌ FALSO — No existen en V717 |
| Gemini V718 | `safe_dot_product` retorna `float` en su propio fix | ⚠️ REGRESIÓN en su código "corregido" |
| GLM-5.2 | `_mm256_extractf32x4_ps` como AVX-256 | ⚠️ Instrucción AVX-512, no existe en AVX-256 |

> [!CAUTION]
> **Qwen (Qwen3.7-Plus) fue la IA más alucinatoria** — inventó 4 errores de sintaxis que no existen en el código real. Sus hallazgos conceptuales (Euler vs Exp Map, FFI mismatch) son correctos pero los detalles de línea son fabricados.

---

## 4. TRIAJE DE PRIORIDAD PARA CÓDIGO FINAL

### 🔴 CRÍTICO (Bloquea certificación)
1. **FFI unificada a 64B exactos** con `static_assert` + padding explícito + `_pad1` para alignment de `timestamp`
2. **Triton global reduction** (two-pass o atomic_add)
3. **Rust → Exp Map real** (reemplazar Euler)
4. **`safe_dot_product` → retorna `double`** con Kahan
5. **`PMTP_EXPORT` macro portable** (eliminar `__declspec` en POSIX)
6. **C++ heap → thread_local scratch** o buffer externo

### 🟡 ALTO (Afecta corrección numérica)
7. **FTZ una sola vez** (DllMain / `__attribute__((constructor))`)
8. **Colapso norm<eps → retornar error**, no [1,0,0...]
9. **VirtualLock/mlock** para pinning RDMA
10. **Spinlock con timeout** + ownership token
11. **Benchmark ejecuta TODOS los backends** (C++ + Rust + Triton)
12. **Fallback NumPy → FAIL, no CERTIFIED**

### 🟢 MEJORA (Industria / SOTA)
13. Cross-backend oracle FP64
14. Long-horizon drift test (10k+ pasos)
15. `atan2` para geodésica estable en extremos
16. `sinc` Taylor para dinámicas pequeñas
17. Error codes enum (`pmtp_status_t`)
18. Seed determinístico para reproducibilidad
19. `-Wall -Werror -fsanitize`
20. Separar `PmtpControl` en cache line propia

---

## 5. DECISIONES ARQUITECTURALES PENDIENTES (PARA ARIEL)

> [!IMPORTANT]
> Estas 4 decisiones requieren tu input antes de generar código final:

1. **Exp Map vs Cayley**: ¿Cuál es el integrador canónico? Gemini propone Cayley exacta (preserva norma sin renorm). ChatGPT/Kimi recomiendan Exp Map. Ambos son válidos pero deben ser **uno solo** en los 3 lenguajes.

2. **Betti-1**: ¿Implementar holonomía (Kimi) o trace-rank (GLM-5.2) como proxy? ¿O eliminar del contrato?

3. **FP16 vs FP32**: README dice FP16 para 1M-D. Código usa FP32. ¿Cuál es la verdad?

4. **`PmtpHeader` layout**: ¿Un struct de 64B con todo (mi parche actual) o dos structs separados `Header` + `Control` para aislar cache lines (propuesta ChatGPT)?

---

> **ESTADO:** Ingesta de 6 IAs completa. Esperando orden de Ariel para desbloquear generación de código ("sal de regla 19").
