***Used 1 tool, Compute MI proxy for noisy latent variables and verify arithmetic**

***Compute MI proxy for noisy latent variables and verify arithmetic**














***Python**

***Python**

***Python**

***Python**

***rust**

***rust**

***rust**

***Python**

***Python**

***Voy a verificar numéricamente las sospechas antes de escribir nada, para no alucinar.**

***Used 1 tool**

***Execute Python code**


***Thinking complete**

# 🛡️ ***AUDITORÍA BULLDOG — POLYDIM V817 (Sesión 2026-09-29)**

## ⚠️ ***DECLARACIÓN DE ALCANCE (antecede a todo juicio)**

***Los artefactos que la auditoría manda atacar — `polydim\_v817\_monolito.py`, `kernel\_rust\_v817.rs`, `kernel\_cpp\_v817.cpp` — NO fueron subidos. Solo recibí: 2 harness de Python, 2 documentos de especificación y el prompt de auditoría. Por tanto:**

- ***No certifico ni descertifico el silicio. Cualquier veredicto "10/10 PASS" sería una alucinación: la suite ni siquiera puede ejecutarse sin el monolito.**

- ***Lo que sigue es una auditoría real y verificada de lo que SÍ está en mis manos: los harness, las especificaciones matemáticas, y la coherencia interna del paquete. Todo hallazgo numérico fue confirmado en silicio (Python/NumPy) antes de reportarse.**

***Los verificaciones ejecutadas confirman cada cifra que cito abajo. Procedo por severidad.**


***plain**

```
***`\[BREACH-ID\]: V817-LETHAL-01`**

***`\[SEVERITY\]: LETHAL`**

***`\[MODULE & LOCATION\]: Paquete completo — artefactos ausentes`**

***`\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]: El mandato exige "prove correctness on silicon",`**

`  ***pero los objetos de la prueba no existen en el material entregado. La certificación`**

`  ***"10/10 EXIT CODE 0" es irreproducible: test\_v817\_comprehensive\_suite.py línea 33 hace`**

`  ***"from polydim\_v817\_monolito import ..." y ese módulo no está en la entrega.`**

`  ***Audité los harness: todo lo que afirman sobre el núcleo es no-falsable.`**

***`\[DEGENERATIVE SCENARIO\]: Un evaluador externo (Cerebras/DeepSeek/o3) reproduce los`**

`  ***Pasos 1-3 de guia\_de\_evaluacion\_adversarial\_v817.md §2 y obtiene ModuleNotFoundError.`**

`  ***El "ground truth" de la Matriz de Aceptación queda como claim no verificado.`**

***`\[PRODUCTION-READY FIX\]: Entregar como mínimo:`**

`  ***1. kernel\_rust\_v817.rs (fuente, no solo DLL)`**

`  ***2. kernel\_cpp\_v817.cpp`**

`  ***3. polydim\_v817\_monolito.py (wrapper ctypes + firma exacta de cada función exportada)`**

`  ***Sin esto, ningún veredicto sobre QSBR/TLS/Stiefel es emitible. Punto.`**
```

***plain**

```
***`\[BREACH-ID\]: V817-LETHAL-02`**

***`\[SEVERITY\]: LETHAL`**

***`\[MODULE & LOCATION\]: test\_v817\_comprehensive\_suite.py — docstring TEST 8 (líneas 10, 286-293)`**

`                     ***vs guia\_de\_evaluacion\_adversarial\_v817.md §3 fila TEST 8`**

***`\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]: Docstring afirma "229.8 GB/s @ 34.8 us" para 8 MB.`**

`  ***Verificado: 8e6 B / 34.8e-6 s = 229.9 GB/s — IMPOSSIBLE en el hardware de certificación:`**

`  ***el A4-6300 (Richland, sin L3, DDR3-1600 dual-channel) tiene techo teórico de 25.6 GB/s.`**

`  ***Además contradice la guía del mismo paquete: "2.80 GB/s (49.0×)" → 140 ms/49 = 2857 us,`**

`  ***no 34.8 us. 34.8 us sería 4023×, no 49×. Las dos cifras del mismo release difieren`**

`  ***82× entre sí. O el docstring mide otra cosa (payload distinto, caché caliente, tiempo`**

`  ***de marshalling exclusión) o es fabricado. En ambos casos la Certificación Física pierde`**

`  ***integridad: el documento no es reproducible desde el código adjunto.`**

***`\[DEGENERATIVE SCENARIO\]: Revisor reproduce TEST 8, obtiene ~2.8 GB/s, y el docstring`**

`  ***prometido 229.8 GB/s → descarte del release entero por datos no replicables.`**

***`\[PRODUCTION-READY FIX\]: Corregir el docstring y separar métricas:`**
```

