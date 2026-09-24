# POLÍTICA DE ARQUITECTURA SOTA: RETRACCIÓN CAYLEY-SMW EN STIEFEL St(D, K)
**Fecha:** 2026-09-19  
**Módulo:** Riemannian Stiefel Manifold Engine ($St(D, K)$)  
**Consenso Multi-IA:** Ariel + Red Team

---

## 1. El Límite de Escalabilidad de CholQR2 vs Cayley-SMW

| Métrica / Parámetro | CholQR2 por Bloques | Cayley Matrix-Free + SMW |
|---|---|---|
| **Régimen Óptimo** | $K \le 32$ (Agentes locales) | $K > 32$ ($K = 64, 128, 256$) |
| **Materialización de Gram $G = X X^T$** | Obligatoria en DRAM ($K \times K$) | **CERO (Matrix-Free en DRAM)** |
| **Cuello de Botella** | Memory-Bound (Tráfico DRAM en tiles) | Compute-Bound (L1/L2 Cache Solves) |
| **Complejidad de Memoria** | $\mathcal{O}(K \cdot D + K^2)$ | $\mathcal{O}(K \cdot D + (2K)^2)$ en registros |
| **Estabilidad Numérica** | Requiere 2 pasadas Cholesky | Exactamente isométrica (Unitaria) |

---

## 2. Formulación Matemática de Cayley-SMW

Para un enjambre de $K$ agentes $X \in \mathbb{R}^{K \times D}$ con gradiente tangente $\xi \in T_X St(D, K)$:
1. Se construye la matriz antisimétrica de bajo rango:
   $$W = U V^T - V U^T \in \mathbb{R}^{D \times D} \quad \text{donde } U = [P_X(\xi), X], \, V = [X, -P_X(\xi)] \in \mathbb{R}^{D \times 2K}$$
2. La retracción se evalúa mediante Sherman-Morrison-Woodbury:
   $$R_X(\xi) = X + U \left(I_{2K} - \frac{1}{2} V^T U\right)^{-1} V^T X$$
3. La inversión ocurre en un bloque diminuto de $2K \times 2K$ en **L1 Cache**, eliminando 14+ GB de tráfico DRAM en $D=10^6$.
