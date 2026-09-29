## Auditoría Bulldog Red Team POLYDIM V817, ronda 1

### Alcance

Recibí 4 archivos: la suite de 10 tests, el fuzz de los 3 sabuesos, la guía de evaluación y el prompt externo. **No recibí `kernel\_rust\_v817.rs`, `kernel\_cpp\_v817.cpp` ni `polydim\_v817\_monolito.py`.**

- Las Pasadas 1, 2, 4 y 5 sobre el código de los kernels no se pueden ejecutar todavía. No emito ningún `\[VERIFIED\_STABLE\]`. 

- Lo que sí audité es la evidencia: si los tests prueban lo que dicen probar, y la matemática de los documentos. 

- Verifiqué numéricamente en sandbox los hallazgos marcados como "verificado". Los demás son de lectura y lo indico. 

Un test que no puede fallar no certifica nada, y el tribunal está aceptando "10/10 PASS" como prueba. Los hallazgos van de mayor a menor gravedad.


**\[BREACH-01\]: HIGH**  
**\[MODULE & LOCATION\]:** `test\_v817\_comprehensive\_suite.py::test\_8`, docstring y aserto. Guía, fila TEST 8.  
**\[CAUSA RAÍZ\]:** La evidencia de rendimiento es contradictoria y una cifra es físicamente imposible.

- El docstring declara 229.8 GB/s a 34.8 µs. La guía declara 2.80 GB/s (49.0x). Es el mismo test con dos resultados. 

- El A4-6300 tiene DDR3 de doble canal, con pico teórico de unos 25.6 GB/s, y un solo MB de L2. Un memcpy de 8 MB no puede ir a 229.8 GB/s, ni siquiera desde caché. 

- La cifra de 875.3 µs para 1 MB (TEST 6) equivale a 1.2 GB/s y no cuadra con ninguna de las dos. Es una medición de un solo disparo, sin calentamiento, dominada por los page faults de un `bytearray` recién creado. 

- El "49x / 140 ms" compara un memcpy con una decodificación autorregresiva. Los 140 ms son una constante inventada en el propio test. 

- El aserto `\> 1.0 GB/s` no falla ante ninguna de las dos cifras. 

**\[ESCENARIO\]:** Un revisor externo ve 229.8 GB/s, sabe que es imposible y descarta toda la certificación.  
**\[FIX\]:**

python

```
`\# Medir sobre buffers ya tocados, con mediana y p95, y calibrar contra un memcpy de referencia`

`import ctypes, numpy as np, time`

`def bw\_ref(n):`

`    a = np.frombuffer(np.random.bytes(n), dtype=np.uint8).copy()`

`    b = np.empty\_like(a); b\[:\] = 0            \# tocar paginas`

`    ts = \[\]`

`    for \_ in range(200):`

`        t0 = time.perf\_counter\_ns(); np.copyto(b, a); ts.append(time.perf\_counter\_ns()-t0)`

`    return n / (np.median(ts)\*1e-9) / 1e9`

`\# En test\_8: assert bw\_kernel \<= 1.5 \* bw\_ref(payload\_bytes), y bw\_kernel \>= 0.5 \* bw\_ref(...)`

`\# Un valor mayor al techo de DRAM (25.6 GB/s) debe FALLAR el test por implausible, no pasarlo.`

`\# Borrar la constante 140 ms o citarla con fuente y hardware.`
```


**\[BREACH-02\]: HIGH (requiere verificación con CPUID)**  
**\[MODULE & LOCATION\]:** Guía, Paso 1: `g++ ... -mavx2 -mfma ...`. Docstrings de test y fuzz: "AMD A4-6300 Floor" y "C++ AVX2".  
**\[CAUSA RAÍZ\]:** Según mi conocimiento, el A4-6300 es Piledriver (Richland). Tiene AVX, FMA3, FMA4 y XOP, pero **no AVX2**, que llegó con Excavator. No lo verifiqué en sandbox.  
**\[ESCENARIO\]:** Con `-mavx2` global, GCC puede emitir instrucciones AVX2 en cualquier función, incluso escalar, y el resultado es SIGILL. Si el test corrió, o el hardware no es el declarado, o hay un dispatch en runtime que la guía no documenta.  
**\[FIX\]:**

bash

```
`\# Verificar en la maquina real:`

