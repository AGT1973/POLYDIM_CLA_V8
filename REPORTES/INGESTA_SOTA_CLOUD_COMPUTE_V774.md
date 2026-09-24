# ==============================================================================
# REPORTE DE INGESTA Y EVALUACIÓN SOTA: ACELERACIÓN CLOUD & SILICIO (GAP-05 A GAP-08)
# (KAGGLE GPU/TPU, CEREBRAS WSE CSL, TRITON AUTOGRAD, JAX/XLA TPU)
# Fase 0: Ingesta Bruta Consolidada | Fase 1: Evaluación Red Team (Bulldog Critic)
# Fecha: 2026-09-24 | Versión Objetivo: POLYDIM V774
# ==============================================================================

## FASE 0: TEXTO ÍNTEGRO EN BRUTO INGRESADO POR ARIEL

```text
Aceleración por Hardware en Cloud (Kaggle GPU/TPU & Cerebras)
GAP-05 [P0 - Validación Cloud]: Benchmark Físico en Silicio Kaggle GPU (Tesla T4 / P100) para D=107D=107.
Diagnóstico: El hardware local es un procesador AMD A4-6300 (APU dual-core sin GPU discreta). Las afirmaciones de throughput de GPU en FP64 (D=107D=107 en <5 ms<5 ms) no pueden certificarse físicamente sin ejecutar el script en Kaggle y descargar el log crudo con Exit Code 0 (Regla 16).
GAP-06 [P0 - Validación Cloud]: Pipeline de Oblea Cerebras WSE (Kernel CSL).
Diagnóstico: Se dispone del código CSL compilable (kernel_csl_v753.csl.txt), pero aún no se ha generado una traza de simulación de hardware en la oblea usando el compilador de Cerebras (cslc).
GAP-07 [P1 - Hardware GPU]: Triton Custom Autograd en GPU Real.
Diagnóstico: El custom op de PyTorch 2.X validado anoche (polydim_torch_custom_op_v774.py) se probó en backend CPU. Falta registrar y validar el dispatcher CUDA/Triton con @torch.library.register_fake y kernels compilados con triton.jit.
GAP-08 [P1 - TPU]: Compilación XLA / JAX para Google TPU v3-8.
Diagnóstico: Se requiere el binding de la proyección de Stiefel a funciones primitivas de JAX (jax.custom_vjp) para habilitar ejecución nativa en TPU sin conversiones intermedias a PyTorch.

busca soluciones sota

Diagnóstico SOTA
Los cuatro gaps deben tratarse como validaciones reproducibles independientes, no como una única afirmación de rendimiento:
Gap	Solución recomendada	Criterio de cierre
GAP-05	Notebook Kaggle parametrizado para T4/P100, con medición CUDA sincronizada y artefactos inmutables	Log crudo, Exit Code 0, hardware identificado y resultado para D=107
GAP-06	Compilación CSL + simulación WSE + ejecución en hardware Cerebras si existe acceso	cslc exitoso, traza de simulación y validación numérica
GAP-07	Operador PyTorch registrado por dispatcher, kernel Triton CUDA, fake kernel y autograd	opcheck, gradcheck, torch.compile y benchmark GPU
GAP-08	Implementación JAX pura con custom_vjp, jit, vmap y backend TPU	Compilación XLA, ejecución TPU y comparación numérica/temporal

[... Texto completo de GAP-05: benchmark Kaggle con eventos CUDA, metadatos JSON y script bash con PIPESTATUS ...]
[... Texto completo de GAP-06: compilación cslc con --arch=wse2, --fabric-dims, --output-json, y cs_python contra simulador o --cmaddr ...]
[... Texto completo de GAP-07: operador PyTorch triton_op / register_fake / register_autograd con backward explícito y gradcheck ...]
[... Texto completo de GAP-08: JAX custom_vjp con projection_impl nativa XLA, jax.jit, vmap, block_until_ready y chequeo de jax.devices() ...]
[... Pipeline de CI/CD en 7 etapas y orden óptimo de implementación ...]
```

---

## FASE 1: EVALUACIÓN CRÍTICA RED TEAM (BULLDOG CRITIC)

### 1. ALERTA CRÍTICA: TRUNCAMIENTO DE FORMATO WEB ($10^7 \to 107$) Y MATRIZ CUADRADA INVIABLE

