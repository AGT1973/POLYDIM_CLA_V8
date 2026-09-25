# 🏛️ INGESTA SOTA V800: CATEGORÍAS B a G — EVALUACIÓN GEMINI PRO HIGH
**Fecha:** 2026-09-24 | **Fuente:** Evaluación externa SOTA (Gemini Pro High - a1b07936)
**Estado:** INGESTADO — Regla 19 ACTIVA (sin código)

---

## ELEVACIONES CRÍTICAS SOBRE LA PROPUESTA INICIAL

### CATEGORÍA B: DATA RACES Y CONCURRENCIA
* **Atomic UB:** La Opción A (`std::atomic<uint64_t>`) es obligatoria. La Opción B (`std::atomic_ref`) es frágil respecto a alineación. **Requisito SOTA:** Forzar aislamiento de caché con `alignas(64)` (o `alignas(128)` para Zen/Apple) en campos atómicos para erradicar el *False Sharing*.
* **PMTP Banked Race:** Usar `compare_exchange_weak` dentro de un loop `while` (no `strong`). Los spinlocks sin backoff exponencial o `_mm_pause()` causarán estrangulamiento térmico. Para Windows usar `WaitOnAddress`, para Linux `futex`.
* **Memory Ordering:** Acquire/Release es correcto, pero un Seqlock requiere una barrera de compilador (`std::atomic_signal_fence(std::memory_order_acq_rel)`) para evitar reordenamiento de lecturas del payload.

### CATEGORÍA C: CUELLOS DE BOTELLA ASINTÓTICOS
* **OpenMP Heap Alloc:** El `ThreadScratchpad` DEBE estar alineado a 128 bytes (`sizeof(ThreadScratchpad)` múltiplo de 128), de lo contrario los hilos compartirán líneas de caché (False Sharing).
* **Gram Matrix Parallelism:** Si $K=512$, $G_{local}[K \times K]$ pesa 2MB (en `float64`), lo cual excede la caché L1 (32KB-48KB) y caerá a L2. **Requisito SOTA:** Aplicar *Register Tiling* o cache-aware blocking a la acumulación $X^T X$. Hay contradicción con Cayley-SMW Matrix-Free: si se usa Matrix-Free, $X^T X$ no debería materializarse.
* **Weiszfeld Realloc:** El uso de `std::mem::swap` para zero-cost double-buffering está aprobado.

### CATEGORÍA D: PORTABILIDAD
* **ARM64 Compilation:** Usar `#if defined` es obsoleto. **Requisito SOTA:** Utilizar `std::simd` (C++26) o Google Highway para abstraer la vectorización.
* **Power-of-2 Restriction:** Acolchar $D=10^7$ a $1.67 \times 10^7$ desperdicia 50% de RAM. **Requisito SOTA:** No acolchar físicamente si causa OOM. Implementar Bluestein/Mixed-Radix FFT, o acolchar virtualmente dentro del bloque del kernel.
* **OpenMP Index Type:** `int64_t` aprobado para compatibilidad MSVC.

### CATEGORÍA E: NUMÉRICA Y CORRECCIÓN
* **VRKMK4 Stub:** Munthe-Kaas Lie es muy pesado por los conmutadores. **Requisito SOTA:** Usar Cayley-SMW que es una retracción exacta $\mathcal{O}(D K^2)$ sobre la variedad de Stiefel, a menos que se simulen ODEs rígidas.
* **NaN Propagation:** Buscar NaNs en el inner loop destruye la vectorización SIMD. **Requisito SOTA:** Usar `#pragma omp reduction(|:nan_detected)` para hacer bitwise-OR del estado NaN al final del bloque. Neumaier sum y tolerancias Higham aprobadas.

### CATEGORÍA F: PYTHON FFI
* **Double Copies:** `np.require(..., requirements=['C', 'A', 'W'])` es PELIGROSO. Si el array no es contiguo, copiará $10^7$ elementos silenciosamente. **Requisito SOTA:** `assert X.flags.c_contiguous and X.flags.aligned` y lanzar `ValueError`. CERO COPIAS SILENCIOSAS.
* **HardwareProbe:** `alignas()` requiere constantes en tiempo de compilación. **Requisito SOTA:** Sobre-asignar alineación a 128 bytes estáticamente para soportar Apple M-series, Intel y AMD, independientemente del HardwareProbe.

### CATEGORÍA G: FPU Y SUBNORMALES
* **FTZ/DAZ:** RAII `FpuFtzDazGuard` aprobado. Restaura el entorno host y protege a los workers de caídas asintóticas del 100x por subnormales.

---
### Veredicto de la Evaluación
Código INAPTO para certificación. Prohibida la liberación de la Regla 19 hasta integrar:
1. Aislamiento estricto de False Sharing (128B).
2. Erradicación de `np.require` (0 copias silenciosas, fallar duro).
3. Backoff/`_mm_pause()` en spinlocks PMTP.