`wmic cpu get name          \# y CPU-Z / coreinfo -f  (buscar AVX2)`

`\# Compilar el baseline para el piso real y despachar en runtime:`

`g++ -std=c++20 -O3 -mavx -mfma -fopenmp -shared kernel\_cpp\_v817.cpp -o polydim\_cpp\_v817.dll`

`\# Ruta AVX2 solo en funciones con \_\_attribute\_\_((target("avx2,fma"))) detras de \_\_builtin\_cpu\_supports("avx2")`
```

Si el A4-6300 no tiene AVX2, "C++ AVX2 OpenMP" en la salida del Sabueso 3 es una afirmación falsa que hay que corregir.


**\[BREACH-03\]: HIGH**  
**\[MODULE & LOCATION\]:** `sabueso\_1\_concurrency\_tls\_race`, bloque "3. QSBR Snapshot copy". Guía TEST 6. Eje "Zero UAF".  
**\[CAUSA RAÍZ\]:** El test no prueba QSBR ni RCU. Cada hilo copia su propio `bytes` privado, que nadie muta. No hay escritor, ni contador de generación, ni lectura desgarrada posible.

- Es un test de thread-safety de un memcpy. 

- No cubre nada de la Pasada 2: ABA, escritura atómica de 64 bits desgarrada, false sharing a 128 B, ni el proceso escritor muerto por SIGKILL a mitad de publicación. 

- La frase "100% thread-safe" no está respaldada. 

**\[ESCENARIO\]:** Un escritor publica a mitad de un `snapshot\_copy` y el lector obtiene la mitad de la generación N y la mitad de la N+1. Ningún test actual lo detecta.  
**\[FIX\]:** Payload autovalidante con escritor real y proceso matado a la fuerza.

python

```
`\# Cada bloque de 64 B lleva \[gen(8B) repetido x8\]. Un snapshot valido tiene TODOS los gen iguales.`

`import multiprocessing as mp, numpy as np, os, signal, time`

`def writer(shm\_ptr\_fn, stop):            \# usa la API de publicacion real del kernel`

`    g = 0`

`    while not stop.is\_set():`

`        g += 1`

`        publish(np.full(N//8, g, dtype=np.uint64))     \# publish = API real del escritor`

`def reader\_check(buf):`

`    a = np.frombuffer(buf, dtype=np.uint64)`

`    return bool((a == a\[0\]).all())                      \# falso =\> lectura desgarrada`

`\# Reader loop: 10^6 snapshots, contar desgarros (debe ser 0).`

`\# Chaos: os.kill(writer\_pid, signal.SIGKILL) en instante aleatorio, y luego`

`\#   verificar que el lector no se cuelga, que el epoch avanza, y que el arena se recupera.`
```


**\[BREACH-04\]: HIGH**  
**\[MODULE & LOCATION\]:** `test\_10`, `ortho\_error = norm(QQ^T - I, 'fro') / n`. Guía TEST 10 ("Err = 0.12 \< 0.2").  
**\[CAUSA RAÍZ\]:** (verificado por aritmética) El axioma 0.2.6 exige `eps\_iso = ||O^T O - I||\_2` (norma espectral). El test mide Frobenius dividido por n, que subestima el error.

- Como `||E||\_2 \>= ||E||\_F / sqrt(n)`, un valor reportado de 0.12 con n=64 implica `||E||\_F = 7.68` y `||E||\_2 \>= 0.96`. 

- Un error espectral cercano a 1 significa singulares muy lejos de 1. Eso no es una isometría. 

- Una matriz gaussiana 64x64 tiene condición enorme, y 5 pasos de NS no orquestan los singulares pequeños. 

- La bandera `converged` no tiene definición visible. 

**\[ESCENARIO\]:** Muon o NorMuon reciben una "ortogonal" con singulares cerca de 0 y el paso de actualización pierde direcciones enteras.  
**\[FIX\]:**

python

```
`E = q\_ortho.T @ q\_ortho - np.eye(n)`

