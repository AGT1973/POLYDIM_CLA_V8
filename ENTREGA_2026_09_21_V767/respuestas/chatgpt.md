

Sí. Y voy a ser directo con esto: **tu crítica al proceso anterior es válida**. Con un sistema de unas pocas miles de líneas, después de tantas rondas, no debería seguir apareciendo una nueva “lista de diez cosas” como si estuviéramos descubriendo el código desde cero. Eso indica que el método de auditoría anterior fue demasiado incremental y demasiado centrado en defectos locales.

Esta ronda cambia de método: **no voy a tratar cada bug como una isla**. Voy a cerrar familias enteras de errores y a exigir que cada propiedad tenga un contrato, una implementación y una prueba que la demuestre.

Y sí: **los hallazgos que marco abajo como CONFIRMADOS no son alucinaciones**. Los separo de los que son inferencias de diseño y de los que no pude ejecutar porque en este entorno no hay Rust/Dart.

# 1. Primera corrección importante: el problema no es que haya “demasiadas líneas”

El paquete tiene alrededor de 2.5k líneas de fuentes ejecutables repartidas entre C++, Python, Rust y Dart; el C++ central ronda 1k.

Eso debería ser perfectamente auditable.

El motivo por el que siguen apareciendo fallos es otro:

```
\`                 2.000 líneas\`  
  
\`                      │\`  
  
\`       ┌──────────────┼──────────────┐\`  
  
\`       │              │              │\`  
  
\`      C++            Rust           Dart\`  
  
\`       │              │              │\`  
  
\`       └────── ABI ───┴──── FFI ─────┘\`  
  
\`                      │\`  
  
\`                 memoria/atomics\`  
  
\`                      │\`  
  
\`               matemática FP64\`  
  
\`                      │\`  
  
\`                 CPU / ARM / GPU\`  
  
\`                      │\`  
  
\`              transporte / RDMA\`
```

Una línea incorrecta en un ABI puede invalidar 500 líneas correctas.

Una máquina de estados incorrecta en PMTP puede volver irrelevantes todos los benchmarks que estén encima.

Una cota numérica incorrecta puede hacer que una implementación perfectamente razonable quede mal certificada.

Así que **no voy a seguir buscando “bugs sueltos”**. El objetivo pasa a ser:

cerrar invariantes completos\\boxed\{ \\text\{cerrar invariantes completos\} \}

# 2. Confirmación de evidencia

Voy a usar esta clasificación:

**\[C\] CONFIRMADO**  
Lo reproduce el código o una prueba local.

**\[D\] DEMOSTRADO POR CONTRADICCIÓN**  
El contrato/documentación afirma A y el código hace B.

**\[S\] SOTA / DISEÑO RECOMENDADO**  
No es un bug necesariamente, sino la solución industrial que sustituiría la actual.

**\[U\] NO VERIFICABLE AÚN**  
Depende de Rust/Dart/hardware/logs que no están ejecutables aquí.

No voy a vender \[U\] como \[C\].

# 3. NUEVOS BLOQUEADORES QUE ENCONTRÉ EN ESTA RONDA

## 3.1 \[C\] `polydim\\\_project\\\_sphere\\\_f64()` reporta el dato equivocado

Este es importante porque aparentemente fue “arreglado” en una ronda anterior.

El código hace:

```
\`const double n = std::sqrt(n2);\`  
  
  
\`if (report)\`  
  
\`    report-\\\>point\\\_norm\\\_err = std::abs(n - 1.0);\`  
  
  
\`const double inv = 1.0 / n;\`  
  
  
\`...\`  
  
  
\`for (...)\`  
  
\`    y\\\_out\\\[i\\\] = y\\\[i\\\] \\\* inv;\`  
  
  
\`return POLYDIM\\\_SUCCESS;\`
```

Pero **no calcula `out\\\_norm\\\_err`**.

Y el propio `PolydimReport` tiene:

```
\`r-\\\>point\\\_norm\\\_err = -1.0;\`  
  
\`...\`  
  
\`r-\\\>out\\\_norm\\\_err = -1.0;\`
```

Así que después de una operación exitosa puedes tener:

```
\`point\\\_norm\\\_err = error de la entrada\`  
  
\`out\\\_norm\\\_err   = -1\`
```

aunque el dossier presente el reporte como si certificara el resultado.

### Prueba local

Con el C++ entregado, medí independientemente:

```
\`D = 10,000\`  
  
\`D = 1,000,000\`  
  
\`D = 10,000,000\`
```

El vector resultante era unitario dentro del error esperado, **pero `out\\\_norm\\\_err` seguía en `-1`**.

### Corrección

El API tiene que decidir qué informa:

```
\`report-\\\>input\\\_norm\\\_err = ...\`  
  
\`report-\\\>output\\\_norm\\\_err = ...\`
```

No reutilizar semánticamente `point\\\_norm\\\_err`.

Y después:

```
\`double out\\\_n2 = compensated\\\_norm2(y\\\_out);\`  
  
\`double out\\\_n = std::sqrt(out\\\_n2);\`  
  
\`double out\\\_err = std::abs(out\\\_n - 1.0);\`  
  
  
\`report-\\\>out\\\_norm\\\_err = out\\\_err;\`  
  
  
\`if (out\\\_err \\\> tol.point\\\_norm)\`  
  
\`    return POLYDIM\\\_ERR\\\_NUMERICAL\\\_INSTABILITY;\`
```

# 4. \[C\] Las tolerancias NaN permiten saltarse las compuertas matemáticas

Esta es particularmente fea.

El código toma directamente:

```
\`const PolydimTolerances tol =\`  
  
\`    tol\\\_in ? \\\*tol\\\_in : polydim\\\_default\\\_tolerances(D);\`
```

pero no comprueba que las tolerancias sean finitas.

La comprobación posterior es:

```
\`if (e\\\_uu \\\> tol.basis\\\_ortho ||\`  
  
\`    e\\\_vv \\\> tol.basis\\\_ortho ||\`  
  
\`    e\\\_uv \\\> tol.basis\\\_ortho)\`
```

En IEEE:

```
\`3.0 \\\> NaN\`
```

es falso.

Lo probé localmente con:

```
\`tol.basis\\\_ortho = NaN;\`  
  
\`tol.point\\\_norm  = NaN;\`  
  
\`tol.gram\\\_ortho  = NaN;\`  
  
\`tol.pivot\\\_rel   = NaN;\`
```

y una base claramente no ortonormal:

```
\`u = \\\[0,2,0,0\\\]\`
```

La función devolvió:

```
\`rc = 0\`
```

y el informe registró:

```
\`basis\\\_uu\\\_err = 3.0\`
```

pero aceptó el resultado.

### Esto invalida cualquier frase tipo

> “las compuertas garantizan la variedad”.

No si el caller controla `tol\\\_in`.

### Solución

Antes de usar cualquier tolerancia:

```
\`inline bool valid\\\_tolerances(const PolydimTolerances& t) noexcept \\\{\`  
  
\`    return\`  
  
\`        std::isfinite(t.basis\\\_ortho) &&\`  
  
\`        std::isfinite(t.point\\\_norm) &&\`  
  
\`        std::isfinite(t.gram\\\_ortho) &&\`  
  
\`        std::isfinite(t.pivot\\\_rel) &&\`  
  
\`        (t.basis\\\_ortho \\\>= 0.0) &&\`  
  
\`        (t.point\\\_norm  \\\>= 0.0) &&\`  
  
\`        (t.gram\\\_ortho  \\\>= 0.0) &&\`  
  
\`        (t.pivot\\\_rel   \\\>= 0.0);\`  
  
\`\\\}\`
```

y:

```
\`if (tol\\\_in && !valid\\\_tolerances(\\\*tol\\\_in))\`  
  
\`    return POLYDIM\\\_ERR\\\_INVALID\\\_TOLERANCE;\`
```

**Nueva clase cerrada:** *toda configuración numérica externa debe ser validada como input hostil.*

# 5. \[C\] `reject\\\_subnormal` existe, pero es un interruptor muerto

El campo está en la estructura:

```
\`t.reject\\\_subnormal = 0;\`
```

y en Rust también existe un estado:

```
\`ErrSubnormalDetected = -4\`
```

pero la implementación no ejecuta la política correspondiente.

Por tanto hay tres conceptos incompatibles:

```
\`“soportamos subnormales”\`  
  
\`“podemos rechazarlas”\`  
  
\`“hay un error ErrSubnormalDetected”\`
```

pero no existe una máquina de estados real que conecte los tres.

### Solución

Definir una sola política:

```
\`ALLOW\`  
  
\`WARN\`  
  
\`REJECT\`
```

y aplicar la misma semántica en:

```
\`C++\`  
  
\`Rust\`  
  
\`CUDA/Triton\`  
  
\`Dart status mapping\`
```

# 6. \[C\] El namespace numérico de errores C++ y Rust está roto

Esto es importante y no lo había elevado suficientemente antes.

Rust:

```
\`ErrSubnormalDetected = -4\`
```

C++/Dart interpreta:

```
\`-4 = DEGENERATE\\\_NORM\`
```

Es decir:

```
\`         -4\`  
  
\`          │\`  
  
\`     ┌────┴────┐\`  
  
\`     │         │\`  
  
\`    Rust      C++\`  
  
\`     │         │\`  
  
\`SUBNORMAL   DEGENERATE\`
```

El mismo número significa dos cosas distintas.

Eso es una **violación del ABI lógico**, incluso aunque físicamente la llamada FFI tenga el número correcto.

### Solución industrial

Un solo header ABI:

```
\`typedef int32\\\_t PolydimStatus;\`  
  
  
\`enum \\\{\`  
  
\`    POLYDIM\\\_OK                    = 0,\`  
  
  
\`    POLYDIM\\\_ERR\\\_NULL\\\_POINTER      = -1,\`  
  
\`    POLYDIM\\\_ERR\\\_INVALID\\\_DIMENSION = -2,\`  
  
\`    POLYDIM\\\_ERR\\\_NAN\\\_OR\\\_INF        = -3,\`  
  
\`    POLYDIM\\\_ERR\\\_DEGENERATE\\\_NORM   = -4,\`  
  
\`    POLYDIM\\\_ERR\\\_NUMERICAL          = -5,\`  
  
\`    POLYDIM\\\_ERR\\\_TOPOLOGY           = -6,\`  
  
\`    POLYDIM\\\_ERR\\\_BUFFER             = -7,\`  
  
\`    POLYDIM\\\_ERR\\\_INVALID\\\_SCALAR     = -8,\`  
  
\`    POLYDIM\\\_ERR\\\_BASIS              = -9,\`  
  
\`    POLYDIM\\\_ERR\\\_MANIFOLD           = -10,\`  
  
\`    POLYDIM\\\_ERR\\\_ALIAS              = -11,\`  
  
\`    POLYDIM\\\_ERR\\\_TOLERANCE          = -12,\`  
  
\`    POLYDIM\\\_ERR\\\_SUBNORMAL          = -13,\`  
  
\`    POLYDIM\\\_ERR\\\_ABI                = -14,\`  
  
\`    POLYDIM\\\_ERR\\\_INTERNAL           = -99\`  
  
\`\\\};\`
```

Rust debe **reexportar esos valores**, no inventar los suyos.

# 7. \[C\] `CholQR2` tiene una propiedad mucho más peligrosa: puede modificar la salida y luego fallar

La función trabaja in-place:

```
\`xi\\\[k\\\] = val / L\\\[k \\\* K + k\\\];\`
```

Si aparece una condición numéricamente mala, el error puede producirse **después de haber modificado `X`**.

Lo probé.

Con datos finitos grandes del orden de:

```
\`1e154\`
```

obtuvimos:

```
\`rc = error\`
```

pero `X` ya había sido transformada.

Con escalas todavía mayores aparecieron:

```
\`NaN\`
```

en la matriz parcialmente modificada antes del retorno.

### Problema contractual

¿Qué significa?

```
\`rc != SUCCESS\`
```

¿El `X`:

- sigue siendo válido?

- está parcialmente modificado?

- está indeterminado?

Actualmente no está definido.

### Industria

Toda operación que reclame robustez debe tener semántica:

```
\`SUCCESS:\`  
  
\`    output válido\`  
  
  
\`ERROR:\`  
  
\`    output unchanged\`
```

o:

```
\`ERROR:\`  
  
\`    output unspecified\`
```

pero tiene que estar documentado.

### Mi elección

Para operaciones geométricas:

transaccionalidad\\boxed\{\\text\{transaccionalidad\}\}

Calcular sobre scratch y publicar solamente si toda la operación pasa:

```
\`temporary -\\\> validate -\\\> commit\`
```

# 8. \[C\] `CholQR2` usa un umbral absoluto `1e-14`

Está literalmente aquí:

```
\`if (s \\\<= 1e-14)\`  
  
\`    return POLYDIM\\\_ERR\\\_DEGENERATE\\\_NORM;\`
```

Eso significa que la misma matriz matemática cambia de “válida” a “degenerada” simplemente escalándola.

Yo lo reproduje:

```
\`escala 1        -\\\> SUCCESS\`  
  
\`escala 1e-8     -\\\> DEGENERATE\`  
  
\`escala 1e-100   -\\\> DEGENERATE\`
```

aunque la matriz siga teniendo rango 2.

### Esto no es una sutileza

Si:

X=QRX = QR

entonces:

10−8X10^\{-8\}X

sigue teniendo exactamente el mismo rango.

La rutina actual no está evaluando condición relativa; está evaluando tamaño absoluto.

### Solución

Usar umbral relativo:

τdiag=u⋅f(K)⋅∥A∥∞\\tau\_\{\\rm diag\} = u\\cdot f(K)\\cdot \\|A\\|\_\\infty

por ejemplo:

```
\`double scale = matrix\\\_inf\\\_norm(A);\`  
  
  
\`if (!std::isfinite(scale) || scale == 0.0)\`  
  
\`    return POLYDIM\\\_ERR\\\_DEGENERATE\\\_NORM;\`  
  
  
\`double pivot\\\_tol =\`  
  
\`    std::numeric\\\_limits\\\<double\\\>::epsilon()\`  
  
\`    \\\* std::max\\\<double\\\>(1.0, static\\\_cast\\\<double\\\>(K))\`  
  
\`    \\\* scale;\`  
  
  
\`if (!(s \\\> pivot\\\_tol))\`  
  
\`    return POLYDIM\\\_ERR\\\_DEGENERATE\\\_NORM;\`
```

Mejor aún: añadir una estimación de condicionamiento.

LAPACK dispone de rutinas para estimación de condición y refinamiento; `DGESVX`, por ejemplo, combina factorización, estimación de condición, refinamiento iterativo y cotas de error.

# 9. \[C\] `CholQR2` tiene además un límite K distinto del resto del sistema

En C++:

```
\`if (K \\\> 1024)\`  
  
\`    return POLYDIM\\\_ERR\\\_BUFFER\\\_OVERFLOW;\`
```

pero el resto del solver declara:

```
\`POLYDIM\\\_MAX\\\_K = 512\`
```

Por tanto:

```
\`Stiefel K=513 -\\\> rechazo\`  
  
\`CholQR2 K=513 -\\\> acepta\`
```

aunque ambos viven dentro del mismo “POLYDIM”.

### Solución

No duplicar límites.

Una única constante ABI:

```
\`POLYDIM\\\_MAX\\\_K\`
```

y una única política de presupuesto:

```
\`max\\\_K\\\_for\\\_memory(D, threads, backend)\`
```

# 10. \[C\] `CholQR2` no tiene presupuesto de memoria por hilo

Hace:

