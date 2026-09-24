**Recibido. Tengo el `auditoria\_externa.zip` disponible y no voy a empezar todavía la auditoría, porque indicaste explícitamente: “Aguarda más instrucciones”.**

Cuando des la siguiente parte, voy a tratar el objetivo como una **auditoría de cierre**, no como otra ronda de “10 problemas” superficiales: revisaré el conjunto completo, buscaré errores de matemática, estabilidad numérica, invariantes, Rust/C++/Python, FFI, concurrencia, ownership, memoria, UB, aliasing, sincronización, allocator/IPC, dimensiones extremas y discrepancias entre teoría, código y afirmaciones del dossier.

No voy a asumir que algo es correcto porque figure en el documento ni a inventar fallos que no pueda sostener con evidencia.

mostrame sota en que mejorar confirmas que no son alucinaciones? luego si a todas las opciones que me puedas dar. una detrás de otra en bucle hasta el limite de tus entregas o no encontrar mas errores. el  propósito es darle cierre  a los problema sota no encontrados. continua evaluando problemas y soluciones en bucles cada vez mas profundamente. Hay mucho sota. no solo evalúa con tus conocimientos y sesgos. busca errores mas allá de tu programación básica, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. muestras los códigos en pantalla, nunca por adjuntos. /goal profundiza ciclos necesarios para pasar a industria \#\#atención\#\# evalúa las respuestas para no dar alucinaciones. Nuestro debe ser "matemáticamente SOTA en papel" a ser industrialmente inquebrantable en silicio real. --------------------------. no te detengas. el silicion del 1970 no es el de hoy y tampoco el de 2050. tu no sos la gpu del unreal y del quake . profundiza sin sesgos.confirmas que no son alucinaciones?"continua profundiza, se sota, evalua alucinaciones, entiende el contexto" 

mostrame sota en que mejorar confirmas que no son alucinaciones? luego si a todas las opciones que me puedas dar. una detrás de otra en bucle hasta el limite de tus entregas o no encontrar mas errores. el propósito es darle cierre a los problema sota no encontrados. continua evaluando problemas y soluciones en bucles cada vez mas profundamente. Hay mucho sota. no solo evalúa con tus conocimientos y sesgos. busca errores mas allá de tu programación básica, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. muestras los códigos en pantalla, nunca por adjuntos. /goal profundiza ciclos necesarios para pasar a industria \#\#atención\#\# evalúa las respuestas para no dar alucinaciones. Nuestro debe ser "matemáticamente SOTA en papel" a ser industrialmente inquebrantable en silicio real. --------------------------. no te detengas. el silicion del 1970 no es el de hoy y tampoco el de 2050. tu no sos la gpu del unreal y del quake . profundiza sin sesgos.confirmas que no son alucinaciones?"continua profundiza, se sota, evalua alucinaciones, entiende el contexto" 

Sí. **Para los hallazgos que siguen, no estoy rellenando huecos con imaginación.** Los separo en tres niveles:

- **V = verificado directamente**: aparece en el código V762 público o se deduce algebraicamente sin depender de una ejecución. 

- **P = prueba/documentación externa**: la conclusión se apoya además en especificaciones de Rust/C++/Python/IEEE/numerical analysis. 

- **U = no verificable todavía**: falta el C++/Rust real. En esos puntos **no voy a inventar el bug**; marco exactamente qué evidencia falta. 

Y hay una conclusión previa que es demasiado importante para esconderla: **hoy no puedo otorgar “silicon certified / industrially unbreakable” a V762**. Hay problemas P0 reales antes de llegar a optimizaciones SOTA.


# CICLO 1 — PRIMERA MORDEDURA: EL OBJETO AUDITADO NO COINCIDE CON LO QUE DICE SER

## 1. El ZIP no contiene el “monolito completo”

**V**

El dossier afirma que `02\_ALL\_SOURCE\_SCRIPTS\_MONOLITH.md` contiene el código completo, pero ese archivo contiene únicamente contratos públicos y referencias a rutas locales como:

```
`file:///E:/POLYDIM\_EINSOF/ENTREGA\_2026\_09\_19\_V762/src/polydim\_kernel.cpp`

`file:///E:/POLYDIM\_EINSOF/ENTREGA\_2026\_09\_19\_V762/rust/src/lib.rs`

`file:///E:/POLYDIM\_EINSOF/ENTREGA\_2026\_09\_19\_V762/dart/polydim\_ffi.dart`

`...`
```

El ZIP contiene 4 Markdown, y el supuesto “monolito” tiene sólo 166 líneas.

Esto es un **P0 de reproducibilidad/auditoría**.

No significa “el C++ está mal”. Significa algo más básico:

> **no tenemos el artefacto físico que permita demostrar que el C++ está bien.**

### Solución de industria

Un único snapshot inmutable:

```
`V762/`

`  include/polydim.h`

`  src/polydim\_kernel.cpp`

`  rust/src/lib.rs`

`  python/polydim\_v762.py`

`  dart/polydim\_ffi.dart`

`  triton/polydim\_kernel.py`

`  tests/`

`  CMakeLists.txt`

`  Cargo.toml`

`  pyproject.toml`

`  BENCHMARK\_MANIFEST.json`

`  SHA256SUMS`
```

y un `BUILD\_ID` común.

Cada componente debe devolver:

```
`const char\* polydim\_build\_id(void);`
```

Y Python debe comprobarlo:

```
`def require\_same\_build(\*libs):`

`    ids = \[lib.polydim\_build\_id().decode("ascii") for lib in libs\]`

`    if len(set(ids)) != 1:`

`        raise RuntimeError(f"ABI/build mismatch: \{ids\}")`
```

**Cierre:** ningún benchmark puede llamarse “certificación V762” si mezcla artefactos de commits/versiones distintos.


# CICLO 2 — EL BUG QUE SE ESCAPA POR LA PUERTA DE ATRÁS: V762 DICE 3 BUFFERS PERO EL PYTHON USA 2

## 2. El dossier dice triple-buffer; el código público usa doble-buffer

**V — confirmado directamente**

El dossier dice:

> “3-slot SPMC ring buffer with per-slot seqlocks”

pero el `polydim\_v762\_monolito.py` público declara:

```
`\# Header: 64 bytes Control + 2 buffers of D \* 8 bytes (FP64)`

`self.total\_bytes = 64 + 2 \* self.tensor\_bytes`
```

y selecciona:

```
`buf\_idx = seq & 1`
```

Eso es **2 buffers**, no 3.

Además, el propio GitHub muestra que este archivo tiene 246 líneas. 

La implementación publicada hace:

```
`packed = (seq \<\< 1) | (buf\_idx & 1)`

`ctrl\_view\[0\] = packed`
```

y el comentario dice:

```
`\# Publish packed atomic sequence`
```

Pero esa instrucción no es una operación atómica IPC explícita. Es una escritura a través de un ndarray de NumPy. 

### Esto es más grave que “faltó una optimización”

El protocolo declarado por el dossier y el protocolo realmente utilizado por Python **no son el mismo protocolo**.

### Solución

Una sola implementación de PMTP.

Python no debe reinventar la sincronización:

```
`\# NO:`

`ctrl\_view\[0\] = packed`
```

sino llamar a la misma API nativa que define el contrato:

```
`slot = ctypes.c\_uint64()`

`status = self.cpp\_lib.polydim\_pmtp\_begin\_write(`

`    ctypes.byref(slot)`

`)`

`if status != 0:`

`    raise RuntimeError(status)`


`\# write payload...`


`status = self.cpp\_lib.polydim\_pmtp\_commit\_write(`

`    ctypes.byref(slot)`

`)`

`if status != 0:`

`    raise RuntimeError(status)`
```

Y el lector:

```
`observed = ctypes.c\_uint64(last\_seq)`

`slot = ctypes.c\_uint64()`

`ticket = ctypes.c\_uint64()`


`status = self.cpp\_lib.polydim\_pmtp\_acquire\_read(`

`    ctypes.byref(observed),`

`    ctypes.byref(slot),`

`    ctypes.byref(ticket),`

