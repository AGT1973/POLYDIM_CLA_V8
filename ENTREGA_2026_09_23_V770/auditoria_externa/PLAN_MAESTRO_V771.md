# PLAN MAESTRO V771 (Síntesis de Sabios - Fase Final)
**ESTADO:** Fase 0 Completada (Ingesta y Arbitraje Listos).
**OBJETIVO:** Implementar el "Silicon Contract" definitivo.

## 1. El Diagnóstico Final
La auditoría externa cruzada ha expuesto dos cuellos de botella / vulnerabilidades masivas en V770:

### A. Vulnerabilidad Numérica (Cerebras)
La contracción $Q = H - SC - C^\top S + S^2$ que introdujimos para evitar materializar $G_{proj}$ sufre de **Cancelación Catastrófica** si el gradiente es predominantemente normal a $X$. Nuestro test C++ demostró empíricamente que el error explota (7000% de error relativo y autovalores negativos) cuando $\epsilon < 10^{-6}$.

### B. Vulnerabilidad de Microarquitectura (Kimi/Claude)
El Paso 3 (Actualización Cayley) en `kernel_cpp_v770.cpp` (líneas 1064-1087) estaba **recalculando $G_{proj}$ fila por fila**. Esto es un desperdicio colosal de CPU (miles de micro-loops $O(D K^2)$ sin cache-awareness). 
Kimi propuso una refactorización algebraica sublime:
Como el update es $Y_{out} = X + \tau G_{proj} Z_1 + \tau X Z_2$, podemos expandirlo:
$$ Y_{out} = X + \tau(G - XS)Z_1 + \tau X Z_2 $$
$$ Y_{out} = X(I + \tau Z_2 - \tau S Z_1) + G(\tau Z_1) $$
Definiendo las matrices $K \times K$ pequeñas:
$W_X = I + \tau Z_2 - \tau S Z_1$
$W_G = \tau Z_1$
El paso entero de actualización se colapsa a:
$$ Y_{out} = X W_X + G W_G $$
**¡Cero $G_{proj}$ materializado, cero re-cálculos, un solo pase limpio de memoria!**

## 2. Plan de Acción Multi-Integración (V771)
Ejecutaremos 3 parches simultáneos en la V771 para destrozar todos los cuellos de botella encontrados:

1. **Absorción Algebraica de $G_{proj}$ (Victoria de Kimi):**
   - **Brecha:** El Paso 3 calcula `row_gp[c] -= xq * Sq[c]` (líneas 1064-1087) miles de veces (Doble Evaluación).
   - **Solución:** Calcular $W_X = I + \tau Z_2 - \tau S Z_1$ y $W_G = \tau Z_1$ en L1.
   - Reemplazar el bucle masivo por una sola pasada en streaming: $Y_{out} = X W_X + G W_G$.

2. **Verificación Numérica Adaptativa para $Q$ (Corrección SOTA):**
   - **Brecha:** La métrica ingenua $\rho$ no detecta pérdida real de precisión, y el nombre "Zero Trust Cerebras" era una alucinación/metáfora.
   - **Solución:** Implementar el estimador riguroso de cancelación: $r_{cancel} = \frac{\|Q_{fast}\|_F}{\|H\|_F + \|S^2\|_F + \tau_{abs}}$ y control de asimetría $a_{sym}$.
   - **Fallback:** Si $r_{cancel} < \tau_{cancel}$ o $a_{sym} > \tau_{sym}$, materializar $G_{proj}$ explícitamente en el buffer de contingencia, calcular $G_{proj}^\top G_{proj}$ y forzar simetría.

*Nota de Vectorización sobre el Teorema de Kimi:* La auditoría cuestionó la existencia de $Z_1$ y $Z_2$. Para nuestro kernel, el reclamo es algebraicamente correcto en el vacío, pero **en nuestra arquitectura, $Z$ es de $2K \times K$** (resultado de la inversión de Cayley). La mitad superior mapea a $G_{proj}$ y la inferior a $X$. Por lo tanto, la partición $W_X = I + \tau Z_2 - \tau S Z_1$ es **físicamente exacta y bit-a-bit congruente** con el update original.

3. **Cuello de Botella Secuencial en Reducción Gram:**
   - **Brecha:** Encontré un tercer cuello de botella masivo de CPU. Al fusionar los hilos en `S[j] += src[j]` (líneas 911-919), el hilo principal ejecuta $\sim 33$ millones de sumas escalares en solitario (para $K=512, N_{threads}=32$). Esto bloquea todo el pipeline.
   - **Solución:** Distribuir la reducción del tensor `arena` ($N_{threads} \times 4K^2$) explícitamente en el `#pragma omp parallel for` para que los núcleos limpien la memoria en paralelo.
