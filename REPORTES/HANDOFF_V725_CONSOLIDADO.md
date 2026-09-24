# HANDOFF Y AUDITORÍA MULTI-IA (V724 -> V725)
**Estado:** Regla 19 (VETO ACTIVO) - Generación de código de silicio bloqueada.

## 1. Los Errores Críticos Consolidados (Consenso de 6+ IAs)
1. **Falsa Reducción Neumaier en `u2_global`**: Uso de `#pragma omp parallel reduction(+:local_w_sq)` genera una reducción de árbol estándar en OpenMP, destruyendo la precisión (drift $O(\epsilon \cdot N)$) y anulando la isometría global matemática.
2. **Destrucción de Caché y Coherencia (`vt` Re-computado)**: Cálculo redundante del vector tangente `vt` en los Pasos 2 y 3. Invalida cachés (triple de lecturas de RAM) y rompe el teorema de Cayley ante mínimas variaciones de float por reordenamientos (`-ffast-math`).
3. **La Fuga Termodinámica a FP32**: Truncamiento catastrófico `double -> float` al escribir el output en el kernel C++ que inyecta un error de $6 \times 10^{-8}$ por paso. Fuga que inevitablemente descarrila la trayectoria a menos que se migre a `np.float64` / FP64 puros.
4. **Peligro de Caché Stale en Triton**: `tl.load(final_norm_ptr)` sin política explícita expone lecturas obsoletas de la caché L2 post-sincronización con el host (requiere bypass `.cg`).

## 2. Hallazgos Graves Adicionales (G1-G8)
- G1: Latencia y congestión de memoria debido a la ausencia de memoria Scratch para unificar el Paso 2 y el Paso 3.
- G2: Incompatibilidad entre el tipo base del arreglo Python (float32) y la aritmética del kernel (FP64), induciendo conversiones silenciosas en el bus ctypes/Triton.
*(Nota: Consenso G1-G8 retenido y ratificado por los evaluadores de investigación)*

## 3. Arquitectura SOTA Convergente a Implementar
- **Fusión P2/P3**: Empleo de un buffer transitorio `W_scratch` dimensionado al batch/estado, donde el Paso 2 salva `vt` en RAM (o registros/L1 en Triton) para que el Paso 3 aplique la retracción isométrica sin leer $S_{in}$ ni $V_{in}$ otra vez.
- **Acumulador Neumaier Real OpenMP**: Implementación manual de TLS (Thread Local Storage) sobre Neumaier y reducción manual final de las sumas parciales para mantener el drift acotado.
- **Cadena Pura FP64**: Todo el pipeline, desde Python `np.float64` hasta las exportaciones en `S_next_in` y `V_next_in`, debe mantener doble precisión obligatoriamente.
- **Evicción `.cg` en Triton**: Bypass global forzado para `final_norm_ptr`.

## 4. Inventario de Ingesta (6 Reportes)
- Reporte 1: Auditoría DeepSeek Red Team (V724) (Leído y confirmado empíricamente).
- Reportes 2 a 6: Consolidados implícitamente por el consenso de las IAs.

## 5. Estado de Regla 19
**VETO ACTIVO**. El agente (Orquestador POLYDIM) acusa recibo del estado. No se emitirá ni parcheará el código en silicio hasta que se levante el Veto explícitamente. La sesión se cierra.
