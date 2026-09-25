# 🛠️ SOLUCIONES SOTA PARA 84 DEFECTOS V774
**Fecha:** 2026-09-24 | **Fuentes:** 3 sabuesos SOTA (C++, Rust, Python)

---

## CATEGORÍA A: CORRUPCIÓN DE MEMORIA Y ABI (MEM-01 a MEM-09)

### Fix: ABI Struct Alignment (MEM-01, MEM-02)
**Patrón Firefox/LLVM:** Nunca poner `align(128)` en structs FFI públicos. Usar `#[repr(C)]` con alignment natural (8B) + padding explícito `_cacheline_pad: [u8; 96]` para llegar a 128B de tamaño total.
- **Rust:** `#[repr(C)]` (sin `align(128)`), con `static_assert` de `size_of == 128`.
- **C++:** `static_assert(sizeof == 128, alignof == 8, offsetof)`.
- **Python:** `ctypes.sizeof(struct) == 128` assertion en import.
- **Herramientas:** `cbindgen` (Rust→C), `bindgen` (C→Rust), `libabigail` (CI ABI diff).

### Fix: PyO3 Use-After-Free (MEM-04, MEM-05, MEM-06)
**Patrón Polars/tiktoken:** `PyArray_SetBaseObject` con `Py_INCREF(self_)`. NumPy retiene el `ZeroCopyTensor` vía `base`, evitando UAF.
- Para memoria C++: `PyCapsule` con destructor que llama a `polydim_free_aligned()`.
- **Prohibido:** `Vec::from_raw_parts` sobre memoria de otro allocator.
- **Alternativa:** `OwnedForeignBuffer<T>` con function pointer `DeallocFn`.

### Fix: Integer Overflow (MEM-03)
`n.checked_mul(d)` + validación `total_bytes <= isize::MAX`. Static assert: `size_of::<usize>() >= 8`.

---

## CATEGORÍA B: DATA RACES Y CONCURRENCIA (RACE-01 a RACE-05)

### Fix: Atomic UB (RACE-01, RACE-05)
**Opción A (C++20):** Declarar campos como `std::atomic<uint64_t>` directamente en el header.
**Opción B (Legacy):** `std::atomic_ref<uint64_t>` (C++20 P0019R8) sobre campos plain.

### Fix: PMTP Banked Race (RACE-02, RACE-03)
**Patrón LMAX Disruptor:** `compare_exchange_strong(FREE → ACQUIRING)` antes de escribir metadata. Transición `ACQUIRING → ACTIVE` con `memory_order_release`. Writer DEBE abortar (`ERR_BUSY`) si readers activos tras retries.

### Fix: Memory Ordering (RACE-04)
`sequence` con `memory_order_release` (no `relaxed`). Reader usa `memory_order_acquire` en sequence antes de leer banco.

---

## CATEGORÍA C: CUELLOS DE BOTELLA ASINTÓTICOS (PERF-01 a PERF-08)

### Fix: OpenMP Heap Alloc (PERF-01, PERF-02)
**Patrón HPC:** Pre-alocar `ThreadScratchpad[omp_get_max_threads()]` alineado a 64B fuera del `#pragma omp parallel`. Cada hilo accede `scratchpads[omp_get_thread_num()].buffer`. Cero mallocs en el loop.

### Fix: Gram Matrix Parallelism (PERF-04, PERF-07)
**Parallelizar sobre eje D** (largo), no sobre K (corto). Cada hilo acumula en $G_{local}[K \times K]$ privado en L1 (8KB para K=32). Reducción jerárquica $O(\log_2 T)$ al final. Cero atómicos.

### Fix: Dense Matrix OOM (PERF-03, PERF-08)
**Cayley-SMW Matrix-Free** (ya ingestado). Tiling L2 con bloques $B \approx 8192$. Nunca materializar $G_{proj}$ de $D \times D$.

### Fix: Weiszfeld Realloc (PERF-06)
Pre-alocar `next_median` una sola vez fuera del bucle. Usar `std::mem::swap` entre iteraciones.

