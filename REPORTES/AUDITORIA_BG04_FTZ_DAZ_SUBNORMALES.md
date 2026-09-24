# 🔬 AUDITORÍA RED TEAM: BG-04 — FTZ/DAZ SUBNORMALES EN FRONTERA FFI

**Fuente de Ingesta:** IA Externa
**Fecha de Evaluación:** 2026-09-18
**Auditor:** Antigravity Bulldog (Red Team POLYDIM)
**Veredicto Global:** 🟢 SÓLIDO — Pero la IA externa NO detectó el bug real en V758

---

## ✅ ELEMENTOS SÓLIDOS (ACEPTADOS)

1. **MXCSR es per-thread:** Correcto y crítico. El registro MXCSR que controla
   FTZ (bit 15) y DAZ (bit 6) es local a cada hilo de ejecución. Activarlo en el
   hilo principal de Python NO garantiza que esté activo en workers OpenMP.

2. **Defensa dual (sanitización Python + FTZ/DAZ C++ per-thread):** Correcto.
   La combinación de `np.abs(y) < np.finfo(y.dtype).tiny → 0.0` en Python y
   `enable_ftz_daz()` dentro de cada worker C++ es la solución SOTA completa.

3. **`eliminar_subnormales()` con `np.copysign(0.0, y[mask])`:** Correcto.
   Preserva el signo del cero IEEE-754, evitando efectos de borde en comparaciones.

4. **Documentar la pérdida de gradual underflow:** Correcto. FTZ/DAZ sacrifica la
   semántica IEEE-754 de underflow gradual. Debe constar como política numérica.

---

## 🔴 BUG REAL ENCONTRADO EN V758 (NO DETECTADO POR LA IA EXTERNA)

### Bug: `enable_ftz_daz()` se llama FUERA del `#pragma omp parallel`

**Evidencia directa** en [`kernel_cpp_v758.cpp:L151 vs L165`](file:///E:/POLYDIM_EINSOF/ENTREGA_2026_09_18_V758/kernel_cpp_v758.cpp#L151-L165):

```cpp
// Línea 151: Se llama en el hilo PRINCIPAL (fuera de la región paralela)
enable_ftz_daz();

// ... setup de acumuladores ...

// Línea 165: Los workers OpenMP arrancan AQUÍ
#pragma omp parallel num_threads(num_threads) reduction(|:nan_detected)
{
    int tid = omp_get_thread_num();
    // ⚠️ enable_ftz_daz() NO se llama dentro de cada worker
    // Los workers OpenMP pueden NO heredar MXCSR del hilo padre
```

**Mismo patrón en las 3 funciones del kernel:**
- `polydim_apply_rodrigues_geodesic_f64`: L151 (fuera) vs L165 (parallel)
- `polydim_apply_orthogonal_mixer_f64`: L307 (fuera) vs L325 (parallel)
- `polydim_apply_adaptive_ortho_f64`: L369 (fuera) vs L386 (parallel)

### ¿Por qué funciona en las pruebas actuales?

GCC propaga MXCSR a los workers OpenMP por defecto (herencia del hilo padre al
crear el pool de hilos). MSVC 2026 también lo hace en la mayoría de los casos.
Pero esto NO está garantizado por la especificación OpenMP. En implementaciones
con pools de hilos pre-creados (que reusan hilos de llamadas anteriores), el MXCSR
puede haber sido restaurado a su valor por defecto entre invocaciones.

### Fix V759: Mover `enable_ftz_daz()` DENTRO de la región paralela

```cpp
#pragma omp parallel num_threads(num_threads) reduction(|:nan_detected)
{
    enable_ftz_daz();  // ← PRIMERA instrucción de cada worker
    int tid = omp_get_thread_num();
    // ... resto del código ...
}
```

Costo: ~3 nanosegundos por hilo (una escritura a MXCSR). Cero impacto en rendimiento.

---

## 🟡 LO QUE FALTA EN PYTHON (polydim_v758_monolito.py)

El monolito Python V758 hace `np.isfinite(y)` pero NO sanitiza subnormales.

### Fix V759 para el enforcer Python:

```python
def require_f64_vector(y, name="y"):
    """Enforcer FFI: valida dtype, contiguidad, finitud y subnormales."""
    if not isinstance(y, np.ndarray):
        raise TypeError(f"{name} must be np.ndarray")
    if y.dtype != np.float64:
        raise TypeError(f"{name} must be float64, got {y.dtype}")
    if y.ndim != 1:
        raise ValueError(f"{name} must be 1D, got {y.ndim}D")
    if not y.flags['C_CONTIGUOUS']:
        y = np.ascontiguousarray(y, dtype=np.float64)
    if not np.all(np.isfinite(y)):
        raise ValueError(f"{name} contains NaN or Inf")

    # Sanitización de subnormales (BG-04 Fix)
    tiny = np.finfo(np.float64).tiny  # 2.2250738585072014e-308
    subnormal_mask = (np.abs(y) < tiny) & (y != 0.0)
    if np.any(subnormal_mask):
        y = y.copy()  # No mutar el array del caller
        y[subnormal_mask] = np.copysign(0.0, y[subnormal_mask])

    return y
```

---

## 📋 RESUMEN DE ACCIONES V759

| Acción | Archivo | Líneas | Costo |
| :----- | :------ | :----- | :---- |
| Mover `enable_ftz_daz()` dentro de `#pragma omp parallel` | kernel_cpp_v759.cpp | L151→L166, L307→L326, L369→L387 | 0 ns overhead |
| Agregar sanitización de subnormales en Python | polydim_v759_monolito.py | require_f64_vector() | O(D) comparación, una sola vez |
| Agregar test canario de subnormales en Suite | raw_silicon_benchmark_v759.py | Nueva Suite 7 | Verificar que 1e-320 → 0.0 bajo FTZ |
| Documentar política IEEE-754 | readme_first.md | Sección nueva | Declarar pérdida de gradual underflow |
