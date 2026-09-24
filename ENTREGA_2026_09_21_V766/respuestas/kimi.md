

# \***AUDITORÍA POLYDIM V764 — Dictamen de fondo**

\***Por qué siguen apareciendo errores después de 600 rondas (respuesta honesta): cada ronda audita los caminos que el log muestra ejecutados. El log dice `BLAS=OFF`, y el orquestador Python y el kernel Triton nunca se ejecutaron en el contrato de silicio. Tres de los cuatro lenguajes del "monolito" están desincronizados con el header. No es que el kernel C++ falle: es que la mitad del sistema enviado no compila/enlaza contra su propio contrato. Eso se cierra ejecutando todo lo enviado en CI, no más reseñas de texto.**

## \***P0 — BLOQUEANTES (el sistema enviado no funciona como está)**

### \***P0-1. El orquestador Python está muerto al nacer contra el ABI V762**

\***`polydim\\\_v762\\\_monolito.py` enlaza símbolos que no existen en `polydim.h`/el kernel:**

\***Table**

| **Python llama** | **V762 exporta** |
| :-: | :-: |
| `polydim\\\_apply\\\_rodrigues\\\_geodesic\\\_f64` | `polydim\\\_rodrigues\\\_geodesic\\\_f64` |
| `polydim\\\_stiefel\\\_cayley\\\_smw\\\_retraction\\\_f64` | `polydim\\\_stiefel\\\_cayley\\\_smw\\\_f64` |
| `compute\\\_gram\\\_and\\\_factorize` | no existe |
| `polydim\\\_rust\\\_betti1\\\_guard` | **eliminado en A8** (y el propio Rust lo declara eliminado) |


\***Y peor: `verify\\\_rust\\\_invariants` declara 3 argumentos `(ptr, d, &drift)` pero la función Rust V762 tiene 5 `(y, u, v, d, report)`. Con ctypes eso es llamada con aridad incorrecta → UB / crash leyendo registros basura como punteros. `AttributeError` en el binding de `betti1\\\_guard` ya impide construir `PolydimNativeCore`.**

\***Fix: regenerar los bindings desde el header (es mecánico): borrar `verify\\\_betti1`, `compute\\\_gram\\\_and\\\_factorize`, corregir los dos nombres, y firmar Rust como:**

\***Python**

```
\*\*\*\`class VerifyReport(ctypes.Structure):\`\*\*  
  
\`    \*\*\*\\\_fields\\\_ = \\\[("norm\\\_drift", ctypes.c\\\_double), ("basis\\\_uu\\\_err", ctypes.c\\\_double),\`\*\*  
  
\`                \*\*\*("basis\\\_vv\\\_err", ctypes.c\\\_double), ("basis\\\_uv\\\_err", ctypes.c\\\_double),\`\*\*  
  
\`                \*\*\*("bound\\\_used", ctypes.c\\\_double), ("subnormal\\\_count", ctypes.c\\\_uint64),\`\*\*  
  
\`                \*\*\*("nonfinite\\\_count", ctypes.c\\\_uint64)\\\]\`\*\*  
  
  
\*\*\*\`self.rust\\\_lib.polydim\\\_rust\\\_verify\\\_invariants.argtypes = \\\[\`\*\*  
  
\`    \*\*\*ctypes.c\\\_void\\\_p, ctypes.c\\\_void\\\_p, ctypes.c\\\_void\\\_p,\`\*\*  
  
\`    \*\*\*ctypes.c\\\_size\\\_t, ctypes.POINTER(VerifyReport)\\\]\`\*\*
```

\***Y añadir un test de humo en CI: `ctypes.CDLL(...)` + `getattr` de cada símbolo del header. Ese test de 10 líneas habría cazado los cuatro errores.**

### \***P0-2. El PMTP de Python ES el diseño V761 vulnerable que A1 dice haber cerrado**

\***`PMTPSlabChannel` usa 2 buffers con `packed = (seq \\\<\\\< 1) | (buf\\\_idx & 1)` y `read\\\_tensor` devuelve una vista zero-copy sin seqlock ni validación — exactamente el esquema que produjo 99.65% de lecturas desgarradas. El README afirma "triple buffer con seqlock por ranura… 0 desgarros" y el tribunal marca A1 CERRADO, pero eso sólo es cierto para el `PMTP\\\_Control` en C. La capa Python que el dossier presenta como parte de V762 sigue siendo la vía rota. Un lector Python puede copiar un tensor a mitad de escritura y no hay `validate\\\_read` que lo detecte.**

\***Fix (elegir una):**

