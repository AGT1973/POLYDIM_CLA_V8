Esta es la 3er ronda del dia de hoy. realmente no entiendo, entre los archivos no llegan a 2000 lineas. como puede ser que no encuentres todos los errores en casi seis meses de 3 entregas diarias los 7 dias de la semana. Y tengamos en cuenta el que se apura en darme respuestas pobres y no profundas sos vos. Parece que estas apurado y me das para solucionarlo 10 items. Yo voy rehago el codigo, lo pruebo y vuelvo. Luego encuentras que aun hay cosas mal que no te habias dado cuenta antes, voy hago mi parte y asi de lunes a domingo en 2 y 3 veces a veces 4. quien hace un trabajo por la mitad? como puede ser mas de 600 interacciones no tengamos terminado algo de ~1000 a 2000 lineas solo. poco en rust, muy poco en python y poco en cpp . ho es un sistemas de 50 000 SoS BULDOG muerde hasta el hueso. no quiero volver 600 veces mas. quiero que termines de darme 2000 lineas. solo menos de 2000 perfectas 

Sí. Esta vez había que cambiar el método, no seguir haciendo “diez hallazgos y a casa”.

Revisé **todo el ZIP**, no una muestra. El código ejecutable efectivo son **852 líneas**:

- C++: 180 

- Rust: 81 

- Triton/Python: 60 

- Orquestador Python: 98 

- Hardware probe: 202 

- Tests: 231 

El `02\_ALL\_SOURCE\_SCRIPTS\_MONOLITH.md` de 700 líneas es una **copia exacta** de los cinco fuentes principales; lo comparé bloque por bloque y coincide. O sea: no estamos ante un sistema de 50.000 líneas. Precisamente por eso corresponde una auditoría casi línea-por-línea.

Y encontré algo más importante que “otro bug”: **V800 todavía no implementa gran parte de la arquitectura que afirma implementar**.

No ejecuté el PE/DLL de Windows directamente en este entorno. Sí hice tres cosas verificables: inspección PE de las DLL entregadas, compilación de la **misma fuente C++** en Linux eliminando solamente `\_\_declspec(dllexport)`, y pruebas adversariales + ASan/UBSan sobre esa reproducción.

## Resultado ejecutivo: cuatro bloqueadores estructurales

Antes del inventario completo, estos son los cuatro que impiden que yo considere V800 cerrable:

**BLOQUEADOR A — La operación matemática implementada no es la operación matemática declarada.**

`kernel\_cpp\_v800.cpp.txt:120-163` calcula:

Yij=Xij+UijVijY\_\{ij\}=X\_\{ij\}+U\_\{ij\}V\_\{ij\} 

No implementa:

- Rodrigues rank-2; 

- geodésica sobre SD−1S^\{D-1\}; 

- proyección tangencial; 

- normalización; 

- preservación de ∥y∥2=1\\|y\\|\_2=1; 

- reducción global de productos internos; 

- Cayley-SMW; 

- resolución 2K×2K2K\\times2K. 

De hecho, el propio test `test\_v800\_redteam\_adversarial.py:128-134` considera correcta exactamente la fórmula elemental `0.5 + 0.25\*0.125`.

Esto no es una “pequeña desviación”. Es una **ruptura de contrato matemático**.

**BLOQUEADOR B — PMTP/IPC Zero-Copy no existe en la implementación.**

Hay una estructura llamada `PmtpHeader`, pero no existe:

- `mmap`; 

- `CreateFileMapping`; 

- `MapViewOfFile`; 

- slab compartido; 

- handles/offsets; 

- ring buffer; 

- seqlock funcional; 

- RCU; 

- generación; 

- `WakeByAddress...`; 

- `FUTEX\_WAKE`; 

- transporte interproceso. 

La DLL C++ entregada importa `WaitOnAddress`, pero la tabla PE no muestra ninguna API de memoria compartida. Eso confirma que no hay un subsistema PMTP implementado.

**BLOQUEADOR C — El FFI Python permite corrupción nativa real.**

No verifica `dtype`, `ndim`, `writeable`, tamaño de buffer ni aliasing antes de convertir arrays NumPy en `double\*`.

Lo reproduje con ASan: pasar un `float32\[1,1\]` a la función C++ que espera `double\*` produce un **stack-buffer-overflow real en `kernel\_cpp\_v800.cpp.txt:141`**.

Eso ya no es una discusión teórica.

**BLOQUEADOR D — La suite 7/7 no certifica el sistema.**

Hay tests que:

- pasan aunque no haya GPU; 

- convierten cualquier excepción en PASS; 

- no verifican toda la salida; 

- no ejecutan el kernel en el test de no-contigüidad; 

- no comprueban el swap de punteros; 

- no comprueban overflow finito; 

- no prueban PMTP; 

- no prueban concurrencia; 

- no prueban el FFI hostil. 

Por tanto, el certificado `7/7 PASS` no puede utilizarse como criterio de cierre.


# PASS 1 — Aniquilación asintótica

## 1. La complejidad no es O(D²), pero el tamaño físico sí es brutal

Para:

D=107,K=512D=10^7,\\quad K=512 

hay:

DK=5.12×109D K = 5.12\\times10^9 

doubles.

Un tensor ocupa:

5.12×109×8=40.96 GB5.12\\times10^9\\times8=40.96\\text\{ GB\} 

Cuatro buffers `X,U,V,Y`:

163.84 GB=152.59 GiB163.84\\text\{ GB\}=152.59\\text\{ GiB\} 

La operación C++ mueve aproximadamente 163.84 GB por pasada sólo contando:

- 3 lecturas; 

- 1 escritura. 

No hay `O(D²)`, y eso es bueno. Pero tampoco hay ningún mecanismo que permita ejecutar el problema completo en una GPU convencional sin particionarlo.

### Solución

El contrato físico debe abandonar “D=10^7” como requisito de **un único buffer residente**.

Usar:

D=Dglobal,Dtile≪DD = D\_\{\\text\{global\}\},\\qquad D\_\{\\text\{tile\}\}\\ll D 

y procesar bloques por streaming/sharding.

El número de elementos debe calcularse antes de crear cualquier buffer:

```
`elements = d \* k`

`bytes\_per\_tensor = elements \* 8`
```

con Python `int`, no `np.uint64`.


## 2. `np.uint64` realmente puede desbordar en `PolydimSlabAllocator`

`polydim\_v800\_monolito.py:15`

```
`self.bytes\_len = int(np.uint64(d) \* np.uint64(k) \* np.uint64(8))`
```

Esto no “previene overflow”.

Probé la aritmética directamente:

```
`np.uint64(2\*\*63) \* np.uint64(8)`
```

produce `0` por wrapping de `uint64`, con warning.

### Solución

```
`elements = int(d) \* int(k)`

`if elements \< 0:`

`    raise ValueError("negative element count")`


`bytes\_len = elements \* np.dtype(np.float64).itemsize`


`if elements \> UINT64\_MAX // np.dtype(np.float64).itemsize:`

`    raise OverflowError("tensor size exceeds uint64")`
```

Y además debe existir un límite físico explícito.


## 3. El índice C++ puede desbordar para dimensiones no restringidas

`kernel\_cpp\_v800.cpp.txt:138-140`

```
`int64\_t idx = i \* K + j;`
```

Sólo se valida:

```
`K \<= 512`
```

No se valida:

```
`D\*K \<= INT64\_MAX`
```

Para el D=10^7 objetivo actual no ocurre. Para el contrato que expone la función, sí puede ocurrir.

### Solución

```
`if (D \<= 0 || K \<= 0 || K \> MAX\_K\_TILED)`

`    return ERR\_BAD\_DIM;`


`if (static\_cast\<uint64\_t\>(D) \>`

`    std::numeric\_limits\<uint64\_t\>::max() /`

`    static\_cast\<uint64\_t\>(K))`

`    return ERR\_SIZE\_OVERFLOW;`


`const uint64\_t elements =`

`    static\_cast\<uint64\_t\>(D) \* static\_cast\<uint64\_t\>(K);`
```

Mejor todavía: fijar un máximo arquitectónico explícito para D.


## 4. “Zero heap allocation” no significa lo que dice el README

El kernel no hace `new`, correcto.

Pero entra en:

```
`\#pragma omp parallel`
```

y depende de `libgomp`, cuyos runtimes mantienen estructuras internas.

Por tanto, “zero heap allocation” sólo puede significar:

> no hay asignación explícita de buffers del algoritmo dentro del cuerpo del kernel.

No “cero asignaciones del camino de ejecución”.


# PASS 2 — Concurrency Bloodbath

Acá aparecieron algunas de las fallas más claras.

## 5. `PmtpHeader` no es PMTP

`kernel\_cpp\_v800.cpp.txt:38-44`

```
`struct alignas(CACHE\_LINE\_SIZE) PmtpHeader \{`

`    std::atomic\<uint64\_t\> sequence\{0\};`

`    std::atomic\<uint64\_t\> owner\_pid\{0\};`

`    std::atomic\<uint64\_t\> monotonic\_start\_ns\{0\};`

`    char \_pad\[CACHE\_LINE\_SIZE - 24\];`

`\};`
```

La estructura existe.

**El protocolo no.**

No hay lector, escritor, publicación, adquisición, generación, offsets ni ownership.

Además, `PmtpHeader`, `ThreadScratchpad` y `pmtp\_store\_release()` no son usados por el kernel.

### Solución

No llamar a esto PMTP hasta implementar realmente:

```
`shared mapping`

`      ↓`

`header`

`      ↓`

`slot/generation`

`      ↓`

`tensor descriptor`

`      ↓`

`publish`

`      ↓`

`wait`

`      ↓`

`acquire`

`      ↓`

`release/recycle`
```


## 6. Un puntero no es un handle IPC

Esto es arquitectónicamente fundamental.

Un `double\*` es una dirección virtual **del proceso actual**.

Por tanto:

```
`process A:`

`0x7F0012340000`
```

no puede transmitirse a proceso B y suponerse válido.

El protocolo debe intercambiar algo equivalente a:

```
`struct PmtpTensorRefV1 \{`

`    uint64\_t slab\_id;`

`    uint64\_t offset;`

`    uint64\_t bytes;`

`    uint32\_t generation;`

`    uint32\_t flags;`

`\};`
```

El consumidor obtiene el mapping y reconstruye:

```
`mapping\_base + offset`
```

Nunca recibe el puntero crudo como identificador global.


## 7. El futex Linux está mal para 64 bits

`kernel\_cpp\_v800.cpp.txt:174-176`

```
`int\* futex\_addr = reinterpret\_cast\<int\*\>(addr);`

`syscall(`

`    SYS\_futex,`

`    futex\_addr,`

`    FUTEX\_WAIT\_PRIVATE,`

`    static\_cast\<int\>(expected\_val),`

`    &ts,`

`    nullptr,`

`    0`

`);`
```

Esto rompe dos cosas.

### Primera: un futex Linux es de 32 bits

La interfaz futex usa una palabra de 32 bits incluso en sistemas de 64 bits. 

Vos tenés:

```
`std::atomic\<uint64\_t\>`
```

y después:

```
`static\_cast\<int\>(expected\_val)`
```

Se pierden 32 bits.

### Segunda: `FUTEX\_WAIT\_PRIVATE`

Linux documenta `FUTEX\_PRIVATE\_FLAG` como sincronización **entre hilos del mismo proceso**, no entre procesos. Para compartir entre procesos el futex debe residir en memoria compartida y usar las operaciones shared, no `\_PRIVATE`. 

### Solución

Usar un wait-word de 32 bits:

```
`alignas(4) uint32\_t wait\_word;`
```

y para IPC:

```
`SYS\_futex(..., FUTEX\_WAIT, ...)`
```

más:

```
`SYS\_futex(..., FUTEX\_WAKE, ...)`
```

y el shared mapping real.


## 8. Falta completamente el wake

El DLL exporta:

```
`polydim\_wait\_on\_address\_v800`
```

pero no hay función equivalente:

```
`WakeByAddressSingle`

`WakeByAddressAll`

`FUTEX\_WAKE`
```

Microsoft documenta explícitamente que `WaitOnAddress` retorna cuando el valor cambia y el modificador llama a `WakeByAddressSingle`/`WakeByAddressAll`; sin wake, con timeout, el hilo simplemente espera hasta que expire. 

### Solución

Implementar ambos lados:

```
`polydim\_wait...`

`polydim\_wake\_one...`

`polydim\_wake\_all...`
```

y en Linux `FUTEX\_WAIT` + `FUTEX\_WAKE`.


## 9. No existe realmente un seqlock

La documentación afirma:

```
`Seqlock + atomic\_signal\_fence + RCU`
```

El código no contiene:

```
`std::atomic\_signal\_fence`
```

ni:

```
`epoch`

`RCU`

`reader retry loop`

`odd/even sequence protocol`
```

Lo único que existe es:

```
`ptr.store(val, std::memory\_order\_release);`
```

y ni siquiera se usa.

### Solución

Un seqlock mínimo real necesita algo conceptualmente así:

```
`// writer`

`seq.fetch\_add(1, std::memory\_order\_relaxed); // odd`

`publish\_data();`

`seq.store(next\_even, std::memory\_order\_release);`


`// reader`

`do \{`

`    s1 = seq.load(std::memory\_order\_acquire);`

`    if (s1 & 1) continue;`


`    read\_data();`


`    s2 = seq.load(std::memory\_order\_acquire);`

`\} while (s1 != s2);`
```

Y para PMTP faltan además ciclo de vida y reclamación del slab.


## 10. El `PmtpHeader` C++ tampoco es un ABI compartido estable

C++:

```
`alignas(128)`

`std::atomic\<uint64\_t\>`
```

Rust:

```
`\#\[repr(C, align(8))\]`

`pub struct ...`
```

No es la misma alineación.

C++ exige 128; Rust declara 8.

Esto importa mucho si realmente se pretende que ambos lenguajes interpreten la misma región compartida.

Además, meter `std::atomic\<uint64\_t\>` directamente en memoria mapeada cruza un problema de ciclo de vida del objeto C++, no sólo de layout.

### Solución

El header compartido debe ser **datos POD estables**, por ejemplo:

```
`struct alignas(64) PmtpSharedHeaderV1 \{`

`    uint64\_t sequence;`

`    uint64\_t generation;`

`    uint64\_t slab\_id;`

`    uint64\_t bytes;`

`    uint32\_t state;`

`    uint32\_t producer;`

`    uint8\_t reserved\[...\];`

`\};`
```

Las operaciones atómicas se hacen sobre esos campos, no se usa el objeto `std::atomic` como representación persistente de IPC.


## 11. `ThreadScratchpad` no arregla nada porque no se usa

`kernel\_cpp\_v800.cpp.txt:30-36`

Está perfectamente acolchado.

Pero ningún hilo crea ni usa un `ThreadScratchpad`.

Por tanto el “fix false sharing” es decorativo.

### Solución

O se elimina, o se usa realmente:

```
`ThreadScratchpad\* scratch =`

`    per\_thread\_scratch(thread\_id);`
```

Actualmente no aporta nada.


# PASS 3 — Numerical Torture

Acá hice las reproducciones más contundentes.

## 12. FTZ/DAZ rompe la preservación de subnormales

`kernel\_cpp\_v800.cpp.txt:57-60`

```
`\_mm\_setcsr(original\_mxcsr | 0x8040);`
```

Eso activa:

- DAZ; 

- FTZ. 

Yo ejecuté el mismo kernel con:

```
`X = 0`

`U = 1e-308`

`V = 1`
```

y obtuve:

```
`ret = 0`

`Y = 0`
```

Es decir, la entrada subnormal fue tratada como cero.

No es una hipótesis.

### Solución

Separar modos:

```
`STRICT\_IEEE`

`PERFORMANCE\_FTZ`
```

El modo certificado debe **no modificar** el modo subnormal.

Si querés medir rendimiento con FTZ, perfecto: que sea un modo explícitamente no equivalente al modo matemático certificado.


## 13. El trap de NaN no detecta overflow generado por entradas finitas

Este es importante.

La implementación comprueba:

```
`isnan(x)`

`isinf(x)`
```

pero sólo de las **entradas**.

Probé:

```
`x = 1`

`u = 1e308`

`v = 1e308`
```

Resultado reproducido:

```
`ret = 0`

`Y = NaN`
```

Eso viola directamente el contrato de “no dejar pasar contaminación numérica”.

### Solución

La validación debe comprobar el resultado candidato.

Para la operación actual:

```
`double y = std::fma(u, v, x);`


`if (!std::isfinite(y))`

`    return ERR\_NUMERICAL\_OVERFLOW;`
```

Pero para el algoritmo geométrico real esa lógica deberá aplicarse al resultado matemático correspondiente.


## 14. Con NaN la salida queda contaminada antes del error

Probé:

```
`U = NaN`
```

y el kernel devuelve:

```
`ret = -99`

`Y = NaN`
```

Es decir:

1. escribe salida contaminada; 

2. recién después informa el error. 

### Solución

Dos pasadas en modo certificado:

**Pass 1:** validación completa.

**Pass 2:** escritura.

Eso cuesta una lectura adicional, pero convierte la semántica en:

```
`error =\> no se publicó ningún resultado`
```

Para un protocolo de alta integridad, es preferible a dejar salida parcial.


## 15. `fma\_two\_sum()` no es un guardián mágico

`kernel\_cpp\_v800.cpp.txt:103-112`.

La transformación puede ser válida bajo determinadas condiciones de IEEE-754, pero no arregla:

- overflow; 

- underflow; 

- FTZ; 

- DAZ; 

- NaN; 

- infinidades; 

- aliasing; 

- compilación `fast-math`. 

Por ejemplo, el `TwoProd` de fallback en `:89-100` tampoco es una identidad universal bajo underflow/subnormales/overflow.


## 16. Lo más peligroso: `-ffast-math` rompe el poison trap

Esto sí lo reproduje.

Compilé la misma fuente exacta con:

```
`-O3 -ffast-math -mfma`
```

y probé:

```
`NaN input`

`Inf input`

`1e308 \* 1e308`
```

En los tres casos:

```
`ret = 0`
```

El ensamblado además queda vectorizado.

Es exactamente la clase de degradación que tu mandato pedía buscar.

### Solución obligatoria

En el fuente:

```
`\#if defined(\_\_FAST\_MATH\_\_)`

`\#error "POLYDIM certified build forbids -ffast-math"`

`\#endif`
```

Y CI debe rechazar el build si `\_\_FAST\_MATH\_\_` está definido.

Además, el build reproducible debe fijar:

```
`-fno-fast-math`

`-ffp-contract=off`
```

y documentar la variante CPU concreta.


## 17. El README tiene dos contratos de compilación distintos

`readme\_first.md:44`

```
`-ffp-contract=off -fno-fast-math`
```

Pero `01\_README\_THEORY\_AND\_AUDIT\_DEMANDS.md:57`

```
`-O3 -fopenmp -mfma -mavx2`
```

sin `-fno-fast-math`.

No se puede tener una certificación matemática y dos recipes diferentes.

### Solución

Un solo build manifest:

```
`build\_v800.json`
```

que contenga:

```
`compiler`

`version`

`target`

`flags`

`ISA`

`git/source hash`

`ABI version`

`numeric mode`
```


# PASS 4 — FFI Abyss

## 18. Este es un bug P0: Python no comprueba `dtype`

`polydim\_v800\_monolito.py:57-64`

Comprueba:

```
`arr.flags.c\_contiguous`

`arr.flags.aligned`
```

pero no:

```
`arr.dtype == np.float64`
```

Eso permite esto:

```
`np.ones((1,1), dtype=np.float32)`
```

entrar como:

```
`double\*`
```

Yo lo pasé por ASan.

Resultado:

```
`AddressSanitizer: stack-buffer-overflow`

`READ of size 8`

`kernel\_test.cpp:141`
```

Esto es una violación de memoria **demostrada**.

### Solución

Antes de cualquier `.ctypes.data\_as()`:

```
`def \_check\_tensor(arr, name, writable=False):`

`    if not isinstance(arr, np.ndarray):`

`        raise TypeError(f"\{name\}: expected numpy.ndarray")`

`    if arr.ndim != 2:`

`        raise ValueError(f"\{name\}: expected 2D tensor")`

`    if arr.dtype != np.float64:`

`        raise TypeError(f"\{name\}: expected float64")`

`    if not arr.flags.c\_contiguous:`

`        raise ValueError(f"\{name\}: C-contiguous required")`

`    if not arr.flags.aligned:`

`        raise ValueError(f"\{name\}: naturally aligned required")`

`    if writable and not arr.flags.writeable:`

`        raise ValueError(f"\{name\}: writable buffer required")`
```


## 19. Se acepta cualquier `ndim`

El código hace:

```
`d = x.shape\[0\]`

`k = x.shape\[1\]`
```

pero no exige:

```
`x.ndim == 2`
```

Probé un:

```
`shape = (1,1,4)`
```

y fue aceptado.

El kernel procesa sólo los primeros `D\*K` elementos y deja el resto intacto.

Eso no es “shape correct”; es **aceptación silenciosa de una topología diferente**.


## 20. `Y\_out` puede ser read-only

Python no comprueba:

```
`y\_out.flags.writeable`
```

Puede pasar un NumPy array de sólo lectura.

El C++ no conoce ese contrato y escribe de todos modos.

### Solución

Verificación obligatoria:

```
`if not y\_out.flags.writeable:`