```
\`std::vector\\\<double\\\>\`  
  
\`    thread\\\_XTX(max\\\_threads \\\* K \\\* K, 0.0);\`
```

No hay limitación.

Con:

```
\`K = 1024\`
```

y:

```
\`max\\\_threads = 256\`
```

se llega a aproximadamente:

256×10242×8≈2 GB256\\times1024^2\\times8 \\approx 2\\,GB

solo para ese array.

Y eso aparece dos veces, una por cada paso.

La contradicción es particularmente clara porque el solver de Stiefel sí creó un presupuesto explícito, mientras `CholQR2` no.

# 11. \[C\] `D` está declarado como `uint64\\\_t` pero varios loops lo reducen a `int64\\\_t`

Ejemplo:

```
\`for (int64\\\_t i = 0;\`  
  
\`     i \\\< static\\\_cast\\\<int64\\\_t\\\>(D);\`  
  
\`     ++i)\`
```

Eso hace que el API admita formalmente:

D\>263−1D\>2^\{63\}-1

pero internamente lo convierta a signed 64-bit.

Lo mismo aparece en varias regiones.

### Solución

O:

```
\`if (D \\\> INT64\\\_MAX)\`  
  
\`    return POLYDIM\\\_ERR\\\_INVALID\\\_DIMENSION;\`
```

o convertir todos los bucles a `uint64\\\_t`.

Para una API que pretende vivir más allá del silicio actual, prefiero la segunda.

# 12. \[C\] La ruta BLAS tiene otra conversión peligrosa: `D -\\\> int`

En Stiefel:

```
\`const int n = static\\\_cast\\\<int\\\>(K2),\`  
  
\`          kk = static\\\_cast\\\<int\\\>(D);\`
```

BLAS clásico utiliza enteros para esas dimensiones.

Por tanto, el backend BLAS tiene un contrato distinto del backend nativo:

```
\`native D: uint64\\\_t\`  
  
\`BLAS D:   int\`
```

### Solución

Si se usa BLAS:

```
\`D \\\<= INT\\\_MAX\`
```

o particionar la dimensión:

D=D1+D2+⋯+DmD = D\_1+D\_2+\\dots+D\_m

y acumular:

XTX=∑iXiTXi.X^TX=\\sum\_i X\_i^TX\_i.

Eso además es mejor para NUMA y memoria.

# 13. \[C\] El “selftest\_all” no prueba “all”

Esto parece menor, pero en un release industrial es gravísimo.

`polydim\\\_selftest\\\_all()` prueba:

- compensación;

- theta NaN;

- base no ortonormal;

- punto fuera de esfera.

No prueba:

```
\`PMTP\`  
  
\`CholQR2\`  
  
\`Stiefel\`  
  
\`Rust\`  
  
\`FFI\`  
  
\`Dart\`  
  
\`Triton\`  
  
\`MIR\`  
  
\`Quantum\`  
  
\`Tangent adapter\`
```

Por tanto:

```
\`selftest\\\_all() == SUCCESS\`
```

no significa:

```
\`POLYDIM == HEALTHY\`
```

### Solución

Separar:

```
\`selftest\\\_numeric()\`  
  
\`selftest\\\_geometry()\`  
  
\`selftest\\\_pmtp()\`  
  
\`selftest\\\_ffi()\`  
  
\`selftest\\\_transport()\`  
  
\`selftest\\\_gpu()\`  
  
\`selftest\\\_topology()\`  
  
\`selftest\\\_quantum()\`
```

y:

```
\`polydim\\\_selftest\\\_all()\`
```

solo devuelve éxito cuando **todos** los subsistemas disponibles han pasado.

# 14. \[D\] El propio dossier declara una prueba que el paquete no contiene

El README dice que se entregan:

```
\`polydim.h / polydim\\\_kernel.h\`
```

y los benchmarks declaran raw logs:

```
\`eval\\\_logs/test\\\_ring3\\\_win11.log\`  
  
\`eval\\\_logs/all\\\_milestones\\\_linux.json\`  
  
\`...\`
```

pero esos artefactos no están en el ZIP.

Además la matriz de benchmark afirma explícitamente que fue:

> “100% physically executed on real silicon with Exit Code 0 and attached raw log artifacts.”

mientras los logs correspondientes no forman parte del paquete.

Y el benchmark documenta específicamente, por ejemplo, 0 torn reads en PMTP y 70.51 GB/s en T4.

### Conclusión correcta

No digo:

> “los benchmarks son falsos”.

Digo:

> **el paquete no permite auditarlos/reproducirlos.**

Eso es una diferencia crucial.

# 15. \[C\] PMTP sigue sin ser un seqlock

La función es:

```
\`polydim\\\_pmtp\\\_begin\\\_write(...) \\\{\`  
  
\`    uint8\\\_t s =\`  
  
\`        c-\\\>state.load(std::memory\\\_order\\\_acquire);\`  
  
  
\`    \\\*slot\\\_out = (s \\\>\\\> 4) & 3;\`  
  
\`    return POLYDIM\\\_SUCCESS;\`  
  
\`\\\}\`
```

Esto **no reserva el slot**.

Dos writers:

```
\`W1 load(state)\`  
  
\`W2 load(state)\`
```

pueden obtener el mismo slot.

No hay:

```
\`CAS FREE -\\\> WRITING\`
```

La documentación del propio monolito lo presenta como triple buffer/seqlock, pero la implementación no tiene esa reserva.

### Corrección estructural

Yo abandonaría el “seqlock” de byte completo.

Usaría:

```
\`enum class SlotState : uint8\\\_t \\\{\`  
  
\`    FREE,\`  
  
\`    WRITING,\`  
  
\`    READY,\`  
  
\`    READING\`  
  
\`\\\};\`  
  
  
\`struct alignas(64) SlotMeta \\\{\`  
  
\`    std::atomic\\\<uint8\\\_t\\\>  state\\\{static\\\_cast\\\<uint8\\\_t\\\>(SlotState::FREE)\\\};\`  
  
\`    std::atomic\\\<uint32\\\_t\\\> readers\\\{0\\\};\`  
  
\`    std::atomic\\\<uint64\\\_t\\\> generation\\\{0\\\};\`  
  
\`\\\};\`
```

# 16. \[S\] PMTP robusto: readers pinzados, no “lee y luego valida”

La solución que propondría:

```
\`bool try\\\_acquire\\\_read(SlotMeta& s, uint64\\\_t& generation)\`  
  
\`\\\{\`  
  
\`    uint8\\\_t expected =\`  
  
\`        static\\\_cast\\\<uint8\\\_t\\\>(SlotState::READY);\`  
  
  
\`    if (!s.state.compare\\\_exchange\\\_strong(\`  
  
\`            expected,\`  
  
\`            static\\\_cast\\\<uint8\\\_t\\\>(SlotState::READING),\`  
  
\`            std::memory\\\_order\\\_acquire,\`  
  
\`            std::memory\\\_order\\\_relaxed))\`  
  
\`        return false;\`  
  
  
\`    s.readers.fetch\\\_add(1, std::memory\\\_order\\\_relaxed);\`  
  
\`    generation =\`  
  
\`        s.generation.load(std::memory\\\_order\\\_acquire);\`  
  
  
\`    return true;\`  
  
\`\\\}\`
```

El writer solo puede hacer:

```
\`FREE -\\\> WRITING\`
```

Nunca:

```
\`READY -\\\> WRITING\`
```

mientras existan lectores.

Con eso la garantía pasa de:

```
\`“espero que la validación detecte la carrera”\`
```

a:

```
\`“la carrera reader/writer está estructuralmente prohibida”.\`
```

Ese es el cambio que quiero.

# 17. \[C\] `validate\\\_read()` sigue siendo una función decorativa

Actualmente:

```
\`polydim\\\_pmtp\\\_validate\\\_read(...) \\\{\`  
  
\`    if (!c) return POLYDIM\\\_ERR\\\_NULL\\\_POINTER;\`  
  
\`    return POLYDIM\\\_SUCCESS;\`  
  
\`\\\}\`
```

No comprueba:

- slot;

- ticket;

- generation;

- estado;

- readers.

Así que una función llamada `validate\\\_read` está devolviendo éxito sin validar la lectura.

Eso debe desaparecer.

# 18. \[C\] Los status de PMTP `observed\\\_seq` y `ticket` son constantes

```
\`\\\*observed\\\_seq = 1;\`  
  
\`\\\*ticket\\\_out = 0;\`
```

Por lo tanto:

```
\`observed\\\_seq\`  
  
\`ticket\`
```

no son identificadores de una lectura.

Son valores ficticios.

Eso explica por qué el API parece mucho más robusto desde afuera de lo que realmente es.

# 19. \[C\] El C++ no tiene frontera noexcept segura en todas las funciones FFI

Hay funciones `extern "C"` que crean `std::vector`.

Por ejemplo Rodrigues:

```
\`std::vector\\\<Neumaier\\\> a\\\_yy(...);\`
```

Una reserva puede lanzar:

```
\`std::bad\\\_alloc\`
```

y esa excepción no está convertida a un status en esa función.

Esto es especialmente relevante porque Microsoft documenta explícitamente que una función C++ `extern "C"` llamada desde código no excepcional **no debe permitir que una excepción cruce la frontera**. Recomienda capturar y convertir a error.

### Solución

Patrón único:

```
\`extern "C" int32\\\_t POLYDIM\\\_CALL\`  
  
\`polydim\\\_xxx(...) noexcept\`  
  
\`\\\{\`  
  
\`    try \\\{\`  
  
\`        return polydim\\\_xxx\\\_impl(...);\`  
  
\`    \\\}\`  
  
\`    catch (const std::bad\\\_alloc&) \\\{\`  
  
\`        return POLYDIM\\\_ERR\\\_BUFFER\\\_OVERFLOW;\`  
  
\`    \\\}\`  
  
\`    catch (const std::exception&) \\\{\`  
  
\`        return POLYDIM\\\_ERR\\\_INTERNAL;\`  
  
\`    \\\}\`  
  
\`    catch (...) \\\{\`  
  
\`        return POLYDIM\\\_ERR\\\_INTERNAL;\`  
  
\`    \\\}\`  
  
\`\\\}\`
```

Y esto en **cada entrada pública**, no “en unas sí y otras no”.

# 20. \[C\] C++ tampoco tiene semántica de fallo transaccional homogénea

Tenemos al menos:

```
\`Rodrigues      -\\\> genera output y luego valida\`  
  
\`ProjectSphere  -\\\> escribe output\`  
  
\`Orthonormalize -\\\> modifica u/v in-place\`  
  
\`CholQR2        -\\\> modifica X in-place\`  
  
\`Stiefel       -\\\> escribe Y\\\_out\`
```

pero no hay una política universal:

```
\`qué queda válido cuando rc != SUCCESS\`
```

### Solución

Para industria:

```
\`VALIDATION\`  
  
\`    ↓\`  
  
\`COMPUTATION\`  
  
\`    ↓\`  
  
\`POSTCONDITION\`  
  
\`    ↓\`  
  
\`PUBLISH\`
```

Nunca:

```
\`COMPUTATION\`  
  
\`    ↓\`  
  
\`“a ver si salió bien”\`
```

# 21. \[C\] `project\\\_tangent\\\_stiefel` carece de las compuertas que sí tiene el solver

Esta función acepta:

```
\`X\`  
  
\`G\`  
  
\`G\\\_out\`  
  
\`D\`  
  
\`K\`
```

pero no comprueba:

```
\`K \\\<= D\`  
  
\`X^T X ≈ I\`  
  
\`finite(X)\`  
  
\`finite(G)\`  
  
\`aliasing\`
```

Yo mismo le pasé NaN en `G`.

Resultado:

```
\`rc = 0\`  
  
\`G\\\_out contiene NaN\`
```

Por tanto:

```
\`project\\\_tangent\\\_stiefel()\`
```

no es todavía una primitiva certificada.

# 22. \[C\] Para Stiefel, “tangent projection” solo es válida si X está en Stiefel

La fórmula:

PX(G)=G−Xsym⁡(XTG)P\_X(G)=G-X\\operatorname\{sym\}(X^TG)

es una proyección tangente válida bajo:

XTX=I.X^TX=I.

Pero la función no lo comprueba.

Por tanto el API real es:

> “proyección bajo la suposición no verificada de que X ya es Stiefel”.

### Solución

Dos APIs:

```
\`project\\\_tangent\\\_stiefel\\\_trusted()\`  
  
\`project\\\_tangent\\\_stiefel\\\_checked()\`
```

o una sola con:

```
\`check\\\_manifold = true\`
```

pero que quede expresado en el contrato.

# 23. \[C\] `\\\_\\\_restrict\\\_\\\_` y aliasing siguen siendo contradictorios

Rodrigues declara:

```
\`const double\\\* \\\_\\\_restrict\\\_\\\_ y\`  
  
\`...\`  
  
\`double\\\* \\\_\\\_restrict\\\_\\\_ y\\\_out\`
```

pero el comentario dice:

```
\`y\\\_out==y sí es legal\`
```

No se puede tener simultáneamente:

```
\`“el caller puede aliasar”\`
```

y:

```
\`“el compilador puede asumir no alias”.\`
```

### Solución

Dos entrypoints:

```
\`polydim\\\_rodrigues\\\_outofplace(...)\`  
  
\`polydim\\\_rodrigues\\\_inplace(...)\`
```

Eso además permite optimización distinta.

# 24. \[D\] El cálculo `overlaps()` no es una base portátil para una API ABI universal

Actualmente:

```
\`auto pa = static\\\_cast\\\<const char\\\*\\\>(a);\`  
  
\`auto pb = static\\\_cast\\\<const char\\\*\\\>(b);\`  
  
  
\`return (pa \\\< pb + bytes) &&\`  
  
\`       (pb \\\< pa + bytes);\`
```

Las comparaciones relacionales entre punteros de objetos arbitrarios no son una buena abstracción para establecer un orden total portátil; el estándar establece reglas especiales para los punteros de orígenes distintos.

### Solución

Convertir el contrato de buffers a rangos enteros con overflow comprobado:

```
\`struct ByteRange \\\{\`  
  
\`    uintptr\\\_t begin;\`  
  
\`    uintptr\\\_t end;\`  
  
\`\\\};\`  
  
  
\`bool make\\\_range(const void\\\* p, size\\\_t n, ByteRange& out)\`  
  
\`\\\{\`  
  
\`    if (!p) return false;\`  
  
  
\`    const uintptr\\\_t b =\`  
  
\`        reinterpret\\\_cast\\\<uintptr\\\_t\\\>(p);\`  
  
  
\`    if (n \\\> UINTPTR\\\_MAX - b)\`  
  
\`        return false;\`  
  
  
\`    out = \\\{ b, b + n \\\};\`  
  
\`    return true;\`  
  
\`\\\}\`
```

Luego comparar enteros.

# 25. \[C\] Rust puede aceptar NaN derivado de overflow aunque el input sea finito

En Rust el código comprueba que cada `val` sea finito.

Pero después calcula esencialmente:

```
\`val \\\* val\`
```

Para valores finitos enormes:

x2→∞x^2\\to\\infty

y puede aparecer:

∞+(−∞)=NaN.\\infty + (-\\infty)=NaN.

Después:

```
\`drift \\\> tol\`
```

con `drift = NaN` también es falso.

### Solución

La condición final debe ser explícita:

```
\`if !norm\\\_sq.is\\\_finite() \\\{\`  
  
\`    return ErrNanOrInf;\`  
  
\`\\\}\`  
  
  
\`let norm = norm\\\_sq.sqrt();\`  
  
  
\`if !norm.is\\\_finite() \\\{\`  
  
\`    return ErrNumericalInstability;\`  
  
\`\\\}\`
```

