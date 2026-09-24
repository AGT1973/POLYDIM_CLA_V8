# Auditoría Bulldog — POLYDIM: kernel_cpp_v768.cpp + kernel_rust_v768.rs
## Primer pase sobre código real (no teoría)

Archivos revisados línea por línea: `kernel_cpp_v768.cpp` (1122 líneas), `kernel_rust_v768.rs.txt`, cruzados contra `polydim.h` (original, ya revisado en la ronda anterior).

---

## Hallazgo 1 (grave, patrón repetido x3): el chequeo de aliasing protege el par equivocado

`overlaps()` está bien implementado como función (línea 91-95, comparación de rangos de bytes correcta). El problema es **contra qué se usa**:

- `polydim_rodrigues_geodesic_f64` (línea 197-198): compara `overlaps(y_out, u, bytes)` y `overlaps(y_out, v, bytes)`. Pero en esta firma `y_out` **no** es `__restrict__` — el solapamiento con `y_out` es legal por diseño (F-03, in-place). Los que sí son `__restrict__` (`u`, `v`) nunca se comparan entre sí.
- `polydim_stiefel_cayley_smw_f64` (línea 493-494): mismo patrón. `X`, `G`, `Y_out` son los tres `__restrict__`, pero solo se compara `Y_out` contra `X`/`G`. `X` contra `G` nunca se verifica.
- `polydim_orthonormalize_pair_f64`: no hay ningún `overlaps()`. `u`, `v` son `__restrict__` y si el llamante pasa `u==v`, es UB antes de llegar a cualquier lógica.

**Por qué importa:** si un llamante pasa `u==v` (o `X==G`), el comportamiter es indefinido por el estándar de C++ — el compilador puede asumir que eso nunca ocurre y generar código que se comporte de cualquier forma, incluida la posibilidad de que el propio `overlaps()` no se ejecute como se espera. El código de error que existe para esto (`POLYDIM_ERR_ALIASED_BUFFERS`) queda, en la práctica, sin poder activarse para el caso real.

**Parche — rodrigues (quitar restrict, comparar el par correcto):**
```cpp
// Firma: quitar __restrict__ de u y v
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_rodrigues_geodesic_f64(
    const double* y, const double* u, const double* v, double* y_out,
    double theta, uint64_t D,
    const PolydimTolerances* tol_in, PolydimReport* report)
{
    ...
    const size_t bytes = static_cast<size_t>(D) * sizeof(double);
    if (overlaps(u, v, bytes))              // <-- el par que realmente puede violar restrict
        return POLYDIM_ERR_ALIASED_BUFFERS;
    // y_out puede aliasear con y (in-place, F-03), con u o con v (no restrict ya) sin problema.
```

**Parche — orthonormalize_pair (agregar el chequeo que falta):**
```cpp
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_orthonormalize_pair_f64(
    double* u, double* v, uint64_t D, PolydimReport* report)   // sin __restrict__
{
    try {
        polydim_report_init(report);
        if (!u || !v) return POLYDIM_ERR_NULL_POINTER;
        if (D < 2)    return POLYDIM_ERR_INVALID_DIMENSION;
        const size_t bytes = static_cast<size_t>(D) * sizeof(double);
        if (overlaps(u, v, bytes)) return POLYDIM_ERR_ALIASED_BUFFERS;
        ...
```

**Parche — stiefel_cayley_smw (comparar X contra G, no solo contra Y_out):**
```cpp
extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_stiefel_cayley_smw_f64(
    const double* X, const double* G, double* Y_out,      // sin __restrict__ entre sí
    uint64_t D, uint32_t K, double tau,
    const PolydimTolerances* tol_in, PolydimReport* report)
{
    ...
    const size_t bytes = static_cast<size_t>(D) * static_cast<size_t>(K) * sizeof(double);
    if (overlaps(X, G, bytes)) return POLYDIM_ERR_ALIASED_BUFFERS;
    // Y_out puede aliasear X si se decide soportar in-place (documentarlo); si no se admite,
    // agregar también overlaps(Y_out, X, bytes) || overlaps(Y_out, G, bytes) aquí explícitamente.
```

Nota de diseño pendiente: decidir si `Y_out == X` (retracción in-place) debe soportarse. Si sí, documentarlo como F-03 lo hizo para Rodrigues. Si no, agregar el chequeo explícito arriba.

---

## Hallazgo 2 (grave): los códigos de error de Rust y C++ no son el mismo contrato

| Código | `polydim.h` (C) | `kernel_rust_v768.rs` |
|---|---|---|
| -4 | `DEGENERATE_NORM` | `SubnormalDetected` |
| -6 | `SEQLOCK_RACE` | `TopologyFragmented` |
| -8 | `INVALID_SCALAR` | `DegenerateNorm` |
| -9 | `BASIS_NOT_ORTHONORMAL` | `SeqLockRace` |
| -10 a -14 | `POINT_OFF_MANIFOLD`, `ALIASED_BUFFERS`, `COMPENSATION_BROKEN`, `ALLOC`, `INTERNAL` | (no existen) |
| -99 | (no existe) | `ErrPanicCaught` |