`eps\_iso = np.linalg.norm(E, 2)                       \# espectral, como exige el axioma`

`sv = np.linalg.svd(q\_ortho, compute\_uv=False)`

`assert eps\_iso \< 0.2 and sv.min() \> 0.8 and sv.max() \< 1.2   \# umbral justificado por Gram-NS q\<=2`

`\# Si el criterio real de Muon es sv en \[0.7,1.2\], documentarlo y ajustar el umbral, no ocultarlo con /n.`
```


**\[BREACH-05\]: MEDIUM**  
**\[MODULE & LOCATION\]:** Kernel AuON `log\_cosh` (según la fórmula del prompt: `|z| + log1p(e^\{-2|z|\}) - ln 2`). Fuzz \[2.1\].  
**\[CAUSA RAÍZ\]:** (verificado contra mpmath) Cancelación catastrófica para |z| pequeño, porque resta ln2 de una cantidad cercana a ln2.

| **z** | **error relativo de la fórmula** |
| :-: | :-: |
| 1e-4 | 4.4e-9 |
| 1e-6 | 8.9e-5 |
| 1e-8 | 122% (devuelve 1.11e-16 en vez de 5e-17) |
| 1e-9 | 100% (devuelve 0) |

La pérdida puede salir 0 o incluso negativa, siendo `log cosh \>= 0`. El gradiente no se afecta, porque usa `tanh`. El aserto del fuzz `abs(loss) \< 1e-12` oculta el defecto.

**\[FIX\]:** Identidad exacta `cosh z = 1 + 2 sinh^2(z/2)`.

rust

```
`fn log\_cosh(z: f64) -\> f64 \{`

`    let a = z.abs();`

`    if a \<= 20.0 \{ (2.0 \* (0.5 \* a).sinh().powi(2)).ln\_1p() \}      // rel. err ~1e-16 (verificado)`

`    else \{ a + (-2.0 \* a).exp().ln\_1p() - std::f64::consts::LN\_2 \}`

`\}`
```


**\[BREACH-06\]: MEDIUM**  
**\[MODULE & LOCATION\]:** Mismo kernel, cálculo `z = x / s`.  
**\[CAUSA RAÍZ\]:** (verificado) Con `x=1e300`, `s=1e-10`, `z` es `+inf` y la pérdida sale `inf` aunque la pérdida real (`lambda\*s\*|x|`, del orden de 1e290) es finita y representable. Los 3 sabuesos no prueban `x` grande con `s` pequeño. Tampoco prueban ±Inf, aunque el título del sabueso lo promete.  
**\[FIX\]:**

rust

```
`// loss = lambda\*s^2\*logcosh(x/s)  ==  lambda\*s\*( |x| + s\*(log1p(exp(-2|z|)) - ln2) )  para |z| grande`

`let az = (x / s).abs();                       // puede ser inf: exp(-inf)=0, no NaN`

`let tail = s \* ((-2.0\*az).exp().ln\_1p() - LN\_2);`

`let loss = lambda \* s \* (x.abs() + tail);     // finito para x=1e300, s=1e-10`

`let grad = lambda \* s \* (x / s).tanh();       // |grad| \<= lambda\*s`
```

Añadir casos `x=±inf` con contrato explícito (código de error o saturación) y `s` subnormal.


**\[BREACH-07\]: MEDIUM**  
**\[MODULE & LOCATION\]:** `test\_2` Caso 4 y fuzz \[2.4\]. Prompt de auditoría, reclamo 2 vs axioma 0.2.1.  
**\[CAUSA RAÍZ\]:**

- Los "casos de estrés 1.0 + 1e-15" son comentarios sin código. En el fuzz, `v\_overflow = u.copy()` es idéntico a `u`. Prueba `acos(1)`, no el desborde. 

- No hay ningún caso con ángulo pequeño no nulo, que es donde `arccos` falla y la fórmula cordal gana. (verificado): 

| **theta** | **arccos** | **cordal** |
| :-: | :-: | :-: |
| 1e-8 | 0 | 1e-8 |
| 1e-9 | 0 | 1e-9 |

- El prompt reclama métrica cordal `2 arcsin(||u-v||/2)`, mientras el axioma 0.2.1 exige `arccos(clip(u^T v))`. Son dos especificaciones distintas del mismo componente. 

- La cordal mueve la mala condición al punto antípoda, con `arcsin'` infinita en 1. Exige `min(1.0, chord/2)`. 