***Python**

```
***`\# test\_v817\_comprehensive\_suite.py — reemplazar docstring y bloque de prints de TEST 8`***

***`\# DATOS CORRECTOS (coherentes con guia §3):`***

***`\#   Latencia de Ruta de Datos: 2.80 GB/s efectivos en DRAM @ p50 = 2857 us (8 MB)`***

***`\#   Razón de Latencia: 49.0x frente a baseline autorregresivo de 140 ms`***

***`\# PROHIBIDO citar 229.8 GB/s / 34.8 us salvo que se documente:`***

***`\#   (a) tamaño de carga útil real, (b) que residía en caché, (c) máquina de medición.`***

***`\# El comparativo memcpy-vs-decode es metodológicamente inválido como "latencia de`***

***`\# cómputo": memorizar bytes ≠ decodificar tokens. Reportarlos como métricas separadas`***

***`\# y eliminar la conclusión causal de la línea "Nota Metodológica".`***
```

***plain**

```
***`\[BREACH-ID\]: V817-HIGH-01`**

***`\[SEVERITY\]: HIGH`**

***`\[MODULE & LOCATION\]: test\_v817\_comprehensive\_suite.py — test\_7\_information\_bottleneck\_dpi (líneas 218-263)`**

***`\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]: El "estimador" NO estima información mutua.`**

`  ***Calcula 0.5\*log(1 + var(T)/mse) — el canal gaussiano ESCALAR con SNR = var/mse.`**

`  ***Verificado en silicio: proxy = 3.0017 nats (coincide con la guía), pero la MI gaussiana`**

`  ***verdadera del canal Z = T + N(0, 0.05²) en d=8 es 8 × 0.5·log(1+400) = 23.98 nats.`**

`  ***El test reporta 1/8 de la MI real y la guía lo consigna como "ground truth" (3.0017 ≥ 1.3968).`**

`  ***Consecuencia: el claim "DPI de Shannon verificada" es falso como demostración;`**

`  ***el proxy no cumple consistencia (no es aditivo por dimensión, no es KSG-consistente)`**

`  ***y puede violarse en configuraciones ajenas a esta construcción particular. El assert`**

`  ***mi\_latent \>= mi\_text pasa aquí por construcción del ruido (0.05 \<\< 0.25), no por teorema.`**

***`\[DEGENERATIVE SCENARIO\]: Cualquier canal con SNR alto por dimensión (p.ej. ruido`**

`  ***heterocedástico) hace que el proxy se comporte no-monótonamente; el test daría FAIL`**

`  ***en un sistema correcto o PASS en uno roto. Certificación de DPI sin validez.`**

***`\[PRODUCTION-READY FIX\]:`**
```

***Python**

```
***`\# Opción A (rigurosa): estimador kNN (KSG) por pares acumulados`***

***`from sklearn.feature\_selection import mutual\_info\_regression`**

***`def estimate\_mi\_knn(source, rep, k=5, seed=0):`**

`    ***\# I(T;R) = sum\_j I(T\_j ; R) solo si T\_j ⊥ T\_k | R — asumir y DOCUMENTAR, o usar KSG multivariado`***

`    ***total = 0.0`**

`    ***for j in range(source.shape\[1\]):`**

`        ***mi = mutual\_info\_regression(rep, source\[:, j\], n\_neighbors=k,`**

`                                    ***random\_state=seed)  *\# I(T\_j ; R) en nats`***

`        ***total += float(mi\[0\])`**

`    ***return total`**

***`\# Y añadir intervalo de confianza por bootstrap sobre I\_latent - I\_text; el assert`***

***`\# debe exigir que el IC al 95% de la DIFERENCIA excluya 0:`***

