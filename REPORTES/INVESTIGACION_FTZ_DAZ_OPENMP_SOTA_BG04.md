# INVESTIGACIÓN SOTA BG-04: CONCURRENCIA FTZ/DAZ EN OPENMP Y EL REGISTRO MXCSR

**Fecha de Ingesta:** 2026-09-18
**Veredicto:** CONFIRMADO. Riesgo arquitectónico latente de subnormales (100x penalty) si `enable_ftz_daz()` se llama solo en el hilo maestro.

---

## 1. El Problema del Registro MXCSR en OpenMP
El registro `MXCSR` de SSE/AVX (que controla Flush-To-Zero y Denormals-Are-Zero) es **thread-local**. 
Si se configura fuera de la región paralela, los *workers* creados o re-utilizados por OpenMP no heredan el valor automáticamente (el SO o el runtime de OpenMP no garantizan la copia del `MXCSR` del master a los threads esclavos).

Si aparece un valor `1e-310` y el worker no tiene el flag, el procesador caerá en microcódigo para resolver el subnormal, destruyendo el ancho de banda asintótico.

## 2. El Patrón Arquitectónico Seguro
El flag debe habilitarse **una sola vez por hilo**, **dentro** de la región `#pragma omp parallel`, pero **antes** del `#pragma omp for`.

```cpp
#include <xmmintrin.h>
#include <pmmintrin.h>

inline void enable_ftz_daz() {
    unsigned int mxcsr = _mm_getcsr();
    mxcsr |= (1u << 15) | (1u << 6); // FTZ | DAZ
    _mm_setcsr(mxcsr);
}

void computo_pesado() {
    #pragma omp parallel
    {
        // 1) CADA hilo configura su registro MXCSR al nacer/entrar
        enable_ftz_daz();

        // 2) Distribución del trabajo numérico
        #pragma omp for
        for (int i = 0; i < N; ++i) {
            // Operaciones FP seguras contra subnormales
        }
    }
}
```

## 3. Fuentes SOTA 2026 Confirmadas
* [RapidDocTools — Floating Point Precision: IEEE 754](https://rapiddoctools.com/blog/floating-point-precision-ieee754-software-engineering)
* [Allisone — Overflow and Underflow | Numerical Analysis Basics](https://www.allisone.co.jp/note/mathematics/numerical-analysis/basic/04_overflow-underflow_en)
* [Science Insights — What Is Underflow in Computing](https://scienceinsights.org/what-is-underflow-in-computing-causes-and-fixes/)
* [Martin Uke — Understanding Underflow](https://martinuke0.github.io/posts/2026-03-31-understanding-underflow-causes-consequences-and-mitigation-strategies/)
* [Dotune — Building a Cross-Platform DAW Engine](https://dotune.com/blog/mobile-real-time-audio-processing-lessons)