Y mejor aún: norma escalada.

# 26. \[C\] `from\\\_raw\\\_parts` no queda seguro por `catch\\\_unwind`

Esto sigue siendo importante.

Rust usa:

```
\`slice::from\\\_raw\\\_parts(ptr, d)\`
```

La función exige precondiciones de:

- validez;

- alineación;

- tamaño;

- representación;

- límites.

Esas precondiciones deben cumplirse antes. `catch\\\_unwind` captura panics; no convierte memoria inválida en memoria válida. La documentación de Rust lo establece explícitamente.

### Solución de arquitectura

No pasar:

```
\`(\\\*mut f64, usize)\`
```

como contrato genérico cuando pueda evitarse.

Usar:

```
\`typedef struct \\\{\`  
  
\`    const double\\\* ptr;\`  
  
\`    size\\\_t len;\`  
  
\`    uint64\\\_t allocation\\\_id;\`  
  
\`    uint64\\\_t generation;\`  
  
\`\\\} PolydimBuffer;\`
```

y validar el descriptor/origen dentro del runtime que lo crea.

# 27. \[C\] MIR-Wire acepta payload truncado

Código:

```
\`while bytes\\\_received \\\< tensor\\\_bytes:\`  
  
\`    n = conn.recv\\\_into(...)\`  
  
\`    if n == 0:\`  
  
\`        break\`  
  
\`    bytes\\\_received += n\`
```

y luego:

```
\`tensor = np.frombuffer(tensor\\\_buf, dtype=np.float64)\`  
  
\`self.received\\\_tensors.append((imm\\\_data, tensor))\`  
  
\`conn.sendall(b"ACK")\`
```

No existe:

```
\`if bytes\\\_received != tensor\\\_bytes:\`  
  
\`    reject\`
```

Así que:

```
\`payload truncado\`  
  
\`     ↓\`  
  
\`buffer parcialmente rellenado\`  
  
\`     ↓\`  
  
\`np.frombuffer()\`  
  
\`     ↓\`  
  
\`tensor aceptado\`  
  
\`     ↓\`  
  
\`ACK\`
```

Eso es un **bug de integridad de datos confirmado por inspección directa del flujo**.

# 28. \[C\] MIR-Wire tampoco es RDMA

Aquí el propio archivo ya delata el problema.

El módulo declara:

> `RDMA ... WRITE WITH IMMEDIATE`

pero implementa:

```
\`socket.socket(AF\\\_INET, SOCK\\\_STREAM)\`
```

y:

```
\`sendall()\`  
  
\`recv()\`  
  
\`recv\\\_into()\`
```

No hay:

```
\`ibverbs\`  
  
\`QP\`  
  
\`CQ\`  
  
\`MR registration\`  
  
\`RDMA WRITE WITH IMM\`
```

Por tanto el nombre correcto sería:

```
\`MIR-Wire TCP emulator\`
```

hasta que exista backend RDMA real.

Para GPUDirect/RDMA real hay además registro/pinning de memoria, sincronización y recursos RDMA específicos; NVIDIA documenta esos requisitos.

# 29. \[C\] `recv(header\\\_size)` no garantiza obtener todo el header TCP

Esto:

```
\`raw\\\_header = conn.recv(header\\\_size)\`
```

no significa:

```
\`“dame exactamente header\\\_size bytes”.\`
```

TCP es stream.

Puede recibir:

```
\`7 bytes\`
```

cuando pediste 16.

### Solución

```
\`def recv\\\_exact(sock, n):\`  
  
\`    buf = bytearray(n)\`  
  
\`    view = memoryview(buf)\`  
  
  
\`    off = 0\`  
  
\`    while off \\\< n:\`  
  
\`        got = sock.recv\\\_into(view\\\[off:\\\], n - off)\`  
  
\`        if got == 0:\`  
  
\`            raise ConnectionError("EOF before frame completion")\`  
  
\`        off += got\`  
  
  
\`    return bytes(buf)\`
```

Y aplicar lo mismo a payload.

# 30. \[C\] MIR-Wire tiene memoria de recepción ilimitada

```
\`self.received\\\_tensors.append((imm\\\_data, tensor))\`
```

No se elimina nada.

Entonces:

M(t)∝NreceivedM(t)\\propto N\_\{\\rm received\}

y finalmente:

```
\`OOM\`
```

### Solución

Pool/ring acotado:

```
\`FREE -\\\> RECEIVING -\\\> READY -\\\> CONSUMED -\\\> FREE\`
```

exactamente como en PMTP.

# 31. \[C\] Un solo error mata el worker de MIR-Wire

```
\`except Exception:\`  
  
\`    break\`
```

Una excepción de un cliente:

```
\`cliente malo\`  
  
\`   ↓\`  
  
\`Exception\`  
  
\`   ↓\`  
  
\`break\`  
  
\`   ↓\`  
  
\`receiver muerto\`
```

Eso es una vulnerabilidad de disponibilidad.

### Solución

```
\`except ConnectionError:\`  
  
\`    continue\`  
  
\`except ProtocolError:\`  
  
\`    continue\`  
  
\`except Exception as exc:\`  
  
\`    log\\\_internal\\\_error(exc)\`  
  
\`    continue\`
```

Y parar solo con una señal explícita de shutdown.

# 32. \[C\] Triton no implementa la reducción compensada que promete la teoría

El kernel hace:

```
\`yu = tl.sum(yi \\\* ui, axis=0)\`
```

y después:

```
\`torch.sum(partial\\\_yu)\`
```

Eso no es Neumaier.

Triton documenta las reducciones bajo las propiedades algebraicas de la operación; no hay aquí una implementación de suma compensada reproducible.

### Consecuencia

No puedes afirmar:

```
\`C++ = Neumaier\`  
  
\`GPU = Neumaier\`
```

Son dos matemáticas numéricas distintas.

# 33. \[C\] Triton no verifica que la salida siga en la esfera

El kernel calcula:

```
\`y\\\_out = yi + alpha \\\* ui + beta \\\* vi\`
```

y devuelve.

No hay:

```
\`||y\\\_out||-1\`
```

No hay gate postcondición.

Por tanto una de las principales garantías geométricas del C++ **no existe en el backend GPU**.

# 34. \[C\] El argumento `stream` de Triton está muerto

Firma:

```
\`stream: torch.cuda.Stream = None\`
```

pero no controla el lanzamiento.

Eso significa que el contrato dice:

```
\`el caller te da un stream\`
```

mientras la ejecución no respeta ese stream.

### Solución

Todo el pipeline:

```
\`allocation\`  
  
\`pass1\`  
  
\`reduction\`  
  
\`pass2\`  
  
\`validation\`
```

debe operar en el stream explícito.

# 35. \[C\] Triton hace sincronización host innecesaria

Esto:

```
\`torch.sum(partial\\\_yu).item()\`
```

fuerza la obtención del resultado en CPU.

Y se hace varias veces.

Eso significa que una medición de:

```
\`kernel latency\`
```

puede estar midiendo:

```
\`kernel + device reduction + sync host\`
```

# 36. \[D\] El Tangent Adapter sigue sin ser “biyectivo” sobre todo RDR^D

Esto continúa:

```
\`if norm\\\_h \\\< self.eps:\`  
  
\`    u\\\[0\\\] = 1.0\`  
  
\`    r = -100.0\`
```

Entonces:

```
\`h1 = 0\`  
  
\`h2 = 1e-20 \\\* e1\`  
  
\`h3 = 1e-100 \\\* e2\`
```

pueden colapsar al mismo representante.

Eso es una violación directa de:

h1≠h2  ⇏  f(h1)≠f(h2).h\_1\\ne h\_2 \\;\\not\\Rightarrow\\; f(h\_1)\\ne f(h\_2).

### Solución

O declarar:

RD∖\{0\}R^D\\setminus\\\{0\\\}

como dominio,

o introducir:

```
\`ZERO\`  
  
\`NONZERO(u,r)\`
```

como suma disjunta.

# 37. \[C\] El Tangent Adapter falla para magnitudes finitas enormes

Con:

```
\`h = \\\[1e300, 0, 0\\\]\`
```

`np.linalg.norm` puede overflowear.

Entonces aparecen:

```
\`norm = inf\`  
  
\`u    = nan\`  
  
\`r    = inf\`
```

aunque el input siga siendo finito.

### Solución

Norma estilo `xLASSQ`:

```
\`def stable\\\_norm(x):\`  
  
\`    scale = 0.0\`  
  
\`    ssq = 1.0\`  
  
  
\`    for value in x:\`  
  
\`        a = abs(float(value))\`  
  
\`        if a == 0.0:\`  
  
\`            continue\`  
  
\`        if scale \\\< a:\`  
  
\`            ssq = 1.0 + ssq \\\* (scale / a) \\\*\\\* 2\`  
  
\`            scale = a\`  
  
\`        else:\`  
  
\`            ssq += (a / scale) \\\*\\\* 2\`  
  
  
\`    return 0.0 if scale == 0.0 else scale \\\* math.sqrt(ssq)\`
```

Para 10710^7 dimensiones obviamente hay que vectorizar/bloquear, pero la matemática es esta.

# 38. \[C\] `project\\\_to\\\_tangent()` presupone que u está normalizado sin comprobarlo

La fórmula:

v⊤=v−⟨v,u⟩uv\_\\top=v-\\langle v,u\\rangle u

solo satisface:

⟨u,v⊤⟩=0\\langle u,v\_\\top\\rangle=0

si:

∥u∥=1.\\|u\\|=1.

Para uu no unitario:

⟨u,v⊤⟩=⟨u,v⟩(1−∥u∥2).\\langle u,v\_\\top\\rangle = \\langle u,v\\rangle(1-\\|u\\|^2).

### Solución

No permitir:

```
\`project\\\_to\\\_tangent(untrusted\\\_u, v)\`
```

sin validar:

```
\`abs(np.dot(u,u)-1) \\\<= tol\`
```

o usar una representación `SpherePoint` que solo pueda construirse mediante constructor validado.

# 39. \[C\] `parallel\\\_transport()` miente sobre su algoritmo

El docstring dice:

```
\`Schild's Ladder / Geodesic Parallel Transport\`
```

pero lo que hace es una fórmula cerrada de transporte sobre la esfera.

No es una implementación de Schild's Ladder.

Eso debería corregirse porque en investigación matemática el nombre del algoritmo forma parte del resultado reproducible.

# 40. \[C\] Transporte paralelo cerca del antipodal tiene una rama artificial

```
\`if norm\\\_w \\\< self.eps:\`  
  
\`    return v\\\_tan1.copy()\`
```

Cuando:

u2≈−u1u\_2\\approx-u\_1

esto significa:

```
\`“no existe dirección de gran círculo bien determinada”\`
```

y el código responde:

```
\`“devuelvo el vector original”.\`
```

Eso generalmente **no deja al vector en Tu2SD−1T\_\{u\_2\}S^\{D-1\}**.

### Solución

Devolver:

```
\`ERR\\\_ANTIPODAL\\\_AMBIGUITY\`
```

o exigir una dirección de referencia que seleccione la geodésica.

# 41. \[D\] Quantum: el nombre “Clifford+T exact synthesis” no corresponde al código

El código hace:

```
\`k = round(theta / (pi/4))\`
```

y mete:

```
\`t q\\\[i\\\];\`
```

repetidamente.

Eso no es una síntesis general Ross–Selinger.

Además el resto:

```
\`h\`  
  
\`t\`  
  
\`h\`  
  
\`s\`
```

no está acompañado de una demostración de:

∥U−Uapprox∥≤ϵtarget.\\|U-U\_\{\\rm approx\}\\|\\le\\epsilon\_\{\\rm target\}.

### Solución

Cada síntesis debe devolver:

```
\`U\\\_approx\`  
  
\`gate\\\_count\`  
  
\`T\\\_count\`  
  
\`error\\\_bound\`
```

y la API debe rechazar si:

error\>ϵtarget.\\text\{error\}\>\\epsilon\_\{\\rm target\}.

# 42. \[C\] El `eps\\\_target` actualmente no certifica nada

Esto es todavía más importante que el algoritmo elegido.

Puedes instanciar:

```
\`CliffordTSynthesizer(eps\\\_target=1e-12)\`
```

y la rutina no tiene una prueba:

```
\`actual\\\_error \\\<= 1e-12\`
```

Por tanto `eps\\\_target` es básicamente un parámetro decorativo.

# 43. \[C\] `synthesize\\\_givens\\\_rotation()` mezcla dos operaciones distintas

Genera:

```
\`CX\`  
  
\`RY(theta)\`  
  
\`...\`  
  
\`RZ(theta) approximation\`  
  
\`...\`  
  
\`CX\`
```

Es decir, no está simplemente reemplazando `Ry(theta)` por una aproximación.

Está haciendo:

CX⋅Ry(θ)⋅Rzapprox(θ)⋅CX.CX \\cdot Ry(\\theta)\\cdot Rz\_\{\\rm approx\}(\\theta)\\cdot CX.

Eso es otra operación.

### Corrección

Si quieres descomponer:

Ry(θ)R\_y(\\theta)

debes sustituir:

Ry(θ)→HRz(θ)HR\_y(\\theta)\\to H R\_z(\\theta)H

y **solo entonces** sintetizar el RzR\_z.

No añadir ambos.

# 44. \[C\] El mapping `p % num\\\_qubits` no representa coordenadas de RDR^D

Esto:

```
\`q1 = p1 % num\\\_qubits\`  
  
\`q2 = p2 % num\\\_qubits\`
```

no representa:

p1,p2∈\{0,…,D−1\}p\_1,p\_2\\in\\\{0,\\ldots,D-1\\\}

en el espacio de Hilbert.

Con:

D=107D=10^7

y:

n=24n=24

hay:

224=16 777 2162^\{24\}=16\\,777\\,216

estados.

Pero el código simplemente hace:

```
\`coordenada 1000000\`  
  
\`→ qubit 16\`
```

y cientos de coordenadas distintas pueden colisionar en el mismo qubit.

Eso no es una codificación reversible de las coordenadas.

# 45. \[C\] El QASM contiene medición, por tanto ya no es solo una representación del operador unitario

OpenQASM define `measure` como una medición del registro cuántico, no como parte de la evolución unitaria.

Por tanto hay que separar:

```
\`POLYDIM\\\_OPERATOR.qasm\`
```

de:

```
\`POLYDIM\\\_BENCHMARK\\\_WITH\\\_MEASUREMENT.qasm\`
```

# 46. \[C\] LSM sigue siendo O(D²), no O(1)

Ya sabemos que:

```
\`nnz = int(dim \\\* sparsity)\`
```

y:

```
\`self.sparse\\\_indices =\`  
  
\`    \\\[np.random.choice(dim, nnz, replace=False)\`  
  
\`     for \\\_ in range(dim)\\\]\`
```

da:

O(D2)O(D^2)

almacenamiento.

Pero esta ronda añade algo importante:

### El coste real de construcción

Cada fila llama a:

```
\`np.random.choice(dim, nnz, replace=False)\`
```

Así que no solo tienes:

O(D2)O(D^2)

de almacenamiento.

También tienes un proceso de construcción gigantesco.

Para:

D=107,sparsity=0.05D=10^7,\\quad sparsity=0.05

son:

5×10125\\times10^\{12\}

entradas.

No existe una arquitectura Python realista basada en ese objeto para ese D.

# 47. \[S\] Reservoir SOTA: operador estructurado, no matriz dispersa explícita

Yo cambiaría el concepto:

```
\`W\\\_res = sparse matrix\`
```

por:

```
\`W\\\_res =\`  
  
\`  H D1 H D2 H D3 ...\`
```

