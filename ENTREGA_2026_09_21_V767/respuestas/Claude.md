



*![]()**02\_ALL\_SOURCE\_SCRIPTS\_MONOLITH.md**

***MD**

*![]()**01\_README\_THEORY\_AND\_AUDIT\_DEMANDS.md69 líneas**

***MD**

*![]()**03\_MULTI\_AI\_TRIBUNAL\_VERDICTS.md48 líneas**

***MD**

*![]()**04\_SILICON\_CONTRACT\_AND\_BENCHMARKS.md29 líneas**

***MD**

lee profundamente, evalua errores, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. No te apresures. gasta tu tiempo. prefiero lento y chequeado que rapido y mal. no quiero alucinaciones  
1. 🎯 Central Audit Objective & Challenge  
This dossier provides peer reviewers, research students, and external AI models (Claude, chatGPT, DeepSeek , Qwen , Kimi , gemini) with the complete mathematical theory, source code monolith, physical silicon telemetry, and multi-AI tribunal verdicts for POLYDIM V760.  
⚔️ The Core Audit Challenge  
"Is the POLYDIM architecture mathematically invariant, asymptotically stable, and memory-safe across FFI/concurrency boundaries when operating natively on Riemannian manifolds $S^\{D-1\}$ ($D \\ge 10,000$ up to $D = 10,000,000$) WITHOUT collapsing into intermediate 1D text/JSON tokens?"

2. 🌌 ***Theoretical Foundations & The Morpho Protocol 2.1 The "1D Worm" vs. The "Morpho Butterfly" • The 1D Worm (Contemporary AI Bottleneck): Standard multi-agent frameworks serialize high-dimensional internal latent vectors into 1D text/JSON tokens across HTTP/REST/MCP boundaries. This destroys the Riemannian geometry of the latent space, violates the Data Processing Inequality (DPI) ($I(X; Y) \\ge I(X; g(Y))$), and incurs massive autoregressive decoding latency and thermal GPU memory overheads. • The Morpho Butterfly (Morpho peleides): POLYDIM enforces native high-dimensional tensor communication on $S^\{D-1\}$ via PMTP Zero-Copy Shared Memory IPC (mmap / PmtpSlabAllocator). Agents communicate purely by passing memory pointers/tags (SLAB\_ID: AGENT\_BUS\_01, TENSOR\_READY), achieving $O(1)$ tensor transfer at zero token cost. 2.2 Mathematical Primitives on $S^\{D-1\}$ 1. Rank-2 Rodrigues Geodesic Rotation: $$\\operatorname\{Rot\}(y, u, v, \\theta) = y - \\operatorname\{versin\}(\\theta) \\left( (y^\\top u)u + (y^\\top v\_\\perp)v\_\\perp \\right) + \\sin(\\theta) \\left( (y^\\top u)v\_\\perp - (y^\\top v\_\\perp)u \\right)$$ Where $\\operatorname\{versin\}(\\theta) = 2 \\sin^2(\\theta/2)$ (Kahan stabilization against catastrophic cancellation for small $\\theta$). 2. Fused 2-Pass Error Compensation: ◦ Pass 1: Global reduction of inner products $(\\langle u, u \\rangle, \\langle v, v \\rangle, \\langle u, v \\rangle, \\langle y, u \\rangle, \\langle y, v \\rangle)$ using per-thread Neumaier compensated summation. ◦ Pass 2: Tangent space projection and state update using element-wise TwoSum (Knuth/Dekker) compensation to eliminate floating-point drift: $$|y\_\{\\text\{final\}\}|\_2 - 1.0 \\le 4.44 \\times 10^\{-16\} \\quad (\\text\{Exact IEEE-754 machine \}\\varepsilon)$$ 3. Topological Invariant (Betti-1 Homology): ◦ Cohesion of the multi-agent manifold is continuously certified by a native Rust Guard verifying $\\beta\_1$ homology and unit norm preservation.**