`)`
```

Eso obliga a que Python, C++, Rust y demás hablen **exactamente el mismo protocolo**.


# CICLO 3 — “ATOMIC” ES UNA PALABRA, NO UNA GARANTÍA

## 3. La publicación de `packed` no demuestra atomicidad IPC

**V/P**

La línea real:

```
`ctrl\_view\[0\] = packed`
```

no proporciona por sí sola la semántica `release`/`acquire` que necesita un protocolo lock-free.

En C++, una escritura no atómica concurrente con otra evaluación conflictiva puede constituir una data race y producir comportamiento indefinido; `release/acquire` son precisamente parte de las herramientas para establecer orden de publicación y visibilidad. 

Hay otra trampa todavía peor:

> incluso un `atomic\<uint64\_t\>` correcto para el **control word** no vuelve automáticamente atómicas las escrituras del payload `double\[D\]`.

Puedes publicar perfectamente la secuencia y aun así tener:

```
`writer: escribe slot`

`reader: lee el mismo slot`
```

mientras el writer lo reutiliza.

### Solución industrial

Separar explícitamente:

```
`CONTROL PLANE`

`    estado / generación / slot / lease`


`DATA PLANE`

`    payload inmutable mientras haya lectores`
```

Modelo que quiero para el cierre:

```
`FREE`

`  │`

`  ├── writer CAS ──\> WRITING`

`  │`

`  └── reader CAS ──\> READING(n)`


`WRITING`

`  │ commit`

`  ▼`

`PUBLISHED`


`PUBLISHED`

`  │ reader acquire`

`  ▼`

`READING(n)`


`READING(0)`

`  │ writer CAS`

`  ▼`

`WRITING`
```

La idea crucial es que el escritor **no puede decidir “reader\_count == 0” y luego ser adelantado por un lector que intenta incrementar el contador**.

Eso debe ser una transición CAS del estado completo, no dos operaciones separadas.


# CICLO 4 — HAY OTRO BUG DE CONCURRENCIA: EL READER RECIBE UNA VISTA VIVA DEL SLOT

## 4. `read\_tensor()` devuelve un alias directo al mmap

**V — directo**

El código hace:

```
`src\_view = np.frombuffer(`

`    self.mmap\_obj,`

`    dtype=np.float64,`

`    count=self.D,`

`    offset=offset`

`)`


`return src\_view, seq`
```

`np.frombuffer()` crea una vista sobre el objeto subyacente, no una copia independiente. 

Eso significa:

```
`reader obtiene view`

`        ↓`

`writer reutiliza slot`

`        ↓`

`reader continúa usando view`

`        ↓`

`payload cambia debajo del reader`
```

Éste es el núcleo real del problema.

No basta con:

```
`read seq`

`read payload`

`read seq otra vez`
```

si después del segundo `seq` el consumidor conserva el puntero durante otros 500 µs.

### Solución

Hay dos diseños válidos.

### Diseño A — cero-copy real

El reader debe adquirir una **lease**:

```
`with channel.acquire() as tensor:`

`    consume(tensor)`
```

y sólo al salir:

```
`release(ticket)`
```

El writer no reutiliza el slot mientras exista una lease activa.

### Diseño B — copia segura

```
`return np.array(src\_view, copy=True), seq`
```

Es seguro pero deja de ser zero-copy.

Para POLYDIM, dado el objetivo, **A es el diseño correcto**.


# CICLO 5 — EL “READ-ONLY VIEW” NO ES READ-ONLY

## 5. La implementación dice read-only, pero el mmap fue abierto como escritura

**V**

Windows:

```
`mmap.mmap(`

`    -1,`

`    self.total\_bytes,`

`    tagname=self.shm\_name,`

`    access=mmap.ACCESS\_WRITE`

`)`
```

Por tanto, el objeto mapeado es escribible.

Luego el lector hace:

```
`src\_view = np.frombuffer(...)`
```

y lo denomina:

```
`\# Zero-Copy Read-Only View`
```

pero la vista no está protegida contra escritura.

### Solución

Separar roles:

```
`if role == "writer":`

`    access = mmap.ACCESS\_WRITE`

`else:`

`    access = mmap.ACCESS\_READ`
```

y en POSIX:

```
`mmap.mmap(`

`    fd,`

`    total\_bytes,`

`    access=mmap.ACCESS\_READ`

`)`
```

Además:

```
`src\_view.flags.writeable = False`
```

como segunda barrera.

**Pero** la protección importante es el mapeo de memoria, no sólo el flag de NumPy.


# CICLO 6 — `assert` NO ES UNA BARRERA DE SEGURIDAD

## 6. Los controles de entrada de Python desaparecen con `python -O`

**V — directo**

Hay:

```
`assert tensor\_f64.dtype == np.float64 and tensor\_f64.size == self.D`
```

y:

```
`assert y.dtype == np.float64 and u.dtype == np.float64 and v.dtype == np.float64`
```

y:

```
`assert X.dtype == np.float64 and G.dtype == np.float64`
```

En Python, `assert` está diseñado para debugging. Con optimización (`python -O`) esas comprobaciones pueden desaparecer.

Entonces una barrera de seguridad puede convertirse literalmente en:

```
`producción optimizada`

`        ↓`

`sin chequeo`

`        ↓`

`puntero nativo`

`        ↓`

`C++ lee memoria suponiendo D elementos`
```

### Solución

Nunca usar `assert` para validar el contrato FFI:

```
`def require\_vector(a, D, name):`

`    if not isinstance(a, np.ndarray):`

`        raise TypeError(f"\{name\}: expected ndarray")`


`    if a.dtype != np.float64:`

`        raise TypeError(f"\{name\}: expected float64")`


`    if a.ndim != 1 or a.size != D:`

`        raise ValueError(`

`            f"\{name\}: expected shape (\{D\},), got \{a.shape\}"`

`        )`


`    if not a.flags.c\_contiguous:`

`        raise ValueError(f"\{name\}: C-contiguous required")`


`    if not a.flags.aligned:`

`        raise ValueError(f"\{name\}: aligned buffer required")`


`    return a`
```

Esto sí sobrevive:

```
`python -O ...`
```


# CICLO 7 — FFI: EL CONTRATO PUBLICADO Y EL BINDING PYTHON NO COINCIDEN

## 7. ABI mismatch real

**V/P**

El header del dossier declara:

```
`polydim\_rodrigues\_geodesic\_f64(`

`    const double\* y,`

`    const double\* u,`

`    const double\* v,`

`    double\* y\_out,`

`    double theta,`

`    uint64\_t D,`

`    const PolydimTolerances\* tol,`

`    PolydimReport\* report`

`);`
```

Es decir: **8 argumentos**.

Pero el Python V762 enlaza:

```
`self.cpp\_lib.polydim\_apply\_rodrigues\_geodesic\_f64.argtypes = \[`

`    c\_void\_p,`

`    c\_void\_p,`

`    c\_void\_p,`

`    c\_void\_p,`

`    c\_double,`

`    c\_uint64`

`\]`
```

y llama a:

```
`self.cpp\_lib.polydim\_apply\_rodrigues\_geodesic\_f64(`

`    y.ctypes.data,`

`    u.ctypes.data,`

`    v.ctypes.data,`

`    y\_out.ctypes.data,`

`    ctypes.c\_double(theta),`

`    ctypes.c\_uint64(D)`

`)`
```

Son contratos diferentes. 

Stiefel presenta la misma discrepancia:

Dossier:

```
`polydim\_stiefel\_cayley\_smw\_f64(`

`    X, G, Y\_out,`

`    D, K, tau,`

`    tol, report`

`);`
```

Python:

```
`polydim\_stiefel\_cayley\_smw\_retraction\_f64(`

`    X, G, Y\_out,`

`    D, K, tau`

`)`
```

### Esto es P0.

No lo llamaría “potencial”.

**Hay que reconciliar nombres, aridad y tipos antes de ejecutar cualquier cosa.**


# CICLO 8 — EL FFI PYTHON PASA PUNTEROS SIN VALIDAR LAS DIMENSIONES FÍSICAS

## 8. `D = y.size` no valida `u` ni `v`

**V**

Aquí:

```
`D = y.size`

`...`

`u.ctypes.data`

`v.ctypes.data`

`...`

`c\_uint64(D)`
```

No se comprueba:

```
`u.size == D`

`v.size == D`

`u.ndim == 1`

`v.ndim == 1`
```

Por ejemplo:

```
`y = np.ones(1\_000\_000, dtype=np.float64)`

`u = np.ones(100, dtype=np.float64)`

`v = np.ones(1\_000\_000, dtype=np.float64)`
```

El wrapper entrega `D=1\_000\_000` al C++.

Si el kernel confía en D:

```
`for (uint64\_t i = 0; i \< D; ++i)`

