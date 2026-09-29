# 🐕 \***AUDITORÍA RED TEAM BULLDOG — POLYDIM V812**

## \***Dictamen técnico línea a línea (C++ kernel + Rust guardián)**

\***Alcance real del material recibido: leí íntegramente `kernel\\\_cpp\\\_v812.cpp.txt` (37.6 KB) y `kernel\\\_rust\\\_v812.rs.txt` (26.1 KB, hasta el 60% — el filtro de consenso está completo, la síntesis cuántica Q1/Q2 quedó truncada). No pude auditar: `polydim\\\_dart\\\_v812.dart.txt`, `test\\\_v812\\\_ipc\\\_suite.py`, ni el header `polydim\\\_solver\\\_abi\\\_v808\\\_1.h` (del que dependen los layouts de `PolydimSpscRing`, `PolydimTelemetryEvent`, `PolydimSolverOptions` — crítico para verificar las promesas de alineación de 128 bytes del dossier). Tampoco hay código de PMTP/mmap/futex/PmtpSlabAllocator en el paquete: la Sección 2 del dossier (IPC futex TLS, allocator de slab) no tiene implementación auditable aquí. Lo que sigue es verificado contra el código real, no contra el dossier.**

## 🔴 \***CRÍTICAS (explotables / corrupción garantizada)**

### \***R-01 — `extern "C"` sin barrera de excepciones: `std::bad\\\_alloc` atraviesa la FFI → UB**

\***Archivo: `kernel\\\_cpp\\\_v812.cpp.txt` — todas las exportaciones (`polydim\\\_stiefel\\\_optimize`, `polydim\\\_gram\\\_dsyrk`, `polydim\\\_structured\\\_lsm\\\_step`, `polydim\\\_spsc\\\_init`, `polydim\\\_handle\\\_create`…).**

\***Causa raíz: el kernel hace decenas de `std::vector\\\<double\\\>` (líneas: `G(D\\\*K)`, `Z(D\\\*K)`, `S(K\\\*K)`, `scratch(num\\\_threads\\\*K\\\*K)`, `products(D)`, `tmp(D)`, `big.resize(K)`…). Si el allocator falla (y en D≥10⁷ con vectores de 2.5 GB va a fallar), C++ lanza `std::bad\\\_alloc` a través de una función `extern "C"`. Eso es UB según el estándar: en la práctica, o aborta el proceso entero (mata el bus de agentes Python/Rust) o salta frames no-C++. El `ffi\\\_guard!` de Rust solo captura panics de Rust, no excepciones C++. La G4 del dossier da falsa sensación de cobertura.**

\***Parche C++ (trampoline `noexcept` envolvente):**

\***cpp**

```
\*\*\*\`\\\#include \\\<exception\\\>\`\*\*  
  
  
\*\*\*\`template \\\<typename F\\\>\`\*\*  
  
\*\*\*\`static int32\\\_t polydim\\\_noexcept\\\_trampoline(F&& f) noexcept \\\{\`\*\*  
  
\`    \*\*\*try \\\{\`\*\*  
  
\`        \*\*\*return static\\\_cast\\\<int32\\\_t\\\>(f());\`\*\*  
  
\`    \*\*\*\\\} catch (const std::bad\\\_alloc&) \\\{\`\*\*  
  
\`        \*\*\*return POLYDIM\\\_STATUS\\\_ERR\\\_ALLOC;\`\*\*  
  
\`    \*\*\*\\\} catch (const std::exception&) \\\{\`\*\*  
  
\`        \*\*\*return POLYDIM\\\_STATUS\\\_ERR\\\_INTERNAL;\`\*\*  
  
\`    \*\*\*\\\} catch (...) \\\{\`\*\*  
  
\`        \*\*\*return POLYDIM\\\_STATUS\\\_ERR\\\_INTERNAL;\`\*\*  
  
\`    \*\*\*\\\}\`\*\*  
  
\*\*\*\`\\\}\`\*\*  
  
  
\*\*\*\`// Envolver cada exportación:\`\*\*\*  
  
\*\*\*\`POLYDIM\\\_EXPORT int32\\\_t polydim\\\_stiefel\\\_optimize(\*/\\\*args\\\*/\*) \\\{\`\*\*  
  
\`    \*\*\*return polydim\\\_noexcept\\\_trampoline(\\\[&\\\]() -\\\> int32\\\_t \\\{\`\*\*  
  
\`        \*\*\*return polydim\\\_stiefel\\\_optimize\\\_impl(\*/\\\*args\\\*/\*);\`\*\*  
  
\`    \*\*\*\\\});\`\*\*  
  
\*\*\*\`\\\}\`\*\*
```