- \***(a) Recomendada: portar el protocolo C a Python con `ctypes` llamando a `polydim\\\_pmtp\\\_\\\*` reales (el control vive en shared memory; los slots son vistas numpy). Así hay una sola implementación del protocolo.**

- \***(b) Si se reimplementa en Python puro: 3 slots, `slot\\\_seq` por ranura en un `ctypes.c\\\_uint64` en el header de 64 bytes, y la secuencia begin/commit/acquire/validate idéntica a la C. Sin eso, borrar `PMTPSlabChannel` del dossier — un canal conocidamente roto no puede enviarse como "hardened".**

### \***P0-3. El kernel Triton anula las compuertas A2/A3/A4 — el pecado original repetido**

- \***Pass 1 calcula `uu, vv, uv`… y el host sólo suma `yu, yv`. Los otros tres parciales se almacenan y se descartan. Eso es literalmente el hallazgo A2 ("acumuladores calculados y descartados") reintroducido en GPU.**

- \***`theta = NaN/Inf` entra a `sin()` sin `isfinite` → NaN propagado con `y\\\_out` devuelto (A3 sin cerrar en GPU).**

- \***No hay compuerta de punto (`||y||`), no hay Neumaier (reducción en árbol sin compensar), y el `stream` argumento nunca se usa. Las cifras "0.00e+00 de deriva" del contrato de silicio no aplican a esta vía y el dossier no lo dice.**

\***Fix mínimo honesto: en el host, tras pass 1, sumar los 5 parciales y aplicar las mismas tres compuertas (`isfinite(theta)`, `|uu−1|,|vv−1|,|uv| ≤ tol`, `|yy−1| ≤ tol`) devolviendo un código de estado; documentar que la deriva GPU es O(eps·log n) sin compensar y medirla en un test. Si no, etiquetar el kernel Triton como "no certificado — happy path" y sacarlo del titular "Silicon Certified".**

## \***P1 — AGUJEROS DE CORRECCIÓN (demostrados arriba)**

### \***P1-1. Aliasing parcial `y\\\_out` vs `y` no detectado (Rodrigues y project\_sphere)**

\***El kernel chequea `y\\\_out` contra `u` y `v`, y documenta "`y\\\_out==y` sí es legal" — pero no chequea `y\\\_out` contra `y` salvo igualdad exacta. Si `y\\\_out = y + 1` (solape desplazado), el bucle in-place escribe `y\\\[i+1\\\]` antes de leerlo en la iteración i+1. La simulación arriba muestra corrupción de magnitud 4.2 (no es teoría). Es un buffer overflow lógico con `rc=SUCCESS`.**

\***Fix (polydim\_rodrigues\_geodesic\_f64 y polydim\_project\_sphere\_f64):**

\***cpp**

```
\*\*\*\`if (y\\\_out != y && overlaps(y\\\_out, y, bytes))\`\*\*  
  
\`    \*\*\*return POLYDIM\\\_ERR\\\_ALIASED\\\_BUFFERS;\`\*\*
```

### \***P1-2. Stiefel: cero chequeo de aliasing, y aquí ni siquiera `Y\\\_out==X` es seguro**

\***A diferencia de Rodrigues, en el axpy loop `Y\\\_out==X` corrompe (demostrado arriba: se lee `xi\\\[p-K\\\]` ya sobrescrito). No hay ningún `overlaps()` en `polydim\\\_stiefel\\\_cayley\\\_smw\\\_f64` ni en `polydim\\\_project\\\_tangent\\\_stiefel\\\_f64`.**

\***Fix: en Stiefel rechazar todo solape, incluida la igualdad exacta (la igualdad exacta sí era legal en la esfera, no aquí — que el mensaje de error lo diga):**

\***cpp**

```
\*\*\*\`const size\\\_t bytesDK = static\\\_cast\\\<size\\\_t\\\>(D) \\\* K \\\* sizeof(double);\`\*\*  
  
\*\*\*\`if (Y\\\_out != X && overlaps(Y\\\_out, X, bytesDK)) return POLYDIM\\\_ERR\\\_ALIASED\\\_BUFFERS;\`\*\*  
  
\*\*\*\`if (Y\\\_out != G && overlaps(Y\\\_out, G, bytesDK)) return POLYDIM\\\_ERR\\\_ALIASED\\\_BUFFERS;\`\*\*  
  
\*\*\*\`if (overlaps(Y\\\_out, X, bytesDK) || overlaps(Y\\\_out, G, bytesDK))\`\*\*  
  
\`    \*\*\*return POLYDIM\\\_ERR\\\_ALIASED\\\_BUFFERS;   \*// igualdad exacta también: no es in-place-safe\`\*\*\*
```