`    ...`
```

`u\[i\]` puede salirse del buffer.

### Solución

La entrada correcta:

```
`def apply\_rodrigues\_geodesic(self, y, u, v, theta):`

`    y = require\_vector(y, y.size, "y")`

`    D = y.size`

`    u = require\_vector(u, D, "u")`

`    v = require\_vector(v, D, "v")`
```

Pero además `D` debe tener un límite explícito:

```
`if D \< 3:`

`    raise ValueError("D too small")`


`if D \> POLYDIM\_MAX\_D:`

`    raise ValueError("D exceeds configured memory/ABI limit")`
```


# CICLO 9 — STIEFEL TIENE EL MISMO PROBLEMA, PERO EN DOS DIMENSIONES

## 9. `G.shape` no está validado

**V**

Se hace:

```
`D, K = X.shape`

`Y\_out = np.empty((D, K), dtype=np.float64)`

`...`

`G.ctypes.data`
```

sin comprobar:

```
`G.shape == (D, K)`
```

Tampoco se exige C-contiguous.

Una matriz transpuesta:

```
`G = original.T`
```

puede tener strides completamente diferentes.

Un kernel C++ que hace:

```
`G\[i\*K + k\]`
```

interpreta esos bytes como si fueran contiguos.

### Solución

```
`def require\_matrix(a, D, K, name):`

`    if not isinstance(a, np.ndarray):`

`        raise TypeError(name)`


`    if a.dtype != np.float64:`

`        raise TypeError(f"\{name\}: float64 required")`


`    if a.shape != (D, K):`

`        raise ValueError(`

`            f"\{name\}: expected \{(D,K)\}, got \{a.shape\}"`

`        )`


`    if not a.flags.c\_contiguous:`

`        raise ValueError(`

`            f"\{name\}: C-contiguous matrix required"`

`        )`


`    if not a.flags.aligned:`

`        raise ValueError(`

`            f"\{name\}: aligned matrix required"`

`        )`


`    return a`
```


# CICLO 10 — EL ERROR MATEMÁTICO MÁS IMPORTANTE: LA FÓRMULA STIEFEL NO ES UNA RETRACCIÓN PARA TODO G TANGENTE

Este es el golpe más serio del lote.

## 10. El tribunal declaró cerrado A “tangencia” pero la propiedad que debe demostrarse es otra

El dossier dice:

RX(τG)=X+τU(I−τ2VTU)−1VTXR\_X(\\tau G) = X+ \\tau U \\left(I-\\frac\{\\tau\}\{2\}V^TU\\right)^\{-1\} V^TX 

con

U=\[G X\],V=\[X −G\].U=\[G\\ X\],\\qquad V=\[X\\ -G\]. 

También afirma que esto es una **retraction** para:

G∈TXSt(D,K).G\\in T\_XSt(D,K). 

El tribunal defiende la fórmula porque:

W=GXT−XGTW=GX^T-XG^T 

es antisimétrica y por eso la transformación Cayley mantiene ortogonalidad.

Eso es insuficiente.

Una **retraction** no se define sólo por:

RX(τG)TRX(τG)=I.R\_X(\\tau G)^T R\_X(\\tau G)=I. 

También tiene que satisfacer:

RX(0)=XR\_X(0)=X 

y:

ddτRX(τG)∣τ=0=G.\\left.\\frac\{d\}\{d\\tau\}R\_X(\\tau G)\\right|\_\{\\tau=0\}=G. 

Ésta es la condición diferencial esencial de una retraction. 

### Hagamos la derivación

Para:

R(τ)=X+τU(I−τ2VTU)−1VTXR(\\tau) = X+\\tau U (I-\\frac\{\\tau\}\{2\}V^TU)^\{-1\}V^TX 

en τ=0\\tau=0:

(I−τ2VTU)−1=I+O(τ)(I-\\frac\{\\tau\}\{2\}V^TU)^\{-1\}=I+O(\\tau) 

por tanto:

R′(0)=UVTX.R'(0)=UV^TX. 

Con:

U=\[G,X\]U=\[G,X\] 

y:

V=\[X,−G\]V=\[X,-G\] 

tenemos:

UVT=GXT−XGT.UV^T = GX^T-XG^T. 

Luego:

R′(0)=(GXT−XGT)X=G−XGTX.R'(0) = (GX^T-XG^T)X = G-XG^TX. 

Ahora definimos:

Ω=XTG.\\Omega=X^TG. 

Como GG es tangente:

XTG+GTX=0X^TG+G^TX=0 

por lo cual:

GTX=−Ω.G^TX=-\\Omega. 

Entonces:

R′(0)=G+XΩ.R'(0) = G+X\\Omega. 

Por tanto:

R′(0)≠G\\boxed\{R'(0)\\neq G\} 

en general.

Sólo coincide cuando:

XTG=0.X^TG=0. 

Eso elimina la parte vertical XΩX\\Omega.

### Esto NO significa que la matriz deje de ser ortogonal

Ésa es precisamente la distinción que el tribunal está mezclando:

```
`Cayley:`

`    puede preservar XᵀX = I`


`Retracción:`

`    además debe tener derivada G en τ=0`
```

El tribunal demuestra una propiedad y la utiliza como si fuera la otra.

**Éste no es un argumento de estilo. Es álgebra.**


# CICLO 11 — REPARACIÓN MATEMÁTICA DE STIEFEL

Podemos conservar la estructura low-rank.

Sea:

Ω=XTG\\Omega=X^TG 

y definamos:

A=GXT−XGT−XΩXT.A = GX^T-XG^T-X\\Omega X^T. 

Entonces:

AT=−AA^T=-A 

y:

AX=G.AX=G. 

Una representación low-rank conveniente es:

U=\[G,X\]U=\[G,X\] V=\[X,−G+XΩ\].V=\[X,-G+X\\Omega\]. 

Entonces:

A=UVTA=UV^T 

y además:

VTX=\[I0\].V^TX = \\begin\{bmatrix\} I\\\\ 0 \\end\{bmatrix\}. 

La implementación conceptualmente debe ser:

```
`Omega = X.T @ G`


`U = np.concatenate(`

`    \[G, X\],`

`    axis=1`

`)`


`V = np.concatenate(`

`    \[X, -G + X @ Omega\],`

`    axis=1`

`)`


`M = np.eye(2\*K) - 0.5\*tau\*(V.T @ U)`


`B = V.T @ X`


`Z = solve(M, B)`


`Y = X + tau \* U @ Z`
```

Pero hay otra mordida:

```
`solve(M, B)`
```

sí.

Esto:

```
`np.linalg.inv(M) @ B`
```

no.

Y tampoco:

```
`M.inverse()`
```

si se puede evitar.


# CICLO 12 — EL PIVOTE RELATIVO NO ES UNA PRUEBA DE ESTABILIDAD

El dossier usa:

pivot\_thr=tol.pivot\_rel∥M∥∞2K.pivot\\\_thr = tol.pivot\\\_rel \\|M\\|\_\\infty 2K. 

Eso es mejor que un `1e-15` absoluto.

Pero **no demuestra que M esté bien condicionada**.

No son equivalentes:

```
`pivot \> threshold`
```

y

```
`sistema numéricamente estable`
```

### Solución SOTA

El solver debe devolver al menos:

```
`factorización exitosa`

`rcond estimada`

`residual`

`pivot mínimo`

`pivot máximo`

`growth factor`
```

Y verificar:

∥MZ−B∥∥M∥∥Z∥+∥B∥\\frac\{\\|MZ-B\\|\} \{\\|M\\|\\|Z\\|+\\|B\\|\} 

contra una cota establecida.

Código de cierre conceptual:

```
`double backward\_error(`

`    const Matrix& M,`

`    const Matrix& Z,`

`    const Matrix& B)`

`\{`

`    const double r =`

`        norm\_inf(M \* Z - B);`


`    const double denom =`

`        norm\_inf(M) \* norm\_inf(Z) +`

`        norm\_inf(B);`


`    return r / std::max(denom, DBL\_MIN);`