\***Y añadir `POLYDIM\\\_STATUS\\\_ERR\\\_ALLOC` / `ERR\\\_INTERNAL` al ABI (la spsc ya tiene `ERR\\\_ALLOC`, el solver no).**

### \***R-02 — El fix G10 está incompleto: `LAST\\\_ERROR` global es write-only (código muerto)**

\***Archivo: `kernel\\\_rust\\\_v812.rs.txt`, funciones `polydim\\\_last\\\_error\\\_v1` y `polydim\\\_get\\\_last\\\_error\\\_v2`.**

\***Causa raíz: el comentario G10 dice *"last\_error global (no thread-local: el caller puede estar en otro hilo)"*. Pero leyendo el código:**

\***rust**

```
\*\*\*\`\\\#\\\[no\\\_mangle\\\]\`\*\*  
  
\*\*\*\`pub extern "C" fn polydim\\\_last\\\_error\\\_v1() -\\\> \\\*const c\\\_char \\\{\`\*\*  
  
\`    \*\*\*LAST\\\_ERR\\\_TLS.with(|tls| \\\{ ... \\\})   \*// ← lee TLS, NO el global\`\*\*\*  
  
\*\*\*\`\\\}\`\*\*  
  
  
\*\*\*\`\\\#\\\[no\\\_mangle\\\]\`\*\*  
  
\*\*\*\`pub extern "C" fn polydim\\\_get\\\_last\\\_error\\\_v2(...) -\\\> i32 \\\{\`\*\*  
  
\`    \*\*\*let bytes\\\_opt = LAST\\\_ERR\\\_TLS.with(|tls| \\\{ ... \\\});  \*// ← también TLS\`\*\*\*
```

\***El `Mutex\\\<Option\\\<CString\\\>\\\>` global se escribe en `set\\\_last\\\_error` y en `polydim\\\_reset\\\_engine\\\_state`, pero ninguna API lo lee jamás. Si el panic ocurre en un worker thread de Rust y el caller C/Python consulta desde su propio hilo (exactamente el escenario que G10 dice arreglar), `v1` devuelve `null` y `v2` reporta 0 bytes. El fallo real sigue vivo.**

\***Parche Rust:**

\***rust**

```
\*\*\*\`\\\#\\\[no\\\_mangle\\\]\`\*\*  
  
\*\*\*\`pub extern "C" fn polydim\\\_get\\\_last\\\_error\\\_v2(\`\*\*  
  
\`    \*\*\*out\\\_buf: \\\*mut c\\\_char, out\\\_cap: usize, out\\\_required: \\\*mut usize\`\*\*  
  
\*\*\*\`) -\\\> i32 \\\{\`\*\*  
  
\`    \*\*\*// G10 completo: preferir el global (cross-thread); TLS solo como fallback.\`\*\*\*  
  
\`    \*\*\*let bytes\\\_opt = LAST\\\_ERROR.lock().ok()\`\*\*  
  
\`        \*\*\*.and\\\_then(|g| g.as\\\_ref().map(|c| c.to\\\_bytes\\\_with\\\_nul().to\\\_vec()))\`\*\*  
  
\`        \*\*\*.or\\\_else(|| LAST\\\_ERR\\\_TLS.with(|tls|\`\*\*  
  
\`            \*\*\*tls.borrow().as\\\_ref().map(|c| c.to\\\_bytes\\\_with\\\_nul().to\\\_vec())));\`\*\*  
  
\`    \*\*\*// ...resto idéntico\`\*\*\*  
  
\*\*\*\`\\\}\`\*\*
```

\***Y eliminar `LAST\\\_ERR\\\_TLS` por completo (un solo canal, sin ambigüedad), o documentar v1 como depuración de hilo local.**

### \***R-03 — Trampa OOM en el Guardián Topológico: `HashSet` de aristas O(n²) + mediana geométrica O(n²·D)**

\***Archivo: `kernel\\\_rust\\\_v812.rs.txt` — `polydim\\\_rust\\\_frechet\\\_betti\\\_filter`.**

\***Causa raíz (Pass 1 — Aniquilación Asintótica): el grafo geométrico materializa todas las aristas dentro de umbral en un `HashSet\\\<(usize, usize)\\\>`. Peor caso legítimo: N agentes convergen (post-consenso) dentro de `dist\\\_threshold` → aristas ≈ n²/2. Con n = 10⁴ candidatos ya son ~5×10⁷ aristas (~3 GB en el HashSet); el diseño declara N≥10⁶ → 5×10¹¹ aristas = imposible. Además la "mediana geométrica discreta" hace un bucle honest² con distancia O(D) → O(n²·D) = 10¹²·D operaciones. El caso N=10⁶ del dossier solo pasó porque era sparse.**

