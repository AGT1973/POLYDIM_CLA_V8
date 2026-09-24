# POLYDIM V768 — Bulldog Red-Team Audit

Fecha de auditoría: 2026-09-21

## Veredicto técnico

La entrega V768 **no puede considerarse cerrada ni certificada para producción** con el material incluido en `auditoria_externa.zip`.

La auditoría encontró fallas reproducibles de ABI, memoria, concurrencia, complejidad, estabilidad numérica y correspondencia entre teoría y código. Varias son P0: pueden impedir la ejecución, producir UB, corromper datos, violar el objetivo asintótico o invalidar una afirmación matemática central.

El hallazgo más importante no es uno solo, sino una clase de problemas: varias propiedades que el dossier declara como “certificadas” no están implementadas por el código entregado o no pueden reproducirse porque faltan artefactos.

---

# 0. Evidencia y método

El ZIP contiene sólo 4 archivos:

- `01_README_THEORY_AND_AUDIT_DEMANDS.md`
- `02_ALL_SOURCE_SCRIPTS_MONOLITH.md`
- `03_MULTI_AI_TRIBUNAL_VERDICTS.md`
- `04_SILICON_CONTRACT_AND_BENCHMARKS.md`

El README afirma que se entregan fuentes individuales, headers y logs `eval_logs/...`, pero esos artefactos no están dentro del ZIP.

Se extrajeron 13 fuentes del monolito para auditoría estática. Los archivos Python, una vez eliminadas las marcas de envoltura del monolito, pasan `py_compile`. El C++ pudo compilarse **sólo después de reconstruir un `polydim.h` mínimo para la auditoría**, porque el header declarado en el inventario no está incluido.

Pruebas ejecutadas:

- GCC 14.2, C++20, OpenMP.
- Build normal y build `-ffast-math`.
- UBSan para alineación PMTP.
- Pruebas ctypes contra el kernel C++ compilado.
- Casos adversariales de overlap, tolerancias NaN, overflow de tamaños, LSM y adapter.
- Prueba TCP de payload truncado en MIR-Wire.

Resultados reproducidos relevantes:

- `-ffast-math`: el self-test de compensación devuelve `-12`, por lo que ese detector sí funciona cuando se ejecuta.
- PMTP con puntero desalineado: UBSan aborta por acceso a `PMTP_Control` que requiere 64 bytes.
- `polydim_pmtp_sizeof(64, UINT64_MAX)` devuelve `4096`: overflow aritmético real.
- `polydim_project_sphere_f64` con overlap parcial devuelve `SUCCESS` pero corrompe el vector.
- Rodrigues con overlap parcial de `y_out` sobre `y` termina con salida corrupta y `DEGENERATE_NORM` después de haber escrito datos.
- LSM declarado “ortogonal”: matriz reconstruida de prueba presenta errores de ortogonalidad ~0.8–1.8 y radio espectral distinto de 1.
- MIR-Wire acepta y ACKea un payload truncado, rellenando silenciosamente el resto con ceros.
- Tangent Adapter desborda con `[1e308,1e308,...]` y no es biyectivo en cero/subnormales pequeños.

---

# PASS 1 — Asymptotic Annihilation

## F-001 — P0 — Stiefel vuelve a materializar `D×K`

**Archivo:** `kernel_cpp_v768.cpp` 621–674, especialmente 622.

```cpp
std::vector<double> G_proj(static_cast<size_t>(D) * K, 0.0);
```

### Causa

La documentación declara workspace O(K²), pero `G_proj` consume Θ(DK).

Para `D=10^7`, `K=512`, FP64:

`10^7 × 512 × 8 = 40.96 GB`

sólo para `G_proj`.

Además existen X, G e Y, cada uno de tamaño D×K. En esa configuración la huella base supera 120 GB aun antes de arenas y matrices auxiliares.

### Impacto

La afirmación “huella de memoria O(K²)” es falsa para la implementación entregada.

### Parche C++

Eliminar `G_proj`. Calcular cada fila proyectada on-the-fly:

```cpp
// Workspace por hilo: K elementos, no D*K.
std::vector<double> row_gp(K);

for (uint64_t i = 0; i < D; ++i) {
    const double* xi = X + i*K;
    const double* gi = G + i*K;
    for (uint32_t c = 0; c < K; ++c) {
        double s = gi[c];
        for (uint32_t q = 0; q < K; ++q)
            s -= xi[q] * Sym[q*K + c];
        row_gp[c] = s;
    }
    // Acumular Gp^T Gp aquí.
}
```

En la pasada final, recomputar `gpi` fila a fila en vez de leer una matriz materializada.

Workspace objetivo: `O(T K² + K²)` y no `O(DK)`.

---

## F-002 — P0 — LSM separado es O(D²), no O(D)

**Archivo:** `polydim_liquid_state_machine.py` 31–33.

```python
nnz = max(1, int(dim * sparsity))
self.sparse_indices = [np.random.choice(dim, nnz, replace=False) for _ in range(dim)]
self.sparse_weights = [np.random.randn(nnz) for _ in range(dim)]
```

