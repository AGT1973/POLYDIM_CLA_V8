# 🏛️ CONTRATO DE SILICIO Y PRECISIÓN SOBERANA MULTIPLATAFORMA SOTA (POLYDIM V804+)

**Fecha:** 2026-09-25  
**Autor:** Ariel & Orquestador POLYDIM (Red Team Master Peer Review)  
**Estado:** Inviolable — La precisión es la restricción soberana que ordena la infraestructura.

---

## 📊 MATRIZ DEL CONTRATO DE SILICIO Y PRECISIÓN SOTA

| Backend / Hardware | FP64 Nativo | Modo de Precisión Garantizado | Alineación | Mecanismo de Detección & Fallback |
| :--- | :--- | :--- | :--- | :--- |
| **x86-64 CPU (v2/v3/v4/AVX10)** | Sí | FP64 Nativo (con contracción explicita / `-ffp-contract=off`) | 128B | CPUID + `XGETBV(OSXSAVE)` + Tabla Punteros / Highway |
| **ARM64 CPU (Apple / Graviton)** | Sí | FP64 Nativo | 128B | `HWCAP` (Linux) / `sysctlbyname` (macOS) |
| **NVIDIA GeForce (RTX 40/50)** | $1/64$ de FP32 | **Double-Float ($FP32 \times 2$)** / Ozaki-II INT8 para GEMM | Warp (32) / Tile 16 | Carga dinámica `cuda.dll` + Kernel Canario 1ms |
| **NVIDIA Datacenter (A100/H100/B200)**| Sí | FP64 Nativo / FP64 Tensor Cores | Tile 32 | Carga dinámica CUDA + Kernel Canario |
| **AMD RDNA3/4 (Consumer / APU)** | Recortado | **Double-Float ($FP32 \times 2$)** | Wave 32 | `hiprtc_XXYY.dll` + `hiprtc-builtins` + `gcnArchName` + Canario |
| **Google TPU (v3/v4/v5p/v6e/7x)** | No | **Double-Float ($FP32 \times 2$) en Pallas** | MXU $128 \times 128$ / $256 \times 256$ | Tabla por generación + Buckets con Máscara |
| **AWS Trainium / Inferentia2** | No | Etapas FP32/BF16 (Estado en CPU / Double-Float $FP32 \times 2$) | Compilador NKI | AOT `torch_neuronx.trace` + Inhabilitar Stochastic Rounding |

---

## 1. ⚙️ CPUS, DISPATCH SIMD & TOPOLOGÍA NUMA

### Detección Dinámica & Compatibilidad Windows/Linux
- **Basal x86-64-v2:** El kernel base se compila estrictamente en `x86-64-v2` (SSE4.2) para permitir la ejecución en CPUs legacy como AMD A4-6300 (Piledriver), que soporta AVX y FMA3 pero **carece de AVX2**.
- **Incompatibilidad de `target_clones` en Windows:** `__attribute__((target_clones(...)))` depende de `ifunc` de ELF y **falla en Windows**. Se utiliza la librería **Google Highway (`HWY_DYNAMIC_DISPATCH`)** o una tabla explícita de punteros a función.
- **Validación Estricta de Registros OS (`XGETBV`):** Antes de invocar kernels AVX/AVX-512, se consulta `XGETBV(0)` (OSXSAVE) para garantizar que el sistema operativo/hipervisor preserve los registros `YMM` (`0x6`) y `ZMM` (`0xe`).
- **Reproducibilidad y FMA:** 
  - Las diferencias de redondeo entre kernels FMA y non-FMA alteran la trayectoria simpléctica. Se compila con `-ffp-contract=off` o se usa `two_prod` explícito.
  - Se evita `std::fma` en CPUs sin FMA nativo (se emula en software y desacelera el cómputo); se usa la descomposición Dekker/Veltkamp escalar.