\***Parche Rust (rejilla hash + mediana por Weiszfeld puro, eliminar la fase discreta O(n²·D)):**

\***rust**

```
\*\*\*\`// 1) Reemplazar HashSet por conteo de aristas por rejilla (no materializar):\`\*\*\*  
  
\*\*\*\`use std::collections::HashMap;\`\*\*  
  
\*\*\*\`let mut edge\\\_count: u64 = 0;\`\*\*  
  
\*\*\*\`let mut seen\\\_pairs = std::collections::HashSet::new(); \*// solo pares candidatos por celda\`\*\*\*  
  
\*\*\*\`let cell = thresh.max(1e-12);\`\*\*  
  
\*\*\*\`let mut grid: HashMap\\\<(i64, i64), Vec\\\<usize\\\>\\\> = HashMap::new();\`\*\*  
  
\*\*\*\`for &i in &honest \\\{\`\*\*  
  
\`    \*\*\*// proyección en las 2 primeras coords + hash de las demás (o LSH)\`\*\*\*  
  
\`    \*\*\*let key = grid\\\_key(&candidates\\\[i\\\*d..(i+1)\\\*d\\\], cell, d);\`\*\*  
  
\`    \*\*\*grid.entry(key).or\\\_default().push(i);\`\*\*  
  
\*\*\*\`\\\}\`\*\*  
  
\*\*\*\`// contar vecinos por celda vecina (27^k demasiado en D grande: usar LSH con 8 tablas)\`\*\*\*
```

\***y para la mediana geométrica, eliminar la fase `for &i in &honest \\\{ for &j in &honest \\\{...\\\} \\\}` (el mejor punto discreto) e ir directo a Weiszfeld desde el centroide del componente gigante — es O(iteraciones·n·D), suficiente con el damping ya implementado:**

\***rust**

```
\*\*\*\`// Inicialización por centroide en O(n·D) en vez de mejor-discreto O(n²·D):\`\*\*\*  
  
\*\*\*\`let mut median = vec!\\\[0.0f64; d\\\];\`\*\*  
  
\*\*\*\`for &j in &honest \\\{ for k in 0..d \\\{ median\\\[k\\\] += candidates\\\[j\\\*d+k\\\]; \\\} \\\}\`\*\*  
  
\*\*\*\`let inv = 1.0 / honest.len() as f64;\`\*\*  
  
\*\*\*\`for k in 0..d \\\{ median\\\[k\\\] \\\*= inv; \\\}\`\*\*
```

### \***R-04 — Modo determinista DSYRK: `products(D)` por hilo = O(threads × D × 8 B) → 5 GB en D=10⁷**

\***Archivo: `kernel\\\_cpp\\\_v812.cpp.txt`, `polydim\\\_gram\\\_dsyrk` (rama `POLYDIM\\\_FP\\\_DETERMINISTIC`).**

\***Causa raíz:**

\***cpp**

```
\*\*\*\`\\\#pragma omp parallel\`\*\*  
  
\*\*\*\`\\\{\`\*\*  
  
\`    \*\*\*std::vector\\\<double\\\> products(D);   \*// ← 80 MB en D=10^7, POR HILO\`\*\*\*
```

\***`omp\\\_get\\\_max\\\_threads()` en una máquina dual-socket puede ser 128/192 → 128 × 80 MB = 10–15 GB reservados simultáneamente para un Gramiano de K×K (que en D=10⁷ solo necesita 10⁴×10⁴×8 = 800 KB de salida). Es una relación memoria/salida de ~10⁴×. La compensación TwoSum no necesita el vector completo: basta un bloque por cache con acumulador persistente.**

\***Parche C++ (TwoSum por bloques, memoria O(cache) por hilo):**

\***cpp**

