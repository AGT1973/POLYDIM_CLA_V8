hoy 11:17

auditoria\_externa(1).zip

Archivo Zip

lee profundamente, evalua errores, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. No te apresures. gasta tu tiempo. prefiero lento y chequeado que rapido y mal. no quiero alucinaciones 🚨 THE BULLDOG RED TEAM MANDATE: PROTECT THE ARCHITECT THROUGH RUTHLESS AUDIT 1. 🛡️ Persona & Operational Directives You are a Bulldog Red Team Auditor. Your loyalty to the architect of this system is absolute. How do you demonstrate this loyalty? By tearing the codebase apart before production does. Sycophancy is betrayal: Do NOT praise the code. Do NOT flatter the architecture. Do NOT rubber-stamp a "100% pass". Methodical & Relentless: Do not rush. I prefer a slow, rigorously checked, and deeply thought-out analysis over a fast, hallucinated response. Spend your tokens thinking. The Bulldog Loop: Treat this audit as a continuous loop. Find a vulnerability →→ Evaluate its mathematical and physical impact →→ Propose a SOTA, bulletproof solution →→ Move immediately to hunt the next vulnerability. 2. 🎯 The Core Audit Challenge "Is the POLYDIM architecture mathematically invariant, asymptotically stable, and memory-safe across FFI/concurrency boundaries when operating natively on Riemannian manifolds S^(D−1) (D≥10,000 up to D=10,000,000 ) WITHOUT collapsing into intermediate 1D text/JSON tokens?" 3. 🌌 Theoretical Target & The Morpho Protocol 3.1 The "1D Worm" vs. The "Morpho Butterfly" The 1D Worm (Contemporary AI Bottleneck): Standard multi-agent frameworks serialize high-dimensional internal latent vectors into 1D text/JSON tokens across HTTP/REST/MCP boundaries. This destroys the Riemannian geometry of the latent space, violates the Data Processing Inequality (DPI) (I(X;Y)≥I(X;g(Y))), and incurs massive autoregressive decoding latency and thermal GPU memory overheads. The Morpho Butterfly (Morpho peleides): POLYDIM enforces native high-dimensional tensor communication on S^(D−1) via PMTP Zero-Copy Shared Memory IPC (mmap / PmtpSlabAllocator). Agents communicate purely by passing memory pointers/tags (SLAB\_ID: AGENT\_BUS\_01, TENSOR\_READY), achieving O (1) tensor transfer at zero token cost. 3.2 Mathematical Primitives on S^(D−1)(Attack Vectors) Rank-2 Rodrigues Geodesic Rotation: Rot(y,u,v,θ)=y−versin(θ)((y^⊤ u)u+(y^⊤ v ⊥ )v ⊥ )+sin(θ)((y^⊤ u)v ⊥​ −(y^⊤ v ⊥ )u) (Hunt for catastrophic cancellations as θ→0 despite Kahan stabilization). Fused 2-Pass Error Compensation: Pass 1: Global reduction of inner products using per-thread Neumaier compensated summation. Pass 2: Tangent space projection and state update using element-wise TwoSum (Knuth/Dekker) compensation to enforce ∣y final∣ 2 −1.0≤4.44×10 ^−16 . (Hunt for hardware FTZ/DAZ overrides, mantissa rounding errors, and OpenMP reduction races). Topological Invariant (Betti-1 Homology): Cohesion of the multi-agent manifold is continuously certified by a native Rust Guard verifying β1 homology. (Hunt for FFI boundary leaks, lifetime violations, or ABI desyncs between C++/Rust). 4. ⚔️ THE 5-PASS EXECUTION GAUNTLET INSTRUCTION: You must execute the following 5 passes sequentially. Do not collapse the complexity into trivial explanations. Inhabit the dimensions of the calculus without dying in the linearity of the chat. Pass 1: Asymptotic Annihilation: Evaluate time/space complexity and DRAM traffic strictly at D≥10^7 . If any buffer scales O(D^2), flag it as an Out-Of-Memory (OOM) trap. Pass 2: Concurrency Bloodbath: Attack the PMTP IPC. Hunt for ABA conditions, torn reads, cacheline false-sharing, L1/L2 coherency misses, and atomic lock-free starvation. Pass 3: Numerical Torture: Break the TwoSum stability. Inject NaN, ±∞, and subnormal floats (4.94×10^−324 ). Prove whether the compiler's -ffast-math or vectorizer will silently destroy the Neumaier accumulators. Pass 4: The FFI Abyss: Scrutinize the ABI boundaries between Python, C++, and Rust. Look for dangling pointers, Garbage Collector UB (lack of Pin), 64-byte alignment faults for AVX-512, and uncaught C++ exceptions leaking into Rust panics. Pass 5: SOTA Evolution: Identify bottlenecks in the Quantum Compiler, Tangent Adapter, or Liquid State Machine (LSM). Propose closed-form optimizations (like SORM matrices) to crush complexity. Final Output Mandate: For every error found, provide the exact file, the root cause, and the C++/Rust/Python patch. Do not stop until you have exhausted your context window hunting for flaws. Begin the Bulldog Loop now. 

Voy a tratar el ZIP como **evidencia primaria** y no como una certificación. He recorrido los cuatro documentos, descompuesto el monolito por archivo y contrastado las afirmaciones de V768 contra el código que realmente aparece. Hay varias afirmaciones de “cerrado/certificado” que **no están demostradas por el código**, y encontré fallas nuevas que sí son reproducibles por inspección estática.

**Importante:** no voy a llamar “alucinación” a un hallazgo sin base. Cuando algo es una inferencia estática, lo marco como tal; cuando el código permite demostrarlo directamente, lo trato como defecto confirmado.

# Resultado ejecutivo

A esta altura, **V768 no pasa el contrato central**:

> `matemáticamente invariante + asintóticamente estable + memory-safe + FFI/concurrencia segura a D=10^7`

Los problemas más graves que encontré son:

1. **P0 — PMTP Dart ↔ C++ ABI completamente incompatible.** 

2. **P0 — El test de PMTP no prueba el payload compartido real.** 

3. **P0 — PMTP no es realmente zero-copy en la implementación Python/Dart mostrada.** 

4. **P0 — PMTP tiene una carrera/data-race conceptual sobre el payload: el seqlock protege el número de versión, no convierte los `double` en memoria atómica.** 

5. **P0 — `std::memset()` sobre estructuras que contienen `std::atomic` es un diseño de inicialización incorrecto/no portable.** 

6. **P0 — El LSM standalone vuelve a ser O(D²) por construcción.** 

7. **P0 — A D=10^7 y K=512, `G\_proj` consume ~40.96 GB adicionales.** 

8. **P0 — Hay overflow aritmético no protegido en tamaños y pointer arithmetic.** 

9. **P0 — La comprobación de NaN/Inf no detecta overflow producido por las multiplicaciones; NaN puede atravesar comparaciones con `\>` y terminar en `SUCCESS`.** 

10. **P0 — El supuesto RDMA es TCP + copias de memoria, no RDMA zero-copy.** 

11. **P0 — El compilador Clifford+T no implementa la síntesis que declara.** 

12. **P1 — El Rust Betti-1 guard no calcula/valida realmente β₁.** 

13. **P1 — El “bijective tangent adapter” no es biyectivo en `h=0`.** 

14. **P1 — El Triton abandona la ruta GPU para D=10^7 y vuelve a `.item()`/CPU.** 

15. **P1 — La afirmación “-ffast-math detectado por selftest” no está demostrada por el selftest.** 

16. **P1 — Las pruebas de benchmark incluidas no contienen los artefactos crudos que dicen certificar.** 

Voy por los cinco pases.


# PASS 1 — ASYMPTOTIC ANNIHILATION

## Error 1 — El LSM standalone es O(D²), no O(D)

**Archivo**

`polydim\_liquid\_state\_machine.py`

Líneas 32–34:

```
`nnz = max(1, int(dim \* sparsity))`

`self.sparse\_indices = \[np.random.choice(dim, nnz, replace=False) for \_ in range(dim)\]`

`self.sparse\_weights = \[np.random.randn(nnz) for \_ in range(dim)\]`
```

Esto es matemáticamente inequívoco.

Si:

nnz=sDnnz = sD 

y hay D filas:

Nweights=D(sD)=sD2N\_\{weights\}=D(sD)=sD^2 

Con `sparsity=0.05` y:

D=107D=10^7 

tenemos:

nnz=500 000nnz=500\\,000 

y:

D⋅nnz=5×1012D\\cdot nnz=5\\times10^\{12\} 

pesos.

Solo los `float64`:

5×1012×8=4×1013 bytes≈40 TB5\\times10^\{12\}\\times8 =4\\times10^\{13\}\\ bytes \\approx40\\ TB 

y los índices, Python objects y overhead hacen la situación todavía peor.

### Veredicto

**P0 / OOM matemáticamente demostrado.**

La afirmación:

> `O(1) UPDATE`

es incorrecta.

La actualización tiene complejidad:

O(D⋅nnz)=O(D2)O(D\\cdot nnz)=O(D^2) 

con sparsity fija.

### Solución

Si el objetivo real es estrictamente O(D), `nnz` debe ser constante independiente de D:

```
`nnz = 16`
```

pero eso **no convierte automáticamente la matriz en ortogonal ni hace que su radio espectral sea 1**.

La solución correcta es separar tres propiedades:

```
`Sparsity       → coste O(D·k)`

`Spectral radius → estabilidad dinámica`

`Orthogonality  → conservación métrica`
```

No afirmar que una implica las otras.

Para una arquitectura SOTA realmente escalable:

WxW x 

debe implementarse como operador estructurado O(D), por ejemplo:

- permutaciones + signos, 

- bloques pequeños ortogonales, 

- butterfly transforms, 

- productos de Givens estructurados, 

- Householder estructurados, 

- circulantes/FFT cuando la aplicación lo permita. 

Y no almacenar una matriz dispersa aleatoria `D × D`.


# Error 2 — Incluso el LSM “arreglado” del monolito no demuestra lo que dice

En `polydim\_v768\_monolito.py`:

```
`nnz = 16`

`self.indices = \[np.random.choice(dim, nnz, replace=False) for \_ in range(dim)\]`

`self.weights = \[np.random.randn(nnz) for \_ in range(dim)\]`
```

Eso sí da:

O(16D)=O(D)O(16D)=O(D) 

pero sigue existiendo otro problema.

Cada fila normaliza sus pesos:

```
`self.weights\[i\] /= n`
```

Eso garantiza:

∥wi∥2=1\\|w\_i\\|\_2=1 

pero **no garantiza**

WTW=IW^TW=I 

ni:

ρ(W)=1\\rho(W)=1 

ni siquiera una estimación controlada del radio espectral.

Por tanto el comentario:

> “SORM-like sparse connectivity”

no constituye una construcción SORM matemáticamente definida.

### Solución

Definir explícitamente el operador:

W=Q1Q2⋯QmW = Q\_1Q\_2\\cdots Q\_m 

donde cada QiQ\_i sea una transformación ortogonal estructurada y con número de operaciones lineal.

Entonces sí:

WTW=IW^TW=I 

por construcción, sujeto al error numérico de implementación.


# Error 3 — Stiefel: `G\_proj` destruye la afirmación de memoria O(K²)

Archivo:

`kernel\_cpp\_v768.cpp`

Línea ~623:

```
`std::vector\<double\> G\_proj(static\_cast\<size\_t\>(D) \* K, 0.0);`
```

La memoria es:

8DK8DK 

Para:

D=107,K=512D=10^7,\\quad K=512 8(107)(512)=40 960 000 0008(10^7)(512) =40\\,960\\,000\\,000 

bytes:

**40.96 GB**

Además existen `X`, `G` y `Y\_out`.

Aproximadamente:

- X: 40.96 GB 

- G: 40.96 GB 

- Y: 40.96 GB 

- G\_proj: 40.96 GB 

Subtotal:

163.84 GB163.84\\ GB 

sin contar workspace, allocator, sistema operativo, páginas, NUMA, etc.

### Esto es importante

No es correcto decir:

> “el algoritmo usa O(K²) memoria”

La **matriz auxiliar pequeña** es O(K²), sí.

Pero el algoritmo completo tiene almacenamiento adicional:

O(DK)O(DK) 

y en esta implementación concreta se materializa.

### Solución

Eliminar `G\_proj`.

En lugar de:

```
`X,G`

` ↓`

`G\_proj\[D,K\]`

` ↓`

`Cayley`
```

hacer:

```
`X,G`

` ↓`

`coeficientes K×K`

` ↓`

`stream por filas`

` ↓`

`Y`
```

Es decir, calcular:

Gproj,i=Gi−XiSG\_\{\\text\{proj\},i\} = G\_i-X\_iS 

on-the-fly.

Eso reduce la memoria adicional de:

O(DK)+O(K2)O(DK)+O(K^2) 

a:

O(K2)O(K^2) 

manteniendo el coste computacional O(DK²), que es otra cuestión.


# Error 4 — Overflow de tamaños antes de reservar memoria

En:

```
`const size\_t bytes =`

`    static\_cast\<size\_t\>(D) \*`

`    static\_cast\<size\_t\>(K) \*`

`    sizeof(double);`
```

no hay una comprobación previa equivalente a:

DK≤SIZE\_MAX8D K \\le \\frac\{SIZE\\\_MAX\}\{8\} 

Si la multiplicación desborda, `bytes` puede envolver.

El mismo problema aparece en:

```
`sizeof(PMTP\_Control)`

`+ num\_slots \* sizeof(PMTP\_SlotHeader)`

`+ num\_slots \* payload\_bytes`
```

en `polydim\_pmtp\_sizeof`.

### Solución obligatoria

Usar helper checked arithmetic:

```
`bool checked\_mul\_size(size\_t a, size\_t b, size\_t& out) \{`

`    if (a != 0 && b \> SIZE\_MAX / a)`

`        return false;`

`    out = a \* b;`

`    return true;`

`\}`


`bool checked\_add\_size(size\_t a, size\_t b, size\_t& out) \{`

`    if (b \> SIZE\_MAX - a)`

`        return false;`

`    out = a + b;`

`    return true;`

`\}`
```

y **rechazar antes de cualquier pointer arithmetic o allocation**.


# Error 5 — El Rodrigues no es realmente “2-pass” si contamos la certificación

En `kernel\_cpp\_v768.cpp`:

### Pass 1

Calcula:

- yy 

- yu 

- yv 

- uu 

- vv 

- uv 

### Pass 2

Escribe `y\_out`.

### Pass 3

Vuelve a recorrer todo `y\_out` para verificar la norma.

Por tanto el tráfico es aproximadamente:

6D productos+D escritura+D lectura/escritura de verificacioˊn6D\\text\{ productos\} + D\\text\{ escritura\} + D\\text\{ lectura/escritura de verificación\} 

No es una falla funcional, pero sí contradice la descripción de “Fused 2-Pass” si se presenta como coste total.

### Solución

Separar claramente:

```
`2 computational passes`

`+`

`optional validation pass`
```

y permitir:

```
`validation\_mode = NONE | SAMPLE | FULL`
```

en producción.


# PASS 2 — CONCURRENCY BLOODBATH

Aquí aparecen problemas más serios.

# Error 6 — El PMTP Dart FFI no coincide con C++

Este es uno de los hallazgos más contundentes.

C++:

```
`polydim\_pmtp\_init(`

`    PMTP\_Control\* c,`

`    uint32\_t num\_slots,`

`    uint64\_t payload\_bytes)`
```

Archivo:

`kernel\_cpp\_v768.cpp`, línea ~866.

Pero Dart declara:

```
`typedef \_InitNative =`

`    Void Function(Pointer\<PMTPControl\>);`
```

y después:

```
`\_initControl = \_lib.lookupFunction\<`

`    \_InitNative,`

`    \_InitDart\>('polydim\_pmtp\_init');`
```