- **Topología & Seqlock Correcto:**
  - Aislamiento de caché con constante fija de **128 Bytes** (`constexpr size_t HARDWARE_CACHE_LINE_SIZE = 128;`).
  - Para evitar *Undefined Behavior* (UB) en la lectura no atómica del Seqlock en C++, se utilizan cargas relajadas atómicas con barreras de memoria (`std::atomic_thread_fence(std::memory_order_acquire)` estilo `rigtorp/Seqlock`).
  - Afinidad NUMA: `hwloc`, `OMP_PLACES=cores`, `OMP_PROC_BIND=close` y asignación *first-touch* por hilo.

---

## 2. 🎮 GPUS: EMULACIÓN DE PRECISIÓN EN HARDWARE CONSUMER

### NVIDIA GeForce & AMD RDNA (Sin FP64 Nativo)
- **Brecha FP64:** Las GPUs GeForce RTX (ej. RTX 4090/5090) ejecutan FP64 a $1/64$ de la velocidad de FP32.
- **Emulación Double-Float ($FP32 \times 2$):**
  - Actualización del estado simpléctico mediante TwoSum + TwoProd con FMA ($\approx 48\text{ bits}$ de mantisa).
  - Acumulación de posición mediante suma compensada (Kahan / TwoSum).
  - Multiplicación de matrices masiva (GEMM) mediante **Ozaki-II en Tensor Cores INT8** (acreditado hasta 9.8 TFLOPS en RTX 4090 y cuBLAS 13.0u2+).
  - *Prohibición:* Desactivar `--use_fast_math` y reasociación algebraica para preservar la exactitud de TwoSum.
- **Métrica de Brouwer contra la Deriva de Energía:**
  - La deriva del error en integradores geométricos se valida contra referencia CPU FP64 en $10^6 - 10^8$ pasos: un redondeo determinista correcto exhibe crecimiento de caminata aleatoria ($\propto \sqrt{N}$), mientras que un redondeo sesgado crece linealmente ($\propto N$).
- **Secuencia de Detección en AMD ROCm/HIP:**
  1. `LoadLibrary` probando `hiprtc_XXYY.dll` + `hiprtc-builtinsXXYY.dll`.
  2. Consulta de arquitectura mediante `hipGetDeviceProperties.gcnArchName`.
  3. Búsqueda de objetos precompilados (`.hsaco`) o compilación `hiprtc`.
  4. Ejecución y validación de **Kernel Canario de 1 ms**.
  5. Fallback automático a `CPU_OPENMP` ante fallos.

---

## 3. ☁️ ACELERADORES CLOUD: GOOGLE TPU & AWS NEURON

### Google TPU (v3 / v4 / v5p / v6e Trillium / TPU7x)
- **MXU Sizing:** Padding configurado por tabla de generación: $128 \times 128$ (hasta v5p) y $256 \times 256$ (v6e Trillium / TPU7x).
- **Emulación en Pallas:** Sin FP64 nativo. El estado simpléctico se procesa en **Double-Float FP32 escrito en Pallas**, bloqueando las simplificaciones algebraicas de XLA sobre TwoSum.
- **Prevención de Recompilaciones JIT:**
  - Agrupar dimensiones en *buckets* estáticos con padding y máscaras.
  - Precompilación AOT vía `jit(...).lower().compile()`.
  - Habilitar la caché persistente de compilación de JAX.
  - Uso de **SparseCore** (v4/v5p/v6e/7x) para operaciones dispersas *gather/scatter*.

### AWS Neuron (Inferentia2 / Trainium1/2/3)
- **Desactivación de Redondeo Estocástico:** Desactivar `NEURON_RT_STOCHASTIC_ROUNDING_EN` para preservar el determinismo y la reversibilidad temporal del integrador.
- **Graviton 3/4/5:** Reclasificado formalmente como CPU ARM Neoverse (Sección 1, soporte NEON/SVE con ancho detectado en runtime y líneas de 64B/128B).
