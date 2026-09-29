



*![]()**auditoria\_externa.rar**

***RAR**

*![]()**03\_INSTRUCCIONES\_PROMPT\_IA.md9 líneas**

***MD**

***lee 03\_INSTRUCCIONES\_PROMPT\_IA.md lee profundamente, evalua errores, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua co**

***pasted**

*![]()**Extraje el `.rar` y leí completo `kernel\_cpp\_v808.cpp`, `kernel\_rust\_v808.rs`, `stiefel\_math\_v808.cpp` y `polydim\_solver\_abi\_v808.h`, además de contrastarlos contra `04\_REPORTE\_DE\_BRECHAS\_Y\_FIXES.md` y `auditoria\_linea\_por\_linea.md` (los "RESUELTO" previos). Dos notas operativas antes del informe:**

- ***Las instrucciones piden auditar `kernel\_cpp\_v807.cpp` / `kernel\_rust\_v807.rs`, pero el `.rar` solo trae `v808`. Audité v808 (la versión más nueva presente).**

- ***`archivos\_fuente/ipc\_futex\_v808.cpp.txt` viene con el bloque RAR corrupto/truncado ("Attempted to read more data than was available") — no lo pude recuperar. Si querés que lo audite, va a hacer falta que lo resubas.**

***No voy a validar el "Exit Code 0 (7/7 Tests Pass)" del tribunal previo como certificación de nada: los tests pasan porque prueban ausencia de crash, no las invariantes que estas funciones prometen (ortonormalidad de Stiefel, robustez Bizantina, disponibilidad del engine). Esa es la brecha que encontré en casi todos los puntos.**

### ***1) Condición de carrera real y no detectada: `pmtp\_banked\_slot\_acquire\_writer`**

*![]()**cpp**

```
***`int retries = 5000;`**

***`while (retries-- \> 0) \{`**

`    ***bool has\_active\_readers = false;`**

`    ***for (...) \{ if (state == PMTP\_LEASE\_ACTIVE) \{ has\_active\_readers = true; break; \} \}`**

`    ***if (!has\_active\_readers) break;`**

`    ***pmtp\_reap\_orphaned\_leases(header, target, 1000000, &reclaimed);`**

***`\}`**

***`header-\>owner\_pid = pid;   // \<- se ejecuta SIEMPRE, incluso si el while salió por agotar retries`**

***`\*write\_bank = target;`**

***`return POLYDIM\_STATUS\_OK; // \<- nunca reporta que quedaron lectores activos`**
```

***Impacto: si hay lectores legítimos (no huérfanos, PID vivo) que tardan más de 5000 iteraciones en soltar el slot, el bucle no distingue "lectores liberados" de "se acabaron los reintentos": en ambos casos cae al mismo código y el writer empieza a escribir sobre el banco que un lector sigue leyendo. Esto rompe la premisa entera del double-buffer RCU (zero-copy compartido entre agentes) — es exactamente el tipo de "condición de borde sin protección" del punto 1 de tus instrucciones, y no está listado en ninguna de las 4 auditorías previas (el `auditoria\_linea\_por\_linea.md` solo verifica el CAS del lado *reader*, nunca este camino del *writer*).**

***Fix: el `while` debe devolver `POLYDIM\_STATUS\_ERR\_WRITER\_BUSY` (o un código nuevo `ERR\_READER\_TIMEOUT`) si se agotan los retries con `has\_active\_readers == true`, y el caller debe reintentar con backoff en vez de recibir un falso `OK`.**

### ***2) TOCTOU de PID no cerrado, pese a tener el campo para cerrarlo**

***`pmtp\_is\_process\_alive` solo hace `kill(pid,0)`. El struct `PmtpReaderLease` ya guarda `process\_start\_time\_ns` (se setea en `pmtp\_banked\_slot\_acquire\_reader`), pero nunca se compara contra el start-time real del proceso vivo con ese PID. Si el proceso original murió y el SO reciclό el PID para otro proceso, `pmtp\_reap\_orphaned\_leases` lo va a considerar "vivo" indefinidamente → lease jamás reclamado → contribuye directamente al bug del punto 1 (el writer nunca ve `has\_active\_readers == false`).**

***Fix: en Linux, leer `/proc/\<pid\>/stat` (campo 22, starttime) y comparar contra `process\_start\_time\_ns`; si no coincide, el lease es huérfano aunque el PID "viva".**

### ***3) Mutación global no aislada: `omp\_set\_num\_threads` dentro de `polydim\_gram\_dsyrk`**

***Esta función se invoca desde `apply\_shifted\_cholqr2` y `retract\_cayley\_smw\_gram`, y pisa el ICV de threads de OpenMP del proceso sin guardar/restaurar el valor anterior. En una arquitectura pensada para múltiples agentes concurrentes compartiendo el mismo proceso (que es literalmente el pitch de POLYDIM), un agente que llama con `num\_threads=1` deja el runtime en ese estado para el próximo agente que asuma su propia config. Es un efecto colateral silencioso, no documentado en la firma de la función.**

***Fix: usar `\#pragma omp parallel num\_threads(threads)` acotado a la región, no `omp\_set\_num\_threads` global.**

### ***4) El "hot path" reinventa el Gram con átomos por escalar (no es bug de corrección, es un colapso de escala a D grande)**

***En `polydim\_stiefel\_optimize`, el cálculo de `XtG` NO reusa `polydim\_gram\_dsyrk` (que sí tiene reducción por hilo bien hecha): hace `\#pragma omp atomic` por cada elemento escalar dentro de un loop `D×K×K`. Con el objetivo declarado de D hasta 10,000,000, esto serializa el bus de coherencia de caché en cada iteración del solver. No es un data race — es la ausencia de protección contra el propio caso de borde que el proyecto dice resolver (alta dimensionalidad).**

### ***5) Tikhonov/CholQR: hay DOS implementaciones divergentes, y la que corre en producción es la más frágil**

- ***`stiefel\_math\_v808.cpp::stiefel\_cholqr` hace `eps = max(1e-12, mean\_diag\*1e-6)` — un piso absoluto+relativo razonable. Esta es la fórmula que `04\_REPORTE\_DE\_BRECHAS\_Y\_FIXES.md` marca como GAP-807-1 RESUELTO.**

- ***Pero `kernel\_cpp\_v808.cpp::apply\_shifted\_cholqr2` (la que de verdad usa `polydim\_stiefel\_optimize`) es distinta:**

*![]()**cpp**

```
***`double adaptive\_shift = (shift\_regularization \> 0.0) ? shift\_regularization \* mean\_diag : 1e-14 \* mean\_diag;`**

***`...`**

***`if (val \<= 1e-14) \{ val += adaptive\_shift; \}`**

***`if (val \<= 0.0) val = 1e-15;`**
```

***Si la columna de entrada es exactamente cero (`mean\_diag == 0`, matriz totalmente degenerada — justo el caso que pide auditar el punto 2), `adaptive\_shift = shift\_regularization \* 0 = 0` sin importar qué `shift\_regularization` haya puesto el usuario. El parámetro de regularización queda anulado exactamente en el caso que debía cubrir. No hay NaN (el piso `1e-15` evita eso), pero la regularización configurable es una ilusión en ese caso límite.**

- ***Además `1e-14` es un umbral absoluto comparado contra magnitudes arbitrarias del problema — si el usuario trabaja con vectores normalizados donde la diagonal típica es, digamos, `1e-3`, el umbral es irrelevante; si trabaja con datos sin normalizar donde la diagonal es `1e8`, el umbral dispara regularización espuria por ruido de redondeo normal.**

- ***`stiefel\_cholqr`, además, cuando detecta pivote degenerado, pone toda la columna de salida en cero (`output\[i\*num\_rows+r\] = 0.0f`) y la función es `void` — sin ningún status. Una columna cero no es un vector unitario: viola directamente la invariante de Stiefel (`||X^T X - I||\_F`) que el resto del sistema existe para vigilar, y lo hace sin ninguna forma de que el caller se entere.**

***Conclusión de este punto: GAP-807-1 está "resuelto" en un archivo que el pipeline activo no usa (y que además incluye un header `v805` inconsistente con su propio nombre de archivo `v808` — sospecho que es código huérfano). El archivo que sí corre en producción tiene el bug original sin resolver en el caso `mean\_diag == 0`.**

***Fix: unificar en una sola función de regularización (`eps = max(abs\_floor, mean\_diag \* rel\_factor)`, aplicada siempre a la diagonal antes de factorizar, no condicionalmente), usarla desde ambos módulos, y hacer que un pivote degenerado devuelva `POLYDIM\_STATUS\_ERR\_RANK\_DEFICIENT` (ya existe en el enum, no se usa nunca) en vez de emitir una columna cero silenciosa.**

### ***6) Filtro Fréchet-Betti: el "fix" de varianza cero (GAP-807-2) es evadible por el propio adversario que dice frenar**

*![]()**rust**

```
***`let step = 1.max(n / 100);`**

***`for i in (0..n).step\_by(step) \{`**

`    ***for j in (i + 1..n).step\_by(step) \{ ... \}`**

***`\}`**
```

***El chequeo de diversidad que decide si se activa el rechazo Bizantino solo muestrea ~100 índices en una grilla determinística (múltiplos de `step`), sea cual sea `n`. Un nodo adversario que conozca `n` (trivial, es un parámetro público de la llamada) puede colocarse en cualquier índice que no sea múltiplo de `step` y su outlier nunca entra en el cálculo de varianza. Si el resto del enjambre es homogéneo, `variance \< 1e-6` da verdadero igual, y entonces:**

*![]()**rust**