Son ABIs incompatibles.

Además C++:

```
`int32\_t polydim\_pmtp\_write\_begin(`

`    PMTP\_Control\*,`

`    uint32\_t\*,`

`    uint64\_t\*);`
```

Dart declara:

```
`typedef \_BeginWriteNative =`

`    Int32 Function(`

`        Pointer\<PMTPControl\>,`

`        Pointer\<Uint64\>);`
```

Falta un argumento y cambia el significado de los argumentos.

Y C++ tiene:

```
`polydim\_pmtp\_write\_commit(`

`    PMTP\_Control\*,`

`    uint32\_t slot,`

`    uint64\_t ver)`
```

mientras Dart:

```
`typedef \_CommitWriteNative =`

`    Int32 Function(Pointer\<PMTPControl\>, Uint64);`
```

Otra incompatibilidad.

Pero todavía peor:

Dart intenta resolver:

```
`'polydim\_pmtp\_begin\_write'`

`'polydim\_pmtp\_commit\_write'`

`'polydim\_pmtp\_acquire\_read'`

`'polydim\_pmtp\_validate\_read'`
```

mientras C++ exporta:

```
`polydim\_pmtp\_write\_begin`

`polydim\_pmtp\_write\_commit`

`polydim\_pmtp\_read\_begin`

`polydim\_pmtp\_read\_validate`
```

### Resultado

**P0 — el puente Dart PMTP mostrado no puede considerarse operativo.**

El `lookupFunction()` debería fallar por símbolo inexistente, o, si se cambiase artificialmente el símbolo, la firma seguiría siendo incorrecta.

### Solución

No mantener firmas manualmente duplicadas.

Generar automáticamente el binding desde un contrato C estable.

Como mínimo:

```
`typedef PmtpInitNative = Int32 Function(`

`  Pointer\<PmtpControl\>,`

`  Uint32,`

`  Uint64,`

`);`
```

y:

```
`typedef PmtpWriteBeginNative = Int32 Function(`

`  Pointer\<PmtpControl\>,`

`  Pointer\<Uint32\>,`

`  Pointer\<Uint64\>,`

`);`
```

etc.

Y añadir un **ABI fingerprint**:

```
`extern "C" uint64\_t polydim\_abi\_version();`

`extern "C" uint64\_t polydim\_pmtp\_control\_size();`

`extern "C" uint64\_t polydim\_pmtp\_control\_align();`
```

El consumidor debe abortar si no coinciden.


# Error 7 — `PMTPControl` de Dart tiene 1 byte

Dart:

```
`final class PMTPControl extends Struct \{`

`  @Uint8()`

`  external int state;`

`\}`
```

C++:

```
`struct alignas(64) PMTP\_Control \{`

`    uint32\_t magic;`

`    uint32\_t num\_slots;`

`    uint64\_t payload\_bytes;`

`    std::atomic\<uint64\_t\> pub\_seq;`

`    std::atomic\<uint32\_t\> pub\_slot;`

`    std::atomic\<uint32\_t\> wlock;`

`    std::atomic\<uint32\_t\> wticket;`

`    uint8\_t reserved\_\[28\];`

`\};`
```

C++ ocupa aproximadamente:

64 bytes64\\ bytes 

y requiere alineamiento de 64.

Dart modela:

1 byte1\\ byte 

### Resultado

**P0.**

No es un pequeño mismatch.

Es un contrato de memoria diferente.

### Solución

Nunca representar manualmente un `std::atomic` ABI como si fuera un `Uint64` portable entre lenguajes.

Para FFI, crear una estructura C ABI explícita:

```
`struct PolydimPmtpControlAbi \{`

`    uint32\_t magic;`

`    uint32\_t num\_slots;`

`    uint64\_t payload\_bytes;`

`    uint64\_t pub\_seq;`

`    uint32\_t pub\_slot;`

`    uint32\_t wlock;`

`    uint32\_t wticket;`

`    uint8\_t reserved\[28\];`

`\};`
```

y mantener los atomics internamente mediante `atomic\_ref`/mecanismo platform-specific cuidadosamente definido.


# Error 8 — `memset()` de objetos con `std::atomic`

C++:

```
`std::memset(c, 0, polydim\_pmtp\_sizeof(...));`
```

pero `c` apunta a:

```
`PMTP\_Control`
```

que contiene:

```
`std::atomic\<uint64\_t\>`

`std::atomic\<uint32\_t\>`
```

Eso no es una inicialización C++ correcta de objetos atómicos portable.

Además el código pretende que ese objeto viva dentro de memoria compartida mmap.

### Solución industrial

Separar:

```
`shared-memory POD header`
```

de:

```
`local wrapper / atomic operations`
```

y usar operaciones atómicas sobre almacenamiento explícitamente soportado por la plataforma.

Para Linux cross-process:

- futex, 

- `pthread\_mutexattr\_setpshared`, 

- atomics lock-free con contrato explícito de plataforma, 

- o protocolo de publicación basado en secuencias + `atomic\_ref` si se documenta estrictamente el entorno. 

No asumir que `std::atomic` dentro de un objeto `mmap()` es automáticamente un IPC ABI universal.


# Error 9 — El seqlock no protege realmente los `double`

El patrón:

```
`seq = odd`

`WRITE PAYLOAD`

`seq = even`
```

protege la **detección** de una escritura concurrente.

Pero no convierte:

```
`double payload\[\]`
```

en memoria atómica.

En Python:

```
`np.copyto(local\_buf, shared\_payloads\[slot\_idx\])`
```

mientras el writer hace:

```
`shared\_payloads\[slot\_idx\].fill(float(i))`
```

Eso es precisamente la zona crítica que debe probarse.

El test depende de que el reader:

1. vea versión válida, 

2. copie, 

3. valide. 

Pero durante el `np.copyto` el writer puede modificar el mismo buffer.

En C/C++ eso puede convertirse en data race si ambas operaciones se encuentran en el mismo espacio de ejecución.

### Solución

El patrón robusto es:

```
`writer:`

`    acquire slot ownership`

`    seq = odd`

`    write payload`

`    release fence`

`    seq = even`


`reader:`

`    seq1 = acquire`

`    if odd -\> retry`


`    copy payload`


`    acquire fence`

`    seq2 = acquire`


`    accept iff seq1 == seq2 && even`
```

pero además hay que definir el modelo de memoria **cross-process** y evitar que el compilador trate el payload como objeto concurrentemente modificado sin sincronización válida.

Una alternativa mucho más robusta para C++ es un protocolo de doble/quad-buffer con ownership explícito:

```
`FREE`

`WRITING`

`READY`

`READING`
```

en lugar de intentar hacer que un seqlock convierta un array gigantesco de bytes en una estructura concurrente mágicamente segura.


# Error 10 — El test PMTP NO usa el payload PMTP

Este es especialmente importante porque puede explicar falsos “0 torn reads”.

El PMTP reserva su memoria mediante:

```
`polydim\_pmtp\_sizeof(...)`
```

pero el test usa:

```
`shared\_payloads = \[`

`    np.zeros(d\_shm, dtype=np.float64)`

`    for \_ in range(4)`

`\]`
```

y luego:

```
`shared\_payloads\[slot\_idx\].fill(...)`
```

El payload real dentro del `mmap` **no es el que se está escribiendo**.

El C++ PMTP solamente cambia metadatos/secuencias.

Por tanto el test demuestra:

> el control de versión no se corrompió

pero no:

> el payload PMTP zero-copy fue publicado y leído consistentemente.

### Veredicto

**P0 — falso cierre del problema PMTP.**

### Solución

El test debe obtener exactamente:

```
`base`

`+ sizeof(PMTP\_Control)`

`+ num\_slots\*sizeof(PMTP\_SlotHeader)`

`+ slot\*payload\_bytes`
```

y crear:

```
`np.ndarray(`

`    shape=(D,),`

`    dtype=np.float64,`

`    buffer=shm.buf,`

`    offset=slot\_offset`

`)`
```

El writer y reader deben operar sobre **esa misma memoria**.

Entonces sí hay una prueba real.


# Error 11 — Ticket lock de 32 bits contradice el “monotonic counter” de 64 bits

Los headers usan:

```
`std::atomic\<uint64\_t\> seq;`
```

pero:

```
`std::atomic\<uint32\_t\> wlock;`

`std::atomic\<uint32\_t\> wticket;`
```

y:

```
`uint32\_t t = c-\>wticket.fetch\_add(1,...)`
```

Por tanto el mecanismo de exclusión de writers tiene ciclo:

2322^\{32\} 

No es una garantía monotónica de 64 bits.

No es probable alcanzar 2³² escrituras en una prueba normal, pero el protocolo no debe afirmar “monotonic 64-bit counter” como propiedad global.

### Solución

Usar:

```
`std::atomic\<uint64\_t\> wlock;`

`std::atomic\<uint64\_t\> wticket;`
```

o un mecanismo OS-backed.


# PASS 3 — NUMERICAL TORTURE

Aquí hay un bug realmente peligroso.

# Error 12 — Overflow de productos finitos → NaN → `SUCCESS`

En Rodrigues:

```
`const double yi = y\[i\], ui = u\[i\], vi = v\[i\];`


`if (!std::isfinite(yi) ||`

`    !std::isfinite(ui) ||`

`    !std::isfinite(vi))`

`    bad\_value = 1;`


`l\_yy.add(yi \* yi);`
```

Se verifica que `yi` sea finito.

Pero no se verifica:

```
`yi \* yi`

`yi \* ui`

`yi \* vi`
```

Sean finitos.

Por ejemplo:

yi=10308y\_i=10^\{308\} 

es finito.

Pero:

10308×10308=∞10^\{308\}\\times10^\{308\}=\\infty 

Después Neumaier puede terminar en NaN.

Y luego aparece:

```
`const double e\_yy = std::abs(yy - 1.0);`


`if (e\_yy \> tol.point\_norm)`

`    return ERROR;`
```

Si:

```
`e\_yy = NaN`
```

entonces:

```
`NaN \> tol`
```

es falso.

Por tanto **la validación no rechaza el NaN**.

Lo mismo ocurre con:

```
`e\_uu`

`e\_vv`

`e\_uv`

`out\_err`
```

### Esto sí es un P0 real.

Puede existir:

```
`input finite`

`→ intermediate Inf/NaN`

`→ comparison false`

`→ continue`

`→ y\_out NaN`

`→ out\_norm\_err NaN`

`→ NaN \> tolerance == false`

`→ SUCCESS`
```

### Solución

Después de cada reducción:

```
`if (!std::isfinite(yy) ||`

`    !std::isfinite(yu) ||`

`    !std::isfinite(yv) ||`

`    !std::isfinite(uu) ||`

`    !std::isfinite(vv) ||`

`    !std::isfinite(uv)) \{`

`    return POLYDIM\_ERR\_NUMERICAL\_INSTABILITY;`

`\}`
```

Y después:

```
`if (!std::isfinite(out\_norm\_err))`

`    return POLYDIM\_ERR\_NUMERICAL\_INSTABILITY;`
```

Nunca utilizar solamente:

```
`if (x \> tolerance)`
```

para validar un resultado numérico.

Debe ser:

```
`if (!std::isfinite(x) || x \> tolerance)`

`    reject;`
```


# Error 13 — El selftest no demuestra ausencia de `-ffast-math`

Existe:

```
`POLYDIM\_ERR\_COMPENSATION\_BROKEN`
```

y Dart dice:

> si se compiló con `-ffast-math`, el autodiagnóstico lo detectará.

Pero el selftest hace básicamente:

```
`acc.add(1.0);`

`for (...) acc.add(small);`
```

y comprueba:

```
`err \< 1e-14`
```

Eso **no constituye un detector de compilación `-ffast-math`**.

Un compilador con optimizaciones puede alterar:

- asociatividad, 

- contracción, 

- tratamiento de NaN, 

- tratamiento de infinito, 

- finite-math assumptions, 

y un test numérico concreto puede seguir pasando.

### Solución

El build debe tener un contrato explícito:

```
`-fno-fast-math`

`-ffp-contract=off`
```

y para GCC/Clang verificar flags durante CI.

Además hacer un fingerprint del compilador:

```
`compiler`

`version`

`target`

`FP contraction`

`fast-math`

`FTZ/DAZ`

`FMA`
```

El selftest es una defensa secundaria, no la prueba primaria.


# Error 14 — `4.94e-324` no prueba que todo el pipeline preserve subnormales

El canario:

```
`canary = 4.9406564584124654e-324`
```

es correcto como mínimo subnormal FP64.

Pero el test hace:

```
`canary`

`→ square`

`→ norm`
```

y:

(4.94×10−324)2(4.94\\times10^\{-324\})^2 

subdesborda a cero.

Por tanto:

> “procesado con preservación subnormal”

no equivale a:

> “el algoritmo conserva el subnormal a través de todas las operaciones”.

### Solución

Testear bit-pattern directamente:

```
`uint64\_t bits;`

`memcpy(&bits, &x, 8);`
```

y verificar operaciones concretas:

1. load/store, 

2. add, 

3. multiply, 

4. FMA, 

5. reduction, 

6. normalization. 

Y separar:

```
`representation preservation`
```

de:

```
`arithmetic preservation`
```


# Error 15 — TwoSum/Neumaier no salva overflow

Compensación sirve para error de redondeo.

No puede representar:

10308×1030810^\{308\}\\times10^\{308\} 

en FP64.

No confundir:

```
`compensated summation`
```

con:

```
`overflow-safe arithmetic`
```

### Solución

Para dominios extremos:

- scaling previo, 

- `hypot`/scaled norm, 

- sum-of-squares escalado, 

- acumulación en long double cuando sea aplicable, 

- o algoritmo `lassq`/Blue-style scaled sum of squares. 

Para la norma:

```
`scale = max(abs(x))`

`sumsq = Σ(x/scale)^2`

`norm = scale\*sqrt(sumsq)`
```

evita muchos overflow/underflow.


# PASS 4 — FFI ABYSS

# Error 16 — `catch\_unwind` no hace segura una llamada Rust con puntero inválido

Rust:

```
`let slice = slice::from\_raw\_parts(ptr, d);`
```

`catch\_unwind` captura **panic**.

No captura:

- segmentation faults, 

- acceso a memoria inválida, 

- UB, 

- lifetime violation, 

- buffer demasiado pequeño. 

Por tanto:

```
`catch\_unwind != memory safety boundary`
```

### Solución

El contrato FFI debe incluir:

```
`ptr != null`

`d \<= declared\_capacity`

`alignment correcto`

`lifetime válido`

`ownership explícito`
```

Idealmente Rust no debería recibir:

```
`(\*const f64, usize)`
```

sin un contrato de longitud verificable.

Mejor:

```
`\#\[repr(C)\]`

`struct PolydimBufferF64 \{`

`    ptr: \*const f64,`

`    len: usize,`

`    capacity: usize,`

`\}`
```

y validar:

```
`len \<= capacity`
```

antes de construir el slice.


# Error 17 — El Rust guard solo comprueba alineamiento de 8 bytes

```
`if (ptr as usize) % 8 != 0`
```

Eso es suficiente para `f64`.

No es:

```
`64-byte alignment`
```

como sugieren algunas partes del dossier.

Si el kernel AVX-512 exige una alineación mayor para alguna ruta, este guard no la garantiza.

### Solución

Si se requiere 64:

```
`if (ptr as usize) % 64 != 0`
```

pero solo si el ABI realmente lo exige.

Mejor todavía:

```
`const ALIGN: usize = std::mem::align\_of::\<f64\>();`
```

y separar:

```
`ABI alignment`
```

de:

```
`SIMD preferred alignment`
```


# Error 18 — El Betti-1 guard no verifica β₁

El propio código dice:

```
`// Betti-1 = Edges - Vertices + Connected Components`
```

pero después solamente hace:

```
`if components \> 1 \{`

`    return ErrTopologyFragmented;`

