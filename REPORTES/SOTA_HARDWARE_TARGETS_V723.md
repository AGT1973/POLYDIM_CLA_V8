# SOTA HARDWARE TARGETS (POLYDIM V723)
**Fecha de Ingesta:** 2026-09-14
**Objetivo:** Viabilidad de despliegue de la arquitectura POLYDIM (Cayley Retraction + Doble Gram-Schmidt) en clústeres HPC externos.

## 1. Kaggle (NVIDIA GPUs & CPU Standard)
- **Triton (GPU):** Viable y nativo. Las GPUs T4/L4 soportan CUDA y la pila MLIR/LLVM de Triton.
- **C++ / Rust (CPU):** Viable mediante compilación JIT/Caliente en celdas de notebook (`subprocess.run`). Requiere compiladores de Linux (`g++ -O3 -march=native -fopenmp`, `cargo build --release`). 
- **Memoria:** El orquestador basado en `mmap` anónimo para asignar bloques alineados a fronteras de página operará con máxima eficiencia bajo el kernel de Linux.

## 2. Cerebras CS-3 (Wafer-Scale Engine)
- **El Paradigma:** No es una GPU Von Neumann. Es un flujo de datos (Dataflow) masivo en una malla 2D con cientos de miles de núcleos. Carece de memoria compartida global y de jerarquía de caché L1/L2 tradicional. Los tensores viajan de núcleo a núcleo.
- **Inviabilidad del Stack Actual:** 
  - Triton compila a PTX (instrucciones NVIDIA). **INÚTIL.**
  - C++ con OpenMP asume memoria compartida (Shared Memory) y coherencia de caché. **INÚTIL.**
  - Rust con punteros crudos asume un mapa de direcciones lineal en RAM. **INÚTIL.**
- **Ruta de Migración Obligatoria:** 
  - La tesis requiere abandonar el concepto de arreglos lineales iterativos y reescribir la retracción de Cayley en **CSL (Compute Kernel Language)** utilizando el SDK propietario de Cerebras.
  - La hiperesfera $S^{D-1}$ y su espacio tangente $T_S$ deben mapearse geométricamente sobre los núcleos físicos del silicio en la malla de enrutamiento 2D, logrando que el transporte paralelo se convierta en una propagación de flujo de energía sin tocar nunca una memoria principal.