Con `sparsity=0.05`, `nnz = 0.05D`, luego memoria y cómputo son Θ(D²).

En `D=10^7`: aproximadamente `5×10^12` aristas.

### Parche Python

Usar grado fijo:

```python
nnz = 16
self.indices = np.empty((dim, nnz), dtype=np.int32)
self.weights = np.empty((dim, nnz), dtype=np.float32)
```

Pero para `D=10^7` tampoco debe construirse con 10 millones de llamadas a `np.random.choice`. Generar vectorizadamente o usar una transformación estructurada implícita.

### Mejor opción SOTA

Sustituir la “matriz sparse orthogonal-like” por un operador ortogonal implícito: producto de permutaciones, diagonales de signos y butterflies/Hadamard. No materializa D² y conserva ortogonalidad por construcción.

---

## F-003 — P1 — El LSM monolítico es O(D), pero no O(1) y es impracticable en Python a D=10^7

**Archivo:** `polydim_v768_monolito.py` 328–334.

Tiene grado fijo 16, por lo que el conteo asintótico en D es lineal. Sin embargo crea **D objetos NumPy para índices y D objetos para pesos**.

Para D=10 millones, 20 millones de objetos Python/NumPy hacen inviable el diseño aunque el número de coeficientes sea lineal.

### Parche

Almacén compacto `(D,16)` y kernel nativo/Numba/C++/Triton. El bucle Python 10 millones de iteraciones también debe desaparecer.

---

## F-004 — P0 — Triton falla precisamente en D≈10^7

**Archivo:** `polydim_triton_kernel_v768.py` 138–157.

Para `BLOCK_SIZE=1024`, `D=10^7` produce ~9766 parciales. Por tanto `block_reduce > 4096` y entra en el fallback:

```python
sn_half = math.sin(half_theta)
```

pero el archivo no importa `math`.

### Resultado

`NameError: name 'math' is not defined` en la dimensión objetivo.

### Parche mínimo

```python
import math
```

### Parche correcto

No bajar la reducción a CPU. Hacer reducción jerárquica multi-stage en GPU hasta quedar en un solo bloque.

---

## F-005 — P1 — “O(1) transfer” confunde control con tráfico físico

Un descriptor/puntero puede publicarse en O(1), pero producir y consumir un tensor D-dimensional requiere tocar Θ(D) bytes.

Para D=10^7 FP64, un tensor son 80 MB. Un anillo de 4 slots necesita al menos 320 MB de payload.

La formulación correcta es:

- publicación/control: O(1),
- copia: potencialmente 0 si se comparte el mismo backing store,
- tráfico DRAM/lectura por consumidores: Θ(D).

---

# PASS 2 — Concurrency Bloodbath

## F-006 — P0 — `PMTPSlabChannel` nunca inicializa el control C++

**Archivo:** `polydim_v768_monolito.py` 90–134.

El constructor crea memoria y `PMTPControl.from_buffer`, pero no llama a `polydim_pmtp_init`.

Luego `write_tensor()` llama a `write_begin()`. `num_slots` permanece cero, y C++ hace:

```cpp
(... + 1) % c->num_slots;
```

### Impacto

División módulo cero / UB o fallo inmediato.

### Parche

El constructor debe recibir `binding` o exponer `initialize(binding)` y comprobar:

```python
required = binding.lib.polydim_pmtp_sizeof(num_slots, self.payload_bytes)
# reservar exactamente required y con alineación válida
rc = binding.lib.polydim_pmtp_init(self.ctrl_ptr, num_slots, self.payload_bytes)
if rc != 0:
    raise RuntimeError(...)
```

---

## F-007 — P0 — El canal Python no escribe tensor alguno

**Archivo:** `polydim_v768_monolito.py` 124–134.

```python
# Omitted payload write for brevity
binding.lib.polydim_pmtp_write_commit(...)
```

Se publica una versión como lista sin haber escrito payload.

### Parche

Añadir una API C `polydim_pmtp_payload_ptr(control, slot)` o calcular un layout ABI formal. Copiar/escribir el tensor **antes** del commit.

---

## F-008 — P0 — PMTP no verifica alineación de 64 bytes

**Archivo:** `kernel_cpp_v768.cpp` 819–875.

`PMTP_Control` es `alignas(64)`, pero `polydim_pmtp_init` acepta cualquier dirección.

UBSan reprodujo fallo con dirección +8 bytes.

### Parche C++

```cpp
if ((reinterpret_cast<uintptr_t>(c) & 63u) != 0)
    return POLYDIM_ERR_ALIASED_BUFFERS; // ideal: nuevo ERR_ALIGNMENT
```

Mejor: exportar `polydim_pmtp_alignof()` y exigir allocator alineado en todos los bindings.

---

## F-009 — P0 — `memset` sobre objetos `std::atomic`

**Archivo:** `kernel_cpp_v768.cpp` 871.

