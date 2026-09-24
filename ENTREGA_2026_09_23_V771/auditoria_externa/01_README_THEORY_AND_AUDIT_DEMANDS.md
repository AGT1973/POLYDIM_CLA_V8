# POLYDIM V771 - SOTA EXTERNAL AUDIT (FASE 1)

## Contexto Arquitectónico
Se presenta al Tribunal la versión **V771**, que marca la transición final de la Fase 0 (Diagnóstico de Código) a la Fase 1 (Validación Empírica en Silicio).
En esta iteración, se han integrado las rectificaciones exactas sugeridas por el arbitraje anterior (Cerebras/Kimi/Claude) respecto al **Cache Thrashing** y los límites asintóticos reales.

## Demandas de Auditoría (Lo que buscamos)
Exigimos al Tribunal Adversarial (Red Team) que ejecute una **verificación destructiva** sobre las modificaciones de la V771. Las áreas críticas a auditar son:

1. **L1 Cache Blocked GEMM en C++:**
   Hemos introducido un kernel de bloqueo ($32 \times 32$) en `polydim_project_tangent_stiefel_f64` y `polydim_stiefel_cayley_smw_f64`.
   *Demanda:* Analizar si el orden de los bucles internos (`p -> i -> c`) y la directiva `#pragma omp simd` realmente logran mantener los datos en L1/L2, o si existe una asfixia de memoria remanente (TLB misses).
2. **Rollover de Pila en OpenMP:**
   Regresamos al `temp[512]` local en CholQR2 para evitar el Segfault multihilo de 16 MiB.
   *Demanda:* ¿Es asintóticamente estable para $K=512$?
3. **Escáner NaN Paralelo:**
   Se aplicó `#pragma omp parallel for reduction(|:bad_value)` en Gram-Schmidt.
   *Demanda:* ¿Existe alguna colisión de variables o data race en la reducción atómica lógica?
4. **Viabilidad de BLAS (Próxima Fase):**
   Demostramos empíricamente que la iteración $X^\top X$ de Cayley tarda 100 segundos para $D=10,000$ debido al límite del producto exterior escalar en C++.
   *Demanda:* Confirmar que el traslado de las rutinas O(D K^2) hacia `cblas_dsyrk` y `cblas_dgemm` es el único camino viable en el hardware moderno para alcanzar $D=10^6$.