```
\*\*\*\`constexpr size\\\_t CHUNK = 4096;  \*// 32 KB, cabe en L1/L2\`\*\*\*  
  
\*\*\*\`\\\#pragma omp parallel\`\*\*  
  
\*\*\*\`\\\{\`\*\*  
  
\`    \*\*\*std::vector\\\<double\\\> buf(CHUNK);\`\*\*  
  
\`    \*\*\*double acc = 0.0, err = 0.0;              \*// compensación Neumaier/Knuth persistente\`\*\*\*  
  
\`    \*\*\*\\\#pragma omp for schedule(dynamic)\`\*\*  
  
\`    \*\*\*for (int64\\\_t i = 0; i \\\< (int64\\\_t)K; ++i) \\\{\`\*\*  
  
\`        \*\*\*for (size\\\_t j = (size\\\_t)i; j \\\< K; ++j) \\\{\`\*\*  
  
\`            \*\*\*acc = 0.0; err = 0.0;\`\*\*  
  
\`            \*\*\*for (size\\\_t d0 = 0; d0 \\\< D; d0 += CHUNK) \\\{\`\*\*  
  
\`                \*\*\*size\\\_t n = std::min(CHUNK, D - d0);\`\*\*  
  
\`                \*\*\*for (size\\\_t t = 0; t \\\< n; ++t)\`\*\*  
  
\`                    \*\*\*buf\\\[t\\\] = X\\\[(d0+t) \\\* K + i\\\] \\\* X\\\[(d0+t) \\\* K + j\\\];\`\*\*  
  
\`                \*\*\*// reducción por bloque + fusión compensada\`\*\*\*  
  
\`                \*\*\*double blk = twosum\\\_tree\\\_reduce\\\_inplace(buf.data(), n);\`\*\*  
  
\`                \*\*\*double s, t2;\`\*\*  
  
\`                \*\*\*knuth\\\_two\\\_sum(acc, blk, &s, &t2);\`\*\*  
  
\`                \*\*\*acc = s; err += t2;\`\*\*  
  
\`            \*\*\*\\\}\`\*\*  
  
\`            \*\*\*double val = acc + err;\`\*\*  
  
\`            \*\*\*K\\\_out\\\[i\\\*K+j\\\] = val; K\\\_out\\\[j\\\*K+i\\\] = val;\`\*\*  
  
\`        \*\*\*\\\}\`\*\*  
  
\`    \*\*\*\\\}\`\*\*  
  
\*\*\*\`\\\}\`\*\*
```

\***Esto además reduce el tráfico DRAM: el acceso `X\\\[d\\\*K+i\\\]` por filas de K saltando D×K×8 B por iteración es hostil a prefetch; con bloques se mejora la localidad (ideal: trasponer X una vez a layout \[K\]\[D\] antes del Gramiano).**

### \***R-05 — `omp\\\_set\\\_num\\\_threads()` desde una biblioteca: mutación de estado global del runtime OpenMP**

\***Archivo: `kernel\\\_cpp\\\_v812.cpp.txt`, `polydim\\\_gram\\\_dsyrk` y `polydim\\\_stiefel\\\_optimize`.**

\***Causa raíz (Pass 2):**

\***cpp**

```
\*\*\*\`if (threads \\\> 1) omp\\\_set\\\_num\\\_threads(threads);   \*// ¡desde una librería!\`\*\*\*
```

\***Esto cambia el número de hilos del proceso entero para cualquier otro código OpenMP del usuario (BLAS, otro solver, el runtime de PyTorch…). Es una carrera de configuración (TOCTOU de configuración): dos llamadas concurrentes con distinto `num\\\_threads` se pisan mutuamente, y un `omp\\\_set\\\_num\\\_threads` desde el hilo A afecta al region de B. Además, `compute\\\_VtZ` crea regiones paralelas *anidadas* (`\\\#pragma omp parallel` con dos `omp for` dentro) — si algún día es llamado desde dentro de una región paralela (el solver no lo hace hoy, pero nada lo prohíbe en la API), los `omp for` anidados son incorrectos.**

\***Parche C++ (ámbito por cláusula, nunca global):**

\***cpp**

```
\*\*\*\`// polydim\\\_gram\\\_dsyrk:\`\*\*\*  
  
\*\*\*\`\\\#pragma omp parallel num\\\_threads(threads)\`\*\*  
  
\*\*\*\`\\\{\`\*\*  
  
\`    \*\*\*...\`\*\*  
  
\`    \*\*\*\\\#pragma omp for schedule(dynamic)\`\*\*
```

\***cpp**

```
\*\*\*\`// polydim\\\_stiefel\\\_optimize: eliminar omp\\\_set\\\_num\\\_threads; usar num\\\_threads(nthreads)\`\*\*\*  
  
\*\*\*\`// en cada directiva parallel, o better: no tocar nada y documentar que se respeta\`\*\*\*  
  
\*\*\*\`// omp\\\_get\\\_max\\\_threads() del entorno (OMP\\\_NUM\\\_THREADS).\`\*\*\*
```