`\}`
```

El pivot deja de ser la única autoridad.


# CICLO 13 — “64 EPS INDEPENDIENTE DE D” NO ESTÁ DEMOSTRADO

## 13. La prueba experimental no alcanza

El dossier afirma:

64ϵmach=1.42×10−1464\\epsilon\_\{mach\}=1.42\\times10^\{-14\} 

independiente de D.

Pero los errores estándar de productos internos dependen de la dimensión y de la magnitud/condicionamiento de los datos. La literatura numérica da cotas que contienen explícitamente el número de términos para el producto interno general. 

Eso **no significa** que Neumaier sea inútil.

Significa:

> Para afirmar una cota universal de 64ϵ64\\epsilon, hay que probarla para exactamente el algoritmo utilizado.

Una prueba:

```
`D = 1,000,000`

`pocos millones de muestras`

`error observado = ...`
```

no prueba:

```
`∀ D ≤ 10,000,000`
```

ni:

```
`∀ inputs`
```

ni:

```
`∀ thread partitions`
```

ni:

```
`∀ compiler/codegen`
```

### Y hay una unidad conceptual que corregir

Si:

u=2−53u=2^\{-53\} 

es la unidad de redondeo tradicional, entonces:

64ϵmach64\\epsilon\_\{mach\} 

no es “exactamente la machine epsilon”.

Es **64 veces** el parámetro que decidieron usar como epsilon.

### Solución

Para cada operación crítica definir:

err≤C(D,κ,u,algorithm)err \\le C(D,\\kappa,u,\\text\{algorithm\}) 

o demostrar que el algoritmo utilizado tiene una cota realmente independiente de DD bajo hipótesis explícitas.

Y necesitamos tests adversariales:

```
`todos positivos`

`signos alternantes`

`cancelación extrema`

`órdenes aleatorios`

`magnitudes 1e-300 ... 1e300`

`subnormales`

`valores cerca de overflow`

`duplicados`

`vectores sparse`

`vectores casi paralelos`
```


# CICLO 14 — EL NORM CHECK PUEDE FALLAR ANTES DE LLEGAR A LA GEOMETRÍA

## 14. `sum(x\*x)` no es un norm robusto a escala extrema

Para D enorme:

```
`sum += x\[i\] \* x\[i\];`
```

puede producir:

```
`x\[i\] ≈ 1e200`

`x\[i\]^2 ≈ 1e400`
```

→ overflow aunque una representación escalada de la norma sea manejable.

También hay underflow.

### Solución

Norma escalada:

```
`double stable\_norm(const double\* x, size\_t n)`

`\{`

`    double scale = 0.0;`

`    double ssq   = 1.0;`


`    for (size\_t i = 0; i \< n; ++i) \{`

`        const double ax = std::abs(x\[i\]);`


`        if (ax == 0.0)`

`            continue;`


`        if (scale \< ax) \{`

`            const double r = scale / ax;`

`            ssq   = 1.0 + ssq \* r \* r;`

`            scale = ax;`

`        \} else \{`

`            const double r = ax / scale;`

`            ssq += r \* r;`

`        \}`

`    \}`


`    return scale == 0.0`

`        ? 0.0`

`        : scale \* std::sqrt(ssq);`

`\}`
```

Esto debe convertirse en **primitive central**, no quedar como detalle del checker.


# CICLO 15 — `isfinite(theta)` NO RESUELVE EL PROBLEMA DE ÁNGULOS GIGANTES

El dossier hace:

```
`std::isfinite(theta)`
```

Eso solamente responde:

```
`¿theta es finito?`
```

No:

```
`¿sin(theta) / cos(theta)`

`tienen una reducción de argumento suficientemente precisa?`
```

Un `theta` enorme puede ser finito pero su representación ya no contiene todos los bits necesarios para conocer con precisión su posición módulo 2π2\\pi.

### Solución

Definir contrato:

```
`if (!std::isfinite(theta))`

`    return INVALID\_SCALAR;`


`if (std::abs(theta) \> POLYDIM\_MAX\_THETA)`

`    return THETA\_OUT\_OF\_CONTRACT;`
```

o reducir explícitamente:

```
`double t = std::remainder(theta, 2.0 \* M\_PI);`


`double s = std::sin(t);`

`double c = std::cos(t);`


`double vers = 2.0 \*`

`              std::sin(0.5 \* t) \*`

`              std::sin(0.5 \* t);`
```

Y testear:

```
`theta`

`theta + 2π`

`theta + 2π\*N`
```

para valores donde la representación lo permita.


# CICLO 16 — EL TEST DE ORTOGONALIDAD PUEDE DEJAR PASAR EL ERROR DE RETRACCIÓN

Éste es muy importante porque explica cómo un bug matemático puede sobrevivir cientos de rondas.

El test reportado es algo como:

```
`max |YᵀY - I| = 2.44e-15`
```

Eso puede pasar aunque:

R′(0)≠G.R'(0)\\neq G. 

Es decir, el test está verificando:

```
`manifold membership`
```

pero no:

```
`retraction first-order property`
```

### Hay que añadir este oracle

Para ττ progresivamente pequeño:

```
`double directional\_error(`

`    const Matrix& X,`

`    const Matrix& G,`

`    const Matrix& Y,`

`    double tau)`

`\{`

`    Matrix approx = (Y - X) / tau;`


`    return norm\_fro(approx - G) /`

`           std::max(1.0, norm\_fro(G));`

`\}`
```

Y hacer:

```
`τ = 2^-4`

`τ = 2^-8`

`τ = 2^-12`

`τ = 2^-16`

`...`
```

La pendiente debe exhibir el orden esperado.

Además hay que generar específicamente:

```
`G = G\_horizontal + XΩ`
```

con:

ΩT=−Ω,Ω≠0.Ω^T=-Ω,\\quad Ω\\neq0. 

Ése es exactamente el caso que el test actual corre el riesgo de no detectar.


# CICLO 17 — BETTI-1: “DSU” NO ES SUFICIENTE PARA β₁ GENERAL

**P**

Un DSU/Union-Find resuelve conectividad, esencialmente β0\\beta\_0.

Para un complejo simplicial general:

β1=dim⁡ker⁡∂1−rank⁡∂2.\\beta\_1 = \\dim \\ker \\partial\_1 - \\operatorname\{rank\}\\partial\_2. 

La literatura de TDA lo expresa mediante las matrices de borde/rangos. 

Por eso:

```
`DSU`
```

por sí solo no demuestra:

```
`β1`
```

de un Vietoris–Rips complejo general.

### Y aparece otra inconsistencia

La wrapper Python se llama:

```
`verify\_betti1(self, adj\_matrix, ...)`
```

y pasa:

```
`N = adj\_matrix.shape\[0\]`

`adj\_matrix.ctypes.data`
```

sin validar que sea cuadrada. 

Además, si realmente se trata de una matriz densa `N×N` en `float64`:

```
`N=1,000     ≈ 8 MB`

`N=10,000    ≈ 800 MB`

`N=100,000   ≈ 80 GB`
```

Eso choca con la descripción de “Sparse VR”.

### Solución

No pasar una matriz densa.

Contrato explícito:

```
`CSR:`

`row\_ptr\[N+1\]`

`col\_idx\[nnz\]`

`weights\[nnz\]`
```

o edge list:

```
`struct Edge \{`

`    uint32\_t u;`

`    uint32\_t v;`

`    double   weight;`

`\};`
```

Y especificar exactamente qué complejo se calcula:

```
`graph G`

`threshold ε`

`Vietoris–Rips complex VR(G, ε)`

`β1(VR)`
```

No:

```
`β1(S^(D-1))`
```

porque son objetos diferentes.


# CICLO 18 — HAY UNA CONFUSIÓN TOPOLOGÍA CONTINUA vs. COMPLEJO DE DATOS

Para:

SD−1S^\{D-1\} 

con:

D\>2,D\>2, 

efectivamente:

β1(SD−1)=0.\\beta\_1(S^\{D-1\})=0. 

Pero si calculas:

```
`muestras discretas`

`      ↓`

`grafo`

`      ↓`

`Vietoris–Rips`

`      ↓`

`β1`
```

estás midiendo el complejo inducido por los datos y el parámetro de escala.

No existe un paso mágico:

```
`β1(dataset) = β1(continuous sphere)`
```

sin hipótesis de muestreo, escala y reconstrucción.

### Solución

Declarar dos invariantes diferentes:

```
`TOPOLOGICAL\_MODEL:`

`    S^(D-1)`


`OBSERVED\_COMPLEX:`

`    VR(X, epsilon)`


`CERTIFIED\_TOPOLOGY:`