```cpp
std::memset(c, 0, polydim_pmtp_sizeof(...));
```

El compilador ya emite advertencia `-Wclass-memaccess` porque el objeto contiene atomics.

### Parche

Separar layout de memoria compartida de tipos C++ con constructores. Dos opciones:

1. campos enteros triviales + `std::atomic_ref` con requisitos lock-free verificados;
2. placement-new explícito de cada header/control, sólo si el modelo de memoria interproceso del target está contractualizado.

Añadir:

```cpp
static_assert(std::atomic<uint64_t>::is_always_lock_free);
static_assert(std::atomic<uint32_t>::is_always_lock_free);
```

si el diseño depende de ello.

---

## F-010 — P0 — Overflow en `polydim_pmtp_sizeof`

**Archivo:** `kernel_cpp_v768.cpp` 855–858.

No existen comprobaciones de overflow de suma/multiplicación.

Prueba reproducida:

`polydim_pmtp_sizeof(64, UINT64_MAX) == 4096`

### Parche

```cpp
uint64_t headers;
if (__builtin_mul_overflow(uint64_t(num_slots), uint64_t(sizeof(PMTP_SlotHeader)), &headers)) return 0;
uint64_t payloads;
if (__builtin_mul_overflow(uint64_t(num_slots), payload_bytes, &payloads)) return 0;
uint64_t total;
if (__builtin_add_overflow(uint64_t(sizeof(PMTP_Control)), headers, &total)) return 0;
if (__builtin_add_overflow(total, payloads, &total)) return 0;
return total;
```

En MSVC usar `_umul128`/comprobaciones por división o helpers portables.

---

## F-011 — P0 — Error de commit/abort puede dejar el ticket lock tomado para siempre

**Archivo:** `kernel_cpp_v768.cpp` 895–916.

```cpp
if (!c || slot >= c->num_slots) return;
```

Si `write_begin` tomó el lock y el caller pasa slot inválido al commit/abort, retorna sin `pmtp2_unlock`.

### Parche

No exponer commit como `void`. Devolver status y asociar un token de escritura no falsificable. Si el lock fue adquirido, toda salida debe liberarlo mediante RAII.

```cpp
struct WriterGuard {
    PMTP_Control* c;
    bool owns;
    ~WriterGuard(){ if (owns) pmtp2_unlock(c); }
};
```

Mejor aún: encapsular begin/write/commit en una operación más difícil de usar incorrectamente.

---

## F-012 — P1 — Writer crash = deadlock permanente

El ticket lock no es robusto. Si un proceso muere después de incrementar `wticket` y antes de incrementar `wlock`, los siguientes writers esperan eternamente.

### Parche

Para IPC industrial usar mecanismo robusto por plataforma o protocolo de lease/epoch/owner PID con recuperación. Un spinlock puro no es crash-safe.

---

## F-013 — P1 — “0% starvation” no está demostrado

Un seqlock favorece al escritor: un reader puede validar y fallar indefinidamente bajo escrituras continuas. El anillo reduce colisiones, pero no demuestra espera acotada.

### Parche

Si se exige progreso de readers, añadir pin/refcount por slot o RCU/epoch reclamation. Sólo reutilizar un slot cuando no haya readers que lo posean.

---

## F-014 — P1 — False sharing en control

`pub_seq`, `pub_slot`, `wlock`, `wticket` comparten la misma línea de 64 bytes.

### Parche

Separar publication state y writer ticket state en dos cachelines `alignas(64)` diferentes.

---

# PASS 3 — Numerical Torture

## F-015 — P0 — FTZ/DAZ “OFF” no se configura realmente

**Archivo:** `kernel_cpp_v768.cpp` 69–74.

Cuando `POLYDIM_ENABLE_FTZ == 0`, `set_fp_mode()` no hace nada.

Si el host entra con FTZ/DAZ activado, sigue activado, aunque `polydim_build_info()` anuncia:

`FTZ/DAZ=OFF (conforme IEEE-754)`.

### Parche C++

```cpp
inline void set_fp_mode() {
#if defined(POLYDIM_X86)
    unsigned csr = _mm_getcsr();
#if POLYDIM_ENABLE_FTZ
    csr |= 0x8000u | 0x0040u;
#else
    csr &= ~(0x8000u | 0x0040u);
#endif
    _mm_setcsr(csr);
#endif
}
```

Y `selftest_all()` debe llamar a `polydim_check_ftz()` cuando se exige IEEE estricto.

---

## F-016 — P0 — tolerancias NaN desactivan los invariantes

**Archivo:** `kernel_cpp_v768.cpp` 201, 253–255, 288.

Un caller puede pasar `PolydimTolerances` con NaN. Comparaciones como `e_yy > NaN` son false.

Prueba: y/u/v de norma 2 fueron aceptados con `rc=0` usando tolerancias NaN.

### Parche

Validar todas las tolerancias:

```cpp
if (!std::isfinite(tol.point_norm) || tol.point_norm < 0 ||
    !std::isfinite(tol.basis_ortho) || tol.basis_ortho < 0 ||
    !std::isfinite(tol.gram_ortho) || tol.gram_ortho < 0 ||
    !std::isfinite(tol.pivot_rel) || tol.pivot_rel < 0)
    return POLYDIM_ERR_INVALID_SCALAR;
```

---

## F-017 — P0 — No existe TwoSum en la actualización Rodrigues

**Archivo:** `kernel_cpp_v768.cpp` 257–269.

La especificación reclama “element-wise TwoSum compensation”, pero el código ejecuta:

```cpp
y_out[i] = y[i] + alpha * u[i] + beta * v[i];
```

No hay Knuth/Dekker/TwoSum.

Además el criterio por defecto acepta `64 eps ≈ 1.42e-14`, no `4.44e-16`.

### Parche

Implementar `two_sum` y opcionalmente FMA para productos:

```cpp
inline void two_sum(double a, double b, double& s, double& e) {
    s = a + b;
    double bb = s - a;
    e = (a - (s - bb)) + (b - bb);
}
```

Combinar `y + alpha*u + beta*v` con compensación y hacer renormalización correctiva si el contrato exige 2 ulp.

No prometer 2 ulp con tolerancia 64 eps.

---

## F-018 — P0 — overlap parcial corrompe `project_sphere`

**Archivo:** `kernel_cpp_v768.cpp` 305–338.

No se verifica overlap.

Prueba reproducida con y=[3,4] y `y_out = y+1`: devuelve SUCCESS y deja `[3,0.6,0.12]` en el buffer.

### Parche

Permitir sólo exact in-place o no-overlap:

```cpp
if (y_out != y && overlaps(y_out, y, bytes))
    return POLYDIM_ERR_ALIASED_BUFFERS;
```

---

## F-019 — P0 — overlap parcial también rompe Rodrigues

**Archivo:** `kernel_cpp_v768.cpp` 197–200, 264–269.

Se comprueba overlap con u y v, pero no overlap parcial con y.

`y_out==y` es seguro; `y_out=y+offset` no lo es.

Prueba reproducida: el kernel modifica y antes de leer elementos posteriores y acaba con salida corrupta.

### Parche

```cpp
if (y_out != y && overlaps(y_out, y, bytes))
    return POLYDIM_ERR_ALIASED_BUFFERS;
```

Además validar alias entre buffers marcados `__restrict__`.

---

## F-020 — P1 — El self-test fast-math es útil, pero no es una garantía del build

El build `-ffast-math` produjo correctamente `POLYDIM_ERR_COMPENSATION_BROKEN` en la prueba realizada.

Eso demuestra que el detector funciona para este patrón, **si se ejecuta**. No evita que una aplicación llame al kernel sin ejecutar `selftest_all`.

### Parche

Exportar un flag de build compilado y fallar en inicialización si macros incompatibles están activas. CI debe compilar un artefacto adversarial con fast-math y verificar rechazo.

---

## F-021 — P1 — Triton no implementa los invariantes del kernel CPU

**Archivo:** `polydim_triton_kernel_v768.py`.

Calcula `uu`, `vv`, `uv`, pero nunca los valida. No calcula `yy`. Tampoco revisa NaN/Inf.

### Parche

Incluir `yy`, flags de finite, validación de bases y norma, y retornar status device-side o lanzar después de una única sincronización final explícita.

---

# PASS 4 — FFI Abyss

## F-022 — P0 — Dart PMTP es una ABI completamente distinta

**Archivos:** `polydim_ffi.dart` 113–165; `kernel_cpp_v768.cpp` 855–943.

Dart busca:

- `polydim_pmtp_begin_write`
- `polydim_pmtp_commit_write`
- `polydim_pmtp_acquire_read`
- `polydim_pmtp_validate_read`

C++ exporta:

- `polydim_pmtp_write_begin`
- `polydim_pmtp_write_commit`
- `polydim_pmtp_read_begin`
- `polydim_pmtp_read_validate`

Las firmas también son distintas.

Dart define `PMTPControl` como 1 byte:

```dart
final class PMTPControl extends Struct {
  @Uint8()
  external int state;
}
```

C++ requiere 64 bytes alineados a 64, más headers y payload.

### Impacto

Con el binario C++ entregado, `Polydim._` ni siquiera puede resolver esos símbolos. Si existieran aliases externos con firmas incompatibles, el riesgo sería corrupción de stack/memoria.

### Parche Dart

No reflejar el control C++ como struct Dart. Tratarlo como `Pointer<Void>` a un bloque cuya longitud proviene de `polydim_pmtp_sizeof`.

Firmas actuales:

```dart
typedef SizeofNative = Uint64 Function(Uint32, Uint64);
typedef InitNative = Int32 Function(Pointer<Void>, Uint32, Uint64);
typedef BeginNative = Int32 Function(Pointer<Void>, Pointer<Uint32>, Pointer<Uint64>);
typedef CommitNative = Void Function(Pointer<Void>, Uint32, Uint64);
typedef ReadBeginNative = Int32 Function(Pointer<Void>, Pointer<Uint32>, Pointer<Uint64>);
typedef ReadValidateNative = Int32 Function(Pointer<Void>, Uint32, Uint64);
```

El allocator debe garantizar 64-byte alignment.

---

## F-023 — P0 — `test_pmtp.dart` certifica una API antigua, no V768

**Archivo:** `test_pmtp.dart` 8–39.

Usa `calloc<PMTPControl>()`, un solo argumento para init, slots uint64 y métodos que ya no existen.

Debe reescribirse por completo contra el ABI V768.

---

## F-024 — P1 — Python ctypes no expresa ni garantiza el requisito de 64 bytes

**Archivo:** `polydim_v768_monolito.py` 72–88, 419–421.

`ctypes.Structure` tiene alineación ABI normal, no `alignas(64)`.

Aunque el allocator observado durante esta auditoría devolvió direcciones múltiplo de 64, eso no es un contrato portable.

### Parche

Asignar `size + 63`, redondear manualmente la dirección y conservar el buffer base vivo. Mejor exportar un allocator/desallocator nativo PMTP.

---

## F-025 — P1 — Rust `catch_unwind` no convierte punteros inválidos en errores seguros

**Archivo:** `kernel_rust_v768.rs` 29–90 y 94–174.

`slice::from_raw_parts` exige que el puntero sea válido para d elementos. Un pointer dangling o longitud falsa constituye UB antes de que `catch_unwind` pueda ayudar.

### Parche

El ABI debe documentar explícitamente ownership, longitud y lifetime. Para procesos no confiables, no exponer raw pointers arbitrarios: usar handles/offsets validados dentro de una región registrada.

---

## F-026 — P1 — El “Betti-1 guard” no verifica Betti-1

**Archivo:** `kernel_rust_v768.rs` 144–168.

Cuenta `edges` y `components`, pero nunca calcula ni compara:

`beta1 = edges - vertices + components`

Sólo verifica conectividad (`components > 1`).

### Parche Rust

```rust
let beta1 = edges
    .checked_add(components)
    .and_then(|v| v.checked_sub(n))
    .ok_or(PolydimRustStatus::ErrNumericalInstability)?;

if beta1 < required_beta1 { ... }
```

La API debe recibir la propiedad topológica esperada. Si la intención es homología de un complejo de Vietoris–Rips y no sólo del grafo 1-skeleton, DSU es insuficiente.

---

## F-027 — P1 — Rust “2024” no incluye manifiesto y usa atributo antiguo

El archivo se anuncia como Rust 2024, pero no se entrega `Cargo.toml`. En Edition 2024, los atributos considerados unsafe deben adaptarse; `no_mangle` requiere la forma correspondiente al edition/lints usados.

Parche recomendado:

```rust
#[unsafe(no_mangle)]
pub unsafe extern "C" fn ...
```

Además envolver operaciones unsafe concretas en `unsafe {}` y activar `unsafe_op_in_unsafe_fn = "deny"` en CI.

---

# PASS 5 — SOTA Evolution

## F-028 — P0 — El compilador “Clifford+T” emite una puerta `ry(theta)` continua

**Archivo:** `polydim_clifford_t_compiler.py` 49–63.

```python
gates.append(f"ry({theta:.6f}) q[{q1}];")
```

Después añade una supuesta aproximación Clifford+T, por lo que no reemplaza la rotación: aplica ambas operaciones.

### Parche

Eliminar la rotación continua de la ruta Clifford+T. El sintetizador debe devolver exclusivamente H/S/T/CNOT (o el conjunto exacto elegido).

---

## F-029 — P0 — La aproximación Rz no tiene la cota `eps_target`

**Archivo:** `polydim_clifford_t_compiler.py` 22–47.

Para cualquier residual no pequeño emite siempre la secuencia fija `H,T,H,S`. `eps_target` no participa en el algoritmo.

No es Ross–Selinger ni ofrece una cota de error.

### Parche

Integrar un sintetizador real de aproximación Clifford+T y verificar numéricamente distancia de operadores antes de emitir el circuito.

---

## F-030 — P0 — El mapping `(p1,p2) % num_qubits` no implementa una rotación Givens entre amplitudes

**Archivo:** `polydim_clifford_t_compiler.py` 88–96.

Un índice de estado de un espacio 2^n no equivale a un índice de qubit. Dos niveles arbitrarios requieren una descomposición de two-level unitary con rutas Gray-code/controles adecuados.

### Parche

Compilar cada two-level unitary sobre estados computacionales |p1>, |p2>, no sobre `p1 % n` y `p2 % n`.

---

## F-031 — P1 — No existe state preparation del tensor latente

El circuito empieza con H en todos los qubits, preparando superposición uniforme. Eso no carga un vector arbitrario de R^D.

Por tanto no se ha implementado “aplicar SO(D) a un tensor latente arbitrario”.

