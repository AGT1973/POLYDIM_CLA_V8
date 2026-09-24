# INVESTIGACIÓN SOTA BG-03: ESTIMADOR DE CONDICIÓN O(N) Y FALLBACK CHOLQR2 -> SVD

**Fecha de Ingesta:** 2026-09-18
**Veredicto:** ACEPTADO. El cálculo explícito de $\kappa_2(A)$ (O(N^3)) destruye el propósito de CholQR2. Se debe usar un estimador adaptativo de dos niveles basado en la diagonal de R (O(N)) y el método iterativo de Hager-Higham (O(N^2)).

---

## 1. El Estimador Diagonal de Nivel 1 (Filtro Rápido O(N))
Sea $G = A^* A = R^* R$.
La diagonal de $R$ ofrece un indicador muy barato. Definimos:
$\eta = \frac{\max_i |r_{ii}|}{\min_i |r_{ii}|}$

La cota inferior es $\kappa_2(R) \ge \eta$. Por tanto, un valor grande de $\eta$ es garantía absoluta de mal condicionamiento. Un valor pequeño no garantiza buen condicionamiento, pero es una heurística excelente para descartar rápidamente el peor de los casos.

## 2. Escalera Adaptativa (Tiers)
* **Tier 0 (Filtro Diagonal):** Calcular $\eta$. Si $d_{min} == 0$, ir directo a MGS2.
* **Tier 1 (CholQR2 Rápido):** Si $\eta \le 10^4$, ejecutar CholQR2 y validar ortogonalidad $\delta_Q = \|Q^* Q - I\|_\infty$.
* **Tier 2 (Zona Ambigua y Shifted-CholQR2):** Si $10^4 < \eta < 10^8$, estimar $\kappa_1(R)$ con Hager-Higham (2-3 iteraciones, costo $O(N^2)$). Si es salvable, aplicar `Shifted-CholQR2`.
* **Tier 3 (MGS2):** Si $\eta \ge 10^8$ o la validación del Tier 1/2 falla, retroceder a MGS2 clásico.
* **Tier 4 (SVD 8x8):** Si MGS2 falla en el rango residual, usar SVD como último recurso (cero fallos).

## 3. Estimador de Nivel 2: Hager-Higham (O(N^2))
Solo se dispara en la zona ambigua. Resuelve sistemas triangulares $Ry = x$ y $R^*z = s$ sin invertir jamás $R^{-1}$ explícitamente. Es el estándar de LAPACK `xTRCON`.

```text
x = ones(N) / N
for k = 1,...,3:
    y = solve(R, x)
    est = ||y||_1
    s_i = sign(y_i)
    z = solve(R*, s)
    j = argmax_i |z_i|
    if |z_j| <= z* x:
        break
    x = e_j
kappa_est = ||R||_1 * est
```

## Referencias SOTA
* LAPACK xTRCON (Estimador de norma para matrices triangulares).
* Higham, N. J. (Estimadores iterativos de condición sin inversión explícita).
