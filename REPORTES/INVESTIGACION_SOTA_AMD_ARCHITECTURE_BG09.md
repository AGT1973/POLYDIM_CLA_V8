# INVESTIGACIÓN SOTA: ARQUITECTURA AMD (ZEN 4/5 & RADEON INSTINCT) PARA POLYDIM

## 1. Topología de Caché (Zen 4/5), Prefetchers y False Sharing Cross-CCD

### Análisis Asintótico y de Aislamiento
Las arquitecturas Zen 4 y Zen 5 mantienen una línea de caché estándar de 64 bytes. Sin embargo, asumir que `alignas(64)` resuelve el False Sharing es un error de diseño de la vieja escuela (Happy-Path). 

- **El Problema del Prefetcher Espacial:** Zen 5 introduce prefetchers de región y un 2D stride prefetcher altamente agresivos. Estos subsistemas especulativos cargan líneas de caché adyacentes de forma preventiva. Por lo tanto, `alignas(64)` es destruido sistemáticamente en cargas de trabajo de alta frecuencia.
- **La Falacia de `alignas(128)`:** Empíricamente, empacar a 128 bytes mitiga la búsqueda preventiva de pares adyacentes en L1/L2, pero falla catastróficamente al cruzar el tejido Infinity Fabric entre chiplets (CCX/CCD). 
- **Penalización NUMA (Cross-CCD):** En procesadores EPYC/Ryzen de alto núcleo con NPS (Nodes Per Socket) activado, cada CCD opera como un nodo NUMA distinto. Una contención atómica inter-CCD sobre líneas de 128 bytes induce un tráfico de invalidación de caché severo (snoop storms) a través del Infinity Fabric.
- **Veredicto Arquitectónico:** Para un aislamiento absoluto de estructuras concurrentes (colas shared memory, tensores IPC, spinlocks de SOTA) en arquitecturas AMD, **el alineamiento a nivel de página del SO (`alignas(4096)`) es estrictamente obligatorio**. Esto no solo suprime el false sharing y paraliza al prefetcher agresivo 2D, sino que aísla las traducciones de la TLB, garantizando que estructuras hiper-demandadas no compartan dominios de página físicos entre CCDs.

## 2. Compilación Triton a AMD y C++ Baremetal (HSACO)

### Del Paradigma PTX al Binario HSACO
El ecosistema AMD (ROCm/HIP) no ejecuta JIT en tiempo de ejecución de la misma forma que NVIDIA con PTX (`.cubin`). Triton para backend AMD (LLVM AMDGPU) genera un ELF AOT (Ahead-Of-Time) estrictamente ligado a la ISA del target de hardware: el **HSA Code Object (`.hsaco`)**.

- **Generación en Triton:** 
  La compilación requiere especificar el GFX exacto (e.g., `gfx90a` para MI250X, `gfx942` para MI300X).
  ```python
  import triton
  from triton.runtime.driver import GPUTarget

  target = GPUTarget("hip", "gfx942", 64)
  kernel = triton.compile(kernel_fn, target=target, options={...})
  hsaco_binary = kernel.asm['hsaco'] # Extracción directa del binario

  with open("polydim_kernel.hsaco", "wb") as f:
      f.write(hsaco_binary)
  ```

### Inyección Baremetal con `hipModuleLoadDataEx`
En C++ baremetal, la API HIP mapea unívocamente a la API Driver de CUDA, pero exige el objeto precompilado HSACO.
- **Equivalencia API:** `cuModuleLoadDataEx` -> `hipModuleLoadDataEx`.
- **Carga Directa:**
  ```cpp
  #include <hip/hip_runtime.h>
  #include <vector>
  #include <fstream>

  // Carga binaria baremetal
  std::ifstream file("polydim_kernel.hsaco", std::ios::binary | std::ios::ate);
  std::streamsize size = file.tellg();
  file.seekg(0, std::ios::beg);
  std::vector<char> buffer(size);
  file.read(buffer.data(), size);

  hipModule_t module;
  // Falla con hipErrorNoBinaryForGpu si el flag gfxXXX de Triton no coincide con el hardware físico
  hipError_t err = hipModuleLoadDataEx(&module, buffer.data(), 0, nullptr, nullptr);
  
  hipFunction_t kernel_func;
  hipModuleGetFunction(&kernel_func, module, "polydim_kernel_name");
  ```
- **Condición de Veto:** Parámetros JIT (como el equivalente a `CU_JIT_MAX_REGISTERS`) frecuentemente son ignorados en el path HIP-Clang. El HSACO debe generarse con los flags asintóticos correctos desde la compilación previa en Triton.

## 3. Fuentes Verificables (Evidencia Empírica SOTA)

- **AMD Cache & Zen 4/5 Architecture:**
  - *AMD EPYC™ 9004 Series Processors Optimization Guide:* Detalles de topología CCD, Infinity Fabric y segmentación NUMA.
  - *AMD Zen 5 Architecture Updates:* Mejoras del L2 stride prefetcher 2D y LSQ buffers.
- **ROCm & HIP API:**
  - *HIP API Reference (`hipModuleLoadDataEx`):* [ROCm Docs - Module Management](https://rocm.docs.amd.com/projects/HIP/en/latest/doxygen/html/group___module.html)
  - *HSA Code Objects (HSACO) ELF Structure:* [LLVM AMDGPU Backend](https://llvm.org/docs/AMDGPUUsage.html#code-object)
- **Triton AMD Backend:**
  - *Triton Compiler GPUTarget (HIP):* Referencia de extracción desde `kernel.asm['hsaco']` del framework OpenAI Triton Backend for AMD.
