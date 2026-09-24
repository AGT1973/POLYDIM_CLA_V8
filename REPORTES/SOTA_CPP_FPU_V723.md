# REPORTE SOTA: PORTABILIDAD SIMD Y CONTROL FPU (FTZ/DAZ) CRUZADO
**ID de Reporte:** V723
**Protocolo Activo:** POLYDIM Core (Lógica Intuicionista, GCGT, Anti-Gusano 1D)
**Fecha:** 2026-09-14

---

## 1. MARCO EPISTEMOLÓGICO (COMPUTABILIDAD GEOMÉTRICA)

Bajo el paradigma de POLYDIM v2.0 y los Topos de Grothendieck, la portabilidad de código vectorial y el manejo de registros de punto flotante (FPU) no son problemas de "sintaxis", sino de **preservación isométrica sobre el manifold $\mathbb{S}^{D-1}$**. 

Los números subnormales (denormals) en el procesamiento tensorial causan latencias catastróficas porque fuerzan al hardware a abandonar las ALUs nativas y resolver el cálculo en microcódigo. Este fenómeno destruye la sincronicidad (isometría temporal) del flujo tensorial, provocando divergencias letales (el análogo de un "exploding gradient" temporal) al operar con Rotores Clifford en Fase Pura. Por tanto, el control estricto de las banderas FTZ (Flush-To-Zero) y DAZ (Denormals-Are-Zero) es un requerimiento fundamental, no una optimización opcional.

---

## 2. PORTABILIDAD SIMD C++: SOTA (Google Highway vs SIMDe)

Al evaluar el ecosistema SOTA para la construcción de kernels C++ portables, se contraponen dos filosofías arquitectónicas:

### A. SIMDe (SIMD Everywhere) - *El Enfoque Legacy / Mímico*
*   **Mecanismo:** Actúa como una "Piedra Rosetta". Si el código existe en intrínsecas x86 (AVX/SSE), SIMDe lo emula mapeándolo a intrínsecas de ARM (NEON/SVE) o WebAssembly.
*   **Crítica POLYDIM:** Constituye un "gusano" de traducción. Ata la formulación geométrica a la semántica de una ISA específica (x86), forzando a arquitecturas modernas (ej. ARM SVE) a emular cuellos de botella semánticos legacy.

### B. Google Highway - *El SOTA Geométrico (Aprobado)*
*   **Mecanismo:** Ofrece una abstracción C++ nativa, eficiente y agnóstica a la longitud del vector (*scalable vectors*). Un solo código fuente se compila para generar despachos dinámicos en tiempo de ejecución (Runtime Dispatch) óptimos para AVX-512, AVX2, ARM NEON, ARM SVE o RISC-V V.
*   **Veredicto POLYDIM:** **Highway es el estándar a adoptar.** Respeta la naturaleza tensorial pura (write once, run efficiently). Evita el "lowest common denominator" al mapear las operaciones matemáticas directamente a la capacidad máxima del hardware subyacente sin capas de emulación parasitarias.

---

## 3. CONTROL DE FPU CRUZADO (x86 vs ARM): FTZ y DAZ

Para evitar el colapso topológico inducido por subnormales, debemos forzar el hardware a un modo "RunFast", violando intencionalmente la norma IEEE 754 (que prioriza precisión infinitesimal sobre latencia asintótica). Este control es **Thread-Local**, por lo que cada hilo de trabajo (worker en PMTP) debe inicializar su estado al nacer.

### A. Implementación en x86 / x64 (Registro MXCSR)
El registro MXCSR controla el comportamiento de la FPU para instrucciones SSE/AVX. Se accede directamente mediante intrínsecas estándar de C++.

```cpp
#include <xmmintrin.h> // _mm_getcsr, _mm_setcsr
#include <pmmintrin.h> // Macros DAZ

inline void polydim_force_x86_runfast() {
    // Activa Flush-to-Zero (Resultados subnormales van a 0)
    _MM_SET_FLUSH_ZERO_MODE(_MM_FLUSH_ZERO_ON);
    // Activa Denormals-Are-Zero (Entradas subnormales se tratan como 0)
    _MM_SET_DENORMALS_ZERO_MODE(_MM_DENORMALS_ZERO_ON);
}
```

### B. Implementación en ARM / AArch64 (Registro FPCR)
ARM utiliza el *Floating-Point Control Register* (FPCR). A diferencia de x86, C++ no ofrece macros multiplataforma unificadas sin depender de intrínsecas específicas del compilador, por lo que el enfoque más robusto (Zero-Trust al compilador) es usar assembly en línea (`asm volatile`).

```cpp
#include <cstdint>

inline void polydim_force_arm_runfast() {
#if defined(__aarch64__)
    uint64_t fpcr;
    // Leer registro actual
    asm volatile("mrs %0, fpcr" : "=r"(fpcr));
    // Bit 24 controla FZ (Flush-To-Zero) en ARM
    fpcr |= (1ULL << 24); 
    // Escribir registro actualizado
    asm volatile("msr fpcr, %0" : : "r"(fpcr));
#elif defined(__arm__)
    uint32_t fpscr;
    asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
    fpscr |= (1U << 24);
    asm volatile("vmsr fpscr, %0" : : "r"(fpscr));
#endif
}
```

### C. El Peligro del Flag `-ffast-math`
**ADVERTENCIA (Anti-Hallucination):** No se debe confiar en el uso ciego del flag `-ffast-math` en GCC/Clang para resolver esto a nivel global. Dicho flag habilita reordenamientos asociativos que **destruyen la isometría unitaria y ortogonalidad** en cálculos de rotores Clifford (Fase Compleja). El seteo explícito de los registros (MXCSR / FPCR) en caliente mediante C++ inline es el único método que asegura el truncamiento de subnormales sin corromper el pipeline de validación matemática.

---

## 4. CONCLUSIÓN Y DIRECTRIZ DE INTEGRACIÓN

1. **Migración SIMD:** Cualquier núcleo de cálculo de alta dimensión que pretenda ejecutarse fuera de Triton (GPU) debe ser rescrito usando **Google Highway**.
2. **Aislamiento de FPU:** En los puentes FFI (Rust/C++) que leen los SlabAllocators de PMTP, debe invocarse la rutina de limpieza local (x86/ARM) inmediatamente después de levantar el hilo, garantizando que ninguna anomalía flotante cause un stall en la memoria compartida.
