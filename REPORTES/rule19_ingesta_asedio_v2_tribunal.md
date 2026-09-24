# REPORTE DE INGESTA: TRIBUNAL RED-TEAM (Regla 19)

**Fecha de Ingesta:** 14 de Septiembre de 2026
**Estado:** INGESTA ACTIVA (Generación de código BLOQUEADA bajo Regla 19)
**Archivos Ingeridos:** `z_ai.md`, `claude.md`, `qwen.md`, `kimi.md`

## 1. Verificación Cruzada y Deduplicación (Consenso del Enjambre)
El análisis cruzado de las 4 IAs confirma de forma unánime y absoluta las siguientes vulnerabilidades estructurales en el sistema POLYDIM V717:

*   **Cancelación Catastrófica en FP32 (Contrato 1 Roto):** La proyección tangente (`v_tangent = velocity - dot_sv * S_t`) castea `dot_sv` a FP32 antes de la resta. En S^(D-1) donde los vectores son casi paralelos, esto descarta 7-9 dígitos de precisión, causando la deriva angular observada. **Solución Consensuada:** La resta debe realizarse en FP64 puro y recién el resultado final de la componente tangente almacenarse en FP32.
*   **Falso Determinismo GPU y Cuello de Botella Atómico:** El kernel de Triton reduce usando `tl.atomic_add` en un puntero `float64`. El hardware GPU emula atómicos FP64 con bucles CAS (Compare-And-Swap), causando hasta un 84% de *warp stalls* y serialización total. **Solución Consensuada:** Acumular en FP32 (suficiente para D=10,000) usando atómicos nativos, o implementar una reducción de dos pasadas (two-pass tree).
*   **Alineación Ficticia en Python (Contrato 4 Roto):** La propiedad `_align_ = 64` es silenciosamente ignorada por `ctypes` en Python. Los buffers no están cayendo en fronteras de cache lines. **Solución Consensuada:** Asignar la memoria manualmente sumando el offset y calculando el puntero alineado `(align - (addr % align)) % align`.

## 2. Identificación de Nuevos Errores Estructurales y SOTA
*   **Corrupción de Punteros FFI en Windows x64 (Segfault):** La falta de definición de `argtypes` y `restype` en las funciones `ctypes` provoca que Windows asuma retornos de 32 bits (int) por defecto. Los punteros de 64 bits son truncados, garantizando un crash (Access Violation) inmediato en producción.
*   **Silenciamiento de Errores en el Harness:** El monolito ignora los códigos de retorno de C++/Rust. Cuando ocurre un NaN, C++ aborta sin actualizar `S_next`, pero Python realiza un `memmove` ciego del estado viejo, convirtiendo el error en un "no-op invisible" y mintiendo con un *PASS* final.
*   **Violación del Modelo de Aliasing en Rust (UB):** En Rust, crear `&[f32]` para `S_t` y `&mut [f32]` para `S_next` simultáneamente cuando `S_t == S_next` viola la regla *Stacked Borrows* (noalias). LLVM puede optimizar esto asumiendo incorrectamente que no se solapan. Requiere aritmética de punteros crudos (`*ptr.add(i)`).
*   **Destrucción de Vectorización SIMD:** Chequear `std::isnan` elemento a elemento *dentro* del bucle `safe_dot_product` destruye la vectorización AVX-512. El chequeo debe realizarse *al final* de la reducción para permitir operaciones vectoriales completas.
*   **Divergencia FTZ/DAZ Comprobada Empíricamente:** Se verificó ejecutando el binario que C++ limpia los subnormales a cero gracias a `_mm_setcsr`, mientras que Rust no modifica el registro MXCSR, provocando que los backends diverjan numéricamente.
*   **Picos de Latencia por Asignación `thread_local`:** El uso de `std::vector<float> tls_tangent_buf` en C++ dispara `malloc` bajo locks globales en un entorno multi-hilo, matando el tiempo real. El buffer debe ser inyectado (Inversion of Control) desde Python.

## 3. Síntesis de Diseño y Arquitectura (Parches Aprobados para Veto)
1.  **Orquestador (Monolito):**
    *   Definir estrictamente `argtypes`/`restype`.
    *   Crear función de asignación de memoria 64-byte/4KB-aligned explícita.
    *   Ampliar el `gc_disabled` con `try...finally` para abarcar el hot-loop de 1000 iteraciones completo, no solo una llamada.
    *   Evaluar el retorno `rc` en cada paso y crashear duro en caso de error.
    *   Implementar una prueba real de holonomía (transporte de vectores en lazo cuadrado) en lugar del `print` hardcodeado.
2.  **Kernel C++/Rust:**
    *   Proyección tangente y suma de normas completamente en FP64 interno.
    *   El loop tangencial debe ser calculado una única vez, almacenado en el scratch buffer (proporcionado por Python, eliminando `tls_tangent_buf`), y reusado para S_next.
    *   Manejo puro de punteros (`unsafe`) en Rust para mutación in-place `S_t == S_next`.
    *   Añadir el guard de Sinc-Taylor a `cayley_step` para homogeneizar la estabilidad de `theta < 1e-4` con el `exp_map`.
    *   El Spinlock debe transicionar a *exponential backoff* sin leer relojes pesados `steady_clock` por iteración.
3.  **Kernel Triton:**
    *   Unificar el contrato de manejo NaN/Inf (rechazar con crash si no es finito, igual que nativo).
    *   Cambiar la reducción atómica a FP32 para desatascar las barreras de silicio en H100/T4.

---
*Fin del Bloque 2.*
