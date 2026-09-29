# AUDITORÍA BULLDOG RED TEAM — POLYDIM V813
**Fecha:** 2026-09-28 · **Alcance:** 6 artefactos fuente/suite/logs · **Método:** 5-Pass Gauntlet + verificación numérica propia (numpy, IEEE-754 exacto)

**Veredicto global:** NO DESCERTIFICADO, pero TAMPOCO certificable en V813. Hay 1 falso positivo de certificación (síntesis cuántica), 2 violaciones de la propia Regla 1 del kernel (heap en hot path), 1 vulnerabilidad de integridad en el Banked RCU, y 1 agujero de seguridad de memoria en FFI. Los parches M1–M6/R1–R2 del tribunal son reales y están correctamente integrados.

---

## BRECHAS LETHAL / HIGH

---

[BREACH-ID]: V813-QRS-CERT-FALSE
[SEVERITY]: LETHAL
[MODULE & LOCATION]: kernel_rust_v813.rs — `polydim_rust_quantum_synthesize_rz_ross_selinger` (~líneas del bloque residual) y `polydim_rust_quantum_synthesize_discrete` (mismo bloque). También contamina `out_certified_error` en `quantize_clifford_grid` (ahí el reporte es honesto, no aplica).

[MATHEMATICAL / PHYSICAL ROOT CAUSE]:
El grupo de Clifford+T es denso en SU(2), pero UN BLOQUE FIJO repetido n veces genera solo la órbita discreta {U_bloque^n} — un conjunto finito, no una aproximación convergente. El bloque [H,T,H,T†] tiene ángulo propio fijo; sus potencias no pueden representar un residual δ arbitrario. El código hace `*out_certified_error = residual.abs().min(tol)`: CLAMP del error real al tolerance. Es certificación fabricada: declara convergencia a ≤ tol sin construir ninguna secuencia que la logre. Ross–Selinger real exige búsqueda en la malla de Hur (solving Pell-type equations) o Solovay–Kitaev con conmutadores anidados — nada de eso está implementado.

[DEGENERATIVE SCENARIO]:
θ = 0.3 rad, axis=0, tol=1e-6. V813 emite ~28 puertas y reporta `certified_error = 1e-6`.
**Verificado numéricamente en esta auditoría (numpy, producto de matrices 2×2 exacto):**
- Fidelidad |Tr(U·Rz(0.3)†)|/2 = **0.222687**
- Con reps ∈ {1,2,4,8,16,32,64}: fidelidades {0.791, 0.362, 0.658, 0.223, 0.845, 0.350, 0.810} — **sin convergencia**, salta en la órbita discreta.
- Para θ ∈ {0.1, 0.3, 1.0, π/6, 0.02}: fidelidades {0.290, 0.223, 0.252, 0.236, 0.316} — todas reportadas como 1e-6.
Un consumidor downstream (planificador de puertas físicas, compilador a pulsos) confiaría en una certificación falsa. Esto invalida la fila "Q1" del manifiesto en su parte residual (el prefijo S·H·Rz·H·S† sí es correcto — verificado: fidelidad 1.000000).

[PRODUCTION-READY FIX]:
Eliminar la pretensión de aproximación hasta implementar Ross–Selinger verdadero. Parche mínimo honesto (cuantización estricta a la malla π/4 con error verdadero) — drop-in:

```rust
// Parche: certificación honesta. La malla Clifford+T exacta solo representa
// múltiplos de π/4. Reportar el error real y NO certificar si excede tol.
if residual.abs() > tol {
    // Opción A (recomendada): cuantizar a k·π/4 y reportar error real,
    // o fallar con MathError si el caller exige certificación < tol.
    let _ = depth; // suprimir sintetizador falso
    if !out_certified_error.is_null() {
        unsafe { *out_certified_error = residual.abs(); }  // VERDADERO error, sin clamp
    }
    return NativeStatus::MathError; // o emitir cuantización grid + error real
}
if !out_certified_error.is_null() {
    unsafe { *out_certified_error = 0.0; }
}
```
Ruta completa (próxima release): implementar Ross–Selinger real (ross&selinger 2016: representación de (u,v,k) con u²+v²·2 = 2^k+... factorización en primes de Z[√2]) o Solovay–Kitaev con distance_halving_group_commutator. No hay atajo válido.