`    β1(VR(X, epsilon))`
```

Y solamente establecer equivalencia con la esfera si existe un teorema/condición de reconstrucción que lo justifique.


# CICLO 19 — EL BENCHMARK DESMIENTE UNA PARTE DE LA NARRATIVA

El propio dossier reporta:

| **D** | **K** | **V762** | **OpenBLAS** |
| :-: | :-: | :-: | :-: |
| 4096 | 16 | 0.89 ms | 1.77 ms |
| 4096 | 64 | 9.90 ms | **5.71 ms** |
| 16384 | 32 | 9.68 ms | 14.99 ms |
| 16384 | 128 | 152.30 ms | **124.24 ms** |
| 65536 | 64 | 143.19 ms | 190.38 ms |

El propio archivo contiene esos números.

Por tanto:

```
`V762 puede ganar en algunas configuraciones`
```

pero no:

```
`V762 es más rápido que OpenBLAS en general.`
```

Y eso importa porque el dossier concluye:

```
`SILICON CONTRACT 100% CERTIFIED`
```

La certificación de corrección y el rendimiento relativo son propiedades distintas.

### Solución

Cambiar el benchmark a una matriz completa:

```
`D:`

`  4096`

`  8192`

`  16384`

`  32768`

`  65536`

`  131072`

`  1e6`


`K:`

`  4`

`  8`

`  16`

`  32`

`  64`

`  128`

`  256`

`  512`
```

y publicar:

```
`median`

`p50`

`p95`

`p99`

`stddev`

`warmup`

`threads`

`CPU affinity`

`CPU frequency`

`NUMA node`

`OpenBLAS threads`

`compiler`

`flags`

`commit`

`binary hash`
```


# CICLO 20 — EL CLAIM “FULL SIMD IN L1” ES DEMASIADO FUERTE

El dossier afirma:

> “full SIMD auto-vectorization in L1 cache”

para D=16384,K=128D=16384,K=128.

Pero sólo:

16384×128×8=16 777 216 bytes16384\\times128\\times8 = 16\\,777\\,216\\ bytes 

≈ 16 MiB para **una** matriz.

Y ZZ de tamaño 2K×K2K\\times K, por ejemplo, ronda:

256 KB256\\ KB 

para K=128K=128, ya por encima de un L1-D típico.

Por tanto:

```
`loop swap`
```

puede mejorar localidad,

pero:

```
`entire working set in L1`
```

no se deduce.

### Solución SOTA

Demostrarlo con:

```
`- compiler vectorization report`

`- assembly`

`- perf stat`

`- cache-misses`

`- L1-dcache-loads`

`- L1-dcache-load-misses`

`- cycles`

`- instructions`

`- FP operations`
```

El claim correcto debe ser algo como:

```
`vectorized inner kernel`

`with measured SIMD width W`

`and measured L1 miss rate M`
```

No “full SIMD in L1” por inferencia.


# CICLO 21 — LOS 33% DE FLOPS TAMPOCO SON AUTOMÁTICAMENTE 33%

El dossier contrapone:

```
`3 Gram matrices`
```

contra:

```
`upper triangle of WᵀW`
```

Eso puede ahorrar frente a una implementación ingenua que recalcula simetrías.

Pero un BLAS serio ya puede explotar:

```
`syrk`

`gemm`

`symmetric structure`
```

Así que el baseline correcto no es necesariamente:

```
`3 \* full GEMM`
```

### Solución

Comparar contra:

```
`DGEMM`

`DSYRK`

`hand-tuned AVX2`

`hand-tuned AVX-512`

`OpenBLAS`

`BLIS`

`oneMKL`

`ARM BLAS`
```

con el **mismo trabajo matemático**.

La métrica debe ser:

```
`actual FLOPs`

`actual bytes moved`

`GFLOP/s`

`GB/s`

`AI = FLOPs/byte`
```

Eso lleva el análisis al roofline.


# CICLO 22 — LA COTA DE D=10⁷ NO ESTÁ RESPALDADA POR LOS TESTS

El objetivo dice hasta:

D=10,000,000.D=10,000,000. 

Pero los tests de Rodrigues llegan a 10610^6, y la parte Stiefel reportada tiene tamaños mucho menores.

Eso no demuestra el contrato final.

Y en Stiefel aparece un problema físico.

Para:

D=107,K=128D=10^7,\\quad K=128 

una matriz `double` cuesta:

107⋅128⋅8=10.24 GB.10^7\\cdot128\\cdot8 = 10.24\\ GB. 

Tres:

```
`X`

`G`

`Y`
```

≈

30.72 GB.30.72\\ GB. 

Para K=512K=512:

122.88 GB122.88\\ GB 

antes de workspaces.

No es una imposibilidad matemática.

Pero **sí es parte del contrato industrial**.

### Solución

Definir:

```
`MAX\_D = 10\_000\_000`

`MAX\_K = 512`


`MEMORY\_BUDGET`

`NUMA\_POLICY`

`THREAD\_POLICY`

`WORKSPACE\_BUDGET`
```

y un fallo explícito:

```
`POLYDIM\_ERR\_RESOURCE\_BUDGET`
```

No llegar a:

```
`malloc`

`    ↓`

`OOM`

`    ↓`

`kill`
```


# CICLO 23 — “O(1) TRANSFER” NECESITA SER REDEFINIDO

El metadato puede transferirse en:

O(1).O(1). 

Pero para producir o consumir un tensor de D elementos:

O(D)O(D) 

de memoria.

La implementación actual además hace:

```
`np.copyto(dest\_view, tensor\_f64)`
```

por lo que hay como mínimo:

```
`producer tensor`

`      ↓`

`copy`

`      ↓`

`shared-memory tensor`
```

Eso no es end-to-end zero-copy.

El consumidor sí puede obtener una vista sin copia. 

### Solución

API real:

```
`slot = channel.begin\_write()`


`\# el productor escribe directamente:`

`slot\[:\] = ...`


`channel.commit\_write(slot)`
```

El productor recibe una región mmap directamente.

Entonces sí podemos afirmar:

```
`control handoff: O(1)`

`payload copy: O(0)`

`payload production: O(D)`

`payload consumption: O(D)`
```

Eso es técnicamente limpio.


# CICLO 24 — EL RECURSO POSIX NO SE CIERRA COMPLETAMENTE

**V/P**

El código:

```
`def close(self):`

`    gc.collect()`


`    try:`

`        self.mmap\_obj.close()`

`    except BufferError:`

`        pass`
```

No hace:

```
`self.posix\_shm.close\_fd()`
```

ni:

```
`self.posix\_shm.unlink()`
```

La documentación de `posix\_ipc` diferencia precisamente cierre del descriptor y eliminación del objeto nombrado. 

Además el `BufferError` es tragado.

Por lo tanto:

```
`“close”`
```

puede terminar siendo:

```
`mapping remains`

`fd remains`

`name remains`
```

### Solución

Ownership explícito:

```
`class PMTP:`

`    def close(self):`

`        if self.\_closed:`

`            return`


`        errors = \[\]`


`        try:`

`            self.mmap\_obj.close()`

`        except BufferError as e:`

`            errors.append(e)`


`        try:`

`            self.posix\_shm.close\_fd()`

`        except Exception as e:`

`            errors.append(e)`


`        if self.\_owner:`

`            try:`

`                self.posix\_shm.unlink()`

`            except Exception as e:`

`                errors.append(e)`


`        self.\_closed = True`


`        if errors:`

`            raise RuntimeError(`

`                f"PMTP close incomplete: \{errors\}"`

`            )`
```

Y `\_\_enter\_\_/\_\_exit\_\_` + `atexit` sólo como segunda barrera.


# CICLO 25 — WINDOWS `create=False` NO ES EL MISMO CONTRATO

El código conserva:

```
`self.create = create`
```

pero en Windows siempre ejecuta:

```
`mmap.mmap(`

`    -1,`

`    self.total\_bytes,`

`    tagname=self.shm\_name,`

`    access=mmap.ACCESS\_WRITE`

`)`
```

La semántica de `tagname` de `mmap` permite abrir un mapping existente o crear uno si no existe; no hay aquí una traducción explícita de:

```
`create=False`
```

a:

```
`OPEN\_EXISTING solamente`
```

La documentación de CPython describe precisamente esa semántica. 

Esto puede producir:

```
`reader cree estar conectándose al canal`

`             ↓`

`mapping no existe`

`             ↓`

`se crea otro mapping`

`             ↓`

`reader “funciona”`

`             ↓`