***`assert mi\_latent - mi\_text \> 0 and boot\_ci\_low \> 0, "DPI no establecida estadísticamente"`**


***`\# Opción B (honesta, mínima): renombrar el test a "test\_7\_snr\_proxy" y eliminar toda`***

***`\# referencia a Shannon/DPI de documentos. Un proxy de SNR NO es el DPI.`***
```

***plain**

```
***`\[BREACH-ID\]: V817-HIGH-02`**

***`\[SEVERITY\]: HIGH`**

***`\[MODULE & LOCATION\]: test\_v817\_comprehensive\_suite.py línea 98`**

`                     ***(assert ang\_1 \< 1e-10) y fuzz\_v817\_destructive\_hounds.py línea 198`**

`                     ***(assert ang\_clamp == 0.0)`**

***`\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]: Aserción numéricamente imposible de garantizar.`**

`  ***Para u ≡ v unitarios, dot(u,u) en fp64 con D=5·10^4 acarrea error de suma δ ~ 1e-12`**

`  ***(paralelo SIMD) → arccos(1-δ) ≈ sqrt(2δ) ≈ 1.4e-6 \> 1e-10. Verificado: acos(1-1e-12)=1.414e-6.`**

`  ***El assert solo pasa si cosθ redondea EXACTAMENTE a 1.0, lo cual depende del orden de`**

`  ***reducción SIMD, del número de hilos OpenMP y del compilador. Es un test que pasa o falla`**

`  ***por azar de hardware — exactamente lo que la guía prometía eliminar. La igualdad exacta`**

`  ***== 0.0 en el fuzz es la misma fragilidad disfrazada de "boundary test".`**

***`\[DEGENERATIVE SCENARIO\]: Recompilar el kernel Rust con otro vectorizador (AVX-512, NEON)`**

`  ***o cambiar el chunk de reducción → dot = 0.9999999999999998 → FAIL en CI ajeno.`**

***`\[PRODUCTION-READY FIX\]: Doble barrera — contrato en el kernel + tolerancia honesta en el test:`**
```

***Python**

```
***`\# En el kernel (Rust): cortocircuito de identidad bit-exacta ANTES de la reducción`***

***`\# if std::ptr::eq(u, v) || (u\[..n\] == v\[..n\]) \{ \*angle\_out = 0.0; return 0; \}`***

***`\# y en el cómputo general usar la forma chordal (evita la singularidad de arccos por diseño):`***

***`\#   d = 2.0 \* (0.5 \* ||u - v||).clamp(0.0, 1.0).asin()`***


***`\# En el test: reemplazar línea 98`***

***`assert ang\_1 \<= 1e-6, f"auto-distancia debe ser ~0, obtuvo \{ang\_1\}"  *\# cota de arccos(1-2ulp) ≈ 2.1e-8, margen 100x`***

***`\# y en fuzz línea 198 reemplazar igualdad exacta por`***

***`assert ang\_clamp \<= 1e-12, f"auto-geodésica debe colapsar a 0, obtuvo \{ang\_clamp\}"`**
```

***plain**

```
***`\[BREACH-ID\]: V817-HIGH-03`**

***`\[SEVERITY\]: HIGH`**

***`\[MODULE & LOCATION\]: Especificación — PART I, axioma 3 (Stiefel Cayley-SMW)`**

***`\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]: Dos defectos, ambos verificados:`**

`  ***(a) Término cuadrático erróneo: M = I + α(S−Sᵀ) + α²SSᵀ. Para que el polinomio herede`**

`      ***la estructura del generador skew, el término debe ser (S−Sᵀ)², no SSᵀ. Tal como está`**

`      ***escrito, si S es simétrico (momentum real nunca es skew), A = S−Sᵀ = 0 y M = I + α²SSᵀ.`**

`  ***(b) Normalización ciega: α\* normaliza contra σ\_max(S−Sᵀ), que es 0 para S simétrica →`**

`      ***α\* = α sin control. CONTRAEJEMPLO EN SILICIO: S = diag(1, 1e-3), α̂ = 100 →`**

`      ***σ\_max(S−Sᵀ) = 0 → α\* = 100 → M = diag(1+10⁴·1, 1+10⁴·1e-6) → κ(M) = 9902.`**

