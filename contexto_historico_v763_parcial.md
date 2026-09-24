# Checkpoint de Transición: POLYDIM V763 (Fase de Parcheo)

## 1. Estado Actual
- **Directorio V763 creado**: E:\POLYDIM_EINSOF\ENTREGA_2026_09_19_V763
- **Evaluación del Tribunal Completada**: Se destilaron los 5 hallazgos críticos reales (PMTP SPSC, FFI ABI, Stiefel Tangente, Neumaier Branchless, OpenMP) y se descartaron las alucinaciones (Coq, Shannon, etc.).
- **Parches ya aplicados**:
  1. Firmas de FFI en Python (polydim_v763_monolito.py) corregidas (de 6 a 8 argumentos, None inyectados).
  2. Integración de VerifyReport en el FFI de Rust desde Python.
  3. Betti-1 purgado del puente Python.
  4. Acumulador Neumaier hecho 100% branchless (Knuth TwoSum) en src/polydim_kernel.cpp.

## 2. Tareas Pendientes Inmediatas (P0) para la Nueva Sesión
Al arrancar la nueva sesión, el agente debe aplicar exactamente estos dos parches en src/polydim_kernel.cpp usando Python scripts con lectura/escritura (sin comillas anidadas problemáticas) o eplace_file_content:

### A. PMTP Wait-Free SPSC Triple Buffer
Reemplazar struct PMTP_Control y sus 5 funciones asociadas por un estado atómico único de 8 bits: std::atomic<uint8_t> state. 
- egin_write: extrae bits 4-5.
- commit_write: swap de newest (4-5) y middle (2-3), marcando el bit 6 como resh.
- cquire_read: si bit 6 está activo, swap de middle (2-3) y oldest (0-1).
- Esto elimina el 98.7% de desgarros reportados por el tribunal.

### B. Retracción Tangente en Cayley-SMW
En polydim_stiefel_cayley_smw_f64, justo antes de computar Y_out = X + tau * U * Z:
- Modificar el bloque $ (las filas  \dots 2K-1$ de $) inyectando  \leftarrow Z_2 - \frac{1}{2} X^T G Z_1$.
- Como el kernel ya calcula ^T G$ y lo deposita en el bloque asimétrico superior de la matriz $ auxiliar, se puede reutilizar directamente para la resta geométrica {new} = G - \frac{1}{2}X(X^TG)$, restaurando la derivada direccional /d\tau = G$.

### C. Hardening FFI (C++ / Rust / Dart)
- Agregar __restrict__ en las firmas de polydim.h y src/polydim_kernel.cpp.
- Ajustar firmas de Dart.
- Compilar V763 y verificar Exit Code 0.

## 3. Reglas a Invocar
- Leer Regla 0 y este archivo.
- Retomar inmediatamente el parcheo de PMTP y Stiefel.
