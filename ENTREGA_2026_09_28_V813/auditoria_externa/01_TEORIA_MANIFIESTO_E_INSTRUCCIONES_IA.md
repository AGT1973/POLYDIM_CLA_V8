# 01. TEORÍA CONSTITUCIONAL, MANIFIESTO E INSTRUCCIONES PARA LA IA — POLYDIM V813

**Proyecto:** POLYDIM (Tesis Doctoral de Computabilidad Pluridimensional)  
**Autor:** Ariel García Traba  
**Versión de Producción:** V813 (Serie 800)  
**Fecha de Consolidación:** 2026-09-28  
**Marco Metodológico:** Regla 1 (Cero Adulación / Bulldog Red Team), Regla 19 (Ingesta Vectorial Silenciosa) & Regla 30 (Presunción Inviolable de Falla).

---

## 1. ¿A QUÉ VIENE EL PROYECTO POLYDIM? (MISIÓN ONTOLÓGICA)

La arquitectura de la inteligencia artificial convencional sufre de un estrangulamiento dimensional crítico: los modelos de lenguaje transforman el pensamiento y las representaciones multidimensionales en un **Gusano 1D de texto y tokens discretos**, perdiendo la geometría continua, la invariancia métrica y forzando una costosa reconstrucción semántica.

**POLYDIM** resuelve esta limitación mediante un paradigma de **Computación Cognitiva Nativa en Variedades de Alta Dimensión**:

```
                       ┌─────────────────────────┐
                       │   POLYDIM ARCHITECTURE  │
                       └────────────┬────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│ESPACIO       │             │ESPACIO       │             │ESPACIO       │
│PROBLEMA      │             │AGENTE        │             │COORDINACIÓN  │
├──────────────┤             ├──────────────┤             ├──────────────┤
│Tensores,     │             │Metas, Estado,│             │Emparejamiento│
│Señales,      │             │Incertidumbre,│             │Geodésico de  │
│Geometría     │             │Memoria       │             │Skills/Tools  │
└──────────────┘             └──────────────┘             └──────────────┘
```

1. **Espacio Latente Continuo:** Los estados cognitivos y el consenso inter-agente residen nativamente en la esfera unitaria $\mathcal{S}^{D-1}$ ($D \ge 10,000$) y en la variedad de Stiefel $St(D, K) = \{X \in \mathbb{R}^{D \times K} \mid X^T X = I_K\}$.
2. **Cero-Copia Inter-Procesos (PMTP Zero-Copy IPC):** Transferencia directa de tensores de alta dimensión a través de Memoria Compartida (`PmtpSlabAllocator` / Banked RCU de 3 épocas), sin serialización a JSON, Base64 ni colapso a texto.
3. **Vectorización de Habilidades (Skill Cards Contract):**
   - Una habilidad deja de ser sólo un prompt textual y se convierte en una coordenada en el espacio de capacidades.
   - **El Contrato Tripartito:** El **Vector** propone cercanía semántica; la **Metadata** define tipos, versiones y límites; la **Política** audita y aplica seguridad.
4. **Colapso a 1D Terminal:** El colapso a lenguaje natural o interfaz 2D/3D ocurre **únicamente al final del pipeline** como puente hacia el observador humano.

---

## 2. ARQUITECTURA MATEMÁTICA FORMAL (SERIE V813)

### A. Optimización sobre la Variedad de Stiefel $St(D, K)$
Para matrices ortonormales $X \in \mathbb{R}^{D \times K}$ ($K \le 64, D \ge 10^4$):

1. **Proyector Ortogonal Tangencial:**
   $$\Pi_X(Z) = Z - X \cdot \operatorname{sym}(X^T Z), \quad \operatorname{sym}(A) = \frac{1}{2}(A + A^T)$$
   Implementado con Kernel Fusion (`std::fma`) in-place $\mathcal{O}(D \cdot K)$ sin búferes temporales ni register spilling.