`pero está hablando consigo mismo`
```

### Solución

En Windows usar una capa explícita:

```
`OpenFileMappingW(...)`
```

para `create=False`.

Y validar:

```
`magic`

`version`

`D`

`slot\_count`

`payload\_bytes`

`build\_id`
```

antes de considerar el canal válido.


# CICLO 26 — FALTA IDENTIDAD DEL SEGMENTO SHARED MEMORY

Actualmente el nombre es:

```
`polydim\_pmtp\_\{tag\}`
```

No veo en la implementación Python un encabezado que diga:

```
`MAGIC`

`ABI`

`D`

`SLOTS`

`PAYLOAD\_SIZE`

`BUILD`

`GENERATION`
```

Eso abre la puerta a:

```
`proceso A usa V761`

`proceso B usa V762`

`mismo tag`
```

o:

```
`reader D=1e6`

`writer D=2e6`
```

### Solución

Primeros bytes:

```
`struct PmtpHeader \{`

`    uint64\_t magic;`

`    uint32\_t abi\_version;`

`    uint32\_t header\_bytes;`


`    uint64\_t build\_id\_hash;`

`    uint64\_t dimension;`


`    uint32\_t slot\_count;`

`    uint32\_t scalar\_format;`


`    uint64\_t payload\_bytes;`

`    uint64\_t generation;`

`\};`
```

Y:

```
`if (h-\>magic != PMTP\_MAGIC)`

`    return ERR\_BAD\_MAGIC;`


`if (h-\>abi\_version != PMTP\_ABI\_VERSION)`

`    return ERR\_ABI\_MISMATCH;`


`if (h-\>dimension != expected\_D)`

`    return ERR\_DIMENSION\_MISMATCH;`
```


# CICLO 27 — SEQUENCE + SLOT = RIESGO ABA

Se empaqueta:

```
`(seq \<\< 1) | buf\_idx`
```

Eso deja menos bits para la generación.

No es un problema práctico a velocidad humana, pero en un protocolo industrial debe estar formalmente definido:

```
`¿Qué ocurre al overflow?`
```

### Solución

Definir arithmetic modular explícita:

```
`uint64\_t sequence`
```

y una comparación modular segura:

```
`static inline bool seq\_newer(`

`    uint64\_t a,`

`    uint64\_t b)`

`\{`

`    return int64\_t(a - b) \> 0;`

`\}`
```

con el requisito:

```
`distancia válida \< 2^63`
```

o utilizar generación + epoch.


# CICLO 28 — SPMC NECESITA SER UNA GARANTÍA, NO UNA SUPOSICIÓN

SPMC significa:

```
`Single Producer`

`Multiple Consumers`
```

Pero la API Python mostrada no tiene un mecanismo evidente que impida:

```
`writer A`

`writer B`
```

sobre el mismo mapping.

Dos productores pueden hacer:

```
`A: seq=10`

`B: seq=11`

`A: escribe slot 10`

`B: escribe slot 11`

`A: publica`

`B: publica`
```

El contrato SPMC solamente existe si:

```
`exactamente un writer`
```

es realmente una precondición enforced.

### Solución

Header:

```
`producer\_pid`

`producer\_generation`
```

y adquisición exclusiva:

```
`single producer lease`
```

o documentarlo como requisito duro y rechazar un segundo productor.


# CICLO 29 — LA GARANTÍA RUST ESTÁ MAL FORMULADA

El dossier afirma:

```
`Rust 2024`

`\#\[unsafe(no\_mangle)\]`

`panic = "unwind"`
```

y de allí:

> “garantizando deterministic memory safety across FFI boundaries”

Eso no se sigue.

Rust exige que los límites FFI y el comportamiento de unwinding sean compatibles; `extern "C-unwind"` es precisamente la ABI para límites que permiten unwind, y los pánicos deben tratarse cuidadosamente en las fronteras FFI. `\#\[unsafe(no\_mangle)\]` en Rust 2024 sólo expresa una obligación de seguridad del atributo; no convierte una llamada FFI en memoria-segura por sí misma. 

### Solución industrial

La frontera C debe ser “panic contained”:

```
`\#\[no\_mangle\]`

`pub extern "C" fn polydim\_rust\_verify(`

`    ptr: \*const f64,`

`    n: usize,`

`    out: \*mut f64,`

`) -\> i32 \{`

`    let result = std::panic::catch\_unwind(`

`        std::panic::AssertUnwindSafe(|| \{`

`            verify\_impl(ptr, n, out)`

`        \})`

`    );`


`    match result \{`

`        Ok(code) =\> code,`

`        Err(\_) =\> POLYDIM\_ERR\_RUST\_PANIC,`

`    \}`

`\}`
```

Y además:

```
`null pointer`

`length`

`alignment`

`aliasing`

`output validity`
```

deben verificarse antes de entrar en la lógica.


# CICLO 30 — `/fp:precise` NO ES EL MISMO CONTRATO QUE CONTROLAR EL FP ENVIRONMENT

El dossier pone:

```
`/fp:precise`
```

pero también discute control runtime del FP environment.

MSVC distingue `/fp:precise` y `/fp:strict`; esta última está diseñada para permitir un control más estricto del entorno de punto flotante en runtime. 

### Solución

Si el kernel toca el entorno:

```
`save FP state`

`set required state`

`run`

`restore exact state`
```

por thread.

Además test:

```
`uint32\_t before = read\_fp\_env();`


`kernel();`


`uint32\_t after = read\_fp\_env();`


`assert(before == after);`
```

La propiedad industrial no es:

```
`“nosotros usamos FTZ=0”`
```

sino:

```
`“la llamada no modifica el entorno observable del proceso/thread”.`
```


# CICLO 31 — LA AFIRMACIÓN SOBRE DPI DEBE ELIMINARSE

El dossier dice:

I(X;Z)≤I(X;Y)I(X;Z)\\le I(X;Y) 

y simultáneamente:

> esto “viola el Data Processing Inequality”.

Eso está conceptualmente invertido.

La desigualdad mostrada **es precisamente** la Data Processing Inequality para X→Y→ZX\\to Y\\to Z. Para una función determinista Z=f(Y)Z=f(Y), se tiene:

I(X;Z)≤I(X;Y)I(X;Z)\\le I(X;Y) 

y si ff es invertible, puede haber igualdad. 

Por tanto:

```
`JSON/text serialization`
```

no “viola DPI” automáticamente.

Puede ser:

```
`lossy`

`lossless`

`invertible`

`quantized`

`slow`

`expensive`

`semantically destructive`
```

dependiendo de la codificación.

### Redacción matemáticamente correcta

```
`A textual or JSON serialization does not violate the`

`Data Processing Inequality.`


`The engineering concern is instead that a chosen encoding`

`may be lossy, quantized, latency-heavy, or may fail to preserve`

`the geometry/precision semantics required by the downstream operator.`


`A lossless invertible serialization can preserve the relevant`

`information, although it may still impose substantial computational`

`and memory overhead.`
```

Esto elimina una afirmación fácil de atacar en revisión científica.


# CICLO 32 — EL HARDWARE PROBE TIENE FALL-OPEN SILENCIOSO

El código:

```
`try:`

`    import torch`

`    if torch.cuda.is\_available():`

`        ...`

`except Exception:`

`    pass`
```

hace que:

```
`CUDA probe fails`
```

termine silenciosamente en:

```
`cuda\_available=False`
```

Eso es peligrosísimo para benchmarking reproducible.

Además:

```
`rocm\_available = False`
```

nunca se convierte en `True` en esta implementación. 

### Solución

Nunca:

```
`except Exception:`

`    pass`
```

para capacidades del hardware.

Usar:

```
`try:`

`    detect()`

`except Exception as e:`

`    info\["probe\_error"\] = repr(e)`
```

y mantener:

```
`UNKNOWN`
```

separado de:

```
`NOT\_AVAILABLE`
```


# CICLO 33 — HAY UNA RUTA DE DLL HARDCODEADA

**V**

```
`mingw\_bin = r"E:\\winlibs\_gcc14\_zip\\mingw64\\bin"`
```

Eso no pertenece a un componente industrial portable. 

Además:

```
`except Exception:`

`    pass`
```

oculta que falló.

### Solución

Orden:

```
`1. package-local runtime`

`2. configured runtime path`

`3. OS loader`