o:

```
\`W\\\_res = product of Householder/Givens/butterfly transforms\`
```

de modo que:

memory⁡(W)=O(D)\\operatorname\{memory\}(W)=O(D)

y la aplicación pueda bajar a:

O(Dlog⁡D)O(D\\log D)

en una estructura adecuada.

Para matrices tall-skinny también existen técnicas de QR recursivas/cache-oblivious y communication-avoiding, como `xGEQRT3` y `xTPQRT`, que son precisamente el tipo de familia algorítmica que conviene considerar cuando D crece de verdad.

# 48. \[D\] El dossier llama “Higham bound” a una tolerancia ad hoc

Aparece algo equivalente a:

```
\`higham\\\_tol = 50\\\*sqrt(d)\\\*eps + 1e-14\`
```

Eso no es una derivación formal de una cota de Higham.

Es una tolerancia diseñada por el autor.

No es necesariamente mala como test empírico, pero hay que llamarla por su nombre.

### Correcto

```
\`empirical\\\_acceptance\\\_threshold\`
```

o derivar una bound formal con las operaciones realmente ejecutadas.

# 49. \[C\] La afirmación “error O(eps) independiente de D” está sobregeneralizada

El comentario del código dice:

> “con sumación compensada la deriva medida es O(eps) e INDEPENDIENTE de D”.

Eso puede describir **una observación de determinados experimentos**, pero no se convierte automáticamente en una cota universal del algoritmo completo.

Especialmente cuando entran:

```
\`producto x\\\*y\`  
  
\`reducciones paralelas\`  
  
\`merge de acumuladores\`  
  
\`sqrt\`  
  
\`sin\`  
  
\`FMA\`  
  
\`BLAS\`  
  
\`GPU reductions\`
```

El `Neumaier` protege una clase concreta de suma; no demuestra una cota global para todo el pipeline.

La documentación de la propia auditoría debería abandonar afirmaciones absolutas y expresar la cota para la operación concreta.

# 50. \[D\] OpenMP “reproducible” no significa “mismo resultado en cualquier número de hilos”

El código usa:

```
\`schedule(static)\`
```

Eso ayuda a la reproducibilidad del reparto, pero no implica que:

```
\`1 hilo\`  
  
\`2 hilos\`  
  
\`4 hilos\`  
  
\`8 hilos\`
```

den exactamente el mismo resultado binario.

El orden de las sumas cambia.

Esto importa muchísimo si el dossier habla de:

```
\`bitwise deterministic\`
```

OpenMP documenta propiedades específicas de reproducibilidad para `static`, no una garantía universal de identidad entre configuraciones distintas.

### Solución

Separar:

```
\`deterministic\\\_given\\\_thread\\\_count\`
```

de:

```
\`bitwise\\\_identical\\\_across\\\_thread\\\_counts\`
```

Si quieres lo segundo:

```
\`fixed partition\`  
  
\`reproducible reduction tree\`  
  
\`binned/reproducible accumulator\`
```

# 51. \[C\] ARM y x86 no tienen ahora la misma política explícita de subnormales

El código toca:

```
\`\\\_MM\\\_SET\\\_FLUSH\\\_ZERO\\\_MODE(...)\`  
  
\`\\\_MM\\\_SET\\\_DENORMALS\\\_ZERO\\\_MODE(...)\`
```

solo para x86.

En ARM64 se debe tratar la configuración equivalente del FPCR. ARM documenta el control de flushing y tratamiento de FP mediante FPCR.

Por tanto hoy no existe un contrato:

```
\`“subnormal semantics identical on x86 and ARM”\`
```

# 52. \[C\] El build del paquete no es reproducible

No encontré en el paquete:

```
\`Cargo.toml\`  
  
\`CMakeLists.txt\`  
  
\`pyproject.toml\`  
  
\`CI\`  
  
\`toolchain lock\`  
  
\`compiler flags manifest\`
```

Además:

```
\`C++ = V764\`  
  
\`Rust = V762\`  
  
\`Triton = V762\`  
  
\`Dart = V762\`  
  
\`Monolith = V766/V764\`  
  
\`README = V767\`
```

No es un release unitario.

La auditoría documental tampoco puede confiar en la cadena:

```
\`fuente\`  
  
\`→ compilador\`  
  
\`→ binario\`  
  
\`→ benchmark\`
```

porque no hay una identificación criptográfica de esa cadena.

# 53. Esto explica por qué las auditorías anteriores pudieron dejar cosas atrás

Aquí está la respuesta a tu pregunta original.

No porque el código sea “demasiado grande”.

Sino porque se estaba haciendo:

```
\`Ronda 1\`  
  
\`  ↓\`  
  
\`encuentro bug A\`  
  
\`  ↓\`  
  
\`lo arreglas\`  
  
\`  ↓\`  
  
\`Ronda 2\`  
  
\`  ↓\`  
  
\`encuentro bug B\`  
  
\`  ↓\`  
  
\`lo arreglas\`
```

Eso es insuficiente para un sistema así.

La auditoría correcta es:

```
\`                    ┌─────────────┐\`  
  
\`                    │ ESPECIFIC.  │\`  
  
\`                    └──────┬──────┘\`  
  
\`                           │\`  
  
\`                   invariantes formales\`  
  
\`                           │\`  
  
\`             ┌─────────────┼─────────────┐\`  
  
\`             │             │             │\`  
  
\`         implementación  ABI/FFI      memoria\`  
  
\`             │             │             │\`  
  
\`             └─────────────┼─────────────┘\`  
  
\`                           │\`  
  
\`                    adversarial tests\`  
  
\`                           │\`  
  
\`             ┌─────────────┼──────────────┐\`  
  
\`             │             │              │\`  
  
\`            ASan          UBSan          TSAN\`  
  
\`             │             │              │\`  
  
\`             └─────────────┼──────────────┘\`  
  
\`                           │\`  
  
\`               x86 / ARM / GPU / RDMA\`  
  
\`                           │\`  
  
\`                     release gate\`
```

Esto es lo que voy a seguir aplicando.

# 54. Cómo llevaría POLYDIM a un nivel realmente industrial

## Capa A — ABI única

Un único:

```
\`polydim.h\`
```

generado/verificado.

Debe definir:

```
\`types\`  
  
\`sizes\`  
  
\`alignment\`  
  
\`status values\`  
  
\`ABI version\`  
  
\`feature bits\`  
  
\`ownership\`  
  
\`thread-safety\`  
  
\`alias rules\`  
  
\`error semantics\`
```

## Capa B — handles opacos

No:

```
\`Struct PMTPControl\`
```

No exponer estructuras C++ internas.

Sí:

```
\`typedef struct PolydimContext PolydimContext;\`  
  
\`typedef struct PolydimBuffer  PolydimBuffer;\`
```

y:

```
\`PolydimContext\\\* polydim\\\_create(...);\`  
  
\`void polydim\\\_destroy(PolydimContext\\\*);\`
```

Dart/Rust/Python solo ve:

```
\`opaque pointer\`
```

# 55. Capa C — memoria comprobada

Una función central:

```
\`struct ByteCount \\\{\`  
  
\`    size\\\_t bytes;\`  
  
\`\\\};\`  
  
  
\`bool checked\\\_mul\\\_size(\`  
  
\`    uint64\\\_t a,\`  
  
\`    uint64\\\_t b,\`  
  
\`    uint64\\\_t& out) noexcept\`  
  
\`\\\{\`  
  
\`    if (a != 0 && b \\\> UINT64\\\_MAX / a)\`  
  
\`        return false;\`  
  
  
\`    out = a \\\* b;\`  
  
\`    return true;\`  
  
\`\\\}\`  
  
  
\`bool checked\\\_bytes(\`  
  
\`    uint64\\\_t elements,\`  
  
\`    uint64\\\_t elem\\\_size,\`  
  
\`    size\\\_t& bytes) noexcept\`  
  
\`\\\{\`  
  
\`    uint64\\\_t tmp;\`  
  
  
\`    if (!checked\\\_mul\\\_size(elements, elem\\\_size, tmp))\`  
  
\`        return false;\`  
  
  
\`    if (tmp \\\> SIZE\\\_MAX)\`  
  
\`        return false;\`  
  
  
\`    bytes = static\\\_cast\\\<size\\\_t\\\>(tmp);\`  
  
\`    return true;\`  
  
\`\\\}\`
```

**Ninguna** función exportada debería hacer:

```
\`D \\\* K \\\* sizeof(double)\`
```

directamente.

# 56. Capa D — norma numéricamente estable

En lugar de:

```
\`sum += x\\\*x;\`
```

usar acumulación escalada:

```
\`struct Lassq \\\{\`  
  
\`    double scale = 0.0;\`  
  
\`    double ssq   = 1.0;\`  
  
  
\`    void add(double x) noexcept \\\{\`  
  
\`        const double a = std::abs(x);\`  
  
  
\`        if (a == 0.0)\`  
  
\`            return;\`  
  
  
\`        if (scale \\\< a) \\\{\`  
  
\`            const double r = scale / a;\`  
  
\`            ssq = 1.0 + ssq \\\* r \\\* r;\`  
  
\`            scale = a;\`  
  
\`        \\\} else \\\{\`  
  
\`            const double r = a / scale;\`  
  
\`            ssq += r \\\* r;\`  
  
\`        \\\}\`  
  
\`    \\\}\`  
  
  
\`    double norm() const noexcept \\\{\`  
  
\`        return scale == 0.0\`  
  
\`             ? 0.0\`  
  
\`             : scale \\\* std::sqrt(ssq);\`  
  
\`    \\\}\`  
  
\`\\\};\`
```

Esto elimina una clase completa de:

```
\`finite input\`  
  
\`→ intermediate overflow\`
```

# 57. Capa E — postcondiciones formales

Cada kernel importante debe tener:

### Preconditions

```
\`pointer valid\`  
  
\`dimensions valid\`  
  
\`finite inputs\`  
  
\`alignment valid\`  
  
\`alias rules valid\`  
  
\`tolerance valid\`
```

### Computation

```
\`kernel\`
```

### Postconditions

```
\`finite output\`  
  
\`norm residual\`  
  
\`Gram residual\`  
  
\`topological residual\`
```

### Publish

Solo al final.

# 58. El verdadero “selftest\_all”

Yo lo llevaría a esto:

```
\`int32\\\_t polydim\\\_selftest\\\_all()\`  
  
\`\\\{\`  
  
\`    const int32\\\_t tests\\\[\\\] = \\\{\`  
  
\`        selftest\\\_abi(),\`  
  
\`        selftest\\\_fp\\\_contract(),\`  
  
\`        selftest\\\_rodrigues(),\`  
  
\`        selftest\\\_sphere(),\`  
  
\`        selftest\\\_orthonormalize(),\`  
  
\`        selftest\\\_stiefel(),\`  
  
\`        selftest\\\_cholqr2(),\`  
  
\`        selftest\\\_pmtp(),\`  
  
\`        selftest\\\_aliasing(),\`  
  
\`        selftest\\\_overflow\\\_guards(),\`  
  
\`        selftest\\\_nan\\\_inf(),\`  
  
\`        selftest\\\_subnormals()\`  
  
\`    \\\};\`  
  
  
\`    for (int32\\\_t rc : tests) \\\{\`  
  
\`        if (rc != POLYDIM\\\_SUCCESS)\`  
  
\`            return rc;\`  
  
\`    \\\}\`  
  
  
\`    return POLYDIM\\\_SUCCESS;\`  
  
\`\\\}\`
```

No volvería a aceptar una función llamada “all” que no pruebe all.

# 59. Test adversarial que debe existir antes de volver a llamarlo “industrial”

Esta es la matriz que cerraría las clases de errores:

```
\`INPUT DOMAIN\`  
  
\`────────────\`  
  
\`D = 1\`  
  
\`D = 2\`  
  
\`D = K\`  
  
\`D = K+1\`  
  
\`D = INT64\\\_MAX\`  
  
\`D overflow\`  
  
\`K = 0\`  
  
\`K = 1\`  
  
\`K = max\`  
  
\`K \\\> max\`  
  
  
\`VALUES\`  
  
\`──────\`  
  
\`0\`  
  
\`-0\`  
  
\`DBL\\\_TRUE\\\_MIN\`  
  
\`subnormal\`  
  
\`DBL\\\_MIN\`  
  
\`1\`  
  
\`1e-8\`  
  
\`1e150\`  
  
\`1e154\`  
  
\`DBL\\\_MAX\`  
  
\`NaN\`  
  
\`+Inf\`  
  
\`-Inf\`  
  
  
\`ALIASING\`  
  
\`────────\`  
  
\`y\\\_out == y\`  
  
\`y\\\_out == u\`  
  
\`y\\\_out == v\`  
  
\`partial overlap\`  
  
\`report overlap\`  
  
  
\`CONCURRENCY\`  
  
\`───────────\`  
  
\`1 writer / 1 reader\`  
  
\`2 writers\`  
  
\`N writers / N readers\`  
  
\`slot exhaustion\`  
  
\`reader stall\`  
  
\`writer stall\`  
  
\`ABA stress\`  
  
\`generation wrap test\`  
  
  
\`NUMERICS\`  
  
\`────────\`  
  
\`1 thread\`  
  
\`2\`  
  
\`3\`  
  
\`4\`  
  
\`8\`  
  
\`16\`  
  
\`...\`  
  
\`different schedules\`  
  
  
\`FFI\`  
  
\`───\`  
  
\`null\`  
  
\`wrong length\`  
  
\`wrong alignment\`  
  
\`wrong ABI version\`  
  
\`wrong status\`  
  
\`exception\`  
  
\`allocation failure\`  
  
  
\`TRANSPORT\`  
  
\`─────────\`  
  
\`partial header\`  
  
\`partial payload\`  
  
\`zero payload\`  
  
\`oversized payload\`  
  
\`bad magic\`  
  
\`bad dtype\`  
  
\`bad byte count\`  
  
\`disconnect mid-frame\`  
  
\`many clients\`  
  
  
\`GPU\`  
  
\`───\`  
  
\`different streams\`  
  
\`different devices\`  
  
\`NaN\`  
  
\`Inf\`  
  
\`subnormal\`  
  
\`odd D\`  
  
\`D % BLOCK != 0\`  
  
  
\`QUANTUM\`  
  
\`────────\`  
  
\`theta=0\`  
  
\`pi/8\`  
  
\`pi/4\`  
  
\`pi/2\`  
  
\`pi\`  
  
\`2pi\`  
  
\`random\`  
  
\`target eps sweep\`  
  
\`unitary matrix comparison\`
```

# 60. Sanitizers: aquí está la parte que faltaba

Para que yo considere cerrada la capa C++:

```
\`-fsanitize=address,undefined\`
```

y otra campaña:

```
\`-fsanitize=thread\`
```

más:

```
\`-Wall\`  
  
\`-Wextra\`  
  
\`-Wpedantic\`  
  
\`-Wconversion\`  
  
\`-Wshadow\`  
  
\`-Werror\`
```

El TSAN es especialmente importante para PMTP porque el problema central es precisamente acceso concurrente a estado compartido.

# 61. SOTA para Stiefel

No me quedaría solamente con:

```
\`CholeskyQR2\`  
  
\`Cayley-SMW\`
```

La familia a considerar para matrices tall-skinny incluye:

```
\`TSQR\`  
  
\`communication-avoiding QR\`  
  
\`recursive/cache-oblivious QR\`  
  
\`polar retraction\`  
  
\`Householder block reflectors\`
```

LAPACK ya incluye `xGEQRT3` precisamente como QR recursivo/cache-oblivious para matrices tall-and-skinny, y `xTPQRT` para variantes communication-avoiding.