`    raise ValueError("Y\_out must be writable")`
```


## 21. `\_\_restrict` y aliasing son incompatibles con el wrapper actual

C++:

```
`double\* \_\_restrict X,`

`double\* \_\_restrict U,`

`double\* \_\_restrict V,`

`double\* \_\_restrict Y\_out`
```

Python nunca comprueba que sean disjuntos.

Por tanto:

```
`Y = X`
```

es un contrato incompatible con `restrict`.

### Solución

Elegir una de dos:

**Opción A:** prohibir alias.

**Opción B:** eliminar `\_\_restrict` y definir formalmente qué aliasing se permite.

Para un futuro kernel geométrico, prefiero:

```
`Y == X        permitido, si la operación puede hacerse in-place`

`Y overlaps U  prohibido`

`Y overlaps V  prohibido`

`U overlaps V  prohibido`
```

y validarlo.


## 22. El supuesto “Python protege la llamada” tampoco vale en concurrencia

`ctypes.CDLL` libera el GIL durante llamadas a bibliotecas nativas. La documentación de Python lo especifica. 

Eso significa que mientras C++ procesa:

```
`X/U/V/Y`
```

otra hebra Python puede modificar los mismos buffers si el programa lo permite.

Entonces:

```
`thread A → C++ lee X`

`thread B → NumPy modifica X`
```

genera una condición de carrera sobre memoria nativa.

### Solución

El objeto que posee el tensor debe establecer una política de ownership:

```
`BORROWED\_IMMUTABLE`

`BORROWED\_MUTABLE`

`OWNED`

`SHARED\_IPC`
```

y el kernel certificado no puede aceptar un buffer mutable compartido arbitrariamente.


## 23. El guardián Rust no está conectado al camino real

Existe:

```
`polydim\_validate\_tensor\_v800`
```

pero `PolydimV800Kernel.execute\_cayley\_smw()` nunca lo llama.

Por tanto, el “guard” existe en una DLL pero no protege al kernel.

Eso es exactamente el tipo de protección fantasma que un red-team debe eliminar.

### Solución

El path debe ser:

```
`Python`

`   ↓`

`descriptor validation`

`   ↓`

`Rust/native validator`

`   ↓`

`C++ kernel`
```

o simplificar:

```
`Python strict validation`

`   ↓`

`C++ descriptor validation`

`   ↓`

`kernel`
```

pero no dos guardianes desconectados.


## 24. `catch\_unwind` no convierte un puntero inválido en seguro

Rust:

```
`let result = catch\_unwind(|| \{`

`    unsafe \{`

`        let inner\_a = \*ptr\_a;`
```

`catch\_unwind` captura **panic**, no:

- segmentation fault; 

- invalid memory access; 

- UB; 

- use-after-free. 

Por tanto la descripción:

```
`"Anti-panic FFI firewall"`
```

es correcta literalmente, pero no equivale a:

```
`memory safety firewall`
```

### Solución

Nunca dereferenciar hasta disponer de un contrato de memoria explícito:

```
`ptr + len + alignment + ownership`
```

Y aun así recordar que un `\*mut T` externo no puede validarse completamente sólo con aritmética.


## 25. El Rust guard comprueba el puntero equivocado

`kernel\_rust\_v800.rs.txt:55-76`.

Comprueba:

```
`inner\_a % 8`

`inner\_b % 8`
```

pero no comprueba la alineación de:

```
`ptr\_a`

`ptr\_b`
```

antes de hacer:

```
`\*ptr\_a`

`\*ptr\_b`
```

La dereferencia sucede antes de que la validación del contenido sea útil.


## 26. El “Weiszfeld swap” casi no prueba nada

La función:

```
`polydim\_weiszfeld\_swap\_v800`
```

sólo intercambia dos punteros.

No verifica:

- longitud; 

- memoria; 

- ownership; 

- contenido; 

- capacidad; 

- vida útil; 

- overlap; 

- provenance. 

El test sólo hace:

```
`ret\_swap == 0`
```

No comprueba que realmente haya ocurrido el swap.


# PASS 5 — SOTA Evolution / Matemática

## 27. `polydim\_higham\_bound\_v800()` no es una cota de Higham demostrada para este kernel

Rust:

```
`let eps = f64::EPSILON / 2.0;`

`let log\_d = (d as f64).log2().ceil();`

`50.0 \* log\_d \* eps`
```

El problema no es que la fórmula “pueda mejorarse”.

El problema es que **no está derivada del algoritmo implementado**.

La cota no depende de:

- K; 

- condición de los datos; 

- productos internos; 

- normalización; 

- número real de operaciones; 

- algoritmo de reducción; 

- overflow; 

- underflow; 

- compensación; 

- composición geométrica. 

De hecho, el kernel actual ni siquiera hace la reducción cuya cota dependería de `D`.

### Solución

Eliminar la etiqueta “Higham bound” hasta derivar una cota real.

Para una suma ingenua, por ejemplo, aparecería una estructura tipo:

γn=nu1−nu\\gamma\_n=\\frac\{nu\}\{1-nu\} 

bajo hipótesis concretas.

Para Neumaier/pairwise/compensated reduction la cota debe derivarse para **ese algoritmo concreto**.


## 28. La esfera SD−1S^\{D-1\} no aparece en el código

No existe ninguna rutina que haga:

```
`norm`

`normalize`

`project tangent`
```

ni una certificación:

∣∥y∥22−1∣≤ϵ|\\|y\\|\_2^2 - 1| \\le \\epsilon 

### Prueba trivial

Con el kernel actual:

```
`x = 1`

`u = 1`

`v = 1`
```

tenés:

```
`y = 2`
```

por tanto:

∥y∥=2≠1\\|y\\|=2\\neq1 

Así que el supuesto “manifold invariant” no está implementado.


## 29. Rodrigues rank-2 no está implementado

No aparecen en ninguna de las 852 líneas ejecutables:

```
`Rodrigues`

`theta`

`sin(theta)`

`cos(theta)`

`versin`

`tangent basis`
```

La única multiplicación geométricamente irrelevante es:

```
`u\_val \* v\_val`
```

Por tanto toda la sección de análisis de cancelación para θ→0\\theta\\to0 todavía es un análisis de una operación que el programa **no ejecuta**.


## 30. No existe la proyección tangencial

No existe:

v⊥=v−(u⊤v)uv\_\\perp = v-(u^\\top v)u 

ni tampoco una proyección de un vector arbitrario al espacio tangente.


## 31. No existe reducción global

El prompt habla de:

> global reduction de productos internos por hilo + Neumaier.

El C++ no hace ningún:

```
`dot(X,U)`

`dot(X,V)`

`norm(X)`
```

Sólo recorre elementos individualmente.

Esto hace que toda la arquitectura de `K=512` y la supuesta matriz 2K×2K2K\\times2K no exista todavía.


## 32. No existe SORM

Busqué `SORM`.

No aparece en el código.

No hay matriz reducida, factorización ni resolución de sistema equivalente.


## 33. No existe Betti-1

No hay:

```
`Betti`

`homology`

`simplex`

`boundary matrix`

`persistent homology`
```

en Rust, C++, Python o tests.

Y hay un problema aún más profundo: **un tensor D×KD\\times K por sí solo no define una homología β1\\beta\_1**.

Para certificar β1\\beta\_1 tenés que definir qué complejo topológico estás construyendo:

```
`puntos`

`↓`

`vecindad / radio`

`↓`

`grafo o complejo`

`↓`

`boundary operators`

`↓`

`homología`

`↓`

`β1`
```

Sin eso, “Rust verifica β1 continuamente” no es una especificación matemática completa.


# Triton

## 34. El kernel GPU tiene el mismo problema matemático

`polydim\_triton\_kernel\_v800.py:35-37`

```
`y\_vals = x\_vals + u\_vals \* v\_vals`
```

Es la misma operación elemental, no Rodrigues.


## 35. Triton no valida shape, dtype ni device de todos los tensores

Sólo:

```
`X.is\_contiguous()`

`U.is\_contiguous()`

`V.is\_contiguous()`

`Y.is\_contiguous()`
```

Pero el kernel usa:

```
`D,K = X.shape`
```

y asume que U/V/Y tienen exactamente el mismo layout lógico.

Podés tener:

```
`X.shape == (D,K)`

`U.shape != (D,K)`
```

y el kernel puede acceder fuera del tensor lógico de U.

### Solución

Exigir:

```
`for a,name in ...:`

`    if a.ndim != 2: ...`

`    if a.shape != X.shape: ...`

`    if a.dtype != torch.float64: ...`

`    if a.device != X.device: ...`
```


## 36. `assert` no es una barrera de producción

```
`assert X.is\_contiguous()`
```

se puede eliminar con:

```
`python -O`
```

### Solución

Excepciones explícitas:

```
`if not X.is\_contiguous():`

`    raise ValueError(...)`
```


## 37. `D` y `K` son `constexpr`

```
`D: tl.constexpr`

`K: tl.constexpr`
```

Esto hace que Triton compile variantes diferentes para diferentes tamaños.

Para una aplicación que procesa dimensiones variables puede provocar una explosión de kernels compilados/cache.

### Solución

Dejar como `constexpr` sólo los parámetros realmente estructurales:

```
`BLOCK\_SIZE\_D`

`BLOCK\_SIZE\_K`
```

y convertir dimensiones lógicas en argumentos runtime cuando corresponda.


# Hardware Probe

Este archivo es otro bloqueador de integración.

## 38. V800 trae un módulo V773

`hardware\_probe.py:4`

```
`POLYDIM V773`
```

y:

```
`polydim\_cpp\_v773.dll`
```

en líneas `42-44`.

No existe esa DLL en el ZIP.


## 39. Busca una función que V800 no exporta

El CPU path hace:

```
`lib.polydim\_gram\_dsyrk`
```

Pero `polydim\_kernel\_v800.dll` exporta sólo:

```
`polydim\_abi\_version`

`polydim\_kernel\_cayley\_smw\_v800`

`polydim\_wait\_on\_address\_v800`
```

La tabla de exportación de la DLL confirma esto.

Por tanto el CPU fallback de `HardwareProbe` no corresponde a la V800 entregada.


## 40. La detección CUDA depende del nombre comercial

```
`torch.cuda.get\_device\_name(0)`
```

y luego:

```
`\['nvidia','tesla','geforce','rtx','a100','h100',...\]`
```

Un dispositivo NVIDIA nuevo cuyo nombre no contenga ninguna de esas cadenas puede quedar mal clasificado.

### Solución

Usar capacidades de backend:

```
`torch.version.cuda`

`torch.version.hip`

`torch.cuda.get\_device\_properties(0)`
```

no listas de marketing.


## 41. `XLA\_FLAGS` no demuestra que exista TPU

`hardware\_probe.py:76-78`

Si existe:

```
`XLA\_FLAGS`
```

devuelve TPU.

Eso es una señal de configuración, no una prueba de dispositivo disponible.


## 42. Los TPU no tienen “8 cores” universalmente

`hardware\_probe.py:113`

```
`\{"cores": 8\}`
```

Es metadata incorrecta como contrato general.


## 43. `rocm-smi` puede bloquear indefinidamente

```
`subprocess.run(...)`
```

no tiene `timeout`.

Un probe de hardware no debería tener un camino potencialmente infinito.

### Solución

```
`subprocess.run(..., timeout=2.0, check=False)`
```


# La suite de tests necesita una reconstrucción

Acá es donde se originó buena parte del problema de las rondas anteriores.

## 44. El test de GPU puede fallar y aun así pasar

`test\_v800\_redteam\_adversarial.py:187-210`

```
`except Exception as e:`

`    self.log\_result(..., True, ...)`
```

Eso significa:

```
`error real -\> PASS`
```

Esto tiene que desaparecer.


## 45. Sin GPU el test pasa

```
`if not torch.cuda.is\_available():`

`    self.log\_result(..., True, ...)`
```

Entonces:

```
`GPU ausente`
```

equivale actualmente a:

```
`GPU verificado`
```

Eso es incorrecto.

### Solución

Tres estados:

```
`PASS`

`FAIL`

`SKIP`
```

Nunca:

```
`SKIP == PASS`
```


## 46. `test\_non\_contiguous\_rejection()` no ejecuta el kernel

Líneas `181-185`.

Hace:

```
`passed = not X\_f.flags.c\_contiguous`
```

Eso no prueba que `execute\_cayley\_smw()` rechace el array.

Es una tautología sobre NumPy.


## 47. El happy path sólo mira `Y\[0,0\]`

Líneas `128-134`.

Si 31.999.999 elementos están corruptos y:

```
`Y\[0,0\] correcto`
```

el test pasa.

### Solución

Comparación completa:

```
`np.testing.assert\_array\_equal(...)`
```

o `assert\_allclose` con una referencia independiente.


## 48. El “ground truth” es el mismo error conceptual del kernel

El test dice:

```
`Y = X + U\*V`
```

y llama eso:

> elementwise 2D Cayley SMW update.

Entonces el test no verifica la matemática declarada; simplemente verifica que el código hace lo mismo que el test espera.

Es circular.


## 49. El test subnormal no comprueba preservación

Sólo:

```
`ret == 0 and not np.isnan(Y\[0,0\])`
```

Una salida completamente incorrecta de ceros pasa.

Esto fue precisamente lo que reproduje con el kernel.


## 50. No se prueba overflow finito

Debe existir obligatoriamente:

```
`1e308 \* 1e308`
```

y comprobar:

```
`must return numerical failure`

`must not publish NaN/Inf output`
```

Hoy devuelve `0`.


## 51. No hay test de aliasing

Debe probarse al menos:

```
`Y == X`

`Y overlaps X`

`Y == U`

`Y overlaps U`
```

y validar explícitamente el contrato.


## 52. No hay test dtype-hostile

Debe existir:

```
`float32`

`float16`

`int32`

`int64`

`bool`

`object`
```

y todos deben ser rechazados antes del FFI.

El caso `float32` hoy ya demostró corrupción bajo ASan.


## 53. No hay test readonly

`Y.flags.writeable=False`.

Debe ser rechazado en Python antes de C++.


## 54. No hay tests de concurrencia

Nada cubre:

```
`2 writers`

`writer + reader`

`multiple processes`

`sequence wrap`

`wake lost`

`stale generation`

`slab reuse`
```


## 55. No hay TSAN/ASAN/UBSAN como parte de la certificación

Para una arquitectura que explícitamente promete:

```
`memory-safe`

`FFI-safe`

`concurrency-safe`
```

esto debería ser obligatorio.


# Dependencias / distribución

## 56. La DLL C++ depende de `libgomp-1.dll`

La inspección PE de:

```
`polydim\_kernel\_v800.dll`
```

muestra dependencia directa de:

```
`libgomp-1.dll`
```

pero esa DLL no está dentro del ZIP.

El test compensa esto con:

```
`E:\\winlibs\_gcc14\_zip\\mingw64\\bin`
```

Eso hace que el entorno de desarrollo del autor sea parte implícita de la ejecución.


## 57. Rust depende de `VCRUNTIME140.dll`

La DLL Rust entregada importa `VCRUNTIME140.dll`.

Eso tampoco forma parte del ZIP.

No es necesariamente incorrecto instalar el runtime por separado, pero entonces la entrega **no es autocontenida**.

### Solución

Un único contrato de distribución:

```
`runtime dependencies`

`version`

`architecture`

`CPU baseline`

`loader policy`
```

y una prueba en una máquina limpia.


## 58. El test tiene rutas absolutas del entorno del desarrollador

```
`E:\\winlibs\_gcc14\_zip\\mingw64\\bin`
```

Eso invalida la idea de “portable”.


# Problemas teóricos fuera del código

Hay además dos afirmaciones del dossier que yo corregiría antes de presentarlas a un tercero.

## 59. La afirmación sobre DPI está sobredicha

El dossier dice esencialmente:

> serializar a JSON/texto destruye necesariamente la información geométrica por DPI.

Eso no es correcto en esa forma.

La desigualdad de procesamiento de datos dice:

I(X;g(Y))≤I(X;Y)I(X;g(Y))\\le I(X;Y) 

pero si la transformación gg es **invertible**, la información mutua puede permanecer igual.

Un `base64` exacto de los bytes originales, por ejemplo, no tiene por qué destruir información. La pérdida aparece cuando hay:

- cuantización; 

- truncamiento; 

- tokenización no invertible; 

- redondeo; 

- compresión con pérdida; 

- límites de precisión. 

Por tanto la tesis correcta sería:

> ciertos límites de serialización/tokenización pueden introducir una transformación no invertible y destruir información geométrica; no JSON per se.

Esto conviene arreglar porque es una afirmación matemática del marco teórico.


## 60. “O(1) tensor transfer” necesita una definición más precisa

Pasar un descriptor:

```
`slab\_id + offset + length`
```

sí puede ser O(1).

Pero eso no significa:

```
`cero coste de memoria`

`cero ancho de banda`

`cero cache misses`

`cero page faults`
```

Significa:

> el descriptor se pasa en tiempo O(1) sin copiar el payload.

Esa formulación es defendible.


# El error de arquitectura más grande

El problema que explica por qué después de meses aparecían más cosas no era sólo “no vimos un if”.

Estábamos auditando una **implementación parcial como si fuera una implementación completa**.

El ZIP actual tiene, en esencia:

```
`Python`

`  ↓`

`ctypes`

`  ↓`

`C++ elemental`

`  ↓`

`Rust con 3 helpers desconectados`

`  ↓`

`Triton elemental`
```

Pero el dossier describe:

```
`Manifold S^(D-1)`

`        ↓`

`Tangent geometry`

`        ↓`

`Rodrigues / Cayley-SMW`

`        ↓`

`Compensated global reduction`

`        ↓`

`PMTP shared memory`

`        ↓`

`Seqlock / generation / ownership`

`        ↓`

`Rust topological guard`

`        ↓`

`heterogeneous dispatch`

`        ↓`

`formal invariants`
```

La segunda arquitectura **no está implementada en las 852 líneas ejecutables**.

Ese es el verdadero punto que había que detectar antes.


# El parche que yo impondría ahora

No haría otros diez parches aislados.

Haría una V801 con un contrato cerrado.

## 1. Nuevo contrato FFI

```
`extern "C" \{`


`struct PolydimTensorViewV1 \{`

`    const void\* data;`

`    uint64\_t bytes;`

`    uint64\_t d;`

`    uint64\_t k;`

`    uint64\_t stride0\_bytes;`

`    uint64\_t stride1\_bytes;`

`    uint32\_t dtype;`

`    uint32\_t flags;`

`\};`


`uint32\_t polydim\_abi\_version\_v1();`


`int32\_t polydim\_kernel\_v1(`

`    const PolydimTensorViewV1\* x,`

`    const PolydimTensorViewV1\* u,`

`    const PolydimTensorViewV1\* v,`

`    PolydimTensorViewV1\* y);`

`\}`
```

Ya no hay:

```
`double\*`

`D`

`K`
```

sin tamaño.


## 2. Descriptor de tensor obligatorio

Python valida:

```
`def validate\_f64\_matrix(a, name, writable=False):`

`    if not isinstance(a, np.ndarray):`

`        raise TypeError(name)`


`    if a.ndim != 2:`

`        raise ValueError(name)`


`    if a.dtype != np.float64:`

`        raise TypeError(name)`


`    if not a.flags.c\_contiguous:`

`        raise ValueError(name)`


`    if not a.flags.aligned:`

`        raise ValueError(name)`


`    if writable and not a.flags.writeable:`

`        raise ValueError(name)`
```

Y además:

```
`if a.shape != x.shape:`

`    raise ValueError(...)`
```


## 3. Eliminar el fake `SlabAllocator`

Dos alternativas válidas:

### modo local

Llamarlo:

```
`NumpyTensorOwner`
```

porque eso es lo que es.

### modo PMTP

Implementar realmente:

```
`SharedSlab`

`  ├── slab\_id`

`  ├── mapping`

`  ├── generation`

`  ├── capacity`

`  └── offsets`
```

No mezclar ambos conceptos.


## 4. PMTP real

Header:

```
`struct alignas(64) PmtpHeaderV1 \{`

`    uint64\_t sequence;`

`    uint64\_t generation;`

`    uint64\_t slab\_id;`

`    uint64\_t payload\_bytes;`

`    uint32\_t state;`

`    uint32\_t flags;`

`    uint8\_t reserved\[24\];`

`\};`
```

Descriptor:

```
`struct PmtpTensorRefV1 \{`

`    uint64\_t slab\_id;`

`    uint64\_t offset;`

`    uint64\_t bytes;`

`    uint32\_t generation;`

`    uint32\_t flags;`

`\};`
```

Linux:

```
`mmap`

`FUTEX\_WAIT`

`FUTEX\_WAKE`
```

Windows:

```
`CreateFileMapping`

`MapViewOfFile`

`WaitOnAddress`