```
***`for k in 0..d \{ out\_vec\[k\] = candidates\[k\]; \} // candidate 0, NO un centroide`**

***`...`**

***`is\_consensus\_certified: true`**
```

***Esto no calcula ningún centroide (a pesar del comentario) — devuelve literalmente el candidato 0 tal cual, certificado, sin pasar por el grafo de umbral, la mediana de Fréchet ni Weiszfeld, que es justo la maquinaria anti-Bizantina que el archivo dice implementar en su propio doc-comment (punto 2 de tu directiva). Si el candidato 0 es el nodo adversario, el filtro certifica el ataque. `auditoria\_linea\_por\_linea.md` valida esto con "Similitud Coseno 1.00000" contra un caso sintético sin adversario — nunca se probó el caso que la directiva pide.**

***Fix: (a) la detección de varianza cero debe ser sobre una muestra aleatoria (con seed) o sobre el conjunto completo si `n` es manejable, nunca una grilla fija y predecible; (b) el retorno de "varianza cero" debe promediar realmente los candidatos (o, mejor, seguir corriendo el grafo de umbral/DSU igual — es barato si ya sabés que están todos cerca — para no saltarte el conteo real de `betti1` y `rejected\_outliers\_count`).**

### ***7) ABI C: no existe contrato canónico para el lado Rust, y los códigos de estado son incompatibles entre sí**

***`polydim\_solver\_abi\_v808.h` declara todas las funciones y structs de `kernel\_cpp\_v808.cpp`, con `static\_assert` de tamaños — buena práctica. Pero no declara ni una sola función/struct de `kernel\_rust\_v808.rs` (`polydim\_rust\_betti\_dual\_guard`, `polydim\_rust\_frechet\_betti\_filter`, `PolydimEdge`, `PolydimBettiResult`, `PolydimFrechetBettiResult`, `NativeStatus`). Cualquier consumidor C++/Python/Dart tiene que declarar esos prototipos a mano, sin que el compilador pueda detectar un desajuste de tipos o de layout — es exactamente lo que el punto 4 de tu directiva pide verificar, y falla.**

***Peor: los dos lados usan espacios de códigos de estado incompatibles con los mismos valores enteros:**

| Valor | **`PolydimStatusCode`** (C++) | **`NativeStatus`** (Rust) |
| :-: | :-: | :-: |
| **`0`** | OK | Ok |
| **`1`** | CONVERGED\_GRADIENT (éxito) | InvalidArgument (error) |
| **`2`** | CONVERGED\_STEP (éxito) | NullPointer (error) |

***Si algún orquestador (tenés `polydim\_ffi\_v806.dart` en el `.rar`, así que hay al menos un tercer consumidor) trata "1" como un código unificado `polydim\_status\_t`, un `1` que significa "convergió con éxito" en el kernel C++ significa "argumento inválido" en el kernel Rust. Esto no es teórico: es el tipo de bug que se descubre en producción cuando alguien loguea "status=1" y otro asume qué significa.**

***Fix: un único enum de status compartido (o al menos documentar explícitamente que son namespaces separados y forzar el prefijo en cada log/telemetría), y extender el header C con los prototipos y structs Rust.**

### ***8) `catch\_unwind`: no gotea memoria, pero sí "envenena" todo el proceso para todos los agentes**

*![]()**rust**

```
***`static INSTANCE\_STATE: AtomicU8 = AtomicU8::new(0);`**

***`...`**

***`if INSTANCE\_STATE.load(Ordering::SeqCst) == 2 \{ return NativeStatus::Panic; \}`**
```

***`INSTANCE\_STATE` es un global de proceso. `LAST\_ERROR\_CSTR` es `thread\_local!`. Combinación problemática en un diseño multi-agente:**

- ***Un panic en el hilo A escribe el mensaje en la TLS del hilo A y pone el flag global en 2.**

- ***Todos los demás hilos/agentes quedan bloqueados (reciben `Panic` sin siquiera intentar ejecutar) hasta que alguien llame `polydim\_reset\_engine\_state()` — un solo input malformado de un agente tira abajo la disponibilidad de todos los demás, aunque el panic no haya corrompido ningún estado compartido (las funciones auditadas solo mutan buffers locales y el buffer de salida del propio caller).**

- ***Si el hilo B llama a `polydim\_last\_error\_v1()` para ver qué pasó, lee su propia TLS (vacía), no el mensaje real del hilo A que causó el envenenamiento. Se entera de que "hubo un panic" sin poder saber cuál fue.**

***El comentario del archivo dice "cero fugas de memoria en pánicos" — eso es cierto (`catch\_unwind` + `drop` funcionan bien), pero memory-safety no es lo mismo que disponibilidad, y el diseño actual convierte cualquier panic aislado en una denegación de servicio para todo el enjambre.**

***Fix: el poison-latch debería ser por-handle/por-agente (pasar un `\*mut polydim\_engine\_t` real en vez de global), o al menos degradar de "hard poison" a "logueá y seguí" para funciones que demostrablemente no tocan estado compartido mutable.**


***¿Querés que siga con `crypto\_aead\_v808.cpp.txt` y `pruebas\_unitarias/test\_v808\_ipc\_suite.py` (el próximo en la cola), que te arme los parches concretos para los puntos 1, 5 y 6 (los de mayor severidad), o que vuelque esto en un `.md` con el mismo formato que tu `04\_REPORTE\_DE\_BRECHAS\_Y\_FIXES.md` para tu tracking?**

Esta es la 3er ronda del dia de hoy. realmente no entiendo, entre los archivos no llegan a 2000 lineas. como puede ser que no encuentres todos los errores en casi seis meses de 3 entregas diarias los 7 dias de la semana. Y tengamos en cuenta el que se apura en darme respuestas pobres y no profundas sos vos. Parece que estas apurado y me das para solucionarlo 10 items. Yo voy rehago el codigo, lo pruebo y vuelvo. Luego encuentras que aun hay cosas mal que no te habias dado cuenta antes, voy hago mi parte y asi de lunes a domingo en  2 y 3 veces a veces 4. quien hace un trabajo por la mitad? como puede ser mas de 600 interacciones no tengamos terminado algo de ~1000 a 2000 lineas solo. poco en rust, muy poco en python y poco en cpp . ho es un sistemas de 50 000

***SoS BULDOG muerde hasta el hueso. no quiero volver 600 veces mas. quiero que termines de darme 2000 lineas. solo menos de 2000 perfectas**

*![]()**Ahora también necesito arreglar los `alignas(128)` de los campos individuales en `PolydimSpscRing`, que en C11 son legales solo si el compilador los trata igual — vamos a confirmar compilando de nuevo en C y C++.**


bash

***`cd /home/claude/audit/fixed && echo "=== C11 ===" && gcc -std=c11 -Wall -Wextra -o check\_abi\_c check\_abi\_c.c && ./check\_abi\_c && echo "=== C++17 ===" && g++ -std=c++17 -Wall -Wextra -o check\_abi check\_abi.cpp && ./check\_abi`**

***Salida**

***`=== C11 === C: sizeof(PolydimBettiResult)=128 sizeof(PolydimFrechetBettiResult)=128 === C++17 === sizeof(PolydimBettiResult) = 128 sizeof(PolydimFrechetBettiResult) = 128 sizeof(PmtpBankedSlotHeader) = 1152 translate(InvalidArgument=1) = -2 (expect POLYDIM\_STATUS\_ERR\_INVALID\_DIM=-2) `**

***bash**

***`which clang clang++ 2\>&1 cd /home/claude/audit/fixed && gcc -std=c11 -pedantic -Wall -Wextra -Werror -o check\_abi\_c2 check\_abi\_c.c 2\>&1 && ./check\_abi\_c2 && echo OK\_PEDANTIC\_C g++ -std=c++17 -pedantic -Wall -Wextra -Werror -o check\_abi2 check\_abi.cpp 2\>&1 && ./check\_abi2 && echo OK\_PEDANTIC\_CPP`**

***Salida**

***`C: sizeof(PolydimBettiResult)=128 sizeof(PolydimFrechetBettiResult)=128 OK\_PEDANTIC\_C sizeof(PolydimBettiResult) = 128 sizeof(PolydimFrechetBettiResult) = 128 sizeof(PmtpBankedSlotHeader) = 1152 translate(InvalidArgument=1) = -2 (expect POLYDIM\_STATUS\_ERR\_INVALID\_DIM=-2) OK\_PEDANTIC\_CPP `**

***Verifying header code across compilers before addressing kernel implementation.**

***Redesigning the regularization so it never becomes a no-op.**

***Weighing whether to flag rank deficiency without breaking existing behavior.**

***Ensuring the diagonal floor applies unconditionally to prevent silent failure.**

***bash**

***`cd /home/claude/audit/auditoria\_externa && sed -n '300,400p' pruebas\_unitarias/test\_v808\_ipc\_suite.py`**

***Salida**

***`K\_ref = X.T @ X diff\_det = np.linalg.norm(K\_det - K\_ref, ord='fro') diff\_thr = np.linalg.norm(K\_thr - K\_ref, ord='fro') diff\_cross = np.linalg.norm(K\_det - K\_thr, ord='fro') print(f"✓ D=\{D\}, K=\{K\}") print(f"✓ Tiempo TwoSum Determinista: \{t\_det\*1000:.2f\} ms (Error Frobenius vs NumPy: \{diff\_det:.2e\})") print(f"✓ Tiempo SIMD Throughput: \{t\_thr\*1000:.2f\} ms (Error Frobenius vs NumPy: \{diff\_thr:.2e\})") print(f"✓ Discrepancia entre modos: \{diff\_cross:.2e\}") assert diff\_det \< 1e-12 assert diff\_thr \< 1e-12 print("\[TEST 1 PASS\] Gramiana DSYRK Dual validada con éxito.") \# ========================================================================= \# TEST 2: Solver Stiefel Monolítico con Shifted CholQR y NT Streaming \# ========================================================================= def test\_stiefel\_shifted\_cholqr\_and\_nt\_stream(): print("\\n--- \[TEST 2\] Stiefel Solver con Shifted CholQR y Non-Temporal Streaming ---") D, K = 12000, 32 rng = np.random.RandomState(99) \# 1. Probar Non-Temporal Streaming Copy src\_data = rng.randn(D \* K).astype(np.float64) dst\_data = np.zeros(D \* K, dtype=np.float64) t0 = time.perf\_counter() st\_nt = cpp\_lib.polydim\_stream\_copy\_nt( dst\_data.ctypes.data\_as(ctypes.POINTER(ctypes.c\_double)), src\_data.ctypes.data\_as(ctypes.POINTER(ctypes.c\_double)), D \* K ) t\_nt = time.perf\_counter() - t0 assert st\_nt == 0 diff\_nt = np.linalg.norm(dst\_data - src\_data) assert diff\_nt == 0.0, f"Fallo en NT copy diff=\{diff\_nt\}" print(f"✓ NT Streaming Store (\{D\*K\*8 / 1024 / 1024:.2f\} MB): \{t\_nt\*1000:.3f\} ms (Exactitud de bit garantizada)") \# 2. Solver Stiefel con Shifted CholQR X\_init = np.linalg.qr(rng.randn(D, K))\[0\].astype(np.float64) X = np.ascontiguousarray(X\_init.copy(), dtype=np.float64) Target = np.ascontiguousarray(X\_init + 0.02 \* rng.randn(D, K), dtype=np.float64) opts = PolydimSolverOptions() opts.max\_iterations = 20 opts.gradient\_tolerance = 1e-6 opts.step\_tolerance = 1e-8 opts.objective\_tolerance = 1e-8 opts.ortho\_tolerance = 1e-5 opts.retraction\_type = 3 \# POLYDIM\_RETRACTION\_SHIFTED\_CHOLQR opts.sampling\_period = 5 opts.num\_threads = 4 opts.learning\_rate = 1e-3 opts.shift\_regularization = 1e-12 result = PolydimSolverResult() capacity = 50 points\_array = (PolydimTelemetryPoint \* capacity)() telemetry = PolydimTelemetryBuffer() telemetry.points = points\_array telemetry.capacity = capacity telemetry.recorded\_count = 0 cpp\_lib.polydim\_set\_fp\_mode(1) t0 = time.perf\_counter() status = cpp\_lib.polydim\_stiefel\_optimize( Target.ctypes.data\_as(ctypes.POINTER(ctypes.c\_double)), D \* K, X.ctypes.data\_as(ctypes.POINTER(ctypes.c\_double)), D, K, ctypes.byref(opts), ctypes.byref(result), ctypes.byref(telemetry) ) t\_opt = time.perf\_counter() - t0 print(f"✓ Tiempo Stiefel Shifted CholQR (\{D\}x\{K\}): \{t\_opt\*1000:.2f\} ms") print(f"✓ Iteraciones: \{result.iterations\_executed\} | Estado: \{result.status\}") print(f"✓ Error de ortogonalidad final: \{result.final\_ortho\_error:.2e\}") assert status in (0, 1, 2, 3) assert result.final\_ortho\_error \<= 1e-5 print("\[TEST 2 PASS\] Shifted CholQR y Non-Temporal Stores validados.") \# ========================================================================= \# TEST 3: SPSC Telemetry Ring Buffer (Wait-Free, Zero-Drop) \# ========================================================================= def test\_spsc\_ring\_buffer(): print("\\n--- \[TEST 3\] Anillo SPSC Wait-Free de Telemetría (128B Cache-Line Isolated) ---") ring = PolydimSpscRing() capacity = 1024 \# Potencia de 2 st\_init = cpp\_lib.polydim\_spsc\_init(ctypes.byref(ring), capacity) assert st\_init == 0, f"Fallo al inicializar SPSC: \{st\_init\}" events\_to\_send = 50000 received\_events = \[\] consumer\_done = threading.Event() def producer(): for i in range(events\_to\_send): `**