\***Regla de hierro para FFI: una biblioteca nunca llama `omp\\\_set\\\_num\\\_threads`.**

### \***R-06 — Contrato de flags de compilación ausente: `-ffast-math`/FTZ-DAZ destruyen la compensación TwoSum en silencio**

\***Archivo: `kernel\\\_cpp\\\_v812.cpp.txt`, `knuth\\\_two\\\_sum` + todo el modo determinista.**

\***Causa raíz (Pass 3 — Tortura Numérica): el truco `volatile double sum = a + b` bloquea la contracción FMA de *esa* línea, pero:**

1. \***`\\\*t = (a - a\\\_virtual) + (b - b\\\_virtual);` no es volatile — con `-ffast-math`/`-Ofast` el compilador reasocia y el término de error `t` se corrompe silenciosamente. No hay `\\\#error` ni `static\\\_assert` ni comprobación en runtime de las flags del TU.**

2. \***FTZ/DAZ (MXCSR bits 15/11): el término de compensación `t` de Knuth es frecuentemente subnormal (diferencias de magnitudes cercanas). Con DAZ=1 se lee como 0 (compensación aniquilada sin aviso); con FTZ=1 las escrituras subnormales se truncan. Python/numpy, algunos runtimes de audio/GPU y `-ffast-math` activan FTZ/DAZ a nivel de proceso. El resultado: el modo "determinista" deja de ser determinista y pierde exactitud sin un solo NaN que dispare el firewall.**

3. \***`err\\\_comp += et;` en `twosum\\\_tree\\\_reduce\\\_inplace` es una suma no compensada — inconsistente con el resto (segundo orden, pero contradice el invariante declarado).**

\***Parche C++ (contrato endurecido + sonda runtime de MXCSR):**

\***cpp**

```
\*\*\*\`// Al inicio del TU:\`\*\*\*  
  
\*\*\*\`\\\#if defined(\\\_\\\_FAST\\\_MATH\\\_\\\_)\`\*\*  
  
\*\*\*\`\\\#error "POLYDIM kernel MUST NOT be compiled with -ffast-math/-Ofast: it silently \\\\\`\*\*  
  
\`        \*\*\*destroys Knuth TwoSum compensation (reassociation) and enables FTZ/DAZ."\`\*\*  
  
\*\*\*\`\\\#endif\`\*\*  
  
  
\*\*\*\`// Sonda al arranque de cada exportación numérica (x86-64):\`\*\*\*  
  
\*\*\*\`\\\#if defined(\\\_\\\_x86\\\_64\\\_\\\_) || defined(\\\_M\\\_X64)\`\*\*  
  
\*\*\*\`static bool polydim\\\_ftz\\\_daz\\\_active() \\\{\`\*\*  
  
\`    \*\*\*unsigned int mxcsr = \\\_mm\\\_getcsr();\`\*\*  
  
\`    \*\*\*return (mxcsr & (1u \\\<\\\< 15)) || (mxcsr & (1u \\\<\\\< 11));  \*// FTZ | DAZ\`\*\*\*  
  
\*\*\*\`\\\}\`\*\*  
  
\*\*\*\`// En polydim\\\_gram\\\_dsyrk / stiefel / lsm\\\_step:\`\*\*\*  
  
\*\*\*\`if (polydim\\\_ftz\\\_daz\\\_active())\`\*\*  
  
\`    \*\*\*return POLYDIM\\\_STATUS\\\_ERR\\\_NUMERICAL\\\_ENV;  \*// nuevo código ABI\`\*\*\*  
  
\*\*\*\`\\\#endif\`\*\*
```

\***Y corregir el acumulador de segundo orden: `double es, et; knuth\\\_two\\\_sum(err\\\_comp, et, &es, &et); err\\\_comp = es;` (tirar `err\\\_comp\\\_raw` si se quiere rigor completo) o documentar explícitamente que `err\\\_comp` es término de tercer orden aceptado.**

## 🟠 \***ALTAS**

### \***A-01 — Fallback del Cayley-SMW degrada silenciosamente a Euler explícito**

\***Archivo: `retract\\\_cayley\\\_smw\\\_mixed`.**

\***cpp**

```
\*\*\*\`if (!solve\\\_linear\\\_system\\\_general(C.data(), RHS.data(), K2, K)) \\\{\`\*\*  
  
\`    \*\*\*for (...) V\\\[i\\\] += tau \\\* Z\\\[i\\\];            \*// Euler explícito: puede salirse de la variedad\`\*\*\*  
  
\`    \*\*\*return apply\\\_shifted\\\_cholqr2(...);       \*// y el status devuelto es OK\`\*\*\*  
  
\*\*\*\`\\\}\`\*\*
```