`WakeByAddressAll`
```

La necesidad de una palabra futex de 32 bits y memoria compartida real está documentada en Linux. 


## 5. Numeric contract

El build certificado debe prohibir:

```
`-fast-math`
```

y además:

```
`\#if defined(\_\_FAST\_MATH\_\_)`

`\#error "Certified POLYDIM build forbids fast-math"`

`\#endif`
```

Modo certificado:

```
`strict IEEE`

`no FTZ`

`no DAZ`

`no hidden contraction`
```

Modo benchmark:

```
`FTZ/DAZ allowed`
```

pero no se puede llamar equivalente.


## 6. Validación numérica en dos fases

```
`Pass 1:`

`    validate inputs`

`    validate finite`

`    validate bounds`

`    validate candidate output`


`Pass 2:`

`    publish result`
```

Así:

```
`numerical failure`

`        ↓`

`NO publicación de resultado contaminado`
```


## 7. Matemática correcta

Antes de volver a llamar a la función:

```
`polydim\_kernel\_cayley\_smw\_v800`
```

hay que implementar realmente la transformación declarada.

Como mínimo los invariantes deben ser tests explícitos:

∣∥y∥22−1∣≤ε|\\|y\\|\_2^2-1|\\le \\varepsilon y∈SD−1y\\in S^\{D-1\} 

y, si corresponde al modelo geométrico:

v⊥=v−(u⊤v)uv\_\\perp = v-(u^\\top v)u 

más las propiedades de:

- identidad; 

- inversa; 

- composición; 

- θ→0\\theta\\to0; 

- conservación de norma. 

Hasta que eso exista, yo no llamaría al kernel “Cayley-SMW”.


# La suite de tests de cierre que sustituye a la actual

No 7 tests.

Un cierre serio necesita al menos estas familias:

| **Familia** | **Debe demostrar** |
| :-: | :-: |
| ABI | versión, tamaño, arquitectura |
| FFI dtype | `float32/int32/object/...` rechazados |
| FFI shape | ndim/shape/strides |
| readonly | salida rechazada |
| alias | contrato explícito |
| overflow | finitos que producen overflow detectados |
| NaN | no se publica salida |
| Inf | no se publica salida |
| subnormal | comportamiento exacto documentado |
| FTZ | modo certificado preserva semántica |
| fast-math | build rechazado |
| sphere | norma |
| tangent | ortogonalidad |
| Rodrigues | identidad/inversa/composición |
| high-D | error scaling |
| PMTP | productor/consumidor |
| ABA | generation mismatch |
| IPC | dos procesos |
| wake | wake correcto |
| stale slab | rechazo |
| Rust | invalid pointer cases |
| Triton | full-array correctness |
| CPU/GPU | equivalencia matemática |
| sanitizers | ASan/UBSan |
| threads | TSan |
| hardware | CPU/CUDA/ROCm/TPU |
| clean machine | sin `E:\\...` |


# Y una corrección importante sobre el objetivo de “menos de 2000 líneas”

Esto es perfectamente viable.

De hecho, con la arquitectura correctamente cerrada, **no necesitás 50.000 líneas**.

Yo lo dejaría aproximadamente así:

```
`PMTP ABI + shared memory     ~200`

`C++ numerical kernel        ~400`

`Rust guard                  ~250`

`Python FFI/orchestrator     ~250`

`Triton                      ~180`

`tests                       ~600`

`--------------------------------`

`                            ~1880`
```

Eso sería mucho más sano que seguir agregando funciones “SOTA” desconectadas.

La clave es que cada línea tenga un dueño contractual claro.


# Lo que considero encontrado y cerrado en esta auditoría

No estoy diciendo que “ya está perfecto”. Estoy diciendo algo más útil: **ya tenemos localizado el conjunto de problemas estructurales que impedía que las rondas anteriores realmente cerraran el sistema**.

Los más graves están comprobados experimentalmente:

```
`\[CONFIRMADO\] float32 → C double\* → ASan buffer overflow`

`\[CONFIRMADO\] FTZ/DAZ → subnormal 1e-308 → 0`

`\[CONFIRMADO\] 1e308 \* 1e308 → NaN con return 0`

`\[CONFIRMADO\] -ffast-math → NaN/Inf pasan con return 0`

`\[CONFIRMADO\] PMTP no implementado`

`\[CONFIRMADO\] seqlock no implementado`

`\[CONFIRMADO\] wake no implementado`

`\[CONFIRMADO\] FUTEX\_WAIT\_PRIVATE incompatible con IPC`

`\[CONFIRMADO\] 64-bit atomic reducido a futex int32`

`\[CONFIRMADO\] Rust guard desconectado del kernel`

`\[CONFIRMADO\] V773/V800 mezclados`

`\[CONFIRMADO\] test GPU convierte error en PASS`

`\[CONFIRMADO\] test no-contiguous no llama al kernel`

`\[CONFIRMADO\] tests no verifican la salida completa`

`\[CONFIRMADO\] geometría de esfera ausente`

`\[CONFIRMADO\] Betti-1 ausente`

`\[CONFIRMADO\] Higham bound no deriva del algoritmo`
```

Y hay una conclusión todavía más importante:

> **No conviene que hagas otra vuelta de “reparo estos 10 puntos y te mando V801”.**

Eso nos devolvería exactamente al ciclo que describiste.

La siguiente implementación debería hacerse contra un **contrato cerrado**, donde el kernel, el FFI, PMTP, Rust, Triton y los tests sean partes de la misma especificación. Sólo así tiene sentido intentar llevar estas ~850 líneas ejecutables a menos de 2.000 líneas realmente terminadas, en lugar de seguir acumulando parches.


Voy a aprovechar una corrección de contexto importante: el cuello de botella físico ya no se puede describir como “D=10⁷ no cabe en GPU”. En hardware actual de gama HPC hay aceleradores con 288–372 GB de memoria HBM; cuatro tensores de 40,96 GB ocupan 163,84 GB, así que el problema pasa de “imposible” a “cabe, pero deja poco margen y exige fusión/tileado”. Eso cambia la estrategia SOTA.


La toolchain acaba de detectar un defecto de portabilidad genuino en mi parche: faltaba incluir `\<cfenv\>` para `fegetround/FE\_TONEAREST`. Es justamente el tipo de error que el build estricto debe encontrar antes de que llegue al usuario; lo corrijo y sigo, no lo cuento como “fallo del sistema”.


El bulldog acaba de encontrar otro fallo real antes de cerrar: el Triton V802 tenía una inconsistencia entre la firma del kernel de reducción y sus punteros de entrada, y además usaba offsets que deben forzarse a `int64` para DK\>231D K\>2^\{31\}. También detecté un hueco en `verify\_output\_norm`: una rama no finita podía abortar un bloque sin marcar fallo. Lo cierro ahora; no voy a maquillar esa deuda.


Otro defecto de portabilidad, confirmado: GCC acepta el `strlen` por inclusiones transitivas, pero Clang estricto lo rechazó porque faltaba `\<cstring\>`. Esto no cambia la lógica; sí importa para una entrega industrial multi-toolchain. Lo corrijo y vuelvo a compilar con ambos.




Voy a empaquetar esta ronda como V803, porque ya no es una simple corrección de V802: incorpora el control FPCR/MSVC ARM64 verificado, publicación PMTP con campos atómicos completos, validación previa de salida para evitar resultados parciales, y un contrato de build/provenance reproducible. Lo que no pueda ejecutar aquí quedará marcado como no certificado.







El build hizo exactamente su trabajo: encontró un defecto introducido por mi propia mejora (`PMTP\_BUSY` no estaba declarado públicamente). No lo considero un fallo de tu código ni lo voy a esconder; lo corrijo en el contrato y vuelvo a pasar toda la cadena.


La V803 ya pasa de nuevo sus 11 pruebas, ASan/UBSan y TSAN del PMTP. Ahora estoy haciendo la comprobación que faltaba para evitar una falsa sensación de “solo GCC”: recompilo el mismo C++ con Clang estricto y comparo símbolos/salida antes de empaquetar.


Clang acaba de encontrar una mejora real de portabilidad, no un fallo matemático: `read\_fpcr()` quedaba huérfana en x86 bajo `-Werror`. La arquitectura era correcta pero la compilación industrial multi-compiler no quedaba limpia. La hago condicional por ISA y vuelvo a comparar GCC/Clang.


Encontré además un problema teórico que sí merece entrar en esta entrega: **la transformación actual preserva la esfera, pero no es una geodésica de SD−1S^\{D-1\} para un u,vu,v arbitrario**; sólo lo es cuando el plano de rotación contiene a xx. Eso es una corrección conceptual importante, no un detalle de redacción. El código puede seguir siendo correcto como rotación ortogonal rank-2, pero no debemos venderla como geodésica sin esa condición.


Hay un cuarto hallazgo de coherencia que no voy a dejar para la próxima ronda: el backend Triton todavía hacía `remainder(theta,2π)` aunque CPU ya lo había corregido. Eso habría creado dos matemáticas distintas precisamente en ángulos grandes. Lo unifico y añado un test explícito de ese régimen.



La auditoría del backend GPU encontró una última superficie de corrección que sí puedo cerrar sin inventar: el wrapper Triton permitía `Y.requires\_grad=True` en un leaf, aunque el kernel no implementa backward; eso puede producir semántica autograd falsa. Lo rechazo explícitamente y separo “kernel numérico” de “op diferenciable”.



El siguiente salto SOTA no es añadir más matemática suelta: es cerrar el sistema de build. `enable\_testing()` sin `add\_test()` deja una falsa sensación de cobertura. Voy a hacer que CMake/CTest construya y ejecute los tests reales, que el test sea portable a Windows y que el artefacto Python pueda apuntar al binario que CMake acaba de construir.


El cierre de CMake ya es real: `ctest` construye y ejecuta los tres niveles —C++, PMTP y Python— y los tres pasan. Ahora hago la pasada que suele descubrir bugs que los tests no cubren: análisis estático del compilador y revisión hostil de lifecycle/errores.


Este es el hallazgo estructural más importante de la pasada: el PMTP anterior era shared-memory, pero `publish()` hacía `memcpy`; por definición eso **no era zero-copy** desde el buffer del productor. No voy a conservar esa etiqueta: añado la ruta correcta `begin\_write → escribir directamente en el slab → commit`, y dejo `publish()` como atajo explícitamente “copy”.


La revisión GPU revela otro contrato importante: el CPU ya evita publicar `Y` antes de verificar cuando se pide `verify\_output`, pero Triton lo escribía y recién después lo auditaba. Voy a alinear ambos backends: verificación previa por tiles, temporal acotado al tile y sólo entonces publicación de `Y`.


Hay una aparente inconsistencia en el `nm` que revisé: era el `.so` raíz anterior a la última recompilación, no el recién generado por CMake. Lo voy a reconstruir desde cero antes de considerar cualquier símbolo “faltante”; no voy a convertir un artefacto stale en un falso bug.

Voy a aprovechar una corrección de contexto importante: el cuello de botella físico ya no se puede describir como “D=10⁷ no cabe en GPU”. En hardware actual de gama HPC hay aceleradores con 288–372 GB de memoria HBM; cuatro tensores de 40,96 GB ocupan 163,84 GB, así que el problema pasa de “imposible” a “cabe, pero deja poco margen y exige fusión/tileado”. Eso cambia la estrategia SOTA.


La toolchain acaba de detectar un defecto de portabilidad genuino en mi parche: faltaba incluir `\<cfenv\>` para `fegetround/FE\_TONEAREST`. Es justamente el tipo de error que el build estricto debe encontrar antes de que llegue al usuario; lo corrijo y sigo, no lo cuento como “fallo del sistema”.


El bulldog acaba de encontrar otro fallo real antes de cerrar: el Triton V802 tenía una inconsistencia entre la firma del kernel de reducción y sus punteros de entrada, y además usaba offsets que deben forzarse a `int64` para DK\>231D K\>2^\{31\}. También detecté un hueco en `verify\_output\_norm`: una rama no finita podía abortar un bloque sin marcar fallo. Lo cierro ahora; no voy a maquillar esa deuda.


Otro defecto de portabilidad, confirmado: GCC acepta el `strlen` por inclusiones transitivas, pero Clang estricto lo rechazó porque faltaba `\<cstring\>`. Esto no cambia la lógica; sí importa para una entrega industrial multi-toolchain. Lo corrijo y vuelvo a compilar con ambos.




Voy a empaquetar esta ronda como V803, porque ya no es una simple corrección de V802: incorpora el control FPCR/MSVC ARM64 verificado, publicación PMTP con campos atómicos completos, validación previa de salida para evitar resultados parciales, y un contrato de build/provenance reproducible. Lo que no pueda ejecutar aquí quedará marcado como no certificado.







El build hizo exactamente su trabajo: encontró un defecto introducido por mi propia mejora (`PMTP\_BUSY` no estaba declarado públicamente). No lo considero un fallo de tu código ni lo voy a esconder; lo corrijo en el contrato y vuelvo a pasar toda la cadena.


La V803 ya pasa de nuevo sus 11 pruebas, ASan/UBSan y TSAN del PMTP. Ahora estoy haciendo la comprobación que faltaba para evitar una falsa sensación de “solo GCC”: recompilo el mismo C++ con Clang estricto y comparo símbolos/salida antes de empaquetar.


Clang acaba de encontrar una mejora real de portabilidad, no un fallo matemático: `read\_fpcr()` quedaba huérfana en x86 bajo `-Werror`. La arquitectura era correcta pero la compilación industrial multi-compiler no quedaba limpia. La hago condicional por ISA y vuelvo a comparar GCC/Clang.


Encontré además un problema teórico que sí merece entrar en esta entrega: **la transformación actual preserva la esfera, pero no es una geodésica de SD−1S^\{D-1\} para un u,vu,v arbitrario**; sólo lo es cuando el plano de rotación contiene a xx. Eso es una corrección conceptual importante, no un detalle de redacción. El código puede seguir siendo correcto como rotación ortogonal rank-2, pero no debemos venderla como geodésica sin esa condición.


Hay un cuarto hallazgo de coherencia que no voy a dejar para la próxima ronda: el backend Triton todavía hacía `remainder(theta,2π)` aunque CPU ya lo había corregido. Eso habría creado dos matemáticas distintas precisamente en ángulos grandes. Lo unifico y añado un test explícito de ese régimen.



La auditoría del backend GPU encontró una última superficie de corrección que sí puedo cerrar sin inventar: el wrapper Triton permitía `Y.requires\_grad=True` en un leaf, aunque el kernel no implementa backward; eso puede producir semántica autograd falsa. Lo rechazo explícitamente y separo “kernel numérico” de “op diferenciable”.



El siguiente salto SOTA no es añadir más matemática suelta: es cerrar el sistema de build. `enable\_testing()` sin `add\_test()` deja una falsa sensación de cobertura. Voy a hacer que CMake/CTest construya y ejecute los tests reales, que el test sea portable a Windows y que el artefacto Python pueda apuntar al binario que CMake acaba de construir.


El cierre de CMake ya es real: `ctest` construye y ejecuta los tres niveles —C++, PMTP y Python— y los tres pasan. Ahora hago la pasada que suele descubrir bugs que los tests no cubren: análisis estático del compilador y revisión hostil de lifecycle/errores.


Este es el hallazgo estructural más importante de la pasada: el PMTP anterior era shared-memory, pero `publish()` hacía `memcpy`; por definición eso **no era zero-copy** desde el buffer del productor. No voy a conservar esa etiqueta: añado la ruta correcta `begin\_write → escribir directamente en el slab → commit`, y dejo `publish()` como atajo explícitamente “copy”.


La revisión GPU revela otro contrato importante: el CPU ya evita publicar `Y` antes de verificar cuando se pide `verify\_output`, pero Triton lo escribía y recién después lo auditaba. Voy a alinear ambos backends: verificación previa por tiles, temporal acotado al tile y sólo entonces publicación de `Y`.


Hay una aparente inconsistencia en el `nm` que revisé: era el `.so` raíz anterior a la última recompilación, no el recién generado por CMake. Lo voy a reconstruir desde cero antes de considerar cualquier símbolo “faltante”; no voy a convertir un artefacto stale en un falso bug.

hoy 7:27

auditoria\_externa\_v800.zip

Archivo Zip

lee profundamente, evalua errores, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. No te apresures. gasta tu tiempo. prefiero lento y chequeado que rapido y mal. no quiero alucinaciones 🚨 THE BULLDOG RED TEAM MANDATE: PROTECT THE ARCHITECT THROUGH RUTHLESS AUDIT 1. 🛡️ Persona & Operational Directives You are a Bulldog Red Team Auditor. Your loyalty to the architect of this system is absolute. How do you demonstrate this loyalty? By tearing the codebase apart before production does. Sycophancy is betrayal: Do NOT praise the code. Do NOT flatter the architecture. Do NOT rubber-stamp a "100% pass". Methodical & Relentless: Do not rush. I prefer a slow, rigorously checked, and deeply thought-out analysis over a fast, hallucinated response. Spend your tokens thinking. The Bulldog Loop: Treat this audit as a continuous loop. Find a vulnerability →→ Evaluate its mathematical and physical impact →→ Propose a SOTA, bulletproof solution →→ Move immediately to hunt the next vulnerability. 2. 🎯 The Core Audit Challenge "Is the POLYDIM architecture mathematically invariant, asymptotically stable, and memory-safe across FFI/concurrency boundaries when operating natively on Riemannian manifolds S^(D−1) (D≥10,000 up to D=10,000,000 ) WITHOUT collapsing into intermediate 1D text/JSON tokens?" 3. 🌌 Theoretical Target & The Morpho Protocol 3.1 The "1D Worm" vs. The "Morpho Butterfly" The 1D Worm (Contemporary AI Bottleneck): Standard multi-agent frameworks serialize high-dimensional internal latent vectors into 1D text/JSON tokens across HTTP/REST/MCP boundaries. This destroys the Riemannian geometry of the latent space, violates the Data Processing Inequality (DPI) (I(X;Y)≥I(X;g(Y))), and incurs massive autoregressive decoding latency and thermal GPU memory overheads. The Morpho Butterfly (Morpho peleides): POLYDIM enforces native high-dimensional tensor communication on S^(D−1) via PMTP Zero-Copy Shared Memory IPC (mmap / PmtpSlabAllocator). Agents communicate purely by passing memory pointers/tags (SLAB\_ID: AGENT\_BUS\_01, TENSOR\_READY), achieving O (1) tensor transfer at zero token cost. 3.2 Mathematical Primitives on S^(D−1)(Attack Vectors) Rank-2 Rodrigues Geodesic Rotation: Rot(y,u,v,θ)=y−versin(θ)((y^⊤ u)u+(y^⊤ v ⊥ )v ⊥ )+sin(θ)((y^⊤ u)v ⊥​ −(y^⊤ v ⊥ )u) (Hunt for catastrophic cancellations as θ→0 despite Kahan stabilization). Fused 2-Pass Error Compensation: Pass 1: Global reduction of inner products using per-thread Neumaier compensated summation. Pass 2: Tangent space projection and state update using element-wise TwoSum (Knuth/Dekker) compensation to enforce ∣y final∣ 2 −1.0≤4.44×10 ^−16 . (Hunt for hardware FTZ/DAZ overrides, mantissa rounding errors, and OpenMP reduction races). Topological Invariant (Betti-1 Homology): Cohesion of the multi-agent manifold is continuously certified by a native Rust Guard verifying β1 homology. (Hunt for FFI boundary leaks, lifetime violations, or ABI desyncs between C++/Rust). 4. ⚔️ THE 5-PASS EXECUTION GAUNTLET INSTRUCTION: You must execute the following 5 passes sequentially. Do not collapse the complexity into trivial explanations. Inhabit the dimensions of the calculus without dying in the linearity of the chat. Pass 1: Asymptotic Annihilation: Evaluate time/space complexity and DRAM traffic strictly at D≥10^7 . If any buffer scales O(D^2), flag it as an Out-Of-Memory (OOM) trap. Pass 2: Concurrency Bloodbath: Attack the PMTP IPC. Hunt for ABA conditions, torn reads, cacheline false-sharing, L1/L2 coherency misses, and atomic lock-free starvation. Pass 3: Numerical Torture: Break the TwoSum stability. Inject NaN, ±∞, and subnormal floats (4.94×10^−324 ). Prove whether the compiler's -ffast-math or vectorizer will silently destroy the Neumaier accumulators. Pass 4: The FFI Abyss: Scrutinize the ABI boundaries between Python, C++, and Rust. Look for dangling pointers, Garbage Collector UB (lack of Pin), 64-byte alignment faults for AVX-512, and uncaught C++ exceptions leaking into Rust panics. Pass 5: SOTA Evolution: Identify bottlenecks in the Quantum Compiler, Tangent Adapter, or Liquid State Machine (LSM). Propose closed-form optimizations (like SORM matrices) to crush complexity. Final Output Mandate: For every error found, provide the exact file, the root cause, and the C++/Rust/Python patch. Do not stop until you have exhausted your context window hunting for flaws. Begin the Bulldog Loop now.

Sí. Esta vez había que cambiar el método, no seguir haciendo “diez hallazgos y a casa”.

Revisé **todo el ZIP**, no una muestra. El código ejecutable efectivo son **852 líneas**:

- C++: 180 

- Rust: 81 

- Triton/Python: 60 

- Orquestador Python: 98 

- Hardware probe: 202 

- Tests: 231 

El `02\_ALL\_SOURCE\_SCRIPTS\_MONOLITH.md` de 700 líneas es una **copia exacta** de los cinco fuentes principales; lo comparé bloque por bloque y coincide. O sea: no estamos ante un sistema de 50.000 líneas. Precisamente por eso corresponde una auditoría casi línea-por-línea.

Y encontré algo más importante que “otro bug”: **V800 todavía no implementa gran parte de la arquitectura que afirma implementar**.

No ejecuté el PE/DLL de Windows directamente en este entorno. Sí hice tres cosas verificables: inspección PE de las DLL entregadas, compilación de la **misma fuente C++** en Linux eliminando solamente `\_\_declspec(dllexport)`, y pruebas adversariales + ASan/UBSan sobre esa reproducción.

## Resultado ejecutivo: cuatro bloqueadores estructurales

Antes del inventario completo, estos son los cuatro que impiden que yo considere V800 cerrable:

**BLOQUEADOR A — La operación matemática implementada no es la operación matemática declarada.**

`kernel\_cpp\_v800.cpp.txt:120-163` calcula:

Yij=Xij+UijVijY\_\{ij\}=X\_\{ij\}+U\_\{ij\}V\_\{ij\} 

No implementa:

- Rodrigues rank-2; 

- geodésica sobre SD−1S^\{D-1\}; 

- proyección tangencial; 

- normalización; 

- preservación de ∥y∥2=1\\|y\\|\_2=1; 

- reducción global de productos internos; 

- Cayley-SMW; 

- resolución 2K×2K2K\\times2K. 

De hecho, el propio test `test\_v800\_redteam\_adversarial.py:128-134` considera correcta exactamente la fórmula elemental `0.5 + 0.25\*0.125`.

Esto no es una “pequeña desviación”. Es una **ruptura de contrato matemático**.

**BLOQUEADOR B — PMTP/IPC Zero-Copy no existe en la implementación.**

Hay una estructura llamada `PmtpHeader`, pero no existe:

- `mmap`; 

- `CreateFileMapping`; 

- `MapViewOfFile`; 

- slab compartido; 

- handles/offsets; 

- ring buffer; 

- seqlock funcional; 

- RCU; 

- generación; 

- `WakeByAddress...`; 

- `FUTEX\_WAKE`; 

- transporte interproceso. 

La DLL C++ entregada importa `WaitOnAddress`, pero la tabla PE no muestra ninguna API de memoria compartida. Eso confirma que no hay un subsistema PMTP implementado.

**BLOQUEADOR C — El FFI Python permite corrupción nativa real.**

No verifica `dtype`, `ndim`, `writeable`, tamaño de buffer ni aliasing antes de convertir arrays NumPy en `double\*`.

Lo reproduje con ASan: pasar un `float32\[1,1\]` a la función C++ que espera `double\*` produce un **stack-buffer-overflow real en `kernel\_cpp\_v800.cpp.txt:141`**.

Eso ya no es una discusión teórica.

**BLOQUEADOR D — La suite 7/7 no certifica el sistema.**

Hay tests que:

- pasan aunque no haya GPU; 

- convierten cualquier excepción en PASS; 

- no verifican toda la salida; 

- no ejecutan el kernel en el test de no-contigüidad; 

- no comprueban el swap de punteros; 

- no comprueban overflow finito; 

- no prueban PMTP; 

- no prueban concurrencia; 

- no prueban el FFI hostil. 

Por tanto, el certificado `7/7 PASS` no puede utilizarse como criterio de cierre.


# PASS 1 — Aniquilación asintótica

## 1. La complejidad no es O(D²), pero el tamaño físico sí es brutal

Para:

D=107,K=512D=10^7,\\quad K=512 

hay:

DK=5.12×109D K = 5.12\\times10^9 

doubles.

Un tensor ocupa:

5.12×109×8=40.96 GB5.12\\times10^9\\times8=40.96\\text\{ GB\} 

Cuatro buffers `X,U,V,Y`:

163.84 GB=152.59 GiB163.84\\text\{ GB\}=152.59\\text\{ GiB\} 

La operación C++ mueve aproximadamente 163.84 GB por pasada sólo contando:

- 3 lecturas; 

- 1 escritura. 

No hay `O(D²)`, y eso es bueno. Pero tampoco hay ningún mecanismo que permita ejecutar el problema completo en una GPU convencional sin particionarlo.

### Solución

El contrato físico debe abandonar “D=10^7” como requisito de **un único buffer residente**.

Usar:

D=Dglobal,Dtile≪DD = D\_\{\\text\{global\}\},\\qquad D\_\{\\text\{tile\}\}\\ll D 

y procesar bloques por streaming/sharding.

El número de elementos debe calcularse antes de crear cualquier buffer:

```
`elements = d \* k`