2. **Retracción Isométrica de Cayley-SMW:**
   $$R_X(\tau Z) = \left(I - \frac{\tau}{2} W\right)^{-1} \left(I + \frac{\tau}{2} W\right) X, \quad W = Z X^T - X Z^T$$
   Reducida a un sistema denso de rango bajo $2K \times 2K$ resuelto mediante eliminación Gaussiana con pivoteo parcial escalado y umbral de estabilidad $\tau = \text{scale} \cdot 10^{-12} + 10^{-15}$.

3. **Shifted CholQR2 con Regularización Tikhonov-Frobenius:**
   $$G = X^T X + \sigma I_K, \quad \sigma = \max(\lambda \|G\|_F, 10^{-14})$$
   Factorización de Cholesky $G = L L^T \implies Q = X L^{-T}$ con 2 iteraciones de refinamiento polar de Newton cuadrático ($Q_{k+1} = Q_k (1.5 I - 0.5 Q_k^T Q_k)$). Si algún pivote diagonal $\le 0$, aborta con `POLYDIM_STATUS_ERR_RANK_DEFICIENT` (cero trampas $10^{-300}$).

### B. Aritmética Exacta IEEE-754 y Sumas Compensadas
1. **Knuth TwoSum:** Descomposición exacta $a + b = s + t$ con `volatile double sum` para blindar la cancelación contra optimizaciones del compilador.
2. **DSYRK Neumaier 2-Pass:** Acumulación compensada de la matriz Gramiana en registros $\mathcal{O}(1)$ memoria dinámica, eliminando alocaciones de heap por hilo.

### C. Topología Homológica y Consenso Métrico
1. **Guardián Topológico Rust (DSU Iterativo):** Cálculo de Betti-0 ($B_0$) y ciclos independientes Betti-1 ($B_1 = |E| - |V| + B_0$) a escala $V = 10^6$ nodos con $\mathcal{O}(1)$ pila y deduplicación de aristas.
2. **Filtro Fréchet-Betti:** Particionamiento Random Projection Tree con vector unitario ($v \leftarrow v / \|v\|$), algoritmo de Weiszfeld esférico con manejo de singularidad Vardi-Zhang y quórum de supermayoría $3a \ge 2n$.

---

## 3. CONTRATO DE SILICIO Y ESPECIFICACIÓN DE COMPILACIÓN

- **Compilador C++:** WinLibs MinGW64 GCC 14.2.0 (`-shared -O3 -fno-fast-math -fno-associative-math -fopenmp -march=native -msse2 -mavx2 -std=c++17 -lwinpthread`).
- **Compilador Rust:** Rustc 1.98.1 (`--edition 2021 --crate-type cdylib -C opt-level=3 -C panic=unwind -C target-feature=+crt-static`).
- **Alineación de Memoria:** Búferes alineados a 64 bytes. Structs ABI empaquetados estrictamente a 8 bytes (`#pragma pack(push, 8)`). Structs Rust forzados a exactamente 128 bytes mediante `#[repr(C, align(8))]` y static asserts.
- **Firewalls FFI:** C++ envuelto en `try { ... } catch (...)`; Rust envuelto en `ffi_guard!` (`catch_unwind`).

---

## 4. INSTRUCCIONES DE INVOCACIÓN PARA CUALQUIER IA EXTERNA

Al analizar este código, toda IA debe asumir:
1. **Nivel PhD / SOTA:** No explicar conceptos básicos de álgebra lineal o C++.
2. **Cero Sesgo de Complacencia:** Atacar el código asumiendo que está roto hasta certificar numéricamente su estabilidad.
3. **Cero Trampas:** Prohibido inventar atajos algebraicos (como Rodrigues en $K>1$) o trampas numéricas ($10^{-300}$).
4. **Honestidad Métrica:** Distinguir rigurosamente entre clustering métrico y BFT, y entre rango de ciclos de grafo y filtración homológica persistente continua.