***Tracing the test suite's use of a Cholesky-based optimization routine.**

***Confirming dead code and planning a status-code compatibility safeguard.**

***bash**

***`cp /home/claude/audit/auditoria\_externa/archivos\_fuente/kernel\_cpp\_v808.cpp.txt /home/claude/audit/fixed/kernel\_cpp\_v809.cpp sed -i "s/kernel\_cpp\_v808.cpp/kernel\_cpp\_v809.cpp/; s/\#include \\"polydim\_solver\_abi.h\\"/\#include \\"polydim\_solver\_abi\_v809.h\\"/" /home/claude/audit/fixed/kernel\_cpp\_v809.cpp head -12 /home/claude/audit/fixed/kernel\_cpp\_v809.cpp`**

***Salida**

***`/\*\* \* @file kernel\_cpp\_v809.cpp \* @brief Kernel Monolítico C++ POLYDIM V808 Definitiva: \* - Stiefel Solver con Shifted CholQR y Retracción Cayley-SMW \* - Non-Temporal Streaming Stores (AVX2 / SSE2) con Fencing por Hilo \* - Wait-Free SPSC Telemetry Ring Buffer (128B Cache-Line Isolated) \* - Strict Allocator Pairing & Protected PolydimHandle \* - Banked Slot Lease RCU con Reclamación Atómica CAS & Gram DSYRK FP Dual Mode \* @copyright POLYDIM Architecture - 2026 \*/ \#include \<cmath\> `**