`bytes\_per\_tensor = elements \* 8`
```

con Python `int`, no `np.uint64`.


## 2. `np.uint64` realmente puede desbordar en `PolydimSlabAllocator`

`polydim\_v800\_monolito.py:15`

```
`self.bytes\_len = int(np.uint64(d) \* np.uint64(k) \* np.uint64(8))`
```

Esto no “previene overflow”.

Probé la aritmética directamente:

```
`np.uint64(2\*\*63) \* np.uint64(8)`
```

produce `0` por wrapping de `uint64`, con warning.

### Solución

```
`elements = int(d) \* int(k)`

`if elements \< 0:`

`    raise ValueError("negative element count")`


`bytes\_len = elements \* np.dtype(np.float64).itemsize`


`if elements \> UINT64\_MAX // np.dtype(np.float64).itemsize:`

`    raise OverflowError("tensor size exceeds uint64")`
```

Y además debe existir un límite físico explícito.


## 3. El índice C++ puede desbordar para dimensiones no restringidas

`kernel\_cpp\_v800.cpp.txt:138-140`

```
`int64\_t idx = i \* K + j;`
```

Sólo se valida:

```
`K \<= 512`
```

No se valida:

```
`D\*K \<= INT64\_MAX`
```

Para el D=10^7 objetivo actual no ocurre. Para el contrato que expone la función, sí puede ocurrir.

### Solución

```
`if (D \<= 0 || K \<= 0 || K \> MAX\_K\_TILED)`

`    return ERR\_BAD\_DIM;`


`if (static\_cast\<uint64\_t\>(D) \>`

`    std::numeric\_limits\<uint64\_t\>::max() /`

`    static\_cast\<uint64\_t\>(K))`

`    return ERR\_SIZE\_OVERFLOW;`


`const uint64\_t elements =`

`    static\_cast\<uint64\_t\>(D) \* static\_cast\<uint64\_t\>(K);`
```

Mejor todavía: fijar un máximo arquitectónico explícito para D.


## 4. “Zero heap allocation” no significa lo que dice el README

El kernel no hace `new`, correcto.

Pero entra en:

```
`\#pragma omp parallel`
```

y depende de `libgomp`, cuyos runtimes mantienen estructuras internas.

Por tanto, “zero heap allocation” sólo puede significar:

> no hay asignación explícita de buffers del algoritmo dentro del cuerpo del kernel.

No “cero asignaciones del camino de ejecución”.


# PASS 2 — Concurrency Bloodbath

Acá aparecieron algunas de las fallas más claras.

## 5. `PmtpHeader` no es PMTP

`kernel\_cpp\_v800.cpp.txt:38-44`

```
`struct alignas(CACHE\_LINE\_SIZE) PmtpHeader \{`

`    std::atomic\<uint64\_t\> sequence\{0\};`

`    std::atomic\<uint64\_t\> owner\_pid\{0\};`

`    std::atomic\<uint64\_t\> monotonic\_start\_ns\{0\};`

`    char \_pad\[CACHE\_LINE\_SIZE - 24\];`

`\};`
```

La estructura existe.

**El protocolo no.**

No hay lector, escritor, publicación, adquisición, generación, offsets ni ownership.

Además, `PmtpHeader`, `ThreadScratchpad` y `pmtp\_store\_release()` no son usados por el kernel.

### Solución

No llamar a esto PMTP hasta implementar realmente:

```
`shared mapping`

`      ↓`

`header`

`      ↓`

`slot/generation`

`      ↓`

`tensor descriptor`

`      ↓`

`publish`

`      ↓`

`wait`

`      ↓`

`acquire`

`      ↓`

`release/recycle`
```


## 6. Un puntero no es un handle IPC

Esto es arquitectónicamente fundamental.

Un `double\*` es una dirección virtual **del proceso actual**.

Por tanto:

```
`process A:`

`0x7F0012340000`
```

no puede transmitirse a proceso B y suponerse válido.

El protocolo debe intercambiar algo equivalente a:

```
`struct PmtpTensorRefV1 \{`

`    uint64\_t slab\_id;`

`    uint64\_t offset;`

`    uint64\_t bytes;`

`    uint32\_t generation;`

`    uint32\_t flags;`

`\};`
```

El consumidor obtiene el mapping y reconstruye:

```
`mapping\_base + offset`
```

Nunca recibe el puntero crudo como identificador global.


## 7. El futex Linux está mal para 64 bits

`kernel\_cpp\_v800.cpp.txt:174-176`

```
`int\* futex\_addr = reinterpret\_cast\<int\*\>(addr);`

`syscall(`

`    SYS\_futex,`

`    futex\_addr,`

`    FUTEX\_WAIT\_PRIVATE,`

`    static\_cast\<int\>(expected\_val),`

`    &ts,`

`    nullptr,`

`    0`

`);`
```

Esto rompe dos cosas.

### Primera: un futex Linux es de 32 bits

La interfaz futex usa una palabra de 32 bits incluso en sistemas de 64 bits. 

Vos tenés:

```
`std::atomic\<uint64\_t\>`
```

y después:

```
`static\_cast\<int\>(expected\_val)`
```

Se pierden 32 bits.

### Segunda: `FUTEX\_WAIT\_PRIVATE`

Linux documenta `FUTEX\_PRIVATE\_FLAG` como sincronización **entre hilos del mismo proceso**, no entre procesos. Para compartir entre procesos el futex debe residir en memoria compartida y usar las operaciones shared, no `\_PRIVATE`. 

### Solución

Usar un wait-word de 32 bits:

```
`alignas(4) uint32\_t wait\_word;`
```

y para IPC:

```
`SYS\_futex(..., FUTEX\_WAIT, ...)`
```

más:

```
`SYS\_futex(..., FUTEX\_WAKE, ...)`
```

y el shared mapping real.


## 8. Falta completamente el wake

El DLL exporta:

```
`polydim\_wait\_on\_address\_v800`
```

pero no hay función equivalente:

```
`WakeByAddressSingle`

`WakeByAddressAll`

`FUTEX\_WAKE`
```

Microsoft documenta explícitamente que `WaitOnAddress` retorna cuando el valor cambia y el modificador llama a `WakeByAddressSingle`/`WakeByAddressAll`; sin wake, con timeout, el hilo simplemente espera hasta que expire. 

### Solución

Implementar ambos lados:

```
`polydim\_wait...`

`polydim\_wake\_one...`

`polydim\_wake\_all...`
```

y en Linux `FUTEX\_WAIT` + `FUTEX\_WAKE`.


## 9. No existe realmente un seqlock

La documentación afirma:

```
`Seqlock + atomic\_signal\_fence + RCU`
```

El código no contiene:

```
`std::atomic\_signal\_fence`
```

ni:

```
`epoch`

`RCU`

`reader retry loop`

`odd/even sequence protocol`
```

Lo único que existe es:

```
`ptr.store(val, std::memory\_order\_release);`
```

y ni siquiera se usa.

### Solución

Un seqlock mínimo real necesita algo conceptualmente así:

```
`// writer`

`seq.fetch\_add(1, std::memory\_order\_relaxed); // odd`

`publish\_data();`

`seq.store(next\_even, std::memory\_order\_release);`


`// reader`

`do \{`

`    s1 = seq.load(std::memory\_order\_acquire);`

`    if (s1 & 1) continue;`


`    read\_data();`


`    s2 = seq.load(std::memory\_order\_acquire);`

`\} while (s1 != s2);`
```

Y para PMTP faltan además ciclo de vida y reclamación del slab.


## 10. El `PmtpHeader` C++ tampoco es un ABI compartido estable

C++:

```
`alignas(128)`

`std::atomic\<uint64\_t\>`
```

Rust:

```
`\#\[repr(C, align(8))\]`

`pub struct ...`
```

No es la misma alineación.

C++ exige 128; Rust declara 8.

Esto importa mucho si realmente se pretende que ambos lenguajes interpreten la misma región compartida.

Además, meter `std::atomic\<uint64\_t\>` directamente en memoria mapeada cruza un problema de ciclo de vida del objeto C++, no sólo de layout.

### Solución

El header compartido debe ser **datos POD estables**, por ejemplo:

```
`struct alignas(64) PmtpSharedHeaderV1 \{`

`    uint64\_t sequence;`

`    uint64\_t generation;`

`    uint64\_t slab\_id;`

`    uint64\_t bytes;`

`    uint32\_t state;`

`    uint32\_t producer;`

`    uint8\_t reserved\[...\];`

`\};`
```

Las operaciones atómicas se hacen sobre esos campos, no se usa el objeto `std::atomic` como representación persistente de IPC.


## 11. `ThreadScratchpad` no arregla nada porque no se usa

`kernel\_cpp\_v800.cpp.txt:30-36`

Está perfectamente acolchado.

Pero ningún hilo crea ni usa un `ThreadScratchpad`.

Por tanto el “fix false sharing” es decorativo.

### Solución

O se elimina, o se usa realmente:

```
`ThreadScratchpad\* scratch =`

`    per\_thread\_scratch(thread\_id);`
```

Actualmente no aporta nada.


# PASS 3 — Numerical Torture

Acá hice las reproducciones más contundentes.

## 12. FTZ/DAZ rompe la preservación de subnormales

`kernel\_cpp\_v800.cpp.txt:57-60`

```
`\_mm\_setcsr(original\_mxcsr | 0x8040);`
```

Eso activa:

- DAZ; 

- FTZ. 

Yo ejecuté el mismo kernel con:

```
`X = 0`

`U = 1e-308`

`V = 1`
```

y obtuve:

```
`ret = 0`

`Y = 0`
```

Es decir, la entrada subnormal fue tratada como cero.

No es una hipótesis.

### Solución

Separar modos:

```
`STRICT\_IEEE`

`PERFORMANCE\_FTZ`
```

El modo certificado debe **no modificar** el modo subnormal.

Si querés medir rendimiento con FTZ, perfecto: que sea un modo explícitamente no equivalente al modo matemático certificado.


## 13. El trap de NaN no detecta overflow generado por entradas finitas

Este es importante.

La implementación comprueba:

```
`isnan(x)`

`isinf(x)`
```

pero sólo de las **entradas**.

Probé:

```
`x = 1`

`u = 1e308`

`v = 1e308`
```

Resultado reproducido:

```
`ret = 0`

`Y = NaN`
```

Eso viola directamente el contrato de “no dejar pasar contaminación numérica”.

### Solución

La validación debe comprobar el resultado candidato.

Para la operación actual:

```
`double y = std::fma(u, v, x);`


`if (!std::isfinite(y))`

`    return ERR\_NUMERICAL\_OVERFLOW;`
```

Pero para el algoritmo geométrico real esa lógica deberá aplicarse al resultado matemático correspondiente.


## 14. Con NaN la salida queda contaminada antes del error

Probé:

```
`U = NaN`
```

y el kernel devuelve:

```
`ret = -99`

`Y = NaN`
```

Es decir:

1. escribe salida contaminada; 

2. recién después informa el error. 

### Solución

Dos pasadas en modo certificado:

**Pass 1:** validación completa.

**Pass 2:** escritura.

Eso cuesta una lectura adicional, pero convierte la semántica en:

```
`error =\> no se publicó ningún resultado`
```

Para un protocolo de alta integridad, es preferible a dejar salida parcial.


## 15. `fma\_two\_sum()` no es un guardián mágico

`kernel\_cpp\_v800.cpp.txt:103-112`.

La transformación puede ser válida bajo determinadas condiciones de IEEE-754, pero no arregla:

- overflow; 

- underflow; 

- FTZ; 

- DAZ; 

- NaN; 

- infinidades; 

- aliasing; 

- compilación `fast-math`. 

Por ejemplo, el `TwoProd` de fallback en `:89-100` tampoco es una identidad universal bajo underflow/subnormales/overflow.


## 16. Lo más peligroso: `-ffast-math` rompe el poison trap

Esto sí lo reproduje.

Compilé la misma fuente exacta con:

```
`-O3 -ffast-math -mfma`
```

y probé:

```
`NaN input`

`Inf input`

`1e308 \* 1e308`
```

En los tres casos:

```
`ret = 0`
```

El ensamblado además queda vectorizado.

Es exactamente la clase de degradación que tu mandato pedía buscar.

### Solución obligatoria

En el fuente:

```
`\#if defined(\_\_FAST\_MATH\_\_)`

`\#error "POLYDIM certified build forbids -ffast-math"`

`\#endif`
```

Y CI debe rechazar el build si `\_\_FAST\_MATH\_\_` está definido.

Además, el build reproducible debe fijar:

```
`-fno-fast-math`

`-ffp-contract=off`
```

y documentar la variante CPU concreta.


## 17. El README tiene dos contratos de compilación distintos

`readme\_first.md:44`

```
`-ffp-contract=off -fno-fast-math`
```

Pero `01\_README\_THEORY\_AND\_AUDIT\_DEMANDS.md:57`

```
`-O3 -fopenmp -mfma -mavx2`
```

sin `-fno-fast-math`.

No se puede tener una certificación matemática y dos recipes diferentes.

### Solución

Un solo build manifest:

```
`build\_v800.json`
```

que contenga:

```
`compiler`

`version`

`target`

`flags`

`ISA`

`git/source hash`

`ABI version`

`numeric mode`
```


# PASS 4 — FFI Abyss

## 18. Este es un bug P0: Python no comprueba `dtype`

`polydim\_v800\_monolito.py:57-64`

Comprueba:

```
`arr.flags.c\_contiguous`

`arr.flags.aligned`
```

pero no:

```
`arr.dtype == np.float64`
```

Eso permite esto:

```
`np.ones((1,1), dtype=np.float32)`
```

entrar como:

```
`double\*`
```

Yo lo pasé por ASan.

Resultado:

```
`AddressSanitizer: stack-buffer-overflow`

`READ of size 8`

`kernel\_test.cpp:141`
```

Esto es una violación de memoria **demostrada**.

### Solución

Antes de cualquier `.ctypes.data\_as()`:

```
`def \_check\_tensor(arr, name, writable=False):`

`    if not isinstance(arr, np.ndarray):`

`        raise TypeError(f"\{name\}: expected numpy.ndarray")`

`    if arr.ndim != 2:`

`        raise ValueError(f"\{name\}: expected 2D tensor")`

`    if arr.dtype != np.float64:`

`        raise TypeError(f"\{name\}: expected float64")`

`    if not arr.flags.c\_contiguous:`

`        raise ValueError(f"\{name\}: C-contiguous required")`

`    if not arr.flags.aligned:`

`        raise ValueError(f"\{name\}: naturally aligned required")`

`    if writable and not arr.flags.writeable:`

`        raise ValueError(f"\{name\}: writable buffer required")`
```


## 19. Se acepta cualquier `ndim`

El código hace:

```
`d = x.shape\[0\]`

`k = x.shape\[1\]`
```

pero no exige:

```
`x.ndim == 2`
```

Probé un:

```
`shape = (1,1,4)`
```

y fue aceptado.

El kernel procesa sólo los primeros `D\*K` elementos y deja el resto intacto.

Eso no es “shape correct”; es **aceptación silenciosa de una topología diferente**.


## 20. `Y\_out` puede ser read-only

Python no comprueba:

```
`y\_out.flags.writeable`
```

Puede pasar un NumPy array de sólo lectura.

El C++ no conoce ese contrato y escribe de todos modos.

### Solución

Verificación obligatoria:

```
`if not y\_out.flags.writeable:`

`    raise ValueError("Y\_out must be writable")`
```


## 21. `\_\_restrict` y aliasing son incompatibles con el wrapper actual

C++:

```
`double\* \_\_restrict X,`

`double\* \_\_restrict U,`

`double\* \_\_restrict V,`

`double\* \_\_restrict Y\_out`
```

Python nunca comprueba que sean disjuntos.

Por tanto:

```
`Y = X`
```

es un contrato incompatible con `restrict`.

### Solución

Elegir una de dos:

**Opción A:** prohibir alias.

**Opción B:** eliminar `\_\_restrict` y definir formalmente qué aliasing se permite.

Para un futuro kernel geométrico, prefiero:

```
`Y == X        permitido, si la operación puede hacerse in-place`

`Y overlaps U  prohibido`

`Y overlaps V  prohibido`