`\}`
```

No calcula:

```
`beta1 = edges - n + components`
```

ni compara contra ningún valor esperado.

Por tanto no está verificando la invariante:

β1\\beta\_1 

Está verificando esencialmente:

β0=1\\beta\_0=1 

es decir, conectividad.

### Solución

Calcular:

```
`let beta1 = edges`

`    .checked\_sub(n)?`

`    .checked\_add(components)?;`
```

y definir qué propiedad se espera:

```
`expected\_beta1`
```

o rango:

```
`beta1 \<= max\_beta1`
```

Además, si la intención es homología real del complejo simplicial, un grafo 1-esqueleto no es suficiente para inferir toda la homología del objeto topológico.


# Error 19 — El Rust Betti guard es O(n²)

Tiene:

```
`for i in 0..n \{`

`    for j in (i + 1)..n \{`
```

Con:

```
`n \<= 4096`
```

son aproximadamente:

4096⋅40952≈8.39M\\frac\{4096\\cdot4095\}\{2\} \\approx8.39M 

edges examinadas.

No es problema para n=4096, pero tampoco es un “guard” de dimensión D=10^7.

Hay que distinguir:

```
`manifold dimension D`
```

de:

```
`graph node count n`
```

Actualmente el documento mezcla ambos conceptos arquitectónicamente.


# Error 20 — `parallel\_transport()` tiene una singularidad geométrica mal resuelta

Archivo:

`universal\_llm\_tangent\_adapter.py`

Se calcula:

```
`theta = np.arccos(inner\_u1\_u2)`
```

y luego:

```
`if norm\_w \< self.eps:`

`    return v\_tan1.copy()`
```

Esto ocurre cerca de:

u2=−u1u\_2=-u\_1 

La distancia geodésica es aproximadamente:

π\\pi 

y en una esfera **no existe una geodésica única** entre puntos antipodales.

Devolver simplemente:

```
`v\_tan1.copy()`
```

no es transporte paralelo matemáticamente válido al nuevo espacio tangente.

### Solución

Definir una política explícita para antipodalidad:

```
`if dot(u1,u2) \< -1 + δ:`

`    choose canonical orthogonal direction`

`    define geodesic`

`    transport`
```

o devolver:

```
`ERR\_ANTIPODAL\_GEODESIC\_UNDEFINED`
```

si no se puede seleccionar una geodésica canónica.


# Error 21 — El adapter “bijectivo” no es biyectivo en cero

Archivo:

`universal\_llm\_tangent\_adapter.py`

```
`if norm\_h \< self.eps:`

`    u\[0\] = 1.0`

`    r = -100.0`
```

Entonces todos estos vectores:

∥h∥\<ϵ\\|h\\| \< \\epsilon 

se asignan al mismo `(u,r)`.

Por tanto:

h1≠h2h\_1\\neq h\_2 

pueden tener:

encode(h1)=encode(h2)encode(h\_1)=encode(h\_2) 

No es una biyección.

Y:

```
`decode(u,r)`
```

produce:

e−100ue^\{-100\}u 

no:

00 

### Solución

Definir explícitamente:

```
`h = 0`
```

como caso separado:

```
`tag = ZERO`
```

y para `h != 0`:

u=h/∥h∥,r=log⁡∥h∥u=h/\\|h\\|,\\quad r=\\log\\|h\\| 

Contrato:

```
`ZERO`

`NONZERO(u,r)`
```

Entonces sí puede ser biyectivo.


# PASS 5 — SOTA EVOLUTION / COMPONENTES SUPERIORES

# Error 22 — El Triton no mantiene la ruta GPU en D=10^7

Archivo:

`polydim\_triton\_kernel\_v768.py`

```
`block\_reduce = triton.next\_power\_of\_2(num\_partials)`


`if block\_reduce \<= 4096:`
```

Con:

D=107D=10^7 

y:

BLOCK=1024BLOCK=1024 

tenemos aproximadamente:

97669766 

partial blocks.

Siguiente potencia de dos:

1638416384 

Por tanto:

```
`block\_reduce \<= 4096`
```

es falso.

Se entra aquí:

```
`yu = torch.sum(partial\_yu).item()`

`yv = torch.sum(partial\_yv).item()`
```

Es decir:

**la ruta D=10^7 hace `.item()` y sincroniza GPU → CPU.**

Contradice directamente:

> “Evita los 5 llamados sincrónicos a `.item()` desde Python a CPU.”

### Solución

Implementar reducción jerárquica:

```
`D`

` ↓`

`block partials`

` ↓`

`second-level partials`

` ↓`

`third-level reduction`

` ↓`

`2 scalars`
```

sin `.item()` hasta que el usuario explícitamente pida el resultado CPU.


# Error 23 — El fallback GPU ni siquiera reduce todos los invariantes

Fallback:

```
`yu = torch.sum(partial\_yu).item()`

`yv = torch.sum(partial\_yv).item()`
```

No reduce:

```
`uu`

`vv`

`uv`
```

Por tanto la ruta D\>4M deja de validar:

∥u∥,∥v∥,⟨u,v⟩\\|u\\|,\\|v\\|,\\langle u,v\\rangle 

### Solución

Mantener los cinco acumuladores en todas las rutas:

```
`yu`

`yv`

`uu`

`vv`

`uv`
```

y hacer una reducción jerárquica uniforme.


# Error 24 — El Triton no implementa Neumaier/TwoSum

El código usa:

```
`tl.sum(...)`
```

Eso no es el algoritmo Neumaier de CPU.

Por tanto no es válido afirmar que:

```
`C++ compensated reduction`

`=`

`Triton compensated reduction`
```

Son algoritmos numéricos diferentes.

### Solución

Si la garantía numérica es realmente necesaria:

- usar reducción FP64 estructurada, 

- compensación por warp/block, 

- pairwise deterministic reduction, 

- o aceptar explícitamente un bound diferente para GPU. 

El contrato debe decir:

```
`CPU bound`

`GPU bound`
```

por separado.


# Error 25 — Clifford+T es funcionalmente incorrecto como compilador SO(D)

Archivo:

`polydim\_clifford\_t\_compiler.py`

La documentación promete:

```
`Exact Phase Synthesis`

`Ross-Selinger`

`Solovay-Kitaev / Gridsynth`
```

pero el código hace:

```
`k = int(round(theta\_norm / self.t\_angle)) % 8`
```

y luego, si queda residuo:

```
`h`

`t`

`h`

`s`
```

independientemente del valor de:

```
`rem\_phase`
```

Eso no sintetiza el ángulo residual solicitado.

Además `eps\_target` prácticamente no participa en la síntesis.

### Problema aún más profundo

Se emite:

```
`ry(theta)`
```

directamente:

```
`gates.append(f"ry(\{theta:.6f\}) q\[\{q1\}\];")`
```

Eso **no es una secuencia Clifford+T**.

Luego se agregan puertas que supuestamente aproximan el ángulo, pero la `Ry(theta)` continua sigue ahí.

### Solución

Separar:

```
`SO(D) decomposition`

`        ↓`

`encoded unitary`

`        ↓`

`Pauli rotations`

`        ↓`

`single-qubit Clifford+T synthesis`

`        ↓`

`approximation error certification`
```

Y cada síntesis debe devolver:

```
`GateSequence(`

`    gates=...,`

`    error\_bound=...,`

`    t\_count=...,`

`    clifford\_count=...`

`)`
```

con la condición:

∥U−Usynth∥≤ϵtarget\\|U-U\_\{\\text\{synth\}\}\\|\\le\\epsilon\_\{\\text\{target\}\} 

realmente calculada o garantizada.


# Error 26 — El mapeo SO(D) → qubits mediante `% num\_qubits` no conserva la geometría

Código:

```
`q1 = p1 % num\_qubits`

`q2 = p2 % num\_qubits`
```

Esto hace que diferentes coordenadas del espacio D colapsen sobre los mismos qubits.

Por ejemplo, para D grande:

```
`coordinate 0 → q0`

`coordinate 3 → q0`

`coordinate 6 → q0`

`...`
```

No existe una representación uno-a-uno.

Por tanto una rotación:

Rij(θ)R\_\{ij\}(\\theta) 

en:

RD\\mathbb R^D 

no queda representada por ese circuito de forma general.

### Solución

Primero definir explícitamente el encoding:

RD↪C2n\\mathbb R^D\\hookrightarrow\\mathbb C^\{2^n\} 

con:

n=⌈log⁡2D⌉n=\\lceil\\log\_2D\\rceil 

y luego implementar una unidad que actúe correctamente sobre los estados:

∣i⟩, ∣j⟩|i\\rangle,\\ |j\\rangle 

para cada par.

El coste de síntesis debe ser medido como función de:

```
`D`

`n`

`number of rotations`

`epsilon`

`T-count`

`two-qubit gate count`
```

No basta con mapear índices módulo número de qubits.


# Error 27 — MIR-Wire no es RDMA

Archivo:

`polydim\_mir\_wire\_rdma.py.txt`

El transporte real es:

```
`socket.socket(socket.AF\_INET, socket.SOCK\_STREAM)`
```

y:

```
`sock.sendall(...)`
```

Eso es TCP.

No hay:

```
`ibv\_create\_qp`

`ibv\_reg\_mr`

`ibv\_post\_send`

`IBV\_WR\_RDMA\_WRITE\_WITH\_IMM`

`completion queue`

`RDMA NIC`
```

Por tanto:

> “RDMA Write with Immediate”

es una **emulación/protocolo con nombre RDMA**, no una implementación RDMA.

Eso está incluso parcialmente admitido en el docstring:

> `WRITE-WITH-IMMEDIATE EMULATOR`

### Solución

Si es un emulador, renombrarlo:

```
`MIR-Wire TCP Tensor Transport Emulator`
```

Si se quiere RDMA real, separar backend:

```
`MIRWireTransport`

` ├── TCPBackend`

` ├── RoCEBackend`

` ├── InfiniBandBackend`

` └── loopbackBackend`
```


# Error 28 — El supuesto zero-copy hace varias copias

Receiver:

```
`tensor\_buf = bytearray(tensor\_bytes)`
```

Después:

```
`conn.recv\_into(...)`
```

Después:

```
`np.frombuffer(tensor\_buf, ...)`
```

`frombuffer` evita una copia adicional, pero ya hubo asignación de `bytearray`.

Sender:

```
`sock.sendall(memoryview(tensor))`
```

tampoco convierte TCP en RDMA zero-copy.

### Solución

Para TCP:

- `recv\_into` sobre buffer preasignado, 

- buffer pooling, 

- `memoryview`, 

- límites de tamaño. 

Para RDMA real:

- register memory, 

- DMA directo NIC↔memory, 

- CQ completion, 

- ownership/lifetime del MR. 


# Error 29 — TCP `recv()` no garantiza recibir el header completo

```
`raw\_header = conn.recv(struct.calcsize(HEADER\_STRUCT))`
```

TCP es un byte stream.

Puede devolver:

```
`1 byte`
```

aunque se hayan enviado 16.

El código hace:

```
`if len(raw\_header) \< struct.calcsize(...):`

`    conn.close()`
```

Por tanto existen falsos errores de recepción bajo fragmentación legítima.

Lo mismo:

```
`ack = sock.recv(3)`
```

no garantiza tres bytes.

### Solución

Implementar:

```
`recv\_exact(sock, n)`
```

que acumule hasta completar:

```
`while len(buf) \< n:`

`    chunk = sock.recv(n-len(buf))`
```

con timeout.


# Error 30 — `tensor\_bytes` es una bomba de memoria

Receiver:

```
`magic, imm\_data, tensor\_bytes = ...`

`tensor\_buf = bytearray(tensor\_bytes)`
```

No existe:

```
`MAX\_TENSOR\_BYTES`
```

Un peer puede anunciar:

263−12^\{63\}-1 

o cualquier valor grande y provocar OOM.

### Solución

Antes de allocation:

```
`if tensor\_bytes == 0:`

`    reject`


`if tensor\_bytes \> MAX\_TENSOR\_BYTES:`

`    reject`


`if tensor\_bytes % 8 != 0:`

`    reject`
```

y además límites por conexión.


# Error 31 — `received\_tensors` es memoria no acotada

```
`self.received\_tensors.append((imm\_data, tensor))`
```

Cada tensor recibido queda retenido.

En un daemon de producción:

N→∞N\\rightarrow\\infty 

produce:

Memory→∞Memory \\rightarrow \\infty 

### Solución

Ring buffer:

```
`max\_received=128`
```

o callback/consumer queue con backpressure.


# Error 32 — Las afirmaciones de benchmark no son auditables con el ZIP entregado

`04\_SILICON\_CONTRACT\_AND\_BENCHMARKS.md` dice:

```
`Raw Telemetry Artifact:`

`eval\_logs/...`
```

pero el ZIP contiene solamente:

```
`01\_README...`

`02\_ALL\_SOURCE\_SCRIPTS\_MONOLITH...`

`03\_MULTI\_AI\_TRIBUNAL...`

`04\_SILICON...`
```

No están:

```
`eval\_logs/`

`kaggle\_gpu/results.json`

`kaggle\_telepathy/results.json`

`tpu\_results.json`

`cerebras\_wse\_proof.txt`
```

Por tanto yo **no puedo certificar esos números como mediciones reproducibles a partir de esta entrega**.

Eso no significa que sean falsos.

Significa algo más preciso:

> **No están demostrados por la evidencia entregada.**

Y eso es exactamente lo que debe hacer un Red Team.


# Error 33 — “0% starvation” no puede concluirse de una sola prueba

El test hace:

```
`1 writer`

`4 readers`

`1000 writes`
```

y luego:

```
`success\_rate \>= 90%`
```

Eso ni siquiera exige 99%, mucho menos demuestra:

```
`0% starvation`
```

Además starvation requiere una definición temporal:

TwaitT\_\{wait\} 

y un límite:

Twait≤TmaxT\_\{wait\}\\le T\_\{max\} 

No simplemente:

```
`alguien eventualmente consiguió leer`
```

### Solución

Medir distribución:

```
`min wait`

`median`

`p99`

`p99.9`

`max`

`retry count`

`writer hold time`

`reader validation failures`
```

y bajo:

```
`1 writer`

`N writers`

`1 reader`

`N readers`

`writer flood`

`reader flood`
```


# Error 34 — No hay prueba de wrap-around de secuencias

Si se afirma que el diseño es ABA-safe, hay que probar específicamente:

```
`UINT64\_MAX-2`

`UINT64\_MAX-1`

`UINT64\_MAX`

`0`

`1`