Para POLYDIM eso es mucho más coherente con:

D=107,K≪DD=10^7,\\quad K\\ll D

que materializar indiscriminadamente intermediarios gigantes.

# 62. La regla nueva para todos los benchmarks

No aceptaré más:

```
\`“measured 4.538 ms”\`
```

como evidencia suficiente.

Debe existir:

```
\`source SHA\`  
  
\`compiler\`  
  
\`flags\`  
  
\`stdlib\`  
  
\`OpenMP runtime\`  
  
\`BLAS\`  
  
\`CPU model\`  
  
\`GPU model\`  
  
\`driver\`  
  
\`runtime\`  
  
\`D\`  
  
\`K\`  
  
\`threads\`  
  
\`warmups\`  
  
\`iterations\`  
  
\`median\`  
  
\`p95\`  
  
\`p99\`  
  
\`max\`  
  
\`min\`  
  
\`error metric\`
```

Y:

```
\`binary SHA256\`
```

# 63. Y una corrección conceptual aún mayor: “zero-copy” está sobreutilizado

Ahora mismo aparecen conceptos distintos bajo la misma etiqueta:

```
\`mmap\`  
  
\`shared memory\`  
  
\`memoryview\`  
  
\`recv\\\_into\`  
  
\`Torch tensor\`  
  
\`RDMA\`  
  
\`GPUDirect\`  
  
\`FFI pointer\`
```

No significan lo mismo.

La taxonomía industrial debe ser:

```
\`ZERO COPY WITHIN PROCESS\`  
  
\`ZERO COPY BETWEEN PROCESSES\`  
  
\`ZERO COPY KERNEL↔CPU\`  
  
\`ZERO COPY NIC↔GPU\`  
  
\`RDMA WRITE\`  
  
\`GPUDirect RDMA\`
```

Cada uno necesita su propio contrato.

# 64. Qué NO considero demostrado todavía

Y esto también es importante para “no alucinar”.

### \[U\] Rust no lo pude compilar aquí

No hay:

```
\`rustc\`  
  
\`cargo\`
```

instalados.

Por tanto:

```
\`Rust memory behavior\`  
  
\`Rust ABI layout\`  
  
\`panic/unwind runtime\`
```

deben volver a validarse en un entorno con toolchain real.

### \[U\] Dart tampoco lo pude compilar

No hay:

```
\`dart\`
```

Así que no voy a inventar resultados de Dart.

### \[U\] GPU físico

No voy a repetir:

```
\`4.538 ms\`  
  
\`70.51 GB/s\`
```

como si los hubiese verificado yo.

Los documentos lo afirman; no pude reproducir los logs de esa ejecución desde el ZIP.

# 65. Qué sí considero confirmado

La lista nueva de esta ronda que considero **real**, no especulativa:

```
\`\\\[C\\\] report.out\\\_norm\\\_err no se rellena en sphere\`  
  
\`\\\[C\\\] tolerancias NaN pueden desactivar las gates\`  
  
\`\\\[C\\\] reject\\\_subnormal es código muerto\`  
  
\`\\\[C\\\] status -4 tiene significados distintos entre Rust/C++\`  
  
\`\\\[C\\\] CholQR2 tiene umbral absoluto 1e-14\`  
  
\`\\\[C\\\] CholQR2 modifica X antes de saber que va a completar\`  
  
\`\\\[C\\\] CholQR2 no comparte el mismo límite K\`  
  
\`\\\[C\\\] CholQR2 no tiene presupuesto de memoria por hilo\`  
  
\`\\\[C\\\] uint64 D se reduce a int64 en loops\`  
  
\`\\\[C\\\] D se reduce a int en BLAS\`  
  
\`\\\[C\\\] selftest\\\_all no prueba all\`  
  
\`\\\[C\\\] PMTP begin\\\_write no reserva\`  
  
\`\\\[C\\\] PMTP validate\\\_read no valida\`  
  
\`\\\[C\\\] observed\\\_seq/ticket no son secuencias reales\`  
  
\`\\\[C\\\] C ABI deja excepciones posibles sin convertir\`  
  
\`\\\[C\\\] PMTP no tiene ownership/pinning\`  
  
\`\\\[C\\\] project\\\_tangent\\\_stiefel acepta NaN y devuelve success\`  
  
\`\\\[C\\\] MIR acepta payload truncado como tensor\`  
  
\`\\\[C\\\] MIR recv() puede devolver header parcial\`  
  
\`\\\[C\\\] MIR receiver muere ante Exception\`  
  
\`\\\[C\\\] MIR cola memoria sin límite\`  
  
\`\\\[C\\\] Triton no hace Neumaier\`  
  
\`\\\[C\\\] Triton no verifica norma de salida\`  
  
\`\\\[C\\\] stream Triton no controla el lanzamiento\`  
  
\`\\\[C\\\] tangent adapter colapsa el entorno de cero\`  
  
\`\\\[C\\\] tangent adapter puede overflowear norm()\`  
  
\`\\\[C\\\] tangent projection presupone u unitario\`  
  
\`\\\[C\\\] parallel\\\_transport ≠ Schild's Ladder\`  
  
\`\\\[C\\\] antipodal devuelve vector no transportado\`  
  
\`\\\[C\\\] quantum eps\\\_target no certifica error\`  
  
\`\\\[C\\\] quantum mapping p % num\\\_qubits colisiona\`  
  
\`\\\[C\\\] quantum mezcla Ry con Rz adicional\`  
  
\`\\\[C\\\] LSM es O(D²)\`  
  
\`\\\[C\\\] benchmark artifacts no están en el paquete\`  
  
\`\\\[C\\\] versiones V762/V764/V766/V767 están mezcladas\`
```

Eso ya no son “10 cosas”.

Es una **familia completa de contratos rotos**.

# 66. La reparación SOTA no es parchear 30 líneas

El camino correcto es hacer cinco reemplazos conceptuales:

```
\`1. ABI único y opaco\`  
  
\`2. PMTP con ownership + generation\`  
  
\`3. kernels transaccionales con postcondición\`  
  
\`4. aritmética escalada/reproducible\`  
  
\`5. transportes reales separados de emuladores\`
```

Después encima:

```
\`Stiefel / QR\`  
  
\`Tangent adapter\`  
  
\`Reservoir\`  
  
\`GPU\`  
  
\`Quantum\`
```

Eso evita que dentro de tres rondas estemos otra vez arreglando el mismo problema desde otro lenguaje.

# 67. El punto más importante sobre tu “quiero menos de 2000 líneas perfectas”

Eso **sí es alcanzable conceptualmente**, pero la condición es que no intentemos meter diez arquitecturas diferentes dentro de las mismas 2000 líneas.

POLYDIM hoy mezcla:

```
\`geometría\`  
  
\`ML latent adapter\`  
  
\`reservoir computing\`  
  
\`Rust topology\`  
  
\`quantum compiler\`  
  
\`RDMA\`  
  
\`Dart omnichannel\`  
  
\`GPU\`  
  
\`PMTP\`
```

Cada capa multiplica el espacio de estados.

La forma de llegar a algo realmente duro no es seguir agregando mecanismos.

Es **reducir mecanismos y endurecer contratos**.

## Mi criterio de cierre a partir de ahora

No voy a considerar una clase solucionada porque:

```
\`“lo probamos una vez y dio Exit Code 0”\`
```

La consideraré cerrada solo cuando exista:

especificacioˊn+implementacioˊn+prueba adversarial+postcondicioˊn+ABI coherente\\boxed\{ \\text\{especificación\} + \\text\{implementación\} + \\text\{prueba adversarial\} + \\text\{postcondición\} + \\text\{ABI coherente\} \}

Y para PMTP, por ejemplo, eso significa que antes de continuar con otra capa quiero poder afirmar algo mucho más fuerte:

∀  interleavings vaˊlidos,writer↛slot  ∣  reader  holds\\forall\\;\\text\{interleavings válidos\}, \\quad writer \\not\\to slot\\;|\\;reader\\;holds

y:

generationafter\>generationbefore\\text\{generation\}\_\{after\}\> \\text\{generation\}\_\{before\}

sin ABA.

Ese es el nivel de “bulldog” que estás pidiendo: **no parar porque el test verde, sino parar cuando la propiedad que el test pretende proteger ya no tiene una vía conocida de violación**.

Esta ronda, por tanto, **sí descubre más de lo que había quedado pendiente**, y varios de estos hallazgos ya están reproducidos localmente.

te interesaria ver el trabajo de devolucion de otras ias?

Sí. Muchísimo.

De hecho, para esta auditoría sería **muy útil ver las devoluciones completas de las otras IAs**, no solo el “veredicto” resumido. Pueden descubrir ángulos que yo haya pasado por alto, y yo puedo someter también sus conclusiones a Red Team: separaré **hallazgo correcto, falso positivo, duplicado, interpretación discutible y problema nuevo**.

Pásamelas juntas, aunque sean largas. Las cruzaré contra el código actual y prepararé una matriz única para evitar volver a recorrer los mismos errores.

respuestas.zip

Archivo Zip

Sí. Y después de leerlas, la respuesta es clara: **valió mucho la pena traerlas**. Pero hay algo todavía más importante: las otras IAs no solo encontraron errores nuevos; también me permitieron detectar **errores en sus propias soluciones** y comparar tres auditorías independientes contra el código actual.

Eso mejora mucho el Red Team porque ahora podemos hacer una operación que faltaba:

coˊdigo actual  ↔  Claude  ↔  DeepSeek  ↔  Gemini  ↔  Kimi\\boxed\{\\text\{código actual\} \\;\\leftrightarrow\\; \\text\{Claude\} \\;\\leftrightarrow\\; \\text\{DeepSeek\} \\;\\leftrightarrow\\; \\text\{Gemini\} \\;\\leftrightarrow\\; \\text\{Kimi\}\}

y quedarnos solamente con lo que sobrevive al cruce.

Mi conclusión: **no hay que aplicar ciegamente ninguna de las soluciones que vienen en `respuestas.zip`**. Varias son buenas direcciones, pero algunas arreglan el fallo A introduciendo el fallo B.

# 1. Primero: sí, encontré una razón objetiva para no confiar en las rondas anteriores como método

Tú tenías razón en algo esencial.

El problema no era la cantidad de código.

El método anterior era demasiado parecido a:

```
\`hallazgo\`  
  
\`→ parche\`  
  
\`→ nueva entrega\`  
  
\`→ nuevo hallazgo\`  
  
\`→ nuevo parche\`
```

Eso es una mala estrategia para cerrar un sistema con:

```
\`C++\`  
  
\`Rust\`  
  
\`Python\`  
  
\`Dart\`  
  
\`GPU\`  
  
\`shared memory\`  
  
\`FFI\`  
  
\`matemática FP64\`  
  
\`concurrencia\`
```

porque cada parche cambia el espacio de estados y puede crear nuevos errores.

La auditoría correcta es:

```
\`ESPECIFICACIÓN\`  
  
\`     ↓\`  
  
\`INVARIANTES\`  
  
\`     ↓\`  
  
\`ABI\`  
  
\`     ↓\`  
  
\`IMPLEMENTACIÓN\`  
  
\`     ↓\`  
  
\`MODELO DE CONCURRENCIA\`  
  
\`     ↓\`  
  
\`MODELO NUMÉRICO\`  
  
\`     ↓\`  
  
\`TEST ADVERSARIAL\`  
  
\`     ↓\`  
  
\`SANITIZADORES\`  
  
\`     ↓\`  
  
\`HARDWARE REAL\`
```

Eso es lo que estoy aplicando ahora.

# 2. El consenso entre las IAs es sorprendentemente bueno

Los cuatro modelos que realmente escribieron un informe convergen en los mismos núcleos:

| **Área** | **Claude** | **DeepSeek** | **Gemini** | **Kimi** | **Estado** |
| :-: | :-: | :-: | :-: | :-: | :-: |
| PMTP roto | sí | sí | sí | sí | **CONFIRMADO** |
| FFI Rust 5 vs 3 args | sí | sí | sí | sí | **CONFIRMADO** |
| GprojG\_\{proj\} enorme | sí | sí | sí | sí | **CONFIRMADO** |
| LSM O(D2)O(D^2) | sí | sí | sí | sí | **CONFIRMADO** |
| Tangent no biyectivo en 0 | sí | sí | sí | sí | **CONFIRMADO** |
| “RDMA” realmente TCP | sí | sí | sí | sí | **CONFIRMADO** |
| Quantum compiler incorrecto | sí | sí | sí | sí | **CONFIRMADO** |
| TwoSum inexistente en Pass 2 | sí | sí | sí | sí | **CONFIRMADO** |
| deriva acumulativa Rodrigues | sí | parcialmente | sí | sí | **CONFIRMADO** |
| Betti-1 no calculado | sí | sí | sí | sí | **CONFIRMADO** |
| versión V762/V764/V766/V767 | sí | sí | sí | sí | **CONFIRMADO** |


Eso ya es una señal muy distinta de las rondas anteriores.

No estamos hablando de cinco modelos inventando problemas independientes.

Estamos viendo **convergencia en las mismas vulnerabilidades estructurales**.

# 3. Pero ahora viene lo interesante: las otras IAs también se equivocaron

Y esto es precisamente por lo que no conviene usarlas como “tribunal”.

## Claude P3-6: ❌ su resultado de `v=3u` NO corresponde al código actual

Claude afirma que:

> `orthonormalize\\\_pair(v=3u)` devuelve SUCCESS.

Yo recompilé **el C++ actual** y lo probé.

Resultado:

```
\`u = e0\`  
  
\`v = 3e0\`  
  
  
\`rc = POLYDIM\\\_ERR\\\_DEGENERATE\\\_NORM\`
```

Por tanto:

esa observacioˊn concreta de Claude estaˊ desactualizada\\boxed\{\\text\{esa observación concreta de Claude está desactualizada\}\}

Pero la causa que señala sigue siendo válida como riesgo futuro:

```
\`if (!(nv2 \\\> 1e-300))\`
```

es un umbral absoluto.

Es decir:

```
\`v muy pequeño pero bien condicionado\`
```

puede ser rechazado por escala.

### Veredicto

```
\`hallazgo histórico: ❌ no aplica al código actual\`  
  
\`causa estructural: ✅ sigue existiendo\`  
  
\`solución relativa: ✅ conservar\`
```

# 4. Claude “hop 574”: ❌ número concreto incorrecto para el paquete actual

Claude informa:

> falla en hop 574.

Yo ejecuté el código actual.

Con:

y=e0,u=e0,v=e1,θ=0.7y=e\_0,\\quad u=e\_0,\\quad v=e\_1,\\quad\\theta=0.7

el código actual falla en:

hop 460\\boxed\{\\text\{hop \}460\}

en mi entorno de compilación.

La métrica fue:

∣yy−1∣=1.4432899320127035×10−14|yy-1|=1.4432899320127035\\times10^\{-14\}

y la tolerancia actual:

64ϵ=1.4210854715202004×10−14.64\\epsilon = 1.4210854715202004\\times10^\{-14\}.

Por eso el siguiente paso devuelve:

```
\`POLYDIM\\\_ERR\\\_POINT\\\_OFF\\\_MANIFOLD\`
```

### Esto es importante

No significa que Claude “alucinó”.

Significa algo más útil:

> **la existencia del fenómeno es robusta; el número exacto de hop no lo es.**

Depende de:

- compilador;

- libm;

- arquitectura;

- optimización;

- orden;

- versión exacta del código.

Así que el contrato jamás debe decir:

```
\`failure\\\_at\\\_hop = 574\`
```

Debe especificar una cota.