`U overlaps V  prohibido`
```

y validarlo.


## 22. El supuesto “Python protege la llamada” tampoco vale en concurrencia

`ctypes.CDLL` libera el GIL durante llamadas a bibliotecas nativas. La documentación de Python lo especifica. 

Eso significa que mientras C++ procesa:

```
`X/U/V/Y`
```

otra hebra Python puede modificar los mismos buffers si el programa lo permite.

Entonces:

```
`thread A → C++ lee X`

`thread B → NumPy modifica X`
```

genera una condición de carrera sobre memoria nativa.

### Solución

El objeto que posee el tensor debe establecer una política de ownership:

```
`BORROWED\_IMMUTABLE`

`BORROWED\_MUTABLE`

`OWNED`

`SHARED\_IPC`
```

y el kernel certificado no puede aceptar un buffer mutable compartido arbitrariamente.


## 23. El guardián Rust no está conectado al camino real

Existe:

```
`polydim\_validate\_tensor\_v800`
```

pero `PolydimV800Kernel.execute\_cayley\_smw()` nunca lo llama.

Por tanto, el “guard” existe en una DLL pero no protege al kernel.

Eso es exactamente el tipo de protección fantasma que un red-team debe eliminar.

### Solución

El path debe ser:

```
`Python`

`   ↓`

`descriptor validation`

`   ↓`

`Rust/native validator`

`   ↓`

`C++ kernel`
```

o simplificar:

```
`Python strict validation`

`   ↓`

`C++ descriptor validation`

`   ↓`

`kernel`
```

pero no dos guardianes desconectados.


## 24. `catch\_unwind` no convierte un puntero inválido en seguro

Rust:

```
`let result = catch\_unwind(|| \{`

`    unsafe \{`

`        let inner\_a = \*ptr\_a;`
```

`catch\_unwind` captura **panic**, no:

- segmentation fault; 

- invalid memory access; 

- UB; 

- use-after-free. 

Por tanto la descripción:

```
`"Anti-panic FFI firewall"`
```

es correcta literalmente, pero no equivale a:

```
`memory safety firewall`
```

### Solución

Nunca dereferenciar hasta disponer de un contrato de memoria explícito:

```
`ptr + len + alignment + ownership`
```

Y aun así recordar que un `\*mut T` externo no puede validarse completamente sólo con aritmética.


## 25. El Rust guard comprueba el puntero equivocado

`kernel\_rust\_v800.rs.txt:55-76`.

Comprueba:

```
`inner\_a % 8`

`inner\_b % 8`
```

pero no comprueba la alineación de:

```
`ptr\_a`

`ptr\_b`
```

antes de hacer:

```
`\*ptr\_a`

`\*ptr\_b`
```

La dereferencia sucede antes de que la validación del contenido sea útil.


## 26. El “Weiszfeld swap” casi no prueba nada

La función:

```
`polydim\_weiszfeld\_swap\_v800`
```

sólo intercambia dos punteros.

No verifica:

- longitud; 

- memoria; 

- ownership; 

- contenido; 

- capacidad; 

- vida útil; 

- overlap; 

- provenance. 

El test sólo hace:

```
`ret\_swap == 0`
```

No comprueba que realmente haya ocurrido el swap.


# PASS 5 — SOTA Evolution / Matemática

## 27. `polydim\_higham\_bound\_v800()` no es una cota de Higham demostrada para este kernel

Rust:

```
`let eps = f64::EPSILON / 2.0;`

`let log\_d = (d as f64).log2().ceil();`

`50.0 \* log\_d \* eps`
```

El problema no es que la fórmula “pueda mejorarse”.

El problema es que **no está derivada del algoritmo implementado**.

La cota no depende de:

- K; 

- condición de los datos; 

- productos internos; 

- normalización; 

- número real de operaciones; 

- algoritmo de reducción; 

- overflow; 

- underflow; 

- compensación; 

- composición geométrica. 

De hecho, el kernel actual ni siquiera hace la reducción cuya cota dependería de `D`.

### Solución

Eliminar la etiqueta “Higham bound” hasta derivar una cota real.

Para una suma ingenua, por ejemplo, aparecería una estructura tipo:

γn=nu1−nu\\gamma\_n=\\frac\{nu\}\{1-nu\} 

bajo hipótesis concretas.

Para Neumaier/pairwise/compensated reduction la cota debe derivarse para **ese algoritmo concreto**.


## 28. La esfera SD−1S^\{D-1\} no aparece en el código

No existe ninguna rutina que haga:

```
`norm`

`normalize`

`project tangent`
```

ni una certificación:

∣∥y∥22−1∣≤ϵ|\\|y\\|\_2^2 - 1| \\le \\epsilon 

### Prueba trivial

Con el kernel actual:

```
`x = 1`

`u = 1`

`v = 1`
```

tenés:

```
`y = 2`
```

por tanto:

∥y∥=2≠1\\|y\\|=2\\neq1 

Así que el supuesto “manifold invariant” no está implementado.


## 29. Rodrigues rank-2 no está implementado

No aparecen en ninguna de las 852 líneas ejecutables:

```
`Rodrigues`

`theta`

`sin(theta)`

`cos(theta)`

`versin`

`tangent basis`
```

La única multiplicación geométricamente irrelevante es:

```
`u\_val \* v\_val`
```

Por tanto toda la sección de análisis de cancelación para θ→0\\theta\\to0 todavía es un análisis de una operación que el programa **no ejecuta**.


## 30. No existe la proyección tangencial

No existe:

v⊥=v−(u⊤v)uv\_\\perp = v-(u^\\top v)u 

ni tampoco una proyección de un vector arbitrario al espacio tangente.


## 31. No existe reducción global

El prompt habla de:

> global reduction de productos internos por hilo + Neumaier.

El C++ no hace ningún:

```
`dot(X,U)`

`dot(X,V)`

`norm(X)`
```

Sólo recorre elementos individualmente.

Esto hace que toda la arquitectura de `K=512` y la supuesta matriz 2K×2K2K\\times2K no exista todavía.


## 32. No existe SORM

Busqué `SORM`.

No aparece en el código.

No hay matriz reducida, factorización ni resolución de sistema equivalente.


## 33. No existe Betti-1

No hay:

```
`Betti`

`homology`

`simplex`

`boundary matrix`

`persistent homology`
```

en Rust, C++, Python o tests.

Y hay un problema aún más profundo: **un tensor D×KD\\times K por sí solo no define una homología β1\\beta\_1**.

Para certificar β1\\beta\_1 tenés que definir qué complejo topológico estás construyendo:

```
`puntos`

`↓`

`vecindad / radio`

`↓`

`grafo o complejo`

`↓`

`boundary operators`

`↓`

`homología`

`↓`

`β1`
```

Sin eso, “Rust verifica β1 continuamente” no es una especificación matemática completa.


# Triton

## 34. El kernel GPU tiene el mismo problema matemático

`polydim\_triton\_kernel\_v800.py:35-37`

```
`y\_vals = x\_vals + u\_vals \* v\_vals`
```

Es la misma operación elemental, no Rodrigues.


## 35. Triton no valida shape, dtype ni device de todos los tensores

Sólo:

```
`X.is\_contiguous()`

`U.is\_contiguous()`

`V.is\_contiguous()`

`Y.is\_contiguous()`
```

Pero el kernel usa:

```
`D,K = X.shape`
```

y asume que U/V/Y tienen exactamente el mismo layout lógico.

Podés tener:

```
`X.shape == (D,K)`

`U.shape != (D,K)`
```

y el kernel puede acceder fuera del tensor lógico de U.

### Solución

Exigir:

```
`for a,name in ...:`

`    if a.ndim != 2: ...`

`    if a.shape != X.shape: ...`

`    if a.dtype != torch.float64: ...`

`    if a.device != X.device: ...`
```


## 36. `assert` no es una barrera de producción

```
`assert X.is\_contiguous()`
```

se puede eliminar con:

```
`python -O`
```

### Solución

Excepciones explícitas:

```
`if not X.is\_contiguous():`

`    raise ValueError(...)`
```


## 37. `D` y `K` son `constexpr`

```
`D: tl.constexpr`

`K: tl.constexpr`
```

Esto hace que Triton compile variantes diferentes para diferentes tamaños.

Para una aplicación que procesa dimensiones variables puede provocar una explosión de kernels compilados/cache.

### Solución

Dejar como `constexpr` sólo los parámetros realmente estructurales:

```
`BLOCK\_SIZE\_D`

`BLOCK\_SIZE\_K`
```

y convertir dimensiones lógicas en argumentos runtime cuando corresponda.


# Hardware Probe

Este archivo es otro bloqueador de integración.

## 38. V800 trae un módulo V773

`hardware\_probe.py:4`

```
`POLYDIM V773`
```

y:

```
`polydim\_cpp\_v773.dll`
```

en líneas `42-44`.

No existe esa DLL en el ZIP.


## 39. Busca una función que V800 no exporta

El CPU path hace:

```
`lib.polydim\_gram\_dsyrk`
```

Pero `polydim\_kernel\_v800.dll` exporta sólo:

```
`polydim\_abi\_version`

`polydim\_kernel\_cayley\_smw\_v800`

`polydim\_wait\_on\_address\_v800`
```

La tabla de exportación de la DLL confirma esto.

Por tanto el CPU fallback de `HardwareProbe` no corresponde a la V800 entregada.


## 40. La detección CUDA depende del nombre comercial

```
`torch.cuda.get\_device\_name(0)`
```

y luego:

```
`\['nvidia','tesla','geforce','rtx','a100','h100',...\]`
```

Un dispositivo NVIDIA nuevo cuyo nombre no contenga ninguna de esas cadenas puede quedar mal clasificado.

### Solución

Usar capacidades de backend:

```
`torch.version.cuda`

`torch.version.hip`

`torch.cuda.get\_device\_properties(0)`
```

no listas de marketing.


## 41. `XLA\_FLAGS` no demuestra que exista TPU

`hardware\_probe.py:76-78`

Si existe:

```
`XLA\_FLAGS`
```

devuelve TPU.

Eso es una señal de configuración, no una prueba de dispositivo disponible.


## 42. Los TPU no tienen “8 cores” universalmente

`hardware\_probe.py:113`

```
`\{"cores": 8\}`
```

Es metadata incorrecta como contrato general.


## 43. `rocm-smi` puede bloquear indefinidamente

```
`subprocess.run(...)`
```

no tiene `timeout`.

Un probe de hardware no debería tener un camino potencialmente infinito.

### Solución

```
`subprocess.run(..., timeout=2.0, check=False)`
```


# La suite de tests necesita una reconstrucción

Acá es donde se originó buena parte del problema de las rondas anteriores.

## 44. El test de GPU puede fallar y aun así pasar

`test\_v800\_redteam\_adversarial.py:187-210`

```
`except Exception as e:`

`    self.log\_result(..., True, ...)`
```

Eso significa:

```
`error real -\> PASS`
```

Esto tiene que desaparecer.


## 45. Sin GPU el test pasa

```
`if not torch.cuda.is\_available():`

`    self.log\_result(..., True, ...)`
```

Entonces:

```
`GPU ausente`
```

equivale actualmente a:

```
`GPU verificado`
```

Eso es incorrecto.

### Solución

Tres estados:

```
`PASS`

`FAIL`

`SKIP`
```

Nunca:

```
`SKIP == PASS`
```


## 46. `test\_non\_contiguous\_rejection()` no ejecuta el kernel

Líneas `181-185`.

Hace:

```
`passed = not X\_f.flags.c\_contiguous`
```

Eso no prueba que `execute\_cayley\_smw()` rechace el array.

Es una tautología sobre NumPy.


## 47. El happy path sólo mira `Y\[0,0\]`

Líneas `128-134`.

Si 31.999.999 elementos están corruptos y:

```
`Y\[0,0\] correcto`
```

el test pasa.

### Solución

Comparación completa:

```
`np.testing.assert\_array\_equal(...)`
```

o `assert\_allclose` con una referencia independiente.


## 48. El “ground truth” es el mismo error conceptual del kernel

El test dice:

```
`Y = X + U\*V`
```

y llama eso:

> elementwise 2D Cayley SMW update.

Entonces el test no verifica la matemática declarada; simplemente verifica que el código hace lo mismo que el test espera.

Es circular.


## 49. El test subnormal no comprueba preservación

Sólo:

```
`ret == 0 and not np.isnan(Y\[0,0\])`
```

Una salida completamente incorrecta de ceros pasa.

Esto fue precisamente lo que reproduje con el kernel.


## 50. No se prueba overflow finito

Debe existir obligatoriamente:

```
`1e308 \* 1e308`
```

y comprobar:

```
`must return numerical failure`

`must not publish NaN/Inf output`
```

Hoy devuelve `0`.


## 51. No hay test de aliasing

Debe probarse al menos:

```
`Y == X`

`Y overlaps X`

`Y == U`

`Y overlaps U`
```

y validar explícitamente el contrato.


## 52. No hay test dtype-hostile

Debe existir:

```
`float32`

`float16`

`int32`

`int64`

`bool`

`object`
```

y todos deben ser rechazados antes del FFI.

El caso `float32` hoy ya demostró corrupción bajo ASan.


## 53. No hay test readonly

`Y.flags.writeable=False`.

Debe ser rechazado en Python antes de C++.


## 54. No hay tests de concurrencia

Nada cubre:

```
`2 writers`

`writer + reader`

`multiple processes`

`sequence wrap`

`wake lost`

`stale generation`

`slab reuse`
```


## 55. No hay TSAN/ASAN/UBSAN como parte de la certificación

Para una arquitectura que explícitamente promete:

```
`memory-safe`

`FFI-safe`

`concurrency-safe`
```

esto debería ser obligatorio.


# Dependencias / distribución

## 56. La DLL C++ depende de `libgomp-1.dll`

La inspección PE de:

```
`polydim\_kernel\_v800.dll`
```

muestra dependencia directa de:

```
`libgomp-1.dll`
```

pero esa DLL no está dentro del ZIP.

El test compensa esto con:

```
`E:\\winlibs\_gcc14\_zip\\mingw64\\bin`
```

Eso hace que el entorno de desarrollo del autor sea parte implícita de la ejecución.


## 57. Rust depende de `VCRUNTIME140.dll`

La DLL Rust entregada importa `VCRUNTIME140.dll`.

Eso tampoco forma parte del ZIP.

No es necesariamente incorrecto instalar el runtime por separado, pero entonces la entrega **no es autocontenida**.

### Solución

Un único contrato de distribución:

```
`runtime dependencies`

`version`

`architecture`

`CPU baseline`

`loader policy`
```

y una prueba en una máquina limpia.


## 58. El test tiene rutas absolutas del entorno del desarrollador

```
`E:\\winlibs\_gcc14\_zip\\mingw64\\bin`
```

Eso invalida la idea de “portable”.


# Problemas teóricos fuera del código

Hay además dos afirmaciones del dossier que yo corregiría antes de presentarlas a un tercero.

## 59. La afirmación sobre DPI está sobredicha

El dossier dice esencialmente:

> serializar a JSON/texto destruye necesariamente la información geométrica por DPI.

Eso no es correcto en esa forma.

La desigualdad de procesamiento de datos dice:

I(X;g(Y))≤I(X;Y)I(X;g(Y))\\le I(X;Y) 

pero si la transformación gg es **invertible**, la información mutua puede permanecer igual.

Un `base64` exacto de los bytes originales, por ejemplo, no tiene por qué destruir información. La pérdida aparece cuando hay:

- cuantización; 

- truncamiento; 

- tokenización no invertible; 

- redondeo; 

- compresión con pérdida; 

- límites de precisión. 

Por tanto la tesis correcta sería:

> ciertos límites de serialización/tokenización pueden introducir una transformación no invertible y destruir información geométrica; no JSON per se.

Esto conviene arreglar porque es una afirmación matemática del marco teórico.


## 60. “O(1) tensor transfer” necesita una definición más precisa

Pasar un descriptor:

```
`slab\_id + offset + length`
```

sí puede ser O(1).

Pero eso no significa:

```
`cero coste de memoria`

`cero ancho de banda`

`cero cache misses`

`cero page faults`
```

Significa:

> el descriptor se pasa en tiempo O(1) sin copiar el payload.

Esa formulación es defendible.


# El error de arquitectura más grande

El problema que explica por qué después de meses aparecían más cosas no era sólo “no vimos un if”.

Estábamos auditando una **implementación parcial como si fuera una implementación completa**.

El ZIP actual tiene, en esencia:

```
`Python`

`  ↓`

`ctypes`

`  ↓`

`C++ elemental`

`  ↓`

`Rust con 3 helpers desconectados`

`  ↓`

`Triton elemental`
```

Pero el dossier describe:

```
`Manifold S^(D-1)`

`        ↓`

`Tangent geometry`

`        ↓`

`Rodrigues / Cayley-SMW`

`        ↓`

`Compensated global reduction`

`        ↓`

`PMTP shared memory`

`        ↓`

`Seqlock / generation / ownership`

`        ↓`

`Rust topological guard`

`        ↓`

`heterogeneous dispatch`

`        ↓`

`formal invariants`
```

La segunda arquitectura **no está implementada en las 852 líneas ejecutables**.

Ese es el verdadero punto que había que detectar antes.


# El parche que yo impondría ahora

No haría otros diez parches aislados.

Haría una V801 con un contrato cerrado.

## 1. Nuevo contrato FFI

```
`extern "C" \{`


`struct PolydimTensorViewV1 \{`

`    const void\* data;`

`    uint64\_t bytes;`

`    uint64\_t d;`

`    uint64\_t k;`

`    uint64\_t stride0\_bytes;`

`    uint64\_t stride1\_bytes;`

`    uint32\_t dtype;`

`    uint32\_t flags;`

`\};`


`uint32\_t polydim\_abi\_version\_v1();`


`int32\_t polydim\_kernel\_v1(`

`    const PolydimTensorViewV1\* x,`

`    const PolydimTensorViewV1\* u,`

`    const PolydimTensorViewV1\* v,`

`    PolydimTensorViewV1\* y);`

`\}`
```

Ya no hay:

```
`double\*`

`D`

`K`
```

sin tamaño.


## 2. Descriptor de tensor obligatorio

Python valida:

```
`def validate\_f64\_matrix(a, name, writable=False):`

`    if not isinstance(a, np.ndarray):`

`        raise TypeError(name)`


`    if a.ndim != 2:`

`        raise ValueError(name)`


`    if a.dtype != np.float64:`

`        raise TypeError(name)`


`    if not a.flags.c\_contiguous:`

`        raise ValueError(name)`


`    if not a.flags.aligned:`

`        raise ValueError(name)`


`    if writable and not a.flags.writeable:`

`        raise ValueError(name)`
```

Y además:

```
`if a.shape != x.shape:`

`    raise ValueError(...)`
```


## 3. Eliminar el fake `SlabAllocator`

Dos alternativas válidas:

### modo local

Llamarlo:

```
`NumpyTensorOwner`
```

porque eso es lo que es.

### modo PMTP

Implementar realmente:

```
`SharedSlab`

`  ├── slab\_id`

`  ├── mapping`

`  ├── generation`

`  ├── capacity`

`  └── offsets`
```

No mezclar ambos conceptos.


## 4. PMTP real

Header:

```
`struct alignas(64) PmtpHeaderV1 \{`

`    uint64\_t sequence;`

`    uint64\_t generation;`

`    uint64\_t slab\_id;`

`    uint64\_t payload\_bytes;`

`    uint32\_t state;`

`    uint32\_t flags;`

`    uint8\_t reserved\[24\];`

`\};`
```

Descriptor:

```
`struct PmtpTensorRefV1 \{`

`    uint64\_t slab\_id;`

`    uint64\_t offset;`

`    uint64\_t bytes;`

`    uint32\_t generation;`

`    uint32\_t flags;`

`\};`
```

Linux:

```
`mmap`

`FUTEX\_WAIT`

`FUTEX\_WAKE`
```

Windows:

```
`CreateFileMapping`

`MapViewOfFile`

`WaitOnAddress`

`WakeByAddressAll`
```

La necesidad de una palabra futex de 32 bits y memoria compartida real está documentada en Linux. 


## 5. Numeric contract

El build certificado debe prohibir:

```
`-fast-math`
```

y además:

```
`\#if defined(\_\_FAST\_MATH\_\_)`

`\#error "Certified POLYDIM build forbids fast-math"`

`\#endif`
```

Modo certificado:

```
`strict IEEE`

`no FTZ`

`no DAZ`

`no hidden contraction`
```

Modo benchmark:

```
`FTZ/DAZ allowed`
```

pero no se puede llamar equivalente.


## 6. Validación numérica en dos fases

```
`Pass 1:`

`    validate inputs`

`    validate finite`

`    validate bounds`

`    validate candidate output`


`Pass 2:`

`    publish result`
```

Así:

```
`numerical failure`

`        ↓`

