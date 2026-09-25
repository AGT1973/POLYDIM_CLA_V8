# 🏛️ MANUAL SOTA DE PROTECCIÓN DE FRONTERAS FFI, RETENCIÓN GC Y GUARDIÁN FTZ/DAZ (V804+)

**Fecha:** 2026-09-25  
**Autor:** Ariel & Orquestador POLYDIM (Red Team Master Peer Review)  
**Estado:** Inviolable — Cortafuegos de Producción FFI, Protocolo de Buffers y Aislamiento de FPU

---

## 📋 MATRIZ TRANSVERSAL DE CONTROL Y AUDITORÍA

| Control | 1. Pánicos de Rust en FFI | 2. Use-After-Free por GC de Python | 3. Subnormales y Guardián FTZ/DAZ |
| :--- | :--- | :--- | :--- |
| **Prevención en Compilación** | `#[cfg(panic = "abort")] compile_error!(...)`, Clippy `unwrap_used`, `no_panic` crate. | Bindings con ownership nativo (DLPack `__dlpack__`, PyO3 `PyBuffer`, `nanobind`). | Compilación declarativa `-fdenormal-fp-math=preserve-sign`. No enlazar con `-ffast-math` global. |
| **Barrera en Runtime** | Macro `ffi_guard!`, canal de error `LAST_ERROR` y marcado de estado *tainted*. | PEP 3118 Buffer Protocol (`PyObject_GetBuffer`/`PyBuffer_Release`), `_pinned` dictionary. | RAII dentro de `#pragma omp parallel` restaurando `MXCSR`/`FPCR` al salir de la región. |
| **Observabilidad** | Custom `std::panic::set_hook` con `Backtrace::force_capture()`, `faulthandler.enable()`. | ASan (`PYTHONMALLOC=malloc LD_PRELOAD=libasan.so`), `python -X dev`, `tracemalloc`. | Métrica "Assists" en VTune o `perf stat` (eventos `assists.fp`). |
| **Test en CI** | `cargo fuzz` sobre API exportada + Miri para UB en código `unsafe`. | `del` + `gc.collect()` inmediato tras trabajos asíncronos en build `free-threaded`. | Assert de no-contaminación de subnormales tras cada `import` de extensión nativa. |

---

## 1. 🛡️ PÁNICOS DE RUST EN LA FRONTERA FFI (RUST 1.71+ / 1.81+)

### Mecánica del Lenguaje
- Desde **Rust 1.81**, las ABIs `extern "C"` sin sufijo `-unwind` abortan inmediatamente el proceso ante un panic no capturado.
- El riesgo en FFI ya no es la corrupción silenciosa de memoria, sino la **terminación abrupta e irrecuperable del proceso ejecutor de Python**.

### Arquitectura de Cortafuegos en Capas (Macro `ffi_guard!`)

```rust
#[cfg(panic = "abort")]
compile_error!("La librería FFI de POLYDIM requiere panic = \"unwind\"");

macro_rules! ffi_guard {
    ($default:expr, $body:block) => {{
        match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| $body)) {
            Ok(v) => v,
            Err(payload) => {
                let msg = payload.downcast_ref::<&str>().map(|s| s.to_string())
                    .or_else(|| payload.downcast_ref::<String>().cloned())
                    .unwrap_or_else(|| "Panic FFI sin mensaje explícito".into());
                set_last_error(msg);
                std::mem::forget(payload); // Previene panic secundario durante el Drop del payload
                $default
            }
        }
    }};
}
```