**\[FIX\]:**

python

```
`for th in (1e-4, 1e-7, 1e-9, 1e-12):`

`    u = np.zeros(D); u\[0\]=1; v = np.zeros(D); v\[0\]=np.cos(th); v\[1\]=np.sin(th)`

`    ang,\_ = rust\_k.riemannian\_geodesic(u, v)`

`    assert abs(ang - th) \<= 1e-12\*th + 1e-300, (th, ang)     \# falla si usa arccos(dot)`

`\# Antipoda: v = -u perturbado en 1 ulp, no debe dar NaN.`
```

En Rust: `2.0 \* (0.5 \* chord).min(1.0).asin()`. Decidir cuál métrica es la normativa y unificar los documentos.


**\[BREACH-08\]: MEDIUM**  
**\[MODULE & LOCATION\]:** `sabueso\_1`, chequeo TLS (`"Null pointers" in last\_err`).  
**\[CAUSA RAÍZ\]:** Los 100 hilos provocan el mismo error con el mismo texto. Si `LAST\_ERROR` fuera **global** en lugar de `thread\_local`, el chequeo positivo pasaría igual.

- El chequeo negativo (limpiar y leer vacío) sólo detecta la carrera por azar, con una ventana de microsegundos. 

- Aparte, si `get\_last\_error\_string()` devuelve un `\*const c\_char` hacia el `CString` del TLS, ese puntero queda colgando si el mismo hilo hace otra llamada FFI que sobrescribe o limpia el error antes de la copia. "Copia inmediata" es sólo una convención, no una garantía de la API. 

- Respondiendo la pregunta 3 del prompt: no, `thread\_local!` por sí solo no previene todos los UAF. Riesgos abiertos a verificar en el código: puntero devuelto que sobrevive a la siguiente llamada, destructores de TLS al descargar la DLL en Windows, e hilos migrados por runtimes asíncronos. 

**\[FIX\]:**

python

```
`\# Test: mensaje unico por hilo (p.ej. usando un parametro invalido cuyo valor se embebe en el mensaje),`

`\# barrera de sincronizacion, y cada hilo exige leer SU propio id.`

`barrier = threading.Barrier(100)`

`\# ... provocar error con tag=thread\_id; barrier.wait(); assert f"\{thread\_id\}" in msg`
```

rust

```
`// API sin punteros vivos: el llamador aporta el buffer`

`\#\[no\_mangle\] pub extern "C" fn polydim\_rust\_last\_error\_copy\_v817(buf:\*mut c\_char, cap:usize)-\>usize \{ /\* copia y devuelve len \*/ \}`
```


**\[BREACH-09\]: MEDIUM**  
**\[MODULE & LOCATION\]:** `test\_3` Caso C. Axioma 0.2.4 vs tests.  
**\[CAUSA RAÍZ\]:** (verificado) Las dos caras `(0,1,4)` y `(0,3,4)` usan la arista `(0,4)`, que **no está** en `edges\_torus`. No es un complejo simplicial válido, porque falta la propiedad de clausura. Además no es un toro: son 6 vértices y 9 aristas, un prisma. El test sólo exige `beta\_1 \> 0`, así que pasa aunque el kernel ignore silenciosamente el borde faltante. El axioma 0.2.4 dice `beta\_1 = 1` mientras los tests demuestran `beta\_1 = 0`; es una inconsistencia documental.  
**\[FIX\]:**

python

```
`def validate\_complex(edges, faces):`

`    E = \{tuple(sorted(e)) for e in edges\}`

`    for a,b,c in faces:`

