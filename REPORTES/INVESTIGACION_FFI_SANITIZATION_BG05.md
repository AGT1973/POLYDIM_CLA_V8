# INVESTIGACIÓN SOTA BG-05: SANITIZACIÓN FFI Y CONTAMINACIÓN SILENCIOSA

**Fecha de Ingesta:** 2026-09-18
**Veredicto:** ACEPTADO. Existe una brecha letal de carrera (Race Condition) si Python inyecta NaN/Inf o subnormales directo al buffer PMTP, envenenando a los lectores concurrentes C++/Rust antes de que el guardián topológico los detenga.

---

## 1. El Peligro del Hot-Path en Memoria Compartida
Hacer `shared_state[:] = x` asumiendo que Rust lo va a validar después es un error arquitectónico masivo. Durante ese delta de tiempo (inter-proceso), los tensores lectores asimilan el NaN y la geometría $S^{D-1}$ colapsa irrevocablemente.

## 2. Contrato de Frontera (Python -> Shared Memory)
**Python:** Único autorizado para formatear a `f64`. Se usará un wrapper estricto `require_f64_vector` antes de tocar la memoria compartida.
```python
F64_TINY = np.finfo(np.float64).tiny

def require_f64_vector(x, dim=None, reject_subnormal=True):
    arr = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError("FATAL: NaN/Inf detectado")
    
    subnormal = (arr != 0.0) & (np.abs(arr) < F64_TINY)
    if np.any(subnormal):
        if reject_subnormal:
            raise ValueError("FATAL: Subnormal detectado")
        arr = arr.copy()
        arr[subnormal] = 0.0
        
    return np.ascontiguousarray(arr, dtype=np.float64)
```

## 3. Topología de Publicación Segura
**Prohibido:** Modificar el tensor in-place sin lock.
**Requerido:** 
1. Sanitizar en un buffer local (candidato).
2. Adquirir el `shared_state_write_lock` (o SeqLock writer).
3. Copiar (Memcpy) a la memoria compartida.
4. Incrementar el `publish_generation` atómicamente.

## 4. Guardián de Segunda Línea (Rust FFI)
Rust debe validar *todo* array crudo como si fuera hostil antes de procesar topología:
```rust
if !value.is_finite() { return Err("NaN/Inf"); }
if value != 0.0 && value.abs() < f64::MIN_POSITIVE { return Err("Subnormal"); }
```

## Referencias SOTA
* NumPy: `np.finfo`, `np.isfinite`
* Rust Standard Library: `f64::is_finite()`, `f64::MIN_POSITIVE`