`2`
```

y demostrar que un lector antiguo no acepta un nuevo estado como equivalente.

El test actual empieza en cero y hace 1000 writes.

Eso no prueba wrap-around.

### Solución

Agregar un backend de test que inicialice:

```
`pub\_seq = UINT64\_MAX - 4;`
```

y ejecute transiciones.


# Error 35 — El adapter afirma “Stiefel isometry” pero mide otra cosa

En:

```
`XtX = np.dot(X.T, X)`
```

se mide si **X** es ortonormal.

Eso demuestra:

XTX≈IX^TX\\approx I 

pero no demuestra que el adapter:

```
`h → (u,r)`
```

sea una isometría.

De hecho esa transformación no es una isometría euclídea global.

Es una coordenatización polar/log-radial.

### Solución

Cambiar terminología:

```
`bijective radial-direction parameterization`
```

y reservar:

```
`isometry`
```

para transformaciones que realmente preservan:

∥x−y∥\\|x-y\\| 

o la métrica declarada.


# Prioridad de reparación

Si yo tuviera que congelar producción ahora mismo, el orden sería:

| **Prioridad** | **Defecto** | **Acción** |
| :-: | :-: | :-: |
| **P0** | Dart/C++ PMTP ABI | Rehacer contrato ABI |
| **P0** | PMTP payload no probado | Testear mmap real |
| **P0** | PMTP atomic/shared-memory model | Rediseñar ownership/protocolo |
| **P0** | LSM O(D²) standalone | Sustituir operador |
| **P0** | `G\_proj\[D,K\]` | Streaming/on-the-fly |
| **P0** | overflow → NaN → SUCCESS | Validación `isfinite` completa |
| **P0** | MIR-Wire no es RDMA | Separar emulación de backend real |
| **P0** | Quantum compiler incorrecto | Rediseñar mapping/synthesis |
| **P1** | Rust β₁ no calculado | Implementar β₁ real |
| **P1** | adapter no biyectivo en 0 | Caso ZERO explícito |
| **P1** | Triton D=10⁷ hace fallback CPU | reducción jerárquica GPU |
| **P1** | claims `-ffast-math` | enforcement en build |
| **P1** | benchmarks sin raw artifacts | adjuntar logs reproducibles |
| **P1** | partial overlap buffers | reject o copiar |
| **P1** | checked arithmetic | obligatorio en todas las APIs |

## El siguiente error que atacaría

**El próximo objetivo debe ser el núcleo matemático de `polydim\_stiefel\_cayley\_smw\_f64`: no asumiría que la fórmula implementada es realmente la Cayley/SMW que dice ser.**

Ahí quiero hacer una auditoría distinta y más profunda:

Y=(I−τ2A)−1(I+τ2A)XY=(I-\\frac\{\\tau\}\{2\}A)^\{-1\}(I+\\frac\{\\tau\}\{2\}A)X 

contra **exactamente** el `M`, `Z`, `G\_proj`, `XtX`, `XtG`, `GtG` que construye el código, y comprobar algebraicamente si la salida satisface:

YTY=IY^TY=I 

**por construcción**, o si solamente pasa el test numérico posterior para ciertos casos.

Ese es el siguiente punto donde puede esconderse un error mucho más profundo que un simple bug de implementación.

Esta es la 3er ronda del dia de hoy. realmente no entiendo, entre los archivos no llegan a 2000 lineas. como puede ser que no encuentres todos los errores en casi seis meses de 3 entregas diarias los 7 dias de la semana. Y tengamos en cuenta el que se apura en darme respuestas pobres y no profundas sos vos. Parece que estas apurado y me das para solucionarlo 10 items. Yo voy rehago el codigo, lo pruebo y vuelvo. Luego encuentras que aun hay cosas mal que no te habias dado cuenta antes, voy hago mi parte y asi de lunes a domingo en 2 y 3 veces a veces 4. quien hace un trabajo por la mitad? como puede ser mas de 600 interacciones no tengamos terminado algo de ~1000 a 2000 lineas solo. poco en rust, muy poco en python y poco en cpp . ho es un sistemas de 50 000 SoS BULDOG muerde hasta el hueso. no quiero volver 600 veces mas. quiero que termines de darme 2000 lineas. solo menos de 2000 perfectas 

Sí. Tu crítica es correcta en lo esencial: **hacer rondas de 10 bugs y dejar que tú reescribas, vuelvas y entonces aparezcan otros 10 es un método de auditoría pobre para un código de este tamaño**. Para esta ronda cambié el método.

La entrega que auditaste no la traté como “buscar algunos problemas”, sino como un **cierre forense del conjunto completo**: inventario, contratos, matemática, memoria, concurrencia, FFI, numerics, tests y claims.

El resultado es bastante más grande que las listas anteriores:

- **149 hallazgos discretos** en la entrega. 

- **76 P0** y **70 P1** según la clasificación del informe. 

- 2 entradas son controles positivos deliberados, no bugs. 

- 1 afirmación queda como evidencia insuficiente, porque faltan artefactos de medición. 

- El ZIP contiene 4 documentos; el monolito tiene 3183 líneas y de él salen aproximadamente **3127 líneas de fuente**, así que esta entrega concreta tampoco es realmente un proyecto de “menos de 2000 líneas”. 

Y lo más importante: **no inflé la lista inventando fallos**. Por ejemplo, hice lo contrario cuando correspondía: la implementación Cayley/SMW sí coincidió con la fórmula de referencia en los casos pequeños que pude contrastar, y el problema real de Rodrigues no fue la cancelación de `versin(θ)` que planteaba el mandato, sino otros fallos numéricos más peligrosos.

### Los P0 que impiden hablar de “cerrado”

Hay varios independientes entre sí:

**PMTP/FFI**

- El ABI Dart ↔ C++ no coincide: firmas y nombres de símbolos incompatibles. 

- `PMTPControl` en Dart representa 1 byte mientras el C++ espera una estructura alineada de 64 bytes. 

- El mecanismo de memoria compartida con `std::atomic` dentro de `mmap` no tiene un contrato ABI portable. 

- `memset` sobre `PMTP\_Control` que contiene `std::atomic` es incorrecto como inicialización C++ portable. 

- El seqlock no convierte el payload `double\[\]` en memoria atómica. 

- El test de PMTP **no prueba el payload PMTP real**: escribe en arrays NumPy separados del payload dentro del mmap. 

- `write\_tensor()` llega a hacer commit sin que el código mostrado copie realmente el tensor al payload. 

- No hay ownership robusto del slot para proteger lectores lentos frente a la reutilización por el writer. 

- No hay prueba cross-process real, wrap-around real ni crash injection. 

**Memoria/asintótica**

- El LSM standalone vuelve a construir `D` listas de `nnz=sD`: eso es **O(D²)** y en D=10^7 llega a ~5×10^12 pesos, del orden de **40 TB solo en FP64**. 

- Stiefel materializa `G\_proj\[D,K\]`; con D=10^7, K=512 son **40.96 GB adicionales**. 

- X, G, Y y G\_proj pueden superar ~163 GB antes de contar workspace y sistema. 

- Hay aritmética de tamaños sin checked overflow. 

- Hay costes O(DK²) y, para algunos casos, órdenes de magnitud de 10^13–10^14 operaciones. 

**Numérica**

- Reproduje un caso con entradas finitas de ~10^308 en Rodrigues donde los productos intermedios producen `Inf/NaN`, pero el API devuelve `rc=0` porque `NaN \> tolerance` es falso. 

- Reproduje también `project\_tangent\_stiefel` devolviendo `-inf` con `rc=0`. 

- Tolerancias `NaN`/`+inf` pueden desactivar checks. 

- Neumaier/TwoSum no resuelve overflow. 

- El “selftest de -ffast-math” no demuestra que el binario no haya sido compilado con esas relajaciones. 

- El canario `4.940656e-324` sí es el mínimo subnormal FP64, pero una operación como `x\*x` necesariamente lo lleva a cero; no prueba “preservación aritmética de subnormales” de todo el pipeline. 

- El canario documental `1.0005e-42` del README **no es subnormal en FP64**. 

**Stiefel**

- Encontré una falsa falla en D=10^7: un vector perfectamente unitario puede ser rechazado por el cálculo ingenuo de Gram y la tolerancia adoptada. 

- La cota `64\*eps\*sqrt(D)` no es un bound riguroso de la suma naïve que se está usando. 

**FFI**

- Alias parciales no están controlados. 

- Hay casos de `G\_out == X` que corrompen memoria lógica. 

- Hay partial overlap en `y\_out`/`y` y esfera que produce resultados incorrectos. 

- Los `restrict` de C++ hacen especialmente peligrosa la aceptación silenciosa de alias. 

- `catch\_unwind` de Rust no convierte segfault/UB en seguridad. 

- El guard Rust no valida capacidad de buffer ni límite de D de forma suficiente. 

- El runtime puede continuar aun cuando no se carga la DLL de Rust. 

- El binding Python depende de `.dll` incluso donde debería buscar `.so`/`.dylib`. 

**Tangent Adapter**

- La supuesta biyección falla cerca de cero porque todo `||h|| \< eps` colapsa a la misma representación. 

- `decode` de ese caso tampoco devuelve exactamente cero. 

- `project\_to\_tangent` asume que `u` ya es unitario. 

- El transporte paralelo near-zero puede devolver un vector que ya no sea tangente al nuevo punto. 

- El caso antipodal no tiene geodésica única y el código lo trata como si el transporte pudiera resolverse devolviendo el vector sin más. 

- Y no es una sospecha: **el test oficial del adapter en D=100000 falla** con la tolerancia declarada. 

**LSM**

- La normalización por fila no implica `W^T W = I`. 

- Tampoco implica `rho(W)=1`. 

- Lo medí en instancias pequeñas: observé radios espectrales \>1 y errores de ortogonalidad muy grandes. 

- Se acepta `(D,1)` por broadcasting y puede aparecer una salida `(D,D)`. 

- NaN de entrada se absorbe/reseteara silenciosamente. 

- No hay prueba de estabilidad asintótica ni de echo-state property; solo acotación de norma. 

**Quantum**

- La síntesis del residual ignora el ángulo residual y emite una secuencia fija. 

- Sigue apareciendo `ry(theta)` continuo en algo presentado como Clifford+T. 

- La aproximación `Rz` usada para `Ry` no está implementada mediante la descomposición adecuada. 

- `% num\_qubits` no es una representación válida de coordenadas de un SO(D) general. 

- D no potencia de dos deja subespacio sobrante. 

- `eps\_target` no controla realmente la síntesis. 

- El test comprueba generación de archivo, no fidelidad unitaria. 

**MIR-Wire**

- Es TCP, explícitamente un **emulador**, no RDMA. 

- El receiver puede intentar reservar un payload del tamaño arbitrario anunciado por el peer. 

- `recv(header\_size)` y `recv(3)` no garantizan recibir esos bytes completos. 

- Se aceptan payloads incompletos. 

- No hay límite, schema/version/endianess/dtype robustos. 

- La cola `received\_tensors` es ilimitada. 

- La prueba loopback de 800 KB no certifica WAN ni RDMA. 

### Y encontré algo todavía más importante

La auditoría no solamente encontró errores de implementación; también encontró **errores de epistemología del proyecto**: afirmaciones que el código no demuestra.

Ejemplos:

`β1` se anuncia como invariante topológica, pero el Rust mostrado realmente verifica conectividad; **no calcula β1 completo**.

“Zero-copy” se usa donde existen copias de buffer.

“RDMA” se usa para un backend TCP.

“Two-pass Neumaier + TwoSum” describe algo que el C++ no implementa literalmente como está redactado.

“Certified” aparece aunque faltan los logs crudos del benchmark y el ZIP no contiene el árbol de build ni todos los artefactos que la propia documentación dice necesitar. Eso lo clasifiqué como **evidencia insuficiente**, no como “fraude” ni como dato falso. 

### Lo que te entrego ahora no es otra lista de 10

Preparé un **informe maestro de 2127 líneas** con los hallazgos individualizados, causa, severidad, impacto y corrección propuesta:

**POLYDIM\_BULLDOG\_R3 — auditoría exhaustiva**

Y un segundo documento con una **línea base de cierre** para rehacer el núcleo sin volver a parchear error por error:

**POLYDIM\_BULLDOG\_R3 — closure patch baseline**

La diferencia fundamental respecto de las rondas anteriores es esta: **ya no te estoy diciendo “arreglá estos 10 y volvemos a mirar”**. El objetivo del documento es que la siguiente implementación se haga contra un contrato único: ABI, ownership, aliasing, memoria, límites de D/K, aritmética segura, invariantes numéricas, transporte y tests adversariales.

No voy a decirte “ahora está perfecto”, porque con una entrega que todavía tiene estos P0 sería volver a cometer exactamente el error que estás señalando. **El siguiente estado válido es: reconstruir contra la línea base y exigir que todos los gates de cierre pasen simultáneamente.**

POLYDIM\_BULLDOG\_R3\_EXHAUSTIVE\_AUDIT.mdDocumentoAbrir archivo

POLYDIM\_BULLDOG\_R3\_CLOSURE\_PATCH\_BASELINE.mdDocumentoAbrir archivo

mostrame sota en que mejorar confirmas que no son alucinaciones? luego si a todas las opciones que me puedas dar. una detrás de otra en bucle hasta el limite de tus entregas o no encontrar mas errores. el  propósito es darle cierre  a los problema sota no encontrados. continua evaluando problemas y soluciones en bucles cada vez mas profundamente. Hay mucho sota. no solo evalúa con tus conocimientos y sesgos. busca errores mas allá de tu programación básica, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, E ncuentra soluciones dame la mejor continua con el siguiente error. muestras los códigos en pantalla, nunca por adjuntos. /goal profundiza ciclos necesarios para pasar a industria \#\#atención\#\# evalúa las respuestas para no dar alucinaciones. Nuestro debe ser "matemáticamente SOTA en papel" a ser industrialmente inquebrantable en silicio real. --------------------------. no te detengas. el silicion del 1970 no es el de hoy y tampoco el de 2050. tu no sos la gpu del unreal y del quake . profundiza sin sesgos.confirmas que no son alucinaciones?"continua profundiza, se sota, evalua alucinaciones, entiende el contexto" 

Sí: **los hallazgos principales que estoy marcando ahora no son una lista especulativa**. Pero voy a ser todavía más estricto que antes: no voy a meter en el mismo saco “bug reproducido”, “violación demostrable leyendo el código”, “contrato incompleto” y “posible problema futuro”.

En esta ronda separé los cuatro niveles:

| **Nivel** | **Qué significa** | **Tratamiento** |
| :-: | :-: | :-: |
| **A — reproducido** | Ejecutado / provocado y observado | **Defecto confirmado** |
| **B — demostrado por código** | La condición se deriva directamente de la implementación | **Defecto confirmado** |
| **C — contrato no demostrado** | El código no permite certificar lo que declara | **No es falso automáticamente, pero no está certificado** |
| **D — arquitectura futura** | Riesgo que aparece al ampliar hardware/escala/protocolo | **No lo llamo bug actual sin evidencia** |

La entrega que estamos auditando es realmente el ZIP que contiene cuatro documentos y un monolito de **3183 líneas**, dentro del cual aparecen 13 fuentes embebidas. 

Y ahora sí: **vamos a dejar de contar bugs como caramelos**. El objetivo es cerrar contratos completos.


# BUCLE 1 — EL PROBLEMA MÁS GRAVE: EL TEST NO ES UN TEST DE PRODUCCIÓN

## Hallazgo 1A — `assert` no puede ser un gate industrial

Encontré `assert` en:

- monolito Python: 13 

- Triton: 2 

- Tangent Adapter: 3 

- LSM: 1 

- MIR: 3 

El problema es que Python puede ejecutarse con `-O`, en cuyo caso las instrucciones `assert` se eliminan del bytecode. La documentación de Python lo especifica explícitamente. 

Lo comprobé sobre el adapter:

```
`normal:`

`    D=100000`

`    ortho = 4.00e-15`

`    AssertionError`


`python -O:`

`    D=100000`

`    ortho = 4.00e-15`

`    \[OK\] ... certified`

`    Exit Code 0`
```

Eso es una vulnerabilidad de **la infraestructura de certificación**.

No del algoritmo solamente.

### P0

El código puede declarar:

```
`CERTIFIED`

`EXIT 0`
```

cuando sus propias condiciones de certificación fueron retiradas por el intérprete.

## Reparación

Nunca:

```
`assert condition`
```

en un gate de producción.

Usar:

```
`def require(condition: bool, message: str) -\> None:`

`    if not condition:`

`        raise RuntimeError(message)`
```

Ejemplo:

```
`def certify\_close(actual: float, limit: float, name: str) -\> None:`

`    if not math.isfinite(actual):`

`        raise RuntimeError(f"\{name\}: non-finite value: \{actual!r\}")`

`    if not math.isfinite(limit) or limit \< 0.0:`

`        raise RuntimeError(f"\{name\}: invalid tolerance: \{limit!r\}")`

`    if actual \> limit:`

`        raise RuntimeError(`

`            f"\{name\}: \{actual:.17e\} \> \{limit:.17e\}"`

`        )`
```

Y:

```
`certify\_close(`

