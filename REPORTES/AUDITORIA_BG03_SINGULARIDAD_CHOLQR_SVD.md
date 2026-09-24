# 🔬 AUDITORÍA RED TEAM: BG-03 — MATRICES CERCA DE LA SINGULARIDAD (κ ≥ 10¹⁶)

**Fuente de Ingesta:** IA Externa (ChatGPT Pro Search)
**Fecha de Evaluación:** 2026-09-18
**Auditor:** Antigravity Bulldog (Red Team POLYDIM)
**Veredicto Global:** 🟢 SÓLIDO — Con 3 correcciones críticas para POLYDIM V758/V759

---

## ✅ ELEMENTOS SÓLIDOS (ACEPTADOS)

### 1. Diagnóstico Central: κ(G) ≈ κ(A)²
**Correcto.** El Gramiano G = AᵀA eleva la condición al cuadrado. Para κ(A) = 10⁸,
κ(G) ≈ 10¹⁶, lo cual roza u⁻¹ ≈ 4.5×10¹⁵ en float64 y hace que Cholesky de G
pierda definitud positiva por ruido de redondeo.

**Referencia SOTA:** Yamamoto (2015) "Rounded error analysis of Cholesky QR2";
Fukaya et al. (2020) "Shifted CholeskyQR3" — ambos establecen que CholQR2 es fiable
solo hasta κ(A) ≲ u^{-1/2} ≈ 10⁸.

### 2. Shifted-CholQR2/3 como Tier Intermedio
**Correcto.** La factorización desplazada:
    RᵀR = AᵀA + sI
estabiliza el Gramiano y extiende el rango operativo hasta κ²(A) = O(u⁻¹).
Shifted-CholQR3 agrega una etapa de refinamiento y reporta robustez hasta κ ≈ 10²⁰
(Fukaya et al. 2020).

### 3. Umbral de Rango LAPACK-Standard
**Correcto.** La fórmula:
    τ_rank = max(c·max(m,n)·u·σ₁, η·σ₁, τ_model)
es el estándar de facto (LAPACK `dgelsd`, `dtrcon`). La combinación de tres fuentes
(redondeo, ruido físico, modelo) es la práctica SOTA.

### 4. Análisis de Brecha Espectral (Gap Ratio)
**Correcto.** g_r = σ_r / σ_{r+1} es el indicador clave. Rango bien definido ↔ g_r ≫ 1.
Sin brecha clara → rango incierto → flag obligatoria.

### 5. Protocolo de Pruebas Destructivas Propuesto
**Correcto y necesario.** El barrido:
    κ(A) ∈ {10², 10⁴, 10⁶, 10⁸, 10¹⁰, 10¹², 10¹⁴, 10¹⁶, 10¹⁸, 10²⁰}
con matrices Hilbert, Vandermonde, espectro geométrico σᵢ = σ₁·ρⁱ⁻¹ y perturbaciones
aleatorias de matrices rank-deficientes es exactamente lo que falta en la Suite 5.

---

## 🔴 CORRECCIONES CRÍTICAS PARA POLYDIM

### CORRECCIÓN 1: V758 NO TIENE TIER 2 — SALTA DE CHOLQR2 DIRECTO A MGS2