Debe especificarse explícitamente el modelo de amplitude encoding y su coste de preparación.

---

## F-032 — P0 — El MIR-Wire “RDMA” entregado es TCP con copias

**Archivo:** `polydim_mir_wire_rdma.py` 33–98.

Usa `socket.AF_INET/SOCK_STREAM`, `bytearray`, `sendall` y `recv_into`. No hay verbs, MR registrada, queue pair, completion queue ni RDMA Write With Immediate.

El propio encabezado lo llama “emulator”, pero las afirmaciones de zero-copy/RDMA físico no pueden derivarse de este código.

### Parche

Separar formalmente dos backends:

- `TcpTensorTransport` para pruebas funcionales.
- `RdmaVerbsTransport` real con `ibv_reg_mr`, QP/CQ, rkey/address y WRITE_WITH_IMM.

Nunca reportar métricas TCP como métricas RDMA.

---

## F-033 — P0 — Payload truncado es aceptado como válido

**Archivo:** `polydim_mir_wire_rdma.py` 57–73.

Si `recv_into` devuelve 0 antes de completar, el bucle sale y aun así reconstruye el tensor, lo agrega y envía `ACK`.

Prueba ejecutada: se anunciaron 16 bytes, se enviaron 8; el receptor ACKeó y produjo `[1.25, 0.0]`.

### Parche

```python
if bytes_received != tensor_bytes:
    conn.close()
    continue
```

No insertar el tensor ni ACKear.

---

## F-034 — P0 — El header TCP también puede llegar fragmentado

**Archivo:** `polydim_mir_wire_rdma.py` 47–50.

`recv(header_size)` no garantiza devolver todo el header en TCP.

### Parche

Implementar `recv_exact(conn, n)` tanto para header como payload.

---

## F-035 — P0 — DoS de memoria remoto

**Archivo:** `polydim_mir_wire_rdma.py` 52–60.

`tensor_bytes` viene de red y se usa directamente en `bytearray(tensor_bytes)` sin límite.

### Parche

Definir `MAX_TENSOR_BYTES`, verificar divisibilidad por dtype, dimensión máxima y autorización antes de reservar.

---

## F-036 — P1 — `received_tensors` crece sin límite

**Archivo:** `polydim_mir_wire_rdma.py` 30, 71.

Es un memory leak lógico bajo tráfico sostenido.

### Parche

Usar ring buffer/deque con `maxlen`, callback de consumo o ownership explícito.

---

## F-037 — P1 — No hay integridad/autenticación de WAN

No checksum/AEAD, identidad de peer ni replay protection. Para WAN, un tag inmediato no es autenticación.

Añadir TLS/QUIC o autenticación criptográfica fuera del fast path de RDMA y CRC/hash cuando corresponda.

---

## F-038 — P0 teórico — El adapter no es biyectivo en R^D completo

**Archivo:** `universal_llm_tangent_adapter.py` 23–47.

La descomposición `(u, log ||h||)` es biyectiva sólo para `h != 0`.

El código mapea todo `||h|| < eps` al mismo floor `r=-100`, perdiendo magnitud y dirección.

Prueba:

- h=0 decodifica a ~`3.72e-44 * e1`, no cero.
- h=`1e-300 e1` produce la misma representación.

### Parche

Definir el dominio como `R^D \ {0}` o añadir estado explícito de cero:

```python
if norm == 0:
    return ZeroLatent()
```

No usar un floor si se reclama biyectividad.

---

## F-039 — P0 numérico — `np.linalg.norm` desborda con vectores finitos grandes

**Archivo:** `universal_llm_tangent_adapter.py` 27–39.

Con `[1e308,1e308,0]`, la prueba produjo `norm=inf`, `u=nan`, `r=inf`.

### Parche

Usar norma escalada BLAS/LAPACK (`dnrm2`) o algoritmo scale/ssq que evita overflow/underflow.

---

## F-040 — P1 — Antípodas: transporte paralelo no es único

**Archivo:** `universal_llm_tangent_adapter.py` 57–79.

Para `u2=-u1`, la geodésica mínima no es única. El código cae en `norm_w < eps` y devuelve el vector sin declarar la ambigüedad.

### Parche

Rechazar el caso antipodal o exigir un plano/geodésica seleccionada por el caller.

---

## F-041 — P0 conceptual — “serializar viola DPI” es matemáticamente incorrecto

La Data Processing Inequality establece que un procesamiento determinista no puede aumentar información mutua. No dice que toda serialización la destruya ni que serializar “viole” DPI.

Una codificación inyectiva puede conservar información aunque sea lenta y geométricamente inconveniente.

### Reformulación correcta

POLYDIM puede sostener que serializar a tokens puede:

- introducir cuantización/truncamiento,
- perder estructura geométrica si la codificación o el receptor no son isométricos,
- añadir latencia de encode/decode,
- aumentar tráfico lógico.

Pero no debe presentarse como violación de DPI.

