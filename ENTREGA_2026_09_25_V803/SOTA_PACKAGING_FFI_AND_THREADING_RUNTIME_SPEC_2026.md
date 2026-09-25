# 🏛️ ESPECIFICACIÓN MAESTRA DE EMPAQUETADO, AISLAMIENTO FFI Y RUNTIME DE CONCURRENCIA SOTA (V804+)

**Fecha:** 2026-09-25  
**Autor:** Ariel & Red Team Bulldog POLYDIM  
**Invariante:** La portabilidad no se logra cargando dependencias arbitrarias; se logra aislando las fronteras y sellando el grafo nativo.

---

## 1. 🛡️ PRINCIPIOS NO NEGOCIABLES DE LA ARQUITECTURA FFI

```
┌────────────────────────────────────────────────────────┐
│ 1. API PYTHON & ORQUESTACIÓN (Thin Binding)            │
│    Gestión de GIL, memoria PEP 3118 / DLPack           │
├────────────────────────────────────────────────────────┤
│ 2. FRONTERA FFI C PURA (C ABI v1.0 Opaca)              │
│    extern "C", structs POD, int32/uint64, códigos error│
├────────────────────────────────────────────────────────┤
│ 3. NÚCLEO NATIVO SELLADO (libpolydim_core)             │
│    C++20 / Rust 1.81+, bucles batch O(N), Cero GIL     │
├────────────────────────────────────────────────────────┤
│ 4. AISLAMIENTO POR PROCESO (Worker Nativo PMTP)        │
│    Para stacks incompatibles (Torch / TF / MKL / OMP)  │
└────────────────────────────────────────────────────────┘
```

1. **Cero Exposición de ABI C++ a Python:** Prohibido retornar `std::vector`, `std::string`, templates o lanzar excepciones C++ a través de la frontera FFI. Todo cruce es `extern "C"` con tipos POD de ancho fijo (`int32_t`, `uint64_t`, `int64_t`).
2. **Un Solo Runtime OpenMP por Proceso:** Prohibida la coexistencia de `libgomp`, `libiomp5` y `vcomp`. `KMP_DUPLICATE_LIB_OK=TRUE` vetado en producción. El wheel base opera con pool interno/Rayon o core serial; el paralelismo pesado se gestiona en un worker nativo aislado.
3. **Llamadas Batch Masivas (Anti-Overhead FFI):** Prohibidas las llamadas FFI microscópicas por iteración. Python invoca operaciones de lote (`polydim_run_batch_v1`), liberando el GIL explícitamente (`Py_BEGIN_ALLOW_THREADS`).

---

## 2. 📦 PIPELINE DE EMPAQUETADO Y LINKER HARDENING POR SISTEMA OPERATIVO

| Plataforma | Toolchain / Linker Hardening | Empaquetado & Vendorización | Gestión de Dependencias & Carga |
| :--- | :--- | :--- | :--- |
| **Windows** | MSVC (`/fp:precise`, `/nodefaultlib:vcomp`) o MinGW (`-static-libgcc -static-libstdc++`) | **`delvewheel repair`** con name mangling sobre DLLs vendorizadas privadas | Retención obligatoria de handles en `_DLL_DIRECTORY_HANDLES = [os.add_dll_directory(...)]` a nivel módulo |
| **Linux** | `-fvisibility=hidden`, `-Wl,-Bsymbolic-functions`, `-Wl,--exclude-libs,ALL`, `exports.map` | **`auditwheel repair`** (política manylinux) | Carga con `ctypes.CDLL(..., mode=RTLD_LOCAL)`. Rutas relativas obligatorias con **`RPATH=$ORIGIN`** |
| **macOS** | `@rpath/libpolydim.dylib`, `@loader_path` en extensiones `.so` | **`delocate-wheel`** + verificación de firmas | **Cadena estricta:** Modificar dylibs/rpath ➔ Firmar (`codesign --force --sign ...`) ➔ Notarizar ➔ Staple |

---

## 3. 🛡️ CONTRATO DE ABI C Y PANIC FIREWALL (Rust / C++)

### Contrato de Cabecera Binaria C (`polydim_ffi_v1.h`)
```c
#ifndef POLYDIM_FFI_V1_H
#define POLYDIM_FFI_V1_H

#include <stdint.h>
#include <stddef.h>

#define POLYDIM_ABI_MAJOR 1
#define POLYDIM_ABI_MINOR 0

typedef struct polydim_engine_t polydim_engine_t;

typedef enum {
    POLYDIM_STATUS_OK = 0,
    POLYDIM_STATUS_INVALID_ARGUMENT = 1,
    POLYDIM_STATUS_OUT_OF_MEMORY = 2,
    POLYDIM_STATUS_PANIC_CAPTURED = 3,
    POLYDIM_STATUS_INTERNAL_ERROR = 255
} polydim_status_t;

typedef struct {
    uint32_t abi_major;
    uint32_t abi_minor;
    uint64_t flags;
    uint64_t worker_count;
    uint64_t reserved[4];
} polydim_config_v1_t;

typedef struct {
    const void* data;
    size_t      byte_length;
    uint32_t    dtype;
    uint32_t    ndim;
    const int64_t* shape;
    const int64_t* strides;
} polydim_tensor_view_v1_t;

#ifdef __cplusplus
extern "C" {
#endif

polydim_status_t polydim_create_v1(const polydim_config_v1_t* config, polydim_engine_t** out_engine);
polydim_status_t polydim_run_batch_v1(polydim_engine_t* engine, const polydim_tensor_view_v1_t* in_tensor, polydim_tensor_view_v1_t* out_tensor);
const char*      polydim_last_error_v1(const polydim_engine_t* engine);
void             polydim_destroy_v1(polydim_engine_t* engine);

#ifdef __cplusplus
}
#endif

#endif
```

### Rust Panic Firewall con Tainting
```rust
use std::panic::{catch_unwind, AssertUnwindSafe};

#[unsafe(no_mangle)]
pub unsafe extern "C" fn polydim_run_batch_v1(
    engine_ptr: *mut PolydimEngine,
    input_ptr: *const f64,
    input_len: usize,
    output_ptr: *mut f64,
    output_len: usize,
) -> i32 {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if engine_ptr.is_null() || input_ptr.is_null() || output_ptr.is_null() {
            return Err("null pointer passed to FFI");
        }
        let engine = unsafe { &mut *engine_ptr };
        let in_slice = unsafe { std::slice::from_raw_parts(input_ptr, input_len) };
        let out_slice = unsafe { std::slice::from_raw_parts_mut(output_ptr, output_len) };
        engine.run_batch(in_slice, out_slice).map_err(|_| "computation failure")
    }));

    match result {
        Ok(Ok(())) => 0,
        Ok(Err(msg)) => {
            unsafe { &mut *engine_ptr }.set_last_error(msg);
            1
        }
        Err(_) => {
            unsafe { &mut *engine_ptr }.set_last_error("CRITICAL: native panic caught at FFI boundary");
            3
        }
    }
}
```

---

## 4. 🧪 GATES DE CI Y TESTS DE COEXISTENCIA EN PROCESOS LIMPIOS

Queda prohibido validar imports únicamente en la misma sesión del runner. Los tests de CI deben instanciar subprocesos limpios evaluando:
1. `import mi_paquete` en aislamiento.
2. `import numpy; import mi_paquete`.
3. `import torch; import mi_paquete` (verificación de pools OpenMP y CUDA streams).
4. `import mi_paquete; import torch` (verificación de orden de carga).
5. Evaluación asintótica de $10^6$ pasos midiendo estabilidad de memoria, conteo de threads y reproducibilidad numérica.
