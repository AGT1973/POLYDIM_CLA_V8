# 🏛️ EVALUACIÓN SOTA ÍTEM POR ÍTEM: SILICIO, ACELERADORES FÍSICOS Y OBSERVABILIDAD NUMÉRICA (V804+)

**Fecha:** 2026-09-25  
**Autor:** Ariel & Red Team Bulldog POLYDIM  
**Invariante:** El rendimiento sin fidelidad física es estéril. Todo acelerador debe cumplir el contrato de conservación simpléctica, reversibilidad temporal ($\epsilon_{\text{rev}}$) y manifiesto numérico auditable.

---

## 1. ⚙️ PROCESADORES CPU (x86-64 vs ARM64) — EVALUACIÓN ÍTEM POR ÍTEM

| Ítem / Característica | Veredicto | Diagnóstico Riguroso | Solución SOTA Implementada |
| :--- | :--- | :--- | :--- |
| **`-mavx2` en AMD A4-6300 (Piledriver)** | **Correcto** | Soporta AVX y FMA3, pero **carece de AVX2**. Instrucciones como `vpaddd ymm` disparan `STATUS_ILLEGAL_INSTRUCTION`. | Compilar baseline en `x86-64` / `x86-64-v2` (SSE4.2). Aislar kernels AVX/AVX2 en unidades separadas con despacho en runtime. |
| **`target_clones` en Windows** | **Correcto** | GCC `__attribute__((target_clones))` depende de GNU `ifunc` (ELF). Falla en Windows (PE/COFF). | Despacho dinámico vía **Google Highway (`HWY_DYNAMIC_DISPATCH`)** o tabla explícita de punteros a función. |
| **Validación OSXSAVE + `XGETBV`** | **Crítico** | CPUID indica soporte de silicio, pero el OS/hipervisor puede no guardar registros. | Chequear `CPUID.1:ECX.OSXSAVE` antes de invocar `XGETBV(0)`. Exigir `(xcr0 & 0x6) == 0x6` para AVX y **`(xcr0 & 0xE6) == 0xE6`** para AVX-512 (XMM, YMM, opmask, ZMM). |
| **Líneas de Caché y False Sharing** | **Ajustado** | AMD Zen usa líneas de 64B (igual que Intel y Graviton). Apple Silicon usa 128B. | Adoptar `constexpr size_t kDestructiveInterferenceSize = 128;` como política de padding conservadora para eliminar false sharing cross-platform. |
| **Seqlocks y Data Races en C++** | **Crítico** | Cargas no atómicas concurrentes mientras un escritor muta el payload violan el modelo de memoria C++ (UB). | Implementar **Double-Buffering con índice activo atómico (`active.store(..., release)` / `load(acquire)`)**, Hazard Pointers o campos atómicos dedicados. |
| **Contracción FMA y TwoSum** | **Correcto** | FMA implícito rompe las hipótesis de algoritmos EFT (Dekker / TwoSum). | Compilar con `-ffp-contract=off` (o `/fp:precise` en MSVC). Usar `two_prod_fma(a, b)` explícito donde se requiera FMA (`p = a*b; e = fma(a,b,-p)`). |

---

## 2. 🎮 GPUs (NVIDIA CUDA vs AMD ROCm/HIP) — EVALUACIÓN ÍTEM POR ÍTEM

