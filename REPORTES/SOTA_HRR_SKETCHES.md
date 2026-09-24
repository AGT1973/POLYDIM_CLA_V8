# 🧨 VETO EMPÍRICO Y DESTRUCCIÓN DE LA NARRATIVA FWHT: LÍMITES ASINTÓTICOS Y ALTERNATIVAS SOTA $O(D)$

**Modo:** BULLDOG CRITIC / RED TEAM (Nivel SOTA / PhD)
**Target:** POLYDIM (Geometría Hiperdimensional $S^{D-1}$, PMTP Zero-Copy IPC)
**Tópico:** Obsolescencia de Fast Walsh-Hadamard Transform (FWHT) en FJLT y HRR.

---

## 1. HRR (Holographic Reduced Representations): Muerte del $O(D \log D)$

La narrativa de que HRR requiere Fast Fourier Transform (FFT) o FWHT para implementar la operación de *binding* (convolución circular) en $O(D \log D)$ está matemáticamente obsoleta en el contexto SOTA de Vector Symbolic Architectures (VSA).

**Evidencia de Sustitución:**
- **Multiply-Add-Permute (MAP) / Fractional HRR:** Modelos paralelos de VSA demuestran que el *binding* puede realizarse mediante operaciones de producto Hadamard (elemento a elemento) y permutaciones cíclicas.
- **Complejidad Asintótica:** El *binding* en MAP es estrictamente $O(D)$. Al evitar el dominio de Fourier, se elimina el peaje topológico del $\log D$.
- **Veredicto:** Seguir utilizando FWHT/FFT para el *binding* en un motor que opera a $D \ge 10,000$ (y escala a $10^6$ o $10^7$) es un desperdicio asintótico injustificable. La robustez frente al ruido y la capacidad del espacio de memoria distribuida se conservan teóricamente equivalentes bajo MAP.

## 2. FJLT y la Ilusión de la Dispersión de Energía

El pipeline clásico de Ailon-Chazelle (FJLT) realiza $x \to P H D x$, utilizando FWHT ($H$) para la dispersión densa de energía (*energy dispersion*) en $O(D \log D)$ antes de aplicar la proyección dispersa ($P$). 

**¿Es FWHT el límite asintótico para dispersión de energía densa?**
Sí, desde un punto de vista puramente topológico: un circuito de grado acotado que conecta todas las $D$ entradas con todas las $D$ salidas (para garantizar que cada coordenada se mezcle uniformemente y acotar la norma infinito) requiere obligatoriamente una profundidad de $O(\log D)$, lo que resulta en $O(D \log D)$ aristas. No existe una transformación ortogonal densa (isometría estricta) que distribuya globalmente la energía en tiempo computacional puro $O(D)$.

**Pero la premisa es incorrecta (Destrucción del Paradigma):**
No necesitas dispersión de energía densa si atacas el problema desde el límite de *Sparse Johnson-Lindenstrauss* (Kane & Nelson, 2014).

- **Kane-Nelson Sparse JL:** Demuestra empíricamente y teóricamente que se puede alcanzar una proyección directa utilizando una matriz dispersa con cardinalidad por columna de $s = O(\epsilon^{-1} \log(1/\delta))$. 
- **Cálculo Asintótico:** Aplicar esta matriz toma exactamente $O(D \cdot s)$ operaciones. 
- **El Punto de Quiebre (The Tipping Point):** Para dimensiones hiperdimensionales masivas $D \gg 10^5$, el término $s$ es constante y dominado por la distorsión deseada $\epsilon$ y la probabilidad de falla. Por tanto, el Sparse JL se ejecuta en **$O(D)$ tiempo de aplicación**, venciendo asintóticamente a la supuesta necesidad del FWHT ($O(D \log D)$).

## 3. Nuevos Sketches Deterministas y Tensores Estructurados

Para evadir completamente la aleatoriedad dependiente del espacio y acelerar la proyección:
- **TensorSketch / Khatri-Rao:** Si los vectores de entrada exhiben estructura (ej. productos Kronecker), los tensores de proyección aleatoria estructurada alcanzan sub-linealidad o proyección paralela $O(D)$ exacta, sin pasar por el cuello de botella del Walsh-Hadamard.
- **Expander Graphs:** Mientras los grafos expansores locales (grado $O(1)$) garantizan la proyección local $O(D)$, no logran la mezcla global *sin* acumular $O(\log D)$ capas. Su utilidad SOTA radica en el *hashing* rápido (como CountSketch para distancias específicas), no en isometría esférica uniforme.

## CONCLUSIÓN Y MANDATO (ACTIONABLE VETO)

1. **HRR:** Destruye el motor FWHT para convolución en memoria latente. Migra inmediatamente a operaciones **MAP (Multiply-Add-Permute)** con binding Hadamard en $O(D)$.
2. **FJLT / DimRed:** Elimina el paso pre-condicionador de FWHT si tu régimen de $D$ es masivo. Implementa **Sparse JL (Kane-Nelson)** directo. FWHT es un relicario $O(D \log D)$ de los 2000s, hoy superado por bounds de dispersión adaptativa y VSA de producto puntual. No pagues un peaje espectral si solo requieres isometría estocástica acotada.

*Certificado por evaluación analítica y bibliografía SOTA (Kane & Nelson 2014; HDC MAP paradigm).*