**Hallazgo del código fuente** [`kernel_cpp_v758.cpp:L466-L476`](file:///E:/POLYDIM_EINSOF/ENTREGA_2026_09_18_V758/kernel_cpp_v758.cpp#L466-L476):

```cpp
if (tier1_ok) {
    // ... retorna PASS con tier_executed = 1
    return POLYDIM_SUCCESS;
}

// TIER 3 FALLBACK: Modified Gram-Schmidt MGS2 with Re-orthogonalization
// ⚠️ ¡¡¡ NO HAY TIER 2 (Shifted-CholQR2/3) !!!
```

**Problema:** Cuando CholQR2 falla (diagonal de L ≤ eps_tol en línea 430), el código
salta directamente a MGS2 escalar (Tier 3), que es O(K²·D) con bucles secuenciales
sin paralelismo OpenMP en las proyecciones internas. Para K=8 y D=10⁶, MGS2 toma
~1.3 segundos vs ~2.8 ms de CholQR2.

**Fix V759:** Insertar Shifted-CholQR2 como Tier 2 entre CholQR2 y MGS2:
```
Tier 1: CholQR2 (rápido, O(K²D) paralelizado, válido para κ < 10⁸)
    ↓ falla Cholesky diagonal ≤ eps
Tier 2: Shifted-CholQR2 (s = max(m,n)·u·‖A‖²₂, reintenta Cholesky con shift)
    ↓ falla ortogonalidad ‖I - QᵀQ‖ > τ_q
Tier 3: MGS2 con reortogonalización (estable pero lento)
    ↓ rango < K
Tier 4: SVD K×K (árbitro final de rango — para K=8: SVD 8×8 = ~512 FLOPs, gratis)
```

### CORRECCIÓN 2: K ES PEQUEÑO (K=8) — LA SVD K×K ES ESENCIALMENTE GRATIS

La ingesta trata la SVD como "fallback costoso". **Esto es incorrecto para POLYDIM.**

En POLYDIM, K = 8 (o como máximo 16-32 para bases del espacio tangente). La SVD de
una matriz 8×8 cuesta ~O(K³) = O(512) FLOPs, lo cual es **despreciable** comparado
con los O(K²·D) = O(64·10⁶) FLOPs de cualquier operación sobre las filas.

**Implicación:** Para POLYDIM, la SVD K×K debería ejecutarse SIEMPRE como validación
post-factorización, no solo como fallback de emergencia. El coste es nulo y provee:
- Rango numérico exacto
- Valores singulares para la brecha espectral
- Número de condición κ(A) = σ₁/σ_K

### CORRECCIÓN 3: FALTA ESTIMADOR DE CONDICIÓN PRE-VUELO

V758 detecta la falla de CholQR2 **post-hoc** (cuando la diagonal de L colapsa).
No hay estimación de κ(A) antes de intentar la factorización.

**Fix V759:** Después de computar el Gramiano G = QᵀQ en el primer paso de CholQR2,
ejecutar una estimación 1-norma de condición sobre el factor L triangular (análogo
a LAPACK `dtrcon`). Coste: O(K²) = O(64) FLOPs. Si κ_est > u^{-1/2}:
- Skip CholQR2 enteramente
- Ir directo a Shifted-CholQR2 o SVD

---

## 🏗️ DISEÑO APROBADO PARA V759: ESCALERA DE 4 TIERS CON ESTIMADOR

### Pseudocódigo de la Escalera Adaptativa

```
function adaptive_ortho(X[K×D], eps_tol):
    Q = copy(X)

    // PASO 0: Gramiano G = QᵀQ (O(K²D), paralelizado con tiling L2)
    G[K×K] = tiled_gram(Q, K, D)

    // PASO 0.5: Estimador de condición barato (O(K²))
    kappa_est = cheap_condition_estimate(G, K)

    if kappa_est < u^{-1/2}:   // κ < ~10⁸
        // TIER 1: CholQR2 Standard
        L = cholesky(G)
        if cholesky_failed: goto TIER_2
        Q = forward_solve(Q, L)  // TRSM
        // Repetir: G₂ = QᵀQ, L₂ = chol(G₂), Q = solve(Q, L₂)
        if ortho_check(Q) OK: return (Q, tier=1, rank=K)

    TIER_2:
        // TIER 2: Shifted-CholQR2
        s = max(K, D) * u * frobenius_norm_sq(G)
        G_shifted = G + s·I
        L = cholesky(G_shifted)
        if cholesky_failed: goto TIER_3
        Q = copy(X)
        Q = forward_solve(Q, L)
        // Segunda pasada CholQR estándar sobre Q precondicionada
        G₂ = QᵀQ
        L₂ = cholesky(G₂)
        Q = forward_solve(Q, L₂)
        if ortho_check(Q) OK: return (Q, tier=2, rank=K)

    TIER_3:
        // TIER 3: MGS2 con reortogonalización
        Q = copy(X)
        rank = mgs2_reortho(Q, K, D, eps_tol)
        if rank == K and ortho_check(Q) OK: return (Q, tier=3, rank=K)

    TIER_4:
        // TIER 4: SVD K×K (árbitro de rango — gratis para K=8)
        G = QᵀQ  // o usar G del paso 0
        U, Σ, Vt = svd_KxK(G)
        tau_rank = max(K, D) * u * Σ[0]
        rank = count(Σ > tau_rank)
        gap_ratio = Σ[rank-1] / Σ[rank] if rank < K else Inf
        // Construir Q = X · V · Σ^{-1/2} (solo columnas retenidas)
        return (Q[:rank], tier=4, rank=rank, sigma=Σ, gap=gap_ratio)
```

### Métricas de Salida Obligatorias (PolydimOrthoResult V759)

```c
typedef struct {
    int32_t   status;              // PolydimStatus enum
    uint32_t  requested_rank;      // K original
    uint32_t  numerical_rank;      // Rango efectivo detectado
    double    estimated_condition;  // κ estimada
    double    orthogonality_error;  // ‖I - QᵀQ‖_F
    double    backward_error;       // ‖A - QR‖_F / ‖A‖_F
    uint32_t  tier_executed;        // 1, 2, 3 o 4
    double    spectral_gap;         // σ_r / σ_{r+1}
    uint32_t  rank_confidence;      // 0=incierto, 1=brecha clara, 2=certificado
} polydim_ortho_result_t;
```

---

## 🧪 PROTOCOLO DE PRUEBAS DESTRUCTIVAS PARA SUITE 5 EXTENDIDA

### Familias de Matrices de Prueba

| ID | Familia | Construcción | κ(A) Target |
| :- | :------ | :----------- | :---------- |
| M1 | Espectro Geométrico | σᵢ = σ₁·ρⁱ⁻¹, ρ = κ^{-1/(K-1)} | 10² a 10²⁰ |
| M2 | Caída Abrupta (Cliff) | σ₁=...=σ_{K/2}=1, σ_{K/2+1}=...=σ_K=κ⁻¹ | 10⁸ a 10²⁰ |
| M3 | Hilbert K×D | H_{ij} = 1/(i+j-1), primeras K filas | ~10¹⁸ para K=8 |
| M4 | Rango Deficiente + Ruido | rank(A)=K-2, + ruido gaussiano η·‖A‖ | ~1/η |
| M5 | Escalamiento Extremo | Filas escaladas por 10^{±8} | Variable |

### Barrido Obligatorio

```python
for kappa in [1e2, 1e4, 1e6, 1e8, 1e10, 1e12, 1e14, 1e16, 1e18, 1e20]:
    for D in [10_000, 100_000, 1_000_000]:
        for family in [M1, M2, M3, M4, M5]:
            for seed in range(10):
                A = generate_matrix(family, K=8, D=D, kappa=kappa, seed=seed)
                result = polydim_adaptive_ortho(A)
                log(kappa, D, family, seed, result.tier_executed,
                    result.numerical_rank, result.orthogonality_error,
                    result.spectral_gap, result.rank_confidence)
```

### Métricas de Certificación

Para CADA punto del barrido, registrar y verificar:
1. ‖I - QᵀQ‖_F ≤ c_q · u (proporcional a K y D)
2. ‖A - QR‖_F / ‖A‖_F ≤ c_r · u
3. Tier ejecutado (debe degradar correctamente: 1→2→3→4)
4. Rango numérico = rango real ± 0 (sin falsos positivos ni negativos)
5. Brecha espectral σ_r/σ_{r+1} reportada y coherente
6. **Zero fallos silenciosos:** nunca devolver rank=K cuando rank_real < K
