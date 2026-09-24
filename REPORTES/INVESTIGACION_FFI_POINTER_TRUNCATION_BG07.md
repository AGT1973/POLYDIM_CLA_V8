# INVESTIGACIÓN SOTA BG-07: TRUNCAMIENTO DE PUNTEROS CUDA EN FFI WINDOWS (LLP64)

**Fecha de Ingesta:** 2026-09-18
**Veredicto:** ACEPTADO. El modelo de datos de Windows (LLP64) define `long` como 32 bits, a diferencia de Linux (LP64) donde es 64 bits. Pasar un puntero de VRAM a través del FFI C++ usando `ctypes.c_long` truncará silenciosamente las direcciones mayores a 4GB, causando page faults aleatorios en la GPU.

---

## 1. La Trampa del `long` en C++ MSVC/MinGW
En Python, `ctypes.c_long` y en C++ `long` miden 4 bytes (32 bits) en Windows x64.
La VRAM de una GPU moderna (A100, T4) maneja direcciones de 64 bits. Un puntero como `0x00000001FFFFFFFF` cruzará el FFI hacia C++ perdiendo sus 32 bits superiores y convirtiéndose en `0x00000000FFFFFFFF`, direccionando basura.

## 2. Contrato Estricto FFI
Toda frontera FFI que involucre punteros de memoria (`CUdeviceptr`, buffers compartidos, data_ptr de tensores) queda sometida a tipado fuerte de 64 bits:

**Lado Python:**
```python
import ctypes
# PROHIBIDO: ctypes.c_long, ctypes.c_int
# OBLIGATORIO:
ptr_array = (ctypes.c_uint64 * num_args)()
ptr_array[0] = ctypes.c_uint64(tensor.data_ptr())
```

**Lado C++:**
```cpp
#include <cstdint>
// PROHIBIDO: long*, int*
// OBLIGATORIO:
extern "C" void launch_kernel(CUfunction kernel, uint64_t* args, int num_args) {
    void* arg_ptrs[16];
    for (int i = 0; i < num_args; i++) {
        arg_ptrs[i] = &args[i]; // El cuLaunchKernel requiere void**
    }
    cuLaunchKernel(kernel, /* grid/block */, arg_ptrs, nullptr);
}
```

## 3. Validación Asintótica
El script de inicialización deberá ejecutar obligatoriamente:
`assert ctypes.sizeof(ctypes.c_void_p) == 8`
`assert ctypes.sizeof(ctypes.c_uint64) == 8`
Si falla, se aborta la ejecución antes de corromper la VRAM.
