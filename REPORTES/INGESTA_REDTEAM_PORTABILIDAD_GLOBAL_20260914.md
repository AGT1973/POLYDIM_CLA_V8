# INGESTA ANALÍTICA RED TEAM - AUDITORÍA DE PORTABILIDAD GLOBAL E INDUSTRIAL
**Fecha:** 2026-09-14
**Estado:** VETO ACTIVO (Regla 19 en efecto - Cero generación de código)

## 1. Detección de Falacias de Portabilidad (Anti-Hallucination)
- **La falacia de -march=native:** Compilar con optimizaciones nativas genera binarios incompatibles (SIGILL) en hardware antiguo o distinto. Para despliegue global, es obligatorio usar **Runtime Dispatch** (multiversioning).
- **La falacia del código #ifdef manual para SIMD:** Escribir y mantener intrínsecos de x86 y ARM a mano es inviable para producción. El estándar industrial es utilizar capas de abstracción zero-cost.
- **La ilusión de la portabilidad Triton:** API portable NO significa rendimiento portable. Un tamaño de bloque (*tile*) optimizado para el *warp* de 32 hilos de NVIDIA arruinará el rendimiento en el *wavefront* de 64 hilos de AMD. **El Autotuning (@triton.autotune) es mandatorio**.
- **NUMA y GPUDirect son ecosistemas fragmentados:** 
uma_alloc_onnode asume Linux x86; ARM requiere manejo distinto de page tables. GPUDirect exige APIs por fabricante (cudaHostRegister vs hipHostRegister vs zeMemAllocHost).

## 2. Elementos SOTA (State of the Art) Identificados
1. **Google Highway (hwy) o SIMDe:** Abstracciones SIMD *length-agnostic* que permiten escribir el kernel C++ una vez, y el compilador genera nativamente AVX-512, AVX2, NEON o SVE. *Highway* incluye la infraestructura de *Runtime Dispatch*.
2. **Arquitectura de Distribución Global (Wheels + CI Matrix):** El SOTA industrial (ej. llama.cpp) no depende de que el usuario recompile. El código fuente es empujado a una **CI Matrix** (GitHub Actions / GitLab CI) que prueba x86, ARM64, macOS y Windows simultáneamente, y emite *Wheels* (.whl) precompilados y bibliotecas compartidas para cada arquitectura.
3. **Autotuning Dinámico de Triton:** Cachear diferentes 	riton.Config para iterar en runtime sobre BLOCK y 
um_warps según las capacidades descubiertas del hardware.

## 3. Deduplicación y Filtro de Redundancias
- Se refina la política del FPU (FTZ/DAZ): en lugar de inyectar #error o #ifdef sueltos, se consolida la necesidad de un objeto FpGuard agnóstico que maneje _mm_setcsr en x86 y FPCR en ARM de forma encapsulada.

## 4. Conclusión de Alternativas (Vía Crítica)
- **El Trade-off Industrial:** Para pasar de un *Script de Laboratorio* a un *Producto de Industria*, debemos abandonar la compilación cruda (GCC directo) en favor de un sistema maduro (CMake + CI) que orqueste la detección de hardware, la compilación de variantes SIMD y el ensamblado de paquetes binarios distribuidos.