`      ***El axioma promete κ(M) ≤ O(1); el enunciado LITERAL produce κ → ∞ cuadrático en α̂.`**

`  ***Matiz honesto: si S fuera skew por construcción, el polinomio I+C+C² con C skew y`**

`  ***|c|≤1 tiene |λ|² = 1−c²+c⁴ ∈ \[0.75, 1\] → κ ≤ 1.33 (verificado: min|λ| = 0.866).`**

`  ***O sea: la cota de condición sobrevive solo bajo una lectura caritativa, y ni siquiera`**

`  ***esa lectura es la transformada de Cayley (que exige coeficientes 2A + 2A² + … y da`**

`  ***κ = 1 exacta con M ortogonal). El axioma 2 (deriva isométrica ≤ 8.88e-16) no se transfiere.`**

***`\[DEGENERATIVE SCENARIO\]: Optimizador Stiefel con momentum simétrico dominante: paso`**

`  ***α̂ grande + normalización según axioma → retraction M con κ ~ 10⁴ → paso efectivo`**

`  ***ampliado 10⁴× en la dirección mayor → divergencia del entrenamiento en la primera`**

`  ***iteración con gradiente mal condicionado.`**

***`\[PRODUCTION-READY FIX\]: Cayley EXACTA con SMW, normalizando contra la norma completa:`**
```

***rust**

```
***`// Retracción de Cayley exacta: M = (I + αA/2)(I − αA/2)^\{-1\}, A = S − Sᵀ (skew)`***

***`// M es ortogonal: κ(M) = 1.0 exacto, preserva St(D,K) por construcción.`***

***`// α limitado contra σ\_max(A) del GENERADOR COMPLETO, con margen de seguridad c \< 2:`***

***`let a = skew\_part(&s);                    *// A = S − Sᵀ, nunca usar SSᵀ del S crudo`***

***`let sigma = spectral\_norm\_power\_iter(&a); *// pow-iteración, buffers O(1), sin heap en hot path`***

***`let alpha = (alpha\_hat / sigma.max(1e-12)).min(1.0);   *// c = 1 ⇒ |α·σ/2| ≤ 0.5 \< 1`***

***`// M = I + αA (I − αA/2)^\{-1\}  — resolver K sistemas por SMW; O(DK²), buffers preasignados`***

***`// Eliminar de la especificación el término α²SSᵀ o reescribirlo como α²(S−Sᵀ)²/4.`***

***`// Y corregir el axioma: la cota κ ≤ O(1) solo es válida para el polinomio en (S−Sᵀ).`***
```

***plain**

```
***`\[BREACH-ID\]: V817-HIGH-04`**

***`\[SEVERITY\]: HIGH`**

***`\[MODULE & LOCATION\]: fuzz\_v817\_destructive\_hounds.py — sabueso\_1 (líneas 55-117)`**

***`\[MATHEMATICAL / PHYSICAL ROOT CAUSE\]: concurrent.futures.wait(futures) NO propaga`**

`  ***excepciones de los workers. Si thread\_worker lanza (ValueError de NumPy, fallo del`**

`  ***FFI, assert interno futuro), la excepción queda almacenada en el Future y NUNCA se`**

`  ***re-lanza: el sabueso imprime "✅ PASSED: Cero colisiones" con hilos muertos.`**

`  ***El harness anti-adversarial produce falsos PASOS — exactamente la falla de`**

`  ***certificación que el mandato prohíbe. Solo se inspecciona errors\_detected (appends`**

`  ***explícitos), no future.exception().`**

***`\[DEGENERATIVE SCENARIO\]: Bajo los 100 hilos, un worker encuentra NaN y lanza; 99`**

`  ***terminan limpios; wait() retorna; verdict "SILICIO BLINDADO" con 1 hilo muerto y`**

`  ***50 transacciones perdidas.`**

***`\[PRODUCTION-READY FIX\]:`**
```

***Python**

```
***`with concurrent.futures.ThreadPoolExecutor(max\_workers=num\_threads) as executor:`**

`    ***futures = \[executor.submit(thread\_worker, tid) for tid in range(num\_threads)\]`**

`    ***concurrent.futures.wait(futures)`**

`    ***for tid, f in enumerate(futures):`**