Cualquier capa que interprete un `int32_t` devuelto por una función Rust usando la tabla `polydim_status_string()` (que solo conoce el enum de C) va a mostrar el mensaje equivocado. Ejemplo concreto: Rust devuelve `-9` (`SeqLockRace`, lectura en carrera) y `polydim_status_string(-9)` responde `"BASIS_NOT_ORTHONORMAL"`.

**Parche — unificar el enum de Rust al de C:**
```rust
#[repr(C)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PolydimRustStatus {
    Success                   = 0,
    ErrNullPointer            = -1,
    ErrInvalidDimension       = -2,
    ErrNanOrInf               = -3,
    ErrDegenerateNorm         = -4,   // antes: SubnormalDetected
    ErrNumericalInstability   = -5,
    ErrSeqLockRace            = -6,   // antes: TopologyFragmented
    ErrBufferOverflow         = -7,
    ErrInvalidScalar          = -8,   // antes: DegenerateNorm (duplicado con -4, corregido)
    ErrBasisNotOrthonormal    = -9,   // antes: SeqLockRace
    ErrTopologyFragmented     = -15,  // nuevo código propio, no pisa el rango de C
    ErrInternal               = -14,  // mapea a la categoría existente en C
}
```
Y el pánico atrapado debe mapear a un código que exista en el contrato C — usar `POLYDIM_ERR_INTERNAL` (-14) en vez de inventar `-99` fuera de la tabla:
```rust
match result {
    Ok(status) => status as i32,
    Err(_) => PolydimRustStatus::ErrInternal as i32,   // antes: ErrPanicCaught = -99
}
```
Si se quiere distinguir "pánico atrapado" de "excepción C++ atrapada" en los logs, hacerlo en un campo de diagnóstico aparte — no en el código de retorno que ambos lenguajes comparten.

---

## Hallazgo 3 (grave, único no encontrado por inspección de contrato, solo por trazar el código): el guardián de invariantes de Rust puede devolver `Success` sobre datos corruptos

En `polydim_rust_verify_invariants`, la validación de entrada es:
```rust
if val.is_nan() || val.is_infinite() { return PolydimRustStatus::ErrNanOrInf; }
let sq = val * val;
```
Se valida `val`, nunca `sq`. Si `val` es finito pero `|val| > ~1.34e154` (el umbral donde `f64` hace overflow al elevar al cuadrado — exactamente el rango de una lectura corrupta/wild pointer), `sq` se vuelve `+inf` sin que nada lo detecte ahí. Trazando la ejecución: `t = sum + sq = inf`; en la rama de compensación, `sq - t = inf - inf = NaN`; `c` queda `NaN`; al final `norm_sq = sum + c = NaN`; `drift = (NaN.sqrt() - 1.0).abs() = NaN`. La comparación final `drift > tol` con `drift = NaN` es **`false`** (las comparaciones con NaN son siempre falsas, tanto en Rust como en IEEE-754), así que la función **no** entra al branch de error y cae en `PolydimRustStatus::Success`.

Es la función cuyo único propósito es detectar corrupción, fallando en detectar corrupción, en el escenario exacto (dato corrupto de gran magnitud) para el que fue diseñada.

**Parche:**
```rust
let sq = val * val;
if sq.is_infinite() {                      // overflow al elevar al cuadrado
    return PolydimRustStatus::ErrNanOrInf;
}
// ... resto del acumulador Neumaier igual ...

// Antes de comparar contra tol, blindar la comparación final:
let norm_sq = sum + c;
if norm_sq.is_nan() || norm_sq.is_infinite() {
    return PolydimRustStatus::ErrNumericalInstability;
}
if norm_sq <= 1e-300 {
    return PolydimRustStatus::ErrDegenerateNorm;
}
let norm = norm_sq.sqrt();
let drift = (norm - 1.0).abs();
let tol = 64.0 * EPS_MACH;
if !(drift <= tol) {          // "not <=" atrapa también NaN, a diferencia de "drift > tol"
    return PolydimRustStatus::ErrNumericalInstability;
}
```
El cambio de `drift > tol` a `!(drift <= tol)` es la corrección mínima: convierte el caso NaN (que antes caía silenciosamente al éxito) en un error, porque la negación de una comparación falsa con NaN es verdadera.

---

## Hallazgo 4 (grave): `polydim_rust_betti1_guard` no calcula Betti-1

El código cuenta `edges` (línea "edges += 1") pero esa variable nunca se vuelve a leer. La única condición de error es `components > 1`, que es Betti-0 (número de componentes conexas), no Betti-1 (ciclos independientes). El propio comentario en el archivo da la fórmula correcta y no la ejecuta:
```rust
// Betti-1 = Edges - Vertices + Connected Components
```
**Parche (con el cuidado de no restar `usize` sin signo, que puede underflowear):**
```rust
let betti1: i64 = edges as i64 - n as i64 + components as i64;
if components > 1 {
    return PolydimRustStatus::ErrTopologyFragmented;
}
if betti1 > 0 {
    // Decisión de diseño pendiente: ¿cualquier ciclo es motivo de rechazo,
    // o hay un umbral de ciclos tolerados para este grafo de agentes?
    // Ninguno de los documentos de teoría lo especifica.
    return PolydimRustStatus::ErrTopologyFragmented; // o un código nuevo, p. ej. ErrBettiNonzero
}
```
Esto necesita una decisión tuya, no mía: ¿qué política de β1 corresponde al enjambre de agentes? El dossier nunca lo dice, solo dice que se "certifica".