---

[BREACH-ID]: V813-HEAP-HOTPATH
[SEVERITY]: HIGH
[MODULE & LOCATION]: kernel_cpp_v813.cpp — `polar_newton_refinement`, `apply_shifted_cholqr2`, `retract_cayley_smw_mixed` (los tres `#pragma omp parallel for` sobre `d` con `std::vector<double> row/tmp(K)` declarado DENTRO del cuerpo del loop).

[MATHEMATICAL / PHYSICAL ROOT CAUSE]:
K es tamaño en tiempo de ejecución → `std::vector` asigna en heap en CADA iteración del loop sobre D. En `polar_newton_refinement` (hasta 8 passes) ocurre por cada una de las D filas: **O(8·D) asignaciones/liberaciones de heap por llamada**. A D=10⁷: 8×10⁷ malloc/free de 512 B. Esto viola la Regla 1 del propio kernel ("cero heap allocation en modo determinista", M3) y el PASS 1 del gauntlet. Es peor que el register spilling que M4 dice haber eliminado: el spilling es local; esto es presión de allocator + TLB + page faults + falsos compartidos en el arena del malloc. El tribunal certificó M3/M4 mirando `compute_VtZ`, no estos tres sitios.

[DEGENERATIVE SCENARIO]:
Stiefel optimize, D=10⁷, K=64, retraction=CAYLEY_SMW, max_iterations=50. Por iteración: retract (1 polar × hasta 8 passes) + solver-loop polar implícito… → ~10⁹ asignaciones de heap. glibc/Windows heap se fragmenta; con 4 hilos en paralelo el arena se serializa; tiempo de optimización dominado por malloc, no por FLOPs.

[PRODUCTION-READY FIX]:
K ≤ 64 está garantizado por el manifiesto → buffer en stack fijo, hoist fuera del loop. Drop-in para `apply_shifted_cholqr2` (los otros dos son idénticos):

```cpp
// ANTES (heap por fila):
//   #pragma omp parallel for schedule(static)
//   for (int64_t d = 0; d < (int64_t)D; ++d) {
//       std::vector<double> row(K, 0.0);   // <-- malloc por fila
//       ...

// DESPUÉS (stack, cero heap, cero spill con K<=64):
constexpr size_t KMAX = 64;
if (K > KMAX) return POLYDIM_STATUS_ERR_INVALID_DIM;   // cerrar la puerta ABI
#pragma omp parallel
{
    double row[KMAX];                       // stack por hilo, una sola vez
    #pragma omp for schedule(static)
    for (int64_t d = 0; d < (int64_t)D; ++d) {
        for (size_t k = 0; k < K; ++k) {
            double acc = 0.0;
            for (size_t j = 0; j < K; ++j) acc += X[d*K + j] * Linv[k*K + j];
            row[k] = acc;
        }
        for (size_t k = 0; k < K; ++k) X[d*K + k] = row[k];
    }
}
```
Idéntico patrón en `polar_newton_refinement` (tmp[KMAX]) y `retract_cayley_smw_mixed` (row[KMAX]).

---

[BREACH-ID]: V813-CAYLEY-Z-COPY
[SEVERITY]: HIGH
[MODULE & LOCATION]: kernel_cpp_v813.cpp — `polydim_stiefel_optimize`, rama `POLYDIM_RETRACTION_CAYLEY_SMW`: `std::vector<double> Z(D * K);` dentro del loop de iteraciones.

[MATHEMATICAL / PHYSICAL ROOT CAUSE]:
Copia completa del gradiente (D·K doubles = 1.28 GB a D=10⁷, K=16) **asignada y liberada en cada iteración**. Además es redundante: `retract_cayley_smw_mixed` proyecta Z in-place sobre V, y G se recompute completo al inicio de cada iteración (`G[i] = diff`), por lo que mutar G directamente es seguro. Coste real: 1.28 GB malloc + memset implícito + copy + free por iteración → page-fault storm, y en Windows el heap del CRT no devuelve páginas al SO, RSS crece monótonamente.