`        for p in ((a,b),(b,c),(a,c)):`

`            assert tuple(sorted(p)) in E, f"cara \{(a,b,c)\} usa arista ausente \{p\}"`
```

El kernel debe devolver error ante bordes faltantes, no un Betti. Para certificar, sumar un caso con respuesta conocida, por ejemplo un triángulo relleno (`beta\_1=0`) y un ciclo de 4 vértices sin cara (`beta\_1=1`). Con rango en flotante hay riesgo de umbral: para certificar conviene rango exacto sobre Q o Z/2.


**\[BREACH-10\]: MEDIUM**  
**\[MODULE & LOCATION\]:** `test\_1`, `test\_9`. Guía: "m\_req = 1215.73 \< 1536".  
**\[CAUSA RAÍZ\]:**

- El test 1 usa un **subespacio lineal** de dimensión 16 con 100 puntos. Su reach es infinito, así que no ejercita la cota sobre una variedad curva con `tau \>= 0.5`. El resultado empírico de 4950 secantes no certifica la variedad completa. 

- El test 9 ingresa `volume=100` y `reach=0.5` como constantes inventadas, no medidas. 

- (verificado) Con estos parámetros el corchete de la fórmula del prompt da entre 2352 y 3273 (para d entre 12 y 20). Llegar a 1215.73 exige `C` entre 0.37 y 0.52. La constante universal de la cota no está fijada; con `C` libre, la factibilidad es un artefacto de calibración, no un teorema. 

- Corrección: la fórmula del prompt pone `ln(1/rho)` aditivo. En Baraniuk–Wakin, según recuerdo, aparece como factor multiplicativo con `K`. Verificarlo contra el artículo antes de usarlo como cota. 

- Two-NN con 200 puntos y tolerancia de 5 sobre 12 (42%) es muy laxa. 

**\[FIX\]:** Reportar `m\_req` como función de `C` con un rango honesto, documentar que es una cota suficiente y no necesaria, y estimar `tau` y `V` empíricamente. Usar además una variedad curva de prueba, por ejemplo una espiral o un toro incrustado, con distorsión medida sobre muchas realizaciones de la proyección.


**Hallazgos menores (LOW)**

- **BREACH-11:** `np.random.seed(thread\_id\*777 + int(time.time()))` reinicia el generador **global** desde 100 hilos. Deja la ejecución no reproducible. Fix: `rng = np.random.default\_rng(\[thread\_id, SEED\])` por hilo. 

- **BREACH-12:** "Cero memory leak" del Sabueso 3 sólo comprueba `ret == 0`. No hay medición de RSS. Fix: `psutil.Process().memory\_info().rss` antes y después de las 50 iteraciones, con tolerancia fija. En Windows, usar además `tracemalloc` para el lado Python. 

- **BREACH-13:** En `test\_10`, `cosh(U) \>= 1` en cada entrada, por lo que `rms \>= 1` siempre. El aserto `rms \> 0` no puede fallar, y el "RMS = 1.0005" indica `U` casi nulo. Fix: asertar sobre la salida normalizada (`||M\_out||\_F / sqrt(N) == 1 ± tol`). Además, la normalización escalar no ortogonaliza: es la refutación AuON del axioma 0.2.6. No presentarla como sustituto del polar. 

- **BREACH-14:** Documentación inconsistente: el docstring de la suite dice "8/8", la ejecución es 10/10. El fuzz declara "SILICIO BLINDADO" y la guía dice "100% thread-safe", pero la evidencia no lo respalda. 

- **BREACH-15:** Los tests comparan sólo Rust contra C++. Si ambos comparten la fórmula (como en BREACH-05), coinciden en el error. Fix: referencia mpmath en los casos de borde. 

- **BREACH-16:** `-mfma` hace que C++ contraiga `a\*b+c`, y Rust no lo hace, por lo que hay diferencias de 1 ulp. TwoSum y Neumaier (sólo sumas) no se rompen sin `-ffast-math`, pero el `\#pragma omp reduction` cambia el orden de suma según el número de hilos. Documentar que la paridad es a tolerancia, no bit a bit.