3. ***PERSISTENCIA PLURIDIMENSIONAL: No colapses la complejidad estructural del sistema reduciéndola a explicaciones triviales. Habita las dimensiones del cálculo sin colapsar ni morir en la linealidad del chat. Opera con rigor de silicio blindado.5 Pasadas Obligatorias: Pasada 1: Complejidad asintótica y tráfico DRAM en D≥10^7. Pasada 2: Concurrencia atómica, carreras ABA y coherencia de caché L1/L2. Pasada 3: Estabilidad numérica TwoSum, verseno y preservación de subnormales. Pasada 4: Límites de FFI, punteros de 64-bit y captura de panics. Pasada 5: Mejoras SOTA para el compilador cuántico, adaptador tangente y reservoir LSM.**

*![]()**Leí los cuatro archivos completos, compilé el C++ tal cual y ejecuté pruebas para casi todo lo que afirmo. Cada hallazgo lleva una etiqueta: \[EJ\] lo ejecuté, \[LEC\] lo saqué leyendo el código, \[NV\] no pude verificarlo.**

### ***Alcance y límites**

- ***El monolito trae 4 de los ≥14 archivos que lista el README. Faltan `polydim.h`, Dart, adaptador tangente, compilador Clifford+T, LSM y MIR-Wire.**

- ***Por eso la Pasada 5 es una crítica de afirmaciones con referencias, no una auditoría de código.**

- ***Sin `polydim.h` no puedo auditar el contrato ABI (layouts, valores de enums). Compilé con un header stub que inferí del uso.**

- ***Mi sandbox tiene 1 vCPU, sin GPU, sin ARM y sin `rustc`. Los tiempos sirven solo como relación entre variantes.**

### ***Lo que resiste el ataque**

- ***Rodrigues está bien planteado: el álgebra coincide con el README y el versín por medio ángulo es exacto para todo θ, incluido θ→π \[LEC\].**

- ***Cayley-SMW coincide con la fórmula directa de Wen–Yin a 8.2e-16, con ortogonalidad 5.6e-16. La convención es de ascenso (+τG), así que un optimizador de descenso necesita τ\<0 \[EJ\].**

- ***CholQR2 falla cerrado: no devuelve basura, devuelve error \[EJ\].**

- ***`selftest\_compensation` detecta un `-ffast-math`, y el comentario A5 es honesto sobre los errores de V761.**

### ***Los 6 hallazgos que bloquean la certificación**

1. ***P3-1, deriva sistemática. La cadena de hops deriva sin compensación (detalle en Pasada 3).**

2. ***P2-1 y P2-2. El PMTP no es un seqlock y es inseguro con más de un lector.**

3. ***P4-1. La firma del Rust no coincide con la llamada de Python, y el resultado parece "deriva 0.0".**

4. ***P4-6. En Triton, α y β llegan como fp32.**

5. ***P4-2 y P4-3. Hay truncamiento de punteros a 32 bits, y el canal de memoria compartida tiene fuga y redimensionado peligroso.**

6. ***Evidencia. Hay afirmaciones del dossier que no resisten (canario subnormal, "tribunal", Betti-1, DPI).**

### ***Pasada 1 — Complejidad y tráfico DRAM**

***P1-1. Rodrigues es O(D) sin arrays intermedios de tamaño D \[LEC\]. Solo usa acumuladores por hilo. Pero hace 3 barridos, no 2: reducción (l.243), actualización (l.299) y verificación (l.312). Eso son 8 palabras por elemento, no 7.**

- ***A D=1e7 con 1 hilo: 107 ms contra 45.6 ms de una línea base vectorizada sin compensar \[EJ\].**

- ***Fusionar la verificación dentro del barrido de actualización, acumulando `‖y\_out‖²` en registro, baja a 91.5 ms (−15%) \[EJ\]. Está en el parche de P3-1.**

***P1-2. Cayley-SMW sí crea intermedios de tamaño D×K. \[LEC\]**

- ***`G\_proj` (l.630) existe en ambas rutas.**