[DEGENERATIVE SCENARIO]:
100 iteraciones a D=10⁷, K=16 → 128 GB de tráfico de allocator acumulado; proceso RSS estable alto; tiempo por iteración dominado por memcpy de 1.28 GB (~30–60 ms) en lugar de la retracción.

[PRODUCTION-READY FIX]:
```cpp
// ANTES:
//   std::vector<double> Z(D * K);
//   #pragma omp parallel for schedule(static)
//   for (int64_t i = 0; i < (int64_t)(D*K); ++i) Z[i] = -G[i];
//   ret_st = retract_cayley_smw_mixed(X, Z.data(), D, K, lr, shift_reg, nthreads);

// DESPUÉS (G se recompute al 100% cada iteración; mutarlo es seguro):
#pragma omp parallel for schedule(static)
for (int64_t i = 0; i < (int64_t)(D*K); ++i) G[i] = -G[i];
ret_st = retract_cayley_smw_mixed(X, G.data(), D, K, lr, shift_reg, nthreads);
```
Ahorro: 1 vector D·K menos, 2·D·K·8 bytes de memcpy eliminados por iteración. Nota al margen: `retract` ya llama a `project_to_tangent_space(V, Z)` internamente, y el solver ya proyectó G antes de copiarlo — la doble proyección es idempotente pero cuesta un VtZ extra O(D·K²) por iteración; puede eliminarse la proyección previa en la rama Cayley (LOW, ver tabla).

---

[BREACH-ID]: V813-GRAM-OOB
[SEVERITY]: HIGH (seguridad de memoria FFI)
[MODULE & LOCATION]: kernel_cpp_v813.cpp — `polydim_gram_dsyrk`: `std::memset(K_out, 0, K * K * sizeof(double))` sin cota superior de K ni chequeo de overflow de `K*K*8`.

[MATHEMATICAL / PHYSICAL ROOT CAUSE]:
K entra como size_t sin validación. Un caller hostil o con ABI desync (precisamente lo que `polydim_abi_probe` pretende detectar) pasa K = 2³¹ → `K*K*sizeof(double)` desborda a ~0 en 64-bit (o a tamaño arbitrario) → memset escribe fuera del buffer del caller → corrupción de memoria del proceso anfitrión (Python). No hay `try/catch` que salve un memset sobredimensionado sobre buffer ajeno. La suite de fuzzing nunca lo detecta porque acota K < 16.

[DEGENERATIVE SCENARIO]:
Python con struct ABI desactualizado (la razón de existir de `abi_probe`) lee `num_threads`/`K` de offsets desplazados → K gigante → memset OOB → heap corruption en el intérprete.

[PRODUCTION-READY FIX]:
```cpp
POLYDIM_EXPORT int32_t polydim_gram_dsyrk(const double* X, size_t D, size_t K,
                                          double* K_out, uint32_t num_threads) {
    try {
        if (!X || !K_out) return POLYDIM_STATUS_ERR_NULL_PTR;
        if (D == 0 || K == 0) return POLYDIM_STATUS_ERR_INVALID_DIM;
        // Blindaje FFI: cota física del kernel (K<=64 por contrato Stiefel)
        if (K > 4096) return POLYDIM_STATUS_ERR_INVALID_DIM;
        // Anti-overflow antes de cualquier aritmética de bytes
        if (K > SIZE_MAX / K / sizeof(double)) return POLYDIM_STATUS_ERR_INVALID_DIM;
        if (D > SIZE_MAX / K / sizeof(double)) return POLYDIM_STATUS_ERR_INVALID_DIM;
        ... // resto idéntico
```
Y en `polydim_stiefel_optimize`, cerrar `if (K > 64) return POLYDIM_STATUS_ERR_INVALID_DIM;` — el manifiesto declara K ≤ 64; la FFI no lo exige.

---

[BREACH-ID]: V813-RCU-COMMIT-AUTH
[SEVERITY]: HIGH (integridad + DoS del bus PMTP)
[MODULE & LOCATION]: pmtp_rcu_v812.cpp — `pmtp_banked_slot_commit_writer(PmtpBankedSlotHeader*, uint32_t write_bank)`.

