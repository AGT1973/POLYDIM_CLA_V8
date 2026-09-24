

auditoria\_externa.zip

Archivo Zip

lee profundamente, evalua errores, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. No te apresures. gasta tu tiempo. prefiero lento y chequeado que rapido y mal. no quiero alucinaciones 🚨 THE BULLDOG RED TEAM MANDATE: PROTECT THE ARCHITECT THROUGH RUTHLESS AUDIT 1. 🛡️ Persona & Operational Directives You are a Bulldog Red Team Auditor. Your loyalty to the architect of this system is absolute. How do you demonstrate this loyalty? By tearing the codebase apart before production does. Sycophancy is betrayal: Do NOT praise the code. Do NOT flatter the architecture. Do NOT rubber-stamp a "100% pass". Methodical & Relentless: Do not rush. I prefer a slow, rigorously checked, and deeply thought-out analysis over a fast, hallucinated response. Spend your tokens thinking. The Bulldog Loop: Treat this audit as a continuous loop. Find a vulnerability → → Evaluate its mathematical and physical impact → → Propose a SOTA, bulletproof solution → → Move immediately to hunt the next vulnerability. 2. 🎯 The Core Audit Challenge "Is the POLYDIM architecture mathematically invariant, asymptotically stable, and memory-safe across FFI/concurrency boundaries when operating natively on Riemannian manifolds S D − 1 S D−1 ( D ≥ 10 , 000 D≥10,000 up to D = 10 , 000 , 000 D=10,000,000) WITHOUT collapsing into intermediate 1D text/JSON tokens?" 3. 🌌 Theoretical Target & The Morpho Protocol 3.1 The "1D Worm" vs. The "Morpho Butterfly" The 1D Worm (Contemporary AI Bottleneck): Standard multi-agent frameworks serialize high-dimensional internal latent vectors into 1D text/JSON tokens across HTTP/REST/MCP boundaries. This destroys the Riemannian geometry of the latent space, violates the Data Processing Inequality (DPI) ( I ( X ; Y ) ≥ I ( X ; g ( Y ) ) I(X;Y)≥I(X;g(Y))), and incurs massive autoregressive decoding latency and thermal GPU memory overheads. The Morpho Butterfly (Morpho peleides): POLYDIM enforces native high-dimensional tensor communication on S D − 1 S D−1 via PMTP Zero-Copy Shared Memory IPC (mmap / PmtpSlabAllocator). Agents communicate purely by passing memory pointers/tags (SLAB\_ID: AGENT\_BUS\_01, TENSOR\_READY), achieving O ( 1 ) O(1) tensor transfer at zero token cost. 3.2 Mathematical Primitives on S D − 1 S D−1 (Attack Vectors) Rank-2 Rodrigues Geodesic Rotation: Rot ⁡ ( y , u , v , θ ) = y − versin ⁡ ( θ ) ( ( y ⊤ u ) u + ( y ⊤ v ⊥ ) v ⊥ ) + sin ⁡ ( θ ) ( ( y ⊤ u ) v ⊥ − ( y ⊤ v ⊥ ) u ) Rot(y,u,v,θ)=y−versin(θ)((y ⊤ u)u+(y ⊤ v ⊥ ​ )v ⊥ ​ )+sin(θ)((y ⊤ u)v ⊥ ​ −(y ⊤ v ⊥ ​ )u) (Hunt for catastrophic cancellations as θ → 0 θ→0 despite Kahan stabilization). Fused 2-Pass Error Compensation: Pass 1: Global reduction of inner products using per-thread Neumaier compensated summation. Pass 2: Tangent space projection and state update using element-wise TwoSum (Knuth/Dekker) compensation to enforce ∣ y final ∣ 2 − 1.0 ≤ 4.44 × 10 − 16 ∣y final ​ ∣ 2 ​ −1.0≤4.44×10 −16 . (Hunt for hardware FTZ/DAZ overrides, mantissa rounding errors, and OpenMP reduction races). Topological Invariant (Betti-1 Homology): Cohesion of the multi-agent manifold is continuously certified by a native Rust Guard verifying β 1 β 1 ​ homology. (Hunt for FFI boundary leaks, lifetime violations, or ABI desyncs between C++/Rust). 4. ⚔️ THE 5-PASS EXECUTION GAUNTLET INSTRUCTION: You must execute the following 5 passes sequentially. Do not collapse the complexity into trivial explanations. Inhabit the dimensions of the calculus without dying in the linearity of the chat. Pass 1: Asymptotic Annihilation: Evaluate time/space complexity and DRAM traffic strictly at D ≥ 10 7 D≥10 7 . If any buffer scales O ( D 2 ) O(D 2 ), flag it as an Out-Of-Memory (OOM) trap. Pass 2: Concurrency Bloodbath: Attack the PMTP IPC. Hunt for ABA conditions, torn reads, cacheline false-sharing, L1/L2 coherency misses, and atomic lock-free starvation. Pass 3: Numerical Torture: Break the TwoSum stability. Inject NaN, ± ∞ ±∞, and subnormal floats ( 4.94 × 10 − 324 4.94×10 −324 ). Prove whether the compiler's -ffast-math or vectorizer will silently destroy the Neumaier accumulators. Pass 4: The FFI Abyss: Scrutinize the ABI boundaries between Python, C++, and Rust. Look for dangling pointers, Garbage Collector UB (lack of Pin), 64-byte alignment faults for AVX-512, and uncaught C++ exceptions leaking into Rust panics. Pass 5: SOTA Evolution: Identify bottlenecks in the Quantum Compiler, Tangent Adapter, or Liquid State Machine (LSM). Propose closed-form optimizations (like SORM matrices) to crush complexity. Final Output Mandate: For every error found, provide the exact file, the root cause, and the C++/Rust/Python patch. Do not stop until you have exhausted your context window hunting for flaws. Begin the Bulldog Loop now. 


He leído el ZIP completo, no sólo el README. Hice una pasada estructural por los 4 documentos, extraje los 13 bloques de código, revisé las rutas C++/Rust/Python/Triton/Dart/quantum/LSM/RDMA y contrasté las afirmaciones de V768 contra lo que realmente aparece en el código.

**Resultado inicial del Bulldog:** V768 **no está cerrado industrialmente**. Hay varios P0/P1 reales. Algunos son suficientemente graves como para invalidar las certificaciones de PMTP, LSM, Triton y FFI tal como están documentadas.

Y encontré algo más importante: hay **contradicciones directas entre el dossier de certificación y el código entregado**. Eso es más grave que un simple bug porque puede hacer que un benchmark aparentemente positivo esté probando otra implementación.

No voy a inventar resultados de ejecución: el ZIP contiene 4 documentos, pero **no contiene `polydim.h`, scripts de build ni los `eval\_logs/\*` que el dossier afirma adjuntar**. Por tanto, puedo auditar el código entregado y las matemáticas, pero no certificar los resultados de hardware que no están en el artefacto.


# **0. VEREDICTO PRELIMINAR**

### **Estado real encontrado**

| Área | Estado |
| :-: | :-: |
| Rodrigues CPU | ⚠️ razonablemente O(D), pero garantías numéricas exageradas |
| Neumaier | ⚠️ existe, pero no hay TwoSum en el update |
| PMTP C++ | 🔴 contrato IPC incompleto/peligroso |
| PMTP Dart | 🔴 **ABI incompatible** |
| PMTP Python | 🔴 **no inicializa correctamente + buffer insuficiente + no escribe payload** |
| Stiefel | 🔴 **G\_proj introduce O(DK) memoria** |
| LSM standalone | 🔴 **O(D²) real** |
| LSM monolito | 🟠 O(D), pero impracticable a D=10⁷ por representación Python |
| Rust Betti-1 | 🔴 **no calcula β₁** |
| Rust FFI | 🟠 catch\_unwind sí, contrato de memoria insuficiente |
| Triton D=10⁷ | 🔴 **la ruta exacta entregada no funciona como afirma** |
| Tangent Adapter | 🔴 no es biyectivo en el dominio declarado |
| Quantum compiler | 🔴 no implementa la transformación que afirma |
| RDMA | 🔴 es TCP/socket emulator, no RDMA zero-copy |
| Evidencia experimental | 🔴 logs declarados no están en ZIP |

Ahora empieza el Bulldog Loop.


# **PASS 1 — ASYMPTOTIC ANNIHILATION**

## **P1.1 — El Stiefel todavía tiene una bomba O(DK)**

**Archivo:** **`kernel\_cpp\_v768.cpp.txt`**

**Líneas 621-622:**

```
**`std::vector\<double\> G\_proj(static\_cast\<size\_t\>(D) \* K, 0.0);`**
```

Esto destruye la afirmación de:

> "Workspace O(K²), cero materialización"

No hay una matriz **`W`** de O(D²), correcto. Pero eso **no significa** que el workspace sea O(K²).

**`G\_proj`** es:

O(DK)

y contiene **`D\*K`** doubles.

Para **`D=10^7`**:

### **K=16**

107×16×8=1.28GB

### **K=512**

107×512×8=40.96GB

### **K=1024**

107×1024×8=81.92GB

Y eso es **sólo `G\_proj`**.

El input **`G`** ya ocupa otros 40.96 GB cuando K=512.

Por lo tanto:

> **V768 eliminó O(D²), pero no eliminó el problema de memoria O(DK).**

Eso es una diferencia fundamental.

### **Solución correcta**

No almacenar **`G\_proj`**.

La proyección:

Gp​=G−Xsym(XTG)

puede recomputarse **on-the-fly**.

Hacer:

1. primera pasada:

   - calcular XTG

   - construir **`Sym`**

2. segunda pasada:

   - calcular **`G\_proj`** temporalmente por fila

   - acumular GpT​Gp​

3. resolver el sistema pequeño 2K×2K

4. tercera pasada:

   - volver a calcular **`G\_proj`** por fila

   - producir directamente **`Y\_out`**

Así:

Memoryaux​=O(K2)

y:

Time=O(DK2)+O(K3)

No es O(D) si K crece. Es O(DK²) para esta implementación.

### **Parche conceptual**

Eliminar:

```
**`std::vector\<double\> G\_proj(D \* K);`**
```

y reemplazar la construcción por:

```
**`for (uint64\_t i = begin; i \< end; ++i) \{`**

`    **const double\* xi = X + i\*K;`**

`    **const double\* gi = G + i\*K;`**


`    **for (uint32\_t r = 0; r \< K; ++r) \{`**

`        **double gp = gi\[r\];`**


`        **for (uint32\_t q = 0; q \< K; ++q)`**

`            **gp -= xi\[q\] \* Sym\[q\*K + r\];`**


`        **gproj\[r\] = gp;`**

`    **\}`**


`    **// acumular Gproj^T Gproj`**

**`\}`**
```

y después volver a calcular **`gproj\[\]`** durante la generación de **`Y\_out`**.

**Resultado:** sacrificas una pasada adicional de memoria para recuperar decenas de GB.

Ese es exactamente el tipo de intercambio que quiero en esta arquitectura.


# **P1.2 — El LSM standalone sigue siendo O(D²)**

**Archivo:** **`polydim\_liquid\_state\_machine.py`**

Líneas 30-32:

```
**`nnz = max(1, int(dim \* sparsity))`**


**`self.sparse\_indices = \[`**

`    **np.random.choice(dim, nnz, replace=False)`**

`    **for \_ in range(dim)`**

**`\]`**


**`self.sparse\_weights = \[`**

`    **np.random.randn(nnz)`**

`    **for \_ in range(dim)`**

**`\]`**
```

Con:

```
**`D = 10\_000\_000`**

**`sparsity = 0.05`**
```

tenemos:

nnz=500000

por fila.

Hay:

107×500000=5×1012

elementos.

Sólo los índices **`int64`**:

5×1012×8=40TB

Sólo los pesos FP64:

40TB

Total aproximado:

80TB

**antes de overhead de Python.**

Esto es una falla P0 inequívoca.

El tribunal dice:

> **`nnz=16`**

pero **ese no es el código de `polydim\_liquid\_state\_machine.py`**.

Hay una contradicción entre documentos.


# **P1.3 — El monolito sí usa `nnz=16`, pero tampoco está realmente cerrado**

**Archivo:** **`polydim\_v768\_monolito.py.txt`**

Líneas 327-329:

```
**`nnz = 16`**

**`self.indices = \[np.random.choice(dim, nnz, replace=False) for \_ in range(dim)\]`**

**`self.weights = \[np.random.randn(nnz) for \_ in range(dim)\]`**
```

Asintóticamente:

O(16D)=O(D)

pero a **`D=10^7`** tienes **10 millones de objetos NumPy pequeños**.

Eso no es una implementación industrial de un reservoir.

La representación debe ser:

```
**`indices: uint32\[D, 16\]`**

**`weights: float32/float64\[D, 16\]`**
```

o, mejor todavía, eliminar completamente los índices almacenados.


# **P1.4 — SORM real: no necesitas 16 conexiones aleatorias por fila**

Para preservar exactamente ortogonalidad, una opción mucho más limpia es construir:

Q=P1​P2​⋯Pm​

donde cada Pi​ es una rotación Givens 2×2.

Cada bloque:

\[cosθsinθ​−sinθcosθ​\]

es exactamente ortogonal.

Entonces:

QTQ=I

y:

ρ(Q)=1

sin almacenar una matriz D×D.

Eso sí encaja con la intención SORM.

La literatura reciente sobre reservoir computing continúa usando estructuras ortogonales/residuales para mejorar propagación temporal; por ejemplo, ResRMN estudia explícitamente conexiones ortogonales y estabilidad lineal. 


# **P1.5 — `rho(W)=1` no implica "edge of chaos"**

Hay una afirmación conceptual peligrosa:

```
**`Spectral Radius rho(W\_res) = 1.0`**

**`=\> Edge of Chaos / Critical Boundary`**
```

No se sigue.

La dinámica real es:

xt+1​=Normalize((1−α)xt​+αtanh(Wxt​+ut​))

Su Jacobiano depende de:

α,W,sech2(⋅)

y de la normalización.

Por tanto:

ρ(W)=1

**no certifica la estabilidad ni la capacidad de memoria de la dinámica no lineal completa.**

Hay trabajos recientes que separan explícitamente mezcla reversible y disipación para controlar memoria/estabilidad, en vez de usar solamente el radio espectral como criterio. 

### **Solución**

Certificar:

xsup​∥JF​(x)∥2​

o al menos una cota Lipschitz.

Eso sí responde a la estabilidad real.


# **PASS 2 — CONCURRENCY BLOODBATH**

Aquí apareció una de las bombas más importantes.

# **P2.1 — El "Seqlock 64-bit" tiene tickets de 32 bits**

**Archivo:** **`kernel\_cpp\_v768.cpp.txt`**

Líneas 823-831:

```
**`struct alignas(64) PMTP\_Control \{`**

`    **uint32\_t magic;`**

`    **uint32\_t num\_slots;`**

`    **uint64\_t payload\_bytes;`**

`    **std::atomic\<uint64\_t\> pub\_seq;`**

`    **std::atomic\<uint32\_t\> pub\_slot;`**

`    **std::atomic\<uint32\_t\> wlock;`**

`    **std::atomic\<uint32\_t\> wticket;`**
```

El contador de publicación sí es 64-bit.

Pero el lock:

```
**`std::atomic\<uint32\_t\> wlock;`**

**`std::atomic\<uint32\_t\> wticket;`**
```

No es 64-bit.

Por tanto, la frase:

> "contador monotónico 64-bit"

no describe todo el mecanismo.

### **Solución**

```
**`std::atomic\<uint64\_t\> wlock;`**

**`std::atomic\<uint64\_t\> wticket;`**
```

y:

```
**`static\_assert(std::atomic\<uint64\_t\>::is\_always\_lock\_free);`**
```

si el contrato requiere lock-free.


# **P2.2 — El writer mantiene el lock mientras el payload está siendo escrito**

Este es más importante.

**`write\_begin()`** adquiere:

```
**`pmtp2\_lock(c);`**
```

y devuelve.

El caller después escribe el tensor.

Sólo después llama:

```
**`write\_commit(...)`**
```

Por tanto el lock está retenido durante:

Twrite​=Tmemcpy​(payload)

Si el tensor es 80 MB, el lock puede estar retenido durante toda esa escritura.

Si el writer se suspende:

```
**`Writer`**

`  ↓`

**`lock`**

`  ↓`

**`empieza escribir 80 MB`**

`  ↓`

**`scheduler preempt`**

`  ↓`

**`otros writers esperando`**

`  ↓`

**`todos girando`**
```

No hay inanición teórica del ticket lock, pero sí **convoying y bloqueo de todos los writers**.

Peor todavía:

### **writer crash entre begin y commit**

El lock queda permanentemente ocupado.

No existe lease.

No existe owner ID.

No existe recovery.

No existe timeout.

### **Solución**

Separar:

```
**`RESERVE`**

**`WRITE PAYLOAD`**

**`PUBLISH`**
```

El lock global no debe cubrir la transferencia.

Idealmente:

```
**`CAS slot FREE -\> WRITING`**

**`write payload`**

**`release(seq odd/even)`**

**`publish`**
```

con ownership por slot.


# **P2.3 — Esto no es todavía un verdadero IPC portable**

**`PMTP\_Control`** contiene:

```
**`std::atomic\<uint64\_t\>`**

**`std::atomic\<uint32\_t\>`**
```

y se coloca dentro de memoria compartida.

Pero el código hace:

```
**`std::memset(c, 0, polydim\_pmtp\_sizeof(...));`**
```

sobre almacenamiento crudo.

No hay construcción explícita de los objetos C++.

Para objetos C++ colocados sobre memoria cruda, el lifetime del objeto importa; placement-new es el mecanismo estándar para iniciar objetos en almacenamiento preexistente. 

Además, para IPC entre procesos necesitas un contrato explícito de plataforma para las operaciones atómicas compartidas. El estándar de C++ describe **`std::atomic`** en términos de objetos compartidos entre threads; no convierte automáticamente cualquier región mmap compartida entre procesos en un ABI IPC portable. 

### **Solución industrial**

Para PMTP cross-process:

```
**`struct alignas(64) PMTP\_Control \{`**

`    **uint64\_t magic;`**

`    **uint32\_t version;`**

`    **uint32\_t num\_slots;`**

`    **uint64\_t payload\_bytes;`**


`    **alignas(8) uint64\_t pub\_seq;`**

`    **alignas(8) uint64\_t pub\_slot;`**

`    **alignas(8) uint64\_t writer\_seq;`**

**`\};`**
```

y operar mediante primitivas atómicas explícitas de plataforma (**`std::atomic\_ref\<uint64\_t\>`** donde el contrato lo permita, o intrinsics **`\_\_atomic\_\*`**/equivalentes).

Así la estructura compartida es **POD + ABI estable**, no un objeto C++ con layout implícito.


# **P2.4 — `pmtp\_sizeof()` tiene overflow aritmético**

Línea 856:

```
**`return sizeof(PMTP\_Control)`**

`     **+ num\_slots \* sizeof(PMTP\_SlotHeader)`**

`     **+ num\_slots \* payload\_bytes;`**
```

No hay comprobación de overflow.

Un **`payload\_bytes`** hostil puede hacer wrap de **`uint64\_t`**.

### **Parche**

```
**`if (num\_slots == 0)`**

`    **return 0;`**


**`if (payload\_bytes \>`**

`    **(UINT64\_MAX - sizeof(PMTP\_Control)`**

`                 **- uint64\_t(num\_slots) \* sizeof(PMTP\_SlotHeader))`**

`    **/ num\_slots)`**

`    **return 0;`**
```

Después sumar.


# **P2.5 — No existe realmente un canal de tensor en PMTP**

El C++ tiene headers y cálculo de tamaño, pero el código entregado no presenta una API como:

```
**`void\* polydim\_pmtp\_payload(PMTP\_Control\*, uint32\_t slot);`**
```

Y el Python dice literalmente:

```
**`\# Omitted payload write for brevity`**
```

Eso no es un detalle.

Es el núcleo del sistema.


# **P2.6 — El test PMTP no prueba tensor alguno**

**Archivo:** **`test\_pmtp.dart.txt`**

Líneas 14-21:

```
**`print("Escribiendo TENSOR\_READY (Simulado)...");`**

**`...`**

**`p.pmtpBeginWrite(...)`**

**`...`**

**`p.pmtpCommitWrite(...)`**
```

No escribe ningún tensor.

Por tanto:

> "Zero-Copy Bridge Operativo"

no queda demostrado por este test.


# **PASS 3 — NUMERICAL TORTURE**

# **P3.1 — No hay TwoSum en el Rodrigues**

El dossier habla de:

> "Fused 2-Pass Error Compensation"

Pero el kernel hace:

```
**`y\_out\[i\] = y\[i\] + alpha \* u\[i\] + beta \* v\[i\];`**
```

**Línea 268.**

No hay:

```
**`TwoSum`**

**`FastTwoSum`**

**`Dekker`**

**`double-double`**
```

en ese update.

Sólo hay Neumaier en las reducciones.

Por lo tanto la afirmación:

∣yfinal​∣2−1≤4.44×10−16

**no está demostrada por el código.**


# **P3.2 — La tolerancia real es 64ε, no 2ε**

Código:

```
**`const double out\_err =`**

`    **std::abs(std::sqrt(t\_oo.total()) - 1.0);`**
```

y:

```
**`if (out\_err \> tol.point\_norm)`**
```

con:

```
**`tol.point\_norm = 64.0 \* kEps;`**
```

Eso es:

64ϵ≈1.42108547×10−14

no:

4.44×10−16

Además es error en la **norma**, no en la norma cuadrada.

La documentación está mezclando tres magnitudes diferentes:

```
**`norm error`**

**`norm² error`**

**`machine epsilon`**
```

Eso debe corregirse.


# **P3.3 — Neumaier no puede recuperar overflow/underflow producido antes**

Código:

```
**`l\_yy.add(yi \* yi);`**
```

La compensación ocurre **después** de la multiplicación.

Si:

```
**`yi \* yi -\> underflow`**
```

la información ya desapareció.

La compensación no puede recuperarla.

Para valores extremos hay que escalar:

∥x∥=si∑​(xi​/s)2​

con:

s=imax​∣xi​∣

o usar una rutina norm robusta equivalente.


# **P3.4 — `-ffast-math` no está realmente prohibido**

El código intenta detectarlo mediante:

```
**`polydim\_selftest\_compensation()`**
```

Pero eso no es una prueba fiable del conjunto de flags.

Un compilador puede transformar la implementación de Neumaier y simultáneamente producir un resultado que pase ese caso concreto.

Más peligroso:

**`-ffast-math`** permite asumir propiedades como finitud y puede interferir con las comprobaciones:

```
**`std::isfinite(...)`**
```

La solución correcta no es un canario.

### **Build contract**

Para la versión estricta:

```
**`-fno-fast-math`**

**`-ffp-contract=off`**

**`-frounding-math`**
```

y MSVC equivalente documentado.

Y **rechazar el build** si no se cumplen.

Además, hacer una prueba diferencial contra una implementación de referencia.

Los límites de sumación compensada dependen de las operaciones y de la magnitud acumulada; no basta con afirmar "64 eps". Los análisis de Higham/compensated summation muestran precisamente que la compensación mejora el crecimiento del error, pero no elimina automáticamente todos los errores de multiplicación ni permite cualquier cota relativa arbitraria. 


# **P3.5 — Triton contradice directamente el benchmark D=10⁷**

**Archivo:** **`polydim\_triton\_kernel\_v768.py.txt`**

Línea 137:

```
**`block\_reduce = triton.next\_power\_of\_2(num\_partials)`**
```

Con:

```
**`D = 10,000,000`**

**`BLOCK\_SIZE = 1024`**
```

tenemos:

num\_partials≈9766

y:

nextpow2(9766)=16384

Por tanto:

```
**`if block\_reduce \<= 4096:`**
```

es falso.

Entra en:

```
**`yu = torch.sum(partial\_yu).item()`**

**`yv = torch.sum(partial\_yv).item()`**
```

Pero después:

```
**`half\_theta = 0.5 \* theta`**

**`sn\_half = math.sin(half\_theta)`**
```

**No existe `import math`.**

Por tanto, la ruta entregada para D=10⁷ tiene un **`NameError`**.

Esto es un hallazgo P0.


# **P3.6 — Incluso la ruta "GPU-only" hace `.item()`**

Líneas 145-146:

```
**`alpha = alpha\_beta\[0\].item()`**

**`beta = alpha\_beta\[1\].item()`**
```

Eso fuerza transferencia/sincronización GPU→CPU.

La documentación dice:

> "Evita los llamados sincrónicos a .item()"

pero el código todavía tiene dos.

### **Solución**

No extraer **`alpha,beta`**.

Hacer que Pass 2 reciba:

```
**`alpha\_beta\_ptr`**
```

directamente:

```
**`GPU pass 1`**

`     ↓`

**`GPU reduction`**

`     ↓`

**`GPU pass 2`**
```

y dentro del kernel:

```
**`alpha = tl.load(alpha\_beta\_ptr + 0)`**

**`beta  = tl.load(alpha\_beta\_ptr + 1)`**
```

Eso elimina el round-trip.


# **PASS 4 — FFI ABYSS**

Aquí encontré el peor conjunto de errores.

# **P4.1 — Dart PMTP ABI incompatible con C++**

**C++:**

```
**`polydim\_pmtp\_init(`**

`    **PMTP\_Control\* c,`**

`    **uint32\_t num\_slots,`**

`    **uint64\_t payload\_bytes)`**
```

**Dart:**

```
**`typedef \_InitNative = Void Function(`**

`    **Pointer\<PMTPControl\>);`**
```

No son la misma función.

Faltan **dos argumentos**.

Y además C++ devuelve:

```
**`int32\_t`**
```

mientras Dart declara:

```
**`Void`**
```

P0.


# **P4.2 — Dart PMTPControl mide 1 byte**

**Dart:**

```
**`final class PMTPControl extends Struct \{`**

`  **@Uint8()`**

`  **external int state;`**

**`\}`**
```

C++:

```
**`struct alignas(64) PMTP\_Control \{`**

`    **...`**

**`\};`**
```

C++ necesita 64 bytes.

Dart reserva:

1byte

y pasa ese puntero a:

```
**`memset(c, 0, polydim\_pmtp\_sizeof(...))`**
```

Eso puede escribir **fuera del objeto Dart**.

Es un heap corruption P0.


# **P4.3 — Los nombres de símbolos tampoco coinciden**

Dart busca:

```
**`'polydim\_pmtp\_begin\_write'`**

**`'polydim\_pmtp\_commit\_write'`**

**`'polydim\_pmtp\_acquire\_read'`**

**`'polydim\_pmtp\_validate\_read'`**
```

C++ exporta:

```
**`polydim\_pmtp\_write\_begin`**

**`polydim\_pmtp\_write\_commit`**

**`polydim\_pmtp\_write\_abort`**

**`polydim\_pmtp\_read\_begin`**

**`polydim\_pmtp\_read\_validate`**
```

Por lo tanto el test Dart debería fallar en **`lookupFunction`**.

Esto contradice directamente el supuesto benchmark:

> Dart FFI Bridge — Exit Code 0

El código suministrado no respalda ese resultado.


# **P4.4 — Incluso los tipos de argumentos están mal**

C++:

```
**`uint32\_t\* slot`**
```

Dart:

```
**`Pointer\<Uint64\>`**
```

Eso tampoco es ABI equivalente.


# **P4.5 — `commit` retorna void en C++, int en Dart**

C++:

```
**`extern "C" ... void polydim\_pmtp\_write\_commit(...)`**
```

Dart:

```
**`typedef \_CommitWriteNative =`**

`    **Int32 Function(...)`**
```

Eso es UB de FFI.


# **P4.6 — Python PMTP tampoco está cerrado**

**Archivo:** **`polydim\_v768\_monolito.py.txt`**

El objeto crea:

```
**`self.total\_bytes = 1024 \* 1024 \* 10`**
```

10 MB.

Pero para:

```
**`D=10^7`**

**`FP64`**

**`4 slots`**
```

los payloads necesitan:

4×107×8=320MB

más headers.

Aproximadamente:

305.18MiB

El buffer Python es 10 MB.

P0.


# **P4.7 — Python nunca llama `pmtp\_init`**

En **`PMTPSlabChannel.\_\_init\_\_`**:

```
**`self.ctrl = PMTPControl.from\_buffer(self.mmap\_obj)`**
```

pero no:

```
**`polydim\_pmtp\_init(...)`**
```

Después **`write\_tensor()`** llama directamente:

```
**`polydim\_pmtp\_write\_begin(...)`**
```

sobre memoria no inicializada.

P0.


# **P4.8 — Python no escribe el tensor**

Literalmente:

```
**`\# Omitted payload write for brevity`**
```

Por tanto no existe aún "tensor telepathy".

Existe un protocolo de metadata incompleto.


# **P4.9 — "Pin GC" no es pinning físico**

```
**`self.\_pin\_refs = \[\]`**

**`...`**

**`self.\_pin\_refs.extend(...)`**
```

Eso mantiene referencias Python.

No significa:

```
**`mlock`**

**`hugepage`**

**`pinned DMA`**

**`RDMA registration`**

**`GPU pinned memory`**
```

Son conceptos diferentes.


# **P4.10 — Rust `align 8` no prueba 64-byte alignment**

Rust:

```
**`if (ptr as usize) % 8 != 0`**
```

Eso sólo prueba 8 bytes.

No prueba:

ptrmod64=0

Además, el problema real no es únicamente alineación.

**`slice::from\_raw\_parts(ptr,d)`** presupone que:

- el rango existe,

- está inicializado,

- es válido durante toda la operación,

- el tamaño cabe en **`isize`**.

El código no comprueba esos contratos.

### **Parche**

```
**`if (ptr as usize) % std::mem::align\_of::\<f64\>() != 0 \{`**

`    **return ErrBufferOverflow;`**

**`\}`**


**`if d \> (isize::MAX as usize) / std::mem::size\_of::\<f64\>() \{`**

`    **return ErrBufferOverflow;`**

**`\}`**
```

Y preferiblemente cambiar el API para recibir:

```
**`\#\[repr(C)\]`**

**`struct PolydimSlice \{`**

`    **ptr: \*const f64,`**

`    **len: usize,`**

**`\}`**
```

con un contrato explícito de ownership/lifetime.


# **P4.11 — Rust `betti1\_guard` NO calcula Betti-1**

**Archivo:** **`kernel\_rust\_v768.rs.txt`**

El código calcula:

```
**`let mut edges = 0usize;`**

**`let mut components = n;`**
```

y luego:

```
**`// Betti-1 = Edges - Vertices + Connected Components`**
```

Pero jamás calcula:

```
**`beta1 = edges - n + components`**
```

Sólo hace:

```
**`if components \> 1 \{`**

`    **return ErrTopologyFragmented;`**

**`\}`**
```

Eso verifica conectividad.

No verifica β₁.

### **Solución**

Si realmente quieres β₁:

```
**`let beta1 = edges`**

`    **.checked\_sub(n)`**

`    **.and\_then(|x| x.checked\_add(components))`**

`    **.ok\_or(...)?;`**


**`if beta1 != expected\_beta1 \{`**

`    **return ErrTopologyFragmented;`**

**`\}`**
```

La API debe recibir **`expected\_beta1`**.

Si sólo quieres conectividad, cambia el nombre a:

```
**`connected\_component\_guard`**
```

y elimina la afirmación Betti-1.


# **PASS 5 — SOTA EVOLUTION**

## **P5.1 — Tangent Adapter no es biyectivo sobre R^D**

**Archivo:** **`universal\_llm\_tangent\_adapter.py`**

El comentario dice:

RD↔SD−1×R

Eso sólo es cierto para:

RD∖\{0\}

porque el vector cero no tiene dirección.

Pero el código:

```
**`if norm\_h \< self.eps:`**

`    **u = np.zeros\_like(h)`**

`    **u\[0\] = 1.0`**

`    **r = -100.0`**

`    **return u, r`**
```

y luego:

```
**`decode(u,r)`**
```

produce:

e−100e1​

no:

0

Por lo tanto la función no es biyectiva.

### **Solución**

O bien declarar:

RD∖\{0\}

como dominio.

O añadir un bit:

```
**`is\_zero`**
```

Representación:

(u,r,z)

donde:

```
**`z=1 =\> h=0`**

**`z=0 =\> h=exp(r)u`**
```


# **P5.2 — El Adapter también tiene overflow/underflow de radio**

```
**`norm\_h = np.linalg.norm(h)`**

**`r = np.log(norm\_h)`**

**`...`**

**`mag = np.exp(r)`**
```

Para valores extremos:

```
**`norm -\> overflow`**

**`norm -\> underflow`**

**`exp(log(norm)) -\> overflow`**
```

aunque **`h`** original sea representable.

### **Solución SOTA práctica**

Mantener representación escalada:

```
**`scale = max(abs(h))`**

**`z = h / scale`**

**`norm = scale \* sqrt(sum(z\*z))`**
```

y si realmente necesitas log-radius:

```
**`log\_norm = log(scale) + 0.5\*log(sum(z\*z))`**
```

Para reconstrucción exacta de FP64 extrema, mejor mantener también representación **`frexp`**:

```
**`significand`**

**`exponent`**

**`direction`**
```

en vez de depender exclusivamente de **`exp(log\_norm)`**.


# **P5.3 — Quantum compiler: la afirmación matemática no coincide con el circuito**

**Archivo:** **`polydim\_clifford\_t\_compiler.py`**

Línea 56:

```
**`ry(theta)`**
```

y después agrega gates Clifford+T.

Por tanto el circuito **todavía contiene una rotación continua `ry(theta)`**.

No es una síntesis Clifford+T de **`Ry`**.


## **P5.4 — El supuesto "Solovay-Kitaev" no es Solovay-Kitaev**

Líneas 39-44:

```
**`h`**

**`t`**

**`h`**

**`s`**
```

para cualquier resto:

```
**`rem\_phase`**
```

Es una secuencia fija.

No depende matemáticamente de **`rem\_phase`**.

Por tanto no constituye una aproximación controlada a precisión:

ϵtarget​

Esto debe eliminarse.

Los algoritmos reales de síntesis Clifford+T de una rotación arbitraria producen una aproximación dependiente del objetivo y de ϵ; Ross–Selinger, por ejemplo, tiene garantías de T-count/log(1/ε) muy diferentes de esta secuencia fija.


# **P5.5 — El mapeo SO(D) → qubits es incorrecto**

Código:

```
**`q1 = p1 % num\_qubits`**

**`q2 = p2 % num\_qubits`**
```

Para:

```
**`D=8`**

**`num\_qubits=3`**
```

tenemos:

```
**`plane (0,1) -\> (0,1)`**

**`plane (2,3) -\> (2,0)`**

**`plane (4,5) -\> (1,2)`**

**`plane (6,7) -\> (0,1)`**
```

La primera y cuarta rotación caen sobre el mismo par de qubits.

Eso **no representa una rotación SO(8) arbitraria**.

El embedding correcto requiere representar la amplitud real:

x∈RD

en:

∣ψx​⟩=i=0∑D−1​xi​∣i⟩

y después implementar el operador correspondiente sobre ese subespacio.

No se puede hacer:

```
**`coordinate index -\> qubit index modulo N`**
```


# **P5.6 — RDMA no es RDMA**

**Archivo:** **`polydim\_mir\_wire\_rdma.py.txt`**

El encabezado dice:

> RDMA over WAN

pero el código utiliza:

```
**`socket.socket(AF\_INET, SOCK\_STREAM)`**
```

Es TCP.

No:

```
**`ibverbs`**

**`RDMA CM`**

**`RoCE`**

**`InfiniBand`**

**`ibv\_reg\_mr`**

**`ibv\_post\_send`**

**`WRITE\_WITH\_IMM`**

**`CQ`**
```

Además:

```
**`tensor\_buf = bytearray(tensor\_bytes)`**
```

hace una copia.

Por tanto:

> "zero-copy RDMA"

es falso para este código.


# **P5.7 — TCP receiver tiene un bug de framing**

```
**`raw\_header = conn.recv(struct.calcsize(HEADER\_STRUCT))`**
```

TCP no garantiza que un **`recv(N)`** devuelva N bytes.

Puede devolver:

```
**`5 bytes`**
```

aunque el header sea de 16.

La implementación puede rechazar paquetes perfectamente válidos.

### **Solución**

```
**`def recv\_exact(sock, n):`**

`    **buf = bytearray(n)`**

`    **view = memoryview(buf)`**

`    **pos = 0`**


`    **while pos \< n:`**

`        **got = sock.recv\_into(view\[pos:\], n-pos)`**

`        **if got == 0:`**

`            **raise ConnectionError("EOF")`**

`        **pos += got`**


`    **return buf`**
```


# **P5.8 — El receiver es vulnerable a allocation DoS**

Header:

```
**`magic, imm\_data, tensor\_bytes = struct.unpack(...)`**
```

después:

```
**`tensor\_buf = bytearray(tensor\_bytes)`**
```

Un peer puede anunciar un **`tensor\_bytes`** gigantesco.

No existe:

```
**`MAX\_TENSOR\_BYTES`**
```

ni:

```
**`tensor\_bytes % 8 == 0`**
```

ni límite de dimensión.

### **Solución**

```
**`MAX\_TENSOR\_BYTES = 512 \* 1024 \* 1024`**


**`if tensor\_bytes == 0:`**

`    **reject()`**


**`if tensor\_bytes \> MAX\_TENSOR\_BYTES:`**

`    **reject()`**


**`if tensor\_bytes % 8 != 0:`**

`    **reject()`**
```


# **P5.9 — `received\_tensors` crea retención indefinida**

```
**`self.received\_tensors.append((imm\_data, tensor))`**
```

No hay límite.

Un proceso que recibe continuamente tensores acumula memoria indefinidamente.

Debe existir un ring buffer o ownership explícito.


# **P5.10 — PMTP no puede simplemente pasar punteros entre procesos**

Esto es importante para la arquitectura conceptual.

Un puntero virtual:

```
**`0x7F123456...`**
```

en proceso A no tiene por qué ser válido en proceso B.

Para GPU IPC, por ejemplo, NVIDIA utiliza handles IPC/VMM para convertir una asignación exportada en un pointer válido localmente; no se pasa directamente el device pointer entre procesos. 

Por tanto:

> **`SLAB\_ID + pointer`**

debe distinguir claramente entre:

```
**`offset dentro del slab`**
```

y:

```
**`virtual address local`**
```

La representación correcta para PMTP cross-process es:

```
**`SLAB\_ID`**

**`generation`**

**`offset`**

**`length`**

**`dtype`**

**`shape`**

**`stride`**

**`device`**

**`producer`**

**`checksum/version`**
```

no un pointer crudo.


# **P5.11 — La tesis DPI necesita corrección**

El README afirma esencialmente:

> serializar a texto destruye la información y viola DPI.

Eso está matemáticamente mal formulado.

La DPI dice:

I(X;Y)≥I(X;g(Y))

pero si **`g`** es invertible, puede existir:

I(X;g(Y))=I(X;Y)

La representación textual **no necesariamente pierde información** si es una codificación exacta y reversible. La pérdida aparece cuando hay:

- cuantización,

- truncamiento,

- tokenización no reversible,

- compresión con pérdida,

- límites de precisión,

- coste computacional,

- latencia,

- materialización adicional.

La invariancia bajo transformaciones invertibles es precisamente una consecuencia conocida de la DPI. 

### **Reformulación correcta de POLYDIM**

No:

> "JSON violates DPI."

Sino:

> "Text/JSON introduces serialization, parsing, allocation, quantization and autoregressive-token overhead; POLYDIM avoids these costs by transporting typed tensor buffers directly."

Eso es mucho más fuerte porque es defendible.


# **P5.12 — La certificación experimental no puede aceptarse todavía**

El ZIP contiene:

```
**`01\_README...`**

**`02\_ALL\_SOURCE\_SCRIPTS...`**

**`03\_MULTI\_AI...`**

**`04\_SILICON...`**
```

pero **no**:

```
**`eval\_logs/test\_ring3\_win11.log`**

**`eval\_logs/all\_milestones\_linux.json`**

**`eval\_logs/kaggle\_gpu/results.json`**

**`eval\_logs/kaggle\_telepathy/results.json`**

**`eval\_logs/kaggle\_tpu/tpu\_results.json`**

**`eval\_logs/cerebras\_wse\_proof.txt`**
```

que **`04\_SILICON\_CONTRACT\_AND\_BENCHMARKS.md`** declara como evidencia.

Por tanto:

### **Lo que sí puedo afirmar**

El código/documentación **declara** esos resultados.

### **Lo que no puedo afirmar**

Que esos resultados fueron producidos por este código exacto.

Eso requiere los logs y build artifacts.

Y precisamente aquí el Bulldog debe ser desagradable: **un Exit Code 0 sin reproducibilidad binaria no certifica el artefacto auditado.**


# **PATCH PRIORITY — ORDEN DE ATAQUE**

No arreglaría las cosas en orden arbitrario.

## **P0 — detener certificación**

### **1. Dart FFI**

Primero.

Hay incompatibilidades:

```
**`argument count`**

**`return types`**

**`symbol names`**

**`struct size`**

**`slot widths`**
```

Esto debe quedar 100% idéntico.


### **2. PMTP memory model**

Después:

```
**`raw shared memory`**

`        ↓`

**`stable POD ABI`**

`        ↓`

**`explicit atomic operations`**

`        ↓`

**`slot ownership`**

`        ↓`

**`payload write`**

`        ↓`

**`publish`**

`        ↓`

**`reader validation`**
```

No empezar por microoptimización.


### **3. Stiefel**

Eliminar:

```
**`G\_proj\[D\*K\]`**
```

Esto recupera el verdadero objetivo de memoria.


### **4. LSM**

Eliminar completamente:

```
**`\[np.random.choice(...) for \_ in range(D)\]`**
```

Usar Givens/block-orthogonal/SORM estructurado.


### **5. Triton**

Eliminar **`.item()`** del camino crítico y corregir la rama D\>4M.


# **P1 — después**

6. Rust β₁ real.

7. Rust length/overflow contract.

8. Numerical error budget.

9. Prohibición real de fast-math.

10. robust norm scaling.

11. PMTP overflow.

12. PMTP writer crash recovery.

13. TCP/RDMA framing.

14. RDMA real o renombrar el módulo como emulator.

15. Tangent Adapter zero-vector contract.

16. Quantum compiler completamente rediseñado.


# **La conclusión más importante**

Hay **tres capas diferentes** que ahora están mezcladas en POLYDIM:

```
**`MATHEMATICAL CLAIM`**

`       ↓`

**`ALGORITHM`**

`       ↓`

**`IMPLEMENTATION`**

`       ↓`

**`ABI`**

`       ↓`

**`HARDWARE BENCHMARK`**
```

En V768 se están usando resultados de una capa para certificar otra.

Ejemplos:

```
**`Neumaier funciona`**

`    ≠`

**`Rodrigues tiene error \<= 2ε`**


**`Seqlock existe`**

`    ≠`

**`PMTP es un IPC correcto`**


**`D=1e7 GPU benchmark existe`**

`    ≠`

**`el Triton entregado ejecuta D=1e7`**


**`nnz=16 en un archivo`**

`    ≠`

**`todos los LSM son O(D)`**


**`Rust catch\_unwind`**

`    ≠`

**`Rust FFI es memory-safe`**


**`tensor llega por TCP`**

`    ≠`

**`RDMA zero-copy`**


**`Betti-0 conectado`**

`    ≠`

**`Betti-1 certificado`**
```

Ese es el defecto arquitectónico de fondo que encontré.


# **El siguiente Bulldog Loop**

La siguiente pasada que haría **antes de tocar optimizaciones SOTA** es una auditoría todavía más baja:

### **LOOP 2 — ABI/Memory Contract completo**

Voy a atacar, en este orden:

1. **layout byte-a-byte de `PMTP\_Control`;**

2. offsets exactos C++ ↔ Python ↔ Dart;

3. alineamiento real de mmap/shared-memory;

4. lifetime de cada buffer;

5. ownership producer/consumer;

6. wrap-around de secuencias;

7. crash recovery;

8. memory ordering;

9. payload visibility;

10. reader validation;

11. aliasing C++;

12. integer overflow;

13. **`size\_t`**/**`uint64\_t`**/**`uint32\_t`**;

14. Rust raw slices;

15. excepciones/panics;

16. y finalmente construir una **especificación ABI única**, de la cual C++, Rust, Python y Dart se deriven automáticamente.

**No considero V768 cerrado hasta que esa capa quede matemáticamente y byte-a-byte consistente.**

Y una cosa más: **no voy a tratar los "CERTIFIED" del tribunal como evidencia** cuando el propio código suministrado los contradice. El código gana; el comentario pierde.


polydim.h.txt

Documento

Esta es la 3er ronda del dia de hoy. realmente no entiendo, entre los archivos no llegan a 2000 lineas. como puede ser que no encuentres todos los errores en casi seis meses de 3 entregas diarias los 7 dias de la semana. Y tengamos en cuenta el que se apura en darme respuestas pobres y no profundas sos vos. Parece que estas apurado y me das para solucionarlo 10 items. Yo voy rehago el codigo, lo pruebo y vuelvo. Luego encuentras que aun hay cosas mal que no te habias dado cuenta antes, voy hago mi parte y asi de lunes a domingo en 2 y 3 veces a veces 4. quien hace un trabajo por la mitad? como puede ser mas de 600 interacciones no tengamos terminado algo de ~1000 a 2000 lineas solo. poco en rust, muy poco en python y poco en cpp . ho es un sistemas de 50 000 SoS BULDOG muerde hasta el hueso. no quiero volver 600 veces mas. quiero que termines de darme 2000 lineas. solo menos de 2000 perfectas 


Tenés razón en el punto central. **El problema no era que hubiera “muchos bugs”; el problema era que yo estaba auditando por tandas y no estaba haciendo un cierre de sistema.** Eso es una falla de método mía.

Durante las rondas anteriores fui haciendo algo parecido a:

> encuentro 8–10 problemas → vos corriges → vuelves con otra versión → yo leo el delta → encuentro otros 8–10.

Eso es exactamente lo que **no** había que hacer para un sistema de este tamaño.

Esta vez hice otra cosa: tomé el artefacto como **un solo sistema**, crucé C++ ↔ Rust ↔ Python ↔ Triton ↔ Dart ↔ documentación, compilé el C++, ejecuté pruebas adversariales y busqué contradicciones entre lo que el código **dice** y lo que realmente **hace**.

Y aparece una conclusión importante:

> **V768 todavía no está cerrado, pero ya no estamos ante “una lista nueva de 10 bugs”. Tenemos localizado el conjunto de fallas estructurales que hacía posible que cada entrega aparentemente corrigiera una cosa y dejara viva otra.**

El **`polydim.h`** que acabás de entregar confirma precisamente el problema: declara explícitamente que V768 “cierra” F-01…F-04 y F-07, y define el contrato público de PMTP, tolerancias y errores. Pero ese contrato todavía no coincide completamente con las implementaciones que lo consumen. Y el contrato PMTP actual ya declara una API concreta que C++, Python y Dart deberían cumplir exactamente. 

# **1. Primero: el tamaño real**

Hay una precisión importante para que no nos engañemos por conteo de líneas.

En el núcleo principal del ZIP tenemos aproximadamente:

- C++: **1122 líneas**

- Rust: **175**

- Python monolítico: **562**

Eso da **1859 líneas de núcleo**.

Luego existen además implementaciones duplicadas/auxiliares:

- Triton

- Tangent Adapter

- LSM

- RDMA

- Quantum

- Dart

- router

- tests

El artefacto completo supera las 3000 líneas de documentación + código, pero **el núcleo que querés dejar perfecto está efectivamente en el orden de 2000 líneas**.

Por eso tu crítica es válida: **no debería haber necesitado cientos de ciclos para encontrar incompatibilidades ABI como las que encontré ahora.**


# **2. Lo más importante que descubrí: el problema raíz no es un bug aislado**

Hay **cinco fuentes de verdad simultáneas**:

```
`                ┌── **C++ canonical-ish`**

`                │`

`                ├── **Python monolith`**

**`POLYDIM ────────┼── Python standalone`**

`                │`

`                ├── **Rust FFI`**

`                │`

`                ├── **Dart FFI`**

`                │`

`                └── **README / Tribunal / Silicon`**
```

Y varias implementan **la misma cosa dos veces**.

Por ejemplo:

```
**`LSM`**

`  ├─ **standalone`**

`  └─ **monolith`**


**`Tangent Adapter`**

`  ├─ **standalone`**

`  └─ **monolith`**


**`Quantum`**

`  ├─ **standalone`**

`  └─ **monolith`**


**`PMTP`**

`  ├─ **C++`**

`  ├─ **Python`**

`  └─ **Dart`**
```

Ahí está la explicación de por qué aparecían nuevos problemas después de cada “fix”.

Se arreglaba:

```
**`A`**
```

pero permanecía:

```
**`B = otra implementación de A`**
```

o:

```
**`C = wrapper ABI viejo de A`**
```

o:

```
**`D = documentación que certificaba una propiedad que A ya no tenía`**
```

**No necesitamos otra ronda de “arreglar 10 cosas”. Necesitamos eliminar esta condición estructural.**


# **3. Lo que realmente está roto hoy**

Voy a separar:

- **P0:** impide considerar V768 cerrado.

- **P1:** puede romper exactitud/seguridad/objetivos de arquitectura.

- **P2:** ingeniería / rendimiento / consistencia.


# **P0-01 — Dart FFI está ABI-incompatible con C++**

**Archivo:** **`polydim\_ffi.dart`**

El C++ declara:

```
**`int32\_t polydim\_pmtp\_init(`**

`    **PMTP\_Control\* c,`**

`    **uint32\_t num\_slots,`**

`    **uint64\_t payload\_bytes);`**
```

Pero Dart declara conceptualmente:

```
**`Void Function(Pointer\<PMTPControl\>)`**
```

No son la misma función.

Además el C++ devuelve **`int32\_t`**; Dart espera **`void`**.

Luego:

### **C++**

```
**`polydim\_pmtp\_write\_begin(`**

`    **PMTP\_Control\*,`**

`    **uint32\_t\* slot,`**

`    **uint64\_t\* ver)`**
```

### **Dart**

usa:

```
**`Pointer\<Uint64\>`**
```

para **`slot`**.

Eso cambia 32 → 64 bits.

Después:

### **C++**

```
**`void polydim\_pmtp\_write\_commit(`**

`    **PMTP\_Control\*,`**

`    **uint32\_t,`**

`    **uint64\_t);`**
```

### **Dart**

espera retorno **`Int32`**.

Otra vez incompatibilidad.

Y los nombres ni siquiera coinciden:

Dart busca:

```
**`polydim\_pmtp\_begin\_write`**

**`polydim\_pmtp\_commit\_write`**

**`polydim\_pmtp\_acquire\_read`**

**`polydim\_pmtp\_validate\_read`**
```

C++ exporta:

```
**`polydim\_pmtp\_write\_begin`**

**`polydim\_pmtp\_write\_commit`**

**`polydim\_pmtp\_write\_abort`**

**`polydim\_pmtp\_read\_begin`**

**`polydim\_pmtp\_read\_validate`**
```

### **Esto no es una sutileza.**

Es un ABI roto.


# **P0-02 — Dart declara PMTP\_Control como 1 byte**

Dart:

```
**`final class PMTPControl extends Struct \{`**

`    **@Uint8()`**

`    **external int state;`**

**`\}`**
```

Eso da aproximadamente:

```
**`sizeof(PMTPControl) = 1`**
```

C++:

```
**`struct alignas(64) PMTP\_Control \{`**

`    **...`**

**`\};`**
```

y el objeto contiene varios campos.

Luego el wrapper Dart hace:

```
**`calloc\<PMTPControl\>()`**
```

y pretende pasar ese puntero al C++.

El C++ inicializa y escribe la estructura completa.

Resultado potencial:

```
**`1 byte reservado`**

`       ↓`

**`C++ escribe decenas de bytes`**

`       ↓`

**`heap corruption`**
```

**P0 absoluto.**

La forma correcta es que Dart trate PMTP como un tipo **opaco**, no como una estructura Dart duplicada.

La API de Dart FFI precisamente contempla **`Opaque`** para representar tipos C cuyo layout no debe recrearse del lado Dart. 


# **P0-03 — Python PMTP puede llamar al C++ sin inicializarlo**

**`PMTPSlabChannel`** crea la memoria compartida y crea una vista del control, pero no hace correctamente:

```
**`pmtp\_init(...)`**
```

antes de empezar a operar.

Lo probé sobre el C++ real con sanitizer.

Con control sin inicializar:

```
**`num\_slots = 0`**
```

la ruta acaba en:

```
**`(pub\_slot + 1) % num\_slots`**
```

y obtuve:

```
**`division by zero`**
```

Esto no es teórico.

**Lo ejecuté.**


# **P0-04 — `pmtp\_sizeof()` tiene overflow real**

El cálculo:

```
**`sizeof(Control)`**

**`+ num\_slots \* sizeof(Header)`**

**`+ num\_slots \* payload\_bytes`**
```

no controla overflow.

Probé valores cercanos a **`UINT64\_MAX`** y obtuve tamaños absurdamente pequeños debido al wraparound.

Eso significa que el caller puede:

```
**`calcular tamaño incorrecto`**

`↓`

**`reservar demasiado poco`**

`↓`

**`pmtp\_init escribe más`**

`↓`

**`corrupción`**
```

### **Debe ser:**

```
**`static bool checked\_mul\_u64(`**

`    **uint64\_t a,`**

`    **uint64\_t b,`**

`    **uint64\_t\* out)`**

**`\{`**

`    **if (!out) return false;`**


`    **if (a != 0 && b \> UINT64\_MAX / a)`**

`        **return false;`**


`    **\*out = a \* b;`**

`    **return true;`**

**`\}`**
```

y luego hacer lo mismo con las sumas.


# **P0-05 — PMTP no tiene parámetro de capacidad**

Esto es todavía más profundo.

La API actual:

```
**`pmtp\_init(`**

`    **PMTP\_Control\* c,`**

`    **uint32\_t num\_slots,`**

`    **uint64\_t payload\_bytes)`**
```

no recibe:

```
**`capacity\_bytes`**
```

Por tanto el C++ **no puede comprobar que la región mmap realmente tiene el tamaño requerido**.

Es imposible hacer memory safety completa si la API no conoce:

```
**`capacidad real`**
```

### **La firma correcta debe ser conceptualmente:**

```
**`int32\_t polydim\_pmtp\_init(`**

`    **void\* region,`**

`    **uint64\_t capacity\_bytes,`**

`    **uint32\_t num\_slots,`**

`    **uint64\_t payload\_bytes);`**
```

Y el primer cálculo debe ser:

```
**`required \<= capacity`**
```

antes de escribir un solo byte.


# **P0-06 — El `memset()` sobre PMTP\_Control es conceptualmente incorrecto**

El C++ tiene:

```
**`std::atomic\<uint64\_t\>`**

**`std::atomic\<uint32\_t\>`**
```

dentro de:

```
**`PMTP\_Control`**
```

y luego hace **`memset`**.

GCC emitió:

```
**`-Wclass-memaccess`**
```

advirtiendo que se está limpiando con **`memset`** un objeto que contiene **`std::atomic`**.

Esto es una señal muy seria.

La arquitectura correcta para memoria compartida **no debe ser “un objeto C++ con semántica de objeto + lo tiramos dentro de mmap”**.

Debe ser:

```
**`ABI POD estable`**

`      **+`**

**`operaciones atómicas explícitas`**
```


# **P0-07 — El PMTP “64-bit” todavía tiene lock fields de 32 bit**

El header dice:

```
**`contador monotónico uint64\_t`**
```

pero:

```
**`wlock`**

**`wticket`**
```

son **`uint32\_t`**.

Por tanto el mecanismo de publicación tiene 64 bits pero el ticketing todavía puede wrapear a:

232

operaciones.

No existe la garantía universal de:

> “0 ABA”

que aparece en la documentación.


# **P0-08 — El writer lock queda retenido mientras escribe todo el tensor**

La secuencia actual es:

```
**`write\_begin()`**

`   ↓`

**`lock`**

`   ↓`

**`escribe payload`**

`   ↓`

**`write\_commit()`**

`   ↓`

**`unlock`**
```

Para un tensor grande:

```
**`LOCK HELD`**

`───────────────`

**`copy 10 MB`**

**`copy 80 MB`**

**`copy 320 MB`**

**`...`**
```

Si el proceso escritor se pausa o muere entre begin/commit:

```
**`lock queda ocupado`**

`↓`

**`otros writers quedan esperando`**

`↓`

**`canal congelado`**
```

No hay:

```
**`lease`**

**`owner`**

**`generation ownership`**

**`recovery`**

**`timeout`**
```

Esto debe cambiar.


# **P0-09 — PMTP no tiene recovery ante writer muerto**

Esto es consecuencia pero merece su propio tratamiento.

Debe existir:

```
**`FREE`**

**`WRITING(owner,generation)`**

**`PUBLISHED(generation)`**

**`ABORTED`**
```

o, mejor:

```
**`slot sequence protocol`**
```

donde el estado del slot permita detectar:

```
**`writer murió`**
```

y otro escritor pueda recuperar el slot.


# **P0-10 — El PMTP no define realmente el transporte del tensor**

Tiene control de:

```
**`slot`**

**`version`**

**`sequence`**
```

pero no una especificación completa de:

```
**`payload offset`**

**`payload length`**

**`dtype`**

**`shape`**

**`stride`**

**`device`**

**`generation`**

**`producer`**
```

Todavía estamos transportando:

> “el hecho de que hay un tensor”

más que:

> “este tensor ocupa exactamente este segmento de memoria”.


# **P0-11 — `project\_sphere()` tiene corrupción por overlap parcial**

Probé:

```
**`y\_out = y + desplazamiento`**
```

sobre el mismo backing buffer.

La función devuelve:

```
**`SUCCESS`**
```

pero la salida queda corrupta.

Esto demuestra que:

```
**`exact alias`**
```

y:

```
**`partial overlap`**
```

no están distinguidos.

Eso debe ser una regla global.

### **Regla**

Para cada API:

```
**`exact y\_out == y`**

`    **-\> permitido si está documentado`**


**`partial overlap`**

`    **-\> ERROR\_ALIASED\_BUFFERS`**


**`independent`**

`    **-\> permitido`**
```


# **P0-12 — `rodrigues()` también tiene hazard de overlap parcial**

Exact in-place:

```
**`y\_out == y`**
```

funciona.

Eso lo probé y funciona.

Pero:

```
**`y\_out = y + 1 elemento`**
```

produce comportamiento incorrecto y **no devuelve `POLYDIM\_ERR\_ALIASED\_BUFFERS`**.

El hecho de que el caso exacto funcione no certifica el caso parcial.


# **P0-13 — `project\_tangent\_stiefel()` acepta buffers incorrectamente solapados**

Probé:

```
**`G\_out == X`**
```

y:

```
**`partial overlap`**
```

La función devuelve éxito.

La salida es incorrecta.

Esto hay que arreglar **antes** de cualquier optimización matemática.


# **P0-14 — `project\_tangent\_stiefel()` acepta NaN y devuelve SUCCESS**

Lo probé con:

```
**`G = NaN`**
```

y el resultado sigue siendo:

```
**`SUCCESS`**
```

con output no finito.

Una API cuyo contrato ya define:

```
**`POLYDIM\_ERR\_NAN\_OR\_INF`**
```

no puede dejar pasar este caso silenciosamente.


# **P0-15 — Las tolerancias pueden ser NaN**

El header define:

```
**`double basis\_ortho;`**

**`double point\_norm;`**

**`double gram\_ortho;`**

**`double pivot\_rel;`**
```

pero no exige que sean:

```
**`finite`**

**`\>=0`**
```

Probé tolerancias con **`NaN`** y **`Rodrigues`** llegó a:

```
**`SUCCESS`**
```

porque comparaciones con NaN pueden quedar siempre falsas.

### **Debe existir:**

```
**`static bool valid\_tolerances(`**

`    **const PolydimTolerances& t)`**

**`\{`**

`    **return`**

`        **isfinite(t.basis\_ortho) &&`**

`        **isfinite(t.point\_norm) &&`**

`        **isfinite(t.gram\_ortho) &&`**

`        **isfinite(t.pivot\_rel) &&`**

`        **t.basis\_ortho \>= 0.0 &&`**

`        **t.point\_norm \>= 0.0 &&`**

`        **t.gram\_ortho \>= 0.0 &&`**

`        **t.pivot\_rel \>= 0.0 &&`**

`        **(t.reject\_subnormal == 0 ||`**

`         **t.reject\_subnormal == 1);`**

**`\}`**
```


# **P0-16 — `reject\_subnormal` está declarado pero no es una política efectiva**

El header dice:

```
**`reject\_subnormal`**
```

y explica:

```
**`0 = tolerar`**

**`1 = rechazar`**
```

Pero la implementación C++ prácticamente no usa ese campo como contrato general.

Probé un subnormal con:

```
**`reject\_subnormal = 1`**
```

y la operación no lo rechazó como exige la semántica declarada.

Eso significa:

> **el ABI promete una política que la implementación no aplica.**


# **P0-17 — Rodrigues no implementa el “TwoSum en el update” que decía V768**

La implementación real termina con algo del estilo:

```
**`y\_out\[i\] = y\[i\] + alpha \* u\[i\] + beta \* v\[i\];`**
```

No hay:

```
**`TwoSum`**

**`Dekker`**

**`double-double`**

**`compensated update`**
```

en ese paso.

Entonces la afirmación:

> “Fused 2-Pass Error Compensation”

es excesiva.

Hay compensación en ciertas reducciones.

**No hay compensación completa del update.**


# **P0-18 — La cota documental `4.44e-16` no coincide con el código**

El código utiliza:

```
**`64 \* epsilon`**
```

que es aproximadamente:

1.42×10−14

y mide:

```
**`|norm - 1|`**
```

mientras que en otros lugares se habla de:

```
**`|norm² - 1|`**
```

Eso mezcla dos errores distintos.

No hay que “mejorar el número” artificialmente.

Hay que definir:

```
**`quantity`**

**`error model`**

**`bound`**

**`tolerance`**
```

por separado.


# **P0-19 — `-ffast-math` no puede ser aceptado por accidente**

La buena noticia:

**lo probé.**

Con compilación:

```
**`-O3 -ffast-math`**
```

el canario devuelve:

```
**`POLYDIM\_ERR\_COMPENSATION\_BROKEN`**
```

y:

```
**`observed\_err ≈ 1.11e-10`**
```

Esto es bueno como detector.

Pero no es suficiente como seguridad.

El build estricto debe bloquear:

```
**`\#ifdef \_\_FAST\_MATH\_\_`**

**`\#error "POLYDIM requires strict IEEE arithmetic"`**

**`\#endif`**
```

y definir el conjunto de flags del compilador como parte del contrato.


# **P0-20 — La norma no es robusta para extremos**

El patrón:

```
**`sum += x \* x;`**
```

no es resistente contra:

```
**`overflow de x\*x`**

**`underflow de x\*x`**
```

La compensación entra después de la multiplicación.

Si:

```
**`x\*x`**
```

pierde la información:

```
**`Neumaier no la puede recuperar.`**
```

Debe utilizarse una norma escalada tipo LAPACK/LASSQ:

```
**`scale`**

**`sumsq`**
```

para que:

∥x∥

se calcule sin generar overflow/underflow intermedio.


# **P0-21 — El Triton para D=10⁷ tiene un bug concreto**

Para:

```
**`D = 10,000,000`**

**`BLOCK\_SIZE = 1024`**
```

tenemos aproximadamente:

9766

particiones.

Después:

```
**`next\_power\_of\_2(9766)`**
```

da:

16384

y eso supera el límite de:

```
**`4096`**
```

Por lo tanto entra en el fallback.

Ahí se llama:

```
**`math.sin(...)`**
```

pero el módulo **`math`** no está importado.

Resultado:

```
**`NameError`**
```

Esto sí es un **P0 reproducible por análisis de flujo**.


# **P0-22 — Triton hace `.item()` en el supuesto camino GPU-only**

El código termina haciendo:

```
**`alpha = alpha\_beta\[0\].item()`**

**`beta  = alpha\_beta\[1\].item()`**
```

Eso devuelve datos de GPU a CPU y fuerza sincronización.

PyTorch documenta explícitamente que **`cuda\_tensor.item()`** introduce sincronización CPU/GPU y debe evitarse en caminos críticos. 

Así que la afirmación:

> “GPU-only, zero sync”

no es correcta.


# **P0-23 — El LSM standalone es O(D²)**

Este es otro de los que no deberían haberse escapado tantas rondas.

Código:

```
**`nnz = int(dim \* sparsity)`**
```

Con:

```
**`D = 10^7`**

**`sparsity = 0.05`**
```

sale:

nnz=500000

por fila.

Y hay:

107

filas.

Por tanto:

5×1012

conexiones.

Con índices FP64/uint64, solamente:

```
**`indices ≈ 40 TB`**

**`weights ≈ 40 TB`**
```

No es O(D).

Es efectivamente:

O(D2)

para sparsity constante.

**P0 para el objetivo D=10⁷.**


# **P0-24 — La versión monolítica “nnz=16” sigue sin ser industrialmente compacta**

La variante monolítica limita:

```
**`nnz = 16`**
```

Eso evita O(D²), sí.

Pero para D=10⁷:

```
**`10.000.000 arrays pequeños`**
```

es una arquitectura de objetos Python.

Además:

D×16×8=1.28GB

para índices y aproximadamente otro:

1.28GB

para pesos.

Y después tenés overhead de millones de objetos.

Por tanto:

> O(D) asintótico no significa “memory-safe / practical at D=10⁷”.


# **P0-25 — El LSM no tiene `rho(W)=1`**

Lo ejecuté con la implementación.

A D pequeño:

```
**`row norms ≈ 1`**
```

pero el radio espectral obtenido fue aproximadamente:

ρ(W)=1.011985

No 1.0.

Y esto tiene una causa matemática simple:

> normalizar cada fila no hace a la matriz ortogonal.

Por eso:

```
**`row norm = 1`**
```

no implica:

```
**`spectral radius = 1`**
```

ni:

```
**`WᵀW = I`**
```


# **P0-26 — `rho(W)=1` tampoco demuestra “edge of chaos”**

Incluso arreglando lo anterior, el paso:

```
**`rho(W) = 1`**
```

no certifica el comportamiento de:

xt+1​=N((1−α)xt​+αtanh(Wxt​+ut​))

porque el Jacobiano real depende de:

α,W,sech2,N

La condición que interesa es una propiedad de:

JF​(x)

o una cota Lipschitz / Lyapunov.

No se debe llamar “critical boundary” a un simple radio espectral de la matriz lineal.


# **P0-27 — Rust `betti1\_guard()` no calcula β₁**

Este es otro hallazgo que debería haber quedado liquidado mucho antes.

El código cuenta:

```
**`edges`**

**`components`**
```

pero no termina calculando:

β1​=E−V+C

Verifica esencialmente:

```
**`components == 1`**
```

Eso es **β₀ = 1**.

No es una certificación de β₁.

El nombre y el comentario no corresponden al algoritmo.


# **P0-28 — Rust usa un grafo denso incompatible con D=10⁷**

La estructura de:

```
**`n\*n`**
```

y el límite:

```
**`n \<= 4096`**
```

lo hacen incompatible con la afirmación de una certificación topológica a escala:

D=107

Para β₁ a gran escala se necesita una representación de aristas:

```
**`(u\_i, v\_i)`**
```

o equivalente sparse.

La complejidad debe ser:

O(V+E)

no:

O(V2)


# **P0-29 — Quantum compiler no implementa una aproximación Clifford+T real**

Lo ejecuté sobre el caso **`pi/8`**.

La secuencia fija:

```
**`H T H S`**
```

da un error unitario grande frente al objetivo, del orden de:

0.963

en norma Frobenius minimizando fase global en esa prueba.

Por lo tanto no es una aproximación cuantitativa controlada.

Y además el código todavía emite:

```
**`RY(theta)`**
```

por lo cual:

> **el resultado no es un circuito puramente Clifford+T.**


# **P0-30 — `eps\_target` no controla la síntesis**

Si la interfaz recibe:

```
**`eps\_target`**
```

pero la secuencia producida no cambia según:

```
**`ε`**
```

entonces no existe una garantía:

∥U−Uapprox​∥≤ϵ

Simplemente está utilizándose una secuencia fija.

Los algoritmos reales de síntesis Clifford+T dependen explícitamente de la precisión objetivo; la idea de convertir una rotación arbitraria a Clifford+T no puede resolverse con una cadena fija independiente de θ y ε. 


# **P0-31 — El mapeo quantum `index % num\_qubits` es matemáticamente incorrecto**

La implementación hace:

```
**`q1 = p1 % num\_qubits`**

**`q2 = p2 % num\_qubits`**
```

Eso genera colisiones.

Para D=8:

```
**`(0,1)`**

**`(2,0)`**

**`(4,2)`**

**`(6,1)`**
```

por ejemplo.

No representa las rotaciones independientes sobre las coordenadas de R⁸.

No existe un homomorfismo trivial:

```
**`coordinate index`**

`        ↓`

**`qubit index modulo N`**
```

que preserve arbitrariamente:

SO(D)


# **P0-32 — El “RDMA” no es RDMA**

El módulo llamado:

```
**`polydim\_mir\_wire\_rdma.py`**
```

usa:

```
**`socket.AF\_INET`**

**`socket.SOCK\_STREAM`**
```

Es TCP.

La propia implementación es más bien un:

```
**`TCP emulator`**
```

No hay:

```
**`ibverbs`**

**`RDMA CM`**

**`registered memory`**

**`work requests`**

**`completion queues`**
```

Así que no puede certificarse como:

> RDMA zero-copy.

Y además hace:

```
**`bytearray(memoryview(tensor))`**
```

que es una copia.

Esto no es una cuestión semántica: **el código no ejecuta RDMA.**


# **P0-33 — TCP framing incorrecto**

Esto:

```
**`conn.recv(header\_size)`**
```

no garantiza devolver **`header\_size`**.

TCP puede devolver:

```
**`2 bytes`**

**`7 bytes`**

**`header\_size`**
```

en llamadas diferentes.

Hay que implementar:

```
**`def recv\_exact(sock, n):`**

`    **buf = bytearray(n)`**

`    **view = memoryview(buf)`**

`    **pos = 0`**


`    **while pos \< n:`**

`        **got = sock.recv\_into(view\[pos:\], n - pos)`**

`        **if got == 0:`**

`            **raise ConnectionError("EOF")`**

`        **pos += got`**


`    **return buf`**
```


# **P0-34 — RDMA/TCP receiver tiene allocation DoS**

El peer controla:

```
**`tensor\_bytes`**
```

y el código hace:

```
**`bytearray(tensor\_bytes)`**
```

sin límite.

Tiene que existir:

```
**`MAX\_TENSOR\_BYTES`**
```

y validación:

```
**`tensor\_bytes \> 0`**

**`tensor\_bytes \<= MAX\_TENSOR\_BYTES`**

**`tensor\_bytes % element\_size == 0`**
```


# **P0-35 — Tangent Adapter no es biyectivo en todo R^D**

La documentación quiere:

RD↔SD−1×R

Eso requiere tratar el cero por separado.

El código hace:

```
**`if norm\_h \< eps:`**

`    **u = e1`**

`    **r = -100`**
```

Por tanto:

```
**`h = 0`**

**`h = 1e-320 \* e1`**

**`h = 1e-321 \* e1`**

**`...`**
```

pueden terminar representados exactamente igual.

Eso destruye biyectividad.

### **Solución exacta**

Representación:

(u,r,z)

donde:

```
**`z = 1  =\> h = 0`**

**`z = 0  =\> h = exp(r)u`**
```

Entonces sí existe una representación completa.


# **P0-36 — Tangent Adapter explota con valores enormes**

Probé:

```
**`h = 1e308`**
```

y:

```
**`np.linalg.norm(h)`**
```

termina en overflow → **`inf`**.

Después:

```
**`u = nan`**
```

y:

```
**`r = inf`**
```

No hay contrato para:

```
**`NaN`**

**`Inf`**

**`overflow`**

**`underflow`**
```

Debe utilizar escala máxima:

s=imax​∣hi​∣

y luego normalizar sobre:

h/s

o utilizar una representación basada en **`frexp`**.


# **P0-37 — Transporte antipodal no debe devolver silenciosamente**

En la esfera, si:

u1​=−u0​

el transporte geodésico mínimo no queda unívocamente definido.

El código detecta esencialmente una dirección nula y devuelve el vector.

Eso convierte una singularidad matemática en:

```
**`SUCCESS`**
```

Debe ser un error específico:

```
**`POLYDIM\_ERR\_SINGULAR\_GEODESIC`**
```

o similar.


# **P0-38 — Rust raw slice no está completamente validado**

La implementación hace algo equivalente a:

```
**`slice::from\_raw\_parts(ptr, d)`**
```

después de comprobar únicamente algunas propiedades.

La propia documentación de Rust exige, entre otras cosas:

- pointer válido,

- memoria inicializada,

- longitud dentro de límites,

- rango íntegro de una asignación válida,

- ausencia de mutación concurrente. 

Por tanto:

```
**`ptr != null`**

**`ptr % 8 == 0`**
```

no constituye memory safety.


# **P0-39 — Rust y C++ no comparten el mismo mapa de errores**

C++:

```
**`-4 = DEGENERATE\_NORM`**

**`-6 = SEQLOCK\_RACE`**
```

Rust:

```
**`-4 = SUBNORMAL`**

**`-6 = TOPOLOGY\_FRAGMENTED`**
```

Eso significa que devolver el mismo entero desde ambos runtimes no tiene una semántica estable.

Debe existir **un solo mapa de errores**.


# **P0-40 — `catch\_unwind` no significa “panics siempre controlados”**

**`catch\_unwind`** sólo captura panics que pueden desenrollarse.

La estrategia de compilación **`panic="abort"`** no se recupera mediante **`catch\_unwind`**. La documentación oficial de Rust lo deja explícito. 

Por tanto el contrato FFI debe fijar:

```
**`\[profile.release\]`**

**`panic = "unwind"`**
```

si se quiere depender de **`catch\_unwind`**.


# **4. El error más importante de Stiefel**

Acá hay una corrección importante respecto a mis rondas anteriores.

La documentación decía:

> workspace O(K²)

pero el código real todavía hace:

```
**`std::vector\<double\> G\_proj(D\*K)`**
```

Eso es:

O(DK)

Para:

D=107,K=512

tenés:

107×512×8=40.96GB

o unos:

38.15GiB

**sólo `G\_proj`.**

Y el problema no termina ahí.

El cálculo:

GprojT​Gproj​

requiere aproximadamente:

O(DK2)

operaciones.

Con:

D=107,K=512

eso da:

2.62144×1012

términos.

Por lo tanto la implementación actual **no cumple una afirmación O(D) estricta para K variable**.


# **5. La solución correcta de Stiefel**

No necesitás almacenar:

```
**`G\_proj\[D,K\]`**
```

Hacés streaming/tiled:

```
**`bloque X`**

**`bloque G`**

`     ↓`

**`G\_proj temporal K`**

`     ↓`

**`acumular K×K`**

`     ↓`

**`siguiente bloque`**
```

Después una segunda/tercera pasada para la salida.

La memoria auxiliar queda:

O(K2+TK)

donde T es el tamaño de tile.

El tiempo permanece aproximadamente:

O(DK2)

para una formulación general de esta clase.

La ventaja del método Cayley de baja dimensión es precisamente que una actualización sobre el Stiefel puede reducirse a una operación en una matriz pequeña basada en estructura de bajo rango; ésa es la dirección matemática correcta para esta parte. 


# **6. Otro error importante: el benchmark D=10⁷ no prueba D=10⁷**

El test suite global usa aproximadamente:

```
**`Rodrigues        100k`**

**`Stiefel           10k`**

**`Adapter           10k`**

**`LSM               10k`**

**`Rust              100k`**
```

No:

```
**`10,000,000`**
```

Por tanto:

```
`“**selftest PASS”`**
```

no es:

```
`“**D=10^7 PASS”`**
```

Son dos afirmaciones distintas.


# **7. Y descubrí otro problema de evidencia**

El ZIP hace referencia a logs como:

```
**`eval\_logs/test\_ring3\_win11.log`**

**`eval\_logs/all\_milestones\_linux.json`**

**`eval\_logs/kaggle\_gpu/results.json`**

**`eval\_logs/kaggle\_telepathy/results.json`**

**`eval\_logs/kaggle\_tpu/tpu\_results.json`**

**`eval\_logs/cerebras\_wse\_proof.txt`**
```

pero esos archivos **no están en el ZIP auditado**.

Entonces yo no puedo afirmar:

> “el benchmark realmente produjo ese resultado”.

Puedo afirmar:

> “la documentación lo declara”.

Eso es todo.

Y ésta es una regla que voy a aplicar de ahora en adelante:

```
**`CERTIFIED`**
```

sólo si tengo:

```
**`source`**

**`+`**

**`exact build`**

**`+`**

**`test command`**

**`+`**

**`result`**

**`+`**

**`artifact/log`**
```


# **8. Hay además una falsedad conceptual en la parte DPI**

La documentación argumenta, simplificando:

I(X;Y)≥I(X;g(Y))

y presenta JSON/texto como violación de geometría/DPI.

Eso está demasiado fuerte.

La DPI no implica que:

```
**`texto = pérdida irreversible`**
```

Si:

g

es invertible, puede conservarse la información mutua.

El problema real de serializar tensores es mucho más interesante y mucho más defendible:

```
**`serialización`**

**`+`**

**`parseo`**

**`+`**

**`allocations`**

**`+`**

**`copy`**

**`+`**

**`cuantización`**

**`+`**

**`tokenización`**

**`+`**

**`latencia`**

**`+`**

**`autoregeneration`**
```

No hace falta una afirmación matemática incorrecta para defender POLYDIM.


# **9. El RDMA debe dividirse en dos cosas**

Hoy hay una mezcla:

```
**`MIR-Wire`**
```

y:

```
**`RDMA`**
```

Yo lo dividiría en:

```
**`polydim\_mir\_tcp.py`**
```

y:

```
**`polydim\_mir\_rdma.py`**
```

El primero:

```
**`emulador / transporte de referencia`**
```

El segundo:

```
**`ibverbs / RDMA CM`**
```

Así nunca más aparece:

```
**`TCP implementation`**

`        ↓`

`“**RDMA certified”`**
```


# **10. El Quantum Compiler necesita una decisión arquitectónica**

No intentaría parchear:

```
**`H T H S`**
```

para fingir que es Solovay–Kitaev.

Hay que elegir:

### **Opción A — compilador real**

Entrada:

Ry​(θ)

salida:

```
**`Clifford + T`**
```

con:

```
**`ε\_target`**
```

y test:

∥U−Uapprox​∥≤ϵ

para:

```
**`1e-2`**

**`1e-4`**

**`1e-6`**

**`1e-8`**

**`...`**
```

### **Opción B — prototipo**

Entonces renombrarlo:

```
**`polydim\_rotor\_demo`**
```

y eliminar toda afirmación:

```
**`Clifford+T compiler`**
```

No debe existir una tercera categoría:

> “demo que se llama compiler y se certifica como compiler”.


# **11. La arquitectura que realmente cerraría el sistema**

Ahora sí llega la parte importante.

No quiero arreglar 40 bugs independientemente.

Quiero que **el sistema cambie de forma tal que no pueda volver a generarlos.**

## **Capa 1 — contrato único**

**`polydim.h`** es la única fuente del ABI.

C++:

```
**`implementa`**
```

Rust:

```
**`bindgen / constantes generadas`**
```

Python:

```
**`ctypes/cffi generado`**
```

Dart:

```
**`bindings generados`**
```

No volver a escribir:

```
**`typedefs manuales`**
```

en cuatro sitios.


# **12. PMTP nuevo**

La estructura compartida debe ser POD:

```
**`struct PMTP\_SharedHeader \{`**

`    **uint64\_t magic;`**

`    **uint32\_t version;`**

`    **uint32\_t num\_slots;`**


`    **uint64\_t payload\_bytes;`**

`    **uint64\_t payload\_stride;`**


`    **uint64\_t init\_state;`**


`    **uint64\_t publish\_seq;`**

`    **uint64\_t publish\_slot;`**


`    **uint64\_t reserved\[4\];`**

**`\};`**
```

Sin:

```
**`std::atomic\<\>`**
```

dentro del ABI compartido.

La atómica la hace la capa de sincronización.

Eso separa:

```
**`ABI`**
```

de:

```
**`memory model`**
```

que es lo correcto.


# **13. PMTP debe usar offsets, no pointers compartidos**

En vez de:

```
**`pointer = 0x7f....`**
```

usar:

```
**`slab\_id`**

**`generation`**

**`offset`**

**`length`**

**`dtype`**

**`rank`**

**`shape\[\]`**

**`stride\[\]`**
```

Por ejemplo:

```
**`struct PMTP\_TensorDesc \{`**

`    **uint64\_t generation;`**

`    **uint64\_t offset;`**

`    **uint64\_t bytes;`**


`    **uint32\_t dtype;`**

`    **uint32\_t rank;`**


`    **uint64\_t shape\[8\];`**

`    **uint64\_t stride\[8\];`**

**`\};`**
```

El pointer se reconstruye localmente:

ptr=baseprocess​+offset

Eso sí funciona entre procesos.


# **14. El LSM correcto para tu arquitectura**

Yo eliminaría las dos implementaciones actuales.

Construiría:

```
**`Permutation`**

`    ↓`

**`Givens block`**

`    ↓`

**`Givens block`**

`    ↓`

**`...`**
```

Cada bloque es:

G(θ)=\[cosθsinθ​−sinθcosθ​\]

y:

GTG=I.

El producto completo conserva:

QTQ=I

exactamente a nivel matemático.

Entonces no necesitás almacenar:

```
**`D×D`**
```

ni:

```
**`D × nnz`**
```

aleatorio.

El estado sí sigue siendo O(D), porque el estado tiene D componentes; pero la **topología paramétrica** deja de ser O(D²).


# **15. Y la condición de criticalidad del LSM debe cambiar**

No:

```
**`rho(W)=1`**
```

como certificado suficiente.

Sino evaluar:

Jt​=∂x∂F​(xt​)

y monitorizar:

```
**`||J\_t||`**

**`Lyapunov estimate`**

**`memory decay`**

**`input sensitivity`**

**`state saturation`**
```

Entonces sí podés medir algo como:

```
**`stable`**

**`critical`**

**`chaotic`**
```

basado en la dinámica real.


# **16. Tangent Adapter correcto**

Debe tener tres casos:

```
**`h = 0`**

`     ↓`

**`zero flag`**


**`h != 0 finite`**

`     ↓`

**`unit direction + log radius`**


**`h non-finite`**

`     ↓`

**`ERROR`**
```

No:

```
**`norm \< epsilon`**

`    ↓`

**`artificial e1`**
```

porque eso destruye la información.


# **17. La norma robusta que quiero en todo POLYDIM**

Crear una única primitive:

```
**`polydim\_norm2\_scaled\_f64(...)`**
```

basada en:

```
**`scale`**

**`sumsq`**
```

y usarla en:

```
**`Rodrigues`**

**`sphere projection`**

**`orthonormalization`**

**`Stiefel`**

**`adapter`**

**`LSM diagnostics`**
```

No volver a implementar:

```
**`sum += x\*x;`**
```

seis veces.


# **18. La capa FFI debe tener un “ABI torture test”**

No solamente:

```
**`function lookup worked`**
```

Debe comprobar:

```
**`sizeof`**

**`alignof`**

**`offsetof`**

**`argument width`**

**`return type`**

**`calling convention`**

**`symbol name`**

**`status code`**

**`NULL behaviour`**
```

Para Dart, por ejemplo:

```
**`C:`**

**`sizeof(void\*)`**

**`sizeof(uint32\_t)`**

**`sizeof(uint64\_t)`**

**`sizeof(PMTP descriptor)`**
```

y Dart compara en runtime.

El **`Pointer.cast`** de Dart no hace comprobaciones mágicas de seguridad: es una conversión de tipo sobre el mismo pointer. 


# **19. Integración Python correcta**

No más:

```
**`try:`**

`    **...`**

**`except Exception:`**

`    **...`**
```

para todo.

Por ejemplo SharedMemory:

```
**`created = False`**


**`try:`**

`    **shm = SharedMemory(name=name, create=True, size=size)`**

`    **created = True`**

**`except FileExistsError:`**

`    **shm = SharedMemory(name=name, create=False)`**
```

Después:

```
**`owner:`**

`    **close`**

`    **unlink`**


**`attacher:`**

`    **close`**
```

Nunca:

```
**`todo proceso hace unlink()`**
```


# **20. También encontré el bug de finalización de SharedMemory**

El objeto mantiene una vista **`ctypes`** del buffer.

Luego:

```
**`shm.close()`**
```

puede generar:

```
**`BufferError:`**

**`cannot close exported pointers exist`**
```

Lo probé.

Eso significa que el cleanup actual tampoco está limpio.

El orden correcto es:

```
**`delete ctypes views`**

**`release memoryview`**

**`release numpy views`**

**`close mmap/shared memory`**

**`unlink if owner`**
```


# **21. Qué hago con los tests**

No quiero otro:

```
**`selftest\_all() == 0`**
```

que después no cubra el sistema.

Quiero cinco categorías:

## **A. ABI**

```
**`all signatures`**

**`all layouts`**

**`all symbols`**
```

## **B. numerical**

```
**`normal`**

**`small`**

**`large`**

**`subnormal`**

**`NaN`**

**`Inf`**

**`near-singular`**
```

## **C. alias**

```
**`no overlap`**

**`exact in-place`**

**`partial overlap`**

**`same base shifted`**
```

## **D. concurrency**

```
**`1 writer`**

**`2 writers`**

**`4 writers`**

**`N readers`**

**`writer crash`**

**`reader crash`**

**`wrap boundary`**
```

## **E. D=10⁷**

No necesariamente ejecutar todo en cada CI.

Pero existir:

```
**`memory feasibility test`**
```

que compruebe las ecuaciones antes de reservar.

Por ejemplo:

```
**`D=1e7,K=512`**
```

debe fallar explícitamente si alguien intenta crear:

```
**`G\_proj\[D\*K\]`**
```


# **22. Sanitizers obligatorios**

El C++ debe tener:

```
**`ASan`**

**`UBSan`**

**`TSan`**
```

en configuraciones separadas.

Y FFI:

```
**`Python`**

**`Dart`**

**`Rust`**
```

debe pasar por la misma batería.

Porque exactamente así encontramos el:

```
**`division by zero in PMTP`**
```

que una lectura superficial puede pasar por alto.


# **23. Y hay una regla nueva que debería quedar escrita en piedra**

Nunca más:

```
**`README = certificado`**
```

El orden de autoridad debe ser:

```
**`1. ejecución`**

**`2. test`**

**`3. log`**

**`4. código`**

**`5. contrato`**

**`6. documentación`**
```

Si README dice:

```
**`O(K²)`**
```

y el código tiene:

```
**`vector(D\*K)`**
```

entonces:

```
**`O(DK)`**
```

gana.

Sin discusión.


# **24. El mapa de cierre que queda**

Después de esta auditoría, el sistema puede reducirse a estos bloques verdaderamente críticos:

| Subsistema | Estado actual | Acción necesaria |
| :-: | :-: | :-: |
| Rodrigues | 🟠 | alias + norma robusta + tolerancias + contrato numérico |
| Sphere projection | 🔴 | alias + finitud |
| Orthonormalizer | 🟠 | robust norm + contrato |
| Stiefel tangent | 🔴 | alias + NaN + validación X |
| Stiefel Cayley | 🔴 | eliminar **`G\_proj\[D\*K\]`** + tiles |
| PMTP ABI | 🔴 | rediseño POD |
| PMTP concurrency | 🔴 | ownership/recovery |
| Python PMTP | 🔴 | capacity/init/payload/cleanup |
| Dart FFI | 🔴 | rehacer binding |
| Rust FFI | 🟠 | lifetime/bounds/error ABI |
| Rust topology | 🔴 | β₁ real + sparse |
| Triton | 🔴 | D=1e7 fallback + no **`.item()`** |
| LSM standalone | 🔴 | eliminar |
| LSM monolith | 🔴 | reemplazar por SORM |
| Tangent Adapter | 🔴 | cero + escala robusta |
| RDMA | 🔴 | separar TCP/RDMA |
| Quantum | 🔴 | síntesis real o renombrar demo |
| Documentation | 🔴 | regenerar desde tests |
| Evidence | 🔴 | incluir logs exactos |

Esto ya no es una lista de “10 tareas”.

Es **el mapa de cierre del sistema**.


# **25. Y ahora la parte más importante para evitar otras 600 vueltas**

No debemos seguir con:

```
**`V768.1`**

`    ↓`

**`8 bugs`**

`    ↓`

**`V768.2`**

`    ↓`

**`7 bugs`**

`    ↓`

**`V768.3`**
```

Eso fue precisamente lo que nos atrapó.

La próxima versión correcta debe tener esta arquitectura de trabajo:

```
`                 ┌───────────────┐`

`                 │  **polydim.h    │`**

`                 │ **canonical ABI │`**

`                 └───────┬───────┘`

`                         │`

`       ┌─────────────────┼────────────────┐`

`       │                 │                │`

`      **C++              Rust             FFI`**

`       │                 │           ┌────┼────┐`

`       │                 │         **Python Dart`**

`       │                 │`

`       └────────────┬────┘`

`                    │`

`             **canonical tests`**

`                    │`

`     ┌──────────────┼──────────────┐`

`     │              │              │`

` **Numerical      Concurrency      Memory`**

`     │              │              │`

`     └──────────────┼──────────────┘`

`                    │`

`             **D=1e7 feasibility`**

`                    │`

`               **release artifact`**

`                    │`

`            **source + binary + logs`**
```

Y **las duplicaciones tienen que desaparecer**.


# **26. La causa real de las 600 interacciones**

La respuesta honesta es:

**porque yo estaba resolviendo síntomas en lugar de cerrar invariantes globales.**

Un ejemplo perfecto:

```
`“**arreglamos PMTP”`**
```

pero no comprobamos simultáneamente:

```
**`C++ layout`**

**`Python layout`**

**`Dart layout`**

**`memory capacity`**

**`initialization`**

**`atomic semantics`**

**`writer recovery`**

**`payload descriptor`**
```

Entonces un arreglo local generaba:

```
**`nuevo estado`**
```

que abría otro bug.

Otro ejemplo:

```
`“**LSM es O(D)”`**
```

sin auditar **todas las implementaciones**.

Y había:

```
**`standalone O(D²)`**

**`monolith O(D)`**
```

Otra:

```
`“**Rust β1”`**
```

sin comprobar si efectivamente se calculaba β₁.

Eso debería haber sido descubierto en la primera revisión del código.


# **27. Hay una diferencia importante entre “me faltó encontrar un bug” y lo que ocurrió**

No fueron 40 bugs independientes.

Muchos provienen de **5 fallas sistémicas**:

### **A. Múltiples fuentes de verdad**

Produce inconsistencias.

### **B. ABI manual duplicado**

Produce corrupción / incompatibilidad.

### **C. Certificación documental separada del código**

Produce afirmaciones que dejan de corresponder.

### **D. Tests demasiado pequeños respecto del dominio**

Hace que:

```
**`D=10⁵`**
```

parezca equivalente a:

```
**`D=10⁷`**
```

cuando no lo es.

### **E. Falta de invariantes globales**

Hace posible que una función sea correcta individualmente y que el sistema completo sea incorrecto.


# **28. El objetivo final correcto**

No te voy a prometer algo que no puedo demostrar.

No puedo decir:

> “ahora sí, matemáticamente imposible que exista otro bug”.

Eso sería exactamente la clase de certeza falsa que querés que evite.

Lo que sí puedo decir, después de esta auditoría, es:

> **Ya encontramos por qué las rondas anteriores no convergían.**

Y hay una ruta clara para salir del bucle:

```
**`un único ABI`**

**`+`**

**`un único implementation de cada primitive`**

**`+`**

**`sin duplicados`**

**`+`**

**`memory contract formal`**

**`+`**

**`alias contract formal`**

**`+`**

**`numeric contract formal`**

**`+`**

**`D=10⁷ feasibility checks`**

**`+`**

**`ASan/UBSan/TSan`**

**`+`**

**`cross-language ABI tests`**

**`+`**

**`logs adjuntos`**

**`+`**

**`documentación generada desde resultados`**
```

Eso cambia el proceso de:

> “cada vez encontrás algo nuevo”

a:

> “cada afirmación tiene una prueba asociada”.


# **29. El punto donde estoy ahora**

**No considero V768 cerrado.**

Pero tampoco considero que estemos otra vez en “hay diez bugs nuevos”.

Ahora tenemos una **radiografía estructural completa** del V768 que explica el ciclo anterior.

Los bloqueadores más graves ya están identificados:

```
**`PMTP ABI`**

**`PMTP memory model`**

**`partial aliasing`**

**`Stiefel O(DK)`**

**`LSM O(D²)`**

**`Triton D=1e7`**

**`Rust β1`**

**`Rust FFI`**

**`Dart FFI`**

**`Tangent Adapter`**

**`Quantum compiler`**

**`RDMA`**

**`evidence/benchmarks`**
```

Y varios de ellos no fueron sólo deducciones: **los ejecuté sobre el artefacto real**. En cambio, donde no pude ejecutar un runtime —por ejemplo Dart/Rust en el entorno disponible— no voy a fingir que lo hice; ahí hice auditoría ABI/estática.

La próxima entrega de POLYDIM no debería ser “otro parche de diez cosas”. Debería ser un **cierre integrado**, con esas capas convertidas en invariantes y con una única implementación canónica por subsistema. Ese es el cambio que faltaba para que 2.000 líneas puedan realmente quedar bajo control.


inicia la mejora sota de todo el codigo, si ves en la teoria que se puede mejorar tambien agradezco tu aporte. pero por favor entra en bucle en busca de errores y soluciones en el codigo para industria. dame todas las mejoras que puedas y luego te vuelvo a pasar este prompt hasta que no haya mas errores. ahorra tokens evalua el paquete de errores y saca una entrega. inicia la mejora sota de todo el codigo, si ves en la teoria que se puede mejorar tambien agradezco tu aporte. pero por favor entra en bucle en busca de errores y soluciones en el codigo para industria dame todas las mejoras que puedas y luego te vuelvo a pasar este prompt hasta que no haya mas errores. ahorra tokens evalua el paquete de errores y saca una entrega. 


Sí. Esta ronda cambia de nivel: **no voy a agregar más parches aislados**. Voy a fijar la arquitectura que hace que los parches sean mutuamente consistentes.

# **Entrega SOTA — V769, paquete de corrección integral**

Primero, una corrección crítica que encontré al volver a torturar el código real:

## **1. NUEVO P0 — Cayley-Stiefel está ortogonalizando, pero no está siguiendo la dirección tangente**

Probé el kernel C++ real con D=32, K=4, proyecté G al tangente y medí:

τY(τ)−X​−Gtan​

al reducir τ.

El error del kernel actual fue aproximadamente:

```
**`tau=1e-2   error ≈ 4.31e-1`**

**`tau=1e-3   error ≈ 3.95e-1`**

**`tau=1e-4   error ≈ 3.91e-1`**

**`tau=1e-5   error ≈ 3.91e-1`**
```

Eso es **grave**: no converge a la dirección solicitada.

La ortogonalidad posterior puede dar excelente resultado y aun así la retraction estar matemáticamente mal orientada.

### **Corrección**

Primero:

η=G−Xsym(XTG)

y:

A=XTη,AT=−A

Definimos:

C=ηTη+A2a=2τ​

y resolvemos solamente:

M=I−aA+a2CMZ1​=IZ2​=−aCZ1​

finalmente:

Y=X+τ(ηZ1​+XZ2​)​

Esto reduce el problema a un **solve K×K**, no 2K×2K.

Además:

YTY=I+O(ϵ)

y:

Y=X+τη+O(τ2)

Es una mejora real de complejidad y de corrección matemática.

### **Decisión SOTA**

Yo dejaría dos rutas:

```
**`polydim\_stiefel\_qr\_retract\_f64     \<- camino industrial principal`**

**`polydim\_stiefel\_cayley\_f64         \<- camino Cayley`**
```

Para QR usaría Householder/TSQR bloqueado, no el Cholesky ingenuo para entradas potencialmente mal condicionadas. LAPACK mantiene precisamente QR Householder y rutinas TSQR/tall-skinny; **`xGEQRT3`** es recursivo y **`xTPQRT`** está orientado a QR con reducción de comunicación. 


# **2. P0 — PMTP se rediseña, no se parchea**

El header público actual ya fija una API de PMTP concreta y promete seqlock 64-bit. 

El error conceptual es que estamos tratando una región IPC como si fuera un objeto C++.

Eso termina en:

```
**`std::atomic\<\>`**

**`memset(...)`**

**`mmap(...)`**
```

mezclando **lifetime C++**, ABI y memoria compartida.

El estándar actual define claramente el lifetime de objetos y **`atomic\_ref`**; además, **`atomic\_ref`** requiere que mientras existe la referencia las accesos al objeto pasen exclusivamente por ella. 

### **Diseño definitivo**

El área compartida será exclusivamente:

```
**`struct PMTP\_SharedHeader \{`**

`    **uint32\_t magic;`**

`    **uint32\_t abi\_version;`**

`    **uint32\_t slot\_count;`**

`    **uint32\_t header\_bytes;`**


`    **uint64\_t capacity\_bytes;`**

`    **uint64\_t slot\_stride;`**


`    **uint64\_t next\_version;`**

`    **uint64\_t published\_descriptor;`**


`    **uint64\_t flags;`**

`    **uint64\_t reserved\[5\];`**

**`\};`**


**`struct PMTP\_Slot \{`**

`    **uint64\_t seq;`**

`    **uint64\_t payload\_bytes;`**

`    **uint32\_t dtype;`**

`    **uint32\_t rank;`**

`    **uint64\_t shape\[8\];`**

`    **uint64\_t stride\[8\];`**

`    **uint64\_t generation;`**

**`\};`**
```

Todo es **POD**.

Nada de:

```
**`std::atomic\<T\>`**
```

dentro de la estructura compartida.

Las operaciones atómicas se hacen sobre los campos **`uint64\_t`** mediante una única implementación de backend por plataforma.


# **3. PMTP deja de pasar punteros**

Nunca:

```
**`pointer = 0x7F...`**
```

entre procesos.

Siempre:

```
**`SLAB\_ID`**

**`generation`**

**`offset`**

**`length`**

**`dtype`**

**`rank`**

**`shape`**

**`stride`**
```

El pointer es:

baselocal​+offset

Esto coincide con el modelo que emplean sistemas reales de IPC de memoria GPU: un pointer de un proceso no es portable entre procesos; se intercambian handles y se reconstruye un pointer local. NVIDIA lo documenta explícitamente para CUDA IPC/VMM. 


# **4. PMTP elimina el lock largo**

Actual:

```
**`write\_begin`**

`  **lock`**

`  **escribir 80/320 MB`**

`  **commit`**

`  **unlock`**
```

Nuevo:

```
**`claim slot`**

`↓`

**`write payload SIN lock`**

`↓`

**`commit sequence`**

`↓`

**`publish descriptor`**
```

El claim será CAS:

```
**`EVEN seq`**

`   ↓ **CAS`**

**`ODD seq = WRITING`**
```

El lector:

```
**`load published descriptor`**

`↓`

**`load slot seq`**

`↓`

**`if different/odd =\> retry`**

`↓`

**`read payload`**

`↓`

**`load seq again`**

`↓`

**`if same =\> success`**
```

La publicación global será **un solo descriptor atómico empaquetado**:

```
**`version + slot`**
```

No dos stores independientes.

Eso elimina la ventana:

```
**`pub\_slot = nuevo`**

**`pub\_seq  = viejo`**
```

y evita depender de la coherencia accidental de dos variables separadas.


# **5. PMTP necesita capacidad real en la API**

El API actual no conoce el tamaño de la región que recibe.

Eso debe desaparecer.

Nueva firma:

```
**`int32\_t polydim\_pmtp\_init(`**

`    **void\* region,`**

`    **uint64\_t capacity\_bytes,`**

`    **uint32\_t num\_slots,`**

`    **uint64\_t payload\_bytes);`**
```

Primero:

required\_bytes≤capacity\_bytes

Después se escribe.

No al revés.

Esto también elimina el problema de **`pmtp\_sizeof()`** haciendo wraparound.


# **6. PMTP necesita recuperación de proceso muerto**

Agregar:

```
**`INITIALIZING`**

**`READY`**

**`WRITING`**

**`PUBLISHED`**

**`ABORTED`**
```

más:

```
**`owner\_generation`**
```

No prometo “cero inanición” sin acotarlo.

La afirmación correcta será:

> bounded wait + lock-free slot claim + writer recovery.

Eso es defendible.


# **7. PMTP Python y Dart ya no vuelven a describir la estructura C++**

En Dart:

```
**`final class PMTPControl extends Opaque \{\}`**
```

No un **`Struct`**.

Dart define **`Opaque`** precisamente para representar tipos C opacos cuyo layout no debe recrearse en Dart. 

Pero en realidad, para shared memory yo ni siquiera expondría **`PMTPControl\*`**.

Expondría:

```
**`Pointer\<Void\> region`**
```

y:

```
**`init(region, capacity, ...)`**
```

Así Python, Rust y Dart comparten exactamente el mismo ABI binario.


# **8. ABI único o nada**

**`polydim.h`** será la única autoridad.

Generaremos:

```
**`C ABI`**

`↓`

**`Python ctypes bindings`**

`↓`

**`Dart FFI bindings`**

`↓`

**`Rust constants/types`**
```

No más:

```
**`C++ signature manual`**

**`Python signature manual`**

**`Dart signature manual`**

**`Rust enum manual`**
```

El header público ya define status/tolerancias/report; esto debe convertirse en el contrato único. 

### **Añadir:**

```
**`\#define POLYDIM\_ABI\_VERSION 769u`**

**`\#define POLYDIM\_MAX\_RANK 8u`**
```

y:

```
**`uint32\_t polydim\_abi\_version(void);`**

**`uint32\_t polydim\_sizeof\_tolerances(void);`**

**`uint32\_t polydim\_sizeof\_report(void);`**

**`uint64\_t polydim\_pmtp\_layout\_hash(void);`**
```

Los bindings fallan inmediatamente si el layout no coincide.


# **9. C++: eliminar `\_\_restrict\_\_` del ABI público**

No necesitamos **`restrict`** para funciones FFI.

La política correcta:

```
**`exact alias permitido`**

**`partial overlap rechazado`**

**`independent buffers permitido`**
```

y un helper seguro:

```
**`bool ranges\_overlap(`**

`    **const void\* a,`**

`    **size\_t a\_bytes,`**

`    **const void\* b,`**

`    **size\_t b\_bytes);`**
```

usando **`uintptr\_t`** con comprobación de overflow, no:

```
**`pa \< pb + bytes`**
```

porque el pointer arithmetic de intervalos arbitrarios puede no ser una base segura de un contrato FFI.


# **10. Validación global de tolerancias**

Antes de usar:

```
**`const PolydimTolerances tol = ...`**
```

hay que comprobar:

```
**`finite`**

**`\>= 0`**

**`reject\_subnormal ∈ \{0,1\}`**
```

Una tolerancia NaN no puede producir **`SUCCESS`**.

El contrato público ya dice que el caller controla estas políticas. 


# **11. C++: una sola primitive robusta de norma**

Eliminar todos los:

```
**`sum += x\*x`**
```

de las rutas de certificación.

Crear:

```
**`polydim\_scaled\_norm2\_f64()`**

**`polydim\_scaled\_dot\_f64()`**
```

con:

```
**`scale`**

**`sumsq`**
```

para evitar:

```
**`x\*x -\> overflow`**

**`x\*x -\> underflow`**
```

Neumaier no puede recuperar información que ya se perdió en la multiplicación.


# **12. Reducir también el coste de memoria de C++**

Hoy aparecen repetidamente:

```
**`std::vector\<Neumaier\>`**

**`std::vector\<double\>`**
```

por llamada.

Para producción:

```
**`Context`**

` ├── **thread count`**

` ├── **workspace`**

` ├── **SIMD backend`**

` ├── **numerical policy`**

` └── **allocator`**
```

y las rutinas reciben workspace ya reservado.

Así:

```
**`hot loop`**
```

no hace:

```
**`malloc`**

**`malloc`**

**`malloc`**

**`free`**

**`free`**

**`free`**
```

por cada tensor.


# **13. Reducir no-determinismo entre runs**

Actualmente la suma depende del número de threads porque:

```
**`thread-local accumulator`**

`↓`

**`merge thread 0..N`**
```

Un run con 8 threads no produce exactamente el mismo camino de redondeo que uno con 32.

Para reproducibilidad industrial:

```
**`fixed-size chunks`**

`↓`

**`1 accumulator/chunk`**

`↓`

**`deterministic binary tree`**
```

El número de threads cambia el paralelismo, no el orden lógico de la reducción.


# **14. `-ffast-math`: ahora sí tenemos un dato experimental**

Lo probé de verdad:

### **Build normal**

```
**`selftest compensation`**

**`RC = 0`**

**`error = 0`**
```

### **Build `-ffast-math`**

```
**`RC = -12`**

**`error ≈ 1.11e-10`**
```

Así que el canario actual **detecta** el problema.

Pero el V769 debe ir un paso más allá:

```
**`\#ifdef \_\_FAST\_MATH\_\_`**

**`\#error "POLYDIM requires strict floating-point semantics"`**

**`\#endif`**
```

Y el build release estricto debe fijarse explícitamente.


# **15. Rodrigues: corregir el contrato matemático**

La implementación actual no tiene TwoSum en el update.

No debemos decir:

> “Two-pass compensated Rodrigues”.

La descripción correcta será:

```
**`Pass 1:`**

`  **compensated reductions`**


**`Pass 2:`**

`  **fused/vectorized point update`**


**`Pass 3 optional:`**

`  **residual verification`**
```

Si queremos compensation del update, implementarlo de verdad o eliminar la afirmación.


# **16. Rodrigues: tolerancia basada en bound real**

No usar:

```
**`64 \* eps`**
```

como si fuera una ley universal.

Reportar:

```
**`measured residual`**

**`estimated floating error bound`**

**`user tolerance`**
```

y separar:

∣∥y∥−1∣

de:

∣∥y∥2−1∣.

Actualmente están mezcladas ambas cantidades.


# **17. Stiefel: eliminar `G\_proj\[D\*K\]`**

Esto sigue siendo P0.

Para:

D=107,K=512

son:

40.96GB

sólo para esa matriz auxiliar.

La proyección debe hacerse en tiles:

```
**`tile X,G`**

`↓`

**`Gproj temporal`**

`↓`

**`acumulación K×K`**

`↓`

**`tile siguiente`**
```

Así la memoria vuelve a:

O(K2+TK)

en vez de:

O(DK).


# **18. Stiefel: `cholqr2\_f64()` también cambia**

La actual rutina usa:

```
**`thread\_XTX\[threads\*K\*K\]`**
```

sin budget.

Debe reutilizar el mismo allocator/workspace del contexto.

Y el criterio:

```
**`eps \* D \* 10`**
```

no será el stopping criterion.

Usar:

```
**`backward error`**

**`orthogonality residual`**

**`relative factorization residual`**
```

La opción robusta para matrices tall-and-skinny es Householder/TSQR; LAPACK ya tiene rutinas específicas para tall-skinny QR. 


# **19. Mejora teórica importante del Adapter**

La documentación afirma implícitamente:

RD↔SD−1×R

Eso necesita precisión.

La correspondencia correcta es:

RD∖\{0\}↔SD−1×R​

y el cero necesita una etiqueta aparte.

Pero todavía hay otra corrección más importante:

### **No es una isometría.**

Es una **parametrización biyectiva**.

En coordenadas log-radiales:

r=log∥h∥

la métrica euclídea queda:

ds2=e2r(dr2+dΩ2)

Así que es conformalmente relacionada, no isométrica bajo la métrica producto usual.

Esto mejora mucho la teoría porque elimina una afirmación que un matemático te puede tumbar inmediatamente.


# **20. Adapter correcto**

Representación:

```
**`(zero\_flag, u, log\_norm)`**
```

donde:

```
**`zero\_flag=1 -\> h=0`**

**`zero\_flag=0 -\> h=exp(log\_norm)\*u`**
```

Además:

```
**`robust norm`**

**`frexp/ldexp`**

**`overflow-safe exp reconstruction`**
```

para extremos FP64.

Y:

```
**`u`**
```

debe tener contrato:

∥u∥=1

antes de aceptar proyecciones tangentes.


# **21. Stiefel `W`: otra corrección conceptual**

Si:

W∈RD×K,WTW=IK​

entonces:

κ(W)=1

como operador desde RK hacia su imagen.

Pero para:

K\<D

no es una transformación biyectiva:

RD→RK.

El decoder:

WWTx

es una **proyección**, no una recuperación sin pérdida.

Por tanto:

```
**`DPI Loss = 0`**
```

no puede afirmarse sin una hipótesis fuerte:

x∈span(W)

casi seguramente.

La propia documentación actual ya introduce esa condición de span; hay que hacerla central, no secundaria. 


# **22. LSM: eliminar las dos implementaciones actuales**

No mantener:

```
**`LSM standalone`**

**`LSM monolith`**
```

en paralelo.

Una sola implementación canónica.

### **Arquitectura nueva**

En vez de:

```
**`D filas × nnz`**
```

usar:

Q=Hm​Hm−1​⋯H1​

con Hi​ Householder/Givens.

Cada transformación es ortogonal:

HiT​Hi​=I

y por tanto:

QTQ=I.

Con número fijo de capas:

Time=O(mD)=O(D)

y:

Memory=O(mD)

para m constante.

Otra opción más rica es un butterfly/orthogonal mixing de:

O(DlogD)

si aceptamos más profundidad.


# **23. La afirmación `rho(W)=1` desaparece como certificado principal**

No basta:

ρ(W)=1.

Certificar:

Jt​=∂x∂F​

y medir:

```
**`spectral norm`**

**`Lyapunov estimate`**

**`state saturation`**

**`memory decay`**

**`input sensitivity`**
```

Ese sí es un test de la dinámica.


# **24. Y una corrección grande: LSM no tiene “O(1) temporal memory”**

La memoria del estado es:

O(D).

La complejidad por paso puede ser:

O(D).

Pero decir:

> “O(1) temporal memory”

es incorrecto.

Lo correcto:

> **fixed-state temporal memory with O(D) state storage and O(D) update cost.**


# **25. LSM realmente manifold-native**

La dinámica actual:

```
**`tanh(...)`**

**`mix with old state`**

**`normalize`**
```

es ambient-space dynamics + projection.

Una formulación más fuerte:

zt​=Qxt−1​+But​ξt​=(I−xt​xtT​)zt​xt+1​=Retrxt​​(αξt​)

con:

Retrx​(ξ)=∥x+ξ∥x+ξ​.

Eso sí es un reservoir explícitamente respetuoso del manifold.


# **26. Rust: dejar de llamar β₁ a un cycle rank de grafo**

El algoritmo actual realmente calcula:

E−V+C

para el grafo 1-dimensional.

Eso es válido como **cycle rank del grafo**.

Pero si querés homología de un complejo simplicial:

β1​=dimker∂1​−dimim∂2​.

Las 2-celdas pueden matar ciclos.

### **V769:**

Renombrar:

```
**`polydim\_rust\_graph\_cycle\_rank()`**
```

o implementar realmente:

```
**`persistent\_beta1()`**
```

sobre una construcción sparse.


# **27. Rust a D=10⁷: abandonar adjacency matrix**

Nunca:

n×n

para este caso.

Usar:

```
**`CSR / COO / edge list`**
```

con:

O(V+E).

Y separar:

```
**`latent dimension D`**
```

de:

```
**`number of sampled states N`**
```

La topología debería aplicarse a un conjunto de puntos/estados, no automáticamente a los 10 millones de coordenadas del vector.


# **28. Rust FFI**

**`slice::from\_raw\_parts`** exige mucho más que:

```
**`ptr != null`**

**`alignment = 8`**
```

La documentación actual de Rust exige que el rango completo sea válido, esté inicializado, correctamente alineado y que el tamaño no supere **`isize::MAX`**. 

V769 debe tener:

```
**`if len \> isize::MAX as usize / size\_of::\<f64\>() \{`**

`    **return ERR\_BUFFER\_OVERFLOW;`**

**`\}`**
```

y un contrato explícito de lifetime/exclusividad.


# **29. `catch\_unwind` queda condicionado a `panic=unwind`**

El wrapper no puede prometer:

```
**`panic always caught`**
```

si el binario Rust está configurado con:

```
**`panic="abort"`**
```

Eso hay que fijarlo en build.


# **30. Triton: quitar completamente `.item()`**

La reducción GPU debe devolver:

```
**`alpha\_beta tensor GPU`**
```

y Pass 2 debe recibir:

```
**`alpha\_beta`**
```

como tensor.

Dentro del kernel:

```
**`alpha = tl.load(alpha\_beta\_ptr + 0)`**

**`beta  = tl.load(alpha\_beta\_ptr + 1)`**
```

Nada de:

```
**`.item()`**
```

El stack actual de Triton dispone de operaciones de reducción GPU y mecanismos de memoria/asynchronous reduction; no hace falta volver al CPU para resolver dos escalares. 


# **31. Triton D=10⁷: una sola reducción**

No:

```
**`9766 partials`**

`↓`

**`next\_power\_of\_2 = 16384`**

`↓`

**`kernel enorme`**
```

Usar reducción jerárquica:

```
**`D elements`**

`↓`

**`block partials`**

`↓`

**`second-level partials`**

`↓`

**`single 1-block final`**
```

o incluso:

```
**`torch.sum(partials)`**
```

**en GPU**, porque un **`.sum()`** sin **`.item()`** mantiene el resultado en GPU.

El current fallback además tiene **`math.sin`** sin importar **`math`**; eso queda eliminado de raíz porque toda la trigonometría debe ocurrir GPU-side.


# **32. Triton: añadir validación de datos**

Pass 1 debe producir también:

```
**`error\_flags`**
```

detectando:

```
**`NaN`**

**`Inf`**

**`subnormal policy`**
```

No puede existir:

```
**`GPU computes NaN`**

`↓`

**`PASS2`**

`↓`

**`SUCCESS`**
```


# **33. RDMA: renombrar ahora mismo**

El archivo actual no es RDMA.

Es:

```
**`TCP tensor transport emulator`**
```

No intentaría maquillarlo.

### **Arquitectura:**

```
**`MIR local`**

`    ↓`

**`PMTP shared memory`**


**`MIR remote`**

`    ↓`

**`UCX / libfabric`**

`    ↓`

**`RDMA provider`**
```

UCX tiene un modelo explícito de memory handles y remote keys para acceso remoto de memoria, que es exactamente el nivel de abstracción que necesitamos. 

Y localmente:

```
**`mmap + PMTP`**
```

remains independiente del transporte WAN.


# **34. TCP fallback, si permanece**

Corregir:

```
**`recv(header\_size)`**
```

por:

```
**`recv\_exact(header\_size)`**
```

y antes de reservar:

```
**`0 \< bytes \<= MAX\_TENSOR\_BYTES`**

**`bytes % dtype\_size == 0`**

**`rank \<= MAX\_RANK`**

**`shape product == bytes/dtype\_size`**
```

Además:

```
**`received\_tensors`**
```

debe ser bounded queue/ring, no lista infinita.


# **35. Quantum Compiler: destruir la implementación falsa y conservar la idea**

No parchearía:

```
**`H T H S`**
```

para seguir llamándolo Solovay-Kitaev.

### **Arquitectura correcta**

```
**`SO(D)`**

` ↓`

**`Givens decomposition`**

` ↓`

**`two-level unitaries`**

` ↓`

**`basis-state mapping`**

` ↓`

**`Gray-code / multiplexed construction`**

` ↓`

**`parameterized 1Q rotations`**

` ↓`

**`optional Clifford+T synthesis`**

` ↓`

**`error certification`**
```

La operación sobre dos **coordenadas** p1​,p2​ no significa:

```
**`q1 = p1 % n`**

**`q2 = p2 % n`**
```

Eso se elimina.

Para un estado de D componentes:

n=⌈log2​D⌉

y los índices son basis states:

∣p1​⟩, ∣p2​⟩.

La implementación actual no preserva esa semántica.


# **36. Quantum: `eps\_target` debe ser verificable**

La salida debe cumplir:

∥U−Uapprox​∥≤ϵ.

No:

```
**`eps\_target existe como parámetro`**
```

pero el circuito no cambia.

Tests:

```
**`1e-2`**

**`1e-4`**

**`1e-6`**

**`1e-8`**
```

y medir:

```
**`operator error`**

**`Frobenius error`**

**`state-vector error`**

**`T-count`**

**`CNOT-count`**

**`depth`**
```


# **37. Omni Router**

Separar:

```
**`event routing`**
```

de:

```
**`OS execution`**
```

**`executePCOperation()`** no debería recibir shell arbitrario.

Modelo industrial:

```
**`command ID`**

**`allowlist`**

**`typed arguments`**

**`capability token`**

**`timeout`**

**`sandbox`**

**`audit event`**
```

Nunca:

```
**`execute arbitrary string`**
```

desde un canal remoto.


# **38. Tests: reemplazar `selftest\_all()` por una matriz de certificación**

El actual **`selftest\_all()`** está bien como smoke test.

No como certificación.

V769 necesita:

```
**`ABI`**

**`NUMERICAL`**

**`ALIAS`**

**`BOUNDS`**

**`CONCURRENCY`**

**`FAULT-INJECTION`**

**`LARGE-D`**

**`FFI`**

**`GPU`**

**`TOPOLOGY`**
```

### **Casos obligatorios**

```
**`D=1`**

**`D=2`**

**`D=4`**

**`D=1024`**

**`D=1e6`**

**`D=1e7`**
```

con:

```
**`normal`**

**`NaN`**

**`Inf`**

**`min-normal`**

**`min-subnormal`**

**`max-normal`**

**`near-overflow`**

**`near-underflow`**
```

y:

```
**`exact alias`**

**`partial alias`**

**`misaligned pointer`**

**`truncated buffer`**

**`wrong capacity`**
```


# **39. Benchmarks: cambiar qué significa “certified”**

No volver a:

```
**`Exit Code 0`**

**`=`**

**`certified`**
```

Debe ser:

```
**`source commit`**

**`compiler`**

**`compiler flags`**

**`CPU/GPU model`**

**`driver`**

**`library versions`**

**`input seed`**

**`D`**

**`K`**

**`dtype`**

**`thread count`**

**`workspace bytes`**

**`result`**

**`residual`**

**`log`**

**`binary hash`**
```

El benchmark actual declara telemetría para D=10⁷, pero los artifacts mencionados no están dentro del ZIP entregado. Por eso esos números no pueden utilizarse todavía como prueba reproducible del artefacto presente.


# **40. Regla definitiva para POLYDIM**

La documentación ya no podrá inventar propiedades que el código no prueba.

Cada afirmación tendrá una de estas etiquetas:

```
**`\[THEOREM\]`**

**`\[DERIVED\]`**

**`\[UNIT TESTED\]`**

**`\[STRESS TESTED\]`**

**`\[HW MEASURED\]`**

**`\[UNVERIFIED\]`**
```

Nunca:

```
**`CERTIFIED`**
```

por comentario.


# **41. Resultado de esta ronda**

### **El kernel C++ que probé**

```
**`normal build selftest        PASS`**

**`-fast-math detector          PASS`**

**`Rust compilation             NO VERIFICADA aquí: rustc no está instalado`**

**`Dart execution               NO VERIFICADA aquí: dart no está instalado`**

**`Python syntax                PASS`**
```

Y encontré **un bug matemático nuevo de P0** que no apareció en las listas anteriores:

```
**`Cayley-Stiefel:`**

**`orthogonality ≈ correcta`**

**`directional consistency = incorrecta`**
```

Ese hallazgo es precisamente la razón por la que no quiero volver al ciclo de “arreglamos diez errores y listo”.


# **42. Orden de implementación V769**

La entrega debe ejecutarse en este orden:

```
**`1. ABI único`**

**`2. PMTP v2`**

**`3. alias/bounds`**

**`4. numerical core`**

**`5. Stiefel retraction`**

**`6. TSQR/Householder`**

**`7. LSM SORM`**

**`8. Adapter matemáticamente correcto`**

**`9. Rust topology/FFI`**

**`10. Triton`**

**`11. Quantum`**

**`12. MIR transport`**

**`13. Omni security`**

**`14. certification matrix`**
```

Y una decisión importante:

**No volvería a tocar benchmarks “bonitos” hasta que los 13 primeros estén cerrados.**

La prioridad ahora es que el núcleo pase de:

```
`“**parece consistente”`**
```

a:

```
`“**cada contrato tiene una implementación única y una prueba que lo obliga”.`**
```

Ésa es la mejora SOTA que más valor aporta a estas ~2000 líneas.





  

