# MULTI-AI TRIBUNAL VERDICTS (V770 -> V771)

## 1. El Límite de C++ vs BLAS (The Engineer's Tragedy)
El Tribunal falló que el Cache Blocking iterativo manual en C++ reduce latencias pero no puede igualar las optimizaciones de registro (AVX-512), *panel packing* y *micro-kernels* que `cblas_dgemm` y `cblas_dsyrk` hacen en lenguaje ensamblador. 
El tiempo masivo de computo de $X^\top X$ en V771 ($D=10k, K=256 \to 100s$) se debe al cuello de botella de la memoria. La Fase 2 debe integrar delegación explícita a la librería BLAS (OpenBLAS/MKL).

## 2. OpenMP Thread Spawning vs Pooling
El Tribunal corrigió el mito del OS creando/destruyendo hilos por cada loop. OpenMP utiliza un *Thread Pool*. El verdadero cuello de botella es la sincronización constante, barreras implícitas, y repetición de `#pragma omp parallel`.
*Solución Aprobada:* Abrir un único `#pragma omp parallel` general, delegar tareas con `#pragma omp for nowait` cuando sea posible sin dependencias, y evitar que el overhead domine en operaciones de microsegundos.

## 3. Caos Determinista en Coma Flotante
La no-asociatividad de la suma (ej. $10^{20} + -10^{20} + 1 = 0 \text{ ó } 1$) no es un bug multihilo, sino un fallo inherente al estándar IEEE-754 sumado al no-determinismo del SO a la hora de decidir el orden de finalización de hilos.
*Solución Aprobada:* Fase 2 requerirá un modo Dual: "Debug" (árbol de reducción fijo y reproducible bit-a-bit, pero lento) y "Performance" (Reducción atómica veloz con ruido estocástico aceptado mediante bandas de tolerancia).

## 4. La Tragedia de las Fronteras (Plano FFI)
El Tribunal corrigió el mito del GIL en `ctypes`. El problema no es el GIL (que ctypes libera), sino los cruces reiterados de la frontera FFI en un bucle *while*.
*Solución Aprobada:* Todo el Bucle de Control (el Plano de Control, iteraciones y `if error < tol`) debe descender a C++. Python debe ser estrictamente un orquestador inicial y un panel de visualización, no el motor de las iteraciones.