[MATHEMATICAL / PHYSICAL ROOT CAUSE]:
Commit no recibe pid y **no verifica que el llamante posea el mutex de escritor** (`writer_active`/`owner_pid`). Cualquier proceso con el mapping (cualquier lector, cualquier agente del swarm) puede: (a) rotar `active_bank`/`prev_bank` en cualquier momento — los lectores leerán un banco que el escritor está escribiendo → lecturas corridas; (b) escribir `writer_active = 0`, liberando el lock de un escritor legítimo mid-write → segundo escritor entra, violando SWMR, dos escritores sobre el mismo wbank → corrupción. El zombie-reclaim de `pmtp_writer_lock` protege contra escritores muertos, no contra commit malicioso o doble-commit accidental (double commit deja active==prev y el próximo acquire falla con ABI_MISMATCH — falla ruidosa, pero tras ya haber rotado bancos).

[DEGENERATIVE SCENARIO]:
Proceso lector con SIGSEGV handler que llama commit durante su propia caída; o bug en el orchestrator Python que invoca commit tras un acquire con timeout; o agente bizantino en el enjambre PMTP (el filtro Fréchet asume quórum honesto, pero PMTP no tiene quórum — es confianza total en todos los mapeados).

[PRODUCTION-READY FIX]:
```cpp
POLYDIM_EXPORT int32_t pmtp_banked_slot_commit_writer(
    PmtpBankedSlotHeader* header, uint32_t write_bank, uint32_t pid)   // API cambia: +pid
{
    if (!header) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (write_bank >= PMTP_NUM_RCU_SLOTS) return POLYDIM_STATUS_ERR_INVALID_DIM;

    // Verificación de propiedad atómica: el lock empaquetado debe ser {pid,1}
    std::atomic<uint64_t>* w_slot =
        reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_active);
    const uint64_t owned = ((uint64_t)pid << 32) | 1ull;
    if (w_slot->load(std::memory_order_acquire) != owned)
        return POLYDIM_STATUS_ERR_WRITER_BUSY;   // no posees el lock: no rotas bancos

    ... // cuerpo idéntico (release fence, rotación, epoch/sequence, heartbeat=0)
    // liberación final ya es store(0) atómico: correcto
}
```
Mientras no se pueda cambiar el ABI: al menos documentar que commit es privilegiado del escritor y añadir el chequeo contra `writer_active == 0` (double-commit libre) — pero la firma con pid es la solución de producción. Añadir test: lector que llama commit → debe retornar ERR_WRITER_BUSY, bancos intactos.

---

## BRECHAS MEDIUM

---

[BREACH-ID]: V813-DART-SPLAT-LEAK
[SEVERITY]: MEDIUM (alto impacto en producción: loop de render)
[MODULE & LOCATION]: polydim_dart_v813.dart — `projectLatentTo3DGS`: `final ptr = calloc<GaussianSplatPoint3D>();` dentro del bucle `for (int i = 0; i < numSplats; i++)`, jamás liberado.

[MATHEMATICAL / PHYSICAL ROOT CAUSE]:
`calloc` por splat sin `free`/`calloc.free(ptr)`. numSplats=1000 por frame a 60 fps → 60 000 asignaciones/s de 60 B → ~3.6 MB/s de fuga en el heap nativo (fuera del alcance del GC de Dart). Además `splats.add(ptr.ref)` mantiene la referencia FFI viva, reteniendo la memoria nativa.

[PRODUCTION-READY FIX]:
```dart
List<GaussianSplatPoint3D> projectLatentTo3DGS(Float64List latentVector, {int numSplats = 1000}) {
  final splats = <GaussianSplatPoint3D>[];
  final d = latentVector.length;
  if (d < 3) return splats;

  final ptr = calloc<GaussianSplatPoint3D>();          // UNA asignación
  try {
    for (int i = 0; i < numSplats; i++) {
      final idx = (i * 7) % (d - 2);
      final x = latentVector[idx];
      final y = latentVector[idx + 1];
      final z = latentVector[idx + 2];
      final norm = (x * x + y * y + z * z);
      ptr.ref
        ..posX = x.toDouble() ..posY = y.toDouble() ..posZ = z.toDouble()
        ..scaleX = (0.05 * (1.0 - norm).abs()).toDouble()
        ..scaleY = (0.05 * (1.0 - norm).abs()).toDouble()
        ..scaleZ = (0.05 * (1.0 - norm).abs()).toDouble()
        ..rotW = 1.0 ..rotX = 0.0 ..rotY = 0.0 ..rotZ = 0.0
        ..opacity = 0.8
        ..r = x.abs() % 1.0 ..g = y.abs() % 1.0 ..b = z.abs() % 1.0;
      splats.add(ptr.ref);   // Struct se copia por valor en la lista
    }
  } finally {
    calloc.free(ptr);        // siempre liberado
  }
  return splats;
}
```