`4. explicit failure`
```

Nunca:

```
`E:\\...`
```

dentro del producto.


# CICLO 34 — EL OUTPUT PUEDE SER DEVUELTO COMO VÁLIDO AUNQUE EL KERNEL HAYA FALLADO

El wrapper hace:

```
`y\_out = np.empty(D, dtype=np.float64)`


`status = native(...)`


`return y\_out, status`
```

Si `status != 0`, `y\_out` no debe considerarse datos válidos.

### Solución

```
`status = ...`


`if status != 0:`

`    return None, status`


`return y\_out, status`
```

o:

```
`if status != POLYDIM\_SUCCESS:`

`    raise PolydimError(status)`


`return y\_out`
```

Para una librería industrial prefiero:

```
`Result\[T, Error\]`
```

semánticamente equivalente.


# CICLO 35 — `verify\_betti1()` TAMBIÉN DEJA PASAR MATRICES NO CUADRADAS

Actualmente:

```
`N = adj\_matrix.shape\[0\]`
```

y se ignora:

```
`adj\_matrix.shape\[1\]`
```

Por tanto:

```
`adj\_matrix.shape == (1000, 10)`
```

puede entrar como si fuera:

```
`1000 × 1000`
```

si el Rust supone N².

Esto es una ruta potencial de out-of-bounds.

El wrapper visible no la cierra. 

### Solución

```
`if adj\_matrix.ndim != 2:`

`    raise ValueError(...)`


`if adj\_matrix.shape\[0\] != adj\_matrix.shape\[1\]:`

`    raise ValueError("adjacency matrix must be square")`
```

pero, como indiqué arriba, **la mejor solución es abandonar la representación densa**.


# CICLO 36 — LA PRUEBA “26/26 PASS” NO ES PRUEBA DE SEGURIDAD INDUSTRIAL

Esto no es un ataque gratuito.

El propio reporte dice:

```
`26 passed`

`8 Rust passed`
```

Eso puede demostrar:

```
`these 26 scenarios passed`
```

No demuestra:

```
`memory safety`

`for all inputs`

`all thread interleavings`

`all compiler code generation`

`all supported CPUs`
```

Para concurrencia en particular:

```
`218,417 reads`
```

son excelentes para stress testing.

Pero no sustituyen:

```
`ThreadSanitizer`

`AddressSanitizer`

`UndefinedBehaviorSanitizer`

`MSan`

`Miri`

`loom/model-checker`

`weak-memory stress`

`cross-process stress`

`fault injection`
```

### Solución SOTA

Pipeline:

```
`UNIT`

` ↓`

`PROPERTY TEST`

` ↓`

`FUZZ`

` ↓`

`ASAN/UBSAN`

` ↓`

`TSAN`

` ↓`

`MIRI (Rust-compatible portions)`

` ↓`

`WEAK MEMORY MODEL`

` ↓`

`CROSS PROCESS`

` ↓`

`LONG-RUN STRESS`

` ↓`

`BENCH`

` ↓`

`REPRODUCIBILITY`
```


# CICLO 37 — EL TEST PMTP “0 TORN READS” NO DEMUESTRA AUSENCIA DE DATA RACE

El propio test indica:

```
`writes=452583`

`reads\_ok=1098`

`races\_detected=82548`

`undetected torn reads=0`
```

Eso es un buen resultado experimental.

Pero:

```
`0 observed failures`
```

no implica:

```
`no undefined behavior`
```

sobre todo si el payload se accede con tipos no atómicos mientras otro thread/proceso puede escribirlo.

C++ y el hardware pueden producir interleavings que no aparecen en esa ejecución. 

### Solución

Un test especial debe tratar el protocolo como una máquina de estados.

Ejemplo:

```
`N slots = 3`


`reader acquire`

`writer begin`

`writer commit`

`reader validate`

`reader release`
```

y comprobar formalmente:

```
`writer never enters WRITING`

`    while reader lease \> 0`


`reader never acquires`

`    while slot is WRITING`


`published generation is monotonic`


`validated payload corresponds exactly`

`to one generation`
```

Eso es mucho más fuerte que mirar bytes después de la carrera.


# CICLO 38 — EL CLAIM “NO HAY STARVATION” TAMPOCO SALE DE 1 TEST

Un test:

```
`1098 lecturas coherentes`
```

prueba que hubo progreso en esa ejecución.

No prueba:

∀schedules\\forall schedules 

que un reader eventualmente progresa.

Para afirmar lock-free/liveness hay que definir exactamente:

```
`obstruction-free`

`lock-free`

`wait-free`
```

No son sinónimos.

### Solución

Documentar:

```
`SAFETY:`

`    no torn payload accepted`


`LIVENESS:`

`    some operation always makes progress`


`WAIT-FREEDOM:`

`    each operation completes within bounded steps`
```

Y decidir cuál es realmente el objetivo.


# CICLO 39 — “TRIBUNAL UNÁNIME” NO ES UNA PRUEBA

El dossier tiene:

```
`Claude`

`ChatGPT`

`DeepSeek`

`...`
```

y termina:

```
`unanimously certified`
```

Eso tiene valor como revisión adversarial.

Pero:

```
`N modelos dicen X`
```

no convierte X en un teorema.

Y especialmente no puede invalidar una objeción matemática simplemente porque otro modelo la llamó “hallucination”.

Aquí sucedió algo especialmente instructivo:

El tribunal refutó:

> “Cayley mantiene ortogonalidad”

pero el verdadero bug que encontré ahora es otro:

> **mantener ortogonalidad ≠ satisfacer la condición diferencial de retraction.**

No necesito decidir qué modelo tuvo razón antes.

Sólo necesito calcular:

R′(0).R'(0). 

Y la cuenta está hecha arriba.


# CICLO 40 — HAY QUE DIVIDIR LAS AFIRMACIONES EN NIVELES DE CERTIFICACIÓN

Ahora mismo el dossier mezcla:

```
`mathematical theorem`

`unit test`

`benchmark`

`stress test`

`engineering policy`

`tribunal opinion`
```

como si fueran la misma clase de evidencia.

No lo son.

Propongo este esquema:

```
`LEVEL M0`

`Algebraically defined`


`LEVEL M1`

`Proven theorem`


`LEVEL N0`

`Numerically tested`


`LEVEL N1`

`Property-tested/fuzzed`


`LEVEL C0`

`Memory-safe under sanitizers`


`LEVEL C1`

`Cross-process/concurrency validated`


`LEVEL P0`

`Performance characterized`


`LEVEL I0`

`Reproducible industrial artifact`
```

Una afirmación sólo puede usar el nivel que realmente alcanzó.


# EL PARCHE ESTRUCTURAL QUE YO HARÍA AHORA

No intentaría agregar otros 20 parches pequeños encima del diseño actual.

Haría cinco cambios de arquitectura.

## A. Una única ABI

Header:

```
`\#define POLYDIM\_ABI\_VERSION 76201`


`typedef int32\_t polydim\_status\_t;`


`typedef struct \{`

`    double basis\_ortho;`

`    double point\_norm;`

`    double gram\_ortho;`

`    double pivot\_rel;`

`    int32\_t reject\_subnormal;`

`\} PolydimTolerances;`
```

No:

```
`int`
```

si quieres un contrato ABI explícito entre lenguajes.

Static checks:

```
`\_Static\_assert(sizeof(double) == 8,`

`               "POLYDIM requires binary64");`


`\_Static\_assert(sizeof(int32\_t) == 4,`

`               "broken platform ABI");`
```


# B. FFI Python seguro

Versión compacta:

```
`import ctypes as C`

`import numpy as np`



`class PolydimTolerances(C.Structure):`

`    \_fields\_ = \[`

`        ("basis\_ortho", C.c\_double),`

`        ("point\_norm", C.c\_double),`

`        ("gram\_ortho", C.c\_double),`

`        ("pivot\_rel", C.c\_double),`

`        ("reject\_subnormal", C.c\_int32),`

`    \]`



`class PolydimReport(C.Structure):`

`    \_fields\_ = \[`

`        ("point\_norm\_err", C.c\_double),`

`        ("basis\_uu\_err", C.c\_double),`

`        ("basis\_vv\_err", C.c\_double),`

`        ("basis\_uv\_err", C.c\_double),`

`        ("out\_norm\_err", C.c\_double),`

`        ("pivot\_min", C.c\_double),`

`        ("pivot\_threshold", C.c\_double),`

`        ("ortho\_err", C.c\_double),`

`        ("threads\_used", C.c\_uint64),`

`    \]`