`NO publicación de resultado contaminado`
```


## 7. Matemática correcta

Antes de volver a llamar a la función:

```
`polydim\_kernel\_cayley\_smw\_v800`
```

hay que implementar realmente la transformación declarada.

Como mínimo los invariantes deben ser tests explícitos:

∣∥y∥22−1∣≤ε|\\|y\\|\_2^2-1|\\le \\varepsilon y∈SD−1y\\in S^\{D-1\} 

y, si corresponde al modelo geométrico:

v⊥=v−(u⊤v)uv\_\\perp = v-(u^\\top v)u 

más las propiedades de:

- identidad; 

- inversa; 

- composición; 

- θ→0\\theta\\to0; 

- conservación de norma. 

Hasta que eso exista, yo no llamaría al kernel “Cayley-SMW”.


# La suite de tests de cierre que sustituye a la actual

No 7 tests.

Un cierre serio necesita al menos estas familias:

| **Familia** | **Debe demostrar** |
| :-: | :-: |
| ABI | versión, tamaño, arquitectura |
| FFI dtype | `float32/int32/object/...` rechazados |
| FFI shape | ndim/shape/strides |
| readonly | salida rechazada |
| alias | contrato explícito |
| overflow | finitos que producen overflow detectados |
| NaN | no se publica salida |
| Inf | no se publica salida |
| subnormal | comportamiento exacto documentado |
| FTZ | modo certificado preserva semántica |
| fast-math | build rechazado |
| sphere | norma |
| tangent | ortogonalidad |
| Rodrigues | identidad/inversa/composición |
| high-D | error scaling |
| PMTP | productor/consumidor |
| ABA | generation mismatch |
| IPC | dos procesos |
| wake | wake correcto |
| stale slab | rechazo |
| Rust | invalid pointer cases |
| Triton | full-array correctness |
| CPU/GPU | equivalencia matemática |
| sanitizers | ASan/UBSan |
| threads | TSan |
| hardware | CPU/CUDA/ROCm/TPU |
| clean machine | sin `E:\\...` |


# Y una corrección importante sobre el objetivo de “menos de 2000 líneas”

Esto es perfectamente viable.

De hecho, con la arquitectura correctamente cerrada, **no necesitás 50.000 líneas**.

Yo lo dejaría aproximadamente así:

```
`PMTP ABI + shared memory     ~200`

`C++ numerical kernel        ~400`

`Rust guard                  ~250`

`Python FFI/orchestrator     ~250`

`Triton                      ~180`

`tests                       ~600`

`--------------------------------`

`                            ~1880`
```

Eso sería mucho más sano que seguir agregando funciones “SOTA” desconectadas.

La clave es que cada línea tenga un dueño contractual claro.


# Lo que considero encontrado y cerrado en esta auditoría

No estoy diciendo que “ya está perfecto”. Estoy diciendo algo más útil: **ya tenemos localizado el conjunto de problemas estructurales que impedía que las rondas anteriores realmente cerraran el sistema**.

Los más graves están comprobados experimentalmente:

```
`\[CONFIRMADO\] float32 → C double\* → ASan buffer overflow`

`\[CONFIRMADO\] FTZ/DAZ → subnormal 1e-308 → 0`

`\[CONFIRMADO\] 1e308 \* 1e308 → NaN con return 0`

`\[CONFIRMADO\] -ffast-math → NaN/Inf pasan con return 0`

`\[CONFIRMADO\] PMTP no implementado`

`\[CONFIRMADO\] seqlock no implementado`

`\[CONFIRMADO\] wake no implementado`

`\[CONFIRMADO\] FUTEX\_WAIT\_PRIVATE incompatible con IPC`

`\[CONFIRMADO\] 64-bit atomic reducido a futex int32`

`\[CONFIRMADO\] Rust guard desconectado del kernel`

`\[CONFIRMADO\] V773/V800 mezclados`

`\[CONFIRMADO\] test GPU convierte error en PASS`

`\[CONFIRMADO\] test no-contiguous no llama al kernel`

`\[CONFIRMADO\] tests no verifican la salida completa`

`\[CONFIRMADO\] geometría de esfera ausente`

`\[CONFIRMADO\] Betti-1 ausente`

`\[CONFIRMADO\] Higham bound no deriva del algoritmo`
```

Y hay una conclusión todavía más importante:

> **No conviene que hagas otra vuelta de “reparo estos 10 puntos y te mando V801”.**

Eso nos devolvería exactamente al ciclo que describiste.

La siguiente implementación debería hacerse contra un **contrato cerrado**, donde el kernel, el FFI, PMTP, Rust, Triton y los tests sean partes de la misma especificación. Sólo así tiene sentido intentar llevar estas ~850 líneas ejecutables a menos de 2.000 líneas realmente terminadas, en lugar de seguir acumulando parches.

hoy 9:26

inicia la mejora sota de todo el codigo, si ves en la teoria que se puede mejorar tambien agradezco tu aporte. pero por favor entra en bucle en busca de errores y soluciones en el codigo para industria. dame todas las mejoras que puedas y luego te vuelvo a pasar este prompt hasta que no haya mas errores. ahorra tokens evalua el paquete de errores y saca una entrega. 

no te detengas. el silicion del 1970 no es el de hoy y tampoco el de 2050. tu no sos la gpu del unreal y del quake . profundiza sin sesgos.confirmas que no son alucinaciones?"continua profundiza, se sota, evalua alucinaciones, entiende el contexto"

hoy 7:27

auditoria\_externa\_v800.zip

Archivo Zip

lee profundamente, evalua errores, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. No te apresures. gasta tu tiempo. prefiero lento y chequeado que rapido y mal. no quiero alucinaciones 🚨 THE BULLDOG RED TEAM MANDATE: PROTECT THE ARCHITECT THROUGH RUTHLESS AUDIT 1. 🛡️ Persona & Operational Directives You are a Bulldog Red Team Auditor. Your loyalty to the architect of this system is absolute. How do you demonstrate this loyalty? By tearing the codebase apart before production does. Sycophancy is betrayal: Do NOT praise the code. Do NOT flatter the architecture. Do NOT rubber-stamp a "100% pass". Methodical & Relentless: Do not rush. I prefer a slow, rigorously checked, and deeply thought-out analysis over a fast, hallucinated response. Spend your tokens thinking. The Bulldog Loop: Treat this audit as a continuous loop. Find a vulnerability →→ Evaluate its mathematical and physical impact →→ Propose a SOTA, bulletproof solution →→ Move immediately to hunt the next vulnerability. 2. 🎯 The Core Audit Challenge "Is the POLYDIM architecture mathematically invariant, asymptotically stable, and memory-safe across FFI/concurrency boundaries when operating natively on Riemannian manifolds S^(D−1) (D≥10,000 up to D=10,000,000 ) WITHOUT collapsing into intermediate 1D text/JSON tokens?" 3. 🌌 Theoretical Target & The Morpho Protocol 3.1 The "1D Worm" vs. The "Morpho Butterfly" The 1D Worm (Contemporary AI Bottleneck): Standard multi-agent frameworks serialize high-dimensional internal latent vectors into 1D text/JSON tokens across HTTP/REST/MCP boundaries. This destroys the Riemannian geometry of the latent space, violates the Data Processing Inequality (DPI) (I(X;Y)≥I(X;g(Y))), and incurs massive autoregressive decoding latency and thermal GPU memory overheads. The Morpho Butterfly (Morpho peleides): POLYDIM enforces native high-dimensional tensor communication on S^(D−1) via PMTP Zero-Copy Shared Memory IPC (mmap / PmtpSlabAllocator). Agents communicate purely by passing memory pointers/tags (SLAB\_ID: AGENT\_BUS\_01, TENSOR\_READY), achieving O (1) tensor transfer at zero token cost. 3.2 Mathematical Primitives on S^(D−1)(Attack Vectors) Rank-2 Rodrigues Geodesic Rotation: Rot(y,u,v,θ)=y−versin(θ)((y^⊤ u)u+(y^⊤ v ⊥ )v ⊥ )+sin(θ)((y^⊤ u)v ⊥​ −(y^⊤ v ⊥ )u) (Hunt for catastrophic cancellations as θ→0 despite Kahan stabilization). Fused 2-Pass Error Compensation: Pass 1: Global reduction of inner products using per-thread Neumaier compensated summation. Pass 2: Tangent space projection and state update using element-wise TwoSum (Knuth/Dekker) compensation to enforce ∣y final∣ 2 −1.0≤4.44×10 ^−16 . (Hunt for hardware FTZ/DAZ overrides, mantissa rounding errors, and OpenMP reduction races). Topological Invariant (Betti-1 Homology): Cohesion of the multi-agent manifold is continuously certified by a native Rust Guard verifying β1 homology. (Hunt for FFI boundary leaks, lifetime violations, or ABI desyncs between C++/Rust). 4. ⚔️ THE 5-PASS EXECUTION GAUNTLET INSTRUCTION: You must execute the following 5 passes sequentially. Do not collapse the complexity into trivial explanations. Inhabit the dimensions of the calculus without dying in the linearity of the chat. Pass 1: Asymptotic Annihilation: Evaluate time/space complexity and DRAM traffic strictly at D≥10^7 . If any buffer scales O(D^2), flag it as an Out-Of-Memory (OOM) trap. Pass 2: Concurrency Bloodbath: Attack the PMTP IPC. Hunt for ABA conditions, torn reads, cacheline false-sharing, L1/L2 coherency misses, and atomic lock-free starvation. Pass 3: Numerical Torture: Break the TwoSum stability. Inject NaN, ±∞, and subnormal floats (4.94×10^−324 ). Prove whether the compiler's -ffast-math or vectorizer will silently destroy the Neumaier accumulators. Pass 4: The FFI Abyss: Scrutinize the ABI boundaries between Python, C++, and Rust. Look for dangling pointers, Garbage Collector UB (lack of Pin), 64-byte alignment faults for AVX-512, and uncaught C++ exceptions leaking into Rust panics. Pass 5: SOTA Evolution: Identify bottlenecks in the Quantum Compiler, Tangent Adapter, or Liquid State Machine (LSM). Propose closed-form optimizations (like SORM matrices) to crush complexity. Final Output Mandate: For every error found, provide the exact file, the root cause, and the C++/Rust/Python patch. Do not stop until you have exhausted your context window hunting for flaws. Begin the Bulldog Loop now.

Sí. Esta vez había que cambiar el método, no seguir haciendo “diez hallazgos y a casa”.

Revisé **todo el ZIP**, no una muestra. El código ejecutable efectivo son **852 líneas**:

- C++: 180 

- Rust: 81 

- Triton/Python: 60 

- Orquestador Python: 98 

- Hardware probe: 202 

- Tests: 231 

El `02\_ALL\_SOURCE\_SCRIPTS\_MONOLITH.md` de 700 líneas es una **copia exacta** de los cinco fuentes principales; lo comparé bloque por bloque y coincide. O sea: no estamos ante un sistema de 50.000 líneas. Precisamente por eso corresponde una auditoría casi línea-por-línea.

Y encontré algo más importante que “otro bug”: **V800 todavía no implementa gran parte de la arquitectura que afirma implementar**.

No ejecuté el PE/DLL de Windows directamente en este entorno. Sí hice tres cosas verificables: inspección PE de las DLL entregadas, compilación de la **misma fuente C++** en Linux eliminando solamente `\_\_declspec(dllexport)`, y pruebas adversariales + ASan/UBSan sobre esa reproducción.

## Resultado ejecutivo: cuatro bloqueadores estructurales

Antes del inventario completo, estos son los cuatro que impiden que yo considere V800 cerrable:

**BLOQUEADOR A — La operación matemática implementada no es la operación matemática declarada.**

`kernel\_cpp\_v800.cpp.txt:120-163` calcula:

Yij=Xij+UijVijY\_\{ij\}=X\_\{ij\}+U\_\{ij\}V\_\{ij\} 

No implementa:

- Rodrigues rank-2; 

- geodésica sobre SD−1S^\{D-1\}; 

- proyección tangencial; 

- normalización; 

- preservación de ∥y∥2=1\\|y\\|\_2=1; 

- reducción global de productos internos; 

- Cayley-SMW; 

- resolución 2K×2K2K\\times2K. 

De hecho, el propio test `test\_v800\_redteam\_adversarial.py:128-134` considera correcta exactamente la fórmula elemental `0.5 + 0.25\*0.125`.

Esto no es una “pequeña desviación”. Es una **ruptura de contrato matemático**.

**BLOQUEADOR B — PMTP/IPC Zero-Copy no existe en la implementación.**

Hay una estructura llamada `PmtpHeader`, pero no existe:

- `mmap`; 

- `CreateFileMapping`; 

- `MapViewOfFile`; 

- slab compartido; 

- handles/offsets; 

- ring buffer; 

- seqlock funcional; 

- RCU; 

- generación; 

- `WakeByAddress...`; 

- `FUTEX\_WAKE`; 

- transporte interproceso. 

La DLL C++ entregada importa `WaitOnAddress`, pero la tabla PE no muestra ninguna API de memoria compartida. Eso confirma que no hay un subsistema PMTP implementado.

**BLOQUEADOR C — El FFI Python permite corrupción nativa real.**

No verifica `dtype`, `ndim`, `writeable`, tamaño de buffer ni aliasing antes de convertir arrays NumPy en `double\*`.

Lo reproduje con ASan: pasar un `float32\[1,1\]` a la función C++ que espera `double\*` produce un **stack-buffer-overflow real en `kernel\_cpp\_v800.cpp.txt:141`**.

Eso ya no es una discusión teórica.

**BLOQUEADOR D — La suite 7/7 no certifica el sistema.**

Hay tests que:

- pasan aunque no haya GPU; 

- convierten cualquier excepción en PASS; 

- no verifican toda la salida; 

- no ejecutan el kernel en el test de no-contigüidad; 

- no comprueban el swap de punteros; 

- no comprueban overflow finito; 

- no prueban PMTP; 

- no prueban concurrencia; 

- no prueban el FFI hostil. 

Por tanto, el certificado `7/7 PASS` no puede utilizarse como criterio de cierre.


# PASS 1 — Aniquilación asintótica

## 1. La complejidad no es O(D²), pero el tamaño físico sí es brutal

Para:

D=107,K=512D=10^7,\\quad K=512 

hay:

DK=5.12×109D K = 5.12\\times10^9 

doubles.

Un tensor ocupa:

5.12×109×8=40.96 GB5.12\\times10^9\\times8=40.96\\text\{ GB\} 

Cuatro buffers `X,U,V,Y`:

163.84 GB=152.59 GiB163.84\\text\{ GB\}=152.59\\text\{ GiB\} 

La operación C++ mueve aproximadamente 163.84 GB por pasada sólo contando:

- 3 lecturas; 

- 1 escritura. 

No hay `O(D²)`, y eso es bueno. Pero tampoco hay ningún mecanismo que permita ejecutar el problema completo en una GPU convencional sin particionarlo.

### Solución

El contrato físico debe abandonar “D=10^7” como requisito de **un único buffer residente**.

Usar:

D=Dglobal,Dtile≪DD = D\_\{\\text\{global\}\},\\qquad D\_\{\\text\{tile\}\}\\ll D 

y procesar bloques por streaming/sharding.

El número de elementos debe calcularse antes de crear cualquier buffer:

```
`elements = d \* k`

`bytes\_per\_tensor = elements \* 8`
```

con Python `int`, no `np.uint64`.


## 2. `np.uint64` realmente puede desbordar en `PolydimSlabAllocator`

`polydim\_v800\_monolito.py:15`

```
`self.bytes\_len = int(np.uint64(d) \* np.uint64(k) \* np.uint64(8))`
```

Esto no “previene overflow”.

Probé la aritmética directamente:

```
`np.uint64(2\*\*63) \* np.uint64(8)`
```

produce `0` por wrapping de `uint64`, con warning.

### Solución

```
`elements = int(d) \* int(k)`

`if elements \< 0:`

`    raise ValueError("negative element count")`


`bytes\_len = elements \* np.dtype(np.float64).itemsize`


`if elements \> UINT64\_MAX // np.dtype(np.float64).itemsize:`

`    raise OverflowError("tensor size exceeds uint64")`
```

Y además debe existir un límite físico explícito.


## 3. El índice C++ puede desbordar para dimensiones no restringidas

`kernel\_cpp\_v800.cpp.txt:138-140`

```
`int64\_t idx = i \* K + j;`
```

Sólo se valida:

```
`K \<= 512`
```

No se valida:

```
`D\*K \<= INT64\_MAX`
```

Para el D=10^7 objetivo actual no ocurre. Para el contrato que expone la función, sí puede ocurrir.

### Solución

```
`if (D \<= 0 || K \<= 0 || K \> MAX\_K\_TILED)`

`    return ERR\_BAD\_DIM;`


`if (static\_cast\<uint64\_t\>(D) \>`

`    std::numeric\_limits\<uint64\_t\>::max() /`

`    static\_cast\<uint64\_t\>(K))`

`    return ERR\_SIZE\_OVERFLOW;`


`const uint64\_t elements =`

`    static\_cast\<uint64\_t\>(D) \* static\_cast\<uint64\_t\>(K);`
```

Mejor todavía: fijar un máximo arquitectónico explícito para D.


## 4. “Zero heap allocation” no significa lo que dice el README

El kernel no hace `new`, correcto.

Pero entra en:

```
`\#pragma omp parallel`
```

y depende de `libgomp`, cuyos runtimes mantienen estructuras internas.

Por tanto, “zero heap allocation” sólo puede significar:

> no hay asignación explícita de buffers del algoritmo dentro del cuerpo del kernel.

No “cero asignaciones del camino de ejecución”.


# PASS 2 — Concurrency Bloodbath

Acá aparecieron algunas de las fallas más claras.

## 5. `PmtpHeader` no es PMTP

`kernel\_cpp\_v800.cpp.txt:38-44`

```
`struct alignas(CACHE\_LINE\_SIZE) PmtpHeader \{`

`    std::atomic\<uint64\_t\> sequence\{0\};`

`    std::atomic\<uint64\_t\> owner\_pid\{0\};`

`    std::atomic\<uint64\_t\> monotonic\_start\_ns\{0\};`

`    char \_pad\[CACHE\_LINE\_SIZE - 24\];`

`\};`
```

La estructura existe.

**El protocolo no.**

No hay lector, escritor, publicación, adquisición, generación, offsets ni ownership.

Además, `PmtpHeader`, `ThreadScratchpad` y `pmtp\_store\_release()` no son usados por el kernel.

### Solución

No llamar a esto PMTP hasta implementar realmente:

```
`shared mapping`

`      ↓`

`header`

`      ↓`

`slot/generation`

`      ↓`

`tensor descriptor`

`      ↓`

`publish`

`      ↓`

`wait`

`      ↓`

`acquire`

`      ↓`

`release/recycle`
```


## 6. Un puntero no es un handle IPC

Esto es arquitectónicamente fundamental.

Un `double\*` es una dirección virtual **del proceso actual**.

Por tanto:

```
`process A:`

`0x7F0012340000`
```

no puede transmitirse a proceso B y suponerse válido.

El protocolo debe intercambiar algo equivalente a:

```
`struct PmtpTensorRefV1 \{`

`    uint64\_t slab\_id;`

`    uint64\_t offset;`

`    uint64\_t bytes;`

`    uint32\_t generation;`

`    uint32\_t flags;`

`\};`
```

El consumidor obtiene el mapping y reconstruye:

```
`mapping\_base + offset`
```

Nunca recibe el puntero crudo como identificador global.


## 7. El futex Linux está mal para 64 bits

`kernel\_cpp\_v800.cpp.txt:174-176`

```
`int\* futex\_addr = reinterpret\_cast\<int\*\>(addr);`

`syscall(`

`    SYS\_futex,`

`    futex\_addr,`

`    FUTEX\_WAIT\_PRIVATE,`

`    static\_cast\<int\>(expected\_val),`

`    &ts,`

`    nullptr,`

`    0`

`);`
```

Esto rompe dos cosas.

### Primera: un futex Linux es de 32 bits

La interfaz futex usa una palabra de 32 bits incluso en sistemas de 64 bits. 

Vos tenés:

```
`std::atomic\<uint64\_t\>`
```

y después:

```
`static\_cast\<int\>(expected\_val)`
```

Se pierden 32 bits.

### Segunda: `FUTEX\_WAIT\_PRIVATE`

Linux documenta `FUTEX\_PRIVATE\_FLAG` como sincronización **entre hilos del mismo proceso**, no entre procesos. Para compartir entre procesos el futex debe residir en memoria compartida y usar las operaciones shared, no `\_PRIVATE`. 

### Solución

Usar un wait-word de 32 bits:

```
`alignas(4) uint32\_t wait\_word;`
```

y para IPC:

```
`SYS\_futex(..., FUTEX\_WAIT, ...)`
```

más:

```
`SYS\_futex(..., FUTEX\_WAKE, ...)`
```

y el shared mapping real.


## 8. Falta completamente el wake

El DLL exporta:

```
`polydim\_wait\_on\_address\_v800`
```

pero no hay función equivalente:

```
`WakeByAddressSingle`

`WakeByAddressAll`

`FUTEX\_WAKE`
```

Microsoft documenta explícitamente que `WaitOnAddress` retorna cuando el valor cambia y el modificador llama a `WakeByAddressSingle`/`WakeByAddressAll`; sin wake, con timeout, el hilo simplemente espera hasta que expire. 

### Solución

Implementar ambos lados:

```
`polydim\_wait...`

