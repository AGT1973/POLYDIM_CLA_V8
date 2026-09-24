# AUDITORÍA DEEPSEEK RED TEAM (V724)
**Fecha:** 14 de Septiembre de 2026
**Objetivo:** Verificación Zero-Trust de Isometría, Drift y hardware en V724.

## VEREDICTO DEEPSEEK: ALGEBRA CORRECTA, NUMÉRICA Y MEMORIA CON FALLAS

La evaluación autónoma de DeepSeek acaba de demoler la afirmación de "Drift Cero" y "Cero Cuellos de Botella" de la V724. Aunque la teoría matemática de la Isometría Global es correcta, el código en silicio contiene tres vectores letales de fallo:

### 1. Falsa Reducción Kahan en `u2_global` (Drift Activo)
El manifiesto V724 presume del acumulador Neumaier, pero en el Paso 2 de C++, la reducción de `local_w_sq` se hace mediante la directiva por defecto de OpenMP (`#pragma omp parallel reduction(+:local_w_sq)`). Esto es una suma en árbol de doble precisión **NO compensada**. Para dimensiones $10^7$, el error de reducción es $O(\epsilon \cdot N \cdot \max|w^2|)$. La isometría se pierde irremediablemente con cada paso.

### 2. Violación de Coherencia de Datos (Re-computación de `vt`)
El Paso 2 calcula `vt` para la norma `w_sq`. Luego, el Paso 3 **recalcula** `vt` desde cero utilizando las mismas lecturas. 
Si el compilador aplica reordenamiento de coma flotante (`-ffast-math`) o si los hilos leen la memoria con latencia, el `vt` del Paso 3 podría ser a nivel de bit distinto al `vt` del Paso 2. Si `w` varía, la matriz racional calculada sobre `u2_global` dejará de ser isométrica respecto al vector real aplicado. Además, leer `S_in` y `V_in` dos veces seguidas destruye el caché (3x tráfico de memoria).

### 3. Truncamiento Castastrófico a FP32
La matemática interna de `cayley_step_global_isometry` se ejecuta en `double` (FP64), pero al finalizar, el resultado se trunca al escribir:
`S_next_in[i] = (float)...;`
Esto inyecta un error relativo de $\approx 6 \times 10^{-8}$ por paso. En 1000 iteraciones, el drift FP32 devorará cualquier garantía matemática. La isometría estricta exige que la máquina de estados mantenga la posición en `double` a menos que se re-normalice periódicamente.

### 4. Peligro de Caché Stale en Triton L2
El Paso 2 en Triton lee la norma final mediante `tl.load(final_norm_ptr)`. DeepSeek advierte que, dependiendo del hardware, la caché L2 podría devolver un valor obsoleto (stale) de antes de la sincronización del host. Requiere explícitamente el modificador de bypass de caché: `tl.load(final_norm_ptr, cache_modifier=".cg")`.

## PLAN DE ACCIÓN REQUERIDO
1. Eliminar el `reduction(+:...)` de OpenMP en el Paso 2 de C++ y aplicar `neumaier_add` manualmente.
2. Inyectar un buffer temporal (`w_scratch`) para no recalcular `vt`.
3. Aplicar `.cg` (Cache Global) en Triton.
4. Escalar los buffers de Python a `np.float64` para frenar la hemorragia de truncamiento.