---

## Hallazgo 5: el Rust real es V762, no V768, y no tiene el fix F-11 que el tribunal certificó

El encabezado del archivo dice `POLYDIM V762`. `03_MULTI_AI_TRIBUNAL_VERDICTS.md` certificó como cerrado el hallazgo F-11 ("Rust FFI Hole... desajuste de 5 vs 3 argumentos... Rust exige align_offset(8), usa catch_unwind"). Ninguna de esas dos cosas aparece en este archivo: no hay `align_offset` en ningún lado, y las dos funciones ya usan `catch_unwind` pero eso no es evidencia de F-11 específicamente (ya lo hacían presumiblemente antes también). El archivo que tengo no es el que el tribunal dice haber revisado.

---

## Hallazgo 6: la API pública no puede ubicar el payload de un slot PMTP

`PMTP_Control` es opaco en `polydim.h` (`typedef struct PMTP_Control PMTP_Control;`, sin miembros visibles). `sizeof(PMTP_Control)` y `sizeof(PMTP_SlotHeader)` solo existen dentro de `kernel_cpp_v768.cpp` (líneas 818-832), invisibles para cualquier llamante externo. Sin esos tamaños, ningún proceso Python/Rust/Dart puede calcular dónde empieza el área de payload de un slot — y ninguna función declarada en el header (`write_begin`, `write_commit`, `read_begin`, `read_validate`) devuelve un puntero al payload. La transferencia "zero-copy" de tensores no es ejecutable con el contrato tal como está.

**Falta declarar algo como:**
```c
/* En polydim.h */
POLYDIM_EXPORT void* POLYDIM_CALL polydim_pmtp_payload_ptr(PMTP_Control* c, uint32_t slot);
```
```cpp
/* En kernel_cpp_v768.cpp */
extern "C" POLYDIM_EXPORT void* POLYDIM_CALL polydim_pmtp_payload_ptr(PMTP_Control* c, uint32_t slot) {
    if (!c || slot >= c->num_slots) return nullptr;
    return reinterpret_cast<char*>(c) + sizeof(PMTP_Control)
         + static_cast<size_t>(c->num_slots) * sizeof(PMTP_SlotHeader)
         + static_cast<size_t>(slot) * c->payload_bytes;
}
```

---

## Hallazgo 7: límite de K inconsistente entre funciones del mismo pipeline

`polydim_cholqr2_f64` (línea 1005): `if (K > 1024) return POLYDIM_ERR_BUFFER_OVERFLOW;`
`polydim_project_tangent_stiefel_f64` y `polydim_stiefel_cayley_smw_f64`: usan `POLYDIM_MAX_K` = 512 (línea 57).

Un `K` entre 513 y 1024 pasa CholQR2 y falla en las otras dos funciones del mismo flujo Stiefel. Unificar a una sola constante.

---

## Lo que está bien (para que quede registrado, no solo lo que falta)

- La suma compensada Neumaier (struct `Neumaier` en C++, líneas 76-87; bucle equivalente en Rust) está correctamente implementada en ambos lenguajes — coincide con el algoritmo Kahan-Babuska-Neumaier de libro.
- El diseño central del Seqlock (`PMTP_SlotHeader::seq` como contador monotónico de 64 bits, ticket lock de escritor único vía `wticket`/`wlock`, publicación de `pub_slot`/`pub_seq` solo en `write_commit`) es correcto y genuinamente libre de ABA: un contador de 64 bits que nunca se reinicia no puede repetir un valor visto antes dentro de ninguna escala de tiempo realista. El emparejamiento release/acquire entre `write_commit` y `read_begin`/`read_validate` es el correcto para publicar datos entre hilos.
- Los tres casos de `polydim_selftest_all` (theta NaN, base no ortonormal, punto fuera de la variedad) son consistentes con el orden real de chequeos en `polydim_rodrigues_geodesic_f64` y deberían pasar tal como están escritos.

---

## Sin revisar todavía en este pase

- El solver Sherman-Morrison-Woodbury dentro de `stiefel_cayley_smw_f64` (aprox. líneas 700-780, la parte BLAS/no-BLAS del sistema lineal K2×K2) — no llegué a trazarlo con el mismo nivel de detalle que el resto.
- Inicialización de `PMTP_Control`/`PMTP_SlotHeader` vía `std::memset` en lugar de construcción propia de los `std::atomic` — funciona en la práctica en x86/ARM pero es técnicamente no conforme al estándar de C++; placement-new (`new (c) PMTP_Control{}`) sería la forma correcta si se quiere cumplimiento estricto. Lo marco como hallazgo menor, no bloqueante.