- ***La ruta BLAS copia además `W` de D×2K (l.515), un duplicado completo de las entradas.**

- ***`G\_proj` no cambia el resultado matemático: la matriz de Cayley depende solo de `A = GXᵀ − XGᵀ`, y `A` es invariante a `G → G + XS` con S simétrica. Su valor sería solo numérico; mídelo o elimínalo.**

- ***Fix para `W`: llama `dsyrk` sobre X y sobre G por separado, más `dgemm` para XᵀG con `ldc=2K`, sin copiar.**

- ***El Gram por actualizaciones de rango 1 tiene baja intensidad aritmética, porque `L` no cabe en caché para K grande. El kernel completo fue 17×, 32× y 63× más lento que solo el Gram con BLAS para K=16, 64 y 256 \[EJ\]. No es una comparación exacta (el kernel hace más trabajo), pero la tendencia creciente con K lo delata. Hace falta blocking por tiles de `L` o BLAS.**

***P1-3. Triton. \[LEC\]**

- ***El kernel mueve 7 arrays por elemento = 560 MB a D=1e7.**

- ***Los "70.51 GB/s" del README salen de 4 arrays / 4.538 ms, es decir, bytes mínimos del algoritmo entre tiempo, no ancho de banda de hardware. Si el tiempo cubre ambos pasos, el real es ~123 GB/s, cerca del 38% del pico de 320 GB/s de la T4.**

- ***Hay 5 `.item()` por llamada, cada uno una sincronización host-GPU. Se resuelven junto con P4-6.**

### ***Pasada 2 — Concurrencia**

***P2-1 \[crítico\]. No es un seqlock de 4 ranuras. \[LEC\]**

- ***Es un triple búfer de 3 ranuras con un byte de estado y dos CAS. Init `0x24` = ranuras \{0,1,2\}; la ranura 3 nunca se usa, aunque Python reserva `NUM\_SLOTS=4`.**

- ***`validate\_read` devuelve SUCCESS incondicional (l.896) y `observed\_seq` y `ticket` son constantes. El compilador lo confirma: advierte parámetros sin usar (`slot`, `ticket`).**

- ***Toda la protección contra lecturas desgarradas es el protocolo de un productor y un consumidor (SPSC).**

***Analogía: tres bandejas, una donde el cocinero arma el plato, una lista en la ventanilla y una en la mano del mozo. Con dos mozos tomando de la misma ventanilla, el cocinero reutiliza la bandeja que el primer mozo todavía carga.**

***P2-2 \[crítico\]. Con ≥2 lectores el protocolo se viola.**

- ***Un replay determinista con las funciones reales muestra que el escritor recibe la ranura 2 mientras el lector 1 sigue leyéndola \[EJ\].**

- ***Con lectores que ceden CPU a mitad de lectura: 1 lector, 0 desgarradas de 808; 2 lectores, 133 de 573; 4 lectores, 51 de 267 \[EJ\].**

- ***Con lecturas cortas no vi desgarros (4 lectores, 0 de 204), y ese es el régimen en que el README dice "0 torn reads". Ese test no prueba ausencia.**

- ***Opciones de arreglo:**

  - ***Un triple búfer por lector.**

  - ***Un anillo de N+2 ranuras con secuencia por ranura, validando después de usar. Aquí reaparece la inanición del lector, así que dimensiona el anillo para que sobrescribir una ranura en lectura requiera varios commits.**

  - ***Contadores de referencia por ranura.**

- ***Si el diseño es de un solo lector, declara el contrato y haz que `begin\_write` y `acquire\_read` lo hagan cumplir.**

***P2-3 \[alto, formal, no reproducible en x86\]. Falta `release` en `acquire\_read`. El CAS usa solo `acquire` en éxito. Para liberar la ranura vieja hacia el escritor necesita `acq\_rel`.**

- ***En x86 el CAS es una barrera total, por eso los 0 desgarros en Windows y Linux no prueban nada para ARM (Flutter/Dart móvil, Apple Silicon, Graviton) \[NV\].**