# 5. Y encontré una solución mejor que la propuesta por Claude

Claude propone reescalar usando `yy`.

Eso mejora la situación, pero no es la variable correcta para la postcondición final.

Tenemos:

y′=y+αu+βv.y'=y+\\alpha u+\\beta v.

Ya conocemos en Pass 1:

yy,  yu,  yv,  uu,  vv,  uv.yy,\\;yu,\\;yv,\\;uu,\\;vv,\\;uv.

Podemos obtener exactamente la norma cuadrática que debe tener `y\\\_out` dentro de las mismas operaciones disponibles:

∥y′∥2=yy+2αyu+2βyv+α2uu+β2vv+2αβuv\\boxed\{ \\|y'\\|^2 = yy +2\\alpha yu +2\\beta yv +\\alpha^2 uu +\\beta^2 vv +2\\alpha\\beta uv \}

Entonces:

```
\`const double out\\\_n2 =\`  
  
\`      yy\`  
  
\`    + 2.0 \\\* alpha \\\* yu\`  
  
\`    + 2.0 \\\* beta  \\\* yv\`  
  
\`    + alpha \\\* alpha \\\* uu\`  
  
\`    + beta  \\\* beta  \\\* vv\`  
  
\`    + 2.0 \\\* alpha \\\* beta \\\* uv;\`  
  
  
\`if (!(out\\\_n2 \\\> 0.0) || !std::isfinite(out\\\_n2))\`  
  
\`    return POLYDIM\\\_ERR\\\_NUMERICAL\\\_INSTABILITY;\`  
  
  
\`const double inv\\\_out\\\_norm = 1.0 / std::sqrt(out\\\_n2);\`  
  
  
\`for (...) \\\{\`  
  
\`    y\\\_out\\\[i\\\] =\`  
  
\`        (y\\\[i\\\] + alpha\\\*u\\\[i\\\] + beta\\\*v\\\[i\\\])\`  
  
\`        \\\* inv\\\_out\\\_norm;\`  
  
\`\\\}\`
```

Eso tiene una propiedad mejor:

```
\`Pass 1: datos geométricos\`  
  
\`Pass 2: generación + normalización\`
```

y elimina la tercera lectura completa.

En una prueba pura con 20.000 aplicaciones de la rotación, esta estrategia mantiene la norma cerca del límite de redondeo.

### Esto sí es un cambio que conservaría.

# 6. ERROR NUEVO muy importante: el PMTP tampoco resuelve el problema de procesos

Esto no estaba suficientemente elevado por las IAs.

El sistema dice:

```
\`mmap\`  
  
\`/dev/shm\`  
  
\`SharedMemory\`
```

y usa:

```
\`std::atomic\\\<uint8\\\_t\\\>\`
```

como sincronización.

Aquí aparecen **dos niveles diferentes de concurrencia**:

```
\`threads\`  
  
\`processes\`
```

El modelo C++ define el memory model entre ejecuciones concurrentes dentro del programa, pero eso no te da automáticamente un protocolo IPC portable entre procesos sobre una región mmap.

Para Linux existe explícitamente el concepto de sincronización process-shared mediante futexes en memoria compartida. El kernel documenta que un futex puede residir en memoria compartida y ser usado entre procesos.

Por tanto, si POLYDIM quiere decir:

> “cross-process portable x86/ARM”

debe existir un backend explícito:

```
\`Linux:\`  
  
\`    atomics + futex/process-shared synchronization\`  
  
  
\`Windows:\`  
  
\`    named events / wait primitives / equivalent shared synchronization\`  
  
  
\`macOS:\`  
  
\`    mecanismo propio\`
```

No basta con:

```
\`std::atomic\\\<uint8\\\_t\\\>\`
```

dentro de un `mmap`.

### Nueva exigencia

Separar:

```
\`PMTP\\\_THREAD\`  
  
\`PMTP\\\_PROCESS\`
```

y dejar el soporte OS explícito.

# 7. ERROR NUEVO: `create=True` puede reinicializar un PMTP vivo

El Python actual hace:

```
\`if create:\`  
  
\`    self.lib.polydim\\\_pmtp\\\_init(self.mmap\\\_ptr)\`
```

Esto ocurre cada vez que se construye el objeto con `create=True`.

Si dos procesos abren:

```
\`polydim\\\_pmtp\\\_TAG\`
```

y ambos creen que son “creator”, el segundo puede ejecutar:

```
\`state = 0x24\`
```

mientras el primero está transmitiendo.

Eso destruye el estado del canal.

### Solución

Separar:

```
\`create()\`  
  
\`open\\\_existing()\`
```

y determinar de forma atómica quién fue realmente el creador.

Nunca:

```
\`if create:\`  
  
\`    init()\`
```

sobre un objeto IPC potencialmente existente.

# 8. Y esto vuelve todavía peor el PMTP: no basta con arreglar el seqlock

Ahora vamos a la propuesta de DeepSeek.

DeepSeek propone algo del estilo:

```
\`latest.store(slot);\`  
  
\`slot.seq.fetch\\\_add(1);\`
```

en ese orden.

Eso tiene un agujero.

Existe esta ventana:

```
\`writer:\`  
  
  
\`latest = new\\\_slot\`  
  
\`           │\`  
  
\`           │ todavía no marcó seq impar\`  
  
\`           ▼\`  
  
\`reader:\`  
  
\`    latest -\\\> new\\\_slot\`  
  
\`    seq == 0\`  
  
\`    copia datos viejos/no inicializados\`  
  
\`    seq == 0\`  
  
\`    acepta\`
```

Así que la propia solución de DeepSeek **puede publicar el slot antes de marcarlo como writing**.

Eso es un bug nuevo que apareció al auditar la solución de la otra IA.

# 9. Y hay un problema todavía más fundamental con el “seqlock puro”

DeepSeek propone:

```
\`seq0 = seq.load(acquire);\`  
  
\`memcpy(... data ...);\`  
  
\`seq1 = seq.load(acquire);\`
```

y cree que eso resuelve el problema.

No necesariamente.

Si otro hilo hace:

```
\`writer:\`  
  
\`    data\\\[i\\\] = ...\`
```

mientras el reader ejecuta:

```
\`reader:\`  
  
\`    memcpy(data)\`
```

los datos son no-atómicos.

En el modelo C++ una evaluación que escribe y otra que lee la misma memoria sin una relación `happens-before` adecuada constituyen una data race y el comportamiento es indefinido.

Los `acquire/release` del contador **no convierten mágicamente los `double` en atómicos**.

Esto es exactamente el tipo de error que quiero evitar.

# 10. Por eso retiro una sugerencia anterior mía

En la ronda anterior sugerí como posibilidad:

```
\`“seqlock + generation”\`
```

como reparación.

Después de cruzarlo con las propuestas de DeepSeek y con el modelo C++ real, lo endurezo:

No usarıˊa seqlock puro para los datos tensoriales de PMTP\\boxed\{\\text\{No usaría seqlock puro para los datos tensoriales de PMTP\}\}

Para este caso prefiero:

```
\`FREE\`  
  
\` ↓\`  
  
\`WRITING\`  
  
\` ↓\`  
  
\`READY\`  
  
\` ↓\`  
  
\`READING\`  
  
\` ↓\`  
  
\`FREE\`
```

con:

- ownership del writer;

- contador de lectores;

- generation 64-bit;

- slot immutable mientras está `READING`.

Eso sí impide físicamente:

```
\`writer -\\\> slot que reader todavía usa\`
```

y elimina la dependencia de “leer y luego descubrir que hubo una carrera”.

La documentación de sequence counters del kernel también deja una condición que las propuestas de las IAs están olvidando: los escritores deben estar serializados; un `seqcount\\\_t` por sí solo no protege múltiples writers.

# 11. PMTP actual: ahora tenemos cuatro fallos, no uno

El estado real es:

```
\`1. begin\\\_write() no reserva\`  
  
\`2. commit\\\_write() ignora slot\`  
  
\`3. validate\\\_read() no valida\`  
  
\`4. reader/writer puede coincidir sobre mismo slot\`  
  
\`5. observed\\\_seq = 1 constante\`  
  
\`6. ticket = 0 constante\`  
  
\`7. slot 3 nunca se usa\`  
  
\`8. valid bit se pierde\`  
  
\`9. dos writers pueden escribir simultáneamente\`  
  
\`10. create=True puede reinicializar el canal\`  
  
\`11. IPC process-shared no tiene contrato de sincronización portable\`
```

Las tres primeras están visibles directamente en el código actual.

Esto ya no es:

> “hay un bug en el seqlock”.

Es:

PMTP necesita redisen˜o completo\\boxed\{\\text\{PMTP necesita rediseño completo\}\}

No más parches incrementales.

# 12. Otro hallazgo: el “4-slot” es realmente 3-slot

Esto está confirmado.

`0x24` codifica:

```
\`oldest  = 0\`  
  
\`middle  = 1\`  
  
\`newest  = 2\`
```

y ningún camino introduce:

```
\`slot = 3\`
```

Así que:

NUM\_SLOTS=4 en Python≠3 slots efectivos en C++\\boxed\{\\text\{NUM\\\_SLOTS=4 en Python\} \\neq \\text\{3 slots efectivos en C++\}\}

Eso significa:

```
\`25% del área reservada nunca participa.\`
```

No es solo memoria desperdiciada.

Es evidencia de que las capas no comparten la misma máquina de estados.

# 13. Stiefel: los otros modelos tenían razón con los 40.96 GB

Esto queda confirmado.

Para:

D=107,K=512D=10^7,\\quad K=512

el vector:

```
\`G\\\_proj.assign(D\\\*K, 0.0);\`
```

requiere:

107×512×8=40 960 000 00010^7\\times512\\times8 = 40\\,960\\,000\\,000

bytes.

40.96 GB\\boxed\{40.96\\ GB\}

solo ese objeto.

El código efectivamente lo materializa.

# 14. Pero una solución de Gemini también está mal

Gemini propone “tile 256” y:

```
\`double local\\\_update =\`  
  
\`    g\\\_val - (y\\\_val \\\* 0.5);\`
```

Eso **no es la retracción Cayley-SMW**.

Es simplemente:

g−y2.g-\\frac y2.

No existe una identidad matemática que permita sustituir el sistema de Cayley:

(I−τ2VTU)Z=...(I-\\frac\{\\tau\}\{2\}V^TU)Z=...

por eso.

Por tanto:

esa propuesta NO DEBE entrar al coˊdigo\\boxed\{\\text\{esa propuesta NO DEBE entrar al código\}\}

Es un pseudo-parche de rendimiento que destruye la matemática.

# 15. La solución matrix-free de DeepSeek sí va en la dirección correcta

La identidad:

Gp=G−X sym⁡(XTG)G\_p = G-X\\,\\operatorname\{sym\}(X^TG)

permite calcular:

XTGpX^TG\_p

sin guardar:

Gp∈RD×K.G\_p\\in\\mathbb R^\{D\\times K\}.

Y:

GpTGp=GTG−GTX S−S XTG+S XTX S,G\_p^TG\_p = G^TG - G^TX\\,S - S\\,X^TG + S\\,X^TX\\,S,

con:

S=sym⁡(XTG).S=\\operatorname\{sym\}(X^TG).

Eso reduce el estado intermedio a:

O(K2)O(K^2)

en vez de:

O(DK).O(DK).

### Pero falta una segunda etapa

La propuesta de DeepSeek sigue teniendo que estudiar:

O(DK2)O(DK^2)

de cálculo por fila.

No es magia:

```
\`40 GB → 2 MB\`
```

es perfectamente plausible,

pero:

```
\`40 GB → “gratis”\`
```

no.

La cuestión pasa del **memory capacity bound** al **memory bandwidth + FLOP bound**.

# 16. El `GpGp` actual parece basura de diseño

Encontré además:

```
\`std::vector\\\<double\\\> GpGp(KK, 0.0);\`
```

en el cálculo de Stiefel.

El objeto se crea pero no es utilizado posteriormente.

Eso es exactamente el tipo de residuo de una iteración de desarrollo que un Red Team industrial debe eliminar.

No es el problema grande, pero es señal de:

```
\`algorithmic drift\`
```

y hay que limpiar estos residuos antes de certificar.

# 17. CholQR2: aquí corrijo otra sospecha anterior

Yo había dejado abierta la posibilidad de que el triangular solve estuviese orientado incorrectamente.

Lo probé.

La implementación actual hace:

A=XTX=LLTA=X^TX=LL^T

y resuelve cada fila mediante:

LqiT=xiTLq\_i^T=x\_i^T

que equivale a:

Q=XL−T.Q=XL^\{-T\}.

Eso es coherente.

### Resultado

Pruebas aleatorias:

```
\`D=8,K=3\`  
  
\`D=64,K=4\`  
  
\`D=100,K=8\`
```

dieron:

∥QTQ−I∥∞\\|Q^TQ-I\\|\_\\infty

del orden de:

10−16.10^\{-16\}.

Por tanto:

la orientacioˊn triangular NO era el bug\\boxed\{\\text\{la orientación triangular NO era el bug\}\}

Esto es exactamente el tipo de corrección que quiero hacer respecto de las otras IAs.

# 18. Pero CholQR2 tiene un problema mucho más importante

El umbral:

```
\`if (s \\\<= 1e-14)\`  
  
\`    return POLYDIM\\\_ERR\\\_DEGENERATE\\\_NORM;\`
```

es absoluto.

Lo probé:

```
\`X\`  
  
\`1e-8 X\`  
  
\`1e-100 X\`  
  
\`1e-154 X\`
```

La matriz sigue teniendo el mismo rango.

Pero:

```
\`X       -\\\> SUCCESS\`  
  
\`1e-8X   -\\\> DEGENERATE\`  
  
\`...\`
```

Por tanto:

la decisioˊn depende de la escala absoluta\\boxed\{\\text\{la decisión depende de la escala absoluta\}\}

y no de una propiedad relativa de la matriz.

# 19. SOTA real para CholQR2

Aquí Claude/Gemini/DeepSeek tienen razón en la dirección, pero hay que afinar.

CholeskyQR2 y Shifted CholeskyQR3 son familias importantes para tall-skinny QR; la literatura señala explícitamente la limitación de CholeskyQR2 para matrices mal condicionadas y el papel estabilizador de Shifted CholeskyQR3.

Y hay trabajos recientes que mejoran el desplazamiento de Shifted CholeskyQR3 para mejorar la aplicabilidad en matrices mal condicionadas.

Pero no haría:

```
\`if kappa \\\> 1e7\`  
  
\`    magically switch\`
```

sin antes definir cómo se estima κ\\kappa.

# 20. Mejor arquitectura de QR

Yo usaría un selector:

```
\`                  X\`  
  
\`                  │\`  
  
\`           estimate conditioning\`  
  
\`                  │\`  
  
\`          ┌───────┴────────┐\`  
  
\`          │                │\`  
  
\`       well-conditioned   ill-conditioned\`  
  
\`          │                │\`  
  
\`      CholQR2          Shifted / TSQR\`  
  
\`          │                │\`  
  
\`          └───────┬────────┘\`  
  
\`                  │\`  
  
\`          independent check\`  
  
\`                  │\`  
  
\`            ||QᵀQ-I||\`
```

Y como tercera línea de investigación:

```
\`Randomized Householder-Cholesky\`
```

porque existe trabajo que analiza precisamente estabilidad de QR tall-skinny con costo cercano a CholeskyQR2 y mejor robustez numérica.

# 21. Tangent Adapter: consenso correcto, pero también hay un detalle que DeepSeek no cerró

El actual:

```
\`if norm\\\_h \\\< eps:\`  
  
\`    u\\\[0\\\] = 1.0\`  
  
\`    r = -100.0\`
```

obviamente no es biyectivo.

Ejemplo:

```
\`h = 0\`  
  
\`h = 1e-20 e1\`  
  
\`h = 1e-30 e2\`
```

pueden terminar en el mismo código especial.

Esto es inequívoco.

# 22. Pero `-inf` tampoco debería ser presentado como “biyección completa” sin definir el espacio

La afirmación matemática correcta es:

RD∖\{0\}≅SD−1×R.\\mathbb R^D\\setminus\\\{0\\\} \\cong S^\{D-1\}\\times\\mathbb R.

El cero es un punto especial.

Así que hay dos diseños limpios:

### Diseño A

Declarar:

h≠0.h\\ne0.

### Diseño B

Usar unión disjunta:

\{ZERO\}⊔(SD−1×R)\\boxed\{ \\\{ZERO\\\} \\sqcup (S^\{D-1\}\\times\\mathbb R) \}

Eso sí es un contrato matemáticamente limpio.

# 23. Además: `np.linalg.norm()` no es suficientemente robusto para extremos

Probé:

```
\`h=\\\[1e300,0,0\\\]\`
```

y la norma convencional puede overflowear.

La estrategia correcta es escalada:

m=max⁡i∣hi∣m=\\max\_i|h\_i| ∥h∥=m∑i(hi/m)2.\\|h\\| = m\\sqrt\{\\sum\_i(h\_i/m)^2\}.

Eso evita overflow intermedio.

El mismo principio debe utilizarse en:

```
\`C++\`  
  
\`Rust\`  
  
\`Python\`  
  
\`GPU\`
```

para que la matemática conceptual sea consistente.

# 24. El canario “subnormal” del dossier está mal elegido

Aquí Claude acertó totalmente.

El dossier utiliza:

1.0005×10−42.1.0005\\times10^\{-42\}.

Para FP64:

min normal≈2.225×10−308.\\text\{min normal\}\\approx2.225\\times10^\{-308\}.

Por tanto:

10−4210^\{-42\}

es perfectamente normal en binary64.

Eso NO prueba preservación de subnormales FP64.

### Canary correcto

Por ejemplo:

10−31010^\{-310\}

o:

5×10−324.5\\times10^\{-324\}.

Este punto es importante porque la certificación publicada de subnormales está basada en una prueba que no prueba lo que dice.

# 25. Gemini exageró muchísimo el problema de subnormales

Gemini afirma una penalización tipo:

> “factores superiores a 100×”

por “microcode traps” en cualquier x86.

Eso **no lo acepto como hallazgo**.

El comportamiento depende de:

- microarquitectura;

- FPU;

- configuración MXCSR;

- tipo de instrucción;

- pipeline;

- compilador;

- distribución de datos.

No hay base para convertir eso en:

100×100\\times

como constante universal.

### Veredicto

```
\`“subnormales tienen posible impacto de rendimiento” → ✅\`  
  
\`“100x universal” → ❌\`  
  
\`“1e-42 prueba FP64 subnormal” → ❌\`
```

# 26. GPU: otra corrección importante a las IAs

Claude/Gemini proponen:

> `math.fsum` sobre los parciales del GPU.

No lo utilizaría como solución final.

`math.fsum()` es una herramienta de suma precisa en CPU, y Python la documenta como una suma de alta precisión relativa.

Pero llevar miles de parciales:

```
\`GPU\`  
  
\`↓\`  
  
\`CPU\`  
  
\`↓\`  
  
\`Python fsum\`  
  
\`↓\`  
  
\`GPU / siguiente etapa\`
```

no es una arquitectura SOTA para un pipeline cuyo objetivo es:

D=107D=10^7

y baja latencia.

### Mejor

Hacer una reducción determinista en GPU:

```
\`tile\`  
  
\` ↓\`  
  
\`FP64 accumulator\`  
  
\` ↓\`  
  
\`second-stage tree reduction\`  
  
\` ↓\`  
  
\`single scalar/vector result\`
```

y solo traer:

```
\`5 o 6 doubles\`
```

al host.

# 27. El stream de Triton sigue siendo un bug real

El API recibe:

```
\`stream\`
```

pero no lo emplea correctamente.

Por tanto:

```
\`caller stream\`  
  
\`       ↓\`  
  
\`expectation\`  
  
\`       X\`  
  
\`actual launch\`  
  
\`       ↓\`  
  
\`default/current stream\`
```

Eso rompe composición asíncrona.

# 28. Triton tampoco implementa las mismas precondiciones que C++

El C++ comprueba:

```
\`theta finite\`  
  
\`y norm\`  
  
\`u norm\`  
  
\`v norm\`  
  
\`u.v\`
```

El GPU no replica todas estas puertas.

Así que actualmente:

CPU contract≠GPU contract\\boxed\{ \\text\{CPU contract\} \\neq \\text\{GPU contract\} \}

Y eso es intolerable para una certificación multi-backend.

# 29. LSM: aquí todas las IAs acertaron

Actual:

```
\`nnz = int(dim \\\* sparsity)\`  
  
  
\`self.sparse\\\_indices = \\\[\`  
  
\`    np.random.choice(dim, nnz, replace=False)\`  
  
\`    for \\\_ in range(dim)\`  
  
\`\\\]\`
```

Por tanto:

nnz=ρDnnz=\\rho D

y:

D⋅nnz=ρD2.D\\cdot nnz = \\rho D^2.

Para:

D=107,ρ=0.05D=10^7,\\rho=0.05

tenemos:

5×10125\\times10^\{12\}

entradas.

Solo índice + weight:

5×1012×16=80 TB.5\\times10^\{12\}\\times16 = 80\\ TB. esto no es un detalle; la arquitectura LSM actual no escala\\boxed\{\\text\{esto no es un detalle; la arquitectura LSM actual no escala\}\}

# 30. Pero “SORM” tampoco es una varita mágica

SORM sí existe como construcción matemática de matrices de reservoir escasas y ortogonales, con propiedades espectrales determinadas por construcción.

Eso es útil.

Pero una implementación SORM correcta debe preservar:

```
\`sparsity target\`  
  
\`orthogonality\`  
  
\`connectivity\`  
  
\`spectral properties\`  
  
\`non-power-of-two dimensions\`  
  
\`reproducibility\`
```

No basta con escribir:

```
\`depth=3\`
```

y llamarlo SORM.

Además, para DD no potencia de 2, una butterfly ingenua puede dejar componentes desconectados.

La construcción tiene que especificar cómo se cubren exactamente:

0,…,D−1.0,\\ldots,D-1.

# 31. Otro bug de LSM que no quiero perder

La afirmación:

> “O(1) temporal memory”

no tiene el significado habitual de complejidad algorítmica.

Un estado:

xt∈RDx\_t\\in\\mathbb R^D

ya requiere:

O(D)O(D)

espacio.

Y actualizarlo cuesta al menos:

Ω(D)\\Omega(D)

porque hay que producir D componentes.

Lo correcto sería decir:

> “sin memoria temporal que crezca con el número de pasos TT”.

Eso sí sería una propiedad de tipo:

O(D)O(D)

independiente de TT.

No:

O(1)O(1)

absoluto.

# 32. Quantum: las otras IAs también acertaron

La implementación actual dice:

```
\`q1 = p1 % num\\\_qubits\`  
  
\`q2 = p2 % num\\\_qubits\`
```

Eso no es una embedding reversible de:

\{0,…,D−1\}\\\{0,\\ldots,D-1\\\}

en:

\{0,…,n−1\}.\\\{0,\\ldots,n-1\\\}.

Para:

D=107D=10^7

hay:

n=24n=24

qubits.

Pero:

```
\`coordinate 0\`  
  
\`coordinate 24\`  
  
\`coordinate 48\`  
  
\`...\`
```

terminan chocando.

# 33. Peor: el “Clifford+T compiler” no sintetiza Clifford+T

La implementación declara:

```
\`Ross-Selinger\`  
  
\`Solovay-Kitaev\`
```

pero hace:

```
\`k = round(theta / (pi/4))\`
```

y si sobra algo:

```
\`H T H S\`
```

Eso no implementa una síntesis garantizada de:

Rz(θ).R\_z(\\theta).

Además el circuito añade directamente:

```
\`ry(theta)\`
```

lo cual contradice la promesa de eliminar ángulos continuos.

### Veredicto:

Quantum compiler: REDESIGN\\boxed\{\\text\{Quantum compiler: REDESIGN\}\}

No parche.

# 34. La corrección SOTA tampoco es simplemente “instala pygridsynth”

DeepSeek propone utilizar una biblioteca como Gridsynth.

La dirección es mucho mejor porque las herramientas reales de síntesis aproximada Clifford+T existen.

Pero el contrato correcto sigue siendo:

∥U−Uapprox∥≤ϵtarget\\boxed\{ \\|U-U\_\{\\mathrm\{approx\}\}\\| \\le \\epsilon\_\{\\mathrm\{target\}\} \}

no:

```
\`“la biblioteca existe”\`
```

Cada síntesis debe producir:

```
\`approximation\\\_error\`  
  
\`T\\\_count\`  
  
\`Clifford\\\_count\`  
  
\`depth\`
```

y el compilador debe validar la cota.

# 35. RDMA: consenso completo

El nombre actual:

```
\`MirWireRdmaEndpoint\`
```

miente respecto de la implementación.

Lo que realmente existe es:

```
\`socket.AF\\\_INET\`  
  
\`socket.SOCK\\\_STREAM\`
```

es decir TCP.

No:

```
\`ibverbs\`  
  
\`QP\`  
  
\`CQ\`  
  
\`MR\`  
  
\`RDMA\\\_WRITE\\\_WITH\\\_IMM\`
```

Por eso:

MIR-Wire actual = protocolo TCP con payload binario\\boxed\{\\text\{MIR-Wire actual = protocolo TCP con payload binario\}\}

No RDMA.

# 36. Pero la solución “use pyverbs” tampoco basta

Para RDMA real hay que resolver:

```
\`memory registration\`  
  
\`PD\`  
  
\`MR\`  
  
\`QP\`  
  
\`CQ\`  
  
\`WR\`  
  
\`completion\`  
  
\`memory ordering\`  
  
\`lifetime\`  
  
\`backpressure\`
```

Y si además se quiere GPU-direct:

- memoria GPU registrada;

- sincronización CUDA;

- compatibilidad de PCIe/root complex;

- IOMMU;

- driver/HCA;

- pin/unpin;

- lifecycle.

NVIDIA documenta explícitamente que GPUDirect RDMA requiere registro de memoria y tiene requisitos de plataforma y sincronización; no es una simple sustitución de `socket` por una llamada RDMA.

Además NVIDIA señala que en ARM64 el soporte depende de hardware/software concretos y no debe interpretarse como universal.

Esto golpea directamente tu requisito:

> “cualquier GPU / CPU / placa”.

Ese requisito **no puede coexistir literalmente con “RDMA/GPU-direct en cualquier hardware”**.

Hay que separar:

```
\`portable baseline\`  
  
\`optimized backend\`  
  
\`optional accelerator backend\`
```

# 37. MIR-Wire tiene además tres fallos de protocolo que siguen vivos

El receiver hace:

```
\`bytes\\\_received += n\`
```

y si llega EOF:

```
\`break\`
```

pero después continúa construyendo el tensor y manda ACK.

Debe ser:

```
\`if bytes\\\_received != tensor\\\_bytes:\`  
  
\`    conn.close()\`  
  
\`    continue\`
```

antes de aceptar el frame.

Segundo:

```
\`ack = sock.recv(3)\`
```

no verifica que sea:

```
\`ACK\`
```

Tercero:

```
\`except Exception:\`  
  
\`    break\`
```

hace que una conexión corrupta pueda matar el receiver.

# 38. Y hay una vulnerabilidad DoS

No hay límite superior explícito para:

```
\`tensor\\\_bytes\`
```

El peer puede anunciar:

```
\`tensor\\\_bytes = enorme\`
```

y el receiver hace:

```
\`bytearray(tensor\\\_bytes)\`
```

antes de comprobar que realmente pueda aceptarlo.

Eso es:

memory denial-of-service\\boxed\{\\text\{memory denial-of-service\}\}

y debe cerrarse con:

```
\`MAX\\\_FRAME\\\_BYTES\`
```

antes de toda asignación.

# 39. Betti-1: todas las IAs tienen razón

Rust calcula:

EE

y:

CC

pero jamás devuelve:

β1=E−V+C.\\beta\_1=E-V+C.

La condición actual es:

```
\`if components \\\> 1 \\\{\`  
  
\`    return ErrTopologyFragmented;\`  
  
\`\\\}\`
```

Eso es un test de:

β0=1.\\beta\_0=1.

No de:

β1.\\beta\_1.

El propio comentario del código dice la fórmula y luego no la usa.

Por tanto:

Betti-1 guard actual = incorrectamente denominado\\boxed\{\\text\{Betti-1 guard actual = incorrectamente denominado\}\}

# 40. Rust tiene otro fallo numérico que quiero conservar en la lista

Hace:

```
\`let sq = val \\\* val;\`
```

Si:

```
\`val = 1e200\`
```

entonces:

val2=∞.val^2=\\infty.

Después el acumulador puede terminar en:

NaN.NaN.

Pero la condición final actual no valida correctamente `norm\\\_sq.is\\\_finite()` antes de comparar el drift.

Y:

```
\`NaN \\\> tolerance\`
```

es falso.

Así que existe una vía:

```
\`finite input\`  
  
\`→ overflow intermedio\`  
  
\`→ NaN\`  
  
\`→ comparación false\`  
  
\`→ posible SUCCESS\`
```

Esto es exactamente la clase de bug que un código “NaN-safe” puede esconder.

`from\\\_raw\\\_parts` además tiene precondiciones estrictas de puntero, alineación y tamaño que deben cumplirse antes de crear el slice; `catch\\\_unwind` no sustituye esas precondiciones. La documentación actual de Rust lo especifica explícitamente.

# 41. FFI: aquí ya tenemos un desastre de versiones, no simplemente una firma incorrecta

Monolito:

```
\`argtypes = \\\[\`  
  
\`    c\\\_void\\\_p,\`  
  
\`    c\\\_void\\\_p,\`  
  
\`    c\\\_void\\\_p,\`  
  
\`    c\\\_size\\\_t,\`  
  
\`    POINTER(VerifyReport)\`  
  
\`\\\]\`
```

→ 5 argumentos.

Rust real:

```
\`polydim\\\_rust\\\_verify\\\_invariants(\`  
  
\`    ptr,\`  
  
\`    d,\`  
  
\`    max\\\_drift\\\_out\`  
  
\`)\`
```

→ 3.

La llamada del monolito incluso pasa:

```
\`tensor.ctypes.data,\`  
  
\`None,\`  
  
\`None,\`  
  
\`c\\\_size\\\_t(D),\`  
  
\`byref(report)\`
```

Eso es una contradicción ABI objetiva.

# 42. Pero además hay una contradicción semántica de errores

Rust:

```
\`-4 = ErrSubnormalDetected\`  
  
\`-8 = ErrDegenerateNorm\`
```

C++:

```
\`-4 = DEGENERATE\\\_NORM\`  
  
\`-5 = NUMERICAL\\\_INSTABILITY\`  
  
\`...\`
```

Entonces:

mismo int32≠mismo significado\\boxed\{ \\text\{mismo int32\} \\ne \\text\{mismo significado\} \}

Eso es aún peor que una firma incorrecta porque puede provocar errores silenciosos al evolucionar las versiones.

# 43. Solución definitiva de FFI

No haría depender el sistema de cinco definiciones manuales.

Una sola fuente:

```
\`typedef int32\\\_t PolydimStatus;\`  
  
  
\`enum \\\{\`  
  
\`    POLYDIM\\\_SUCCESS = 0,\`  
  
\`    POLYDIM\\\_ERR\\\_NULL\\\_POINTER = -1,\`  
  
\`    POLYDIM\\\_ERR\\\_INVALID\\\_DIMENSION = -2,\`  
  
\`    ...\`  
  
\`\\\};\`
```

Y:

```
\`C ABI\`  
  
\`  ↓\`  
  
\`bindgen / cbindgen / generated ctypes declarations\`  
  
\`  ↓\`  
  
\`Rust\`  
  
\`  ↓\`  
  
\`Python\`  
  
\`  ↓\`  
  
\`Dart\`
```

Además:

```
\`uint32\\\_t polydim\\\_abi\\\_version(void);\`  
  
\`const char\\\* polydim\\\_abi\\\_hash(void);\`
```

El loader debe rechazar:

```
\`ABI mismatch\`
```

en lugar de descubrirlo mediante un crash.

# 44. `extern "C"` no debe dejar escapar excepciones

Esto también está confirmado.

Microsoft especifica que una función `extern "C"` llamada desde código no excepcional debe impedir que las excepciones C++ crucen esa frontera; si no pueden manejarse de forma específica, debe existir `catch(...)` final.

Y un exception sin handler termina en `std::terminate`.

Por eso todas las exportaciones públicas deben tener una política uniforme:

```
\`extern "C"\`  
  
\`POLYDIM\\\_EXPORT\`  
  
\`int32\\\_t\`  
  
\`POLYDIM\\\_CALL\`  
  
\`foo(...) noexcept\`  
  
\`\\\{\`  
  
\`    try \\\{\`  
  
\`        return foo\\\_impl(...);\`  
  
\`    \\\}\`  
  
\`    catch (const std::bad\\\_alloc&) \\\{\`  
  
\`        return POLYDIM\\\_ERR\\\_BUFFER\\\_OVERFLOW;\`  
  
\`    \\\}\`  
  
\`    catch (...) \\\{\`  
  
\`        return POLYDIM\\\_ERR\\\_INTERNAL;\`  
  
\`    \\\}\`  
  
\`\\\}\`
```

No algunas sí y algunas no.

# 45. Python tiene un problema industrial diferente: `assert`

En el código aparecen:

```
\`assert ...\`
```

para validación de inputs.

Con:

```
\`python -O\`
```

los asserts desaparecen.

Por tanto un release optimizado puede perder precisamente sus validaciones de seguridad.

### Sustitución

```
\`if tensor.dtype != np.float64:\`  
  
\`    raise TypeError(...)\`  
  
  
\`if tensor.size != self.D:\`  
  
\`    raise ValueError(...)\`
```

Los `assert` quedan solo para invariantes internas de desarrollo.

# 46. La afirmación teórica sobre DPI también está mal

Esto apareció repetidamente en el dossier y varias IAs lo señalaron.

El dossier dice esencialmente:

> serializar a texto viola DPI.

No.

Si:

Z=g(Y)Z=g(Y)

entonces DPI dice:

I(X;Y)≥I(X;Z)\\boxed\{ I(X;Y)\\ge I(X;Z) \}

Es decir, si la serialización es una transformación con pérdida:

I(X;text)\<I(X;latent)I(X;\\text\{text\}) \< I(X;\\text\{latent\})

puede ocurrir.

Pero eso **es precisamente compatible con DPI**, no una violación.

La DPI expresa justamente que el procesamiento posterior no puede aumentar mutual information.

### Formulación que sí salvaría la teoría

En lugar de:

> “text serialization violates DPI”

usar:

> “a lossy serialization/quantization step can reduce recoverable information and may impose latency, bandwidth and representation costs.”

Eso es defendible.

# 47. Otra exageración teórica: “0 tokens ⇒ DPI loss = 0”

Tampoco se deduce.

Zero tokens on wire significa:

```
\`no textual tokenization in transport\`
```

No significa:

I(X;Y)=I(X;Z).I(X;Y)=I(X;Z).

Podrías transformar:

```
\`latent A\`  
  
\`→ latent B\`
```

y perder información incluso sin usar tokens.

La información debe medirse con un modelo estadístico explícito.

# 48. La certificación “20.000 hops ≤ 2.22e-16” debe desaparecer del dossier

Esto ya no es negociable.

La ejecución actual muestra deriva acumulativa.

No voy a aceptar:

```
\`20k hops\`  
  
\`≈ epsilon\`
```

como propiedad del kernel actual.

La condición correcta sería algo como:

∥yn∥−1≤B(n,u,θ,κ)\\|y\_n\\|-1 \\le B(n,u,\\theta,\\kappa)

o, si se introduce re-normalización cada paso:

∥yn∥−1≤B(u)\\|y\_n\\|-1 \\le B(u)

con el modelo numérico correspondiente.

# 49. Y tampoco llamaría a `4.44e-16` “machine epsilon”

Binary64:

ϵ=2.220446049250313×10−16.\\epsilon=2.220446049250313\\times10^\{-16\}.

Entonces:

4.44×10−16≈2ϵ.4.44\\times10^\{-16\}\\approx2\\epsilon.

No es la “epsilon exacta”.

Es un detalle pequeño matemáticamente, pero enorme documentalmente porque el dossier utiliza esas cifras como certificaciones.

# 50. Otro error documental: `Neumaier` no es `TwoSum`

El código actual implementa:

```
\`Neumaier::add()\`  
  
\`Neumaier::merge()\`
```

No un algoritmo element-wise `TwoSum` en Pass 2.

En la transformación:

```
\`y\\\_out\\\[i\\\] = y\\\[i\\\] + alpha\\\*u\\\[i\\\] + beta\\\*v\\\[i\\\];\`
```

no hay compensación TwoSum.

Así que la teoría y el código divergen.

# 51. Hay que eliminar una frase que puede inducir a una certificación falsa

El comentario:

> “Con sumación compensada la deriva medida es O(eps) e independiente de D”

es demasiado fuerte.

Debe convertirse en:

```
\`“En el conjunto de pruebas X, bajo el modelo de compilación Y,\`  
  
\`la desviación observada fue...”\`
```

o en una bound formal realmente derivada.

Nunca:

```
\`measured once\`  
  
\`→ theorem\`
```

# 52. False positives importantes de las otras IAs que NO voy a incorporar

Estas son las que considero incorrectas o sobredimensionadas:

### ❌ “cada stride 4096 produce TLB miss”

No.

Puede aumentar la presión de TLB, pero no hay una relación:

1 acceso=1 TLB miss.1\\text\{ acceso\}=1\\text\{ TLB miss\}.

Caches de TLB, page walks y prefetching cambian el comportamiento.

### ❌ “branch `isnan` causa 16×”

No como regla universal.

Un test finito con branch casi siempre predecible puede no costar prácticamente nada y el compilador puede vectorizar.

### ❌ “subnormals → 100× seguro”

No.

Arquitectura-dependiente.

### ❌ “AVX-512 siempre reduce de 4.5 GHz a 2 GHz”

No.

Depende de la microarquitectura y del vector mix.

### ❌ “nontemporal pragma garantiza `vmovntpd`”

No.

Una sugerencia/hint de no temporalidad no equivale a una instrucción específica del ISA en todo compilador/hardware.

### ❌ “liberar GIL manualmente dentro de una función llamada por ctypes” como solución universal

Eso merece una prueba específica de la ruta de binding; no introduciría `PyEval\\\_SaveThread()` dentro de una función arbitraria sin demostrar quién posee el GIL en ese punto.

### ❌ “seqlock puro arregla el PMTP”

No para datos `double` no atómicos concurrentemente escritos.

# 53. Lo que sí rescato de cada IA

## Claude

Muy fuerte en:

```
\`deriva acumulada\`  
  
\`canario subnormal\`  
  
\`métrica Gram\`  
  
\`memory traffic\`  
  
\`version skew\`
```

pero debe corregirse:

```
\`hop 574\`  
  
\`v=3u SUCCESS\`
```

para el código actual.

## DeepSeek

Muy fuerte en:

```
\`PMTP\`  
  
\`FFI\`  
  
\`G\\\_proj\`  
  
\`LSM\`  
  
\`tangent\`  
  
\`RDMA\`  
  
\`quantum\`
```

pero su solución PMTP propuesta **no la aceptaría tal cual**.

## Gemini

Útil para descubrir:

```
\`OOM\`  
  
\`reduction GPU\`  
  
\`bad\\\_alloc\`  
  
\`versioning\`  
  
\`Betti\`
```

pero tiene demasiadas extrapolaciones de hardware sin evidencia:

```
\`TLB x cada acceso\`  
  
\`100x subnormal\`  
  
\`16x branch\`  
  
\`AVX frequency exacta\`
```

Es bueno como generador de hipótesis; no como certificado.

## Kimi

Su valor principal fue confirmar que varios hallazgos no eran propios de una única auditoría.

## Qwen

No hay respuesta útil en el archivo.

# 54. El nuevo mapa maestro que recomiendo

Después del cruce completo, ya no quiero 30 tickets sueltos.

Quiero **9 subsistemas**.

```
\`A — ABI / versioning\`  
  
\`B — memory safety\`  
  
\`C — PMTP / IPC\`  
  
\`D — numerical kernel\`  
  
\`E — Stiefel / QR\`  
  
\`F — Rust topology\`  
  
\`G — GPU backend\`  
  
\`H — transport\`  
  
\`I — quantum / tangent / reservoir\`
```

Cada subsistema tendrá:

```
\`contract\`  
  
\`implementation\`  
  
\`adversarial tests\`  
  
\`sanitizers\`  
  
\`benchmark\`  
  
\`failure semantics\`
```

# 55. Orden de reconstrucción

Este orden es crítico.

### 1. ABI

Porque todo lo demás depende de él.

### 2. PMTP

Porque actualmente es inseguro.

### 3. memoria/overflow

Porque un cálculo matemáticamente perfecto puede corromper memoria.

### 4. Rodrigues + sphere projection

Porque es el núcleo geométrico.

### 5. Stiefel/QR

Porque depende de la base numérica.

### 6. Rust

Porque es un guard externo.

### 7. GPU

Cuando el contrato CPU esté cerrado.

### 8. transport

Porque debe transmitir un objeto ya correcto.

### 9. quantum/tangent/reservoir

Como adaptadores superiores.

# 56. La regla más importante que sale de todo esto

No volver a permitir esto:

```
\`“PASS”\`
```

sin saber **qué fue probado**.

Debe existir:

```
\`PASS\\\_MEMORY\`  
  
\`PASS\\\_ABI\`  
  
\`PASS\\\_NUMERICS\`  
  
\`PASS\\\_GEOMETRY\`  
  
\`PASS\\\_CONCURRENCY\`  
  
\`PASS\\\_GPU\`  
  
\`PASS\\\_TRANSPORT\`  
  
\`PASS\\\_TOPOLOGY\`
```

Y finalmente:

```
\`POLYDIM\\\_RELEASE\\\_CERTIFIED\`
```

solo si todos están en verde.

# 57. Estado real después de cruzar las otras IAs

Ahora mismo mi evaluación sería:

```
\`MATEMÁTICA BASE\`  
  
\`████████░░  buena, pero sobreclaimeada\`  
  
  
\`RODRIGUES\`  
  
\`██████░░░░  fórmula correcta; composición numérica aún no cerrada\`  
  
  
\`STIEFEL\`  
  
\`█████░░░░░  matemática razonable; escalabilidad/conditioning pendientes\`  
  
  
\`PMTP\`  
  
\`█░░░░░░░░░  REDESIGN REQUIRED\`  
  
  
\`FFI\`  
  
\`██░░░░░░░░  REDESIGN REQUIRED\`  
  
  
\`RUST GUARD\`  
  
\`███░░░░░░░  lógica topológica incorrecta\`  
  
  
\`GPU\`  
  
\`███░░░░░░░  contrato no equivalente al CPU\`  
  
  
\`LSM\`  
  
\`█░░░░░░░░░  arquitectura actual no escala\`  
  
  
\`RDMA\`  
  
\`█░░░░░░░░░  actualmente no es RDMA\`  
  
  
\`QUANTUM\`  
  
\`█░░░░░░░░░  no implementa lo que declara\`  
  
  
\`TANGENT\`  
  
\`████░░░░░░  fundamento correcto; bordes numéricos pendientes\`
```

No significa que “todo esté mal”.

Significa que **la base matemática existe, pero las capas industriales todavía no están cerradas**.

# 58. Y esto, finalmente, responde a tu preocupación de las 500 rondas

Sí: después de ver las respuestas de las otras IAs y volver a ejecutar el código, puedo decir algo con bastante confianza:

**el problema no era que faltara una décima ronda más. Faltaba una estrategia de cierre.**

Ahora ya tenemos algo muy diferente:

```
\`ANTES\`  
  
  
\`bug 1\`  
  
\`→ parche\`  
  
\`→ bug 2\`  
  
\`→ parche\`  
  
\`→ bug 3\`  
  
\`→ parche\`
```

Ahora:

```
\`PMTP\`  
  
\` ├─ writer ownership\`  
  
\` ├─ reader lifetime\`  
  
\` ├─ generation\`  
  
\` ├─ ABA\`  
  
\` ├─ process sharing\`  
  
\` ├─ initialization\`  
  
\` └─ backpressure\`  
  
  
\`FFI\`  
  
\` ├─ ABI\`  
  
\` ├─ layout\`  
  
\` ├─ status codes\`  
  
\` ├─ exceptions\`  
  
\` ├─ pointer contracts\`  
  
\` └─ version hash\`  
  
  
\`NUMERICS\`  
  
\` ├─ scaling\`  
  
\` ├─ compensation\`  
  
\` ├─ composition\`  
  
\` ├─ bounds\`  
  
\` ├─ subnormals\`  
  
\` └─ reproducibility\`
```

Una vez que cada árbol queda cerrado, **no debería volver a aparecer el mismo tipo de bug disfrazado tres rondas después**.

Y hay una decisión concreta que tomo a partir de esta auditoría cruzada:

NO aplicar el parche de seqlock de DeepSeek ni el pseudocoˊdigo Cayley de Gemini\\boxed\{\\textbf\{NO aplicar el parche de seqlock de DeepSeek ni el pseudocódigo Cayley de Gemini\}\}

El primero no cierra el modelo de memoria C++; el segundo rompe la matemática.

En cambio sí conservaría como líneas SOTA:

PMTP con slots pinzados+Stiefel matrix-free+normas escaladas+Shifted/TSQR seguˊn condicionamiento+reduccioˊn GPU determinista+ABI generado+SORM/estructurado para reservoir\\boxed\{ \\text\{PMTP con slots pinzados\} + \\text\{Stiefel matrix-free\} + \\text\{normas escaladas\} + \\text\{Shifted/TSQR según condicionamiento\} + \\text\{reducción GPU determinista\} + \\text\{ABI generado\} + \\text\{SORM/estructurado para reservoir\} \}

La documentación actual de sequence counters refuerza precisamente la necesidad de serializar los escritores y de tratar correctamente la consistencia del conjunto protegido.

Y aquí sí puedo darte una confirmación fuerte de “no alucinación”: **varios hallazgos atribuidos por las otras IAs a “verificación” fueron falsos o desactualizados, y los estoy descartando explícitamente en vez de sumarlos a la lista**. A la vez, los fallos que sobreviven aparecen directamente en el código actual y varios fueron reproducidos localmente. Esa es la diferencia entre coleccionar críticas y hacer Red Team de verdad.