`        ***exc = f.exception()                      *\# \<- la línea que faltaba`***

`        ***if exc is not None:`**

`            ***errors\_detected.append(f"Thread \{tid\}: EXCEPCIÓN NO CAPTURADA: \{exc!r\}")`**
```


### ***Hallazgos MEDIUM**

***plain**

```
***`\[BREACH-ID\]: V817-MED-01  \[SEVERITY\]: MEDIUM`**

***`\[MODULE & LOCATION\]: Prompt de auditoría — PARTE I, axioma 6 ("Gram NS Segment Bound")`**

***`\[RAÍZ\]: "q\_segment \<= 2 continuous steps max. Schedule: \[2, 3, 2, ...\]" — la agenda`**

`  ***contiene un segmento de 3, violando la cota declarada de 2. Contradicción interna`**

`  ***del spec; TEST 10 llama max\_total\_steps=5 con agenda implícita \[2,3\]: ambiguo.`**

***`\[FIX\]: Elegir una: (a) cota q ≤ 3 con agenda \[2,3,2\] documentada, o (b) agenda \[2,2,2\].`**

`  ***Escribirla como invariante en el código Rust: debug\_assert!(seg\_len \<= Q\_MAX).`**
```

***plain**

```
***`\[BREACH-ID\]: V817-MED-02  \[SEVERITY\]: MEDIUM`**

***`\[MODULE & LOCATION\]: fuzz Sabueso 2 (líneas 143, 163, 190): códigos -2/-3/-3`**

***`\[RAÍZ\]: Sobrecarga de códigos: -3 significa "scale\_s ≤ 0" en AuON y "norma cero" en`**

`  ***geodésica. Los tests asumen números mágicos (-1, -2, -3) frágiles a refactor. El`**

`  ***cliente FFI no puede disambiguar fallos distintos con el mismo código.`**

***`\[FIX\]:`**
```

***rust**

```
***`\#\[repr(i32)\]`**

***`pub enum PolydimErrV817 \{ Ok = 0, NullPointer = -1, NanOrInf = -2,`**

`    ***InvalidScale = -3, ZeroNormVector = -4, DimensionMismatch = -5 \}`**

***`\#\[no\_mangle\] pub extern "C" fn polydim\_error\_name\_v817(code: i32) -\> \*const c\_char`**

***`// Tests: assert ret == int(PolydimErrV817.NanOrInf), no -2.`***
```

***plain**

```
***`\[BREACH-ID\]: V817-MED-03  \[SEVERITY\]: MEDIUM`**

***`\[MODULE & LOCATION\]: fuzz Sabueso 3 (líneas 228-247): claim "Cero Memory Leak"`**

***`\[RAÍZ\]: El leak NUNCA se mide. 50 iteraciones de copia sin instrumentación de RSS`**

`  ***no pruean ausencia de fuga — prueban ausencia de crash. Claim de certificación sin`**

`  ***instrumento de medición.`**

***`\[FIX\]:`**
```

***Python**

```
***`import resource`**

***`def rss\_kb():`**

`    ***with open("/proc/self/statm") as f:`**

`        ***return int(f.read().split()\[1\]) \* os.sysconf("SC\_PAGE\_SIZE") // 1024`**

***`rss0 = rss\_kb()`**

***`\# ... las 50 iteraciones ...`***

***`rss1 = rss\_kb()`**

***`assert rss1 - rss0 \< payload\_16mb // 1024, f"RSS creció \{rss1-rss0\} KB — sospecha de leak"`**

***`\# Nota: ru\_maxrss es pico monótono en Linux; para deltas usar /proc/self/statm o psutil.`***
```

***plain**

```
***`\[BREACH-ID\]: V817-MED-04  \[SEVERITY\]: MEDIUM`**

***`\[MODULE & LOCATION\]: Especificación axioma 6 vs TEST 4; fuzz Sabueso 2 §2.2`**

***`\[RAÍZ\]: (a) El spec dice "emergency brake evaluated in Log-Cosh domain |x\_i| ≤ 30"`**

`  ***pero TEST 4 fuerza |x| = 100,000 (z = x/s = 40,000 \> 30). Si el kernel clampa z a`**

`  ***±30 el test pasa; el spec y el test se contradicen en la cota. (b) Nunca se prueba`**

