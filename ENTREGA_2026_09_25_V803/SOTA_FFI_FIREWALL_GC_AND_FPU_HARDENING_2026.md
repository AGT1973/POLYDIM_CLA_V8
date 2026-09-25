# 🏛️ ESPECIFICACIÓN MAESTRA DE FRONTERAS FFI, CONTRATOS DE PROPIEDAD GC Y GUARDIA FPU SOTA (V804+)

**Fecha:** 2026-09-25  
**Autor:** Ariel & Red Team Bulldog POLYDIM  
**Invariante:** Los punteros deben tener leases; los fallos deben tener estados; las tareas deben tener propietarios; y los cambios del FPU deben tener semántica declarada.

---

## 1. 🛡️ FIREWALL FFI RUST–PYTHON (Zero-Panic Architecture)

```
┌────────────────────────────────────────────────────────┐
│ 1. API PYTHON (Python Exception Translation)          │
│    NativePanicError, NativeStatus mapping              │
├────────────────────────────────────────────────────────┤
│ 2. FRONTERA FFI C PURA (ffi_boundary Adapter)          │
│    catch_unwind + AssertUnwindSafe + mem::forget       │
├────────────────────────────────────────────────────────┤
│ 3. CANAL DE ERROR POR HILO (Thread-Local LAST_ERROR)   │
│    Código de estado tipado + mensaje truncado a 4KB    │
├────────────────────────────────────────────────────────┤
│ 4. MÁQUINA DE ESTADOS DE INSTANCIA (AtomicU8 Tainting) │
│    Healthy(0) ──> Draining(1) ──> Tainted(2) ──> Destroyed(3) │
└────────────────────────────────────────────────────────┘
```

### Contrato de Compilación y Adaptador de Borde:
```rust
#[cfg(panic = "abort")]
compile_error!(
    "El backend FFI de POLYDIM requiere panic = \"unwind\" \
     para interceptar panics y proteger el runtime de Python."
);

use std::{
    cell::RefCell,
    panic::{catch_unwind, AssertUnwindSafe},
    sync::atomic::{AtomicU8, Ordering},
};

#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NativeStatus {
    Ok = 0,
    InvalidArgument = 1,
    NotReady = 2,
    Cancelled = 3,
    OutOfMemory = 4,
    BackendError = 5,
    Tainted = 6,
    Panic = 7,
    Internal = 8,
}

#[derive(Debug)]
pub struct NativeError {
    pub status: NativeStatus,
    pub message: String,
}

thread_local! {
    static LAST_ERROR: RefCell<Option<NativeError>> = const { RefCell::new(None) };
}

pub fn set_last_error(status: NativeStatus, message: impl Into<String>) {
    let mut message = message.into();
    message.truncate(4_096);
    LAST_ERROR.with(|slot| {
        *slot.borrow_mut() = Some(NativeError { status, message });
    });
}

pub fn ffi_boundary<F>(f: F) -> NativeStatus
where
    F: FnOnce() -> Result<(), NativeError>,
{
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(())) => NativeStatus::Ok,
        Ok(Err(err)) => {
            set_last_error(err.status, err.message);
            err.status
        }
        Err(payload) => {
            set_last_error(NativeStatus::Panic, "CRITICAL: Rust panic caught at FFI boundary");
            // Contención de crisis: evitar Drop del payload para no arriesgar un segundo panic
            std::mem::forget(payload);
            NativeStatus::Panic
        }
    }
}
```

---

## 2. 🧠 CONTRATOS DE PROPIEDAD DE MEMORIA (Anti-UAF & Leases)

| Modalidad de Acceso | Mecanismo Obligatorio | Garantía de Propiedad / Ciclo de Vida | Riesgo Mitigado |
| :--- | :--- | :--- | :--- |
| **Matrices CPU Síncronas** | **PEP 3118 (`Py_buffer`)** con `PyBUF_C_CONTIGUOUS \| PyBUF_FORMAT` | `PyObject_GetBuffer` al inicio y `PyBuffer_Release` en salida | Punteros efímeros `(a + b).ctypes.data` liberados por GC |
| **Matrices CPU Asíncronas**| **`BufferLease` / `NativeTask`** | Retención explícita del objeto exportador hasta `task.wait()` o copia nativa | Destrucción del buffer mientras un worker lee en background |
| **Tensores CPU / GPU** | **DLPack (`__dlpack__`)** | Transferencia explícita con renombrado a `used_dltensor` y llamada única al deleter | Doble liberación de memoria o alias no sincronizados |
| **Memoria Compartida IPC** | **`mmap` Anónimo con Sellos** | Slicing directo con `PmtpHeaderV804` de 128B y verificación de longitud | Modificación de tamaño concurrente (`SIGBUS`) |

---

## 3. ⚡ GUARDIA FPU FTZ/DAZ Y MODOS NUMÉRICOS EXPLÍCITOS

### Modos Numéricos Formales:
1. **`strict_ieee`:** Preserva subnormales y el *underflow* gradual IEEE 754. FTZ/DAZ desactivado. Uso: Verificación científica, cálculo de invariantes y auditoría.
2. **`fast_flush`:** Activa FTZ/DAZ por hilo dentro del hot loop. Magnitudes $< 2.225 \times 10^{-308}$ se convierten a cero instantáneamente. Uso: Simulación de alta tasa en producción.

### Guardia RAII por Hilo (x86_64 & AArch64):
```cpp
class FpuFtzDazGuard final {
public:
    explicit FpuFtzDazGuard(bool enable_ftz_daz = true) noexcept {
#if defined(__x86_64__) || defined(_M_X64)
        saved_mxcsr_ = _mm_getcsr();
        if (enable_ftz_daz) {
            constexpr unsigned kDaz = 1u << 6;   // Denormals Are Zero
            constexpr unsigned kFtz = 1u << 15;  // Flush To Zero
            _mm_setcsr(saved_mxcsr_ | kDaz | kFtz);
        }
#elif defined(__aarch64__)
        __asm__ __volatile__("mrs %0, fpcr" : "=r"(saved_fpcr_));
        if (enable_ftz_daz) {
            uint64_t new_fpcr = saved_fpcr_ | (1ULL << 24) | (1ULL << 25); // FZ + FZDN
            __asm__ __volatile__("msr fpcr, %0" : : "r"(new_fpcr));
        }
#endif
    }

    ~FpuFtzDazGuard() noexcept {
#if defined(__x86_64__) || defined(_M_X64)
        _mm_setcsr(saved_mxcsr_);
#elif defined(__aarch64__)
        __asm__ __volatile__("msr fpcr, %0" : : "r"(saved_fpcr_));
#endif
    }

    FpuFtzDazGuard(const FpuFtzDazGuard&) = delete;
    FpuFtzDazGuard& operator=(const FpuFtzDazGuard&) = delete;

private:
#if defined(__x86_64__) || defined(_M_X64)
    unsigned saved_mxcsr_{0};
#elif defined(__aarch64__)
    uint64_t saved_fpcr_{0};
#endif
};
```

### Ubicación Obligatoria en OpenMP:
```cpp
#pragma omp parallel
{
    FpuFtzDazGuard fpu_guard(true); // Una instancia por cada worker thread
    #pragma omp for schedule(static)
    for (int64_t i = 0; i < D; ++i) {
        // Hot loop libre de assists de microcódigo
    }
}
```