#### Detección Inmediata de Alucinación / Deformación Numérica:
1. **La Deformación $D=10^7 \to 107$:**  
   En el texto ingresado, la expresión en LaTeX `$D=10^7$` fue despojada del superíndice por el parser web, quedando como `D=107`.
   En el snippet de GAP-05, la IA generó literalmente:
   ```python
   D = 107
   x = torch.randn((D, D), device=device, dtype=torch.float64)
   y = x @ x
   ```
2. **Impacto Físico y Matemático:**
   * **Caso 1 ($D=107$):** Una matriz cuadrada $107 \times 107$ tiene solo 11,449 elementos ($\approx 91\text{ KB}$). Multiplicarla ($107^3 \approx 1.2 \times 10^6$ operaciones) toma menos de **$15\,\mu\text{s}$** en cualquier GPU modesta. Medir eso no valida nada de la escala asintótica de POLYDIM.
   * **Caso 2 (Si fuera $D=10^7$ Cuadrada):** Una matriz cuadrada de $10^7 \times 10^7$ en FP64 requeriría $10^{14} \times 8\text{ bytes} = \mathbf{800\text{ Terabytes}}$ de memoria VRAM. Ni un cluster de 10,000 GPUs NVIDIA H100 podría alojar esa matriz en memoria contigua.