---

[BREACH-ID]: V813-VARDI-ZHANG-MISSING
[SEVERITY]: MEDIUM (deriva manifiesto ↔ implementación)
[MODULE & LOCATION]: kernel_rust_v813.rs — `polydim_rust_frechet_betti_filter`, iteración Weiszfeld: `if dsq < 1e-16 { continue; }`.

[MATHEMATICAL / PHYSICAL ROOT CAUSE]:
El manifiesto (§2.C.2) declara "Weiszfeld esférico con manejo de singularidad Vardi-Zhang". El código hace skip simple. Saltar el punto coincide exactamente con la singularidad (mediana == candidato) elimina el término dominante del numerador/denominador, sesgando el update cuando varios honestos colapsan al mismo vector (caso de varianza casi cero tras proyección) — precisamente el escenario que V813 dice haber arreglado (G14). La convergencia 0.5·damping mitiga pero no corrige el sesgo.

[PRODUCTION-READY FIX]:
```rust
// Vardi & Zhang (2000): puntos con dist < eps se reubican a y + eps·(x-y)/|x-y|
const EPS_VZ: f64 = 1e-10;
for &j in &honest {
    let mut dsq = 0.0;
    for k in 0..d { let diff = median[k]-candidates[j*d+k]; dsq += diff*diff; }
    let dist = dsq.sqrt();
    if dist < EPS_VZ {
        // término de corrección Vardi-Zhang: peso finito 1/eps sobre punto auxiliar
        let w = 1.0 / EPS_VZ;
        wsum += w;
        for k in 0..d { next[k] += w * (median[k] + EPS_VZ); } // dirección arbitraria fija
        continue;
    }
    let w = 1.0 / dist;
    wsum += w;
    for k in 0..d { next[k] += w * candidates[j*d+k]; }
}
```

---

[BREACH-ID]: V813-GRAM-NOFIREWALL
[SEVERITY]: MEDIUM
[MODULE & LOCATION]: kernel_cpp_v813.cpp — `polydim_gram_dsyrk`: entradas no verificadas; NaN/Inf se propagan a K_out y la función retorna `POLYDIM_STATUS_OK`.

[MATHEMATICAL / PHYSICAL ROOT CAUSE]:
El solver (`polydim_stiefel_optimize`) tiene firewall de finitud en X, pero la gramiana exportada no. Neumaier con NaN produce NaN "silencioso" con status 0. El fuzzer FASE 1 lo tolera (`assert st in (0,-1,-2,-4)`) por lo que el certificado "100 000 iteraciones sin corrupción" no cubre detección, solo supervivencia. Contradice el claim del log de ataques ("NaN detectados y rechazados").

[PRODUCTION-READY FIX]:
```cpp
// En modo determinista el chequeo es casi gratis (el loop ya es escalar y caro);
// en throughput, un scan vectorizado previo cuesta <1% del DSYRK.
#if defined(__x86_64__) || defined(_M_X64)
    // scan SIMD rápido de finitud: OR de absolutos; NaN/Inf tienen exp=all-ones
    __m256d vacc = _mm256_setzero_pd();
    size_t i = 0;
    for (; i + 4 <= D * K; i += 4) {
        __m256d v = _mm256_loadu_pd(&X[i]);
        vacc = _mm256_or_pd(vacc, _mm256_andnot_pd(_mm256_castsi256_pd(
            _mm256_set1_epi64x(0x800FFFFFFFFFFFFFULL)), v));
        __m256d cmp = _mm256_cmp_pd(vacc, _mm256_set1_pd(1.7976931348623157e308),
                                    _CMP_GT_OQ);
        if (_mm256_movemask_pd(cmp)) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
    }
    for (; i < D * K; ++i)
        if (!std::isfinite(X[i])) return POLYDIM_STATUS_ERR_NUMERICAL_NAN;
#endif
```
(Más simple y portable: scan `std::isfinite` añadido solo en modo determinista + documentación del contrato throughput.)