\***(Quédese con la segunda forma: simple y correcta.)**

### \***P1-3. El error de ortogonalidad a posteriori en Stiefel se mide… y nunca se usa**

\***El comentario dice "ahora se mide, no se declara", pero tras calcular `err = max|YᵀY−I|` la función devuelve `SUCCESS` sin compararlo con nada. Un retraction numéricamente roto (pivote apenas sobre el umbral) sale certificado. Sé que el propio comentario admite que la medida interna sobreestima 4–7× — por eso la compuerta no puede ser `tol.gram\\\_ortho` a secas.**

\***Fix: añadir tolerancia a posteriori explícita y documentada:**

\***cpp**

```
\*\*\*\`/\\\* Cota a posteriori: la medida interna sobreestima 4-7x (sin compensar).\`\*\*\*  
  
\` \*\*\*\\\* Se fija en 8x gram\\\_ortho: conservadora, nunca acepta peor de lo que declara. \\\*/\`\*\*\*  
  
\*\*\*\`if (err \\\> 8.0 \\\* tol.gram\\\_ortho) return POLYDIM\\\_ERR\\\_NUMERICAL\\\_INSTABILITY;\`\*\*
```

\***Y un test negativo que fuerce el rechazo (G con norma tal que el sistema quede al borde).**

### \***P1-4. `std::bad\\\_alloc` cruza la frontera `extern "C"` → `std::terminate`**

\***El kernel captura `bad\\\_alloc` en `S`, `arena`, `W`… pero no en `M`, `Z`, `Mc`, `Zc`, `ipiv`, ni en los vectores de Rodrigues (`a\\\_yy…`, `a\\\_oo`). Un `extern "C"` que deja escapar una excepción es `terminate` — exactamente lo contrario de "memory-safe FFI" que V762 certifica. Bajo presión de memoria (que es cuando importa), el proceso muere en vez de devolver `-7`.**

\***Fix: `try/catch (const std::bad\\\_alloc&)` → `POLYDIM\\\_ERR\\\_BUFFER\\\_OVERFLOW` en toda función exportada, o un wrapper `noexcept` único. Y un test con `POLYDIM\\\_GRAM\\\_ARENA\\\_BUDGET\\\_BYTES` forzado a 1 byte que verifique `-7` y no el crash.**

## \***P2 — SEMÁNTICA DE CONCURRENCIA (PMTP C: correcto en detección, con dos asteriscos)**

### \***P2-1. Pérdida silenciosa de secuencia en `acquire\\\_read`**

\***`acquire\\\_read` escribe `\\\*observed\\\_seq = gs` antes de que el lector copie y valide. Si `validate\\\_read` devuelve `SEQLOCK\\\_RACE`, esa secuencia `gs` ya está marcada como vista: el lector la salta para siempre y conserva datos más viejos sin saberlo. Para telemetría es tolerable; para "agents communicate state" es un lost update.**

\***Fix: no comitear `observed\\\_seq` hasta que la validación pase:**

\***c**

```
\*\*\*\`/\\\* acquire\\\_read: NO escribir \\\*observed\\\_seq. Devolver gs en ticket\\\_out... \\\*/\`\*\*\*  
  
\*\*\*\`/\\\* tras validate\\\_read == SUCCESS, el llamador hace: \\\*observed\\\_seq = gs; \\\*/\`\*\*\*
```

\***(API: devolver `gs` por un out-param adicional; en la raza, `observed\\\_seq` intacto → reintenta la misma `gs`.) Si se prefiere la semántica actual, documéntela en el header: "una lectura rasgada descarta esa secuencia; el lector avanza a la siguiente".**

### \***P2-2. `begin\\\_write` asume un único escritor sin decirlo**

\***`write\\\_cursor` se toca con load/store relaxed — dos escritores se pisan. Es SPMC (un productor), bien, pero ni el header ni el código lo hacen valer. Un `assert`/documentación "single-writer by contract" o un CAS. Barato: documentarlo.**

### \***P2-3. Los tests de A1 no prueban lo que el dossier celebra**

- \***Un solo lector (SPMC con M readers nunca se ejercita).**

- \***`check(true, "…ruta de retorno")` es una aserción vacía — pasa aunque `races==0`.**

- \***El log real: 1.098 lecturas válidas vs 82.548 carreras detectadas y 7,8M de "sin novedad". El lector progresa, sí, pero 98,7% de los intentos son rechazados: "0 desgarros no detectados" es casi tautológico cuando casi nada se acepta. La métrica correcta a fijar como umbral es: `undetected==0` y `ok/(ok+races) \\\> 1%` (o lo que midan), con ≥4 lectores.**