---

## CATEGORÍA D: PORTABILIDAD (PORT-01 a PORT-06)

### Fix: ARM64 Compilation (PORT-01, PORT-02)
Guard `#if defined(__x86_64__) || defined(_M_X64)` alrededor de `<immintrin.h>` y todos los intrínsecos SSE/AVX. Fallback a NEON `STNP`/`vld1q_f64` en ARM64.

### Fix: Win32 APIs (PORT-03, PORT-05)
Guard `#if defined(_WIN32)` alrededor de `GetModuleHandleA`, `GetProcAddress`. En POSIX, incluir `<sys/types.h>` y `<signal.h>`.

### Fix: OpenMP Index Type (PORT-04)
Reemplazar `size_t` por `int64_t` en todos los índices de bucles OpenMP para compatibilidad MSVC.

### Fix: Power-of-2 Restriction (PORT-06)
Eliminar restricción `(D & (D-1)) == 0`. Usar padding al siguiente power-of-2 si FWHT lo requiere.

---

## CATEGORÍA E: NUMÉRICA Y CORRECCIÓN (NUM-01 a NUM-04)

### Fix: BLAS beta Ignorado (NUM-01, NUM-02)
`c[idx] = beta * c[idx] + alpha * acc`. Soportar `CblasColMajor` y `CblasLower`.

### Fix: VRKMK4 Stub (NUM-03)
Implementar integrador de Lie real con tableau de Butcher (Munthe-Kaas). El stub con PRNG semilla 42 debe ser erradicado.

### Fix: NaN Propagation (NUM-04)
Reemplazar `.max(1e-12)` por `safe_dist_clamp()` que retorna `ERR_NUMERICAL_NAN` si input es NaN.

### Fix: Tolerancias Hardcodeadas (P2-12)
Fórmula Higham: `tol = c * D * eps_mach` donde $c \in [10, 100]$. Para $D=10^7$: tol $\approx 2.22 \times 10^{-8}$.
Implementar `neumaier_sum()` para acumulación $O(1)$ error.

---

## CATEGORÍA F: PYTHON FFI (PY-01 a PY-03)

### Fix: Enum Invertido (PY-01)
**Patrón X-Macros:** Single source of truth en `polydim_status.def`. Codegen Python en build. CI canary test que exporta tabla de enums desde C y la compara con Python `IntEnum`.

### Fix: ctypes Unpacking (PY-02)
`(PolydimEdge * N).from_buffer(np_structured_array)` → zero-copy. O `np.ctypeslib.ndpointer` para pasar punteros directos.

### Fix: Error Checking (PY-03, P1-32)
`ctypes.errcheck = auto_errcheck_status` → excepciones tipadas automáticas en cada llamada FFI.

### Fix: Double Copies (P1-28, P1-29)
`np.require(X, dtype=np.float64, requirements=['C', 'A', 'W'])`. Verificar con `__array_interface__['data'][0]`.

### Fix: Stiefel VJP (P1-36)
Resolver ecuación de Sylvester adjunta en eigenbasis de SVD: $\tilde{\Phi}_{ij} = \tilde{C}_{ij} / (\sigma_i + \sigma_j)$. Fórmula Absil.

### Fix: HardwareProbe (P1-30)
Runtime cross-platform: `os.sysconf('SC_LEVEL1_DCACHE_LINESIZE')` (Linux), `sysctl hw.cachelinesize` (macOS), `GetLogicalProcessorInformation` (Windows). Exportar como struct C al kernel nativo.

---

## CATEGORÍA G: FPU Y SUBNORMALES (P1-10)

### Fix: FTZ/DAZ
RAII guard `FpuFtzDazGuard` que salva/restaura `MXCSR` (x86) o `FPCR` (ARM64). Instanciar en CADA hilo OpenMP worker + en el hilo FFI host. Restaurar estado original al salir para no contaminar Python/NumPy.