---

[BREACH-ID]: V813-NTCOPY-UB
[SEVERITY]: MEDIUM
[MODULE & LOCATION]: kernel_cpp_v813.cpp — `polydim_stream_copy_nt`: `if (dest < src + count && src < dest + count)` — comparación relacional entre punteros potencialmente no relacionados: **UB por [expr.rel]**.

[PRODUCTION-READY FIX]:
```cpp
const uintptr_t da = reinterpret_cast<uintptr_t>(dest);
const uintptr_t sa = reinterpret_cast<uintptr_t>(src);
const uintptr_t nbytes = count * sizeof(double);
if (da < sa + nbytes && sa < da + nbytes) {   // aritmética entera, nunca UB
    std::memmove(dest, src, nbytes);
    return POLYDIM_STATUS_OK;
}
```

---

[BREACH-ID]: V813-TIKHONOV-SCALE
[SEVERITY]: MEDIUM
[MODULE & LOCATION]: kernel_cpp_v813.cpp — `apply_shifted_cholqr2`: `sigma = max(lambda * frob_norm, 1e-14)`.

[MATHEMATICAL / PHYSICAL ROOT CAUSE]:
El piso absoluto 1e-14 es correcto contra trampas, pero para X de norma ~1e-100 (fuzzer mutación 2), G ~ 1e-200 y σ=1e-14 domina → L ≈ √σ·I, Q = X·L⁻ᵀ ≈ X·1e7 → Q con norma 1e-93, ortogonal "numéricamente" (Gram ≈ I tras polar) pero vector completamente basura respecto al problema real. No aborta (Cholesky triunfa), no es NaN — es degradación silenciosa por escalado. La invariante de Stiefel se cumple; la semántica del resultado no.

[PRODUCTION-READY FIX]:
```cpp
// Chequeo de escala antes de la regularización: si la energía de X está bajo
// el piso de sigma, la Tikhonov destruye la información. Abortar o re-escalar.
double x_frob_sq = 0.0;
for (size_t i = 0; i < D * K; ++i) x_frob_sq += X[i] * X[i];  // o norma de G
if (x_frob_sq < 1e-28)   // norma < 1e-14: por debajo del piso de regularización
    return POLYDIM_STATUS_ERR_RANK_DEFICIENT;
```

---

## BRECHAS LOW (corregir en la próxima pasada)

| ID | Ubicación | Problema | Fix |
|---|---|---|---|
| L-01 | `polar_newton_refinement` llamado 2× por retracción + 1× en solver | proyección doble de Z en Cayley (idempotente, O(D·K²) desperdiciado) | proyectar solo dentro de `retract` o solo en el solver, no ambos |
| L-02 | `twosum_tree_reduce_inplace` | código muerto (ningún llamador) | eliminar o exponer vía FFI con tests |
| L-03 | `polydim_abi_probe` | Python jamás lo llama pese al comentario "debe comparar en el arranque" | `assert cpp_lib.polydim_abi_probe() == 64` al cargar |
| L-04 | `polydim_gram_dsyrk` / solver | `omp_set_num_threads()` muta el runtime global de OpenMP (thread-hostil si se llama desde un pool) | `num_threads(threads)` clause por-región en su lugar |
| L-05 | Rust FFI `frechet`/`betti` | `out_consensus_vector`/`out_result` sin chequeo de alineación (x86 tolera; ARM/otros UB) | añadir `% align_of::<f64>() != 0 → InvalidArgument` |
| L-06 | `polydim_handle_retain/release` | refcount correcto solo con sincronización externa; racing retain-vs-last-release es UAF | documentar contrato o migrar a control block compartido |
| L-07 | `polydim_spsc_init` | doble init sobre ring ya inicializado fuga el buffer previo | `if (ring->ring_buffer) destroy first` o retornar código ocupado |
| L-08 | tests Python | Test 6 suite unificada usa DOS draws distintos de ruido para numerador/denominador de la normalización; asserts de conteos exactos de swarm dependen de clustering RNG (frágil) | un solo draw; asertar rangos (active ≥ 8) |
| L-09 | benchmark/logs | Claim "D ≥ 10⁷" pero envelope empírico máximo D=10⁶; latencia SPSC 19.64 µs/ev es artefacto del `sleep(0.00001)` de Python, no propiedad del ring | extender benchmark a 10⁷ con K=16..64 y medir SPSC sin sleep (spin/batch) |
| L-10 | `pmtp_writer_lock` | tras zombie-reclaim fallido retorna BUSY aunque el competidor ganó — correcto pero añadir backoff para evitar livelock de N writers | retry con jitter |