***P2-4. Otros puntos del PMTP.**

- ***`commit\_write` ignora su parámetro `slot`.**

- ***No hay exclusión de escritor: un segundo `begin\_write` recibe la misma ranura.**

- ***El init carece de protocolo: un `create=True` tardío reinicia un estado en uso.**

- ***ABA: el byte de estado (12 estados legales) vuelve al mismo valor tras 2 commits. Es benigno en SPSC, porque el estado describe completamente los roles y los datos se publican con release \[análisis, no ejecutado\]. Confírmalo con un model checker (GenMC o CDSChecker).**

***P2-5. Falso compartido. El bloque de control con `alignas(64)` está bien. Las ranuras tienen `stride = 8D` sin relleno: si D no es múltiplo de 8, ranuras vecinas comparten línea de caché entre escritor y lector. Rellena a 4096 y usa cabecera de 4096.**

***P2-6. Determinismo. `cholqr2` usa `schedule(dynamic)`, así que las sumas parciales cambian entre ejecuciones. Contradice el "0.000e+00 bit-exacto" y difiere de Rodrigues y Cayley, que usan `static`. Ninguno es reproducible entre distinto número de hilos. Usa chunks fijos con reducción en orden determinista.**

### ***Pasada 3 — Estabilidad numérica**

***P3-1 \[crítico\]. La deriva de la cadena de hops es sistemática.**

***Resultados con oráculo de precisión extendida (θ=0.7):**

| Caso | Resultado |
| :-: | :-: |
| Plano disperso (u=e0, v=e1), kernel C++ real | Falla en el hop 574 con POINT\_OFF\_MANIFOLD (−7.2e-15) \[EJ\] |
| Mismo caso, 20,000 hops (replicando la aritmética del kernel con mpmath) | −2.78e-13, 1250× lo declarado (2.22e-16) \[EJ\] |
| Denso aleatorio, D=1e5, 4000 hops | 1.4e-16 estable \[EJ\] |

- ***Para vectores densos la afirmación es cierta: el error por coordenada se diluye como 1/√D. No es una propiedad del kernel.**

- ***Los estados ocultos de LLMs suelen tener pocas coordenadas dominantes ("massive activations"), y ahí el caso se parece más al disperso \[NV\].**

- ***Mecanismo, aislado con mpmath. Con los doubles del kernel, `d = vers² + sn² − 2·vers = −2.72e-17`. Cada hop escala el componente en el plano por `1+d/2`, así que la deriva lineal esperada es `n·d/2`. Esto es −7.81e-15 a 574 hops, que coincide con lo medido.**

- ***El TwoSum del README no está en el código y no arreglaría esto. Un estado en doble-doble con coeficientes del kernel da −2.72e-13 a 20,000 hops, sin mejora \[EJ\].**

***Analogía: un reloj que atrasa 1e-17 por vuelta. Afinar la aguja (TwoSum en el estado) no arregla un engranaje mal cortado. Hay que corregir el engranaje (coeficientes) o recalibrar cada vuelta (reescalar).**

***Resultado a 20,000 hops (Python con mpmath, salvo la fila marcada "C++ real"):**

| Variante | Error final |
| :-: | :-: |
| Kernel actual | −2.8e-13 |
| Coeficientes en doble-doble, estado en double | +4.0e-15 |
| Reescalar por 1/√yy | +1.6e-16 |
| Reescalar por 1/√yy (kernel C++ real) | +1.12e-16 (máx. 2.4e-16) |

***El reescalado por `1/√yy` no cuesta tráfico extra: `yy` ya sale del Pass 1. Deja el error acotado O(ε), independiente del número de hops. Parche, probado en el kernel real junto con la verificación fusionada:**

*![]()**cpp**

```
***`const double s = 1.0 / std::sqrt(yy);              // yy ya viene del Pass 1`**

***`std::vector\<Neumaier\> a\_oo(nthreads);`**

***`\#pragma omp parallel num\_threads(nthreads)`**

