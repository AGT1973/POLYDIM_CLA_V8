# Asymptotic Conditioning of Cayley Transform and CholQR on the Stiefel Manifold (D > 10000)

## 1. Asymptotic Bottlenecks and Conditioning for $D > 10,000$
In the high-dimensional regime ($D > 10,000$, often denoted $N \gg p$ or $D \gg K$), optimization on the Stiefel manifold $\mathcal{S}t(D, K) = \{ X \in \mathbb{R}^{D \times K} : X^T X = I_K \}$ requires highly stable retractions. The two dominant approaches—CholQR and the Cayley Transform—exhibit distinct asymptotic vulnerabilities.

### 1.1 CholQR Asymptotic Collapse
- **Mechanism:** CholQR computes the Gram matrix $G = X^T X$ ($\mathcal{O}(D K^2)$ operations), followed by the Cholesky decomposition $G = R^T R$ and inversion $Q = X R^{-1}$.
- **Numerical Collapse Trigger:** The condition number squares: $\kappa(G) = \kappa(X)^2$. If $\kappa(X) > u^{-1/2}$ (where $u$ is the unit roundoff, $\approx 10^{-8}$ in FP32 or $10^{-16}$ in FP64), the Cholesky decomposition breaks down due to apparent rank deficiency.
- **Orthogonality Loss:** The empirical loss of orthogonality scales as $\|Q^T Q - I\|_2 \approx \mathcal{O}(u \cdot \kappa(X)^2)$. In $D > 10,000$, accumulated roundoff in the inner products of the Gram matrix exacerbates this drift, leading to catastrophic collapse unless mitigated (e.g., via CholQR2, which applies the process twice).

### 1.2 Cayley Transform and Sherman-Morrison-Woodbury (SMW)
- **Mechanism:** The Cayley transform $Y = (I - \frac{1}{2}W)^{-1} (I + \frac{1}{2}W) X$ provides a retraction map avoiding matrix exponentials. For tangent vectors parameterized as low-rank updates $W = U V^T - V U^T$, SMW reduces the inversion from $\mathbb{R}^{D \times D}$ to $\mathbb{R}^{2K \times 2K}$.
- **Numerical Collapse Trigger:** While SMW completely removes $D$ from the inversion complexity (confining the solve to $\mathcal{O}(K^3)$ in L1 Cache), the explicit SMW formula is notoriously unstable. Small perturbations in the low-dimensional $2K \times 2K$ space exponentially amplify during the back-projection to the $D$-dimensional space.
- **Matrix-Free Instability:** Matrix-free implementations that rely on SMW without careful preconditioning or regularization suffer from orthogonality deterioration over successive iterations, which is a lethal flaw for continuous optimization on $\mathcal{S}t(D, K)$.

## 2. Verdict & SOTA Recommendations
1. **DRAM vs. Stability Trade-off:** CholQR2 solves the stability issue of CholQR but requires heavy $\mathcal{O}(D K^2)$ DRAM traffic to form the Gram matrix. 
2. **SMW Vulnerability:** SMW eliminates the DRAM bottleneck but introduces numerical instability in the $2K \times 2K$ inversion that violates the Stiefel constraints.
3. **Architectural Implication for POLYDIM:** For $K > 32$, direct SMW is mathematically elegant but empirically fragile. To survive $D > 10,000$, the $2K \times 2K$ solve must be protected by iterative refinement or replaced by a stabilized TRSM (Triangular Solve) forward substitution, avoiding explicit $L^{-1}$ inversion entirely.