### Canal de Error Explícito y Tainting de Instancia
- `thread_local!` `LAST_ERROR` leído por Python tras recibir un código de error negativo (ej. `-999`).
- **Instancia Tainted:** Ante un panic capturado en Rust, la estructura subyacente se marca como *poisoned/tainted* y rechaza llamadas subsecuentes hasta su recreación total.
- **Eventos No Capturables por `catch_unwind`:**
  - *Doble Panic:* Panic dentro de un `Drop` durante la fase de unwinding (Aborto).
  - *OOM:* Fallos de asignación masiva (`handle_alloc_error`). Validación previa con `try_reserve`.
  - *Stack Overflow:* Desbordamiento de pila (SIGSEGV). Evitar recursión en FFI.
  - *Excepciones C++:* Deben ser atrapadas en C++ con `catch (...)` antes de retornar a Rust/Python.

---

## 2. 🧟 GESTIÓN DE USE-AFTER-FREE (UAF) Y RECOLECTOR DE BASURA DE PYTHON

### Taxonomía de Riesgos en Python / CFFI
1. **Temporales en Expresiones (`.ctypes.data`):** Operaciones como `(A + B).ctypes.data` retornan un entero crudo. A diferencia de `data_as()`, **no mantienen la referencia al array temporal**, resultando en un puntero a memoria inmediatamente liberada por el GC.
2. **Buffer Reallocation & Resizing:** `bytearray.resize()` o `ndarray.resize()` en Python invalidan los punteros nativos mapeados en C++/Rust.
3. **mmap & SIGBUS:** Truncar un archivo compartido desde otro proceso causa `SIGBUS` en lugar de `SIGSEGV`.
4. **Python Free-Threaded (3.13+ / `Py_GIL_DISABLED`):** Sin el GIL, hilos de Python pueden mutar o redimensionar un buffer de forma concurrente mientras el kernel C++ lo lee.

### Escala SOTA de Soluciones (Mayor a Menor Robustez)
1. **DLPack (`__dlpack__`):** Transferencia de propiedad mediante cápsula con *deleter* explícito. Estándar multiplataforma entre PyTorch, NumPy, JAX y Triton.
2. **PyO3 / nanobind (`py::keep_alive<>`):** Enlace del ciclo de vida de los tensores directamente con los objetos Python mediante borrosidad en tiempo de ejecución.
3. **PEP 3118 Buffer Protocol (`PyObject_GetBuffer`):** Mantiene una referencia dura vía `Py_buffer`. Bloquea redimensionamientos y liberaciones (lanza `BufferError`).
4. **Pinning Manual / Handles Opaque:** Registro explícito en diccionario `self._pinned[job]` hasta la conclusión del trabajo asíncrono.

---

## 3. ⚡ SUBNOBARES Y AISLAMIENTO DE ENTORNO FPU (FTZ/DAZ GUARD)

### Microcode Assists & Medición Físicacon VTune/perf
- Operaciones con números subnormales ($< 10^{-308}$ en FP64) fuerzan al procesador a ejecutar *microcode assists*, desacelerando la CPU.
- **Medición Real:** Métrica "Assists" en Intel VTune o eventos `assists.fp` en `perf stat`.

### Reglas Inviolables de RAII y No-Inlining

```cpp
// Hot Loop en función aislada NO-INLINEABLE para evitar optimizaciones erróneas de LLVM/GCC
__attribute__((noinline)) void polydim_hot_kernel_impl(
    const double* X, const double* U, const double* V, double* Y, int64_t N) 
{
    // Cómputo vectorizado puro
}

// Guardián RAII dentro de cada región paralela OpenMP
#pragma omp parallel
{
    FpuFtzDazGuard fpu_guard; // Aplica FTZ/DAZ localmente en el hilo del pool
    
    #pragma omp for schedule(static)
    for (int64_t i = 0; i < N; ++i) {
        // Invocación a la función noinline
    }
} // ~FpuFtzDazGuard restaura MXCSR/FPCR original del hilo al salir
```

### Verificación de no-contaminación FPU en Python
```python
def assert_fpu_environment_clean():
    tiny = float.fromhex("0x1p-1074")
    assert tiny * 1.0 != 0.0, "FATAL: Entorno FPU contaminado con FTZ/DAZ por extensión cargada."
```