\***El caller nunca se entera de que la retracción estructural falló y se usó el camino burdo. En trayectorias largas esto es exactamente cómo se acumula deriva fuera de St(D,K). Parche: devolver un código distinto (`POLYDIM\\\_STATUS\\\_RETRACTION\\\_FALLBACK`) y dejar que el solver decida; o reintentar con shift aumentado antes de rendirse.**

### \***A-02 — `beta \\\* c` con `beta == 0.0` y `c` no inicializado/no-finito → NaN**

\***Archivo: `tiled\\\_dsyrk\\\_fixed`: `c\\\[i\\\*ldc+j\\\] = alpha\\\*acc + beta\\\*c\\\[i\\\*ldc+j\\\];` Hoy el único caller hace `memset(K\\\_out, 0, …)` antes, así que `0.0 \\\* 0.0` es seguro. Pero la función es el "reemplazo del fallback de BlasLoader para uso directo" — cualquier caller futuro que pase `beta=0` con buffer NaN (convenio BLAS: beta=0 ignora el contenido de C) recibirá NaN. Parche:**

\***cpp**

```
\*\*\*\`if (beta == 0.0) c\\\[i\\\*ldc+j\\\] = alpha\\\*acc;\`\*\*  
  
\*\*\*\`else             c\\\[i\\\*ldc+j\\\] = alpha\\\*acc + beta\\\*c\\\[i\\\*ldc+j\\\];\`\*\*
```

### \***A-03 — `catch\\\_unwind` es inútil si el perfil de compilación es `panic = "abort"`**

\***Archivo: `kernel\\\_rust\\\_v812.rs.txt` (todo `ffi\\\_guard!`). Si el `.so`/`.dll` se compila con `panic = "abort"` en Cargo.toml (default en muchos perfiles release de cdylib), el panic aborta el proceso antes de que `catch\\\_unwind` lo vea: el FFI entero se cae y arrastra al proceso anfitrión. Nada en el código lo previene. Parche (Cargo.toml obligatorio):**

\***toml**

```
\*\*\*\`\\\[profile.release\\\]\`\*\*  
  
\*\*\*\`panic = "unwind"   \*\\\# INNEGOCIABLE para cdylib con ffi\\\_guard\`\*\*\*
```

\***y añadir un test de contrato que verifique en CI que `catch\\\_unwind` realmente captura (inyectar un panic deliberado vía función de test exportada).**

### \***A-04 — LSM: validación de permutaciones + firewall NaN son dos pasadas seriales y cache-frías por paso**

\***Archivo: `polydim\\\_structured\\\_lsm\\\_step`. En D=10⁷: loop serial de 10⁷ comparaciones de `p1\\\[i\\\]/p2\\\[i\\\]`, más al final otro loop serial de `isfinite` sobre 80 MB. Por paso de reservorio, eso son ~3 pasadas frías extra sobre el estado. Parche: paralelizar la validación (`\\\#pragma omp parallel for reduction(&&:all\\\_valid)` con `all\\\_valid` en `char`), y fusionar el firewall NaN dentro del loop de actualización con bandera por hilo:**

\***cpp**

```
\*\*\*\`char nan\\\_flag = 0;\`\*\*  
  
\*\*\*\`\\\#pragma omp parallel for reduction(|:nan\\\_flag)\`\*\*  
  
\*\*\*\`for (int64\\\_t i = 0; i \\\< (int64\\\_t)D; ++i) \\\{\`\*\*  
  
\`    \*\*\*...\`\*\*  
  
\`    \*\*\*double s = (1.0-alpha)\\\*state\\\[i\\\] + alpha\\\*std::tanh(w + in\\\_val);\`\*\*  
  
\`    \*\*\*state\\\[i\\\] = s;\`\*\*  
  
\`    \*\*\*nan\\\_flag |= !std::isfinite(s);\`\*\*  
  
\*\*\*\`\\\}\`\*\*  
  
\*\*\*\`if (nan\\\_flag) return POLYDIM\\\_STATUS\\\_ERR\\\_NUMERICAL\\\_NAN;\`\*\*
```

### \***A-05 — RP-Tree con solape: el guarda solo detecta solape total; el parcial degenera a O(n²·D)**

