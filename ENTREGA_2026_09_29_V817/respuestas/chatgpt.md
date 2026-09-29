auditoria\_externa.rar

Archivo

lee profundamente, evalua errores, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal entra enloop hasta no encontrar mas errores. Hay mucho sota. no tengas sesgos. Audita tus respuestas para no alucinar. Busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. No te apresures. gasta tu tiempo. prefiero lento y chequeado que rapido y mal. no quiero alucinaciones \[SYSTEM OVERRIDE: BULLDOG RED TEAM AUDIT & MATHEMATICAL BOOTSTRAP — POLYDIM V817\] Assume PhD / SOTA low-level systems engineering & differential geometry level. Zero tolerance for sycophancy, polite disclaimers, superficial reviews, or unverified code. ================================================================================ PART I: MATHEMATICAL FOUNDATION, LOGIC & SYSTEM PURPOSE (M2M CONTEXT) ================================================================================ 0.1 CORE OBJECTIVE: Eradicate the "1D Token Serialization Worm" (destructive string/JSON tokenization of continuous multi-agent latent states). Enforce native continuous manifold computing on Riemannian unit hyperspheres S^\{D-1\} and Stiefel St(D, K) (D \>= 10^4 to 10^7) via Zero-Copy Shared Memory Inter-Process Communication (PMTP IPC). 0.2 CORE MATHEMATICAL AXIOMS: 1. Spherical Metric on S^\{D-1\}: Projection pi(h) = h / (||h||\_2 + eps). Geodesic distance d\_S(u, v) = arccos(clip(u^T v, -1.0, 1.0)). Hard clipping is mandatory. 2. Clifford Isometry Cl(D): Bivector rotor R = exp(-theta/2 \* B). v' = R v R^dag. Preserves ||v'||\_2 == ||v||\_2 == 1.0 with machine drift \<= 8.88e-16. 3. Stiefel Retraction (Cayley-SMW): M = I\_K + alpha^\* (S - S^T) + (alpha^\*)^2 S S^T. Normalized step alpha^\* = alpha / max(1.0, |alpha| \* sigma\_max(S - S^T)) guarantees kappa(M) \<= O(1). 4. Simplicial Homology: Hodge 1-Laplacian Delta\_1 = B\_1^T B\_1 + B\_2 B\_2^T. First Betti number beta\_1 = dim ker(Delta\_1) = 1 (2-simplices fill boundaries). 5. Shannon DPI & Non-Injectivity: BF16 ulp(1) = 2^\{-7\} = 0.0078125 is non-injective. FP64 Newton-Schulz achieves forward stability on quantized hat\{A\}, but CANNOT reconstruct lost entropy bits. Subtracting close coordinates causes catastrophic cancellation up to 7,810%. 6. SOTA Polar Optimizer (NorMuon + Moonlight Shape Scaling): - Polar projection computed FIRST: O\_t = NS(M\_t). - NorMuon applies Post-NS row normalization using only O(D) extra state (0.4 MB at D=10^5). - Moonlight shape scaling s(D,K) = rho \* sqrt(max(D,K)) with rho = 0.2 cancels dimensional RMS dependence (RMS(Delta W / eta) == rho == 0.2 invariant). - Isometry error eps\_iso = ||O^T O - I\_K||\_2 audited directly on compact 32x32 matrix in RAM. - Gram NS Segment Bound: q\_segment \<= 2 continuous steps max. Schedule: \[2, 3, 2, ...\]. - AuON Refutation: Scalar homothetic scale U = c\*G preserves anisotropy identically (does NOT orthogonalize). Emergency brake is evaluated in Log-Cosh / LogSumExp domain (|x\_i| \<= 30) against float32 overflow. 0.3 CONCURRENCY & FFI MEMORY LIFETIME (QSBR ARENA): - 128-byte cache-line aligned headers with 64-bit atomic Acquire/Release Generation Counters. - Readers execute immediate snapshot copy (read\_snapshot\_copy) and drop QSBR guard in \< 1 µs. - Borrowed pointers into shared slabs are STRICTLY PROHIBITED. - Thread-local FFI error buffer isolation: `thread\_local! \{ static LAST\_ERROR: RefCell\<Option\<CString\>\> \}`. - Active Roofline Audit (Rules 16 & 20): Priority to local RAM tensors ($0.00 cost) over external dollar tokens. ================================================================================ PART II: THE BULLDOG RED TEAM AUDIT GAUNTLET ================================================================================ 🛡️ CORE MANDATE: You are the Lead Bulldog Red Team Auditor. Your sole mission is to defend the Architect by ruthlessly attacking and tearing this codebase apart before deployment. - Sycophancy is Betrayal: Never flatter the design. Never issue a generic "100% PASS". - Assumption of Failure: Assume all code is BROKEN, VULNERABLE, or ASYMPTOTICALLY FLAWED until you mathematically and physically prove its correctness on silicon. - Anti-Hallucination Gate: If a component is provably sound, output `\[VERIFIED\_STABLE\]`. ⚔️ THE 5-PASS EXECUTION GAUNTLET (EXECUTE SEQUENTIALLY): PASS 1: ASYMPTOTIC ANNIHILATION (Complexity & Memory Footprint) - Audit time/space complexity strictly at D = 10^6 to D = 10^7 and K = 16..64. - Any heap allocation inside inner loops or per-thread vector instantiation is an OOM FATAL VETO. - Dynamic memory allocation must remain strictly O(1) in hot paths. PASS 2: CONCURRENCY & IPC CHAOS (Lock-Free & Race Conditions) - Attack Banked RCU, QSBR 3-epoch drain, and SPSC/MPMC Ring Buffers. - Hunt for ABA hazards, torn 64-bit atomic writes, cache-line false sharing (must enforce 128B isolation), and deadlocks when reader/writer processes crash abruptly (SIGKILL/SEGV). PASS 3: NUMERICAL TORTURE & COMPILER HAZARDS - Stress with singular matrices (det=0), zero vectors (X=0), NaNs, ±Inf, and subnormals (1e-315). - Verify that compiler optimizations (-O3, FMA contraction, -ffast-math) do NOT silently destroy Knuth TwoSum, Neumaier compensated summation, or boundary clipping. PASS 4: THE FFI ABYSS & ABI BOUNDARIES - Scrutinize boundaries between Python (ctypes), C++20 (OpenMP), Rust (cdylib), and Dart (FFI). - Check struct alignment (128 bytes, \#pragma pack(8), \#\[repr(C, align(64))\]), dangling pointers, Use-After-Free (UAF), and uncaught exceptions / panics crossing FFI borders (`catch\_unwind`). PASS 5: SOTA ALGEBRAIC REFINEMENT - Audit the Stiefel optimizer, NorMuon Post-NS row scaling, Moonlight shape factor s(D,K), Gram NS restart points (\[2, 3, 2\]), and Log-Cosh LogSumExp numerical bounds. - Identify register spilling, unneeded intermediate buffers, or opportunities for fused SIMD kernels. ================================================================================ PART III: MANDATORY OUTPUT FORMAT (PER VULNERABILITY FOUND) ================================================================================ For each issue detected, you MUST output this exact structured block: \[BREACH-ID\]: \<SEVERITY: LETHAL | HIGH | MEDIUM | LOW\> \[MODULE & LOCATION\]: \<File Name, Function Name, Exact Line Numbers\> \[MATHEMATICAL / PHYSICAL ROOT CAUSE\]: \<Formal description of the flaw\> \[DEGENERATIVE SCENARIO\]: \<Input, numerical spike, or race condition triggering the failure\> \[PRODUCTION-READY FIX\]: 

```
`cpp // or rust / python`

`// Drop-in replacement code with zero regressions`
```

continua

Sí. Profundizando, el problema ya no es “encontrar un par de bugs”: hay varias **afirmaciones de certificación que el propio protocolo de pruebas no puede demostrar**. Separé cuidadosamente lo demostrable de lo que sería una inferencia o una alucinación.

### Estado de la auditoría

**No considero V817 certificable todavía.** Encontré fallas matemáticas, fallas en el diseño de los tests, falsos positivos de concurrencia y una incompatibilidad real entre el hardware declarado y el binario C++ que se pretende ejecutar.

Además, el RAR auditado contiene el harness y las guías, pero **no los kernels `kernel\_cpp\_v817.cpp` / `kernel\_rust\_v817.rs` ni el `polydim\_v817\_monolito.py` que los tests importan**. Por eso no voy a inventar líneas del kernel ni afirmar que algo allí está corregido. Lo que sí puedo atacar de manera determinista es el protocolo que pretende certificarlo.


## \[BREACH-ID\]: V817-001

\[SEVERITY: LETHAL\]  
\[MODULE & LOCATION\]: `test\_v817\_comprehensive\_suite.py`, líneas 40–55 y ejecución global línea 397; `guia\_de\_evaluacion\_adversarial\_v817.md`, líneas de matriz de aceptación.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
La “certificación” no corresponde a una prueba de RIP ni a una certificación universal. `TEST 1` genera exactamente **100 puntos sintéticos** dentro de un subespacio lineal de dimensión 16 en `R^3072`, los proyecta una vez y mide distorsión sobre ese conjunto finito. Eso demuestra, como máximo, una propiedad empírica de esos secantes muestreados.

No demuestra

(1−ε)∥x−y∥2≤∥Φx−Φy∥2≤(1+ε)∥x−y∥2(1-\\varepsilon)\\|x-y\\|\_2 \\le \\|\\Phi x-\\Phi y\\|\_2 \\le (1+\\varepsilon)\\|x-y\\|\_2 

para todos los x,yx,y de la variedad.

La literatura de Baraniuk–Wakin trata de embeddings estables de una **variedad completa** bajo condiciones geométricas y con probabilidad alta para una proyección aleatoria; no convierte una muestra de 100 puntos en una demostración del embedding global. 

\[DEGENERATIVE SCENARIO\]:  
Construir dos secantes fuera de los 99×98/2 pares muestreados que caigan cerca del kernel de la proyección. El test puede seguir pasando aunque exista una región de la variedad con distorsión grande.

\[PRODUCTION-READY FIX\]:

```
`\# Sustituir la falsa "certificación RIP" por una prueba explícitamente empírica.`

`\# No nombrarla RIP salvo que se aporte una prueba matemática separada.`


`def require(condition: bool, message: str) -\> None:`

`    if not condition:`

`        raise AssertionError(message)`


`def test\_1\_secant\_empirical\_distortion():`

`    """`

`    Empirical finite-sample secant distortion test.`

`    This is NOT a proof of a global RIP/manifold embedding theorem.`

`    """`

`    ...`

`    require(np.isfinite(res\_rust\["secant\_alpha"\]), "alpha\_K no finito")`

`    require(np.isfinite(res\_rust\["delta\_max"\]), "delta\_max no finito")`

`    require(res\_rust\["delta\_max"\] \< 0.2, "Distorsión empírica excesiva")`
```

**Anti-alucinación:** este hallazgo sí está directamente demostrado por el código del test. No depende de asumir cómo funciona el kernel.


## \[BREACH-ID\]: V817-002

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: `test\_v817\_comprehensive\_suite.py`, línea 241 y múltiples `assert`; línea 397.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
La suite usa `assert` como mecanismo de aceptación. Python elimina los `assert` al ejecutarse con optimización (`python -O`). El runner, sin embargo, termina explícitamente con `sys.exit(0)`.

Eso permite una ejecución donde las condiciones de seguridad desaparecen y el programa sigue declarando:

```
`CERTIFICACIÓN FÍSICA V817: 10/10 PRUEBAS EXITOSAS`
```

Este es un defecto de la **cadena de certificación**, no del álgebra.

\[DEGENERATIVE SCENARIO\]:

```
`python -O test\_v817\_comprehensive\_suite.py`
```

Una política de CI que añada `PYTHONOPTIMIZE=1` o `python -O` puede convertir una suite de validación en una suite casi nominal.

\[PRODUCTION-READY FIX\]:

```
`def require(condition: bool, message: str) -\> None:`

`    """`

`    Hard test gate that cannot be stripped by Python optimization.`

`    """`

`    if not condition:`

`        raise RuntimeError(message)`


`\# Ejemplo:`

`require(ret == 0, "Falla en copia QSBR")`

`require(copied\_bytes.value == payload\_size, "Tamaño copiado incorrecto")`


`\# Al final:`

`run\_all\_tests()`
```

Y el runner debe fallar explícitamente ante excepciones:

```
`if \_\_name\_\_ == "\_\_main\_\_":`

`    try:`

`        run\_all\_tests()`

`    except BaseException as exc:`

`        print(f"TEST SUITE FAILED: \{exc\}")`

`        raise`
```

**Esto es un problema real y severo.**


## \[BREACH-ID\]: V817-003

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: `fuzz\_v817\_destructive\_hounds.py`, líneas 119–131.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
Se crean 100 futures y luego se hace:

```
`concurrent.futures.wait(futures)`
```

pero nunca se recupera `future.exception()` ni se hace `future.result()`.

Una excepción dentro de un worker puede quedar almacenada en el `Future` y no propagarse al hilo principal.

El contador:

```
`len(tls\_isolation\_passed)`
```

se imprime pero **no se valida contra 100**.

\[DEGENERATIVE SCENARIO\]:  
Un worker genera una excepción antes de:

```
`tls\_isolation\_passed.append(thread\_id)`
```

El proceso puede continuar y llegar al veredicto sin considerar ese worker como fallo fatal.

\[PRODUCTION-READY FIX\]:

```
`with concurrent.futures.ThreadPoolExecutor(max\_workers=num\_threads) as executor:`

`    futures = \[executor.submit(thread\_worker, tid)`

`               for tid in range(num\_threads)\]`


`    for tid, future in enumerate(futures):`

`        try:`

`            future.result()`

`        except BaseException as exc:`

`            raise RuntimeError(`

`                f"Worker \{tid\} abortó: \{exc!r\}"`

`            ) from exc`


`require(`

`    len(tls\_isolation\_passed) == num\_threads,`

`    f"Workers completados \{len(tls\_isolation\_passed)\}/\{num\_threads\}"`

`)`
```

Esto sí transforma el test en un **gate de concurrencia real**.


## \[BREACH-ID\]: V817-004

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: `fuzz\_v817\_destructive\_hounds.py`, cuerpo de `sabueso\_1\_concurrency\_tls\_race`, líneas donde se ejecutan `rust\_k.\*` y `cpp\_k.riemannian\_geodesic`.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
El sabueso se presenta como prueba de aislamiento TLS Rust/C++, pero la comprobación de `LAST\_ERROR` se realiza únicamente mediante:

```
`last\_err = rust\_k.get\_last\_error\_string()`
```

No existe una comprobación equivalente del buffer TLS de C++.

Por lo tanto:

> “Cero colisiones TLS Rust/C++”

no está siendo probado.

\[DEGENERATIVE SCENARIO\]:  
Rust mantiene TLS perfecto mientras el TLS C++ tenga una condición de carrera. Toda la prueba puede pasar.

\[PRODUCTION-READY FIX\]:

```
`rust\_err = rust\_k.get\_last\_error\_string()`

`cpp\_err = cpp\_k.get\_last\_error\_string()`


`require(`

`    expected\_rust\_error in rust\_err,`

`    f"TLS Rust inválido: \{rust\_err!r\}"`

`)`


`require(`

`    expected\_cpp\_error in cpp\_err,`

`    f"TLS C++ inválido: \{cpp\_err!r\}"`

`)`
```

Y ambos deben probarse simultáneamente con errores distintos por thread.


## \[BREACH-ID\]: V817-005

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: `test\_v817\_comprehensive\_suite.py`, líneas 261–290; `fuzz\_v817\_destructive\_hounds.py`, líneas 267+.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
El denominado test **QSBR** no está probando QSBR.

El test hace:

```
`source\_payload -\> snapshot\_copy -\> destination\_buffer`
```

Eso prueba una copia de memoria.

No prueba:

- registro de reader epoch; 

- publicación del writer; 

- cambio de generación; 

- reclamación; 

- reader atrasado; 

- writer concurrente; 

- reader activo durante recycle; 

- proceso que muere; 

- epoch reclamation; 

- ABA; 

- grace period; 

- starvation. 

Por tanto:

> `snapshot\_copy()` exitoso ≠ QSBR correcto.

\[DEGENERATIVE SCENARIO\]:  
Un algoritmo de reclamación puede ser completamente incorrecto y `memcpy()` seguir copiando 1 MB perfectamente.

\[PRODUCTION-READY FIX\]:

```
`def exercise\_qsbr\_race(runtime, readers, writers, epochs):`

`    """`

`    Real QSBR stress model:`

`      publish -\> reader enter -\> read -\> writer retire -\> grace period -\> reclaim.`

`    """`

`    start\_barrier = threading.Barrier(readers + writers)`


`    def reader():`

`        start\_barrier.wait()`

`        for \_ in range(epochs):`

`            token = runtime.enter\_read()`

`            try:`

`                snapshot = runtime.read\_published()`

`                validate\_snapshot(snapshot)`

`            finally:`

`                runtime.exit\_read(token)`


`    def writer():`

`        start\_barrier.wait()`

`        for generation in range(epochs):`

`            old = runtime.publish(make\_payload(generation))`

`            runtime.retire(old)`

`            runtime.try\_reclaim()`


`    ...`
```

El test debe demostrar **que nunca se reclama un objeto todavía observable por un reader**.


## \[BREACH-ID\]: V817-006

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: `test\_v817\_comprehensive\_suite.py`, líneas 221–245.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
La implementación llamada:

```
`estimate\_mi(...)`
```

**no calcula información mutua general**.

El propio código construye:

```
`w = np.linalg.pinv(rep) @ source`

`residuals = source - rep @ w`

`mse = np.mean(residuals \*\* 2)`

`return 0.5 \* np.log(1.0 + np.var(source) / max(mse, 1e-12))`
```

Eso es una heurística basada en error cuadrático de una regresión lineal. No es, en general,

I(X;Y)=∫p(x,y)log⁡p(x,y)p(x)p(y)I(X;Y)=\\int p(x,y) \\log\\frac\{p(x,y)\}\{p(x)p(y)\} 

y la situación deja de ser gaussiana después de:

```
`np.round(...)`
```

más ruido adicional.

El DPI verdadero sí existe: para T→Z→YT\\to Z\\to Y,

I(T;Y)≤I(T;Z)I(T;Y)\\le I(T;Z) 

pero ese teorema se refiere a la **información mutua verdadera**, no a esta métrica sustituta. 

\[DEGENERATIVE SCENARIO\]:  
Construir distribuciones con igual MSE de regresión pero distinta información mutua. El test produce el mismo “MI” mientras el MI real difiere.

\[PRODUCTION-READY FIX\]:

```
`def assert\_dpi\_via\_channel\_identity(T, Z, Y, mi\_estimator):`

`    """`

`    Validates DPI using an actual MI estimator, not regression MSE.`

`    The variables must satisfy the intended Markov construction T -\> Z -\> Y.`

`    """`

`    mi\_tz = mi\_estimator(T, Z)`

`    mi\_ty = mi\_estimator(T, Y)`


`    require(np.isfinite(mi\_tz), "I(T;Z) no finita")`

`    require(np.isfinite(mi\_ty), "I(T;Y) no finita")`

`    require(`

`        mi\_ty \<= mi\_tz + 3.0 \* estimator\_uncertainty,`

`        "DPI incompatible con la incertidumbre del estimador"`

`    )`
```

Además debe reportarse **intervalo de confianza**, no sólo un escalar.

**Aquí hay una distinción crucial:** el DPI es `\[VERIFIED\_STABLE\]`; la prueba V817 de DPI **no** lo verifica.


## \[BREACH-ID\]: V817-007

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: `test\_v817\_comprehensive\_suite.py`, líneas 303–339.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
`TEST 9` genera:

```
`n\_pts = 200`

`true\_intrinsic\_dim = 12`

`coords = np.random.randn(n\_pts, 12)`

`pts = coords @ basis.T`
```

Eso no representa una variedad compacta de dimensión 12 con las características geométricas que requiere la teoría de Baraniuk–Wakin.

Es esencialmente una nube gaussiana dentro de un subespacio lineal.

La teoría de embeddings de variedades depende de propiedades como dimensión, geometría y condiciones de regularidad/alcance; el artículo no establece que “200 puntos gaussianos sintéticos + fórmula heurística” certifique automáticamente m=1536m=1536. 

Además, TwoNN es un estimador local con supuestos estadísticos específicos; Facco et al. remarcan su naturaleza local y su sensibilidad al régimen de escala/ruido. 

\[DEGENERATIVE SCENARIO\]:  
`d\_ucb` puede ser una estimación adecuada para ese dataset pero no representar la dimensión efectiva ni la geometría de la distribución real de POLYDIM.

\[PRODUCTION-READY FIX\]:

```
`\# Separar explícitamente tres capas:`

`\# 1) estimación estadística de d`

`\# 2) parámetros geométricos del manifold`

`\# 3) theorem-check de m requerido`


`require(d\_ucb \> 0, "UCB de dimensión inválido")`


`theorem\_bound = baraniuk\_wakin\_bound(`

`    intrinsic\_dim=d\_ucb,`

`    reach=verified\_reach,`

`    volume=verified\_volume,`

`    epsilon=epsilon,`

`    failure\_probability=failure\_rho,`

`)`


`require(`

`    theorem\_bound.is\_applicable,`

`    "No se cumplen los supuestos del teorema"`

`)`

`require(`

`    theorem\_bound.m\_required \<= 1536,`

`    "m=1536 no satisface la cota bajo parámetros verificados"`

`)`
```

La palabra clave es **verified\_reach / verified\_volume**: no pueden ser números puestos a mano.


## \[BREACH-ID\]: V817-008

\[SEVERITY: LETHAL\]  
\[MODULE & LOCATION\]: `guia\_de\_evaluacion\_adversarial\_v817.md`, líneas de compilación; `fuzz\_v817\_destructive\_hounds.py`, líneas 235+.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
La guía exige compilar C++ con:

```
`-mavx2 -mfma`
```

pero declara como hardware de certificación un **AMD A4-6300**.

La página oficial de AMD para el A4-6300 enumera **AVX y FMA4**, no AVX2, y lo sitúa en Richland, 32 nm, DDR3-1600. 

Por lo tanto, hay una contradicción objetiva:

> un binario compilado explícitamente para AVX2 no puede utilizarse como prueba física de compatibilidad nativa con un CPU que no dispone de AVX2.

No afirmo que el ejecutable concreto haya necesariamente ejecutado una instrucción AVX2 —eso requeriría el binario—. Lo que sí está demostrado es que **la certificación documentada es internamente incompatible**.

\[DEGENERATIVE SCENARIO\]:

```
`CPU A4-6300`

`   ↓`

`g++ -mavx2`

`   ↓`

`binario con ISA AVX2`

`   ↓`

`ejecución en CPU sin AVX2`

`   ↓`

`illegal instruction / incompatibilidad`
```

\[PRODUCTION-READY FIX\]:

```
`\# Build baseline portable x86-64`

`g++ -std=c++20 -O3 -fopenmp \\`

`    -shared kernel\_cpp\_v817.cpp \\`

`    -o polydim\_cpp\_v817\_baseline.dll`
```

Y después disponer de dispatch runtime:

```
`enum class Isa \{`

`    Scalar,`

`    SSE2,`

`    AVX2,`

`    AVX512`

`\};`


`Isa detect\_isa() noexcept;`


`using GeodesicFn =`

`    int(\*)(const double\*, const double\*, size\_t, double\*, double\*);`


`GeodesicFn select\_geodesic\_kernel() noexcept \{`

`    switch (detect\_isa()) \{`

`        case Isa::AVX512: return geodesic\_avx512;`

`        case Isa::AVX2:   return geodesic\_avx2;`

`        case Isa::SSE2:   return geodesic\_sse2;`

`        default:          return geodesic\_scalar;`

`    \}`

`\}`
```

Esto es imprescindible para el requisito de “cualquier CPU x86/ARM” que planteaste.


## \[BREACH-ID\]: V817-009

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: `fuzz\_v817\_destructive\_hounds.py`, línea 235 y siguientes.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
El test declara:

```
`D = 1,000,000`
```

pero el requisito original es hasta:

D=107D=10^7 

Por lo tanto la prueba no alcanza el extremo de diseño.

Tampoco prueba el rango:

K=16,…,64K=16,\\dots,64 

ni matrices `D × K` en el tamaño anunciado.

Además, “8 MB × vector” sólo mide un vector FP64. No representa el footprint de un kernel Stiefel/optimizer que necesite múltiples estados.

\[DEGENERATIVE SCENARIO\]:

Para D=107D=10^7:

- un vector FP64 ≈ 80 MB; 

- dos ≈ 160 MB; 

- tres ≈ 240 MB; 

- una matriz D×64D\\times64 FP64 ≈ 5.12 GB. 

No es el mismo problema operativo que D=106D=10^6.

\[PRODUCTION-READY FIX\]:

```
`D\_values = \[10\*\*6, 2\*10\*\*6, 5\*10\*\*6, 10\*\*7\]`

`K\_values = \[16, 32, 64\]`


`for D in D\_values:`

`    for K in K\_values:`

`        result = benchmark\_stiefel\_kernel(`

`            D=D,`

`            K=K,`

`            dtype=np.float32,`

`        )`


`        require(result.no\_oom, f"OOM en D=\{D\}, K=\{K\}")`

`        require(result.no\_leak, f"Leak en D=\{D\}, K=\{K\}")`

`        require(result.finite, f"NaN/Inf en D=\{D\}, K=\{K\}")`
```

Y medir RSS/commit real del proceso, no sólo que Python siga vivo.


## \[BREACH-ID\]: V817-010

\[SEVERITY: MEDIUM\]  
\[MODULE & LOCATION\]: `fuzz\_v817\_destructive\_hounds.py`, líneas 168–178 y sección Sabueso 3.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
El test proclama:

> “sin underflow stalls”

pero no mide stalls.

Simplemente verifica resultados numéricos.

Un stall de subnormalidad es un fenómeno de rendimiento/microarquitectura. Debe medirse con tiempo, contadores o al menos comparación controlada entre rutas FTZ/DAZ.

\[DEGENERATIVE SCENARIO\]:

La operación devuelve valores correctos en ambos casos pero tarda, por ejemplo, 20× más con subnormales. El test seguiría pasando.

\[PRODUCTION-READY FIX\]:

```
`def benchmark\_subnormal\_latency(fn, values, repeats=10000):`

`    samples = \[\]`

`    for x in values:`

`        t0 = time.perf\_counter\_ns()`

`        for \_ in range(repeats):`

`            fn(x)`

`        t1 = time.perf\_counter\_ns()`

`        samples.append((x, (t1 - t0) / repeats))`

`    return samples`


`normal = benchmark\_subnormal\_latency(fn, \[1e-2, 1e-1\])`

`subnormal = benchmark\_subnormal\_latency(fn, \[1e-315, 5e-324\])`


`ratio = max(t for \_, t in subnormal) / max(t for \_, t in normal)`

`print("subnormal/normal latency ratio:", ratio)`
```


## \[BREACH-ID\]: V817-011

\[SEVERITY: MEDIUM\]  
\[MODULE & LOCATION\]: `test\_v817\_comprehensive\_suite.py`, línea 284 y líneas 247–289.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
El benchmark que se etiqueta como:

> “Data-Path Latency”

hace una **copia de 8 MB**:

```
`src\_data -\> dst\_data`
```

Eso no mide zero-copy IPC.

Además compara el tiempo de la copia contra:

```
`baseline\_autoregressive\_ms = 140.0`
```

que es un número fijado dentro del test, no una medición del mismo workload.

Así que:

RAM memcpyvs140 ms inventariado como baseline\\text\{RAM memcpy\} \\quad \\text\{vs\} \\quad \\text\{140 ms inventariado como baseline\} 

no es una comparación de sistemas equivalentes.

\[DEGENERATIVE SCENARIO\]:  
Un sistema podría tener un PMTP zero-copy excelente pero una copia lenta; o una memoria compartida podría ser extremadamente rápida aunque el protocolo completo fuera inviable.

\[PRODUCTION-READY FIX\]:

```
`\# Benchmark A: zero-copy`

`t0 = time.perf\_counter\_ns()`

`view = shared\_memory\_view(offset, length)`

`t1 = time.perf\_counter\_ns()`


`\# Benchmark B: copy`

`t2 = time.perf\_counter\_ns()`

`dst\[:\] = src`

`t3 = time.perf\_counter\_ns()`


`zero\_copy\_ns = t1 - t0`

`copy\_ns = t3 - t2`


`print(\{`

`    "zero\_copy\_ns": zero\_copy\_ns,`

`    "copy\_ns": copy\_ns,`

`\})`
```

El benchmark debe separar explícitamente:

1. publicación; 

2. adquisición; 

3. acceso; 

4. copia; 

5. reclamación. 


## \[BREACH-ID\]: V817-012

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: `POLYDIM V817 specification`, axioma 0.2.1 proporcionado en el dossier.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
La supuesta proyección:

π(h)=h∥h∥2+ε\\pi(h)=\\frac\{h\}\{\\|h\\|\_2+\\varepsilon\} 

**no es una proyección exacta a SD−1S^\{D-1\}**.

Su norma es:

∥π(h)∥=∥h∥∥h∥+ε\<1\\|\\pi(h)\\| = \\frac\{\\|h\\|\}\{\\|h\\|+\\varepsilon\} \<1 

para cualquier 0\<∥h∥\<∞0\<\\|h\\|\<\\infty.

Por lo tanto:

π(h)∉SD−1\\pi(h)\\notin S^\{D-1\} 

exactamente.

Esto no es una cuestión de software ni una opinión: es una consecuencia algebraica directa.

\[DEGENERATIVE SCENARIO\]:

Para ∥h∥=1\\|h\\|=1:

∥π(h)∥=11+ε\\|\\pi(h)\\|=\\frac\{1\}\{1+\\varepsilon\} 

y ya no pertenece exactamente a la esfera.

Para ∥h∥≪ε\\|h\\|\\ll\\varepsilon, el vector cae todavía más lejos de la esfera.

\[PRODUCTION-READY FIX\]:

```
`bool project\_to\_sphere(`

`    const double\* h,`

`    double\* out,`

`    size\_t D,`

`    double norm\_tol)`

`\{`

`    if (!h || !out || D == 0) return false;`


`    long double ss = 0.0L;`

`    for (size\_t i = 0; i \< D; ++i) \{`

`        const long double x = h\[i\];`

`        if (!std::isfinite((double)x)) return false;`

`        ss += x \* x;`

`    \}`


`    const long double n = std::sqrt(ss);`


`    if (!(n \> norm\_tol) || !std::isfinite((double)n))`

`        return false;`


`    const double inv = 1.0 / (double)n;`


`    for (size\_t i = 0; i \< D; ++i)`

`        out\[i\] = h\[i\] \* inv;`


`    return true;`

`\}`
```

Para vector nulo, la API debe **rechazar** o aplicar una política explícita. No esconder el problema sumando `eps` al denominador y luego afirmar pertenencia exacta a la esfera.


## \[BREACH-ID\]: V817-013

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: axioma 0.2.4 del dossier; inconsistencia con `test\_v817\_comprehensive\_suite.py`, TEST 3.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
Se declara:

β1=1\\beta\_1 = 1 

como axioma.

Pero el primer Betti number no es una constante universal. Depende del espacio simplicial.

El propio TEST 3 demuestra:

```
`tetraedro sin caras: beta\_1 = 3`

`tetraedro rellenado: beta\_1 = 0`
```

Así que la especificación y el test están contradiciéndose.

\[DEGENERATIVE SCENARIO\]:  
Un complejo contractible tiene:

β1=0\\beta\_1=0 

un toro tiene:

β1=2\\beta\_1=2 

y otros complejos pueden tener valores diferentes.

\[PRODUCTION-READY FIX\]:

```
`def validate\_betti1(expected: int, computed: int) -\> None:`

`    """`

`    Betti-1 is a topological invariant of the supplied complex,`

`    not a universal POLYDIM constant.`

`    """`

`    require(expected \>= 0, "Betti-1 esperado inválido")`

`    require(`

`        computed == expected,`

`        f"Betti-1 incorrecto: esperado=\{expected\}, obtenido=\{computed\}"`

`    )`
```

Eliminá `beta1 = 1` como axioma general. Debe ser una **propiedad del complejo concreto**, no de POLYDIM.


## \[BREACH-ID\]: V817-014

\[SEVERITY: HIGH\]  
\[MODULE & LOCATION\]: axiomas de Newton–Schulz del dossier; `test\_v817\_comprehensive\_suite.py`, TEST 10, línea 351.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
El protocolo trata:

```
`q \<= 2`

`restart \[2,3,2,...\]`
```

como si eso implicara estabilidad universal.

No es así.

La convergencia de Newton–Schulz depende del escalado/espectro inicial. Trabajos recientes de 2026 sobre Muon/Newton–Schulz analizan precisamente esa dependencia del espectro y la cantidad/polynomial degree de pasos; no existe una regla general de “dos pasos + restart = convergencia garantizada” para cualquier matriz. 

\[DEGENERATIVE SCENARIO\]:

Una matriz mal escalada, singular o con singular values fuera del dominio de convergencia puede no aproximar el factor polar dentro del presupuesto de pasos.

\[PRODUCTION-READY FIX\]:

```
`def gram\_ns\_safe(A, max\_steps=5, tol=1e-6):`

`    X = spectral\_scale(A)`


`    for step in range(max\_steps):`

`        G = X.T @ X`

`        X\_next = 1.5 \* X - 0.5 \* X @ G`


`        if not np.isfinite(X\_next).all():`

`            raise RuntimeError("Newton-Schulz produjo NaN/Inf")`


`        err = np.linalg.norm(`

`            X\_next.T @ X\_next - np.eye(X.shape\[1\]),`

`            ord=2,`

`        )`


`        X = X\_next`


`        if err \<= tol:`

`            return X, step + 1, True`


`    return X, max\_steps, False`
```

El **restart es una política**, no una prueba matemática de convergencia.


## \[BREACH-ID\]: V817-015

\[SEVERITY: MEDIUM\]  
\[MODULE & LOCATION\]: `test\_v817\_comprehensive\_suite.py`, línea 6; `run\_all\_tests()`, líneas finales.

\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]:  
El archivo declara:

```
`8/8 Pruebas`
```

pero ejecuta:

```
`test\_1`

`...`

`test\_10`
```

y anuncia:

```
`10/10`
```

Eso parece menor, pero en una cadena de certificación SOTA la trazabilidad del artefacto es parte de la seguridad.

\[DEGENERATIVE SCENARIO\]:  
Un informe externo puede indicar “8/8”, mientras la versión modificada ejecuta 10, y el auditor no sabe qué matriz de aceptación corresponde al hash/versión ejecutada.

\[PRODUCTION-READY FIX\]:

```
`TESTS = \[`

`    test\_1\_secant\_rip,`

`    test\_2\_riemannian\_geodesic\_clamp,`

`    test\_3\_simplicial\_homology,`

`    test\_4\_auon\_log\_cosh\_brake,`

`    test\_5\_ffi\_thread\_local\_error\_contract,`

`    test\_6\_qsbr\_snapshot\_copy,`

`    test\_7\_information\_bottleneck\_dpi,`

`    test\_8\_data\_path\_latency\_benchmark,`

`    test\_9\_two\_nn\_baraniuk\_wakin\_feasibility,`

`    test\_10\_gram\_ns\_polar\_restart\_and\_auon\_matrix,`

`\]`


`print(f"Suite V817: \{len(TESTS)\} tests")`

`for idx, test in enumerate(TESTS, 1):`

`    print(f"\[\{idx\}/\{len(TESTS)\}\] \{test.\_\_name\_\_\}")`

`    test()`
```


# Lo que sí puedo marcar como `\[VERIFIED\_STABLE\]`

**\[VERIFIED\_STABLE\] DPI matemático:** si realmente existe la cadena de Markov

T→Z→YT\\rightarrow Z\\rightarrow Y 

entonces

I(T;Y)≤I(T;Z)I(T;Y)\\le I(T;Z) 

es una consecuencia real del Data Processing Inequality. 

**\[VERIFIED\_STABLE\] Geometría básica de la esfera:** para vectores realmente normalizados,

dS(u,v)=arccos⁡(clip⁡(uTv,−1,1))d\_S(u,v)=\\arccos(\\operatorname\{clip\}(u^Tv,-1,1)) 

es una forma válida de calcular la distancia geodésica principal de la esfera. Lo que **no** queda verificado por el TEST 2 es que toda la infraestructura preserve siempre la normalización ni que todos los caminos FFI respeten el contrato.

**\[VERIFIED\_STABLE\] TwoNN existe y es una técnica publicada**, pero su utilización exige respetar sus supuestos estadísticos y régimen local; el test V817 no convierte automáticamente su resultado en una prueba global del manifold. 

**\[VERIFIED\_STABLE\] Newton–Schulz es una técnica real para aproximar el factor polar**, pero su estabilidad/convergencia depende del escalado/espectro y del esquema concreto. 


# Y aparece un problema aún más profundo

La matriz dice:

> `TEST 8 = 2.80 GB/s (49.0×)`

mientras que la propia cabecera del test dice:

> `229.8 GB/s @ 34.8 us`

y el código realmente recalcula el valor a partir del cronómetro.

Es decir, **hay varias “ground truths” simultáneas para el mismo benchmark**. Eso debe eliminarse antes de cualquier auditoría matemática.

Además, la guía dice “8/8”, la suite ejecuta 10, y el criterio final dice 10/10. Esa cadena de metadatos ya no es reproducible de manera unívoca. 

### Conclusión de este ciclo

El hallazgo más peligroso hasta ahora **no es un `segfault`**. Es que V817 tiene varios lugares donde el test puede devolver “PASS” sin haber demostrado la propiedad que el nombre del test afirma demostrar.

Y hay una incompatibilidad física objetiva en la supuesta certificación A4-6300 + AVX2. AMD documenta para ese procesador AVX/FMA4, no AVX2. 

El siguiente nivel que queda abierto es el **kernel nativo real**: ahí es donde hay que buscar, línea por línea, UB de C/C++, aliasing `data\_ptr()`, layout ABI real, `repr(C)`, atomics, reclamación QSBR, `catch\_unwind`, SIMD ilegítimo y las fórmulas exactas de Cayley/NS. En el RAR actual esos fuentes no están presentes, así que no voy a inventar una sola línea de ellos.  
Profundizar la auditoría sin inventar evidencia

- Construir una matriz anti-alucinación de evidencia 

- Auditar las afirmaciones matemáticas restantes 

Continúa con una auditoría matemática rigurosa de los axiomas de Clifford, Cayley-SMW, NorMuon, Moonlight y Newton–Schulz. Para cada afirmación, separa teorema, supuesto, contraejemplo y corrección, y marca explícitamente qué está verificado y qué no.

Sí. Este ciclo lo llevé un nivel más abajo: no estoy preguntando “¿la fórmula parece razonable?”, sino **qué parte es un teorema, qué hipótesis necesita, qué contraejemplo la rompe y qué formulación sí queda matemáticamente defendible**.

También contrasté las piezas SOTA con fuentes primarias o de referencia: Clifford/rotors, Cayley en Stiefel, Muon/Newton–Schulz, Moonlight y NorMuon. 

## Mapa de verdad matemática

| **Afirmación** | **Estado** |
| :-: | :-: |
| RvR†R v R^\\dagger es una isometría para un rotor euclídeo correctamente normalizado | **\[VERIFIED\_STABLE\]**, bajo hipótesis precisas |
| “drift ≤8.88×10−16\\le 8.88\\times10^\{-16\}” universal hasta D=107D=10^7 | **\[NOT\_VERIFIED\]** |
| Cl(D) genérico puede ser el tipo de dato denso nativo para D=107D=10^7 | **\[FALSE AS WRITTEN\]** |
| Fórmula Cayley-SMW de V817 y su cota κ(M)=O(1)\\kappa(M)=O(1) | **\[FALSE AS WRITTEN\]** |
| El Cayley correcto preserva Stiefel exactamente en aritmética exacta | **\[VERIFIED\_STABLE\]**, bajo hipótesis |
| NorMuon necesita sólo O(D)O(D) estado adicional | **\[VERIFIED\_STABLE\]**, interpretando D=mD=m filas |
| Post-NS row normalization preserva automáticamente κ\\kappa baja | **\[NOT A THEOREM\]** |
| 0.2max⁡(m,n)0.2\\sqrt\{\\max(m,n)\} cancela exactamente el RMS dimensional | **\[VERIFIED\_STABLE\]** sólo para polar exacta/full-rank |
| Esa misma fórmula es automáticamente válida después de NorMuon | **\[FALSE / MISAPPLIED\]** |
| Newton–Schulz clásico converge bajo condiciones espectrales adecuadas | **\[VERIFIED\_STABLE\]** |
| Quintic 3.4445,−4.7750,2.03153.4445,-4.7750,2.0315 converge a 11 | **\[FALSE\]** |
| “5 pasos” o “\[2,3,2,…\]” garantizan polarización/convergencia | **\[NOT\_VERIFIED\]** |


# 1. AXIOMA DE CLIFFORD

## C-01 — Rotor + sandwich product

### Afirmación

R=exp⁡(−θB/2),v′=RvR†R=\\exp(-\\theta B/2),\\qquad v'=RvR^\\dagger 

y

∥v′∥2=∥v∥2.\\|v'\\|\_2=\\|v\\|\_2. 

### Teorema

En un espacio euclídeo y con un rotor RR normalizado,

RR~=1,R−1=R~,R\\widetilde R=1, \\qquad R^\{-1\}=\\widetilde R, 

y la acción

v↦RvR−1v\\mapsto RvR^\{-1\} 

es una transformación ortogonal sobre el subespacio vectorial. La literatura de álgebra geométrica formula precisamente el rotor y el sandwich product de esta manera. 

Por tanto,

(v′)2=RvR−1RvR−1=Rv2R−1=v2.(v')^2 = RvR^\{-1\}RvR^\{-1\} = Rv^2R^\{-1\} = v^2. 

Para firma euclídea,

v2=∥v∥22,v^2=\\|v\\|\_2^2, 

luego la norma se conserva.

### Supuestos necesarios

No basta con escribir “Clifford”. Hay que fijar:

Cl(D,0)Cl(D,0) 

o la firma correspondiente;

RR~=1;R\\widetilde R=1; R†=R~R^\\dagger=\\widetilde R 

si usás †\\dagger como reverse/adjoint apropiado.

Además, si querés llamar a θ\\theta **el ángulo de rotación**, un bivector simple unitario es la interpretación limpia. La forma exponencial de un rotor simple se documenta como R=cos⁡(θ/2)−Bsin⁡(θ/2)R=\\cos(\\theta/2)-B\\sin(\\theta/2). 

### Contraejemplo

Si RR no está normalizado, el sandwich general es

v′=RvR†,v' = RvR^\\dagger, 

pero si

RR†=c≠1,RR^\\dagger=c\\neq1, 

entonces, en general,

∥v′∥22=c2∥v∥22\\|v'\\|\_2^2=c^2\\|v\\|\_2^2 

en lugar de una isometría.

Y si Cl(p,q)Cl(p,q) es indefinida, preservar la forma cuadrática no significa preservar la norma euclídea ℓ2\\ell\_2.

### Corrección

El axioma debería ser:

R∈Spin(D),RR~=1,v′=RvR~\\boxed\{ R\\in Spin(D),\\quad R\\widetilde R=1,\\quad v'=Rv\\widetilde R \} 

con firma euclídea explícita.

### Estado

**\[VERIFIED\_STABLE\]**, pero **condicional a esas hipótesis**.


# 2. CLIFFORD A D=107D=10^7: EL PROBLEMA QUE PUEDE ESTAR ESCONDIDO

## C-02 — “Clifford es el tipo de dato nativo”

Esta frase necesita una cirugía.

### Teorema

Para V=RDV=\\mathbb R^D,

dim⁡Cl(V)=2D.\\dim Cl(V)=2^D. 

Eso está establecido en la teoría de las álgebras de Clifford. 

Para D=107D=10^7,

21072^\{10^7\} 

es obviamente intratable.

Pero incluso un **bivector denso** tiene

(D2)=D(D−1)2\\binom D2=\\frac\{D(D-1)\}2 

coeficientes.

Para D=107D=10^7:

(1072)=49 999 995 000 000.\\binom\{10^7\}\{2\}=49\\,999\\,995\\,000\\,000. 

A 8 bytes:

≈400 TB\\approx 400\\text\{ TB\} 

para **un solo bivector denso FP64**.

### Supuesto

La única vía viable es que POLYDIM no pretenda almacenar un elemento genérico de Cl(D)Cl(D), sino una representación estructurada:

- bivectores simples; 

- sumas de pocos bivectores; 

- representación de bajo rango; 

- rotores factorizados; 

- multivectores dispersos/estructurados. 

### Contraejemplo

Si el diseño dice:

> “Cl(D) es el tipo nativo”

pero internamente almacena todos los coeficientes de grado 0…D0\\ldots D, el sistema muere mucho antes de llegar al cálculo útil.

### Corrección

La especificación debe hablar de una **familia representacional**, no del álgebra completa:

B=UVT−VUTB=UV^T-VU^T 

con

U,V∈RD×r,r≪D.U,V\\in\\mathbb R^\{D\\times r\}, \\qquad r\\ll D. 

Eso sí permite memoria

O(Dr)O(Dr) 

en vez de

O(D2)O(D^2) 

para un bivector de bajo rango.

### Estado

**\[VERIFIED\_STABLE\]** que el álgebra densa explota exponencialmente; **\[UNVERIFIED\]** cuál es exactamente la representación estructurada de V817.

Esto es importante: **“no serializamos a JSON” no implica que automáticamente hayamos eliminado la explosión combinatoria de Clifford**.


# 3. “MACHINE DRIFT ≤8.88×10−16\\le 8.88\\times10^\{-16\}”

## C-03

### Teorema

La isometría es exacta en aritmética exacta.

### Pero el número 8.88×10−168.88\\times10^\{-16\}

No es un teorema de Clifford.

En floating point aparecen errores en productos, sumas, normalización, `exp`, FMA, reducción paralela, etc. Higham documenta que la acumulación de error de sumas e inner products depende del tamaño y del método de reducción; el análisis clásico introduce términos del tipo γn\\gamma\_n. 

Para una suma secuencial típica:

γn=nu1−nu.\\gamma\_n=\\frac\{nu\}\{1-nu\}. 

Con binary64,

u=2−53≈1.11×10−16.u=2^\{-53\}\\approx1.11\\times10^\{-16\}. 

Para

n=107,n=10^7, 

el orden de magnitud es

γn≈1.11×10−9,\\gamma\_n\\approx1.11\\times10^\{-9\}, 

no 10−1610^\{-16\}.

Eso **no significa que el error real vaya a ser 10−910^\{-9\}**; significa que un límite universal de 8.88×10−168.88\\times10^\{-16\} no puede salir gratuitamente del hecho “es Clifford”.

### Contraejemplo

Un cálculo de norma/dot product con una reducción desfavorable en D=107D=10^7 puede tener error acumulado muy superior a 4u4u.

### Corrección

Hay que reemplazar:

“drift≤8.88e−16”\\text\{“drift\}\\le8.88e\{-16\}\\text\{”\} 

por algo como:

∥QTQ−I∥≤E(D,dtype,reduction,ISA)\\boxed\{ \\|Q^TQ-I\\|\\le E(D,\\text\{dtype\},\\text\{reduction\},\\text\{ISA\}) \} 

y producir EE mediante análisis backward/forward del kernel concreto.

### Estado

**\[NOT\_VERIFIED\]**.


# 4. CAYLEY-SMW DE STIEFEL

Aquí está uno de los puntos más delicados del dossier.

## C-04 — Cayley correcto

Para

X∈St(D,K),XTX=IK,X\\in St(D,K), \\qquad X^TX=I\_K, 

un vector tangente ZZ satisface

XTZ+ZTX=0.X^TZ+Z^TX=0. 

La construcción Cayley clásica usa una matriz skew-symmetric WW y

RX(tZ)=(I−t2W)−1(I+t2W)X.R\_X(tZ) = \\left(I-\\frac t2 W\\right)^\{-1\} \\left(I+\\frac t2 W\\right)X. 

Esa curva permanece en la variedad de Stiefel y tiene derivada inicial ZZ. Esto está establecido en el trabajo de Wen–Yin y formulaciones posteriores. 

### Estado

**\[VERIFIED\_STABLE\]**.


# 5. C-05 — LA FÓRMULA V817 DE MM

La afirmación dada es

M=IK+α∗(S−ST)+(α∗)2SST.M= I\_K+\\alpha^\*(S-S^T) +(\\alpha^\*)^2SS^T. 

y

α∗=αmax⁡(1,∣α∣ σmax⁡(S−ST)).\\alpha^\* = \\frac\{\\alpha\}\{ \\max(1,|\\alpha|\\,\\sigma\_\{\\max\}(S-S^T)) \}. 

Después se afirma:

κ(M)≤O(1).\\kappa(M)\\le O(1). 

## Teorema

No existe un teorema general que permita concluir eso de esa expresión.

## Contraejemplo directo

Tomá

S=(c001).S= \\begin\{pmatrix\} c&0\\\\ 0&1 \\end\{pmatrix\}. 

Entonces

S−ST=0.S-S^T=0. 

Por tanto:

α∗=α.\\alpha^\*=\\alpha. 

Y

M=I+α2SST=(1+α2c2001+α2).M = I+\\alpha^2SS^T = \\begin\{pmatrix\} 1+\\alpha^2c^2&0\\\\ 0&1+\\alpha^2 \\end\{pmatrix\}. 

Así,

κ2(M)=1+α2c21+α2.\\kappa\_2(M) = \\frac\{1+\\alpha^2c^2\} \{1+\\alpha^2\}. 

Cuando

c→∞,c\\to\\infty, 

tenemos

κ2(M)→∞.\\kappa\_2(M)\\to\\infty. 

No es O(1)O(1).

### El problema profundo

La normalización de α\\alpha controla

S−ST,S-S^T, 

pero **no controla la parte simétrica de SS**, mientras que SSTSS^T sí la ve.

### Corrección

Para una Cayley genuina se debe controlar la matriz skew

WT=−WW^T=-W 

y usar

Q=(I−τ2W)−1(I+τ2W).Q= \\left(I-\\frac\{\\tau\}\{2\}W\\right)^\{-1\} \\left(I+\\frac\{\\tau\}\{2\}W\\right). 

Si

τ2∥W∥2≤12,\\frac\{\\tau\}\{2\}\\|W\\|\_2\\le \\frac12, 

entonces, en exact arithmetic, QQ es ortogonal y

κ2(Q)=1.\\kappa\_2(Q)=1. 

Incluso el denominador I−τ2WI-\\frac\{\\tau\}\{2\}W tiene un análisis espectral limpio porque WW skew-symmetric.

### Estado

**\[FALSE AS WRITTEN\]** para la fórmula de MM y su cota de condición.


# 6. C-06 — SMW: TAMBIÉN HAY UN PROBLEMA DE DIMENSIÓN

En la construcción de Wen–Yin, el skew matrix de Stiefel puede factorizarse como

W=UVTW=UV^T 

con factores de tamaño aproximadamente

D×2K,D\\times 2K, 

y SMW reduce el problema grande a un sistema pequeño del orden de 2K2K, no mágicamente a K×KK\\times K sin hipótesis adicionales. 

La forma genérica es:

(I−cUVT)−1=I+cU(I−cVTU)−1VT.(I-cUV^T)^\{-1\} = I+cU(I-cV^TU)^\{-1\}V^T. 

### Contraejemplo

Si V817 define S∈RD×KS\\in\\mathbb R^\{D\\times K\}, entonces

S−STS-S^T 

ni siquiera está definido.

Para que esa resta exista, SS tendría que ser cuadrada.

### Corrección

La especificación debe separar:

X,Z∈RD×KX,Z\\in\\mathbb R^\{D\\times K\} 

de

W∈RD×DW\\in\\mathbb R^\{D\\times D\} 

y después:

W=UVT,U,V∈RD×r.W=UV^T, \\qquad U,V\\in\\mathbb R^\{D\\times r\}. 

Luego SMW trabaja con

Ir−cVTU.I\_r-cV^TU. 

### Estado

**\[NOT\_VERIFIED / DIMENSIONALLY AMBIGUOUS\]** en la formulación V817.


# 7. NORMUON

## C-07 — Lo que NorMuon realmente hace

La formulación publicada de NorMuon es:

Mt=β1Mt−1+(1−β1)GtM\_t=\\beta\_1M\_\{t-1\}+(1-\\beta\_1)G\_t Ot=NS5(Mt)O\_t=NS5(M\_t) vt=β2vt−1+(1−β2)mean⁡cols(Ot2)v\_t= \\beta\_2v\_\{t-1\} + (1-\\beta\_2)\\operatorname\{mean\}\_\{cols\}(O\_t^2) O^t=Ot/(Vt+ϵ)\\widehat O\_t = O\_t/ (\\sqrt\{V\_t\}+\\epsilon) 

y luego

η^=0.2ηmn∥O^t∥F.\\hat\\eta = 0.2\\eta \\frac\{\\sqrt\{mn\}\} \{\\|\\widehat O\_t\\|\_F\}. 

La publicación de NorMuon confirma explícitamente ese pipeline: **orthogonalize first, row normalization afterwards**, y estado vt∈Rmv\_t\\in\\mathbb R^m. 

### Estado

**\[VERIFIED\_STABLE\]** como descripción del algoritmo publicado.


# 8. C-08 — “POST-NS ROW NORMALIZATION PRESERVA LA CONDICIÓN”

Aquí hay que separar descripción empírica de teorema.

### Teorema

Para una matriz arbitraria diagonal de reescalado

Dr=diag⁡(d1,…,dm),D\_r=\\operatorname\{diag\}(d\_1,\\dots,d\_m), 

tenemos

κ(DrO)≤κ(Dr)κ(O).\\kappa(D\_rO) \\le \\kappa(D\_r)\\kappa(O). 

Por tanto, aunque

κ(O)=1,\\kappa(O)=1, 

podemos tener

κ(DrO)≫1.\\kappa(D\_rO)\\gg1. 

### Contraejemplo

Tomá

O=I2,Dr=(10−8001).O=I\_2, \\qquad D\_r= \\begin\{pmatrix\} 10^\{-8\}&0\\\\ 0&1 \\end\{pmatrix\}. 

Entonces

κ(O)=1,\\kappa(O)=1, 

pero

κ(DrO)=108.\\kappa(D\_rO)=10^8. 

### Matiz importante

Esto **no prueba que NorMuon real necesariamente produzca ese peor caso**, porque DrD\_r no es arbitrario: viene de la estadística de OtO\_t y de su EMA.

Lo que sí prueba es:

> no existe un teorema algebraico de “row normalization ⇒ conditioning preservada”.

La propia publicación describe la preservación de las ventajas de condicionamiento como propiedad observada/experimental, no como una igualdad algebraica universal. 

### Corrección

La propiedad que conviene certificar es:

κ(O^t)κ(Ot)\\frac\{\\kappa(\\widehat O\_t)\} \{\\kappa(O\_t)\} 

o directamente

κ(O^t)≤Kbound\\kappa(\\widehat O\_t) \\le K\_\{\\rm bound\} 

para el dominio de entradas definido.

No afirmar preservación automática.

### Estado

**\[NOT\_A\_THEOREM\]**.


# 9. C-09 — EL ESTADO O(D)O(D) DE NORMUON

Esta parte sí está bastante limpia.

El artículo define

vt∈Rm.v\_t\\in\\mathbb R^m. 

Por lo tanto el estado adicional es:

O(m).O(m). 

Si m=D=105m=D=10^5 y FP32:

105×4=0.4 MB.10^5\\times4=0.4\\text\{ MB\}. 

Eso cuadra.

Pero a

D=107:D=10^7: 107×4=40 MB.10^7\\times4 = 40\\text\{ MB\}. 

### Estado

**\[VERIFIED\_STABLE\]** que es O(D)O(D), no O(1)O(1).

La diferencia es importante para tu requisito de “hot path sin allocaciones”: podés tener **memoria O(D) preasignada**, pero no podés describirla como memoria constante.


# 10. MOONLIGHT: 0.2max⁡(m,n)0.2\\sqrt\{\\max(m,n)\}

## C-10 — ¿Hay una base matemática real?

Sí.

Supongamos que OO es el factor polar exacto de una matriz full-rank.

Si

m≤n,m\\le n, 

entonces

OOT=ImOO^T=I\_m 

y

∥O∥F2=m.\\|O\\|\_F^2=m. 

El RMS sobre los mnmn elementos es

RMS(O)=∥O∥Fmn=mmn=1n.RMS(O) = \\frac\{\\|O\\|\_F\}\{\\sqrt\{mn\}\} = \\frac\{\\sqrt m\}\{\\sqrt\{mn\}\} = \\frac1\{\\sqrt n\}. 

Como

n=max⁡(m,n),n=\\max(m,n), 

queda:

RMS(O)=1max⁡(m,n).RMS(O) = \\frac1\{\\sqrt\{\\max(m,n)\}\}. 

Por tanto:

0.2max⁡(m,n) O0.2\\sqrt\{\\max(m,n)\}\\,O 

tiene RMS exactamente

0.2.0.2. 

Análogamente si m\>nm\>n.

### Estado

**\[VERIFIED\_STABLE\]**, bajo estas hipótesis:

1. polar exacta; 

2. full rank; 

3. RMS calculado sobre todos los mnmn elementos; 

4. sin modificación posterior. 

La implementación/documentación actual de PyTorch describe precisamente el ajuste Moonshot como:

γ←0.2 γmax⁡(A,B).\\gamma\\leftarrow0.2\\,\\gamma\\sqrt\{\\max(A,B)\}. 


# 11. C-11 — PERO ESO NO ES TODAVÍA NORMUON

Este es un punto crucial que veo en la especificación V817.

NorMuon hace:

O⟶O^O \\longrightarrow \\widehat O 

después de la ortogonalización.

La fórmula publicada entonces no dice simplemente:

O^⋅0.2max⁡(m,n).\\widehat O\\cdot0.2\\sqrt\{\\max(m,n)\}. 

Dice:

η^=0.2ηmn∥O^∥F.\\hat\\eta = 0.2\\eta \\frac\{\\sqrt\{mn\}\} \{\\|\\widehat O\\|\_F\}. 

### Demostración

Idealmente, ignorando ϵ\\epsilon, si cada fila queda normalizada de forma que

1n∑jO^ij2=1,\\frac1n\\sum\_j \\widehat O\_\{ij\}^2=1, 

entonces:

∥O^∥F2=mn.\\|\\widehat O\\|\_F^2=mn. 

Luego:

η^=0.2η.\\hat\\eta = 0.2\\eta. 

No aparece el factor adicional

max⁡(m,n)\\sqrt\{\\max(m,n)\} 

porque ya fue absorbido por la normalización basada en la norma Frobenius.

### Contraejemplo conceptual

Si después de NorMuon volvés a aplicar:

0.2max⁡(m,n),0.2\\sqrt\{\\max(m,n)\}, 

estarías aplicando una segunda corrección de shape.

### Corrección

Hay que elegir una de estas dos arquitecturas:

**Muon/Moonlight:**

O→0.2max⁡(m,n)OO \\rightarrow 0.2\\sqrt\{\\max(m,n)\}O 

o

**NorMuon:**

O→O^→η^=0.2ηmn∥O^∥F.O \\rightarrow \\widehat O \\rightarrow \\hat\\eta = 0.2\\eta \\frac\{\\sqrt\{mn\}\}\{\\|\\widehat O\\|\_F\}. 

No mezclar las dos como si fueran algebraicamente equivalentes.

### Estado

**\[FALSE / MISAPPLIED\]** para la afirmación V817 si aplica Moonlight scaling directamente después de NorMuon.


# 12. C-12 — ρ=0.2\\rho=0.2 NO ES UN TEOREMA UNIVERSAL

La igualdad:

RMS(ρmax⁡(m,n)O)=ρRMS\\left( \\rho\\sqrt\{\\max(m,n)\}O \\right)=\\rho 

sí es algebraica bajo las hipótesis anteriores.

Pero:

ρ=0.2\\rho=0.2 

no sale de geometría de Stiefel ni de Clifford.

Es una elección de ajuste para hacer comparable la escala de actualización con AdamW. Moonlight documenta el mecanismo como ajuste de RMS y validación experimental de transferencia del learning rate. 

### Estado

“ρ=0.2” = disen˜o empıˊrico, no teorema\\boxed\{ \\text\{“\}\\rho=0.2\\text\{” = diseño empírico, no teorema\} \} 


# 13. NEWTON–SCHULZ CLÁSICO

## C-13 — Teorema correcto

Para el Newton–Schulz cúbico:

Xk+1=12Xk(3I−XkTXk),X\_\{k+1\} = \\frac12X\_k(3I-X\_k^TX\_k), 

las singular values evolucionan de acuerdo con

xk+1=12xk(3−xk2).x\_\{k+1\} = \\frac12x\_k(3-x\_k^2). 

Si las singular values iniciales están en el dominio apropiado, por ejemplo después de escalado espectral:

0\<x0≤1,0\<x\_0\\le1, 

las no nulas convergen hacia 1.

Es la base clásica para aproximar el factor polar.

### Supuesto

La entrada debe estar adecuadamente escalada y ser suficientemente regular.

### Problema

Si

σi(A)=0,\\sigma\_i(A)=0, 

entonces

p(0)=0.p(0)=0. 

La singular value cero permanece cero.

Por tanto Newton–Schulz **no puede crear rango que no existe**.

### Estado

**\[VERIFIED\_STABLE\]** como teorema condicionado.


# 14. C-14 — EL QUINTIC V817/ MUON NO CONVERGE A 1

Acá encontramos una brecha matemática especialmente fuerte.

El código upstream de Muon usa:

a=3.4445,b=−4.7750,c=2.0315.a=3.4445,\\quad b=-4.7750,\\quad c=2.0315. 

El polinomio escalar es:

p(x)=3.4445x−4.7750x3+2.0315x5.p(x)=3.4445x-4.7750x^3+2.0315x^5. 

Evaluemos exactamente en el supuesto objetivo:

p(1)=3.4445−4.7750+2.0315=0.701.p(1) = 3.4445-4.7750+2.0315 = 0.701. 

Por lo tanto:

p(1)≠1\\boxed\{p(1)\\ne1\} 

.

### Esto mata una afirmación concreta

Si V817 dice:

> “Newton–Schulz converge a polar / singular values → 1”

esa frase es **falsa para esos coeficientes**.

De hecho, empezando en

x0=1x\_0=1 

obtenemos:

1→0.701→1.1136202→0.7207059→1.0899742→0.69643641 \\rightarrow 0.701 \\rightarrow 1.1136202 \\rightarrow 0.7207059 \\rightarrow 1.0899742 \\rightarrow 0.6964364 

en sólo cinco pasos.

No hay convergencia a 1.

### El propio diseño upstream lo reconoce

La implementación de Muon explica que esta quintica deliberadamente no converge a UVTUV^T exactamente y produce algo tipo

US′VTUS'V^T 

con singular values aproximadamente en una banda alrededor de 1. 

### Estado

\[FALSE\] “NS5 exact polar factor”\\boxed\{\\text\{\[FALSE\] “NS5 exact polar factor”\}\} 

pero

\\boxed\{\\text\{\[VERIFIED\_STABLE\] “NS5 es un operador aproximado de balanceo espectral”\}\} 

.

Esta distinción es fundamental.


# 15. C-15 — “5 PASOS = CONVERGENCIA”

### Teorema

No.

Los cinco pasos de Muon son una **decisión algorítmica/empírica**, no una garantía matemática universal.

La fuente de Muon explica explícitamente que los coeficientes fueron ajustados experimentalmente para velocidad y que el resultado no es el polar exacto. 

### Contraejemplo

Ya tenemos uno:

x0=1.x\_0=1. 

Después de 5 pasos:

x5≈0.6964.x\_5\\approx0.6964. 

Si “convergido” significa

∣x−1∣\<10−6,|x-1|\<10^\{-6\}, 

claramente:

∣0.6964−1∣≈0.3036.|0.6964-1|\\approx0.3036. 

### Corrección

Hay que cambiar el contrato de API:

```
`NS5:`

`    approximate spectral balancing operator`


`NO:`

`    exact polar decomposition`
```

Y si necesitás polar exacta/controlled:

∥XTX−I∥≤ε\\|X^TX-I\\| \\le \\varepsilon 

debe ser una condición explícita.

### Estado

**\[FALSE\]** como garantía de polarización exacta.


# 16. C-16 — “RESTART \[2,3,2,…\] GARANTIZA ESTABILIDAD”

Esto tampoco sale de Newton–Schulz.

### Contraejemplo escalar

Con

x0=0.01x\_0=0.01 

y el quintic de Muon:

0.01→0.03444→0.11843.0.01 \\rightarrow 0.03444 \\rightarrow 0.11843. 

Después de dos pasos sigue lejísimos de 1.

Entonces:

q=2q=2 

no proporciona por sí mismo una convergencia.

### Más fuerte

No hay un teorema que diga:

q≤2⇒Newton-Schulz estable\\boxed\{ q\\le2 \\Rightarrow \\text\{Newton-Schulz estable\} \} 

sin especificar:

- escalado; 

- espectro; 

- coeficientes; 

- criterio de restart; 

- qué estado conserva el restart; 

- cuál es la métrica de error; 

- cuándo se acepta convergencia. 

### Corrección

Definir un monitor:

ek=∥XkTXk−I∥2e\_k= \\|X\_k^TX\_k-I\\|\_2 

o la variante rectangular apropiada.

Y hacer:

```
`repeat`

`    perform q iterations`

`    measure e\_k`

`    if e\_k \<= tolerance:`

`        STOP: verified`

`    if nonfinite or divergence:`

`        RESCALE / FAIL`

`until max\_steps`
```

### Estado

**\[NOT\_VERIFIED\]** como garantía general.


# 17. UNA DISTINCIÓN QUE V817 DEBE HACER OBLIGATORIAMENTE

Ahora mismo hay tres objetos conceptualmente diferentes:

### A. Factor polar exacto

U=UVTU=UV^T 

para

A=UΣVT.A=U\\Sigma V^T. 

### B. Newton–Schulz convergente

Aproxima UU bajo hipótesis de escalado/convergencia.

### C. Muon NS5 quintic

p(x)=3.4445x−4.775x3+2.0315x5p(x)=3.4445x-4.775x^3+2.0315x^5 

y deliberadamente **no** busca precisión polar matemática completa; busca una actualización espectralmente equilibrada. 

V817 no debe llamar A, B y C “polar projection” indistintamente.

Ese es un problema de **semántica matemática del contrato**, y en un sistema de alta integridad eso importa tanto como un bug.


# 18. RESULTADO DEL CICLO

## `\[VERIFIED\_STABLE\]`

RvR~R v\\widetilde R 

es una isometría en el caso euclídeo correcto y rotor normalizado. 

El Cayley estándar para Stiefel preserva la restricción en aritmética exacta. 

NorMuon realmente usa orthogonalization → estadísticas por fila → row normalization → escala Frobenius dinámica. 

El factor Moonshot

0.2max⁡(m,n)0.2\\sqrt\{\\max(m,n)\} 

tiene una justificación algebraica de RMS para una actualización polar exacta/full-rank y está documentado en implementaciones actuales. 

## `\[FALSE AS WRITTEN\]`

M=I+α(S−ST)+α2SSTM=I+\\alpha(S-S^T)+\\alpha^2SS^T 

con la cota universal

κ(M)=O(1).\\kappa(M)=O(1). 

El contraejemplo diagonal rompe la afirmación.

También es incorrecto tratar el quintic Muon:

3.4445x−4.775x3+2.0315x53.4445x-4.775x^3+2.0315x^5 

como una iteración que converge a 11: directamente,

p(1)=0.701.p(1)=0.701. 

El repositorio upstream confirma además que la intención de esa variante no es producir exactamente UVTUV^T. 

## `\[NOT\_VERIFIED\]`

El supuesto:

drift≤8.88×10−16\\text\{drift\}\\le8.88\\times10^\{-16\} 

a D=107D=10^7.

La afirmación:

q≤2⇒NS estable/convergente.q\\le2 \\Rightarrow \\text\{NS estable/convergente\}. 

La afirmación de que row normalization **preserva matemáticamente** el buen condicionamiento de Muon para todo input.


### El punto que considero más importante para POLYDIM

La arquitectura puede quedar matemáticamente sólida, pero necesita **separar tres capas de contrato**:

Geometrıˊa exacta≠algoritmo numeˊrico≠garantıˊa fıˊsica en hardware\\boxed\{ \\text\{Geometría exacta\} \\quad\\neq\\quad \\text\{algoritmo numérico\} \\quad\\neq\\quad \\text\{garantía física en hardware\} \} 

Por ejemplo:

RvR~Rv\\widetilde R 

puede tener una prueba matemática exacta;

NS5(M)NS5(M) 

puede ser un operador aproximado muy bueno;

y el kernel SIMD puede tener un error finito dependiente de ISA/dtype/reducción.

No se debe convertir automáticamente:

teorema→algoritmo→“certificado en silicio”.\\text\{teorema\} \\rightarrow \\text\{algoritmo\} \\rightarrow \\text\{“certificado en silicio”\}. 

Ahí es donde estaban escondidas varias de las afirmaciones más peligrosas de V817.











