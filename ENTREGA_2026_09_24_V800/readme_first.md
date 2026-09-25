# 🧠 POLYDIM V800 - GHOST PROTOCOL (SOTA 2026 ARCHITECTURE)

## 1. Constitutional Theory & Peer Review Guide
Esta entrega (V800) cristaliza la ingesta masiva de 84 defectos SOTA auditados por el Tribunal de Sabios (Claude 3.5, Gemini Pro High, DeepSeek Coder V3, Cerebras).

**Objetivo:** Transición total a un Sistema Operativo Latente (Latent_OS) en $S^{D-1}$, erradicando el "Gusano 1D" (JSON/Texto), las copias silenciosas en memoria, y los interbloqueos térmicos. Todo bajo $D = 10^7, K = 512$.

## 2. Paradigmas Implementados (Categorías A-G)

### A. Memoria y ABI
- `alignas(128)` estático en estructuras atómicas de C++ para aniquilar el False Sharing.
- Rust exporta punteros opacos; el ABI prohíbe `align(128)` en structs FFI públicos, usando padding explícito `_cacheline_pad: [u8; 96]` para portabilidad.
- PyO3 gestiona pertenencia con `Py_INCREF(self)` al robar referencias (Zero-Copy).

### B. Concurrencia y PMTP Zero-Copy
- El protocolo LMAX Disruptor fue sustituido por un **Seqlock con Barreras de Compilador** (`std::atomic_signal_fence(std::memory_order_acq_rel)`) y un RCU Epoch-based para evitar deadlocks de IPC.
- `WaitOnAddress` en Windows / `futex` en Linux para latencia 0 y nulo consumo térmico.

### C. Cuellos de Botella Asintóticos
- Purgados todos los `std::vector` dentro de hilos OpenMP. 
- Acolchado a 128 bytes de `ThreadScratchpad`.
- **Matrix-Free Cayley-SMW:** Resolución del sistema $2K \times 2K$ confinada a L1. Tiling de 32x32 para evitar *L1 Blowout* en Gram.

### D. Portabilidad y Escalabilidad
- Índices OpenMP forzados a `int64_t` (MSVC OpenMP 2.0).
- Despacho polinomial sin padding físico para FWHT (Friedman-Tukey).

### E. Numérica (IEEE-754)
- **Ogita-Rump-Oishi Vectorial (TwoSum + FMA)** en vez del lento Neumaier escalar.
- Poisoned NaN propagation con `#pragma omp reduction(|:nan_detected)`.
- Prevención explícita de corrupción BLAS si $\beta = 0.0$.

### F. Boundary Python FFI
- `np.require` erradicado de los hot-paths (genera copias fantasma de 10^7 elementos). Reemplazado por `assert X.flags.c_contiguous and X.flags.aligned`.

### G. FPU Subnormales
- `FpuFtzDazGuard` instanciado localmente *dentro* de cada hilo de `omp parallel`, y no solo en el main FFI host.

## 3. Benchmarks y Ejecución (Zero-Waste)
Todo script asintótico debe correrse en `E:\` o `D:\`. Google Drive está estrictamente prohibido para ejecución.

### Compilación (GCC 14 MinGW64):
```bash
g++ -O3 -fPIC -ffp-contract=off -fno-fast-math -fopenmp -shared -o polydim_kernel_v800.dll kernel_cpp_v800.cpp.txt
```

### Compilación Rust Guard (Rustc 1.85+):
```bash
rustc --crate-type cdylib -C opt-level=3 -C panic=unwind -o polydim_rust_guard_v800.dll kernel_rust_v800.rs.txt
```