`def require\_vector(`

`    a: np.ndarray,`

`    D: int,`

`    name: str,`

`) -\> np.ndarray:`

`    if not isinstance(a, np.ndarray):`

`        raise TypeError(f"\{name\}: ndarray required")`


`    if a.dtype != np.float64:`

`        raise TypeError(f"\{name\}: float64 required")`


`    if a.ndim != 1 or a.size != D:`

`        raise ValueError(`

`            f"\{name\}: expected (\{D\},), got \{a.shape\}"`

`        )`


`    if not a.flags.c\_contiguous:`

`        raise ValueError(f"\{name\}: C contiguous required")`


`    if not a.flags.aligned:`

`        raise ValueError(f"\{name\}: aligned required")`


`    return a`
```

Después:

```
`def apply\_rodrigues(`

`    self,`

`    y,`

`    u,`

`    v,`

`    theta,`

`):`

`    D = y.size`


`    y = require\_vector(y, D, "y")`

`    u = require\_vector(u, D, "u")`

`    v = require\_vector(v, D, "v")`


`    out = np.empty(D, dtype=np.float64)`


`    tol = self.default\_tolerances(D)`

`    report = PolydimReport()`


`    status = self.cpp\_lib.polydim\_rodrigues\_geodesic\_f64(`

`        y.ctypes.data,`

`        u.ctypes.data,`

`        v.ctypes.data,`

`        out.ctypes.data,`

`        C.c\_double(theta),`

`        C.c\_uint64(D),`

`        C.byref(tol),`

`        C.byref(report),`

`    )`


`    if status != 0:`

`        raise RuntimeError(`

`            f"POLYDIM Rodrigues failed: \{status\}"`

`        )`


`    return out, report`
```

Esto elimina una enorme clase de errores de frontera.


# C. PMTP con lease real

La API conceptual correcta:

```
`with pmtp.acquire\_read() as tensor:`

`    consume(tensor)`
```

Internamente:

```
`acquire`

`  ↓`

`CAS state`

`  ↓`

`increment lease`

`  ↓`

`re-check generation`

`  ↓`

`reader owns snapshot`

`  ↓`

`consume`

`  ↓`

`release lease`
```

El writer sólo reutiliza:

```
`slot == FREE`
```

nunca:

```
`slot parece no observado`
```


# D. Retracción Stiefel corregida

El núcleo matemático:

```
`Omega = X.T @ G`


`U = np.concatenate(`

`    \[G, X\],`

`    axis=1,`

`)`


`V = np.concatenate(`

`    \[X, -G + X @ Omega\],`

`    axis=1,`

`)`


`M = np.eye(2 \* K) - (`

`    0.5 \* tau \* (V.T @ U)`

`)`


`B = V.T @ X`


`Z = solve(M, B)`


`Y = X + tau \* (U @ Z)`
```

Y tests obligatorios:

```
`XᵀX = I`

`G tangent`

`R(0) = X`

`dR/dτ|0 = G`

`YᵀY = I`
```

No sólo:

```
`YᵀY ≈ I`
```


# E. El nuevo test SOTA para encontrar el bug que el tribunal no encontró

Este test es especialmente valioso:

```
`def test\_stiefel\_retraction\_first\_order(`

`    X,`

`    G,`

`    retraction,`

`):`

`    \# Construir G con componente vertical no nula`

`    D, K = X.shape`


`    R = np.random.randn(K, K)`

`    Omega = R - R.T`


`    A = np.random.randn(D, K)`

`    G\_perp = A - X @ (X.T @ A)`


`    G = G\_perp + X @ Omega`


`    \# Tangencia`

`    tangency = np.linalg.norm(`

`        X.T @ G + G.T @ X,`

`        ord="fro",`

`    )`


`    assert tangency \< 1e-12`


`    previous = None`


`    for p in \[4, 8, 12, 16\]:`

`        tau = 2.0 \*\* (-p)`


`        Y = retraction(X, G, tau)`


`        err = np.linalg.norm(`

`            (Y - X) / tau - G,`

`            ord="fro",`

`        )`


`        if previous is not None:`

`            \# esperamos reducción aproximadamente de primer orden`

`            assert err \< previous \* 0.75`


`        previous = err`
```

Esto ataca precisamente la propiedad que el test:

```
`max |YᵀY-I|`
```

no verifica.


# MI DIAGNÓSTICO DE “ALUCINACIÓN”

## Confirmación explícita

### **No son alucinaciones estos hallazgos:**

**1.** El Python V762 público tiene **2 buffers**, no 3. 

**2.** El Python escribe el control mediante un `numpy` array y lo llama “atomic sequence”; eso no demuestra una operación atómica IPC. 

**3.** `read\_tensor()` devuelve una vista directa al mmap. 

**4.** Los wrappers FFI visibles sólo validan `dtype`, no dimensiones/layout completos. 

**5.** Hay discrepancia entre los prototipos del header del dossier y los símbolos/aridad usados por Python.

**6.** La derivación:

R′(0)=G−XGTX=G+X(XTG)R'(0)=G-XG^TX=G+X(X^TG) 

es una consecuencia algebraica directa de la fórmula declarada.

**7.** Por tanto, afirmar que esa fórmula es una retraction para cualquier G∈TXSt(D,K)G\\in T\_XSt(D,K) requiere una corrección matemática adicional.

**8.** La DPI está usada incorrectamente en el dossier: I(X;Z)≤I(X;Y)I(X;Z)\\le I(X;Y) es precisamente la desigualdad, no su violación. 

**9.** Rust `\#\[unsafe(no\_mangle)\] + panic="unwind"` no constituye por sí mismo una garantía de seguridad FFI. 

**10.** El modelo de memoria C++ exige sincronización adecuada para evitar data races. 

**11.** La semántica del mapping Windows no implementa por sí sola el contrato `create=False`. 

**12.** El manejo POSIX mostrado no completa el lifecycle de fd/unlink. 

**13.** Una cota universal 64ϵ64\\epsilon, independiente de D, no queda demostrada por los tests reportados; requiere una prueba específica del algoritmo numérico. 

**14.** `/fp:precise` no debe confundirse con un contrato completo sobre el floating-point environment. 


# Y AHORA LO MÁS IMPORTANTE: QUÉ NO VOY A LLAMAR BUG

No voy a decir:

```
`“el C++ tiene UB aquí”`
```

porque **el C++ completo no está en el ZIP**.

No voy a decir:

```
`“Rust tiene un double free”`
```

porque no tengo `rust/src/lib.rs`.

No voy a decir:

```
`“el Triton está mal”`
```

porque el kernel Triton no está presente.

Eso sería exactamente la clase de “alucinación” que me pediste eliminar.

En cambio:

```
`Python visible → BUG verificable`

`fórmula matemática → BUG verificable`

`contrato ABI visible → inconsistencia verificable`

`documentación oficial → propiedad verificable`

`C++ ausente → NO CERTIFICADO, NO INVENTADO`
```

Ese es el estándar que propongo mantener durante las siguientes mordidas.

## Estado real después de este ciclo

El sistema **todavía no está en estado de cierre industrial**. Los bloqueadores principales son:

```
`P0-1  Artefacto auditado ≠ fuente completa`

`P0-2  V762 declarado triple-buffer ≠ Python real de 2 buffers`

`P0-3  PMTP no demuestra atomicidad/lifetime seguro`

`P0-4  ABI C ↔ Python inconsistente`

`P0-5  Stiefel retraction matemáticamente mal especificada`

`P0-6  FFI permite inputs con layout/tamaño incompatibles`

`P0-7  Rust FFI safety claim incorrecto`
```

Y después vienen los **P1** numéricos/topológicos/performance.

Esto ya explica una parte de por qué después de cientos de iteraciones podían seguir apareciendo problemas: **se estaba cerrando “la propiedad que se testeaba”, no necesariamente la propiedad que el nombre del componente prometía**. El ejemplo perfecto es Stiefel: `YᵀY≈I` podía dar excelente, mientras la condición diferencial de retraction seguía sin comprobarse.

El próximo ciclo que corresponde atacar, siguiendo esta misma metodología, es **C++/Rust real: ownership, aliasing, `restrict`, OpenMP, layout, reducción Neumaier, TwoSum, MXCSR, ASan/UBSan/TSan, solver SMW y todas las rutas tempranas de error**, porque ahí todavía no conviene inventar un solo defecto sin el cuerpo de las implementaciones.