---

## F-042 — P0 conceptual — No existe isometría global inyectiva 3072→1536

Una transformación lineal desde R^3072 a R^1536 tiene kernel no trivial. No puede preservar todas las distancias/normas ni ser biyectiva globalmente.

La única afirmación sostenible es una isometría **sobre un subespacio/manifold de dimensión intrínseca ≤1536** o una representación con pérdida controlada.

El propio texto del adapter menciona la condición `span(W)`, pero los benchmarks “DPI loss = 0.0” no entregan la evidencia necesaria para demostrar que los latentes reales cumplen esa condición.

---

# Inconsistencias documentales y reproducibilidad

## F-043 — P0 — Faltan headers y build system

El inventario declara `polydim.h / polydim_kernel.h`, pero no están en el ZIP. Tampoco hay CMake/Meson, Cargo.toml ni manifest de dependencias.

No hay build reproducible de la entrega tal como fue enviada.

---

## F-044 — P0 — Faltan todos los raw logs citados

`04_SILICON_CONTRACT_AND_BENCHMARKS.md` referencia `eval_logs/...`, pero no están incluidos.

Por tanto latencias, drift, “250.6×” y ejecuciones en TPU/Cerebras no pueden auditarse con este paquete.

Estado correcto: **UNVERIFIED FROM PROVIDED ARTIFACT**.

---

## F-045 — P1 — Contradicción del canario subnormal

El README V768 habla del verdadero mínimo subnormal FP64 `4.9406564584124654e-324`.

`04_SILICON_CONTRACT_AND_BENCHMARKS.md` sigue documentando `1.0005e-42` como canario “float”. Eso es subnormal en FP32, pero es un valor normal en FP64.

Debe fijarse el dtype explícitamente y unificar la documentación.

---

## F-046 — P1 — La prueba de canario no verifica igualdad bit-a-bit

**Archivo:** `polydim_v768_monolito.py` 528–538.

Sólo verifica `rc_sub == 0` y después consulta MXCSR. No compara `canary_out[0]` con el bit pattern de entrada.

### Parche

```python
assert canary_arr[0].view(np.uint64) == canary_out[0].view(np.uint64)
```

si el contrato realmente exige preservación bit-exacta.

---

## F-047 — P1 — Métrica de bandwidth GPU parece contar tráfico insuficiente

Para el Triton de dos pasadas:

- pass1: y,u,v = 3D reads
- pass2: y,u,v = 3D reads + y_out = 1D write

mínimo aproximado: `7 D × 8` bytes = 560 MB cuando D=10^7, sin contar parciales.

`70.51 GB/s × 4.538 ms ≈ 320 MB`, equivalente sólo a 4 vectores de 80 MB.

La métrica debe declarar exactamente qué bytes se contabilizan.

---

# Otros hallazgos importantes

## F-048 — P1 — `polydim_pmtp_init` no valida magic/tamaño en operaciones posteriores

Los entrypoints confían en `num_slots` y demás campos sin comprobar `magic`. Un control corrupto puede producir módulo cero o offsets fuera de región.

Añadir `validate_control(c)` a cada operación.

---

## F-049 — P1 — destructor POSIX puede unlinkear memoria que no creó

**Archivo:** `polydim_v768_monolito.py` 108–148.

Si `SharedMemory(create=True)` falla y luego se adjunta a un segmento existente, `__del__` igualmente llama `unlink()`. El proceso consumidor puede borrar el nombre del segmento ajeno.

Registrar `self.owner = True/False` y unlink sólo si es owner.

---

## F-050 — P1 — lifecycle del buffer exportado puede impedir `close()`

`self.ctrl`, `self.ctrl_ptr` y `_pin_refs` mantienen vistas/punteros al shared buffer. Deben liberarse antes de `shm.close()`.

No usar `__del__` como único mecanismo; implementar context manager `close()/unlink()` explícito.

---

## F-051 — P1 — Cholesky QR usa O(T K²) memory y O(DK²) time

**Archivo:** `kernel_cpp_v768.cpp` 1016–1113.

`thread_XTX = max_threads*K*K` puede superar cientos de MB con K=1024.

No es O(D²), pero tampoco es barato en el régimen K grande.

Añadir el mismo budget de arena usado en Stiefel y usar reducción por bloques.

---

## F-052 — P2 — posible falso negativo al final de CholQR2

La convergencia se comprueba al principio de iteraciones `step>0`. Si la última actualización (`step=2`) deja X dentro de tolerancia, el bucle termina sin una nueva comprobación y retorna `NUMERICAL_INSTABILITY`.

Añadir un Gram final después de la última actualización o reestructurar el loop como update→verify.

---

## F-053 — P1 — row normalization no produce matriz ortogonal ni rho=1

**Archivos:** ambos LSM.

Normalizar cada fila independientemente sólo fija su norma. No hace filas mutuamente ortogonales.

Prueba D=100:

- implementación separada: error máx. `W^T W-I ≈ 1.79`, radio espectral ≈1.05.
- monolito grado 16: error ≈0.88, radio espectral ≈1.08.

La afirmación “W_res in SO(D), spectral radius exactly 1” no corresponde al código.

---

## F-054 — P1 — el parámetro `stream` de Triton se ignora

**Archivo:** `polydim_triton_kernel_v768.py` 105–168.

Se recibe `stream` pero no se usa para lanzar kernels ni contexto CUDA.

---

## F-055 — P1 — la ruta Triton sigue sincronizando CPU/GPU

**Archivo:** `polydim_triton_kernel_v768.py` 146–151.

Usa `.item()` para alpha/beta y en fallback para yu/yv. El comentario “evita .item() sincrónico” no es cierto.

Solución: mantener alpha/beta en device memory y hacer que pass2 cargue esos dos escalares desde `alpha_beta_ptr`.

---

# Arquitectura de reparación recomendada

## Fase A — congelar afirmaciones no demostradas

Retirar temporalmente de README/benchmarks:

- “100% P0/P1 Closed”
- “DPI loss 0.0” global
- “zero starvation”
- “O(K²) Stiefel workspace”
- “real RDMA” para el backend TCP
- “Clifford+T exact/controlled”
- “SO(D) reservoir”

hasta que CI genere evidencia reproducible.

## Fase B — contrato ABI único

Crear `include/polydim.h` como única fuente de verdad y generar bindings Python/Dart/Rust desde ese contrato cuando sea posible.

Añadir funciones:

- `polydim_abi_version()`
- `polydim_sizeof_control()`
- `polydim_alignof_control()`
- `polydim_pmtp_payload_offset(slot)`
- `polydim_pmtp_validate_control()`

Nunca duplicar manualmente structs atómicos en Dart/Python.

## Fase C — PMTP v3

Control separado en cachelines:

- immutable metadata
- publication cacheline
- writer coordination cacheline
- slot headers cacheline-aligned
- payload offsets checked

Añadir owner epoch, crash recovery y reader pinning si se exige progreso acotado.

## Fase D — kernel matemático

- FTZ/DAZ explícito por thread.
- tolerancias validadas.
- overlap exacto.
- TwoSum real o eliminar la afirmación.
- test adversarial NaN/Inf/subnormal/huge/tiny.
- propiedades generativas con MPFR/long double como oracle para dimensiones pequeñas.

## Fase E — Stiefel matrix-free real

Eliminar `G_proj[D,K]`; recomputar filas.

Separar dos regímenes:

- K pequeño/moderado: SMW + BLAS/streaming.
- K grande: TSQR/blocked methods y distribución por D.

El contrato debe expresar coste `O(DK² + K³)` de tiempo y `O(K² T)` workspace, no “O(D)” sin mencionar K.

## Fase F — LSM estructurado

Usar operador ortogonal implícito verificable. Si el objetivo requiere grado fijo, no llamarlo SO(D) salvo que la construcción lo garantice.

## Fase G — Quantum

Separar:

1. descripción clásica de Givens/SO(D),
2. state encoding,
3. two-level unitary synthesis,
4. Clifford+T approximation con epsilon certificado,
5. verificación por distancia de operador para tamaños pequeños.

## Fase H — evidencia reproducible

Cada benchmark debe incluir:

- commit hash
- compiler/version/flags
- hardware exacto
- source hash
- stdout/stderr completos
- exit code
- raw JSON/CSV
- número de warmups/runs
- mediana/p95
- fórmula exacta de bandwidth
- seed

---

# Prioridad de cierre

## P0 antes de cualquier nueva feature

1. ABI Dart/C++.
2. PMTP init/payload/alignment/overflow/object lifetime.
3. Overlap parcial C++.
4. Stiefel `G_proj` D×K.
5. Triton D=10^7 + eliminación de `.item()`.
6. LSM O(D²) y falsa ortogonalidad.
7. MIR truncation/header/DoS y separación TCP/RDMA.
8. Quantum semantics.
9. Adapter zero/overflow.
10. Entrega reproducible con headers/logs/build files.

## P1 inmediatamente después

- crash-safe writer coordination,
- bounded reader progress,
- Rust topology semantics,
- FTZ CI multi-platform,
- CholQR memory/convergence,
- documentación matemática DPI/isometría.

---

# Resultado final de esta pasada

No encontré evidencia suficiente para sostener un “100% certified”. Sí encontré evidencia directa y reproducible de múltiples defectos P0/P1.

La arquitectura puede conservar como objetivo válido la comunicación tensorial nativa, geometría esférica y kernels streaming, pero antes de hablar de cierre industrial necesita unificar el contrato ABI, retirar materializaciones D×K ocultas, separar simulación de transporte real, y transformar las afirmaciones matemáticas en invariantes realmente chequeados por código y CI.

Esta auditoría no presupone que los benchmarks externos sean falsos; simplemente marca como **no verificables desde el artefacto entregado** aquellos cuyos raw logs y build provenance faltan.