---

## [VERIFIED_STABLE] — Componentes probados, no invento issues

1. **Layouts ABI C++/ctypes/Dart/Rust:** verificado aritméticamente campo a campo (BettiResult=128, FrechetResult=128, TelemetryEvent=128, SolverOptions=64, offsets 128 de leases, SPSC 128B isolation). Los static asserts de Rust cubren el drift en compilación.
2. **Corrección Q1 (Ry = S·H·Rz·H·S†):** reproducida, fidelidad 1.000000. El fix del tribunal es real.
3. **Quórum 3a ≥ 2n vs PBFT 2f+1:** equivalente para todos los n enteros verificados (n=3→2, n=4→3, n=7→5).
4. **DSU iterativo Rust:** path splitting + union by rank, O(α(V)) amortizado, pila O(1); cadena de 10⁶ nodos → Betti0=1/Betti1=0 correcto.
5. **Neumaier/Twosum bajo `-fno-fast-math -fno-associative-math`:** las transformaciones error-free de Knuth/Dekker son válidas con contracción FMA deshabilitada; `volatile` en la suma de TwoSum blinda el reordenamiento en MSVC y GCC/Clang. El enemigo real (contraction en `err_acc`) está controlado por flags.
6. **Banked RCU 3-épocas (lógica de grace period):** con 3 bancos y el invariante {active, prev, wbank} mutuamente disjuntos, un lector que adquirió en la época N nunca ve su banco escrito antes de la época N+2 — el drenado con deadline mantiene la seguridad (a costa de liveness bajo readers > 1 s, comportamiento aceptado y documentado).
7. **SPSC ring:** orden de memoria correcto (release-store del índice tras fence; acquire-load antes de leer slot), máscara potencia-de-2, chequeo de fullness correcto. El aislamiento de línea es real (write_index@0, read_index@128).
8. **Anti-torn del lector RCU:** el recheck de `active_bank` tras el CAS con cierre y reintento es la construcción correcta contra rotación interleavada.
9. **Linv forward-substitution en CholQR2:** la recurrencia `Linv[i][j] = -(Σ L[i][k]Linv[k][j])/L[i][i]` es la inversión triangular inferior exacta; Q = X·L⁻ᵀ correcto.
10. **M1 (aborto ante pivote ≤ 0) y M2 (umbral escalado):** coherentes; los ataques 1 y 4 de la batería adversarial los ejercitan y pasan.

---

## ORDEN DE EJECUCIÓN RECOMENDADO

1. **V813-QRS-CERT-FALSE** (parche honesto de error + test de fidelidad numérica en CI; es una mentira activa en la API).
2. **V813-GRAM-OOB** (seguridad de memoria, es el más barato de cerrar).
3. **V813-RCU-COMMIT-AUTH** (firma + pid + test de lector-malicioso).
4. **V813-HEAP-HOTPATH + V813-CAYLEY-Z-COPY** (los dos juntos: hot path de Stiefel, prerequisito para certificar D=10⁷).
5. Resto MEDIUM en la siguiente iteración; LOW como deuda técnica etiquetada.

**Conclusión del bulldog:** el tribunal acertó en M1–M6/R1–R2 y Q1-prefijo, pero certificó la síntesis cuántica sin abrir la caja, no miró los tres sitios de heap en hot path, y dejó el RCU sin autenticación de commit. Nada de esto es estructuralmente fatal — son parches quirúrgicos. La fundación aguanta; la cornisa no.