3. **La Realidad Arquitectónica de POLYDIM:**
   * En POLYDIM, $D = 10^7$ representa la dimensión del espacio ambiental hiperdimensional ($S^{D-1}$).
   * Para la variedad de Stiefel $St(D, K)$, la matriz $X$ es **alta y flaca (tall-skinny)** de dimensiones $D \times K$:
     * Si $K = 32$: $10^7 \times 32 \times 8\text{ bytes} = \mathbf{2.56\text{ GB}}$.
     * Si $K = 64$: $10^7 \times 64 \times 8\text{ bytes} = \mathbf{5.12\text{ GB}}$.
   * Tanto 2.56 GB como 5.12 GB **caben perfectamente** en los 16 GB de VRAM de una Tesla T4 o Tesla P100 en Kaggle.
   * La operación real a benchmarkear **NO es `y = x @ x`**, sino la proyección de Stiefel de [`polydim_torch_custom_op_v774.py`](file:///E:/POLYDIM_EINSOF/src/polydim_torch_custom_op_v774.py):
     $$A = X^\top X \quad (K \times K), \quad L = \operatorname{chol}(A + \alpha I), \quad Q = X L^{-\top}$$
     o la rotación geodésica de Rodrigues en $S^{D-1}$ ($10^7 \times 1 \to 80\text{ MB}$).

---

### 2. EVALUACIÓN DE GAP-05: Benchmark Físico Kaggle (P100 vs. T4)

#### Elementos Válidos SOTA
1. **Medición con Eventos CUDA (`torch.cuda.Event`):** Correctísimo. Usar `time.perf_counter()` sin eventos en PyTorch mide únicamente el tiempo asíncrono de encolamiento de comandos en el driver de NVIDIA, no el tiempo físico de ejecución del silicio.
2. **Diferenciación de Throughput FP64 (Arquitectura Pascal P100 vs. Turing T4):**
   * **Tesla P100 (Pascal GP100):** Diseñada para cómputo científico. Ratio FP64:FP32 de **1:2**. Ofrece **4.7 TFLOPS** en FP64.
   * **Tesla T4 (Turing TU104):** Diseñada para inferencia FP16/INT8. Ratio FP64:FP32 de **1:32**. Solo ofrece **0.25 TFLOPS** en FP64 ($\approx 19\times$ más lenta en FP64 que la P100).
   * Por consiguiente, la meta de $<5\text{ ms}$ para la proyección en $D=10^7$ debe evaluarse prioritariamente en **Tesla P100** o documentar que en T4 se debe operar en FP32/BF16 para alcanzar esa latencia.
3. **Contrato de Salida Inmutable:** Capturar `PIPESTATUS[0]`, registrar `nvidia-smi`, volcando un artefacto JSON estructurado con hash SHA-256 del script.

---

### 3. EVALUACIÓN DE GAP-06: Pipeline Cerebras CSL (WSE-2 / WSE-3)

#### Elementos Válidos SOTA
1. **Taxonomía de Estados de Certificación:**
   * `compile_pass`: Compilado con `cslc`.
   * `sim_pass`: Simulado con `cs_python run.py --name out` en el simulador de software.
   * `device_pass`: Ejecutado en oblea física vía `--cmaddr "${CS_IP_ADDR}:9000"`.
2. **Parámetros de `cslc`:** `--output-json=out/compile.json` y `--out-routes` son indispensables para analizar la saturación de rutas de colores y el layout de memoria SRAM en la oblea.
3. **Advertencia de Fabric Dims:** La configuración `--fabric-dims=8,3` es un test canario para simulación rápida. La oblea real WSE-2 posee $750 \times 994$ PEs y la WSE-3 posee más de 900,000 PEs.

#### Situación Operativa Real
* Ariel dispone de cuenta pagada en Cerebras Inference API (`pi.cerebras.ai`), la cual otorga inferencia ultra-rápida en `gpt-oss-120b` y `qwen-3.8-27b`.
* Sin embargo, el compilador CSL (`cslc`) y el simulador de oblea requieren el **Cerebras SDK**, el cual se distribuye en imágenes Docker oficiales de Cerebras para Linux x86_64.
* *Acción Concreta:* Preparar el runner en Kaggle o Linux para descargar el SDK de CSL y validar `cslc` sobre [`ENTREGA_2026_09_18_V755/kernel_csl_v753.csl.txt`](file:///E:/POLYDIM_EINSOF/ENTREGA_2026_09_18_V755/kernel_csl_v753.csl.txt).

---

### 4. EVALUACIÓN DE GAP-07: Triton Custom Autograd en GPU Real

#### Elementos Válidos SOTA
1. **`torch.library.triton_op` vs. Binding Manual:** La recomendación de usar `torch.library.triton_op` es SOTA 2026 para PyTorch $\ge 2.4$, permitiendo que AOTInductor fusione el kernel Triton sin graph breaks.
2. **Registro Obligatorio del Backward:** El backward de la proyección de Stiefel ($G - Q \operatorname{sym}(Q^\top G)$) involucra reducciones y proyecciones. Registrarlo como operador rastreable en Dynamo evita caídas a Python eager durante el entrenamiento.
3. **Validación Formal con `opcheck` y `gradcheck`:** Usar `torch.library.opcheck` garantiza que el fake tensor no lea memoria no inicializada ni asuma propiedades de layout que Triton pueda violar.

---

### 5. EVALUACIÓN DE GAP-08: JAX / XLA para TPU v3-8

#### Elementos Válidos SOTA
1. **Purismo JAX (Cero Fuga a PyTorch/NumPy):** La prohibición absoluta de conversiones clandestinas `torch.from_numpy` dentro de la función primal de JAX es fundamental para que el compilador XLA pueda vectorizar y generar instrucciones directas para la Matrix Multiply Unit (MXU) del TPU.
2. **`custom_vjp` con `.defvjp`:** La definición explícita de `stiefel_fwd` y `stiefel_bwd` garantiza que el gradiente inverso use la fórmula geométrica exacta del espacio tangente sin intentar diferenciar la descomposición QR interna paso a paso (lo que generaría inestabilidad numérica por derivadas de Householder cuando los autovalores son casi degenerados).
3. **Precisión Numérica en TPU:** En Google TPU v3-8, las unidades MXU operan nativamente en **bfloat16** acumulando en **float32**. Operar en FP64 en TPU es emulado por software y muy lento. La matriz de aceptación define correctamente: **FP32 como objetivo primario en TPU**.

---

## PLAN DE ACCIÓN REFINADO Y ORDEN DE EJECUCIÓN (CONSENSO BULLDOG)

1. **Sprint 1 (Kaggle GPU - Inmediato):**
   * Crear el script de benchmark `benchmark_kaggle_stiefel.py` parametrizado con la forma real de POLYDIM: $D = 10,000,000$, $K = 32$ (matriz tall-skinny de 2.56 GB).
   * Medir en Tesla P100 y T4 la proyección con Shifted CholQR2 usando eventos CUDA.
   * Generar el artefacto inmutable `benchmark_D10M_K32.json` con Exit Code 0.
2. **Sprint 2 (PyTorch 2.X + Triton GPU Dispatcher):**
   * Tomar el archivo validado en CPU [`polydim_torch_custom_op_v774.py`](file:///E:/POLYDIM_EINSOF/src/polydim_torch_custom_op_v774.py) y añadir el dispatcher CUDA con Triton para ser ejecutado en el mismo runner de Kaggle.
3. **Sprint 3 (JAX / TPU v3-8):**
   * Implementar `polydim_jax_stiefel_tpu.py` con `custom_vjp` puro y compilar con `jax.jit` sobre TPU v3-8 en Kaggle/Colab.
4. **Sprint 4 (Cerebras CSL):**
   * Compilar el kernel CSL con `cslc` en un runner con Docker para certificar `compile_pass` y `sim_pass`.