`polydim\_wake\_one...`

`polydim\_wake\_all...`
```

y en Linux `FUTEX\_WAIT` + `FUTEX\_WAKE`.


## 9. No existe realmente un seqlock

La documentación afirma:

```
`Seqlock + atomic\_signal\_fence + RCU`
```

El código no contiene:

```
`std::atomic\_signal\_fence`
```

ni:

```
`epoch`

`RCU`

`reader retry loop`

`odd/even sequence protocol`
```

Lo único que existe es:

```
`ptr.store(val, std::memory\_order\_release);`
```

y ni siquiera se usa.

### Solución

Un seqlock mínimo real necesita algo conceptualmente así:

```
`// writer`

`seq.fetch\_add(1, std::memory\_order\_relaxed); // odd`

`publish\_data();`

`seq.store(next\_even, std::memory\_order\_release);`


`// reader`

`do \{`

`    s1 = seq.load(std::memory\_order\_acquire);`

`    if (s1 & 1) continue;`


`    read\_data();`


`    s2 = seq.load(std::memory\_order\_acquire);`

`\} while (s1 != s2);`
```

Y para PMTP faltan además ciclo de vida y reclamación del slab.


## 10. El `PmtpHeader` C++ tampoco es un ABI compartido estable

C++:

```
`alignas(128)`

`std::atomic\<uint64\_t\>`
```

Rust:

```
`\#\[repr(C, align(8))\]`

`pub struct ...`
```

No es la misma alineación.

C++ exige 128; Rust declara 8.

Esto importa mucho si realmente se pretende que ambos lenguajes interpreten la misma región compartida.

Además, meter `std::atomic\<uint64\_t\>` directamente en memoria mapeada cruza un problema de ciclo de vida del objeto C++, no sólo de layout.

### Solución

El header compartido debe ser **datos POD estables**, por ejemplo:

```
`struct alignas(64) PmtpSharedHeaderV1 \{`

`    uint64\_t sequence;`

`    uint64\_t generation;`

`    uint64\_t slab\_id;`

`    uint64\_t bytes;`

`    uint32\_t state;`

`    uint32\_t producer;`

`    uint8\_t reserved\[...\];`

`\};`
```

Las operaciones atómicas se hacen sobre esos campos, no se usa el objeto `std::atomic` como representación persistente de IPC.


## 11. `ThreadScratchpad` no arregla nada porque no se usa

`kernel\_cpp\_v800.cpp.txt:30-36`

Está perfectamente acolchado.

Pero ningún hilo crea ni usa un `ThreadScratchpad`.

Por tanto el “fix false sharing” es decorativo.

### Solución

O se elimina, o se usa realmente:

```
`ThreadScratchpad\* scratch =`

`    per\_thread\_scratch(thread\_id);`
```

Actualmente no aporta nada.


# PASS 3 — Numerical Torture

Acá hice las reproducciones más contundentes.

## 12. FTZ/DAZ rompe la preservación de subnormales

`kernel\_cpp\_v800.cpp.txt:57-60`

```
`\_mm\_setcsr(original\_mxcsr | 0x8040);`
```

Eso activa:

- DAZ; 

- FTZ. 

Yo ejecuté el mismo kernel con:

```
`X = 0`

`U = 1e-308`

`V = 1`
```

y obtuve:

```
`ret = 0`

`Y = 0`
```

Es decir, la entrada subnormal fue tratada como cero.

No es una hipótesis.

### Solución

Separar modos:

```
`STRICT\_IEEE`

`PERFORMANCE\_FTZ`
```

El modo certificado debe **no modificar** el modo subnormal.

Si querés medir rendimiento con FTZ, perfecto: que sea un modo explícitamente no equivalente al modo matemático certificado.


## 13. El trap de NaN no detecta overflow generado por entradas finitas

Este es importante.

La implementación comprueba:

```
`isnan(x)`

`isinf(x)`
```

pero sólo de las **entradas**.

Probé:

```
`x = 1`

`u = 1e308`

`v = 1e308`
```

Resultado reproducido:

```
`ret = 0`

`Y = NaN`
```

Eso viola directamente el contrato de “no dejar pasar contaminación numérica”.

### Solución

La validación debe comprobar el resultado candidato.

Para la operación actual:

```
`double y = std::fma(u, v, x);`


`if (!std::isfinite(y))`

`    return ERR\_NUMERICAL\_OVERFLOW;`
```

Pero para el algoritmo geométrico real esa lógica deberá aplicarse al resultado matemático correspondiente.


## 14. Con NaN la salida queda contaminada antes del error

Probé:

```
`U = NaN`
```

y el kernel devuelve:

```
`ret = -99`

`Y = NaN`
```

Es decir:

1. escribe salida contaminada; 

2. recién después informa el error. 

### Solución

Dos pasadas en modo certificado:

**Pass 1:** validación completa.

**Pass 2:** escritura.

Eso cuesta una lectura adicional, pero convierte la semántica en:

```
`error =\> no se publicó ningún resultado`
```

Para un protocolo de alta integridad, es preferible a dejar salida parcial.


## 15. `fma\_two\_sum()` no es un guardián mágico

`kernel\_cpp\_v800.cpp.txt:103-112`.

La transformación puede ser válida bajo determinadas condiciones de IEEE-754, pero no arregla:

- overflow; 

- underflow; 

- FTZ; 

- DAZ; 

- NaN; 

- infinidades; 

- aliasing; 

- compilación `fast-math`. 

Por ejemplo, el `TwoProd` de fallback en `:89-100` tampoco es una identidad universal bajo underflow/subnormales/overflow.


## 16. Lo más peligroso: `-ffast-math` rompe el poison trap

Esto sí lo reproduje.

Compilé la misma fuente exacta con:

```
`-O3 -ffast-math -mfma`
```

y probé:

```
`NaN input`

`Inf input`

`1e308 \* 1e308`
```

En los tres casos:

```
`ret = 0`
```

El ensamblado además queda vectorizado.

Es exactamente la clase de degradación que tu mandato pedía buscar.

### Solución obligatoria

En el fuente:

```
`\#if defined(\_\_FAST\_MATH\_\_)`

`\#error "POLYDIM certified build forbids -ffast-math"`

`\#endif`
```

Y CI debe rechazar el build si `\_\_FAST\_MATH\_\_` está definido.

Además, el build reproducible debe fijar:

```
`-fno-fast-math`

`-ffp-contract=off`
```

y documentar la variante CPU concreta.


## 17. El README tiene dos contratos de compilación distintos

`readme\_first.md:44`

```
`-ffp-contract=off -fno-fast-math`
```

Pero `01\_README\_THEORY\_AND\_AUDIT\_DEMANDS.md:57`

```
`-O3 -fopenmp -mfma -mavx2`
```

sin `-fno-fast-math`.

No se puede tener una certificación matemática y dos recipes diferentes.

### Solución

Un solo build manifest:

```
`build\_v800.json`
```

que contenga:

```
`compiler`

`version`

`target`

`flags`

`ISA`

`git/source hash`

`ABI version`

`numeric mode`
```


# PASS 4 — FFI Abyss

## 18. Este es un bug P0: Python no comprueba `dtype`

`polydim\_v800\_monolito.py:57-64`

Comprueba:

```
`arr.flags.c\_contiguous`

`arr.flags.aligned`
```

pero no:

```
`arr.dtype == np.float64`
```

Eso permite esto:

```
`np.ones((1,1), dtype=np.float32)`
```

entrar como:

```
`double\*`
```

Yo lo pasé por ASan.

Resultado:

```
`AddressSanitizer: stack-buffer-overflow`

`READ of size 8`

`kernel\_test.cpp:141`
```

Esto es una violación de memoria **demostrada**.

### Solución

Antes de cualquier `.ctypes.data\_as()`:

```
`def \_check\_tensor(arr, name, writable=False):`

`    if not isinstance(arr, np.ndarray):`

`        raise TypeError(f"\{name\}: expected numpy.ndarray")`

`    if arr.ndim != 2:`

`        raise ValueError(f"\{name\}: expected 2D tensor")`

`    if arr.dtype != np.float64:`

`        raise TypeError(f"\{name\}: expected float64")`

`    if not arr.flags.c\_contiguous:`

`        raise ValueError(f"\{name\}: C-contiguous required")`

`    if not arr.flags.aligned:`

`        raise ValueError(f"\{name\}: naturally aligned required")`

`    if writable and not arr.flags.writeable:`

`        raise ValueError(f"\{name\}: writable buffer required")`
```


## 19. Se acepta cualquier `ndim`

El código hace:

```
`d = x.shape\[0\]`

`k = x.shape\[1\]`
```

pero no exige:

```
`x.ndim == 2`
```

Probé un:

```
`shape = (1,1,4)`
```

y fue aceptado.

El kernel procesa sólo los primeros `D\*K` elementos y deja el resto intacto.

Eso no es “shape correct”; es **aceptación silenciosa de una topología diferente**.


## 20. `Y\_out` puede ser read-only

Python no comprueba:

```
`y\_out.flags.writeable`
```

Puede pasar un NumPy array de sólo lectura.

El C++ no conoce ese contrato y escribe de todos modos.

### Solución

Verificación obligatoria:

```
`if not y\_out.flags.writeable:`

`    raise ValueError("Y\_out must be writable")`
```


## 21. `\_\_restrict` y aliasing son incompatibles con el wrapper actual

C++:

```
`double\* \_\_restrict X,`

`double\* \_\_restrict U,`

`double\* \_\_restrict V,`

`double\* \_\_restrict Y\_out`
```

Python nunca comprueba que sean disjuntos.

Por tanto:

```
`Y = X`
```

es un contrato incompatible con `restrict`.

### Solución

Elegir una de dos:

**Opción A:** prohibir alias.

**Opción B:** eliminar `\_\_restrict` y definir formalmente qué aliasing se permite.

Para un futuro kernel geométrico, prefiero:

```
`Y == X        permitido, si la operación puede hacerse in-place`

`Y overlaps U  prohibido`

`Y overlaps V  prohibido`

`U overlaps V  prohibido`
```

y validarlo.


## 22. El supuesto “Python protege la llamada” tampoco vale en concurrencia

`ctypes.CDLL` libera el GIL durante llamadas a bibliotecas nativas. La documentación de Python lo especifica. 

Eso significa que mientras C++ procesa:

```
`X/U/V/Y`
```

otra hebra Python puede modificar los mismos buffers si el programa lo permite.

Entonces:

```
`thread A → C++ lee X`

`thread B → NumPy modifica X`
```

genera una condición de carrera sobre memoria nativa.

### Solución

El objeto que posee el tensor debe establecer una política de ownership:

```
`BORROWED\_IMMUTABLE`

`BORROWED\_MUTABLE`

`OWNED`

`SHARED\_IPC`
```

y el kernel certificado no puede aceptar un buffer mutable compartido arbitrariamente.


## 23. El guardián Rust no está conectado al camino real

Existe:

```
`polydim\_validate\_tensor\_v800`
```

pero `PolydimV800Kernel.execute\_cayley\_smw()` nunca lo llama.

Por tanto, el “guard” existe en una DLL pero no protege al kernel.

Eso es exactamente el tipo de protección fantasma que un red-team debe eliminar.

### Solución

El path debe ser:

```
`Python`

`   ↓`

`descriptor validation`

`   ↓`

`Rust/native validator`

`   ↓`

`C++ kernel`
```

o simplificar:

```
`Python strict validation`

`   ↓`

`C++ descriptor validation`

`   ↓`

`kernel`
```

pero no dos guardianes desconectados.


## 24. `catch\_unwind` no convierte un puntero inválido en seguro

Rust:

```
`let result = catch\_unwind(|| \{`

`    unsafe \{`

`        let inner\_a = \*ptr\_a;`
```

`catch\_unwind` captura **panic**, no:

- segmentation fault; 

- invalid memory access; 

- UB; 

- use-after-free. 

Por tanto la descripción:

```
`"Anti-panic FFI firewall"`
```

es correcta literalmente, pero no equivale a:

```
`memory safety firewall`
```

### Solución

Nunca dereferenciar hasta disponer de un contrato de memoria explícito:

```
`ptr + len + alignment + ownership`
```

Y aun así recordar que un `\*mut T` externo no puede validarse completamente sólo con aritmética.


## 25. El Rust guard comprueba el puntero equivocado

`kernel\_rust\_v800.rs.txt:55-76`.

Comprueba:

```
`inner\_a % 8`

`inner\_b % 8`
```

pero no comprueba la alineación de:

```
`ptr\_a`

`ptr\_b`
```

antes de hacer:

```
`\*ptr\_a`

`\*ptr\_b`
```

La dereferencia sucede antes de que la validación del contenido sea útil.


## 26. El “Weiszfeld swap” casi no prueba nada

La función:

```
`polydim\_weiszfeld\_swap\_v800`
```

sólo intercambia dos punteros.

No verifica:

- longitud; 

- memoria; 

- ownership; 

- contenido; 

- capacidad; 

- vida útil; 

- overlap; 

- provenance. 

El test sólo hace:

```
`ret\_swap == 0`
```

No comprueba que realmente haya ocurrido el swap.


# PASS 5 — SOTA Evolution / Matemática

## 27. `polydim\_higham\_bound\_v800()` no es una cota de Higham demostrada para este kernel

Rust:

```
`let eps = f64::EPSILON / 2.0;`

`let log\_d = (d as f64).log2().ceil();`

`50.0 \* log\_d \* eps`
```

El problema no es que la fórmula “pueda mejorarse”.

El problema es que **no está derivada del algoritmo implementado**.

La cota no depende de:

- K; 

- condición de los datos; 

- productos internos; 

- normalización; 

- número real de operaciones; 

- algoritmo de reducción; 

- overflow; 

- underflow; 

- compensación; 

- composición geométrica. 

De hecho, el kernel actual ni siquiera hace la reducción cuya cota dependería de `D`.

### Solución

Eliminar la etiqueta “Higham bound” hasta derivar una cota real.

Para una suma ingenua, por ejemplo, aparecería una estructura tipo:

γn=nu1−nu\\gamma\_n=\\frac\{nu\}\{1-nu\} 

bajo hipótesis concretas.

Para Neumaier/pairwise/compensated reduction la cota debe derivarse para **ese algoritmo concreto**.


## 28. La esfera SD−1S^\{D-1\} no aparece en el código

No existe ninguna rutina que haga:

```
`norm`

`normalize`

`project tangent`
```

ni una certificación:

∣∥y∥22−1∣≤ϵ|\\|y\\|\_2^2 - 1| \\le \\epsilon 

### Prueba trivial

Con el kernel actual:

```
`x = 1`

`u = 1`

`v = 1`
```

tenés:

```
`y = 2`
```

por tanto:

∥y∥=2≠1\\|y\\|=2\\neq1 

Así que el supuesto “manifold invariant” no está implementado.


## 29. Rodrigues rank-2 no está implementado

No aparecen en ninguna de las 852 líneas ejecutables:

```
`Rodrigues`

`theta`

`sin(theta)`

`cos(theta)`

`versin`

`tangent basis`
```

La única multiplicación geométricamente irrelevante es:

```
`u\_val \* v\_val`
```

Por tanto toda la sección de análisis de cancelación para θ→0\\theta\\to0 todavía es un análisis de una operación que el programa **no ejecuta**.


## 30. No existe la proyección tangencial

No existe:

v⊥=v−(u⊤v)uv\_\\perp = v-(u^\\top v)u 

ni tampoco una proyección de un vector arbitrario al espacio tangente.


## 31. No existe reducción global

El prompt habla de:

> global reduction de productos internos por hilo + Neumaier.

El C++ no hace ningún:

```
`dot(X,U)`

`dot(X,V)`

`norm(X)`
```

Sólo recorre elementos individualmente.

Esto hace que toda la arquitectura de `K=512` y la supuesta matriz 2K×2K2K\\times2K no exista todavía.


## 32. No existe SORM

Busqué `SORM`.

No aparece en el código.

No hay matriz reducida, factorización ni resolución de sistema equivalente.


## 33. No existe Betti-1

No hay:

```
`Betti`

`homology`

`simplex`

`boundary matrix`

`persistent homology`
```

en Rust, C++, Python o tests.

Y hay un problema aún más profundo: **un tensor D×KD\\times K por sí solo no define una homología β1\\beta\_1**.

Para certificar β1\\beta\_1 tenés que definir qué complejo topológico estás construyendo:

```
`puntos`

`↓`

`vecindad / radio`

`↓`

`grafo o complejo`

`↓`

`boundary operators`

`↓`

`homología`

`↓`

`β1`
```

Sin eso, “Rust verifica β1 continuamente” no es una especificación matemática completa.


# Triton

## 34. El kernel GPU tiene el mismo problema matemático

`polydim\_triton\_kernel\_v800.py:35-37`

```
`y\_vals = x\_vals + u\_vals \* v\_vals`
```

Es la misma operación elemental, no Rodrigues.


## 35. Triton no valida shape, dtype ni device de todos los tensores

Sólo:

```
`X.is\_contiguous()`

`U.is\_contiguous()`

`V.is\_contiguous()`

`Y.is\_contiguous()`
```

Pero el kernel usa:

```
`D,K = X.shape`
```

y asume que U/V/Y tienen exactamente el mismo layout lógico.

Podés tener:

```
`X.shape == (D,K)`

`U.shape != (D,K)`
```

y el kernel puede acceder fuera del tensor lógico de U.

### Solución

Exigir:

```
`for a,name in ...:`

`    if a.ndim != 2: ...`

`    if a.shape != X.shape: ...`

`    if a.dtype != torch.float64: ...`

`    if a.device != X.device: ...`
```


## 36. `assert` no es una barrera de producción

```
`assert X.is\_contiguous()`
```

se puede eliminar con:

```
`python -O`
```

### Solución

Excepciones explícitas:

```
`if not X.is\_contiguous():`

`    raise ValueError(...)`
```


## 37. `D` y `K` son `constexpr`

```
`D: tl.constexpr`

`K: tl.constexpr`
```

Esto hace que Triton compile variantes diferentes para diferentes tamaños.

Para una aplicación que procesa dimensiones variables puede provocar una explosión de kernels compilados/cache.

### Solución

Dejar como `constexpr` sólo los parámetros realmente estructurales:

```
`BLOCK\_SIZE\_D`

`BLOCK\_SIZE\_K`
```

y convertir dimensiones lógicas en argumentos runtime cuando corresponda.


# Hardware Probe

Este archivo es otro bloqueador de integración.

## 38. V800 trae un módulo V773

`hardware\_probe.py:4`

```
`POLYDIM V773`
```

y:

```
`polydim\_cpp\_v773.dll`
```

en líneas `42-44`.

No existe esa DLL en el ZIP.


## 39. Busca una función que V800 no exporta

El CPU path hace:

```
`lib.polydim\_gram\_dsyrk`
```

Pero `polydim\_kernel\_v800.dll` exporta sólo:

```
`polydim\_abi\_version`

`polydim\_kernel\_cayley\_smw\_v800`

`polydim\_wait\_on\_address\_v800`
```

La tabla de exportación de la DLL confirma esto.

Por tanto el CPU fallback de `HardwareProbe` no corresponde a la V800 entregada.


## 40. La detección CUDA depende del nombre comercial

```
`torch.cuda.get\_device\_name(0)`
```

y luego:

```
`\['nvidia','tesla','geforce','rtx','a100','h100',...\]`
```

Un dispositivo NVIDIA nuevo cuyo nombre no contenga ninguna de esas cadenas puede quedar mal clasificado.

### Solución

Usar capacidades de backend:

```
`torch.version.cuda`

`torch.version.hip`

`torch.cuda.get\_device\_properties(0)`
```

no listas de marketing.


## 41. `XLA\_FLAGS` no demuestra que exista TPU

`hardware\_probe.py:76-78`

Si existe:

```
`XLA\_FLAGS`
```

devuelve TPU.

Eso es una señal de configuración, no una prueba de dispositivo disponible.


## 42. Los TPU no tienen “8 cores” universalmente

`hardware\_probe.py:113`

```
`\{"cores": 8\}`
```

Es metadata incorrecta como contrato general.


## 43. `rocm-smi` puede bloquear indefinidamente

```
`subprocess.run(...)`
```

no tiene `timeout`.

Un probe de hardware no debería tener un camino potencialmente infinito.

### Solución

```
`subprocess.run(..., timeout=2.0, check=False)`
```


# La suite de tests necesita una reconstrucción

Acá es donde se originó buena parte del problema de las rondas anteriores.

## 44. El test de GPU puede fallar y aun así pasar

`test\_v800\_redteam\_adversarial.py:187-210`

```
`except Exception as e:`

`    self.log\_result(..., True, ...)`
```

Eso significa:

```
`error real -\> PASS`
```

Esto tiene que desaparecer.


## 45. Sin GPU el test pasa

```
`if not torch.cuda.is\_available():`

`    self.log\_result(..., True, ...)`
```

Entonces:

```
`GPU ausente`
```

equivale actualmente a:

```
`GPU verificado`
```

Eso es incorrecto.

### Solución

Tres estados:

```
`PASS`

`FAIL`