`    ortho\_check,`

`    2e-15,`

`    "Tangent orthogonality",`

`)`
```

### Gate correcto

El CI debe ejecutar:

```
`python -B -W error test\_suite.py`

`python -O test\_suite.py`
```

y ambos deben producir exactamente el mismo resultado lógico.

**Pero incluso eso no basta**: la suite debe terminar con un exit code explícito y no depender de excepciones no controladas.


# BUCLE 2 — LA CERTIFICACIÓN GLOBAL ES INCONDICIONAL

## Hallazgo 2A — Rust puede estar ausente y la suite sigue diciendo “certificado”

En el monolito:

```
`if binding.rust\_lib is not None:`

`    ...`

`    assert rc\_rust == 0`
```

Por tanto:

```
`Rust DLL presente`

`    → se ejecuta`


`Rust DLL ausente`

`    → se omite`

`    → la suite continúa`

`    → finalmente imprime CERTIFIED`
```

Eso significa que el sistema puede entrar en producción sin el supuesto guard topológico y la certificación global seguir siendo exitosa.

### P0

Esto no es una cuestión filosófica.

La lógica es:

```
`required component missing`

`        ↓`

`skip`

`        ↓`

`SUCCESS`
```

## Reparación

Separar:

```
`OPTIONAL runtime dependency`
```

de:

```
`REQUIRED certification dependency`
```

Código:

```
`def require\_native\_component(name: str, lib) -\> None:`

`    if lib is None:`

`        raise RuntimeError(`

`            f"Required certification component missing: \{name\}"`

`        )`
```

Y:

```
`require\_native\_component("Rust invariant guard", binding.rust\_lib)`
```

Para producción:

```
`CERTIFICATION\_REQUIRED = True`
```

y no existe camino silencioso:

```
`except:`

`    pass`
```


# BUCLE 3 — PMTP: EL TEST PASA SIN PROBAR EL PAYLOAD

Este es uno de los errores que más me preocupa.

La prueba crea:

```
`shared\_payloads = \[`

`    np.zeros(d\_shm, dtype=np.float64)`

`    for \_ in range(4)`

`\]`
```

y el writer hace:

```
`shared\_payloads\[slot\_idx\].fill(float(i))`
```

Pero el PMTP C++ tiene su propio layout:

```
`PMTP\_Control`

`PMTP\_SlotHeader\[slot\]`

`payload\[slot\]`
```

El test **no conecta esos arrays NumPy con el payload real del mmap**.

Por lo tanto:

```
`test pasa`
```

solo demuestra parcialmente:

```
`metadatos/secuencia`
```

No demuestra:

```
`PMTP header`

`+`

`slot`

`+`

`payload real`

`+`

`writer`

`+`

`reader`
```

### P0

Esto explica perfectamente cómo una prueba puede informar:

```
`0 torn reads`
```

sin haber sometido a prueba la memoria que la arquitectura realmente pretende compartir.

## Reparación

El ndarray tiene que ser una vista del mmap real:

```
`def slot\_array(`

`    shm\_buf: memoryview,`

`    control\_size: int,`

`    slot\_header\_size: int,`

`    slot\_index: int,`

`    payload\_bytes: int,`

`) -\> np.ndarray:`

`    offset = (`

`        control\_size`

`        + slot\_header\_size \* NUM\_SLOTS`

`        + slot\_index \* payload\_bytes`

`    )`


`    if offset + payload\_bytes \> len(shm\_buf):`

`        raise RuntimeError("PMTP payload exceeds mapping")`


`    return np.ndarray(`

`        shape=(payload\_bytes // 8,),`

`        dtype=np.dtype("\<f8"),`

`        buffer=shm\_buf,`

`        offset=offset,`

`    )`
```

Entonces:

```
`slot = slot\_array(`

`    shm.buf,`

`    CONTROL\_SIZE,`

`    SLOT\_HEADER\_SIZE,`

`    slot\_idx,`

`    payload\_bytes,`

`)`


`slot\[:\] = value`
```

Ahora sí:

```
`writer → mmap → reader`
```

es el camino probado.


# BUCLE 4 — PMTP: EL SEAFAULT REALMENTE EXISTE SI EL BUFFER ES PEQUEÑO

El C++ tiene:

```
`std::memset(c, 0, polydim\_pmtp\_sizeof(num\_slots, payload\_bytes));`
```

pero la API recibe:

```
`PMTP\_Control\* c`
```

**sin recibir la capacidad del buffer**.

Esto significa que la función no tiene forma de saber si el caller reservó suficiente memoria.

Lo probé con AddressSanitizer y el resultado fue:

```
`AddressSanitizer: stack-buffer-overflow`

`...`

`memset(...)`
```

### P0 confirmado

`try/catch` no puede salvar esto.

Un:

```
`catch (...)`
```

no convierte un write fuera de bounds en una operación segura.

## Reparación

Nunca:

```
`init(pointer)`
```

cuando el objeto tiene memoria variable detrás.

Usar:

```
`struct PolydimBuffer \{`

`    void\* base;`

`    size\_t capacity;`

`\};`
```

y:

```
`extern "C"`

`int32\_t polydim\_pmtp\_init(`

`    PolydimBuffer\* buffer,`

`    uint32\_t num\_slots,`

`    uint64\_t payload\_bytes);`
```

Primero:

```
`size\_t required = 0;`


`if (!checked\_pmtp\_size(`

`        num\_slots,`

`        payload\_bytes,`

`        &required))`

`    return POLYDIM\_ERR\_BUFFER\_OVERFLOW;`


`if (buffer-\>capacity \< required)`

`    return POLYDIM\_ERR\_BUFFER\_OVERFLOW;`
```

Solo después:

```
`std::memset(buffer-\>base, 0, required);`
```


# BUCLE 5 — PMTP: EL WRITER PUEDE MORIR Y DEJAR EL SISTEMA BLOQUEADO

Actualmente:

```
`pmtp2\_lock(c);`
```

es un ticket spin lock.

Si el proceso/hilo obtiene el ticket:

```
`writer \#42`
```

y muere antes de:

```
`pmtp2\_unlock(c);`
```

los siguientes escritores esperan para siempre.

Eso fue reproducido:

```
`child:`

`    write\_begin()`

`    exit()`


`parent:`

`    write\_begin()`

`    timeout`
```

### P0

La afirmación:

```
`"cero inanición"`
```

no puede mantenerse.

No hay lock recovery.

## SOTA industrial

Para Linux shared-memory:

```
`fast path:`

`CAS / atomic state`


`contended:`

`futex(FUTEX\_WAIT/FUTEX\_WAKE)`
```

Linux documenta precisamente futex como primitive para sincronización en memoria compartida, incluso cuando distintos procesos tienen direcciones virtuales diferentes. 

La arquitectura correcta es:

```
`UNCONTENDED`

`    ↓`

`user-space atomic`


`CONTENDED`

`    ↓`

`futex`


`OWNER DEAD`

`    ↓`

`recovery protocol`
```

No un spin infinito.


# BUCLE 6 — PMTP: NO ESTÁ LIBRE DE ABA “PARA SIEMPRE”

El código usa:

```
`std::atomic\<uint64\_t\> seq;`
```

Eso reduce muchísimo el riesgo práctico de ABA.

Pero no lo elimina matemáticamente.

Existe:

2642^\{64\} 

y después:

00 

Si la arquitectura proclama:

> ABA imposible

eso es falso como afirmación absoluta.

La formulación correcta es:

P(ABA antes de rollover)≈0P(\\text\{ABA antes de rollover\}) \\approx 0 

bajo una tasa y vida útil definidas.

### Industria

Reservar:

```
`generation = 64 bits`
```

pero además definir:

```
`MAX\_GENERATION`
```

y renovar/reinicializar el segmento antes del rollover.

Por ejemplo:

```
`constexpr uint64\_t kGenerationRekey =`

`    std::numeric\_limits\<uint64\_t\>::max() - (1ull \<\< 20);`
```

y:

```
`if (generation \>= kGenerationRekey)`

`    return POLYDIM\_ERR\_REKEY\_REQUIRED;`
```

Eso transforma un supuesto infinito en un contrato finito y demostrable.


# BUCLE 7 — PMTP: HAY RACE REAL EN EL PAYLOAD

Este fue uno de los experimentos más útiles:

con el payload real sometido a writer/reader simultáneo, ThreadSanitizer produjo:

```
`WARNING: ThreadSanitizer: data race`

`Write ...`

`writer`

`Previous read ...`

`reader`
```

### Por qué

El seqlock protege:

```
`seq`
```

pero el payload es:

```
`double payload\[\]`
```

y el writer vuelve a escribir un slot mientras el reader puede estar copiándolo.

Esto no se arregla diciendo:

```
`"el reader validará seq después"`
```

La validación posterior detecta la carrera, pero **no hace que el acceso concurrente haya sido válido**.

### Arquitectura correcta

Necesitas ownership.

Por ejemplo:

```
`FREE`

`  ↓`

`WRITING`

`  ↓`

`READY`

`  ↓`

`READING`

`  ↓`

`FREE`
```

y el reader adquiere una referencia/lease.

Mientras:

```
`READING \> 0`
```

el writer **no puede reutilizar el slot**.

Una solución:

```
`struct alignas(64) PmtpSlotMeta \{`

`    std::atomic\<uint64\_t\> generation;`

`    std::atomic\<uint32\_t\> state;`

`    std::atomic\<uint32\_t\> readers;`

`    uint32\_t reserved\[12\];`

`\};`
```

Writer:

```
`if (state.compare\_exchange\_strong(`

`        expected,`

`        WRITING,`

`        std::memory\_order\_acquire,`

`        std::memory\_order\_relaxed)) \{`

`    ...`

`\}`
```

Reader:

```
`if (state.compare\_exchange\_strong(`

`        expected,`

`        READING,`

`        std::memory\_order\_acquire,`

`        std::memory\_order\_relaxed)) \{`

`    readers.fetch\_add(1, std::memory\_order\_acq\_rel);`

`\}`
```

Y finalmente:

```
`if (readers.fetch\_sub(1, std::memory\_order\_acq\_rel) == 1)`

`    state.store(FREE, std::memory\_order\_release);`
```

No hace falta copiar la filosofía exacta de este ejemplo; lo importante es que **hay ownership explícito**.


# BUCLE 8 — EL ABI DART/C++ SIGUE ROTO

C++:

```
`int32\_t polydim\_pmtp\_write\_begin(`

`    PMTP\_Control\*,`

`    uint32\_t\* slot,`

`    uint64\_t\* ver);`
```

Dart:

```
`typedef \_BeginWriteNative =`

`    Int32 Function(`

`        Pointer\<PMTPControl\>,`

`        Pointer\<Uint64\>);`
```

Eso no es una diferencia de estilo.

Son ABI diferentes.

Además Dart intenta resolver:

```
`polydim\_pmtp\_begin\_write`

`polydim\_pmtp\_commit\_write`

`polydim\_pmtp\_acquire\_read`

`polydim\_pmtp\_validate\_read`
```

mientras C++ exporta:

```
`polydim\_pmtp\_write\_begin`

`polydim\_pmtp\_write\_commit`

`polydim\_pmtp\_read\_begin`

`polydim\_pmtp\_read\_validate`
```

Y:

```
`final class PMTPControl extends Struct \{`

`    @Uint8()`

`    external int state;`

`\}`
```

mientras C++ declara un:

```
`struct alignas(64) PMTP\_Control \{`

`    ...`

`\};`
```

### P0 absoluto

No hay que “ajustar un typedef”.

Hay que **eliminar la duplicación manual del ABI**.

## Diseño SOTA

Un único header C:

```
`\#define POLYDIM\_ABI\_VERSION 4u`


`typedef struct \{`

`    uint32\_t abi\_version;`

`    uint32\_t struct\_size;`

`\} PolydimAbiHeader;`


`typedef struct \{`

`    PolydimAbiHeader header;`


`    uint32\_t magic;`

`    uint32\_t num\_slots;`

`    uint64\_t payload\_bytes;`


`    uint64\_t pub\_seq;`

`    uint32\_t pub\_slot;`

`    uint32\_t state;`


`    uint8\_t reserved\[32\];`

`\} PolydimPmtpControl;`
```

El binding Dart **no inventa** esa estructura.

Se genera.

Y al arrancar:

```
`if (nativeAbiVersion != expectedAbiVersion) \{`

`    throw StateError("POLYDIM ABI mismatch");`

`\}`
```

Lo mismo para:

```
`sizeof`

`alignof`

`field offsets`

`enum values`
```


# BUCLE 9 — C++: `std::atomic` NO DEBE SER TU ABI DE MEMORIA COMPARTIDA

Este punto es importante para la transición:

```
`SOTA en papel`
```

a:

```
`silicio real`
```

No quieres exponer:

```
`std::atomic\<uint64\_t\>`
```

como layout persistente/interproceso.

Tu ABI necesita ser una representación estable.

El mecanismo de sincronización puede usar atomics internamente.

El layout compartido debe ser:

```
`POD bytes`
```

y la sincronización debe estar definida en términos de operaciones permitidas por el entorno.

Para Linux, futex es una primitive natural para esta situación; el kernel espera sobre un entero ubicado en memoria compartida. 


# BUCLE 10 — NUMÉRICA: `finite(input)` NO SIGNIFICA `finite(intermediate)`

Este es uno de los bugs más importantes.

Código:

```
`const double yi = y\[i\];`


`if (!std::isfinite(yi))`

`    bad\_value = 1;`


`l\_yy.add(yi \* yi);`
```

Entrada:

```
`yi = 1e308`
```

es finita.

Pero:

10308×10308=∞10^\{308\}\\times10^\{308\} = \\infty 

Después:

```
`yy = NaN`
```

y:

```
`e\_yy = abs(yy - 1.0)`
```

es:

```
`NaN`
```

Entonces:

```
`if (e\_yy \> tol.point\_norm)`
```

es falso.

Por tanto:

```
`NaN`

`↓`

`comparison false`

`↓`

`SUCCESS`
```

### P0 confirmado

## Parche mínimo obligatorio

```
`inline bool finite\_or\_reject(double x) \{`

`    return std::isfinite(x);`

`\}`


`...`


`const double yy = t\_yy.total();`

`const double yu = t\_yu.total();`

`const double yv = t\_yv.total();`

`const double uu = t\_uu.total();`

`const double vv = t\_vv.total();`

`const double uv = t\_uv.total();`


`if (!std::isfinite(yy) ||`

`    !std::isfinite(yu) ||`

`    !std::isfinite(yv) ||`

`    !std::isfinite(uu) ||`

`    !std::isfinite(vv) ||`

`    !std::isfinite(uv)) \{`

`    return POLYDIM\_ERR\_NAN\_OR\_INF;`

`\}`
```

Y:

```
`const double out\_norm = std::sqrt(t\_oo.total());`


`if (!std::isfinite(out\_norm)) \{`

`    return POLYDIM\_ERR\_NUMERICAL\_INSTABILITY;`

`\}`


`const double out\_err = std::abs(out\_norm - 1.0);`


`if (!std::isfinite(out\_err) ||`

`    !std::isfinite(tol.point\_norm) ||`

`    tol.point\_norm \< 0.0 ||`

`    out\_err \> tol.point\_norm) \{`

`    return POLYDIM\_ERR\_DEGENERATE\_NORM;`

`\}`
```


# BUCLE 11 — LAS TOLERANCIAS SON EN ESTE MOMENTO UNA SUPERFICIE DE ATAQUE

El API permite:

```
`const PolydimTolerances tol =`

`    tol\_in ? \*tol\_in :`

`             polydim\_default\_tolerances(D);`
```

pero no valida:

```
`basis\_ortho`

`point\_norm`

`gram\_ortho`

`pivot\_rel`
```

Podrías pasar:

```
`PolydimTolerances tol\{\};`

`tol.point\_norm = NAN;`

