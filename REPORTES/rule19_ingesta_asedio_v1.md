# REPORTE DE INGESTA: ASEDIO RED-TEAM V1 (Regla 19)

**Fecha de Ingesta:** 14 de Septiembre de 2026
**Estado:** INGESTA ACTIVA (Generación de código BLOQUEADA bajo Regla 19)

## 1. Detección de Alucinaciones y Tautologías (Código del Monolito)
El escrutinio del Sabueso/IA ha expuesto fallas severas y falsificaciones en el código base (Monolito) actual:
*   **Falsificación de Pruebas (FRAUDE EVIDENTE):** La prueba de holonomía en el monolito está **FABRICADA**. Imprime `[PASSED] Traza de holonomía mantenida Pi/2 ± 1e-4` sin realizar ningún cálculo real.
*   **Falsa Transformada de Cayley:** La función denominada `cayley_step` no es una transformada de Cayley. Es un alias directo del mapa exponencial (Rodrigues), presentando una desviación analítica de `~0.01 rad`.
*   **Canal de Error Inexistente (Kahan Artifact):** `safe_geodesic(Inf)` no maneja el infinito por diseño. Devuelve `NaN` puramente por un artefacto aritmético de la suma de Kahan (`(inf-0)-inf=NaN`), no por una política de control. Esto significa que con `-ffast-math`, un input `Inf` colapsaría a una distancia válida engañosa.

## 2. Fallas Estructurales y Topológicas (Asedio a los 4 Contratos)
*   **CONTRATO 1 (Dominio y Distorsión):** 
    *   La función geodésica arroja basura numérica si recibe vectores no unitarios.
    *   El clamp de `1e-15` en FP32 es insuficiente para la distorsión antipodal, mostrando errores de hasta `1.41e-04` rad.
*   **CONTRATO 3 (Holonomía Real):** Al medir el transporte paralelo en un lazo cerrado con proyección tangente correcta, el error de cierre del lazo es catastrófico (`||s_final - s_inicial|| = 8.728e-01`).
*   **CONTRATO 4 (Alineación RDMA):** Ausencia total de `posix_memalign`, `mmap` o `VirtualAlloc`. El kernel C++ no está preparado para Zero-Copy real, cumpliendo apenas con la alineación de structs a 64B.
*   **Triton GPU Kernel:** Existe una divergencia semántica completa. Las normas de fila retornan `~0.34` (en lugar de `1.0`). El kernel de Triton jamás es invocado por el monolito para verificación cruzada.

## 3. Identificación de Cuellos de Botella y SOTA
*   **Deriva Numérica del Integrador (Riemannian Exp Map):** En el rastreo paso a paso (250 pasos), el ángulo acumulado experimenta una deriva masiva (`ratio = 0.739771` respecto a lo esperado) y la norma decae a `0.99999994`. La proyección tangente pierde velocidad.
*   **Sobrecarga Ctypes:** El script de Python experimentó un *Timeout* al intentar iterar `D=100,000` por 250 pasos debido a la sobrecarga del límite FFI (`ctypes`). Las evaluaciones asintóticas en alta dimensión deben empujarse al lado nativo (C++/Rust) para no saturar el orquestador 1D.
*   **Perfilado de Memoria (D=10,000):** La mutación `in-place` es `1.10x` más rápida que `memmove`, validando la necesidad de punteros inmutables Zero-Copy para PMTP.

## 4. Veredicto y Opciones de Diseño (Trade-offs)
1.  **Reescritura de Cayley:** Se debe implementar la VERDADERA transformada de Cayley-SMW en C++ y Rust para el step de integración, abandonando la aproximación de Rodrigues para garantizar `Drift=0.0`.
2.  **Manejo de Errores PMTP:** Reemplazar el "accidente numérico" por el retorno explícito de códigos de estado PMTP (`PMTP_ERR_COLLAPSE = -1`, `PMTP_ERR_NAN = -2`) propagados a través de las fronteras FFI.
3.  **Kernel de GPU Veto:** El kernel Triton actual debe ser marcado como *roto* y requiere reescritura.

---
*Fin del Bloque 1.*
