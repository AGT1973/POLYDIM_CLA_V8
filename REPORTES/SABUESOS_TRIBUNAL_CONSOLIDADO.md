# TRIBUNAL RED TEAM - REVISIÓN ADVERSARIAL SOTA (V759)

**Fecha de Ejecución:** 2026-09-18
**Modo:** Bulldog Critic | Anti-Happy-Path Engaged

El Tribunal de Sabuesos ha destrozado las asunciones iniciales de los reportes anteriores. La realidad del silicio es más cruda.

## 1. BG-01: TRITON CUBIN (HOUND-1)
* **Veredicto:** El `.cubin` es SASS puro, PERO la frontera ABI es un campo minado.
* **El Error Letal (La Trampa):** Triton ajusta el tamaño dinámico de la Shared Memory internamente. Si lanzas con `sharedMemBytes = 0` en C++ sin leer la metadata, harás OOM en VRAM o corromperás el bloque.
* **Anti-Tautología de Asincronía:** `cuLaunchKernel` devuelve `CUDA_SUCCESS` aunque el kernel haga segfault instantáneo en la GPU. OBLIGATORIO usar `cuCtxSynchronize()` justo después para atrapar errores reales en el puente.
* **Manejo de Contexto:** `cuDevicePrimaryCtxRetain` y `cuCtxSetCurrent` no tienen bypass.

## 2. BG-04: CONCURRENCIA FTZ/DAZ (HOUND-2)
* **Veredicto:** `enable_ftz_daz()` dentro del parallel es INSULFICIENTE si el compilador lo reordena.
* **El Error Letal (Reordenamiento de GCC/Clang):** Los intrínsecos como `_mm_setcsr()` no emiten barreras de memoria duras. El compilador de GCC puede "izar" (hoist) las instrucciones vectoriales AVX **antes** de que el registro se configure, exponiéndote a la penalidad 100x en los primeros ciclos.
* **Fix Obligatorio:** Se debe inyectar una barrera física de compilador: `__asm__ volatile("":::"memory");` inmediatamente después de setear el MXCSR.

## 3. BG-02: FALSE SHARING D=10^8 (HOUND-3)
* **Veredicto:** `alignas(64)` es una solución miope (Happy Path).
* **El Error Letal (128-byte L2 Prefetchers):** En arquitecturas modernas avanzadas, el prefetcher espacial lee líneas de 128 bytes (2x64). Dos structs de 64 bytes adyacentes aún sufrirán *False Sharing* por culpa del prefetcher.
* **El Error Letal (Striding):** `tid * num_blocks + block` sigue chocando en los "bordes" matemáticos donde el hilo N termina y empieza el hilo N+1 si `num_blocks * sizeof` no es múltiplo del caché físico.
* **Fix Obligatorio:** Usar `alignas(128)` como cota pesimista segura, o mejor aún, forzar a que cada vector de parciales se asigne alineado a página del SO (4096 bytes) con `posix_memalign` (o `_aligned_malloc` en Windows MSVC/MinGW) para asegurar conjuntos de caché mutuamente excluyentes a nivel de hardware.