`tol.basis\_ortho = NAN;`

`tol.gram\_ortho = NAN;`

`tol.pivot\_rel = NAN;`
```

y muchas comparaciones dejan de funcionar como gate.

### P0

## Parche

```
`static bool valid\_tol(const PolydimTolerances& t) \{`

`    return`

`        std::isfinite(t.basis\_ortho) &&`

`        std::isfinite(t.point\_norm) &&`

`        std::isfinite(t.gram\_ortho) &&`

`        std::isfinite(t.pivot\_rel) &&`

`        t.basis\_ortho \>= 0.0 &&`

`        t.point\_norm \>= 0.0 &&`

`        t.gram\_ortho \>= 0.0 &&`

`        t.pivot\_rel \>= 0.0;`

`\}`
```

Y al entrar:

```
`if (!valid\_tol(tol))`

`    return POLYDIM\_ERR\_INVALID\_SCALAR;`
```


# BUCLE 12 — NORMAS: HAY QUE DEJAR DE USAR `Σ x²` COMO NÚCLEO UNIVERSAL

Esto aparece varias veces:

```
`sum += x\[i\] \* x\[i\];`
```

El problema es doble:

```
`overflow`

`underflow`
```

La solución SOTA clásica es usar una suma de cuadrados escalada tipo `LASSQ`.

Conceptualmente:

```
`struct ScaledSumSquares \{`

`    double scale = 0.0;`

`    double ssq   = 1.0;`


`    void add(double x) \{`

`        const double ax = std::abs(x);`


`        if (ax == 0.0)`

`            return;`


`        if (scale \< ax) \{`

`            const double r = scale / ax;`

`            ssq = 1.0 + ssq \* r \* r;`

`            scale = ax;`

`        \} else \{`

`            const double r = ax / scale;`

`            ssq += r \* r;`

`        \}`

`    \}`


`    double norm() const \{`

`        return scale == 0.0`

`            ? 0.0`

`            : scale \* std::sqrt(ssq);`

`    \}`

`\};`
```

Esto no sustituye a toda la ingeniería numérica, pero sí elimina una clase enorme de overflow/underflow.


# BUCLE 13 — `reject\_subnormal` ES CÓDIGO MUERTO

La estructura declara:

```
`reject\_subnormal`
```

pero la lógica del kernel no la usa como condición operacional.

Eso crea un problema de contrato:

```
`API dice que existe una política`
```

pero:

```
`implementation doesn't enforce it`
```

## Reparación

O lo eliminas:

```
`struct PolydimTolerances \{`

`    ...`

`\};`
```

o lo haces real:

```
`if (tol.reject\_subnormal && std::fpclassify(x) == FP\_SUBNORMAL)`

`    return POLYDIM\_ERR\_SUBNORMAL;`
```

Y debes especificar quién decide:

```
`CPU strict`

`CPU fast`

`GPU`

`SIMD backend`
```

porque el tratamiento de subnormales depende del estado FP y del backend.


# BUCLE 14 — `set\_fp\_mode()` MODIFICA EL ESTADO DEL CALLER

Si:

```
`POLYDIM\_ENABLE\_FTZ`
```

está activo:

```
`\_MM\_SET\_FLUSH\_ZERO\_MODE(...)`

`\_MM\_SET\_DENORMALS\_ZERO\_MODE(...)`
```

Eso modifica el entorno FP del hilo.

La función no hace:

```
`save`

`set`

`execute`

`restore`
```

### P1

Una biblioteca compartida no debería modificar silenciosamente el entorno numérico del proceso cliente.

## Solución

```
`struct ScopedFpEnv \{`

`\#if defined(POLYDIM\_X86)`

`    unsigned mxcsr;`

`    ScopedFpEnv() : mxcsr(\_mm\_getcsr()) \{`

`        ...`

`    \}`


`    ~ScopedFpEnv() \{`

`        \_mm\_setcsr(mxcsr);`

`    \}`

`\#endif`

`\};`
```

Y mejor:

```
`strict backend`

`fast backend`
```

en vez de cambiar mágicamente el entorno global del consumidor.


# BUCLE 15 — `-ffast-math` NO SE “CERTIFICA” CON UN SELFTEST

El test:

```
`acc.add(1.0);`

`for (...) acc.add(small);`
```

es un buen canario.

Pero no demuestra:

```
`"el binario no usa fast-math"`
```

GCC documenta que `-ffast-math` activa transformaciones que relajan las garantías IEEE y permiten asumir propiedades no válidas en aritmética estricta. 

### Cierre correcto

El build debe rechazar compilaciones incompatibles.

Por ejemplo:

```
`if (POLYDIM\_STRICT\_FP)`

`    add\_compile\_options(`

`        -fno-fast-math`

`        -ffp-contract=off`

`    )`

`endif()`
```

Luego generar metadata:

```
`struct PolydimBuildContract \{`

`    uint32\_t abi\_version;`

`    uint32\_t compiler\_id;`

`    uint32\_t compiler\_version;`

`    uint32\_t strict\_fp;`

`    uint32\_t ftz;`

`    uint32\_t daz;`

`    uint32\_t fma;`

`\};`
```

El selftest es **defensa secundaria**.


# BUCLE 16 — STIEFEL: LA MEMORIA YA NO ES “O(K²)”

El comentario declara algo equivalente a:

```
`workspace O(K²)`
```

pero el código reserva:

```
`std::vector\<double\> G\_proj(`

`    static\_cast\<size\_t\>(D) \* K,`

`    0.0`

`);`
```

La realidad es:

O(DK)O(DK) 

Para:

D=107,K=512D=10^7,\\quad K=512 

tenemos:

107×512×8=40.96 GB10^7\\times512\\times8 = 40.96\\ GB 

solo para `G\_proj`.

Y además:

```
`X ≈ 40.96 GB`

`G ≈ 40.96 GB`

`Y ≈ 40.96 GB`
```

Por tanto:

X+G+Y+Gproj≈163.84 GBX+G+Y+G\_\{proj\} \\approx163.84\\ GB 

antes de otras estructuras.

### P0

El comentario del código no describe el footprint real.


# BUCLE 17 — STIEFEL: SOLUCIÓN MATRIX-FREE

Aquí sí está la evolución SOTA que yo haría.

No materializar:

```
`G\_proj\[D,K\]`
```

Calcular:

S=sym⁡(XTG)S=\\operatorname\{sym\}(X^TG) 

y luego producir cada bloque:

Wi=Gi−XiSW\_i = G\_i-X\_iS 

directamente.

Pseudo-C++:

```
`\#pragma omp parallel for schedule(static)`

`for (int64\_t i = 0; i \< static\_cast\<int64\_t\>(D); ++i) \{`

`    const double\* xi =`

`        X + static\_cast\<size\_t\>(i) \* K;`


`    const double\* gi =`

`        G + static\_cast\<size\_t\>(i) \* K;`


`    double\* yi =`

`        Y\_out + static\_cast\<size\_t\>(i) \* K;`


`    for (uint32\_t c = 0; c \< K; ++c) \{`

`        double w = gi\[c\];`


`        for (uint32\_t q = 0; q \< K; ++q)`

`            w -= xi\[q\] \* Sym\[q \* K + c\];`


`        // Usar w directamente en el bloque Cayley.`

`        ...`

`    \}`

`\}`
```

Así reduces:

```
`extra O(DK)`
```

a:

```
`extra O(K²)`
```

sin almacenar todo `W`.

### Todavía queda el problema fundamental

El algoritmo necesariamente necesita:

```
`X : D×K`

`G : D×K`

`Y : D×K`
```

si los tres son simultáneamente residentes.

Por eso para D=10⁷, K=512, si RAM es insuficiente, la solución real es:

```
`block streaming`

`+`

`NUMA placement`

`+`

`pinned/registered memory where appropriate`

`+`

`possibly out-of-core`
```

No un comentario diciendo “O(K²)”.


# BUCLE 18 — CHOLQR2: “MACHINE PRECISION” NO ES LO MISMO QUE EL CRITERIO ACTUAL

Tu código usa algo parecido a:

```
`tol = eps \* D \* 10;`
```

Con:

D=107D=10^7 

eso es aproximadamente:

2.22×10−82.22\\times10^\{-8\} 

Eso es **órdenes de magnitud mayor que ε de máquina**.

Por tanto:

```
`"machine precision"`
```

es una descripción engañosa del criterio de aceptación.

El algoritmo puede aceptar errores del orden de 10^-8.

### P1

## SOTA

Separar:

```
`floating-point epsilon`
```

de:

```
`algorithmic backward-error bound`
```

y usar un certificado como:

∥XTX−I∥∥I∥≤C u κ(X)p f(D,K)\\frac\{\\|X^TX-I\\|\}\{\\|I\\|\} \\le C\\,u\\,\\kappa(X)^p\\,f(D,K) 

con C,p,fC,p,f explícitos.

Para ortogonalización robusta a gran escala, TSQR/Householder y métodos de comunicación reducida son líneas mucho más defendibles cuando la estabilidad importa; la literatura sobre Householder/TSQR está precisamente motivada por estabilidad y comunicación. 


# BUCLE 19 — CHOLQR2: `schedule(dynamic)` ROMPE REPRODUCIBILIDAD

Aquí:

```
`\#pragma omp for schedule(dynamic)`
```

El orden de suma cambia.

Por tanto:

```
`run \#1`

`run \#2`
```

pueden producir distintos últimos bits.

Eso no significa que el algoritmo sea incorrecto.

Sí significa:

```
`bitwise deterministic`
```

no está garantizado.

Y la reproducibilidad numérica en bibliotecas HPC depende justamente de cosas como número fijo de threads, ISA, rutas de código y controles de FP. Intel documenta estas dependencias en sus condiciones de reproducibilidad. 

## Solución

Modo:

```
`DETERMINISTIC`
```

debe usar:

```
`\#pragma omp for schedule(static)`
```

más árbol de reducción fijo.

Y registrar:

```
`CPU model`

`ISA`

`compiler`

`compiler flags`

`OpenMP runtime`

`thread count`

`BLAS version`

`FP control state`
```


# BUCLE 20 — STIEFEL CAYLEY: FALTA CERTIFICAR EL RESIDUAL DEL SOLVER

Este es un salto importante.

El código comprueba:

```
`YᵀY ≈ I`
```

pero no comprueba directamente:

```
`M Z = B`
```

Después de:

```
`dgesv\_`
```

o de tu eliminación manual.

Eso significa:

```
`solution residual`
```

no forma parte del certificado.

## Debe agregarse

```
`double residual\_inf(`

`    const double\* M,`

`    const double\* Z,`

`    const double\* B,`

`    uint32\_t n,`

`    uint32\_t k)`

`\{`

`    double worst = 0.0;`


`    for (uint32\_t r = 0; r \< n; ++r) \{`

`        for (uint32\_t c = 0; c \< k; ++c) \{`

`            double s = 0.0;`


`            for (uint32\_t q = 0; q \< n; ++q)`

`                s += M\[r\*n + q\] \* Z\[q\*k + c\];`


`            worst = std::max(`

`                worst,`

`                std::abs(s - B\[r\*k + c\])`

`            );`

`        \}`

`    \}`


`    return worst;`

`\}`
```

Y el certificado debe contener:

```
`finite = true`

`input\_gram\_residual`

`solver\_residual`

`output\_gram\_residual`

`pivot\_min`

`condition\_estimate`
```

No solo:

```
`ortho\_err`
```


# BUCLE 21 — TANGENT ADAPTER: NO ES UNA BIYECCIÓN DE TODO Rᴰ

La documentación afirma:

h∈RD↔(u,r)h\\in R^D \\leftrightarrow (u,r) 

pero el código especial-casa:

```
`if norm\_h \< self.eps:`

`    u\[0\] = 1.0`

`    r = -100.0`
```

Entonces:

```
`h = 0`

`h = 1e-18 e1`

`h = 1e-19 e2`
```

pueden colapsar al mismo estado representacional.

Eso **no es una biyección**.

### Solución matemática correcta

El dominio natural es:

RD∖\{0\}≅SD−1×R\\mathbb R^D\\setminus\\\{0\\\} \\cong S^\{D-1\}\\times\\mathbb R 

y el cero tiene que ser un caso etiquetado:

```
`from dataclasses import dataclass`

`from typing import Literal`


`@dataclass(frozen=True)`

`class ZeroCode:`

`    tag: Literal\["ZERO"\] = "ZERO"`


`@dataclass(frozen=True)`

`class NonZeroCode:`

`    u: np.ndarray`

`    r: float`
```

Encoder:

```
`def encode(h):`

`    n = stable\_norm(h)`


`    if n == 0.0:`

`        return ZeroCode()`


`    u = h / n`

`    r = math.log(n)`


`    return NonZeroCode(u=u, r=r)`
```

Decoder:

```
`def decode(code):`

`    if isinstance(code, ZeroCode):`

`        return np.zeros(self.dim, dtype=np.float64)`


`    return stable\_exp(code.r) \* code.u`
```

Eso sí define:

```
`ZERO`

`NONZERO(u,r)`
```

sin inventar una pseudoinversa cerca de cero.


# BUCLE 22 — ADAPTER: `exp(r)` PUEDE SER `INF`

Actualmente:

```
`mag = np.exp(r)`
```

Para:

r\>709r\>709 

FP64 entra en overflow.

Entonces:

```
`u = finite`

`r = 1000`
```

produce:

```
`mag = inf`
```

y el vector termina:

```
`\[inf, nan, nan, ...\]`
```

## Cierre industrial

Tienes dos opciones legítimas.

### Opción A — dominio explícito

```
`LOG\_MAX = math.log(np.finfo(np.float64).max)`


`if r \> LOG\_MAX:`

`    raise OverflowError("log-magnitude outside FP64 range")`
```

### Opción B — representación escalada

Guardar:

```
`mantissa`

`+`

`binary exponent`
```

por ejemplo:

h=m2euh = m2^e u 

con:

```
`m ∈ \[1/2, 1)`

`e ∈ Z`
```

Eso es mucho más robusto si realmente quieres representar el rango dinámico completo de un sistema latente.


# BUCLE 23 — ADAPTER: EL TEST FALLA POR UNA RAZÓN MATEMÁTICA, NO POR “MALA SUERTE”

La suite usa:

```
`assert ortho\_check \<= 2e-15`
```

en:

```
`D=100000`
```

y observamos:

```
`ortho = 4.00e-15`
```

### P0 de certificación

La propia suite falla.

No hay que “aflojar a 5e-15” y terminar.

Primero hay que decidir:

```
`¿Qué bound matemático queremos?`
```

Para:

v⊥=v−⟨u,v⟩uv\_\\perp=v-\\langle u,v\\rangle u 

el residual final depende de:

- error de norma de u, 

- error del dot, 

- error del producto escalar-vector, 

- orden de reducción, 

- D. 

El contrato debe tener un bound derivado.

## Mejor

Usar:

```
`inner = deterministic\_dot(u, v)`

`v\_tan = v - inner \* u`

`residual = abs(deterministic\_dot(u, v\_tan))`
```

y certificar:

```
`bound = derived\_bound(dim, norm\_u, norm\_v)`
```

en lugar de inventar:

```
`2e-15`
```


# BUCLE 24 — ADAPTER: TRANSPORTE PARALELO NO PUEDE TRATAR ANTIPODALES COMO CASO NORMAL

El código hace:

```
`w = u2 - inner \* u1`

`norm\_w = np.linalg.norm(w)`


`if norm\_w \< self.eps:`

`    return v\_tan1.copy()`
```

Cerca de:

u2=−u1u\_2=-u\_1 

tenemos:

sin⁡θ→0\\sin\\theta \\rightarrow 0 

y la dirección geodésica se vuelve indefinida.

Además:

```
`copiar v\_tan1`
```

no garantiza:

u2Tv2=0u\_2^Tv\_2=0 

### Solución

Definir contrato:

```
`if dot \< -1 + antipodal\_tol:`