- \***El README y el tribunal citan "218.417 lecturas validadas"; el log de silicio enviado dice 1.098. Ese número no es reproducible desde la telemetría entregada. O es de otra corrida (entonces: entregar esa corrida) o está mal. En un dossier cuyo tema central es "medir, no declarar", un número sin log es exactamente el vicio que se corrige.**

## \***P3 — INTEGRIDAD DOCUMENTAL (lo que un revisor hostile cita contra ustedes)**

1. \***"218,417" ≠ 1,098 (ver P2-3).**

2. \***Tribunal: "max|YᵀY−I| = 3.2e-15 medido" — no aparece en ningún log enviado (los logs dan 6.66e-16…2.44e-15).**

3. \***Tribunal: "el C++ nativo es 2.0× más rápido que OpenBLAS" — eso es una fila de cinco. En (4096,64) y (16384,128) OpenBLAS gana (5.71 vs 9.90; 124.24 vs 152.30). La tabla lo muestra; la prosa lo oculta. Escriban "2.0× en (4096,16); OpenBLAS gana en las dos configuraciones de K grande" — ganan credibilidad y el argumento P1 (loop-swap) se sostiene igual.**

4. \***README 2.2.1: "The 5 inner products" y lista seis.**

5. \***Comentario Dart: "mediana ~3.4 ms" — 3.41 es el mínimo; la mediana del log es 4.27.**

6. \***El contrato de silicio certifica con `BLAS=OFF`. La ruta `POLYDIM\\\_USE\\\_BLAS` (dsyrk/dgesv con sus transposiciones) nunca se ejecutó en lo entregado. Yo la verifiqué analíticamente y las transposiciones son correctas — pero "correcta sobre el papel" es lo que V761 ya decía. Certifiquen las dos rutas en CI y un cross-check BLAS=ON vs OFF (mismo input, diff \< 1e-12).**

## \***Lo que está BIEN (para que no lo toquen)**

- \***La refutación de la "falacia de tangencia" es correcta — verificado: 4.4e-16 con G arbitrario no tangente. Cayley no necesita G tangente.**

- \***Neumaier + árbol de reducción + `num\\\_threads` explícito + selftest de compensación: sólido.**

- \***La decisión A5 (cota fija 64ε, sin escalar en D, sin piso 1e-12) es la correcta y está bien argumentada en el código.**

- \***El guardián Rust es de lo mejor del dossier: reporte siempre inicializado, `-13` distinto de `-5`, subnormales como telemetría, tests que de verdad prueban el umbral. Único matiz: la cota se aplica a ⟨y,y⟩, así que la tolerancia efectiva sobre ‖y‖ es ~32ε — documenlo en el header de Rust y listo.**

## \***Contrato de cierre (para que la ronda 601 sea la última)**

\***Cada hallazgo arriba se cierra con un test que falla antes del fix y pasa después:**

\***Table**

| **\#** | **Test que lo prueba** |
| :-: | :-: |
| P0-1 | `test\\\_python\\\_abi\\\_smoke`: getattr de todo símbolo del header vía ctypes + llamada Rust 5-arg |
| P0-2 | Stress Python PMTP ≥4 lectores, mismo criterio que `test\\\_a1\\\_pmtp` (undetected==0) |
| P0-3 | Triton: `theta=NaN` → error; base rota → error; deriva medida reportada |
| P1-1 | `y\\\_out = y+1` → `-11` (mi simulación es el test) |
| P1-2 | `Y\\\_out==X` → `-11` en Stiefel |
| P1-3 | Caso Stiefel forzado al borde → `-5` por compuerta a posteriori |
| P1-4 | Budget de arena = 1 byte → `-7`, proceso vivo |
| P2-1 | Inyectar escritor entre acquire y validate → el lector **relee** la misma seq |
| P2-3 | ≥4 lectores, asserts no vacíos, ratios fijados; reconciliar "218.417" |
| P3-6 | Suite C++ corrida dos veces: BLAS=ON y BLAS=OFF, exit 0 ambas |


\***Si quieren, en la siguiente respuesta les entrego los tres archivos corregidos completos (`polydim\\\_kernel.cpp` con los parches P1, `polydim\\\_v762\\\_monolito.py` reescrito contra el ABI real, y `PMTPSlabChannel` portado al protocolo triple-búfer) como monolito listo para compilar — pero la lista de arriba es el trabajo pendiente: 3 bloqueantes, 4 de corrección, 3 de concurrencia, 6 documentales. Nada de esto requiere rehacer la matemática; requiere ejecutar todo lo que se envía.**

**InstantHigh**



