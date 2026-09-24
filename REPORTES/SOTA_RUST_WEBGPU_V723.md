# REPORTE SOTA: WEBGPU RUST (WGPU) Y CÓMPUTO TENSORIAL ZERO-COPY (V723)

## ESTADO DEL ARTE: ARQUITECTURA DE CÓMPUTO TENSORIAL EN WEBGPU

Este reporte consolida el Estado del Arte (SOTA) sobre la implementación de tensores y cálculo intensivo utilizando la API de Rust `wgpu` y WGSL. Se rige estrictamente por los principios de Computabilidad Geométrica (GCGT) y la prohibición del colapso tokenizado 1D, priorizando el mantenimiento del estado latente dentro del manifold de la VRAM.

---

### 1. Zero-Copy Tensor Compute en `wgpu`

**El Obstáculo Geométrico:**
La promesa del "Zero-Copy" auténtico, donde la CPU y GPU acceden al mismo bloque de memoria física (como en CUDA Unified Memory o RDMA), está fundamentalmente bloqueada en `wgpu` por su diseño. Como capa de abstracción de hardware sobre Vulkan, Metal y DX12, `wgpu` exige la separación de dominios de memoria (RAM vs VRAM) por seguridad y portabilidad, forzando inherentemente el uso de *staging buffers*.

**Resolución SOTA (Zero-Redundant-Copy):**
Dado que el paso por el controlador PCIe / bus de memoria es asintóticamente caro (rompiendo el $O(1)$ de transferencia ideal), la industria (ej. *Burn* / *CubeCL*) aplica las siguientes topologías:
1. **Fusión Automática de Kernels (Kernel Fusion):** La estrategia principal no es hacer "zero-copy" entre CPU/GPU, sino lograr que el tensor **nunca regrese a la CPU** durante el ciclo de vida de la inferencia. Varias operaciones matemáticas se colapsan en un único kernel WGSL, preservando el tensor en registros o memoria local de la GPU, cortando el "Gusano" del ancho de banda.
2. **Pool Persistente de Staging Buffers:** Cuando es imprescindible el I/O, el estado del arte pre-aloja un slab de staging buffers reciclables, mapeando asíncronamente (`map_async`) para evitar cuellos de botella en la asignación dinámica del sistema operativo.
3. **By-pass a Vulkan Nativo (Ash/DMA-BUF):** Si el protocolo exige strict zero-copy para hardware específico (e.g., sensores de visión directa), se debe abandonar la capa segura `wgpu` e invocar interop nativa (pasando el descriptor `DMA-BUF` directamente a la GPU).

---

### 2. WGSL Subgroups (Paralelismo SIMD en Manifold Local)

Para cálculos matriciales (Matmul) eficientes, se debe minimizar el acceso a la memoria global. Los **Subgroups** habilitan la comunicación directa de registros a nivel SIMD sin pasar por memoria compartida (Shared Memory), crucial para evitar divergencias de fase matemática.

**Implementación Arquitectónica:**
- **Activación:** Exige habilitar explícitamente el pragma `enable subgroups;` en WGSL y requerir la feature `wgpu::Features::SUBGROUP` en el `DeviceDescriptor`.
- **Topología Adaptativa (Anti-Hardcoding):** Está **terminantemente prohibido** asumir un tamaño de subgrupo fijo. El tamaño de onda (`Wavefront` en AMD, `Warp` en NVIDIA) fluctúa entre 32 y 64 hilos. El código WGSL no debe asumir constantes escalares para dimensiones matriciales, sino interrogar al adaptador en tiempo real (mediante `subgroupMinSize` y `subgroupMaxSize`) para reestructurar la geometría de convolución al vuelo.
- **Funciones de Dominio:** Utilización de `subgroupBroadcast()`, `subgroupAdd()`, `subgroupBallot()` para sincronizaciones isométricas. Existe el riesgo de que el análisis de uniformidad del compilador rechace flujos si el algoritmo presenta ramificaciones divergentes asintóticas; todo control de flujo debe mantenerse topológicamente liso.

---

### 3. Emulación Double-Single (Two-Sum) para evitar el Colapso Numérico (FP64)

**El Problema Matemático (Colapso de Precisión):**
El hardware móvil (GLES, Metal) y el estándar WebGPU carecen del soporte nativo IEEE-754 de 64 bits (FP64). En cálculos tensoriales continuos (ej. iteraciones RNN, atractores dinámicos), el error de flotación FP32 diverge rápidamente a un colapso numérico, rompiendo la isometría exigida por los principios de POLYDIM.

**Enfoque Double-Single (DS) & Two-Sum:**
El SOTA emula FP64 estructurando un hiper-número `vec2<f32>` (Hi|Lo), entregando $\approx 48$ bits de precisión de mantisa matemática a partir de las sumas no evaluadas.

**El Ataque del Compilador (Vulnerabilidad Crítica):**
La implementación ingenua de un algoritmo *Two-Sum* estándar de CUDA a WGSL **fracasará catastróficamente**. El compilador de WebGPU (especialmente sobre Apple Metal) aplica por defecto optimizaciones de Álgebra de Reasociación (Fast Math). Un paso crítico en Two-Sum:
$z = a + b$
$b_{virtual} = z - a$
será simplificado implícitamente por el compilador como $b_{virtual} = b$, eliminando por completo el error subnormal compensador que el algoritmo intenta calcular.

**Mitigación SOTA Exigida:**
1. **Romper la Reasociación:** Deben inyectarse barreras semánticas o usar librerías consolidadas de WebGPU (como `fp64arithmetic`) que aplican trucos algorítmicos (ej. conversiones explícitas a bits o desvíos enteros) para engañar al compilador y forzar el orden estricto de las operaciones FP32, previniendo el "fuego amigo" del optimizador.
2. **Kahan Summation & Esquema de Ozaki:** Si el `Two-Sum` algorítmico resulta inestable por la reasociación del backend, la arquitectura debe replegarse al esquema de Ozaki para multiplicaciones de matrices o una variante de sumatoria de Kahan que pueda resistir la fusión agresiva de instrucciones `fma` (Fused Multiply-Add).

---
*Reporte autogenerado bajo las directrices Zero-Trust y Anti-1D-Worm. Sin generación de métricas artificiales; implementaciones empíricas sujetas a pruebas destructivas posteriores.*