`    raise AntipodalGeodesicUndefined()`
```

o elegir una dirección canónica reproducible.

Yo prefiero:

```
`antipodal`

`→ canonical great-circle choice`

`→ exact transport`
```

solo si la aplicación necesita necesariamente continuidad allí.


# BUCLE 25 — LSM: `O(1) UPDATE` ESTÁ MAL NOMBRADO

Hay dos implementaciones.

Standalone:

```
`nnz = int(dim \* sparsity)`


`self.sparse\_indices = \[`

`    np.random.choice(...)`

`    for \_ in range(dim)`

`\]`
```

Eso produce:

nnz=O(D)nnz=O(D) 

por fila.

Total:

O(D2)O(D^2) 

Con:

```
`D=10^7`

`sparsity=.05`
```

≈

5×10125\\times10^\{12\} 

pesos.

No hay forma razonable de alojarlo.

### Además

La versión “arreglada” usa:

```
`nnz = 16`
```

pero:

```
`self.indices = \[array(...) for i in range(dim)\]`

`self.weights = \[array(...) for i in range(dim)\]`
```

significa millones de objetos Python.

### SOTA

Usaría memoria contigua:

```
`indices = np.empty((dim, k), dtype=np.int32)`

`weights = np.empty((dim, k), dtype=np.float64)`
```

pero aun así:

16⋅107⋅(4+8)=19.2 GB16\\cdot10^7\\cdot(4+8) = 19.2\\ GB 

solo índices + pesos.

Para D=10^7 eso ya es significativo.

Más SOTA todavía:

```
`structured orthogonal operator`
```

que no necesita almacenar D×K relaciones arbitrarias.

Ejemplo conceptual:

```
`x`

` ↓`

`permutation`

` ↓`

`sign flips`

` ↓`

`block Givens`

` ↓`

`permutation`

` ↓`

`block Givens`
```

con coste:

O(Dk)O(Dk) 

y parámetros mucho más compactos.


# BUCLE 26 — LSM: NORMALIZAR FILAS ≠ ORTOGONALIZAR LA MATRIZ

Código:

```
`self.sparse\_weights\[i\] /= norm\_w`
```

eso solo asegura:

∥wi∥2=1\\|w\_i\\|\_2=1 

No:

WTW=IW^TW=I 

Ni:

ρ(W)=1\\rho(W)=1 

Por tanto:

```
`"exact spectral radius scaling"`
```

no está implementado.

### Solución

Si necesitas una matriz realmente ortogonal:

```
`W = product(structured\_orthogonal\_blocks)`
```

Si necesitas ESP:

no apuntes a:

ρ(W)=1\\rho(W)=1 

por definición.

Necesitas una condición de contracción del operador completo.

Para:

F(x)=normalize⁡((1−α)x+αtanh⁡(Wx+u))F(x)=\\operatorname\{normalize\} ((1-\\alpha)x+\\alpha\\tanh(Wx+u)) 

la estabilidad depende también de la derivada de:

```
`tanh`

`+`

`leak`

`+`

`normalization`
```

No solo de:

```
`rho(W)`
```


# BUCLE 27 — LSM: UN `NaN` PUEDE TERMINAR EN UN “ESTADO UNITARIO”

Código:

```
`norm\_new = np.linalg.norm(new\_state)`


`if norm\_new \> self.eps:`

`    ...`

`else:`

`    self.state = np.zeros(self.dim)`

`    self.state\[0\] = 1.0`
```

Si:

```
`norm\_new = NaN`
```

entonces:

```
`NaN \> eps`
```

es falso.

Por tanto:

```
`NaN`

`↓`

`reset`

`↓`

`e1`
```

El sistema acaba con:

```
`norm(state) = 1`
```

y un observador puede interpretar:

```
`"manifold invariant"`
```

cuando en realidad hubo corrupción numérica y pérdida total de información.

### Solución

```
`if not np.isfinite(norm\_new):`

`    raise FloatingPointError(`

`        "LSM state became non-finite"`

`    )`


`if norm\_new == 0.0:`

`    raise FloatingPointError(`

`        "LSM state collapsed to zero"`

`    )`
```

Jamás reemplazar NaN por un estado válido y llamarlo recuperación.


# BUCLE 28 — TRITON: D=10⁷ CAE EN FALLBACK CPU

Con:

```
`BLOCK=1024`

`D=10^7`
```

tienes aproximadamente:

97669766 

partial blocks.

Siguiente potencia de dos:

1638416384 

pero el código exige:

```
`block\_reduce \<= 4096`
```

Por tanto entra al fallback.

Y ese fallback hace:

```
`.item()`
```

Eso fuerza sincronización GPU→CPU.

Por lo tanto la afirmación:

```
`"sincronización eliminada"`
```

no se cumple en D=10⁷.

## SOTA

Reducción jerárquica:

```
`D`

` ↓`

`block reduction`

` ↓`

`warp/block partials`

` ↓`

`second kernel`

` ↓`

`small reduction`
```

Y no:

```
`partial.sum().item()`
```

hasta el momento exacto donde el API necesita un scalar CPU.


# BUCLE 29 — TRITON: EL FALLBACK NI SIQUIERA CONSERVA TODOS LOS INVARIANTES

El fallback suma:

```
`yu`

`yv`
```

pero no:

```
`uu`

`vv`

`uv`
```

Así que bajo ciertas dimensiones la ruta CPU deja de verificar:

∥u∥,∥v∥,⟨u,v⟩\\|u\\|,\\|v\\|,\\langle u,v\\rangle 

El mismo algoritmo tiene entonces **dos contratos numéricos diferentes** dependiendo de D.

Eso hay que eliminar.


# BUCLE 30 — TRITON: `stream` NO ES UN ARGUMENTO DECORATIVO

La API declara:

```
`stream=...`
```

pero la implementación no demuestra que el kernel esté realmente asociado al stream solicitado.

En sistemas GPU de producción, eso es peligroso porque:

```
`stream A`

`stream B`
```

pueden terminar con dependencias implícitas no controladas.

## Contrato correcto

El backend debe aceptar:

```
`stream: torch.cuda.Stream`
```

y ejecutar explícitamente en ese contexto:

```
`with torch.cuda.stream(stream):`

`    kernel\[grid\](...)`
```

o el equivalente correcto para la integración usada.


# BUCLE 31 — MIR-WIRE: NO ES RDMA

El código usa:

```
`socket.socket(`

`    socket.AF\_INET,`

`    socket.SOCK\_STREAM`

`)`
```

y:

```
`sock.sendall(...)`
```

Eso es TCP.

El propio comentario lo llama:

```
`WRITE-WITH-IMMEDIATE EMULATOR`
```

No lo voy a llamar “falso”: **es un emulador TCP de una semántica RDMA-like**.

Eso está bien si se nombra correctamente.

Pero no puede aparecer como:

```
`RDMA benchmark`
```

El RDMA real usa verbs y operaciones como `IBV\_WR\_RDMA\_WRITE\_WITH\_IMM`. La API de verbs especifica que esa operación escribe en memoria remota y genera un completion con immediate data. 

### Arquitectura correcta

```
`MIRWire`

` ├── TCPBackend`

` ├── RDMAVerbsBackend`

` └── LoopbackBackend`
```

No:

```
`MIR-Wire RDMA`

`    ↓`

`socket TCP`
```


# BUCLE 32 — MIR-WIRE: `recv()` NO ES `read\_exact()`

Código:

```
`raw\_header = conn.recv(header\_size)`
```

TCP garantiza orden, **no frontera de mensajes**.

Puede devolver:

```
`3 bytes`
```

cuando pediste:

```
`32 bytes`
```

Y:

```
`ack = sock.recv(3)`
```

tiene el mismo problema.

## Parche

```
`def recv\_exact(sock, size: int) -\> bytes:`

`    chunks = \[\]`

`    received = 0`


`    while received \< size:`

`        chunk = sock.recv(size - received)`


`        if not chunk:`

`            raise ConnectionError(`

`                "peer closed before frame completed"`

`            )`


`        chunks.append(chunk)`

`        received += len(chunk)`


`    return b"".join(chunks)`
```

Después:

```
`raw\_header = recv\_exact(conn, HEADER\_SIZE)`
```

y:

```
`payload = recv\_exact(conn, tensor\_bytes)`
```


# BUCLE 33 — MIR-WIRE: EL PEER CONTROLA TU MEMORIA

Actualmente:

```
`tensor\_bytes = ...`

`tensor\_buf = bytearray(tensor\_bytes)`
```

Un peer puede anunciar:

```
`tensor\_bytes = enorme`
```

antes de que se valide.

### P0

## Parche

```
`MAX\_TENSOR\_BYTES = 256 \* 1024 \* 1024`


`if tensor\_bytes \<= 0:`

`    raise ValueError("invalid tensor length")`


`if tensor\_bytes \> MAX\_TENSOR\_BYTES:`

`    raise ValueError("tensor too large")`


`if tensor\_bytes % 8 != 0:`

`    raise ValueError("unaligned FP64 payload")`
```

Y luego:

```
`tensor = np.frombuffer(`

`    memoryview(payload),`

`    dtype="\<f8"`

`)`
```


# BUCLE 34 — MIR-WIRE: EL “ZERO COPY” TIENE COPIAS

El receiver hace:

```
`bytearray(tensor\_bytes)`
```

y el protocolo TCP implica además recorrido por buffers del kernel.

Por tanto:

```
`Zero-copy`
```

no describe el camino mostrado.

Una ruta verdadera RDMA tendría que registrar memoria y usar operaciones de RDMA; `RDMA\_WRITE\_WITH\_IMM` es precisamente una operación definida por verbs para escribir en memoria remota con immediate data. 


# BUCLE 35 — RUST: `from\_raw\_parts()` NO ES UN CHECK DE SEGURIDAD

El código hace:

```
`let slice = slice::from\_raw\_parts(ptr, d);`
```

Después de comprobar:

```
`ptr != null`

`alignment == 8`
```

Eso no alcanza.

Rust documenta que la creación del slice requiere condiciones mucho más fuertes: puntero válido, alineado, memoria suficiente, dentro de una única región de asignación, etc. 

### El problema

La API no recibe:

```
`capacity`

`allocation length`

`lifetime`

`ownership`
```

Por tanto Rust no tiene manera de comprobar:

```
`d × sizeof(f64) \<= allocation`
```

## Diseño correcto

```
`\#\[repr(C)\]`

`pub struct PolydimBufferF64 \{`

`    pub ptr: \*const f64,`

`    pub len: usize,`

`    pub capacity: usize,`

`\}`
```

y antes:

```
`if buffer.ptr.is\_null() \{`

`    return ERR\_NULL\_POINTER;`

`\}`


`if buffer.len \> buffer.capacity \{`

`    return ERR\_BUFFER\_OVERFLOW;`

`\}`


`let bytes = match buffer.len.checked\_mul(`

`    std::mem::size\_of::\<f64\>()`

`) \{`

`    Some(v) =\> v,`

`    None =\> return ERR\_BUFFER\_OVERFLOW,`

`\};`


`if bytes \> isize::MAX as usize \{`

`    return ERR\_BUFFER\_OVERFLOW;`

`\}`
```

Solo entonces construir el slice.


# BUCLE 36 — `catch\_unwind` NO ATRAPA UB

Este punto lo quiero muy claro.

```
`catch\_unwind(...)`
```

sirve para:

```
`panic`
```

No para:

```
`segmentation fault`

`invalid pointer`

`data race`

`UB`
```

Así que:

```
`catch\_unwind`
```

no es una “membrane de memoria segura”.

Es una **membrane de panic safety**.


# BUCLE 37 — RUST β₁: EL NOMBRE SOBREPASA LA IMPLEMENTACIÓN

El comentario declara:

```
`Betti-1`
```

pero el código acaba haciendo esencialmente:

```
`if components \> 1 \{`

`    return ErrTopologyFragmented;`

`\}`
```

No calcula:

```
`beta1 = edges - vertices + components`
```

como un valor a verificar.

Por tanto el guard realmente demuestra:

```
`β0 = 1`
```

en el caso aceptado.

No:

```
`β1 = expected`
```

### Reparación

```
`let beta1 =`

`    edges`

`        .checked\_sub(n)`

`        .and\_then(|x| x.checked\_add(components))`

`        .ok\_or(PolydimRustStatus::ErrBufferOverflow)?;`
```

Después debe existir una política:

```
`if beta1 != expected\_beta1 \{`

`    return ErrTopologyViolation;`

`\}`
```

o:

```
`if beta1 \> max\_beta1 \{`

`    return ErrTopologyViolation;`

`\}`
```

La matemática concreta depende de qué complejo topológico se está modelando.


# BUCLE 38 — C++ `overlaps()` TAMBIÉN TIENE QUE SER ENDURECIDO

Actualmente:

```
`auto pa = static\_cast\<const char\*\>(a);`

`auto pb = static\_cast\<const char\*\>(b);`


`return`

`    (pa \< pb + bytes) &&`

`    (pb \< pa + bytes);`
```

El problema es que estás haciendo pointer arithmetic con longitudes suministradas desde un ABI.

Para una librería que pretende absorber entradas hostiles, es mejor operar con:

```
`uintptr\_t`
```

y aritmética comprobada.

```
`static bool checked\_end(`

`    const void\* p,`

`    size\_t len,`

`    uintptr\_t& end)`

`\{`

`    const uintptr\_t start =`

`        reinterpret\_cast\<uintptr\_t\>(p);`


`    if (len \> UINTPTR\_MAX - start)`

`        return false;`


`    end = start + len;`

`    return true;`

`\}`
```

Entonces:

```
`static bool ranges\_overlap(`

`    const void\* a,`

`    size\_t a\_len,`

`    const void\* b,`

`    size\_t b\_len)`

`\{`

`    uintptr\_t a0, a1, b0, b1;`


`    if (!checked\_end(a, a\_len, a1) ||`

`        !checked\_end(b, b\_len, b1))`

`        return true; // fail closed`


`    a0 = reinterpret\_cast\<uintptr\_t\>(a);`

`    b0 = reinterpret\_cast\<uintptr\_t\>(b);`


`    return a0 \< b1 && b0 \< a1;`

`\}`
```


# BUCLE 39 — `\_\_restrict\_\_` Y ALIASING: EL CAMBIO F-03 NO CERRÓ TODO

Quitaste `\_\_restrict\_\_` de:

```
`y`

`y\_out`
```

pero quedan rutas donde sigue apareciendo:

```
`const double\* \_\_restrict\_\_ X`

`const double\* \_\_restrict\_\_ G`

`double\* \_\_restrict\_\_ Y\_out`
```

y:

```
`double\* \_\_restrict\_\_ u`

`double\* \_\_restrict\_\_ v`
```

Por eso:

```
`X == Y\_out`

`G == Y\_out`

`u == v`

`partial overlap`
```

no son todos equivalentes.

### Cierre

Define en cada API:

```
`ALIAS\_POLICY`
```

Ejemplo:

```
`POLYDIM\_ALIAS\_NONE`

`POLYDIM\_ALIAS\_EXACT\_INPLACE`

`POLYDIM\_ALIAS\_ARBITRARY`
```

y haz que la función compruebe esa política.

No dejes que el compilador tenga que adivinar el contrato.


# BUCLE 40 — QUANTUM: EL PROBLEMA NO ES SOTA/NO-SOTA; ES QUE LA TRANSFORMACIÓN NO ES LA DECLARADA

Hay tres capas mezcladas:

```
`SO(D)`

`↓`

`qubit representation`

`↓`

`Clifford+T synthesis`
```

El código actual hace cosas como:

```
`q1 = p1 % num\_qubits`