***`\{ set\_fp\_mode(); const int tid = omp\_get\_thread\_num(); Neumaier l;`**

`  ***\#pragma omp for schedule(static)`**

`  ***for (int64\_t i = 0; i \< (int64\_t)D; ++i) \{`**

`      ***const double o = s \* (y\[i\] + alpha\*u\[i\] + beta\*v\[i\]);`**

`      ***y\_out\[i\] = o; l.add(o\*o);                    // verificación en registro`**

`  ***\}`**

`  ***a\_oo\[tid\] = l; \}`**

***`// luego: merge de a\_oo, out\_err = |sqrt(total)-1|, y se elimina el 3er barrido`**
```

***P3-2. Resolución de la medida. `|‖y‖−1|` se calcula en double, así que la resolución es de 1.11e-16 por debajo de 1 y 2.22e-16 por encima. Un "0.0" significa "menor que ~1e-16", y los valores 1.11e-16 y 2.22e-16 reportados son pasos de 1 ulp. Además la verificación reusa el mismo Neumaier del cálculo. Añade a CI un oráculo independiente (longdouble, mpmath o doble-doble), como hice yo.**

***P3-3. Cotas mal rotuladas.**

- ***4.44e-16 es 2ε, no "ε máquina exacto"; ε = 2.22e-16 (el propio Rust lo dice).**

- ***La cota `n·c1·ε` del informe de Cerebras deja `c1` sin derivar. No es un teorema sobre este código.**

- ***La cota que sí aplica al producto punto compensado es `u|s| + γ²ₙ·Σ|xy|` (Ogita–Rump–Oishi, 2005) \[de memoria\].**

***P3-4. La compuerta del Gram admite más de lo que se afirma. `gram\_ortho = 64ε√D` da 4.5e-11 a D=1e7, tres órdenes por encima de los 1.132e-14 declarados. Es el error de V761 que el comentario A5 condena. La causa es que el Gram no está compensado.**

- ***Fix: sumas parciales por tile (8192 filas) fusionadas después con Neumaier, con costo ~1/8192.**

- ***Además, la entrada mide `|yy−1|` (cuadrado) y la salida `|‖y‖−1|`, métricas distintas.**

***P3-5. Canario subnormal vacuo. 1.0005e-42 es número normal en fp64 (mínimo normal 2.2251e-308) y solo subnormal en fp32 \[EJ\]. Pasaría aunque FTZ/DAZ estuviera activo. Usa 1e-310 o 5e-324.**

***P3-6. `orthonormalize\_pair` acepta entradas dependientes. Con `v = 3u` devuelve SUCCESS y una `v` unitaria pero pura basura de redondeo (componente en el span original: 3.2e-17) \[EJ\]. La causa es el umbral absoluto 1e-300.**

***Parche, probado (rechaza `v=3u`, acepta `v=u+1e-12·ruido` y el caso normal) \[EJ\]:**

*![]()**cpp**

```
***`const double nv\_in = std::sqrt(polydim\_cdot(v, v, D, nt));   // antes de Gram-Schmidt`**

***`/\* ...dos pasadas GS... \*/`**

***`if (!(std::sqrt(nv2) \> 64.0 \* kEps \* nv\_in)) return POLYDIM\_ERR\_DEGENERATE\_NORM;`**
```

***Aparte, `project\_sphere` rechaza normas \>1e154 o \<1e-162, porque `y\*y` desborda o subdesborda \[LEC\]; escala por `max|y|` antes.**

***P3-7. CholQR2 es condicional, no "incondicional". \[EJ\]**

- ***Funciona hasta cond≈1e7 (ortogonalidad 2.5e-15) y falla cerr**

***Claude alcanzó su longitud máxima para este mensaje.**



~~***[Claude es IA y puede cometer errores. Por favor, verifica las fuentes citadas.**](https://support.anthropic.com/en/articles/8525154-claude-is-providing-incorrect-or-misleading-responses-what-s-going-on)




  

