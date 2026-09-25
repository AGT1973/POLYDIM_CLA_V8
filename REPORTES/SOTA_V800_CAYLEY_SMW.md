# 🏛️ INGESTA SOTA V800: CAYLEY-SMW MATRIX-FREE (STIEFEL RETRACTION)
**Fecha:** 2026-09-24
**Módulo:** Geometría Riemanniana / Retracción Stiefel $St(D, K)$
**Escala:** $D = 10^7, K = 512$

## 1. El Problema (OOM de la Proyección Densa)
La retracción de Cayley estándar materializa la matriz $W = \xi X^\top - X \xi^\top$ o matrices densas proporcionales a $D \times D$. Para $D=10^7$, esto es $10^{14}$ flotantes, lo cual es incomputable.

## 2. Solución Analítica: Sherman-Morrison-Woodbury (SMW) de Rango $2K$
El operador $W$ es asimétrico y de rango $\le 2K$. 
Factorización exacta: $W = U V^\top$, donde $U, V \in \mathbb{R}^{D \times 2K}$.
$$ U = [\xi, -X], \quad V = [X, \xi] $$

Aplicando la identidad SMW a la inversa de Cayley $(I - \frac{1}{2} W)^{-1}$:
$$ (I - \frac{1}{2} U V^\top)^{-1} = I + \frac{1}{2} U \underbrace{\left(I_{2K} - \frac{1}{2} V^\top U \right)^{-1}}_{M^{-1} \in \mathbb{R}^{2K \times 2K}} V^\top $$

**Reducción Asintótica:** Toda la inversión pesada se reduce a invertir $M$, que es de $2K \times 2K$. Para $K=512$, $M$ es $1024 \times 1024$ ($\approx 8$ MB en FP64). Esta matriz vive eternamente en L2/L3 Caché, **nunca en DRAM**.

## 3. Arquitectura Tiling 2-Pass Cache-Aware (L1/L2)
**Pase 1: Acumulación de Bloques L2**
- Bloques de $B \approx 8192$ filas. 
- Calcular dinámicamente $U_i$ y $V_i$ del bloque (tamaño $B \times 2K$).
- Acumular matrices pequeñas `VtU += Vi^T * Ui` y `VtX += Vi^T * Xi`. (Total $2K \times 2K$).

**Pase 2: Resolución $M^{-1}$ y Streaming de Bloques L2**
- El Orquestador o Hilo Maestro invierte $M = (I_{2K} - 0.5 \cdot VtU)$ en L2 Caché.
- En paralelo, cada hilo vuelve a procesar su bloque $B$:
  $$ \Delta_i = U_i \cdot \left[ M^{-1} \left( V_i^\top X + \frac{1}{2} V_i^\top U (\dots) \right) \right] $$
  $$ X_{new}[i] = X_i + \Delta_i $$

## 4. Complejidad Lograda
- **Flops:** $O(D K^2)$ (Lineal en $D$).
- **Memoria Auxiliar (RAM):** $O(B K)$ (Limitada al Tiling L2 por hilo, erradicando el uso masivo de DRAM).
- **Ancho de Banda:** $O(D K)$ (Solo 2 pasadas sobre $X$ y $\xi$).

## 5. Implementación en C++ / OpenMP
Se inyectará un kernel fusionado donde `build_UV` y el producto BLAS-3 subyacente operen localmente en el TLS (Thread Local Storage) evitando falsos compartir y overhead de asignación en el heap. 