| Ítem / Característica | Veredicto | Diagnóstico Riguroso | Solución SOTA Implementada |
| :--- | :--- | :--- | :--- |
| **Brecha FP64 en GeForce (RTX 40/50)** | **Correcto** | En Ada AD102 el ratio FP64 es $1/64$ de FP32 (82.6 TFLOPS FP32 vs 1.29 TFLOPS FP64). | Estado simpléctico canónico en **Double-Float (`df32 { float hi, lo; }`)** con renormalización continua $|x_{lo}| \lesssim \frac{1}{2}\text{ulp}(x_{hi})$ y FMA explícita. |
| **FP16 / BF16 en Variedad $S^{D-1}$** | **Correcto** | Mantisa de 8/11 bits destruye la conservación de fase y reversibilidad en trayectorias largas. | Prohibido FP16/BF16 para el estado canónico. Restringido a clasificaciones o precondicionadores aislados. |
| **Ozaki-II / INT8 Tensor Cores** | **Condicional** | Emulación GEMM mediante descomposición modular. | Válido para bloques matriciales bien condicionados. Exige validación previa de número de condición ($\kappa$) y verificación cruzada contra FP64. |
| **Métrica de Reversibilidad Temporal** | **SOTA** | Medir solo error de energía al final puede ocultar rotura simpléctica y desfasaje orbital. | Auditoría obligatoria del **Defecto de Reversibilidad**: $\epsilon_{\text{rev}} = \frac{\|q_0 - \hat{q}_0\|}{\max(1, \|q_0\|)} + \frac{\|p_0 + \hat{p}_0\|}{\max(1, \|p_0\|)}$ tras $N$ pasos adelante e inversión temporal $N$ pasos atrás. |
| **AMD ROCm / HIP en Windows** | **Correcto** | Carga de `hiprtc` falla si faltan builtins (`hiprtc-builtinsXXYY.dll`) o hay discordancia de versionado. | Carga dinámica de DLLs versionadas, consulta de `gcnArchName`, ejecución de **Kernel Canario** con timeout y fallback determinista a `CPU_OPENMP`. |

---

## 3. ☁️ ACELERADORES CLOUD (Google TPU & AWS Neuron) — EVALUACIÓN ÍTEM POR ÍTEM

| Ítem / Característica | Veredicto | Diagnóstico Riguroso | Solución SOTA Implementada |
| :--- | :--- | :--- | :--- |
| **Google TPU (v3..v6e/7x) sin FP64** | **Correcto** | Diseñadas para alta densidad BF16/FP8 en matrices sistólicas MXU, no para FP64 científico. | Estado procesado en **Double-Float FP32 en Pallas** solo si el microbenchmark demuestra ventaja sobre host CPU. |
| **Shapes Dinámicos y Recompilación XLA**| **Correcto** | Dimensiones cambiantes disparan continuas recompilaciones de grafos XLA. | **Buckets estáticos de shapes** con padding por generación ($128 \times 128$ hasta v5p, $256 \times 256$ en v6e/7x) y máscaras. |
| **SparseCore en TPU** | **Ajustado** | No es un backend general para cualquier gather/scatter arbitrario; orientado a dataflows de embeddings. | Restringir SparseCore a accesos compatibles; operaciones de simulación dispersas no estructuradas retenidas en host. |
| **AWS Neuron (Trainium / Inferentia)** | **Correcto** | NeuronCore carece de FP64 nativo. Soporta `--native-int64`. | AOT tracing con `torch_neuronx.trace`, NKI kernels con double buffering host-device, y **desactivación obligatoria de `NEURON_RT_STOCHASTIC_ROUNDING_EN=0` (RNE)**. |
| **AWS Graviton 3/4/5** | **Correcto** | CPU ARM64 Neoverse de servidor. | Tratado como arquitectura ARM64 estándar: kernel escalar portable + despacho NEON/SVE según HWCAP del sistema. |

---

## 4. 📋 MANIFIESTO DE OBSERVABILIDAD NUMÉRICA SOTA (Audit Trail)

Toda corrida de producción o benchmark debe generar y adjuntar el manifiesto estructurado:

```ini
run_id=20260925_V804_SILICON_CERT
algorithm=Cayley_SMW_Rodrigues_S^{D-1}
dimension_D=1000000
rank_K=32
steps=100000000

backend=CPU_OPENMP
device=AMD_A4_6300_Piledriver
compiler=GCC_14.2.0_MinGW64
cpu_dispatch=SSE42_AVX_FMA
xcr0=0x0000000000000007

kernel_precision=FP64_STRICT
fma_policy=explicit_twoprod
fast_math=false
flush_to_zero=true

energy_max_relative_error=0.0000e+00
reversibility_defect=1.1102e-16
drift_metric_l2=0.0000e+00
validation=CERTIFIED_PASS_EXIT_CODE_0
```