`  ***z → ∞: x = 1e308, s = 1e-15 ⇒ z = 1e323 = +Inf ⇒ logcosh(Inf) = Inf ⇒ loss = Inf`**

`  ***(o NaN vía Inf·0 si s² underflowea). (c) Región muerta: s aceptado = 1e-15 ⇒`**

`  ***gradiente saturado λ·s ≈ 1e-15 ≈ 0: el freno desaparece sin error.`**

***`\[FIX\]:`**
```

***rust**

```
***`let z = (x / s).clamp(-30.0, 30.0);           *// dominio acotado, coherente con el spec`***

***`if !(s \>= 1e-6) \{ return ZeroNormVector/InvalidScale \}  *// zona muerta prohibida`***

***`// Añadir al fuzz: auon\_brake(1e308, 1e-15) debe retornar código de error, no Inf.`***
```

***plain**

```
***`\[BREACH-ID\]: V817-MED-05  \[SEVERITY\]: MEDIUM`**

***`\[MODULE & LOCATION\]: test\_v817\_comprehensive\_suite.py — TEST 10 (líneas 309-311)`**

***`\[RAÍZ\]: ortho\_error = ||QQᵀ−I||\_F / n. La norma de Frobenius de I es √n; la`**

`  ***normalización correcta es /√n. Con /n el error queda subestimado por factor √n = 8`**

`  ***para n=64 — el "auditor de isometría" enmascara 8× de error. Y el umbral 0.2 es`**

`  ***~3 órdenes de magnitud más laxo que lo que NS5 entrega en bien condicionado (~1e-3):`**

`  ***la compuerta auditada carece de dientes.`**

***`\[FIX\]:`**
```

***Python**

```
***`ortho\_error = np.linalg.norm(qqt - ident, ord='fro') / np.sqrt(n)`**

***`assert ortho\_error \< 1e-2, f"isometría insuficiente para certificación: \{ortho\_error\}"`**
```


### ***Hallazgos LOW (lote, todos verificados en el texto)**

- ***V817-LOW-01: `test\_2` comentario "Caso 4: Estrés de punto flotante forzado (1.0 + 1e-15)" — el caso nunca se construye; solo se prueba identidad exacta. Igual en fuzz §2.4 ("perturbación singular" = `u.copy()`). Cobertura declarada ≠ cobertura real.**

- ***V817-LOW-02: Docstring "8/8 Pruebas" (línea 12) vs suite que corre 10 tests (línea 273 dice 10/10). Cosmético pero indica docstring no revisado — coherente con LETHAL-02.**

- ***V817-LOW-03: TEST 1 usa un subespacio lineal plano (`coords @ basis.T`), no una variedad con reach τ = 0.5: el término de volumen/alcance de Baraniuk–Wakin jamás se ejercita; 100 puntos no certifican α\_K. El TEST 9 estima en el mismo tipo de objeto plano.**

- ***V817-LOW-04: `assert "Null pointers" in last\_err` (fuzz línea 82): el test de aislamiento TLS depende del texto exacto del mensaje de error — se rompe con cualquier rewording. Usar el código de error, no el string.**

- ***V817-LOW-05: TEST 9 sin semilla fija sobre el estimador Two-NN (la semilla 42 fija los datos, no la varianza del estimador en runtime): `abs(d\_mle − 12) \< 5` puede ser flake en hardware ajeno; sin CI de repetibilidad.**


## 📋 ***Veredicto y siguiente paso**

***Hallazgos reales y verificados: 14 (2 LETHAL, 4 HIGH, 5 MEDIUM, 5 LOW incluidos en el lote). Cero componentes marcados `\[VERIFIED\_STABLE\]` — no tengo el código para verificarlos, y afirmarlo sería traición al mandato.**

***El error que bloquea todos los demás es V817-LETHAL-01: para continuar la cadena ("el siguiente error") necesito que subas el monolito y los dos kernels fuente. Con esos archiefs ejecuto la segunda pasada: QSBR (ABA, 128B isolation, torn writes), TLS/UAF en FFI, FMA vs TwoSum, y el NS con reinicio q real. Sin ellos, cualquier veredicto adicional sería alucinación — y eso es exactamente lo que me pediste no hacer.**