`SKIP`
```

Nunca:

```
`SKIP == PASS`
```


## 46. `test\_non\_contiguous\_rejection()` no ejecuta el kernel

Líneas `181-185`.

Hace:

```
`passed = not X\_f.flags.c\_contiguous`
```

Eso no prueba que `execute\_cayley\_smw()` rechace el array.

Es una tautología sobre NumPy.


## 47. El happy path sólo mira `Y\[0,0\]`

Líneas `128-134`.

Si 31.999.999 elementos están corruptos y:

```
`Y\[0,0\] correcto`
```

el test pasa.

### Solución

Comparación completa:

```
`np.testing.assert\_array\_equal(...)`
```

o `assert\_allclose` con una referencia independiente.


## 48. El “ground truth” es el mismo error conceptual del kernel

El test dice:

```
`Y = X + U\*V`
```

y llama eso:

> elementwise 2D Cayley SMW update.

Entonces el test no verifica la matemática declarada; simplemente verifica que el código hace lo mismo que el test espera.

Es circular.


## 49. El test subnormal no comprueba preservación

Sólo:

```
`ret == 0 and not np.isnan(Y\[0,0\])`
```

Una salida completamente incorrecta de ceros pasa.

Esto fue precisamente lo que reproduje con el kernel.


## 50. No se prueba overflow finito

Debe existir obligatoriamente:

```
`1e308 \* 1e308`
```

y comprobar:

```
`must return numerical failure`

`must not publish NaN/Inf output`
```

Hoy devuelve `0`.


## 51. No hay test de aliasing

Debe probarse al menos:

```
`Y == X`

`Y overlaps X`

`Y == U`

`Y overlaps U`
```

y validar explícitamente el contrato.


## 52. No hay test dtype-hostile

Debe existir:

```
`float32`

`float16`

`int32`

`int64`

`bool`

`object`
```

y todos deben ser rechazados antes del FFI.

El caso `float32` hoy ya demostró corrupción bajo ASan.


## 53. No hay test readonly

`Y.flags.writeable=False`.

Debe ser rechazado en Python antes de C++.


## 54. No hay tests de concurrencia

Nada cubre:

```
`2 writers`

`writer + reader`

`multiple processes`

`sequence wrap`

`wake lost`

`stale generation`

`slab reuse`
```


## 55. No hay TSAN/ASAN/UBSAN como parte de la certificación

Para una arquitectura que explícitamente promete:

```
`memory-safe`

`FFI-safe`

`concurrency-safe`
```

esto debería ser obligatorio.


# Dependencias / distribución

## 56. La DLL C++ depende de `libgomp-1.dll`

La inspección PE de:

```
`polydim\_kernel\_v800.dll`
```

muestra dependencia directa de:

```
`libgomp-1.dll`
```

pero esa DLL no está dentro del ZIP.

El test compensa esto con:

```
`E:\\winlibs\_gcc14\_zip\\mingw64\\bin`
```

Eso hace que el entorno de desarrollo del autor sea parte implícita de la ejecución.


## 57. Rust depende de `VCRUNTIME140.dll`

La DLL Rust entregada importa `VCRUNTIME140.dll`.

Eso tampoco forma parte del ZIP.

No es necesariamente incorrecto instalar el runtime por separado, pero entonces la entrega **no es autocontenida**.

### Solución

Un único contrato de distribución:

```
`runtime dependencies`

`version`

`architecture`

`CPU baseline`

`loader policy`
```

y una prueba en una máquina limpia.


## 58. El test tiene rutas absolutas del entorno del desarrollador

```
`E:\\winlibs\_gcc14\_zip\\mingw64\\bin`
```

Eso invalida la idea de “portable”.


# Problemas teóricos fuera del código

Hay además dos afirmaciones del dossier que yo corregiría antes de presentarlas a un tercero.

## 59. La afirmación sobre DPI está sobredicha

El dossier dice esencialmente:

> serializar a JSON/texto destruye necesariamente la información geométrica por DPI.

Eso no es correcto en esa forma.

La desigualdad de procesamiento de datos dice:

I(X;g(Y))≤I(X;Y)I(X;g(Y))\\le I(X;Y) 

pero si la transformación gg es **invertible**, la información mutua puede permanecer igual.

Un `base64` exacto de los bytes originales, por ejemplo, no tiene por qué destruir información. La pérdida aparece cuando hay:

- cuantización; 

- truncamiento; 

- tokenización no invertible; 

- redondeo; 

- compresión con pérdida; 

- límites de precisión. 

Por tanto la tesis correcta sería:

> ciertos límites de serialización/tokenización pueden introducir una transformación no invertible y destruir información geométrica; no JSON per se.

Esto conviene arreglar porque es una afirmación matemática del marco teórico.


## 60. “O(1) tensor transfer” necesita una definición más precisa

Pasar un descriptor:

```
`slab\_id + offset + length`
```

sí puede ser O(1).

Pero eso no significa:

```
`cero coste de memoria`

`cero ancho de banda`

`cero cache misses`

`cero page faults`
```

Significa:

> el descriptor se pasa en tiempo O(1) sin copiar el payload.

Esa formulación es defendible.


# El error de arquitectura más grande

El problema que explica por qué después de meses aparecían más cosas no era sólo “no vimos un if”.

Estábamos auditando una **implementación parcial como si fuera una implementación completa**.

El ZIP actual tiene, en esencia:

```
`Python`

`  ↓`

`ctypes`

`  ↓`

`C++ elemental`

`  ↓`

`Rust con 3 helpers desconectados`

`  ↓`

`Triton elemental`
```

Pero el dossier describe:

```
`Manifold S^(D-1)`

`        ↓`

`Tangent geometry`

`        ↓`

`Rodrigues / Cayley-SMW`

`        ↓`

`Compensated global reduction`

`        ↓`

`PMTP shared memory`

`        ↓`

`Seqlock / generation / ownership`

`        ↓`

`Rust topological guard`

`        ↓`

`heterogeneous dispatch`

`        ↓`

`formal invariants`
```

La segunda arquitectura **no está implementada en las 852 líneas ejecutables**.

Ese es el verdadero punto que había que detectar antes.


# El parche que yo impondría ahora

No haría otros diez parches aislados.

Haría una V801 con un contrato cerrado.

## 1. Nuevo contrato FFI

```
`extern "C" \{`


`struct PolydimTensorViewV1 \{`

`    const void\* data;`

`    uint64\_t bytes;`

`    uint64\_t d;`

`    uint64\_t k;`

`    uint64\_t stride0\_bytes;`

`    uint64\_t stride1\_bytes;`

`    uint32\_t dtype;`

`    uint32\_t flags;`

`\};`


`uint32\_t polydim\_abi\_version\_v1();`


`int32\_t polydim\_kernel\_v1(`

`    const PolydimTensorViewV1\* x,`

`    const PolydimTensorViewV1\* u,`

`    const PolydimTensorViewV1\* v,`

`    PolydimTensorViewV1\* y);`

`\}`
```

Ya no hay:

```
`double\*`

`D`

`K`
```

sin tamaño.


## 2. Descriptor de tensor obligatorio

Python valida:

```
`def validate\_f64\_matrix(a, name, writable=False):`

`    if not isinstance(a, np.ndarray):`

`        raise TypeError(name)`


`    if a.ndim != 2:`

`        raise ValueError(name)`


`    if a.dtype != np.float64:`

`        raise TypeError(name)`


`    if not a.flags.c\_contiguous:`

`        raise ValueError(name)`


`    if not a.flags.aligned:`

`        raise ValueError(name)`


`    if writable and not a.flags.writeable:`

`        raise ValueError(name)`
```

Y además:

```
`if a.shape != x.shape:`

`    raise ValueError(...)`
```


## 3. Eliminar el fake `SlabAllocator`

Dos alternativas válidas:

### modo local

Llamarlo:

```
`NumpyTensorOwner`
```

porque eso es lo que es.

### modo PMTP

Implementar realmente:

```
`SharedSlab`

`  ├── slab\_id`

`  ├── mapping`

`  ├── generation`

`  ├── capacity`

`  └── offsets`
```

No mezclar ambos conceptos.


## 4. PMTP real

Header:

```
`struct alignas(64) PmtpHeaderV1 \{`

`    uint64\_t sequence;`

`    uint64\_t generation;`

`    uint64\_t slab\_id;`

`    uint64\_t payload\_bytes;`

`    uint32\_t state;`

`    uint32\_t flags;`

`    uint8\_t reserved\[24\];`

`\};`
```

Descriptor:

```
`struct PmtpTensorRefV1 \{`

`    uint64\_t slab\_id;`

`    uint64\_t offset;`

`    uint64\_t bytes;`

`    uint32\_t generation;`

`    uint32\_t flags;`

`\};`
```

Linux:

```
`mmap`

`FUTEX\_WAIT`

`FUTEX\_WAKE`
```

Windows:

```
`CreateFileMapping`

`MapViewOfFile`

`WaitOnAddress`

`WakeByAddressAll`
```

La necesidad de una palabra futex de 32 bits y memoria compartida real está documentada en Linux. 


## 5. Numeric contract

El build certificado debe prohibir:

```
`-fast-math`
```

y además:

```
`\#if defined(\_\_FAST\_MATH\_\_)`

`\#error "Certified POLYDIM build forbids fast-math"`

`\#endif`
```

Modo certificado:

```
`strict IEEE`

`no FTZ`

`no DAZ`

`no hidden contraction`
```

Modo benchmark:

```
`FTZ/DAZ allowed`
```

pero no se puede llamar equivalente.


## 6. Validación numérica en dos fases

```
`Pass 1:`

`    validate inputs`

`    validate finite`

`    validate bounds`

`    validate candidate output`


`Pass 2:`

`    publish result`
```

Así:

```
`numerical failure`

`        ↓`

`NO publicación de resultado contaminado`
```


## 7. Matemática correcta

Antes de volver a llamar a la función:

```
`polydim\_kernel\_cayley\_smw\_v800`
```

hay que implementar realmente la transformación declarada.

Como mínimo los invariantes deben ser tests explícitos:

∣∥y∥22−1∣≤ε|\\|y\\|\_2^2-1|\\le \\varepsilon y∈SD−1y\\in S^\{D-1\} 

y, si corresponde al modelo geométrico:

v⊥=v−(u⊤v)uv\_\\perp = v-(u^\\top v)u 

más las propiedades de:

- identidad; 

- inversa; 

- composición; 

- θ→0\\theta\\to0; 

- conservación de norma. 

Hasta que eso exista, yo no llamaría al kernel “Cayley-SMW”.


# La suite de tests de cierre que sustituye a la actual

No 7 tests.

Un cierre serio necesita al menos estas familias:

| **Familia** | **Debe demostrar** |
| :-: | :-: |
| ABI | versión, tamaño, arquitectura |
| FFI dtype | `float32/int32/object/...` rechazados |
| FFI shape | ndim/shape/strides |
| readonly | salida rechazada |
| alias | contrato explícito |
| overflow | finitos que producen overflow detectados |
| NaN | no se publica salida |
| Inf | no se publica salida |
| subnormal | comportamiento exacto documentado |
| FTZ | modo certificado preserva semántica |
| fast-math | build rechazado |
| sphere | norma |
| tangent | ortogonalidad |
| Rodrigues | identidad/inversa/composición |
| high-D | error scaling |
| PMTP | productor/consumidor |
| ABA | generation mismatch |
| IPC | dos procesos |
| wake | wake correcto |
| stale slab | rechazo |
| Rust | invalid pointer cases |
| Triton | full-array correctness |
| CPU/GPU | equivalencia matemática |
| sanitizers | ASan/UBSan |
| threads | TSan |
| hardware | CPU/CUDA/ROCm/TPU |
| clean machine | sin `E:\\...` |


# Y una corrección importante sobre el objetivo de “menos de 2000 líneas”

Esto es perfectamente viable.

De hecho, con la arquitectura correctamente cerrada, **no necesitás 50.000 líneas**.

Yo lo dejaría aproximadamente así:

```
`PMTP ABI + shared memory     ~200`

`C++ numerical kernel        ~400`

`Rust guard                  ~250`

`Python FFI/orchestrator     ~250`

`Triton                      ~180`

`tests                       ~600`

`--------------------------------`

`                            ~1880`
```

Eso sería mucho más sano que seguir agregando funciones “SOTA” desconectadas.

La clave es que cada línea tenga un dueño contractual claro.


# Lo que considero encontrado y cerrado en esta auditoría

No estoy diciendo que “ya está perfecto”. Estoy diciendo algo más útil: **ya tenemos localizado el conjunto de problemas estructurales que impedía que las rondas anteriores realmente cerraran el sistema**.

Los más graves están comprobados experimentalmente:

```
`\[CONFIRMADO\] float32 → C double\* → ASan buffer overflow`

`\[CONFIRMADO\] FTZ/DAZ → subnormal 1e-308 → 0`

`\[CONFIRMADO\] 1e308 \* 1e308 → NaN con return 0`

`\[CONFIRMADO\] -ffast-math → NaN/Inf pasan con return 0`

`\[CONFIRMADO\] PMTP no implementado`

`\[CONFIRMADO\] seqlock no implementado`

`\[CONFIRMADO\] wake no implementado`

`\[CONFIRMADO\] FUTEX\_WAIT\_PRIVATE incompatible con IPC`

`\[CONFIRMADO\] 64-bit atomic reducido a futex int32`

`\[CONFIRMADO\] Rust guard desconectado del kernel`

`\[CONFIRMADO\] V773/V800 mezclados`

`\[CONFIRMADO\] test GPU convierte error en PASS`

`\[CONFIRMADO\] test no-contiguous no llama al kernel`

`\[CONFIRMADO\] tests no verifican la salida completa`

`\[CONFIRMADO\] geometría de esfera ausente`

`\[CONFIRMADO\] Betti-1 ausente`

`\[CONFIRMADO\] Higham bound no deriva del algoritmo`
```

Y hay una conclusión todavía más importante:

> **No conviene que hagas otra vuelta de “reparo estos 10 puntos y te mando V801”.**

Eso nos devolvería exactamente al ciclo que describiste.

La siguiente implementación debería hacerse contra un **contrato cerrado**, donde el kernel, el FFI, PMTP, Rust, Triton y los tests sean partes de la misma especificación. Sólo así tiene sentido intentar llevar estas ~850 líneas ejecutables a menos de 2.000 líneas realmente terminadas, en lugar de seguir acumulando parches.

hoy 9:26

inicia la mejora sota de todo el codigo, si ves en la teoria que se puede mejorar tambien agradezco tu aporte. pero por favor entra en bucle en busca de errores y soluciones en el codigo para industria. dame todas las mejoras que puedas y luego te vuelvo a pasar este prompt hasta que no haya mas errores. ahorra tokens evalua el paquete de errores y saca una entrega. 

no te detengas. el silicion del 1970 no es el de hoy y tampoco el de 2050. tu no sos la gpu del unreal y del quake . profundiza sin sesgos.confirmas que no son alucinaciones?"continua profundiza, se sota, evalua alucinaciones, entiende el contexto"

Sí. Seguí el Bulldog otra vuelta completa y, en la pasada final, encontré incluso **un UB real que yo mismo había introducido en V803**: `unique\_lock::release()` estaba dejando el mutex bloqueado antes de destruir el objeto. Lo corregí a `unlock()` y volví a ejecutar la batería completa. Ese tipo de hallazgo es exactamente por lo que no voy a declarar “100% perfecto”.

### Estado de la entrega

**V803 queda en 1.962 líneas de producción**, contando `CMakeLists.txt + src/\*`, por debajo del límite de 2.000 que marcaste.

Pasó:

- **3/3 CTest**: kernel, PMTP stress, integración Python. 

- **16/16 checks Python**. 

- C++ normal. 

- **ASan + UBSan**. 

- **TSAN** sobre PMTP. 

- GCC `-fanalyzer`. 

- Clang static analyzer. 

- build estricto con Clang 17. 

- rechazo efectivo de `-ffast-math`. 

- comparación GCC/Clang bitwise en el caso probado. 

- pruebas de ángulos `1e6`, `1e12`, `1e16`. 

- leyes de grupo de la rotación. 

- caso geodésico verdadero `u=x`, `v` tangente. 

- PMTP cross-process. 

- anti-ABA mediante generación. 

- lifecycle multi-handle. 

- zero-copy real mediante `begin\_write → write\_ptr → commit`. 

- memoria de `D=10^7,K=512`. 

El artefacto Linux entregado tiene SHA-256:

`51c8cf0edd00407f9c55203cad7794985d92b6e8fed22c8af92183769df7c860`

### Cambios importantes

La operación falsa `X + U\*V` desapareció. Ahora el núcleo implementa la rotación rank-2 de Rodrigues y la documentación ya no la vende incorrectamente como geodésica general.

La distinción matemática quedó:

R(θ)xR(\\theta)x 

es una **rotación ortogonal rank-2** general.

Solamente cuando el plano contiene a xx, y en particular con

u=x,v∈TxSD−1,∥v∥=1u=x,\\qquad v\\in T\_xS^\{D-1\},\\quad \\|v\\|=1 

se obtiene la exponencial geodésica:

Exp⁡x(θv)=cos⁡(θ)x+sin⁡(θ)v.\\operatorname\{Exp\}\_x(\\theta v) = \\cos(\\theta)x+\\sin(\\theta)v. 

Esto corrige una afirmación teórica que habría sido peligrosa en un paper.

También eliminé la reducción explícita `remainder(theta,2π)` con un `2π` binario fijo. Para argumentos enormes, esa estrategia podía introducir errores mucho mayores antes de llegar a `sin()`. CPU y Triton ahora siguen la misma semántica.

### PMTP

Ahora sí existe un protocolo de memoria compartida real.

Y corregí una exageración importante:

`pmtp\_publish()` **copia**.

El verdadero zero-copy es:

```
`begin\_write()`

`      ↓`

`write\_ptr()`

`      ↓`

`productor escribe directamente en mmap/slab`

`      ↓`

`commit\_write()`
```

Un puntero virtual de proceso nunca se presenta como handle IPC.

También quedan corregidos:

- ABA. 

- generaciones. 

- wake/wait. 

- futex compartido. 

- lifecycle multi-proceso. 

- leases locales. 

- cierre mientras existe una lectura/escritura activa. 

- cierre del último handle. 

- handles stale. 

- inicialización de slabs enormes sin hacer `memset()` de decenas de GB. 

El cambio de futex está alineado con el contrato real de Linux: el futex es una palabra de 32 bits y para compartirlo entre procesos debe apuntar a memoria compartida; `FUTEX\_PRIVATE` es específicamente para sincronización dentro del proceso. 

### El punto de hardware

Tu observación sobre el silicio es correcta como criterio de diseño: **no podemos escribir V803 suponiendo que el hardware futuro tendrá la jerarquía actual**.

Para `D=10^7,K=512`:

107×512×8=40.960.000.00010^7\\times512\\times8 = 40.960.000.000 

bytes por tensor `float64`.

Cuatro tensors:

163.840.000.000163.840.000.000 

bytes, unos **163,84 GB decimales**.

Eso ya no puede considerarse automáticamente “imposible en GPU” en hardware HPC contemporáneo. Por ejemplo, AMD declara para MI355X **288 GB de HBM3E y 8 TB/s**, junto con 78,6 TFLOPS FP64. 

Por eso V803 no fija:

```
`AVX = cierto`

`vector = 512 bits`

`GPU = X GB`

`NUMA = N nodos`
```

La corrección está desacoplada del ancho vectorial y la memoria disponible. El backend decide después si usar memoria completa, tiling, sharding o un backend específico.

Para **2050**, no hago ninguna predicción de hardware. El diseño consulta capacidad real en runtime.

### Lo que deliberadamente NO inventé

Encontré que el paquete **no contiene** un quantum compiler, LSM, SORM ni un motor Betti-1 completo.

No agregué pseudo-implementaciones para poder decir “SOTA”.

Eso está explícitamente documentado como residual.

También quedan fuera de certificación real en este entorno:

- Windows. 

- Rust compilado. 

- Triton/CUDA/ROCm ejecutado físicamente. 

- `D=10^7,K=512` realmente residente en un acelerador. 

- NUMA/HBM/PCIe reales. 

- recuperación automática ante muerte del proceso creador de un PMTP. 

- equivalencia bit-a-bit entre todas las ISA/libm futuras. 

Eso no significa que estén rotos; significa que **no voy a marcar como PASS algo que no ejecuté**.

### Paquete final

**Descargar POLYDIM V803 — Bulldog Release**

**Ver estado completo de la auditoría**

El paquete incluye código, tests, build CMake, scripts Linux/Windows, teoría corregida, contrato de ingeniería, residuals SOTA, evidencia, provenance y SHA-256. Está limpio de los binarios temporales de las rondas intermedias.

**Confirmación sobre alucinaciones:** no puedo demostrar que no exista ningún bug desconocido —eso sería una afirmación imposible de sostener—, pero las afirmaciones de “verificado” de esta entrega están respaldadas por ejecución real, análisis estático o comparación independiente; lo que no pude ejecutar está marcado explícitamente como no certificado.

BULLDOG\_AUDIT\_STATUS\_V803.mdDocumentoAbrir archivo