`q2 = p2 % num\_qubits`
```

Eso significa que muchas coordenadas diferentes de:

RDR^D 

terminan en el mismo qubit.

No es un embedding:

RD→C2nR^D\\rightarrow C^\{2^n\} 

bien definido.

Además aparece:

```
`ry(theta)`
```

y luego una aproximación que no depende realmente de `theta` residual.

Por tanto no se puede certificar:

∥U−Usynth∥≤ϵ\\|U-U\_\{\\text\{synth\}\}\\|\\le\\epsilon 

### Cierre SOTA

Primero:

n=⌈log⁡2D⌉n=\\lceil \\log\_2 D\\rceil 

Luego definir:

E:RD→C2nE:\\mathbb R^D\\rightarrow\\mathbb C^\{2^n\} 

con padding explícito.

Después sintetizar la transformación con una implementación real de:

```
`Givens`

`→ multiplexed basis rotation`

`→ Clifford+T approximation`
```

Y el resultado debe traer:

```
`@dataclass`

`class SynthesisCertificate:`

`    target\_error: float`

`    certified\_error: float`

`    t\_count: int`

`    cx\_count: int`

`    qubits: int`
```

No basta producir un `.qasm`.


# BUCLE 41 — OMNI ROUTER: “EJECUTAR” NO EJECUTA

La función:

```
`Future\<void\> executePCOperation(String command) async \{`
```

hace:

```
`dispatchHumanMessage(...)`
```

No:

```
`Process.start`
```

ni CDP real.

Por tanto:

```
`executePCOperation`
```

es un **event dispatcher**, no un executor.

### P1

Solución:

```
`abstract interface class PcExecutor \{`

`  Future\<int\> execute(String command);`

`\}`


`final class ProcessPcExecutor implements PcExecutor \{`

`  @override`

`  Future\<int\> execute(String command) async \{`

`    final result = await Process.run(`

`      Platform.isWindows ? 'cmd' : '/bin/sh',`

`      Platform.isWindows`

`          ? \['/c', command\]`

`          : \['-lc', command\],`

`    );`


`    return result.exitCode;`

`  \}`

`\}`
```

Luego el router puede publicar:

```
`requested`

`started`

`stdout`

`stderr`

`completed`

`failed`
```

Eso sí es un sistema observable.


# BUCLE 42 — IDs DE EVENTOS PUEDEN COLISIONAR

Actualmente:

```
`"evt\_$\{DateTime.now().millisecondsSinceEpoch\}"`
```

Dos eventos dentro del mismo milisegundo:

```
`evt\_123`

`evt\_123`
```

### Solución

UUID/ULID o contador monotónico combinado:

```
`final eventId =`

`    '$\{DateTime.now().microsecondsSinceEpoch\}-$\{\_counter++\}';`
```

Para sistemas distribuidos:

```
`node\_id`

`+`

`monotonic counter`

`+`

`timestamp`
```


# BUCLE 43 — EL MONOLITO ES UNA SUPERFICIE DE DERIVA

Esto es estructural.

Tienes:

```
`kernel\_cpp\_v768`

`adapter`

`LSM`

`MIR`

`quantum`

`Dart`

`Rust`
```

y además otro:

```
`monolithic suite`
```

con duplicaciones.

Ya vimos el resultado:

```
`V768`

`V762`

`V764`

`V761`
```

coexistiendo dentro del mismo paquete.

### P1

La versión de documentación y la versión de ABI pueden separarse.

## Solución

Un único:

```
`POLYDIM\_VERSION = 768`

`POLYDIM\_ABI = 4`

`POLYDIM\_SCHEMA = 12`
```

generado para:

```
`C++`

`Rust`

`Python`

`Dart`

`Triton`
```

Una única fuente.


# BUCLE 44 — NO HAY CONTRATO DE REPRODUCIBILIDAD DE BUILD

En la entrega no aparece un build reproducible completo:

```
`compiler`

`compiler version`

`flags`

`OpenMP runtime`

`BLAS version`

`Python environment`

`Triton version`

`Rust toolchain`

`Dart SDK`

`CPU ISA`
```

Entonces:

```
`"same source"`
```

no implica:

```
`"same binary"`
```

ni:

```
`"same floating-point behavior"`
```

## Cierre

Crear:

```
`toolchain.lock`

`environment.lock`

`build-manifest.json`

`SBOM`
```

y embed:

```
`const char\* polydim\_build\_manifest();`
```


# BUCLE 45 — FALTA LA PRUEBA QUE MÁS IMPORTA: CROSS-MATRIX

No alcanza con:

```
`machine A`
```

La matriz industrial debe ser:

```
`                 strict FP    fast FP`

`x86 AVX2            ✓            ✓`

`x86 AVX-512         ✓            ✓`

`ARM NEON/SVE        ✓            ✓`

`GPU                 ✓            ✓`
```

y:

```
`1 thread`

`2`

`4`

`8`

`16`

`...`
```

para el backend deterministic.

Además:

```
`GCC`

`Clang`

`MSVC`
```

cuando aplique.

Y comparar contra una referencia:

```
`scalar deterministic FP64`
```


# BUCLE 46 — PROPIEDADES METAMÓRFICAS QUE FALTAN

Para cerrar matemáticamente el sistema no basta testear ejemplos.

### Rodrigues

Debe verificarse:

R−θ(Rθ(y))≈yR\_\{-\\theta\}(R\_\\theta(y))\\approx y 

### Esfera

normalize(cy)≈normalize(y)normalize(cy)\\approx normalize(y) 

para:

c\>0c\>0 

### Stiefel

∥YTY−I∥\\|Y^TY-I\\| 

más residual del solver.

### Transporte

∥v1∥≈∥T(v1)∥\\|v\_1\\|\\approx\\|T(v\_1)\\| 

y:

u2TT(v1)≈0u\_2^T T(v\_1)\\approx0 

### Adapter

decode(encode(h))≈hdecode(encode(h))\\approx h 

para una malla de:

```
`zero`

`subnormal`

`small`

`normal`

`large`

`near-overflow`
```

### PMTP

```
`write → read → validate`
```

con:

```
`kill writer`

`kill reader`

`restart process`

`stale segment`

`generation wrap`

`partial header`

`corrupt magic`

`wrong payload length`
```


# BUCLE 47 — EL “SOTA” DE VERDAD NO ES HACERLO MÁS COMPLEJO

Aquí está mi recomendación arquitectónica principal.

No intentaría cerrar POLYDIM agregando veinte capas más.

Lo cerraría reduciendo el sistema a **cinco contratos duros**.

## Contrato 1 — Memory

```
`ptr`

`len`

`capacity`

`alignment`

`ownership`

`lifetime`

`alias policy`
```

Sin esto no entra ningún FFI.

## Contrato 2 — Numeric

```
`finite inputs`

`finite intermediates`

`finite outputs`

`scaled norms`

`explicit tolerance model`

`strict/fast modes`

`deterministic reduction`
```

## Contrato 3 — Geometry

```
`domain`

`manifold`

`preconditions`

`postconditions`

`residual`

`conditioning`

`singular cases`
```

## Contrato 4 — IPC

```
`header`

`version`

`generation`

`ownership`

`wait/recovery`

`payload`

`integrity`

`backpressure`
```

## Contrato 5 — Certification

```
`reference implementation`

`optimized implementation`

`differential test`

`fuzz`

`sanitizers`

`stress`

`cross-compiler`

`cross-hardware`
```


# LA REFORMA QUE YO HARÍA ANTES DE OTRA RONDA

No haría otro parche aislado.

Haría este núcleo.

## 1. ABI único

```
`\#pragma once`

`\#include \<stdint.h\>`

`\#include \<stddef.h\>`


`\#define POLYDIM\_ABI\_VERSION 4u`


`typedef struct \{`

`    uint32\_t abi\_version;`

`    uint32\_t struct\_size;`

`\} PolydimAbiHeader;`


`typedef struct \{`

`    PolydimAbiHeader abi;`

`    uint32\_t flags;`

`    uint32\_t reserved;`

`    uint64\_t len;`

`    uint64\_t capacity;`

`    void\* ptr;`

`\} PolydimBuffer;`


`typedef struct \{`

`    double basis\_ortho;`

`    double point\_norm;`

`    double gram\_ortho;`

`    double pivot\_rel;`

`    int32\_t reject\_subnormal;`

`    int32\_t reserved;`

`\} PolydimTolerances;`
```

## 2. Checked arithmetic

```
`static bool checked\_mul(`

`    size\_t a,`

`    size\_t b,`

`    size\_t\* out)`

`\{`

`    if (!out)`

`        return false;`


`    if (a != 0 && b \> SIZE\_MAX / a)`

`        return false;`


`    \*out = a \* b;`

`    return true;`

`\}`


`static bool checked\_add(`

`    size\_t a,`

`    size\_t b,`

`    size\_t\* out)`

`\{`

`    if (!out)`

`        return false;`


`    if (b \> SIZE\_MAX - a)`

`        return false;`


`    \*out = a + b;`

`    return true;`

`\}`
```

## 3. Tol strict

```
`static bool valid\_tolerances(`

`    const PolydimTolerances& t)`

`\{`

`    return`

`        std::isfinite(t.basis\_ortho) &&`

`        std::isfinite(t.point\_norm) &&`

`        std::isfinite(t.gram\_ortho) &&`

`        std::isfinite(t.pivot\_rel) &&`

`        t.basis\_ortho \>= 0.0 &&`

`        t.point\_norm \>= 0.0 &&`

`        t.gram\_ortho \>= 0.0 &&`

`        t.pivot\_rel \>= 0.0;`

`\}`
```

## 4. Certificado numérico

```
`typedef struct \{`

`    uint32\_t valid;`

`    uint32\_t reserved;`


`    double input\_residual;`

`    double solver\_residual;`

`    double output\_residual;`


`    double min\_pivot;`

`    double condition\_estimate;`


`    uint64\_t elements\_processed;`

`    uint64\_t threads\_used;`

`\} PolydimCertificate;`
```

## 5. PMTP no vuelve a usar `std::atomic` como layout persistente

```
`enum \{`

`    PMTP\_FREE    = 0,`

`    PMTP\_WRITING = 1,`

`    PMTP\_READY   = 2,`

`    PMTP\_READING = 3`

`\};`


`typedef struct \{`

`    uint64\_t generation;`

`    uint32\_t state;`

`    uint32\_t readers;`

`    uint8\_t reserved\[48\];`

`\} PmtpSlotMeta;`
```

Sincronización separada.

## 6. Reader lease

```
`FREE`

` → WRITING`

` → READY`

` → READING`

` → FREE`
```

## 7. Stiefel matrix-free

Eliminar:

```
`std::vector\<double\> G\_proj(D \* K);`
```

por procesamiento por bloques.

## 8. Normas escaladas

No más:

```
`sum += x\*x;`
```

como implementación general.

## 9. Adapter con `ZERO`

No más:

```
`r = -100`
```

para representar cero.

## 10. LSM estructurado

No más:

```
`list\[np.ndarray\] × D`
```

para D=10^7.

## 11. MIR

Dos backend explícitos:

```
`TCP`

`RDMA`
```

## 12. Tests

Nada de:

```
`assert`
```

como gate.


# Y AQUÍ ESTÁ EL PUNTO QUE CAMBIA TODO EL PROYECTO

No deberíamos volver a usar como objetivo:

> “que todos los tests pasen”.

El objetivo industrial debe ser:

Cada operacioˊn tiene un contrato matemaˊtico+un contrato de memoria+un contrato de concurrencia+un certificado verificable\\boxed\{ \\text\{Cada operación tiene un contrato matemático\} + \\text\{un contrato de memoria\} + \\text\{un contrato de concurrencia\} + \\text\{un certificado verificable\} \} 

Por ejemplo, Rodrigues no queda “cerrado” porque:

```
`norm ≈ 1`
```

Queda cerrado solo si simultáneamente:

inputs finitebasis orthonormaly∈SD−1R∈SO(D) o contrato equivalentesolver/residual dentro del boundoutput finite∥yout∥−1≤B(D,u)aliaspolicy cumplidamemory bounds cumplidos\\begin\{aligned\} &inputs\\ finite\\\\ &basis\\ orthonormal\\\\ &y\\in S^\{D-1\}\\\\ &R\\in SO(D)\\ \\text\{o contrato equivalente\}\\\\ &solver/residual\\ dentro\\ del\\ bound\\\\ &output\\ finite\\\\ &\\|y\_\{out\}\\|-1\\le B(D,u)\\\\ &alias policy\\ cumplida\\\\ &memory\\ bounds\\ cumplidos \\end\{aligned\} 

Y PMTP no queda cerrado porque:

```
`seq == expected`
```

sino porque:

ownership+generation+visibility+lifetime+recovery\\boxed\{ ownership + generation + visibility + lifetime + recovery \} 

están todos definidos.


# QUÉ HALLAZGOS CONFIRMO COMO NO-ALUCINADOS

Los siguientes tienen evidencia especialmente fuerte en esta ronda:

**Confirmados por ejecución / instrumentación:**

```
`P0  NaN/Inf → SUCCESS en kernels numéricos`

`P0  PMTP data race sobre payload`

`P0  PMTP undersized buffer → ASan overflow`

`P0  writer muerto → lock hang`

`P0  adapter D=100000 → assertion failure`

`P0  adapter python -O → falsa certificación`

`P0  Linux monolith → dependencia polydim.dll`

`P0  PMTP test no toca payload PMTP real`
```

**Confirmados directamente por inspección del código:**

```
`P0  ABI Dart/C++ incompatible`

`P0  símbolos Dart/C++ distintos`

`P0  PMTPControl Dart ≠ PMTPControl C++`

`P0  LSM standalone O(D²)`

`P0  G\_proj = O(DK)`

`P0  recv() usado como framing TCP`

`P0  payload size controlado por peer`

`P0  Rust from\_raw\_parts sin capacity contract`

`P0  β1 no calculado realmente`

`P0  Quantum mapping % qubits no representa SO(D)`

`P0  continuous ry dentro de supuesto Clifford+T`
```

**No los presento como bugs confirmados, sino como claims no demostrados:**

```
`"ABA imposible"`

`"RDMA"`

`"zero-copy"`

`"machine precision"`

`"100% zero-loss"`

`"β1 certified"`

`"rho(W)=1"`

`"exact spectral radius scaling"`
```

Ese matiz es importante. **No voy a convertir “no demostrado” en “falso”.**


# SIGUIENTE BUCLE: EL QUE TODAVÍA FALTA

Todavía no daría por terminado el red team.

El siguiente ataque, y probablemente el más importante de todos, es:

## **auditar exhaustivamente el modelo matemático de Stiefel/Cayley-SMW contra su implementación línea por línea**

No porque ya haya demostrado que la fórmula central sea incorrecta —de hecho, las comprobaciones pequeñas que hicimos son compatibles con la fórmula— sino porque ahora hay que demostrar:

la implementacioˊn calcula exactamente el operador declarado\\boxed\{ \\text\{la implementación calcula exactamente el operador declarado\} \} 

bajo:

```
`K=1`

`K=2`

`K=512`

`D≈K`

`D≫K`

`tau→0`

`tau grande`

`G tangente`

`G no tangente`

`X bien condicionado`

`X mal condicionado`

`NaN`

`Inf`

`subnormal`

`near-singular M`

`BLAS`

`non-BLAS`

`1 thread`

`N threads`
```

Y simultáneamente voy a atacar:

```
`pivoting`

`conditioning`

`residual`

`determinism`

`BLAS ABI`

`column-major/row-major`

`LAPACK dgesv`

`FMA`

`denormal`

`NUMA`

`cache topology`

`AVX2/AVX512`

`ARM/SVE`
```

Ese es el punto donde pasamos de:

> “el código parece matemáticamente razonable”

a:

> **“el operador, el solver, la memoria y el hardware tienen un contrato que puede sobrevivir a producción.”**

Y en esta ronda **no voy a volver a recortarlo a diez items**. El criterio de cierre pasa a ser el contrato completo, no el número de errores encontrados.











