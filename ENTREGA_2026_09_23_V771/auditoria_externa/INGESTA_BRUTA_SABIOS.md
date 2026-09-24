# PROTOCOLO DE INGESTA — FASE 0 (Unión en Bruto)
**FECHA:** 2026-09-23
**VERSIÓN:** V770 (Post-Fase 1)

## 1. Estado del Bloqueo (Rule 19)
**VETO ACTIVADO:** La generación y modificación de código fuente C++/Rust/Python queda **ESTRICTAMENTE PROHIBIDA** hasta que se complete la Fase 1 (Evaluación y Adición) y el usuario autorice el desbloqueo.

## 2. Ingesta Bruta Recibida (Consolidación)

### 2.1 Origen: Cerebras WSE (mcp-cerebras)
**Resumen del Reporte:**
> The algebraic identity $G_{proj}^T G_{proj} = G^T G - S(X^T G) - (G^T X)S + S(X^T X)S$ is mathematically exact but numerically unstable.
> In floating-point arithmetic, the subtraction of two large, nearly equal matrices incurs **catastrophic cancellation**.
> The relative error bound explodes to $O(u D \sqrt{K})$, meaning hundreds of bits of error for $D=10^6$.
> The current implementation will catastrophically diverge, overflow RAM, and invoke undefined behavior on any realistic workload.

### 2.2 Origen: Kimi/Claude (Vía Ariel)
**Resumen del Reporte:**
> La contracción algebraica $Q = H - S C - (S C)^\top + S^2$ (donde $C=X^\top G, S=\text{sym}(C), H=G^\top G$) es matemáticamente correcta y representa la mejora de mayor impacto.
> Recomienda fuertemente el uso de BLAS-3 (SYRK/GEMM) en lugar de bucles C++ manuales para los bloques $K \times K$.
> Sugiere forzar simetría numérica al final: `Q = 0.5 * (Q + Q.transpose())` para mitigar asimetrías de coma flotante.
> Cuestiona el conteo de TFLOPs original, ajustando a $\sim 0.1$ GFLOP por evaluación para $D=10^7, K=512$, asumiendo que 160MB de DRAM y TFLOPs vienen de iteraciones de line-search o loops anidados.
> **Regla de oro:** No materializar $G_{proj}$ salvo que sea consumidor final.
> Disiente implícitamente con Cerebras: considera la contracción robusta conceptualmente si se usa álgebra de alta intensidad y se fuerza la simetría.

### 2.3 Origen: Tribunal de Sabios (Síntesis de DeepSeek/Qwen)
**Resolución del Conflicto Cerebras vs Kimi:**
> El Tribunal dictamina que **ambos tenían razón parcial**, y la solución SOTA requiere un diseño "Zero Trust" (Fallback Adaptativo).
> 
> **Sobre la Arquitectura (Victoria de Kimi):**
> 1. Es un error garrafal haber mantenido la doble evaluación de $G_{proj}$ en el Paso 3 (líneas 1064-1087). 
> 2. Si $G_{proj}$ solo se usa para el update Cayley ($Y_{out} = X + \alpha G_{proj} B$), **NUNCA debe materializarse**. Debe fusionarse como $Y_{out} = X + \alpha G B - \alpha X (S B)$.
> 3. Esto destruye un cuello de botella de memoria gigantesco y permite usar BLAS-3 puro.
>
> **Sobre la Matemática (Victoria de Cerebras):**
> 1. La ecuación $Q = H - S C - C^\top S + S^2$ sufre de **cancelación catastrófica severa** si el gradiente $G$ es predominantemente normal a $X$ (es decir, $G \approx XS$). En ese caso, la resta pierde todos los bits significativos.
> 2. Simetrizar $Q = 0.5 * (Q + Q^\top)$ **no cura** la cancelación; solo enmascara la asimetría de redondeo, pudiendo dejar autovalores negativos (pérdida de semidefinitud positiva).
>
> **Diseño Final Aprobado (Fast-Path + Fallback):**
> - Usar la vía rápida algebraica con BLAS-3 en FP64.
> - Calcular un indicador de peligro: $\rho = \frac{\|Q_{fast}\|_F}{\|H\|_F + 2\|SC\|_F + \|S^2\|_F}$.
> - Si $\rho$ es muy pequeño (ej. $< 10^3 u \max(D,K)$), o si el factorizador de Cholesky detecta pérdida de PSD, **activar el fallback lento** que calcula $G_{proj} = G - XS$ explícitamente y luego su Gram.

## 3. Fase 1: Verificación Empírica (Bulldog Mode)
Se procederá a escribir un script C++ aislado para demostrar empíricamente la aserción de la cancelación catastrófica variando la componente normal de $G$. Una vez probado en silicio, se diseñará la V771.
