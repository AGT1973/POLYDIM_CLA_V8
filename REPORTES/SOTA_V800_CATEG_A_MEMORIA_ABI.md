# 🏛️ INGESTA SOTA V800: CATEGORÍA A — CORRUPCIÓN DE MEMORIA Y ABI
**Fecha:** 2026-09-24 | **Fuente:** Evaluación externa SOTA (AI peer review)
**Estado:** INGESTADO — Regla 19 ACTIVA (sin código)

---

## ELEVACIONES CRÍTICAS SOBRE LA PROPUESTA INICIAL

### 1. Separar TAMAÑO de ALINEACIÓN (Corrección Fundamental)
- **Tamaño = 128B:** Útil para slots fijos, formatos de intercambio, batches.
- **Alineación = 128B:** Solo si hardware/DMA/SIMD/atomicidad lo exige.
- **Un struct de 128B con alignof=8 puede cruzar límites de caché.** Si se necesita aislamiento de false sharing, la alineación mayor NO debe estar en la ABI pública → usar wrapper interno `#[repr(C, align(128))] struct InternalCachePaddedSlot { abi: TensorSlotV1 }`.

### 2. Arquitectura SOTA: POD Header + Handle Opaco (No Structs Ricos)
**Regla estratégica:** Los structs FFI públicos representan datos inertes. Ownership, mutabilidad, callbacks, allocators y estados complejos viajan detrás de un handle opaco.

```
Python / NumPy
│   PyCapsule o Python owner como base del ndarray
▼
C API estable: handles opacos + POD headers versionados
│
├── Rust: Arc / Drop / checked arithmetic / panic containment
└── C++: RAII interno / destructor C explícito / allocator original
```

**No incluir en ABI pública:** Vec, String, Box, Arc, std::vector, std::string, vtables, bool, enums no fijados, bit-fields, long, size_t, punteros si necesitás ABI idéntica entre targets, atomics, mutexes, callbacks sin ABI explícita.

### 3. Contrato ABI Versionado Extensible
```c
typedef struct polydim_tensor_desc {
    uint32_t abi_version;    // Versión del contrato semántico
    uint32_t struct_size;    // Permite detectar binario antiguo
    uint32_t dtype;
    uint32_t ndim;
    uint64_t shape[8];
    int64_t  stride_bytes[8];
    uint64_t byte_offset;
    uint64_t byte_length;
    uint64_t flags;
    uint8_t  reserved[16];   // Espacio para evolución sin romper offsets
} polydim_tensor_desc_t;
```
- `abi_version` + `struct_size` en los primeros bytes = detección de incompatibilidad.
- `reserved` = evolución sin desplazar offsets.
- `polydim_tensor_t*` = recurso opaco con `retain/release`.

### 4. OwnedForeignBuffer Completo (No Solo Puntero + DeallocFn)
```rust
pub type DeallocFn = unsafe extern "C" fn(
    ptr: *mut c_void,
    bytes: usize,
    alignment: usize,
    ctx: *mut c_void,
);

pub struct OwnedForeignBuffer<T> {
    ptr: NonNull<T>,
    len: usize,
    bytes: usize,
    alignment: usize,
    dealloc: DeallocFn,
    context: *mut c_void,
    _element: PhantomData<T>,
}
```
- Validar en constructor: `checked_mul`, `isize::MAX`, `alignment.is_power_of_two()`, `ptr % alignment == 0`.
- No Clone. Para compartir: `Arc<OwnedForeignBuffer<T>>`.
- No Send/Sync automático si allocator/callback no es thread-safe.

### 5. PyArray_SetBaseObject: Semántica "Steals Reference" (Corrección)
```c
Py_INCREF(owner);  // Referencia destinada a ser transferida
if (PyArray_SetBaseObject(array, owner) < 0) {
    // NO Py_DECREF(owner): SetBaseObject YA tomó/robó esa referencia
    Py_DECREF(array);
    return NULL;
}
```
- Destructor de PyCapsule: debe ser no-throw, idempotente, tolerar finalización del intérprete.
- Cápsula debe incluir: ptr, bytes, alignment, deallocator, context, etiqueta/nombre.

### 6. Validación de Views N-Dimensionales (Strides + Offsets)
No alcanza con `elements = rows * cols`. Para views no contiguas:
$$\Delta_i = (\text{shape}_i - 1) \times \text{stride}_i$$
Rango total: $0 \le \text{byte\_offset} + \min\_\text{relative}$ y $\text{byte\_offset} + \max\_\text{relative} + \text{itemsize} \le \text{allocation\_bytes}$.

Validar: ndim, dtype vs itemsize, alineación base, strides negativos, views vacías, conversiones a `Py_ssize_t`.

### 7. Target de 64 Bits Explícito
```rust
#[cfg(not(target_pointer_width = "64"))]
compile_error!("polydim FFI ABI v1 requires a 64-bit target");
```
Más claro que `assert!(size_of::<usize>() >= 8)`. Incluso en 64-bit, `isize::MAX` sigue siendo relevante.

### 8. Fronteras de Errores: Cero Panics/Excepciones Cruzando FFI
**Rust:**
```rust
#[no_mangle]
pub unsafe extern "C" fn polydim_tensor_create(...) -> Status {
    match std::panic::catch_unwind(|| tensor_create_impl(...)) {
        Ok(Ok(())) => Status::Ok,
        Ok(Err(status)) => status,
        Err(_) => Status::InternalError,
    }
}
```
**C++:**
```cpp
extern "C" polydim_status_t polydim_cpp_operation(...) noexcept {
    try { return operation_impl(...); }
    catch (const std::bad_alloc&) { return POLYDIM_OUT_OF_MEMORY; }
    catch (...) { return POLYDIM_INTERNAL_ERROR; }
}
```

### 9. NumPy Zero-Copy: Read-Only por Defecto
| Modo | NumPy | Regla |
|------|-------|-------|
| Inmutable | WRITEABLE=False | Compartir libre mientras owner viva |
| Lectura durante cómputo | Read-only | Kernel no puede escribir |
| Escritura exclusiva | Writable | Sin acceso concurrente |
| Copy-on-write | Writable lógico | Clonar antes de mutar si >1 dueño |

### 10. CI Pipeline ABI Completo
1. Generar `api.h` con cbindgen, fallar si diff no intencional.
2. Compilar consumidor C11 y C++17 contra ese header.
3. Asserts de sizeof/alignof/offsetof en Rust, C, C++, Python.
4. Tests round-trip: C crea → Rust consume → Python expone → NumPy conserva → C++ libera.
5. `abidw` + `abidiff` en Linux (ELF/DWARF).
6. ASan/UBSan/LSan/TSAN/Miri.
7. Fuzzing: shapes, strides, offsets, dtype, buffers vacíos, punteros nulos, tamaños ~isize::MAX.
8. Property testing: si `validate_view` acepta, cada acceso lógico debe estar dentro de la asignación.

### 11. Test Crítico de UAF (Exactamente 1 Destrucción)
```python
def test_numpy_view_keeps_owner_alive():
    tensor = make_zero_copy_tensor()
    destroyed = tensor.debug_destruction_counter()
    array = tensor.to_numpy()
    del tensor; gc.collect()
    assert destroyed.value == 0  # tensor vivo por ndarray.base
    assert array[0, 0] == expected_value
    del array; gc.collect()
    assert destroyed.value == 1  # liberado exactamente 1 vez
```
Variantes: `array.view()`, `array[::2]`, `array.T`, `array[::-1]`, cadena de views, excepción durante construcción, destrucción desde otro hilo.