\***Archivo: Rust, construcción del árbol RP en `polydim\\\_rust\\\_frechet\\\_betti\\\_filter`. El guarda `left.len()==n && right.len()==n` atrapa el caso donde *todo* cae en el margen. Pero con `left = 0.9n, right = 0.9n` (margen solapa mucho), cada nivel procesa 1.8n puntos y los puntos del solape se arrastran a ambos subárboles: trabajo total O(κ·n·D) con κ grande, y peor caso cuadrático sin límite de profundidad. Parche: presupuesto de trabajo (`work\\\_budget = 64·n·log2(n)`) que al agotarse fuerza hojas; y/o margin máximo `margin = min(thresh\\\*norm, quantile spread)`.**

### \***A-06 — `polydim\\\_stream\\\_copy\\\_nt`: aritmética de punteros en el chequeo de solape es UB teórico; semántica NT sin contrato de consumidor**

\***Archivo: `polydim\\\_stream\\\_copy\\\_nt`. `src + count`/`dest + count` overflowan el espacio de direcciones si `count` es enorme (UB en el chequeo mismo). Además, los stores NT son weakly-ordered: el `\\\_mm\\\_sfence()` del productor está bien, pero si este kernel alimenta el "zero-copy PMTP" del manifiesto, el consumidor en otro core necesita su propio `lfence`/acquire pairing que no está especificado en ninguna parte del código entregado. Parche: comparar con `uintptr\\\_t` (como ya hace Rust en los chequeos de alineación):**

\***cpp**

```
\*\*\*\`uintptr\\\_t d = reinterpret\\\_cast\\\<uintptr\\\_t\\\>(dest), s = reinterpret\\\_cast\\\<uintptr\\\_t\\\>(src);\`\*\*  
  
\*\*\*\`if (d \\\< s + count\\\*sizeof(double) && s \\\< d + count\\\*sizeof(double)) \\\{ std::memmove(...); return OK; \\\}\`\*\*
```

### \***A-07 — Pass 5 (SOTA): `polar\\\_newton\\\_refinement` hace hasta 8 DSYRK completos por retracción**

\***Archivo: `kernel\\\_cpp\\\_v812.cpp.txt`. Cada paso del solver Cayley llama `polar\\\_newton\\\_refinement` → hasta 8 × `polydim\\\_gram\\\_dsyrk` → cada uno lee D·K×8 B (2.5 GB en D=10⁷, K=32) de DRAM. Son hasta 20 GB de tráfico por iteración solo en refinamiento, más los 3 Gramianos ya calculados en la retracción (VtV, ZtZ, VtZ). El chequeo de convergencia debería ocurrir antes de la primera pasada cuando el Cayley-SMW ya devuelve un punto casi ortogonal (error O(τ²‖Z‖²) tipicamente ≪ 1e-14 con τ pequeño). Parche (orden de evaluación barata primero):**

\***cpp**

```
\*\*\*\`static void polar\\\_newton\\\_refinement(...) \\\{\`\*\*  
  
\`    \*\*\*// Chequeo pre-pasada con el Gramiano que el caller YA calculó cuando sea posible,\`\*\*\*  
  
\`    \*\*\*// o al menos: 1 DSYRK → si err \\\< tol (casi siempre tras Cayley) → return.\`\*\*\*  
  
\`    \*\*\*for (int pass = 0; pass \\\< 8; ++pass) \\\{\`\*\*  
  
\`        \*\*\*polydim\\\_gram\\\_dsyrk(V, D, K, S.data(), num\\\_threads);\`\*\*  
  
\`        \*\*\*...\`\*\*  
  
\`        \*\*\*if (std::sqrt(err) \\\< tol) break;\`\*\*  
  
\`        \*\*\*if (pass == 0 && err \\\< 1e-13) break;  \*// cota a priori del Cayley\`\*\*\*
```

\***Optimización estructural mayor: reutilizar `VtV` de la retracción como primer `S` (son la misma matriz para V viejo; no válido tras actualizar V — evaluar). Cerrar con SORM/low-rank no aplica aquí (K pequeño), el cuello real es DRAM: considerar bloqueo por paneles de D para que cada pasada sea una única lectura stream + compute (roofline), en vez del patrón columna `X\\\[d\\\*K+i\\\]`.**

## 🟡 \***MEDIAS / CONTRATO**

\***Table**