*![]()**Se ha quedado sin [mensajes](https://support.claude.com/en/articles/11647753-understanding-usage-and-length-limits) gratuitos hasta las 1:50**


~~***[Claude es una IA y puede cometer errores. Comprueba siempre sus respuestas.**](https://support.anthropic.com/en/articles/8525154-claude-is-providing-incorrect-or-misleading-responses-what-s-going-on)


## ***Kernel cpp v809 · CPP**

**`/\*\*`**

***`\* @file kernel\_cpp\_v809.cpp`**

***`\* @brief Kernel Monolítico C++ POLYDIM V808 Definitiva:`**

***`\* - Stiefel Solver con Shifted CholQR y Retracción Cayley-SMW`**

***`\* - Non-Temporal Streaming Stores (AVX2 / SSE2) con Fencing por Hilo`**

***`\* - Wait-Free SPSC Telemetry Ring Buffer (128B Cache-Line Isolated)`**

***`\* - Strict Allocator Pairing & Protected PolydimHandle`**

***`\* - Banked Slot Lease RCU con Reclamación Atómica CAS & Gram DSYRK FP Dual Mode`**

***`\* @copyright POLYDIM Architecture - 2026`**

***`\*/`**

` `

***`\#include \<cmath\>`**

***`\#include \<cstdio\>`**

***`\#include \<cstdlib\>`**

***`\#include \<cstring\>`**

***`\#include \<chrono\>`**

***`\#include \<atomic\>`**

***`\#include \<algorithm\>`**

***`\#include \<vector\>`**

***`\#include \<immintrin.h\>`**

` `

***`\#if defined(\_OPENMP)`**

***`\#include \<omp.h\>`**

***`\#endif`**

` `

***`\#if defined(\_WIN32)`**

***`\#include \<windows.h\>`**

***`\#else`**

***`\#include \<signal.h\>`**

***`\#include \<sys/types.h\>`**

***`\#include \<errno.h\>`**

***`\#endif`**

` `

***`\#include "polydim\_solver\_abi\_v809.h"`**

***`\#include "polydim\_blas\_loader.h"`**

` `

***`\#define POLYDIM\_ALIGN 128`**

***`\#define TILE\_D 32`**

***`\#define TILE\_K 32`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 1. MODO FLOTANTE DUAL IEEE-754: DETERMINISTIC (TwoSum) vs THROUGHPUT \*/`**

***`/\* ========================================================================= \*/`**

` `

***`typedef enum \{`**

***`POLYDIM\_FP\_DETERMINISTIC = 0,`**

***`POLYDIM\_FP\_THROUGHPUT = 1`**

***`\} PolydimFpMode;`**

` `

***`static std::atomic\<int32\_t\> g\_fp\_mode\{POLYDIM\_FP\_THROUGHPUT\};`**

` `

***`extern "C" void polydim\_set\_fp\_mode(int32\_t mode) \{`**

***`g\_fp\_mode.store(mode, std::memory\_order\_relaxed);`**

***`\}`**

` `

***`extern "C" int32\_t polydim\_get\_fp\_mode() \{`**

***`return g\_fp\_mode.load(std::memory\_order\_relaxed);`**

***`\}`**

` `

***`/\* Algoritmo TwoSum de Knuth (Exact Roundoff Addition) \*/`**

***`static inline void knuth\_two\_sum(double a, double b, double\* s, double\* t) \{`**

***`double sum = a + b;`**

***`double b\_virtual = sum - a;`**

***`double a\_virtual = sum - b\_virtual;`**

***`double b\_roundoff = b - b\_virtual;`**

***`double a\_roundoff = a - a\_virtual;`**

***`\*s = sum;`**

***`\*t = a\_roundoff + b\_roundoff;`**

***`\}`**

` `

***`/\* Reducción determinista por árbol binario de potencias de 2 \*/`**

***`static double twosum\_tree\_reduce(const double\* data, size\_t N) \{`**

***`if (N == 0) return 0.0;`**

***`if (N == 1) return data\[0\];`**

` `

***`std::vector\<double\> current(data, data + N);`**

***`std::vector\<double\> errors;`**

***`errors.reserve(N);`**

` `

***`while (current.size() \> 1) \{`**

***`size\_t n\_pairs = current.size() / 2;`**

***`std::vector\<double\> next\_level;`**

***`next\_level.reserve(n\_pairs + (current.size() % 2));`**

` `

***`for (size\_t i = 0; i \< n\_pairs; ++i) \{`**

***`double s, t;`**

***`knuth\_two\_sum(current\[2 \* i\], current\[2 \* i + 1\], &s, &t);`**

***`next\_level.push\_back(s);`**

***`if (std::abs(t) \> 0.0) \{`**

***`errors.push\_back(t);`**

***`\}`**

***`\}`**

***`if (current.size() % 2 != 0) \{`**

***`next\_level.push\_back(current.back());`**

***`\}`**

***`current = std::move(next\_level);`**

***`\}`**

` `

***`double total\_sum = current\[0\];`**

***`for (double err : errors) \{`**

***`double s, t;`**

***`knuth\_two\_sum(total\_sum, err, &s, &t);`**

***`total\_sum = s + t;`**

***`\}`**

***`return total\_sum;`**

***`\}`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 2. NON-TEMPORAL STREAMING STORES (AVX2 / SSE2) CON FENCING POR HILO \*/`**

***`/\* ========================================================================= \*/`**

` `

***`extern "C" int32\_t polydim\_stream\_copy\_nt(double\* dest, const double\* src, size\_t count) \{`**

***`if (!dest || !src) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

***`if (count == 0) return POLYDIM\_STATUS\_OK;`**

` `

***`size\_t i = 0;`**

***`uintptr\_t dest\_addr = reinterpret\_cast\<uintptr\_t\>(dest);`**

***`if ((dest\_addr % 16 == 0) && count \>= 2) \{`**

***`size\_t sse\_blocks = count / 2;`**

***`\#pragma omp parallel`**

***`\{`**

***`\#pragma omp for schedule(static)`**

***`for (size\_t b = 0; b \< sse\_blocks; ++b) \{`**

***`size\_t idx = b \* 2;`**

***`\_\_m128d data = \_mm\_loadu\_pd(&src\[idx\]);`**

***`\_mm\_stream\_pd(&dest\[idx\], data);`**

***`\}`**

***`\_mm\_sfence(); // Fencing individual por cada hilo de ejecución`**

***`\}`**

***`i = sse\_blocks \* 2;`**

***`\_mm\_sfence();`**

***`\}`**

` `

***`for (; i \< count; ++i) \{`**

***`dest\[i\] = src\[i\];`**

***`\}`**

` `

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 3. STRICT ALLOCATOR PAIRING & PROTECTED POLYDIM\_HANDLE \*/`**

***`/\* ========================================================================= \*/`**

` `

***`static std::atomic\<uint64\_t\> g\_allocation\_seq\{1\};`**

` `

***`extern "C" void\* polydim\_alloc\_aligned(size\_t bytes, size\_t alignment) \{`**

***`size\_t align = (alignment \> 0) ? alignment : 64;`**

***`if ((align & (align - 1)) != 0) align = 64;`**

` `

***`\#if defined(\_MSC\_VER) || defined(\_\_MINGW32\_\_) || defined(\_\_MINGW64\_\_)`**

***`return \_aligned\_malloc(bytes, align);`**

***`\#else`**

***`void\* ptr = nullptr;`**

***`if (posix\_memalign(&ptr, align, bytes) != 0) return nullptr;`**

***`return ptr;`**

***`\#endif`**

***`\}`**

` `

***`extern "C" void polydim\_free\_aligned(void\* ptr) \{`**

***`if (!ptr) return;`**

***`\#if defined(\_MSC\_VER) || defined(\_\_MINGW32\_\_) || defined(\_\_MINGW64\_\_)`**

***`\_aligned\_free(ptr);`**

***`\#else`**

***`free(ptr);`**

***`\#endif`**

***`\}`**

` `

***`extern "C" PolydimHandle\* polydim\_handle\_create(size\_t bytes, size\_t alignment) \{`**

***`void\* data = polydim\_alloc\_aligned(bytes, alignment);`**

***`if (!data) return nullptr;`**

` `

***`PolydimHandle\* handle = static\_cast\<PolydimHandle\*\>(std::malloc(sizeof(PolydimHandle)));`**

***`if (!handle) \{`**

***`polydim\_free\_aligned(data);`**

***`return nullptr;`**

***`\}`**

` `

***`handle-\>data = data;`**

***`handle-\>bytes = bytes;`**

***`reinterpret\_cast\<std::atomic\<int32\_t\>\*\>(&handle-\>refcount)-\>store(1, std::memory\_order\_release);`**

***`handle-\>flags = 0;`**

***`handle-\>allocation\_id = g\_allocation\_seq.fetch\_add(1, std::memory\_order\_relaxed);`**

***`return handle;`**

***`\}`**

` `

***`extern "C" void polydim\_handle\_retain(PolydimHandle\* handle) \{`**

***`if (!handle) return;`**

***`std::atomic\<int32\_t\>\* ref = reinterpret\_cast\<std::atomic\<int32\_t\>\*\>(&handle-\>refcount);`**

***`ref-\>fetch\_add(1, std::memory\_order\_relaxed);`**

***`\}`**

` `

***`extern "C" void polydim\_handle\_release(PolydimHandle\* handle) \{`**

***`if (!handle) return;`**

***`std::atomic\<int32\_t\>\* ref = reinterpret\_cast\<std::atomic\<int32\_t\>\*\>(&handle-\>refcount);`**

***`if (ref-\>fetch\_sub(1, std::memory\_order\_acq\_rel) == 1) \{`**

***`if (handle-\>data) \{`**

***`polydim\_free\_aligned(handle-\>data);`**

***`handle-\>data = nullptr;`**

***`\}`**

***`std::free(handle);`**

***`\}`**

***`\}`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 4. WAIT-FREE SPSC TELEMETRY RING BUFFER (128B ISOLATED CACHE-LINES) \*/`**

***`/\* ========================================================================= \*/`**

` `

***`extern "C" int32\_t polydim\_spsc\_init(PolydimSpscRing\* ring, size\_t capacity) \{`**

***`if (!ring) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

***`if (capacity \< 2 || (capacity & (capacity - 1)) != 0) \{`**

***`return POLYDIM\_STATUS\_ERR\_INVALID\_DIM;`**

***`\}`**

` `

***`size\_t total\_bytes = capacity \* sizeof(PolydimTelemetryEvent);`**

***`PolydimTelemetryEvent\* buffer = static\_cast\<PolydimTelemetryEvent\*\>(polydim\_alloc\_aligned(total\_bytes, 128));`**

***`if (!buffer) return POLYDIM\_STATUS\_ERR\_ALLOC;`**

` `

***`std::memset(buffer, 0, total\_bytes);`**

` `

***`reinterpret\_cast\<std::atomic\<uint64\_t\>\*\>(&ring-\>write\_index)-\>store(0, std::memory\_order\_relaxed);`**

***`reinterpret\_cast\<std::atomic\<uint64\_t\>\*\>(&ring-\>read\_index)-\>store(0, std::memory\_order\_relaxed);`**

***`ring-\>capacity = capacity;`**

***`ring-\>capacity\_mask = capacity - 1;`**

***`ring-\>ring\_buffer = buffer;`**

` `

***`std::atomic\_thread\_fence(std::memory\_order\_seq\_cst);`**

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`extern "C" int32\_t polydim\_spsc\_push(PolydimSpscRing\* ring, const PolydimTelemetryEvent\* event) \{`**

***`if (!ring || !event || !ring-\>ring\_buffer) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

` `

***`std::atomic\<uint64\_t\>\* w\_atomic = reinterpret\_cast\<std::atomic\<uint64\_t\>\*\>(&ring-\>write\_index);`**

***`std::atomic\<uint64\_t\>\* r\_atomic = reinterpret\_cast\<std::atomic\<uint64\_t\>\*\>(&ring-\>read\_index);`**

` `

***`uint64\_t w = w\_atomic-\>load(std::memory\_order\_relaxed);`**

***`uint64\_t r = r\_atomic-\>load(std::memory\_order\_acquire);`**

` `

***`if (w - r \>= ring-\>capacity) \{`**

***`return POLYDIM\_STATUS\_ERR\_RING\_FULL;`**

***`\}`**

` `

***`ring-\>ring\_buffer\[w & ring-\>capacity\_mask\] = \*event;`**

***`std::atomic\_thread\_fence(std::memory\_order\_release);`**

***`w\_atomic-\>store(w + 1, std::memory\_order\_release);`**

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`extern "C" int32\_t polydim\_spsc\_pop(PolydimSpscRing\* ring, PolydimTelemetryEvent\* event) \{`**

***`if (!ring || !event || !ring-\>ring\_buffer) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

` `

***`std::atomic\<uint64\_t\>\* w\_atomic = reinterpret\_cast\<std::atomic\<uint64\_t\>\*\>(&ring-\>write\_index);`**

***`std::atomic\<uint64\_t\>\* r\_atomic = reinterpret\_cast\<std::atomic\<uint64\_t\>\*\>(&ring-\>read\_index);`**

` `

***`uint64\_t r = r\_atomic-\>load(std::memory\_order\_relaxed);`**

***`uint64\_t w = w\_atomic-\>load(std::memory\_order\_acquire);`**

` `

***`if (r == w) \{`**

***`return POLYDIM\_STATUS\_ERR\_RING\_EMPTY;`**

***`\}`**

` `

***`\*event = ring-\>ring\_buffer\[r & ring-\>capacity\_mask\];`**

***`r\_atomic-\>store(r + 1, std::memory\_order\_release);`**

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`extern "C" void polydim\_spsc\_destroy(PolydimSpscRing\* ring) \{`**

***`if (!ring) return;`**

***`if (ring-\>ring\_buffer) \{`**

***`polydim\_free\_aligned(ring-\>ring\_buffer);`**

***`ring-\>ring\_buffer = nullptr;`**

***`\}`**

***`ring-\>capacity = 0;`**

***`ring-\>capacity\_mask = 0;`**

***`\}`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 5. GRAMIANA SIMÉTRICA: X^T \* X (DSYRK / L1-L2 TILED PACKING) \*/`**

***`/\* ========================================================================= \*/`**

` `

***`int32\_t polydim\_gram\_dsyrk(`**

***`const double\* X,`**

***`size\_t D,`**

***`size\_t K,`**

***`double\* K\_out,`**

***`uint32\_t num\_threads`**

***`) \{`**

***`if (!X || !K\_out) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

***`if (D == 0 || K == 0) return POLYDIM\_STATUS\_ERR\_INVALID\_DIM;`**

` `

***`int threads = (num\_threads \> 0) ? (int)num\_threads : 1;`**

***`\#if defined(\_OPENMP)`**

***`if (threads \> 1) \{`**

***`omp\_set\_num\_threads(threads);`**

***`\}`**

***`\#endif`**

` `

***`std::memset(K\_out, 0, K \* K \* sizeof(double));`**

***`int fp\_mode = g\_fp\_mode.load(std::memory\_order\_relaxed);`**

` `

***`if (fp\_mode == POLYDIM\_FP\_DETERMINISTIC) \{`**

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`for (size\_t j = i; j \< K; ++j) \{`**

***`std::vector\<double\> products(D);`**

***`for (size\_t d = 0; d \< D; ++d) \{`**

***`products\[d\] = X\[d \* K + i\] \* X\[d \* K + j\];`**

***`\}`**

***`double val = twosum\_tree\_reduce(products.data(), D);`**

***`K\_out\[i \* K + j\] = val;`**

***`K\_out\[j \* K + i\] = val;`**

***`\}`**

***`\}`**

***`\} else \{`**

***`BlasLoader::instance().compute\_dsyrk(`**

***`CblasRowMajor, CblasUpper, CblasTrans,`**

***`K, D,`**

***`1.0, X, K,`**

***`0.0, K\_out, K,`**

***`num\_threads`**

***`);`**

` `

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`for (size\_t j = 0; j \< i; ++j) \{`**

***`K\_out\[i \* K + j\] = K\_out\[j \* K + i\];`**

***`\}`**

***`\}`**

***`\}`**

` `

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`extern "C" const char\* polydim\_get\_blas\_backend\_name() \{`**

***`return BlasLoader::instance().backend\_name();`**

***`\}`**

` `

***`extern "C" void polydim\_set\_blas\_num\_threads(int32\_t num\_threads) \{`**

***`typedef void (\*openblas\_set\_threads\_fn)(int);`**

***`HMODULE mod = BlasLoader::instance().is\_blas\_loaded() ? GetModuleHandleA("libopenblas.dll") : nullptr;`**

***`if (mod) \{`**

***`auto fn = (openblas\_set\_threads\_fn)GetProcAddress(mod, "openblas\_set\_num\_threads");`**

***`if (fn) fn(num\_threads);`**

***`\}`**

***`\}`**

` `

***`extern "C" void polydim\_set\_omp\_num\_threads(int32\_t num\_threads) \{`**

***`\#if defined(\_OPENMP)`**

***`if (num\_threads \> 0) \{`**

***`omp\_set\_num\_threads(num\_threads);`**

***`\}`**

***`\#endif`**

***`\}`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 6. OPERACIONES MATRICIALES KxK CONFINADAS A L1 \*/`**

***`/\* ========================================================================= \*/`**

` `

***`static void matmul\_kxk(const double\* A, const double\* B, double\* C, size\_t K) \{`**

***`std::memset(C, 0, K \* K \* sizeof(double));`**

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`for (size\_t k = 0; k \< K; ++k) \{`**

***`double a\_ik = A\[i \* K + k\];`**

***`\#pragma omp simd`**

***`for (size\_t j = 0; j \< K; ++j) \{`**

***`C\[i \* K + j\] += a\_ik \* B\[k \* K + j\];`**

***`\}`**

***`\}`**

***`\}`**

***`\}`**

` `

***`static double matrix\_frobenius\_norm\_diff(const double\* A, const double\* B, size\_t size) \{`**

***`double sum = 0.0;`**

***`\#pragma omp simd reduction(+:sum)`**

***`for (size\_t i = 0; i \< size; ++i) \{`**

***`double diff = A\[i\] - B\[i\];`**

***`sum += diff \* diff;`**

***`\}`**

***`return std::sqrt(sum);`**

***`\}`**

` `

***`static bool solve\_linear\_system\_kxk(double\* A, double\* B, size\_t K, size\_t NRHS) \{`**

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`size\_t pivot = i;`**

***`double max\_val = std::abs(A\[i \* K + i\]);`**

***`for (size\_t r = i + 1; r \< K; ++r) \{`**

***`double val = std::abs(A\[r \* K + i\]);`**

***`if (val \> max\_val) \{`**

***`max\_val = val;`**

***`pivot = r;`**

***`\}`**

***`\}`**

***`if (max\_val \< 1e-15) return false;`**

` `

***`if (pivot != i) \{`**

***`for (size\_t c = 0; c \< K; ++c) std::swap(A\[i \* K + c\], A\[pivot \* K + c\]);`**

***`for (size\_t c = 0; c \< NRHS; ++c) std::swap(B\[i \* NRHS + c\], B\[pivot \* NRHS + c\]);`**

***`\}`**

` `

***`double diag = A\[i \* K + i\];`**

***`for (size\_t c = i; c \< K; ++c) A\[i \* K + c\] /= diag;`**

***`for (size\_t c = 0; c \< NRHS; ++c) B\[i \* NRHS + c\] /= diag;`**

` `

***`for (size\_t r = 0; r \< K; ++r) \{`**

***`if (r != i) \{`**

***`double factor = A\[r \* K + i\];`**

***`for (size\_t c = i; c \< K; ++c) A\[r \* K + c\] -= factor \* A\[i \* K + c\];`**

***`for (size\_t c = 0; c \< NRHS; ++c) B\[r \* NRHS + c\] -= factor \* B\[i \* NRHS + c\];`**

***`\}`**

***`\}`**

***`\}`**

***`return true;`**

***`\}`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 7. RETRACCIÓN SHIFTED CHOLQR2 & CAYLEY-SMW \*/`**

***`/\* ========================================================================= \*/`**

` `

***`static int32\_t apply\_shifted\_cholqr2(`**

***`double\* X,`**

***`size\_t D,`**

***`size\_t K,`**

***`double shift\_regularization,`**

***`uint32\_t num\_threads`**

***`) \{`**

***`std::vector\<double\> Gram(K \* K, 0.0);`**

***`polydim\_gram\_dsyrk(X, D, K, Gram.data(), num\_threads);`**

` `

***`double trace\_gram = 0.0;`**

***`for (size\_t i = 0; i \< K; ++i) trace\_gram += Gram\[i \* K + i\];`**

***`double mean\_diag = trace\_gram / static\_cast\<double\>(K);`**

` `

***`/\* \[MATH-1\] FIX V809: el V808 original hacía`**

***`\* adaptive\_shift = shift\_regularization \* mean\_diag`**

***`\* y solo la sumaba SI val\<=1e-14. Si la entrada es una matriz totalmente`**

***`\* degenerada (p.ej. una columna entera en cero), mean\_diag == 0, y`**

***`\* entonces adaptive\_shift = shift\_regularization \* 0 = 0 SIN IMPORTAR`**

***`\* qué shift\_regularization haya pedido el caller: la regularización de`**

***`\* Tikhonov quedaba anulada exactamente en el caso que debía cubrir.`**

***`\* Además el piso "1e-14" era un umbral absoluto comparado contra`**

***`\* magnitudes arbitrarias del problema.`**

***`\*`**

***`\* Fix: un eps con piso absoluto Y relativo, sumado SIEMPRE a la diagonal`**

***`\* antes de factorizar (no condicional), igual que ya se hacía bien en`**

***`\* stiefel\_math\_v808.cpp::stiefel\_cholqr -- generalizado aquí a doble`**

***`\* precisión y al layout D x K real que usa este solver. \*/`**

***`const double PD\_ABS\_FLOOR = 1e-12;`**

***`double rel\_factor = (shift\_regularization \> 0.0) ? shift\_regularization : 1e-6;`**

***`double eps = std::max(PD\_ABS\_FLOOR, mean\_diag \* rel\_factor);`**

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`Gram\[i \* K + i\] += eps;`**

***`\}`**

***`double pivot\_tol\_sq = eps \* eps \* 1e-6; /\* piso de seguridad tras redondeo, ya no debería activarse casi nunca \*/`**

` `

***`int32\_t rank\_deficient\_pivots = 0;`**

***`std::vector\<double\> L(K \* K, 0.0);`**

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`for (size\_t j = 0; j \<= i; ++j) \{`**

***`double sum = 0.0;`**

***`for (size\_t k = 0; k \< j; ++k) \{`**

***`sum += L\[i \* K + k\] \* L\[j \* K + k\];`**

***`\}`**

***`if (i == j) \{`**

***`double val = Gram\[i \* K + i\] - sum;`**

***`if (val \< pivot\_tol\_sq) \{`**

***`val = pivot\_tol\_sq;`**

***`++rank\_deficient\_pivots;`**

***`\}`**

***`L\[i \* K + j\] = std::sqrt(val);`**

***`\} else \{`**

***`if (L\[j \* K + j\] \<= 0.0) \{`**

***`L\[i \* K + j\] = 0.0; /\* columna j ya marcada degenerada: no propagar 0/0 \*/`**

***`\} else \{`**

***`L\[i \* K + j\] = (Gram\[i \* K + j\] - sum) / L\[j \* K + j\];`**

***`\}`**

***`\}`**

***`\}`**

***`\}`**

` `

***`std::vector\<double\> Linv(K \* K, 0.0);`**

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`Linv\[i \* K + i\] = 1.0 / L\[i \* K + i\];`**

***`for (size\_t j = 0; j \< i; ++j) \{`**

***`double sum = 0.0;`**

***`for (size\_t k = j; k \< i; ++k) \{`**

***`sum += L\[i \* K + k\] \* Linv\[k \* K + j\];`**

***`\}`**

***`Linv\[i \* K + j\] = -sum / L\[i \* K + i\];`**

***`\}`**

***`\}`**

` `

***`\#pragma omp parallel for schedule(static)`**

***`for (size\_t d = 0; d \< D; ++d) \{`**

***`std::vector\<double\> row\_temp(K, 0.0);`**

***`for (size\_t k = 0; k \< K; ++k) \{`**

***`double acc = 0.0;`**

***`for (size\_t j = 0; j \< K; ++j) \{`**

***`acc += X\[d \* K + j\] \* Linv\[k \* K + j\];`**

***`\}`**

***`row\_temp\[k\] = acc;`**

***`\}`**

***`for (size\_t k = 0; k \< K; ++k) \{`**

***`X\[d \* K + k\] = row\_temp\[k\];`**

***`\}`**

***`\}`**

` `

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`static int32\_t retract\_cayley\_smw\_gram(`**

***`double\* X,`**

***`const double\* G,`**

***`size\_t D,`**

***`size\_t K,`**

***`double tau,`**

***`double shift\_regularization,`**

***`uint32\_t num\_threads`**

***`) \{`**

***`std::vector\<double\> XtX(K \* K, 0.0);`**

***`std::vector\<double\> XtG(K \* K, 0.0);`**

***`std::vector\<double\> GtG(K \* K, 0.0);`**

` `

***`polydim\_gram\_dsyrk(X, D, K, XtX.data(), num\_threads);`**

` `

***`\#pragma omp parallel for schedule(static) collapse(2)`**

***`for (size\_t i0 = 0; i0 \< K; i0 += TILE\_K) \{`**

***`for (size\_t j0 = 0; j0 \< K; j0 += TILE\_K) \{`**

***`size\_t i\_max = std::min(i0 + TILE\_K, K);`**

***`size\_t j\_max = std::min(j0 + TILE\_K, K);`**

` `

***`for (size\_t d0 = 0; d0 \< D; d0 += TILE\_D) \{`**

***`size\_t d\_max = std::min(d0 + TILE\_D, D);`**

***`for (size\_t i = i0; i \< i\_max; ++i) \{`**

***`for (size\_t j = j0; j \< j\_max; ++j) \{`**

***`double acc\_xg = 0.0;`**

***`double acc\_gg = 0.0;`**

***`\#pragma omp simd reduction(+:acc\_xg, acc\_gg)`**

***`for (size\_t d = d0; d \< d\_max; ++d) \{`**

***`acc\_xg += X\[d \* K + i\] \* G\[d \* K + j\];`**

***`if (j \>= i) acc\_gg += G\[d \* K + i\] \* G\[d \* K + j\];`**

***`\}`**

***`\#pragma omp atomic`**

***`XtG\[i \* K + j\] += acc\_xg;`**

***`if (j \>= i) \{`**

***`\#pragma omp atomic`**

***`GtG\[i \* K + j\] += acc\_gg;`**

***`\}`**

***`\}`**

***`\}`**

***`\}`**

***`\}`**

***`\}`**

` `

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`for (size\_t j = 0; j \< i; ++j) \{`**

***`GtG\[i \* K + j\] = GtG\[j \* K + i\];`**

***`\}`**

***`\}`**

` `

***`std::vector\<double\> XtX\_XtG(K \* K, 0.0);`**

***`matmul\_kxk(XtX.data(), XtG.data(), XtX\_XtG.data(), K);`**

` `

***`std::vector\<double\> GpGp(K \* K, 0.0);`**

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`for (size\_t j = 0; j \< K; ++j) \{`**

***`double dot = 0.0;`**

***`for (size\_t k = 0; k \< K; ++k) \{`**

***`dot += XtG\[k \* K + i\] \* XtX\_XtG\[k \* K + j\];`**

***`\}`**

***`GpGp\[i \* K + j\] = GtG\[i \* K + j\] - dot;`**

***`\}`**

***`\}`**

` `

***`std::vector\<double\> H(K \* K, 0.0);`**

***`matmul\_kxk(GpGp.data(), XtX.data(), H.data(), K);`**

` `

***`std::vector\<double\> S(K \* K, 0.0);`**

***`std::vector\<double\> RHS\_S(K \* K, 0.0);`**

***`double tau\_sq\_fourth = 0.25 \* tau \* tau;`**

***`double half\_tau = 0.5 \* tau;`**

` `

***`for (size\_t idx = 0; idx \< K \* K; ++idx) \{`**

***`S\[idx\] = tau\_sq\_fourth \* H\[idx\];`**

***`RHS\_S\[idx\] = -half\_tau \* H\[idx\];`**

***`\}`**

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`S\[i \* K + i\] += 1.0;`**

***`\}`**

` `

***`if (!solve\_linear\_system\_kxk(S.data(), RHS\_S.data(), K, K)) \{`**

***`return POLYDIM\_STATUS\_ERR\_NUMERICAL\_NAN;`**

***`\}`**

` `

***`const double\* Z2 = RHS\_S.data();`**

` `

***`std::vector\<double\> XtX\_Z2(K \* K, 0.0);`**

***`matmul\_kxk(XtX.data(), Z2, XtX\_Z2.data(), K);`**

` `

***`std::vector\<double\> Z1(K \* K, 0.0);`**

***`for (size\_t idx = 0; idx \< K \* K; ++idx) \{`**

***`Z1\[idx\] = XtX\[idx\] + half\_tau \* XtX\_Z2\[idx\];`**

***`\}`**

` `

***`std::vector\<double\> XtG\_Z1(K \* K, 0.0);`**

***`matmul\_kxk(XtG.data(), Z1.data(), XtG\_Z1.data(), K);`**

` `

***`std::vector\<double\> Coef\_X(K \* K, 0.0);`**

***`for (size\_t idx = 0; idx \< K \* K; ++idx) \{`**

***`Coef\_X\[idx\] = Z2\[idx\] - XtG\_Z1\[idx\];`**

***`\}`**

` `

***`\#pragma omp parallel for schedule(static)`**

***`for (size\_t d = 0; d \< D; ++d) \{`**

***`std::vector\<double\> row\_update(K, 0.0);`**

***`for (size\_t k = 0; k \< K; ++k) \{`**

***`double g\_term = 0.0;`**

***`double x\_term = 0.0;`**

***`for (size\_t j = 0; j \< K; ++j) \{`**

***`g\_term += G\[d \* K + j\] \* Z1\[j \* K + k\];`**

***`x\_term += X\[d \* K + j\] \* Coef\_X\[j \* K + k\];`**

***`\}`**

***`row\_update\[k\] = X\[d \* K + k\] - tau \* g\_term - tau \* x\_term;`**

***`\}`**

***`for (size\_t k = 0; k \< K; ++k) \{`**

***`X\[d \* K + k\] = row\_update\[k\];`**

***`\}`**

***`\}`**

` `

***`return apply\_shifted\_cholqr2(X, D, K, shift\_regularization, num\_threads);`**

***`\}`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 8. SOLVER MONOLÍTICO DE STIEFEL (C++ SINGLE-SHOT PIPELINE) \*/`**

***`/\* ========================================================================= \*/`**

` `

***`int32\_t polydim\_stiefel\_optimize(`**

***`const double\* problem\_data,`**

***`size\_t problem\_size,`**

***`double\* X,`**

***`size\_t D,`**

***`size\_t K,`**

***`const PolydimSolverOptions\* options,`**

***`PolydimSolverResult\* result,`**

***`PolydimTelemetryBuffer\* telemetry`**

***`) \{`**

***`if (!X || !options || !result) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

***`if (D == 0 || K == 0 || K \> D) return POLYDIM\_STATUS\_ERR\_INVALID\_DIM;`**

` `

***`auto t\_start = std::chrono::high\_resolution\_clock::now();`**

` `

***`uint64\_t max\_iters = options-\>max\_iterations \> 0 ? options-\>max\_iterations : 100;`**

***`double grad\_tol = options-\>gradient\_tolerance \> 0 ? options-\>gradient\_tolerance : 1e-6;`**

***`double step\_tol = options-\>step\_tolerance \> 0 ? options-\>step\_tolerance : 1e-8;`**

***`double ortho\_tol = options-\>ortho\_tolerance \> 0 ? options-\>ortho\_tolerance : 1e-5;`**

***`double lr = options-\>learning\_rate \> 0 ? options-\>learning\_rate : 1e-3;`**

***`uint32\_t sample\_period = options-\>sampling\_period \> 0 ? options-\>sampling\_period : 1;`**

***`uint32\_t num\_threads = options-\>num\_threads \> 0 ? options-\>num\_threads : 1;`**

***`double shift\_reg = options-\>shift\_regularization;`**

` `

***`std::vector\<double\> G(D \* K, 0.0);`**

***`std::vector\<double\> I\_K(K \* K, 0.0);`**

***`for (size\_t i = 0; i \< K; ++i) I\_K\[i \* K + i\] = 1.0;`**

` `

***`int32\_t final\_status = POLYDIM\_STATUS\_MAX\_ITERATIONS;`**

***`uint64\_t iter = 0;`**

***`double current\_obj = 0.0;`**

***`double current\_grad\_norm = 0.0;`**

***`double current\_ortho\_err = 0.0;`**

` `

***`for (iter = 0; iter \< max\_iters; ++iter) \{`**

***`current\_obj = 0.0;`**

***`\#pragma omp parallel for reduction(+:current\_obj) schedule(static)`**

***`for (size\_t i = 0; i \< D \* K; ++i) \{`**

***`double target\_val = (problem\_data && i \< problem\_size) ? problem\_data\[i\] : 0.0;`**

***`double diff = X\[i\] - target\_val;`**

***`G\[i\] = diff;`**

***`current\_obj += 0.5 \* diff \* diff;`**

***`\}`**

` `

***`std::vector\<double\> XtG(K \* K, 0.0);`**

***`\#pragma omp parallel for schedule(static) collapse(2)`**

***`for (size\_t i0 = 0; i0 \< K; i0 += TILE\_K) \{`**

***`for (size\_t j0 = 0; j0 \< K; j0 += TILE\_K) \{`**

***`size\_t i\_max = std::min(i0 + TILE\_K, K);`**

***`size\_t j\_max = std::min(j0 + TILE\_K, K);`**

***`for (size\_t d = 0; d \< D; ++d) \{`**

***`for (size\_t i = i0; i \< i\_max; ++i) \{`**

***`for (size\_t j = j0; j \< j\_max; ++j) \{`**

***`double val = X\[d \* K + i\] \* G\[d \* K + j\];`**

***`\#pragma omp atomic`**

***`XtG\[i \* K + j\] += val;`**

***`\}`**

***`\}`**

***`\}`**

***`\}`**

***`\}`**

` `

***`std::vector\<double\> SymXtG(K \* K, 0.0);`**

***`for (size\_t i = 0; i \< K; ++i) \{`**

***`for (size\_t j = 0; j \< K; ++j) \{`**

***`SymXtG\[i \* K + j\] = 0.5 \* (XtG\[i \* K + j\] + XtG\[j \* K + i\]);`**

***`\}`**

***`\}`**

` `

***`current\_grad\_norm = 0.0;`**

***`\#pragma omp parallel for reduction(+:current\_grad\_norm) schedule(static)`**

***`for (size\_t d = 0; d \< D; ++d) \{`**

***`for (size\_t k = 0; k \< K; ++k) \{`**

***`double corr = 0.0;`**

***`for (size\_t j = 0; j \< K; ++j) \{`**

***`corr += X\[d \* K + j\] \* SymXtG\[j \* K + k\];`**

***`\}`**

***`G\[d \* K + k\] -= corr;`**

***`current\_grad\_norm += G\[d \* K + k\] \* G\[d \* K + k\];`**

***`\}`**

***`\}`**

***`current\_grad\_norm = std::sqrt(current\_grad\_norm);`**

` `

***`if (current\_grad\_norm \< grad\_tol) \{`**

***`final\_status = POLYDIM\_STATUS\_CONVERGED\_GRADIENT;`**

***`break;`**

***`\}`**

` `

***`int32\_t ret\_st = 0;`**

***`if (options-\>retraction\_type == POLYDIM\_RETRACTION\_CAYLEY\_SMW) \{`**

***`ret\_st = retract\_cayley\_smw\_gram(X, G.data(), D, K, lr, shift\_reg, num\_threads);`**

***`\} else \{`**

***`\#pragma omp parallel for schedule(static)`**

***`for (size\_t i = 0; i \< D \* K; ++i) \{`**

***`X\[i\] -= lr \* G\[i\];`**

***`\}`**

***`ret\_st = apply\_shifted\_cholqr2(X, D, K, shift\_reg, num\_threads);`**

***`\}`**

` `

***`if (ret\_st != 0) \{`**

***`final\_status = ret\_st;`**

***`break;`**

***`\}`**

` `

***`std::vector\<double\> Gram(K \* K, 0.0);`**

***`polydim\_gram\_dsyrk(X, D, K, Gram.data(), num\_threads);`**

***`current\_ortho\_err = matrix\_frobenius\_norm\_diff(Gram.data(), I\_K.data(), K \* K);`**

` `

***`if (current\_ortho\_err \> ortho\_tol && iter \> 5) \{`**

***`final\_status = POLYDIM\_STATUS\_ERR\_ORTHO\_VIOLATION;`**

***`break;`**

***`\}`**

` `

***`if (telemetry && telemetry-\>points && (iter % sample\_period == 0)) \{`**

***`if (telemetry-\>recorded\_count \< telemetry-\>capacity) \{`**

***`auto now = std::chrono::high\_resolution\_clock::now();`**

***`uint64\_t elapsed\_ns = std::chrono::duration\_cast\<std::chrono::nanoseconds\>(now - t\_start).count();`**

***`PolydimTelemetryPoint& pt = telemetry-\>points\[telemetry-\>recorded\_count++\];`**

***`pt.iteration = iter;`**

***`pt.objective\_value = current\_obj;`**

***`pt.gradient\_norm = current\_grad\_norm;`**

***`pt.step\_size = lr;`**

***`pt.ortho\_error = current\_ortho\_err;`**

***`pt.elapsed\_time\_ns = elapsed\_ns;`**

***`\}`**

***`\}`**

***`\}`**

` `

***`auto t\_end = std::chrono::high\_resolution\_clock::now();`**

***`uint64\_t total\_ns = std::chrono::duration\_cast\<std::chrono::nanoseconds\>(t\_end - t\_start).count();`**

` `

***`std::vector\<double\> Gram\_final(K \* K, 0.0);`**

***`polydim\_gram\_dsyrk(X, D, K, Gram\_final.data(), num\_threads);`**

***`current\_ortho\_err = matrix\_frobenius\_norm\_diff(Gram\_final.data(), I\_K.data(), K \* K);`**

` `

***`result-\>status = final\_status;`**

***`result-\>iterations\_executed = iter;`**

***`result-\>final\_objective = current\_obj;`**

***`result-\>final\_grad\_norm = current\_grad\_norm;`**

***`result-\>final\_ortho\_error = current\_ortho\_err;`**

***`result-\>total\_time\_ns = total\_ns;`**

` `

***`switch (final\_status) \{`**

***`case POLYDIM\_STATUS\_CONVERGED\_GRADIENT:`**

***`std::snprintf(result-\>status\_message, sizeof(result-\>status\_message), "Converged: Gradient norm below tolerance.");`**

***`break;`**

***`case POLYDIM\_STATUS\_MAX\_ITERATIONS:`**

***`std::snprintf(result-\>status\_message, sizeof(result-\>status\_message), "Completed maximum iterations.");`**

***`break;`**

***`case POLYDIM\_STATUS\_ERR\_ORTHO\_VIOLATION:`**

***`std::snprintf(result-\>status\_message, sizeof(result-\>status\_message), "Error: Stiefel manifold orthogonality violated.");`**

***`break;`**

***`default:`**

***`std::snprintf(result-\>status\_message, sizeof(result-\>status\_message), "Optimization terminated with status code %d.", final\_status);`**

***`break;`**

***`\}`**

` `

***`return final\_status;`**

***`\}`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 9. BANKED SLOT LEASE RCU (ZERO-COPY IPC PMTP) CON ATOMIC CAS \*/`**

***`/\* ========================================================================= \*/`**

` `

***`static int pmtp\_is\_process\_alive(uint32\_t pid) \{`**

***`if (pid == 0) return 0;`**

***`\#if defined(\_WIN32)`**

***`HANDLE h = OpenProcess(PROCESS\_QUERY\_LIMITED\_INFORMATION, FALSE, (DWORD)pid);`**

***`if (h == NULL) \{`**

***`DWORD err = GetLastError();`**

***`return (err == ERROR\_ACCESS\_DENIED) ? 1 : 0;`**

***`\}`**

***`DWORD exit\_code = 0;`**

***`if (GetExitCodeProcess(h, &exit\_code)) \{`**

***`CloseHandle(h);`**

***`return (exit\_code == STILL\_ACTIVE) ? 1 : 0;`**

***`\}`**

***`CloseHandle(h);`**

***`return 0;`**

***`\#else`**

***`int res = kill((pid\_t)pid, 0);`**

***`if (res == 0) return 1;`**

***`if (errno == EPERM) return 1; // Proceso existe pero pertenece a otro usuario`**

***`return 0;`**

***`\#endif`**

***`\}`**

` `

***`extern "C" int32\_t pmtp\_reap\_orphaned\_leases(`**

***`PmtpBankedSlotHeader\* header, `**

***`uint32\_t target\_bank, `**

***`uint64\_t timeout\_ns, `**

***`uint32\_t\* num\_reclaimed`**

***`) \{`**

***`if (!header || !num\_reclaimed) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

***`if (target\_bank \> 1) return POLYDIM\_STATUS\_ERR\_INVALID\_DIM;`**

` `

***`\*num\_reclaimed = 0;`**

***`PmtpReaderLease\* leases = (target\_bank == 0) ? header-\>leases\_bank0 : header-\>leases\_bank1;`**

` `

***`for (size\_t i = 0; i \< PMTP\_MAX\_READERS\_PER\_BANK; ++i) \{`**

***`std::atomic\<uint32\_t\>\* state\_atom = reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&leases\[i\].state);`**

***`uint32\_t cur\_state = state\_atom-\>load(std::memory\_order\_acquire);`**

` `

***`if (cur\_state == PMTP\_LEASE\_ACTIVE) \{`**

***`uint32\_t pid = leases\[i\].pid;`**

***`if (!pmtp\_is\_process\_alive(pid)) \{`**

***`uint32\_t expected = PMTP\_LEASE\_ACTIVE;`**

***`if (state\_atom-\>compare\_exchange\_strong(expected, PMTP\_LEASE\_RECLAIMED, std::memory\_order\_acq\_rel)) \{`**

***`(\*num\_reclaimed)++;`**

***`reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&header-\>num\_reclaimed\_orphans)-\>fetch\_add(1, std::memory\_order\_relaxed);`**

***`\}`**

***`\}`**

***`\}`**

***`\}`**

` `

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`extern "C" int32\_t pmtp\_banked\_slot\_acquire\_reader(`**

***`PmtpBankedSlotHeader\* header, `**

***`uint32\_t\* acquired\_bank,`**

***`uint32\_t\* acquired\_slot\_idx,`**

***`uint32\_t pid, `**

***`uint64\_t start\_time\_ns`**

***`) \{`**

***`if (!header || !acquired\_bank || !acquired\_slot\_idx) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

` `

***`uint32\_t bank = reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&header-\>active\_bank)-\>load(std::memory\_order\_acquire);`**

***`PmtpReaderLease\* leases = (bank == 0) ? header-\>leases\_bank0 : header-\>leases\_bank1;`**

` `

***`for (size\_t i = 0; i \< PMTP\_MAX\_READERS\_PER\_BANK; ++i) \{`**

***`std::atomic\<uint32\_t\>\* state\_atom = reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&leases\[i\].state);`**

***`uint32\_t cur\_state = state\_atom-\>load(std::memory\_order\_relaxed);`**

` `

***`if (cur\_state == PMTP\_LEASE\_FREE || cur\_state == PMTP\_LEASE\_CLOSED || cur\_state == PMTP\_LEASE\_RECLAIMED) \{`**

***`uint32\_t expected = cur\_state;`**

***`if (state\_atom-\>compare\_exchange\_strong(expected, PMTP\_LEASE\_ACTIVE, std::memory\_order\_acq\_rel)) \{`**

***`leases\[i\].pid = pid;`**

***`leases\[i\].process\_start\_time\_ns = start\_time\_ns;`**

***`leases\[i\].generation = reinterpret\_cast\<std::atomic\<uint64\_t\>\*\>(&header-\>sequence)-\>load(std::memory\_order\_acquire);`**

***`\*acquired\_bank = bank;`**

***`\*acquired\_slot\_idx = static\_cast\<uint32\_t\>(i);`**

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

***`\}`**

***`\}`**

` `

***`return POLYDIM\_STATUS\_ERR\_NO\_FREE\_SLOT;`**

***`\}`**

` `

***`extern "C" int32\_t pmtp\_banked\_slot\_release\_reader(PmtpBankedSlotHeader\* header, uint32\_t bank, uint32\_t slot\_idx) \{`**

***`if (!header || slot\_idx \>= PMTP\_MAX\_READERS\_PER\_BANK) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

` `

***`PmtpReaderLease\* leases = (bank == 0) ? header-\>leases\_bank0 : header-\>leases\_bank1;`**

***`std::atomic\<uint32\_t\>\* state\_atom = reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&leases\[slot\_idx\].state);`**

***`state\_atom-\>store(PMTP\_LEASE\_CLOSED, std::memory\_order\_release);`**

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`extern "C" int32\_t pmtp\_banked\_slot\_acquire\_writer(PmtpBankedSlotHeader\* header, uint32\_t\* write\_bank, uint32\_t pid, uint64\_t start\_time\_ns) \{`**

***`if (!header || !write\_bank) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

` `

***`uint32\_t expected = 0;`**

***`if (!reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&header-\>writer\_active)-\>compare\_exchange\_strong(expected, 1, std::memory\_order\_acq\_rel)) \{`**

***`return POLYDIM\_STATUS\_ERR\_WRITER\_BUSY;`**

***`\}`**

` `

***`uint32\_t active = reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&header-\>active\_bank)-\>load(std::memory\_order\_relaxed);`**

***`uint32\_t target = 1 - active;`**

***`PmtpReaderLease\* target\_leases = (target == 0) ? header-\>leases\_bank0 : header-\>leases\_bank1;`**

` `

***`int retries = 5000;`**

***`while (retries-- \> 0) \{`**

***`bool has\_active\_readers = false;`**

***`for (size\_t i = 0; i \< PMTP\_MAX\_READERS\_PER\_BANK; ++i) \{`**

***`std::atomic\<uint32\_t\>\* state\_atom = reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&target\_leases\[i\].state);`**

***`if (state\_atom-\>load(std::memory\_order\_acquire) == PMTP\_LEASE\_ACTIVE) \{`**

***`has\_active\_readers = true;`**

***`break;`**

***`\}`**

***`\}`**

***`if (!has\_active\_readers) break;`**

` `

***`uint32\_t reclaimed = 0;`**

***`pmtp\_reap\_orphaned\_leases(header, target, 1000000, &reclaimed);`**

***`\}`**

` `

***`header-\>owner\_pid = pid;`**

***`header-\>owner\_start\_time\_ns = start\_time\_ns;`**

***`\*write\_bank = target;`**

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`extern "C" int32\_t pmtp\_banked\_slot\_commit\_writer(PmtpBankedSlotHeader\* header, uint32\_t write\_bank) \{`**

***`if (!header) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

` `

***`std::atomic\_thread\_fence(std::memory\_order\_release);`**

***`reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&header-\>active\_bank)-\>store(write\_bank, std::memory\_order\_release);`**

***`reinterpret\_cast\<std::atomic\<uint64\_t\>\*\>(&header-\>sequence)-\>fetch\_add(1, std::memory\_order\_relaxed);`**

***`reinterpret\_cast\<std::atomic\<uint32\_t\>\*\>(&header-\>writer\_active)-\>store(0, std::memory\_order\_release);`**

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `

***`/\* ========================================================================= \*/`**

***`/\* 10. RESERVORIO ESTRUCTURADO WALSH-HADAMARD (LSM O(D log D), O(D) MEMORIA) \*/`**

***`/\* ========================================================================= \*/`**

` `

***`static void fwht\_normalized\_inplace(double\* x, size\_t D) \{`**

***`for (size\_t len = 1; len \< D; len \<\<= 1) \{`**

***`\#pragma omp parallel for schedule(static)`**

***`for (size\_t i = 0; i \< D; i += 2 \* len) \{`**

***`for (size\_t j = 0; j \< len; ++j) \{`**

***`double u = x\[i + j\];`**

***`double v = x\[i + j + len\];`**

***`x\[i + j\] = u + v;`**

***`x\[i + j + len\] = u - v;`**

***`\}`**

***`\}`**

***`\}`**

` `

***`double inv\_sqrt\_d = 1.0 / std::sqrt(static\_cast\<double\>(D));`**

***`\#pragma omp parallel for simd schedule(static)`**

***`for (size\_t i = 0; i \< D; ++i) \{`**

***`x\[i\] \*= inv\_sqrt\_d;`**

***`\}`**

***`\}`**

` `

***`extern "C" int32\_t polydim\_structured\_lsm\_step(`**

***`double\* state,`**

***`const double\* input,`**

***`const int8\_t\* d1,`**

***`const uint32\_t\* p1,`**

***`const int8\_t\* d2,`**

***`const uint32\_t\* p2,`**

***`size\_t D,`**

***`double alpha\_leak,`**

***`double input\_scale`**

***`) \{`**

***`if (!state || !d1 || !p1 || !d2 || !p2) return POLYDIM\_STATUS\_ERR\_NULL\_PTR;`**

***`if (D == 0 || (D & (D - 1)) != 0) return POLYDIM\_STATUS\_ERR\_INVALID\_DIM;`**

` `

***`std::vector\<double\> tmp(D, 0.0);`**

` `

***`\#pragma omp parallel for schedule(static)`**

***`for (size\_t i = 0; i \< D; ++i) \{`**

***`double s\_val = state\[p1\[i\]\] \* (d1\[p1\[i\]\] \< 0 ? -1.0 : 1.0);`**

***`tmp\[i\] = s\_val;`**

***`\}`**

` `

***`fwht\_normalized\_inplace(tmp.data(), D);`**

` `

***`double alpha = (alpha\_leak \> 0.0 && alpha\_leak \<= 1.0) ? alpha\_leak : 0.8;`**

***`double in\_scale = (input\_scale != 0.0) ? input\_scale : 1.0;`**

` `

***`\#pragma omp parallel for schedule(static)`**

***`for (size\_t i = 0; i \< D; ++i) \{`**

***`double w\_act = tmp\[p2\[i\]\] \* (d2\[i\] \< 0 ? -1.0 : 1.0);`**

***`double in\_val = (input != nullptr) ? (in\_scale \* input\[i\]) : 0.0;`**

***`double next\_val = std::tanh(w\_act + in\_val);`**

***`state\[i\] = (1.0 - alpha) \* state\[i\] + alpha \* next\_val;`**

***`\}`**

` `

***`return POLYDIM\_STATUS\_OK;`**

***`\}`**

` `






  