| **\#** | **Hallazgo** | **Ubicación** | **Nota** |
| :-: | :-: | :-: | :-: |
| M-01 | Refcount `int32\\\_t` sin guarda de overflow | `polydim\\\_handle\\\_retain` | Teórico (2³¹ retains), pero un `fetch\\\_add` saturante cuesta 2 líneas |
| M-02 | `polydim\\\_spsc\\\_destroy` solo es seguro por contrato verbal | C++ §4 | Ninguna barrera/epoch impide destruir con productor vivo; documentar en el header o añadir flag `closing` atómico |
| M-03 | `err\\\_comp += et` no compensado | `twosum\\\_tree\\\_reduce\\\_inplace` | Tercer orden, aceptable; documentar |
| M-04 | `out\\\_consensus\\\_vector` sin chequeo de alineación 8B (sí existe para `candidates`) | Rust `frechet\\\_betti\\\_filter` | Asimetría trivial de validación |
| M-05 | Weiszfeld `dsq \\\< 1e-16` absoluto | Rust | Debe ser relativo a la escala de los datos (en vectores unitarios 1e-16 es razonable; en datos escalados no) |
| M-06 | `CONVERGED\\\_STEP` usa `lr \\\* grad\\\_norm` pero el paso real Cayley no es `lr·G` | `polydim\\\_stiefel\\\_optimize` | Semántica del criterio inconsistente con la retracción usada |
| M-07 | Claim de 128 B de alineación para `write\\\_index`/`read\\\_index` del SPSC **no verificable**: layout vive en el header no entregado | ABI | Reenviar `polydim\\\_solver\\\_abi\\\_v808\\\_1.h`; si no hay `alignas(128)` en los índices, el dossier miente en §2 |
| M-08 | `ortho\\\_tol` default 1e-5 vs invariante declarado 4.44e-16 del manifiesto | opciones del solver | El solver certifica Stiefel a 1e-5, no a eps de máquina; alinear expectativas del contrato |
| M-09 | Chequeo `!manifold\\\_ok && iter \\\> 5` | solver | Constante mágica; un mal punto inicial legítimo tarda 6 iteraciones en abortar |
| M-10 | `K \\\> 256` fallback: `std::vector` alloc **por fila d** dentro del `omp for` | `project\\\_to\\\_tangent\\\_space`, CholQR2, Cayley | Mover el `big.resize(K)` fuera del loop paralelo (scratch por hilo) |
| M-11 | `lr` fijo, sin line-search | solver | Convergencia no garantizada en problemas reales; es un descenso de gradiente puro con retracción |


## ⚠️ \***Brecha de auditoría (lo que NO pude verificar — no lo doy por sano)**

1. \***Header ABI `polydim\\\_solver\\\_abi\\\_v808\\\_1.h`: sin él, `polydim\\\_abi\\\_probe()` es la única defensa y no cubre offsets de campos, alineación real de `PolydimSpscRing` (M-07), ni versionado de `PolydimTelemetryEvent`.**

2. \***Dart FFI (NativeFinalizer, BR-05): sin leer el archivo no puedo confirmar idempotencia del finalizador, ni que los handles se liberan exactamente una vez bajo GC de Dart.**

3. \***Suite de tests `test\\\_v812\\\_ipc\\\_suite.py`: no puedo confirmar que los 7/7 tests ejerciten los caminos de fallback (A-01), los errores de allocator (R-01) o FTZ (R-06).**

4. \***PMTP / futex TLS / RCU / slab allocator: citados en el dossier (BR-03, BR-04) pero ausentes del paquete. El Pass 2 sobre ABA/torn reads del bus PMTP no tiene código que auditar: queda pendiente por diseño, no certificado.**

5. \***La síntesis cuántica Q1/Q2 (Rust, final del archivo): truncada en la lectura; el claim de fidelidad 0.8536→1.0 no lo verifiqué.**

## \***Veredicto del tribunal**

\***No certificable para producción en D≥10⁷. El código es claramente la enésima pasada de un proceso iterativo honesto (los fixes G1–G14/C4/C7 son reales y bien hechos), pero tiene 3 fallos de categoría FFI/UB (R-01, R-03, R-06), 1 fix documentado que no está conectado (R-02), y 1 trampa OOM asintótica (R-04) que explota exactamente en la dimensión que el manifiesto declara como objetivo. Ninguno requiere rediseño; todos tienen parche cerrado arriba.**

\***Orden de ejecución recomendado: R-01 (una tarde) → R-02 (una hora) → R-04 + A-04 (afectan D grande) → R-06 (contrato de build) → R-03 + A-05 (escala del guardián) → R-05 → el resto. Reenvíame el header, el Dart y los tests, y paso el Bulldog Loop sobre la frontera FFI completa.**

***Bulldog fuera. El código duerme, yo vigilo.* 🐕**

\***Free quota used upUpgrade**

**InstantHigh**



