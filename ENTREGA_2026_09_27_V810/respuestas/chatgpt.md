He leído `03\_INSTRUCCIONES\_PROMPT\_IA.md` y he contrastado esas directivas contra el código, la suite, los logs y los artefactos auxiliares del archivo entregado. Las directivas exigen explícitamente verificar carreras/condiciones de borde, la regularización Tikhonov, el filtro Fréchet-Betti y la compatibilidad ABI/pánicos. 

## Veredicto del asedio actual

**POLYDIM V808 no puede certificarse como matemáticamente invariante, estable y memory-safe en su estado entregado.**

Y no por un único detalle: encontré **varios bloqueadores independientes**, algunos suficientemente graves como para invalidar por sí solos una certificación.

Los cinco más serios son:

1. **El ABI C/C++ y el ABI que usa la suite no coinciden.** 

2. **El ABI de los resultados Rust tampoco coincide con `ctypes`; hay potenciales escrituras fuera de buffer.** 

3. **El RCU/lease de PMTP tiene una carrera real y el escritor puede continuar aunque sigan existiendo lectores activos.** 

4. **El “Fréchet-Betti BFT” puede certificar enjambres maliciosos que el algoritmo debería rechazar.** 

5. **La regularización Tikhonov evita alguna división por cero, pero no garantiza que la salida pertenezca a Stiefel; en casos degenerados puede devolver una matriz con columna cero.** 

Además aparecen problemas de build, overflow, validación FFI, geometría esférica, determinismo, dimensiones objetivo y credibilidad de los “7/7 tests pass”.


# PASS 1 — Proveniencia, build y ABI

## 1. La auditoría solicitada pide V807, pero el objeto real es V808

El prompt de auditoría pide:

- `kernel\_cpp\_v807.cpp` 

- `kernel\_rust\_v807.rs` 

Pero el material consolidado y los fuentes principales entregados son:

- `kernel\_cpp\_v808.cpp.txt` 

- `kernel\_rust\_v808.rs.txt` 

- `polydim\_solver\_abi\_v808.h.txt` 

Y la propia suite se llama `test\_v808\_ipc\_suite.py`, pero contiene repetidamente texto de **V807**:

```
`test\_v807\_ipc\_suite.py`

`Suite ... V807 Definitiva`

`Definición de Estructuras Ctypes ABI V807`

`EJECUTANDO ... V807`

`7/7 TESTS PASS ... (V807)`
```

### Impacto

No se está certificando inequívocamente un único artefacto.

El riesgo aquí no es estético: un test V807, un header V808 y un DLL distinto pueden producir un “PASS” perfectamente inútil.

### Corrección

Hay que imponer un **identificador único de build**:

```
`POLYDIM\_VERSION = 808`

`POLYDIM\_GIT\_COMMIT = \<hash\>`

`POLYDIM\_ABI\_VERSION = 8`

`POLYDIM\_BUILD\_ID = SHA256(...)`
```

Y exponerlo mediante una función:

```
`int32\_t polydim\_get\_abi\_info(PolydimAbiInfo\* out);`
```

El test debe verificar que el binario cargado, el header esperado y el manifiesto pertenecen al mismo build.

### Criterio de cierre

La suite debe fallar si:

```
`source\_version != binary\_version`

`abi\_version != expected\_abi`

`binary\_hash != manifest\_hash`
```


## 2. El header que pretende ser C estándar no compila como C11

Lo comprobé compilando directamente:

```
`gcc -std=c11 polydim\_solver\_abi\_v808.h ...`
```

Resultado:

```
`error: expected specifier-qualifier-list before 'alignas'`
```

El header utiliza:

```
`alignas(128)`
```

pero en C11 la sintaxis estándar es `\_Alignas`; `alignas` sólo entra como palabra clave en C23, o como macro de compatibilidad desde `\<stdalign.h\>` hasta C23. 

### Impacto

El documento dice “C ABI”, pero el header no es un header C11 válido.

Eso invalida la afirmación de interoperabilidad C estándar.

### Corrección

Algo del estilo:

```
`\#if defined(\_\_cplusplus)`

`\#  define PD\_ALIGNAS(N) alignas(N)`

`\#else`

`\#  include \<stdalign.h\>`

`\#  define PD\_ALIGNAS(N) \_Alignas(N)`

`\#endif`
```

Y todavía mejor: **no exponer estructuras internas de concurrencia en el ABI público**.


## 3. Hay una contradicción ABI concreta en `PolydimSpscRing`

El header C++ declara:

```
`typedef struct \{`

`    alignas(128) uint64\_t write\_index;`

`    alignas(128) uint64\_t read\_index;`

`    alignas(128) uint64\_t capacity;`

`    uint64\_t capacity\_mask;`

`    PolydimTelemetryEvent\* ring\_buffer;`

`\} PolydimSpscRing;`
```

Yo compilé exactamente ese header con C++20 y obtuve:

```
`sizeof(PolydimSpscRing) = 40`

`alignof(PolydimSpscRing) = 8`


`offsets:`

`write\_index  = 0`

`read\_index   = 8`

`capacity     = 16`

`ring\_buffer  = 32`
```

La suite Python, en cambio, construye:

```
`write\_index = 0`

`read\_index  = 128`

`capacity    = 256`

`ring\_buffer = 272`
```

y por tanto:

```
`sizeof(ctypes PolydimSpscRing) = 280`
```

### Esto es crítico

No estamos hablando de una interpretación distinta de la alineación.

Estamos hablando de que **C++ leería/escribiría los campos en offsets completamente diferentes a los que cree Python**.

Si el C++ DLL correspondiente a ese header recibe la estructura creada por `ctypes`, el campo que C++ interpreta como `ring\_buffer` se encuentra donde Python tiene parte del padding.

Eso puede terminar en:

- puntero basura, 

- acceso inválido, 

- corrupción, 

- falsos positivos, 

- o simplemente una prueba que no está ejercitando el objeto que pretende ejercitar. 

### Causa adicional

El header está bajo:

```
`\#pragma pack(push,8)`
```

Eso impide que se materialice la intención de aislamiento de 128 bytes para el `Ring`.

### Corrección

No usaría esta estructura pública.

Haría:

```
`typedef struct polydim\_spsc\_ring polydim\_spsc\_ring\_t;`
```

y expondría:

```
`polydim\_spsc\_ring\_t\* polydim\_spsc\_create(size\_t capacity);`
```

El layout real queda privado.

Si obligatoriamente se necesita ABI estructural, entonces:

- layout C exacto, 

- `static\_assert(sizeof...)`, 

- `static\_assert(offsetof...)`, 

- `static\_assert(alignof...)`, 

- binding Python generado desde ese header, 

- test automático de layout. 


## 4. El ABI Rust está aún peor desalineado

Rust declara:

```
`\#\[repr(C, align(128))\]`

`pub struct PolydimBettiResult \{ ... \}`


`\#\[repr(C, align(128))\]`

`pub struct PolydimFrechetBettiResult \{ ... \}`
```

Con esos atributos, el tamaño efectivo de cada estructura debe respetar alineación de 128 bytes; en la práctica serán estructuras de **128 bytes**.

La suite Python, en cambio, las declara como:

```
`PolydimBettiResult       = 40 bytes`

`PolydimFrechetBettiResult = 48 bytes`
```

### Impacto

Rust hace:

```
`\*out\_result = PolydimFrechetBettiResult \{ ... \};`
```

Eso escribe la estructura Rust completa.

La memoria que `ctypes` reserva para ese objeto es sustancialmente menor.

**Esto es una potencial escritura fuera de límites en el objeto de salida.**

No lo clasificaría como “warning ABI”.

Lo clasificaría como **bloqueador de seguridad FFI**.

### Corrección

Un único header ABI debe definir esas estructuras.

No:

```
`Rust inventa layout`

`Python vuelve a inventar layout`

`C++ tiene otro layout`
```

sino:

```
`                ┌───────────────┐`

`                │ C ABI canonico│`

`                └───────┬───────┘`

`                        │`

`           ┌────────────┼─────────────┐`

`           ▼            ▼             ▼`

`         C++          Rust          Python`
```

Y el CI comprueba automáticamente `sizeof`, `alignof` y `offsetof`.


## 5. Los fuentes individuales ni siquiera son autónomos

Hay referencias como:

```
`\#include "polydim\_solver\_abi.h"`

`\#include "polydim\_blas\_loader.h"`
```

pero el árbol entregado contiene:

```
`polydim\_solver\_abi\_v808.h.txt`
```

y el BLAS loader aparece embebido dentro del consolidado.

Igualmente:

```
`\#include "polydim\_stiefel\_v805.h"`

`\#include "polydim\_ipc\_v805.h"`

`\#include "polydim\_crypto\_v805.h"`
```

desde archivos declarados V808.

Además el `CMakeLists.txt` archivado sigue siendo V807 y apunta a:

```
`src/polydim.cpp`
```

no a esta arquitectura V808.

### Corrección

Eliminar el “monolito textual” como artefacto de build.

El repositorio canónico debe contener:

```
`include/`

`src/`

`rust/`

`tests/`

`cmake/`
```

y `V808\_CODIGO\_FUENTE\_CONSOLIDADO.txt` sólo puede ser un artefacto documental generado.


# PASS 2 — Memoria, FFI y concurrencia

## 6. El `refcount` no es realmente un `std::atomic`

El ABI declara:

```
`int32\_t refcount;`
```

y luego el código hace:

```
`reinterpret\_cast\<std::atomic\<int32\_t\>\*\>(&handle-\>refcount)`
```

Eso no convierte mágicamente el objeto C en un objeto `std::atomic\<int32\_t\>` legítimo.

La herramienta adecuada en C++20 para aplicar operaciones atómicas sobre un objeto existente es `std::atomic\_ref`, que además exige alineación y que el objeto sea accedido conforme a sus reglas durante la vida del `atomic\_ref`. 

### Corrección preferida

Privatizar:

```
`struct HandleImpl \{`

`    std::atomic\<uint32\_t\> refs;`

`    ...`

`\};`
```

y hacer que el ABI público sólo vea:

```
`typedef struct polydim\_handle polydim\_handle\_t;`
```


## 7. `retain/release` tiene además un problema de lifetime

Aunque el contador fuese atómico, esto no soluciona:

```
`Thread A: release()`

`Thread B: retain()`
```

si B ya recibió un puntero cuyo objeto está llegando a destrucción.

Un refcount sólo es correcto si existe una garantía de que **ya se posee una referencia válida antes de intentar incrementarla**.

### Corrección

No permitir que un handle desnudo viaje sin ownership explícito.

Usar:

```
`create -\> owner ref`

`retain  -\> sólo desde owner existente`

`release -\> decrement`
```

y preferiblemente handles opacos con API de ownership clara.


## 8. La destrucción del SPSC puede correr contra push/pop

`polydim\_spsc\_destroy()` hace:

```
`polydim\_free\_aligned(ring-\>ring\_buffer);`

`ring-\>ring\_buffer = nullptr;`
```

No existe sincronización con:

```
`polydim\_spsc\_push()`

`polydim\_spsc\_pop()`
```

### Escenario

```
`CPU 1                       CPU 2`

`------                      ------`

`push()                     destroy()`

`lee ring\_buffer`

`                            free(buffer)`

`escribe buffer\[...\]`
```

Eso es un **use-after-free**.

### Corrección

Implementar un estado:

```
`OPEN`

`CLOSING`

`CLOSED`

`DESTROYED`
```

y exigir:

```
`close()`

`wait quiescence`

`destroy()`
```

o referencias internas que garanticen que no hay operaciones en curso.


## 9. El SPSC no garantiza que realmente exista un productor y un consumidor

El algoritmo presupone SPSC.

La API no impide que:

```
`2 productores`
```

llamen simultáneamente a `push()`.

Tampoco impide:

```
`2 consumidores`
```

llamando simultáneamente a `pop()`.

En ese caso deja de ser SPSC.

### Corrección

Separar handles:

```
`producer\_handle`

`consumer\_handle`
```

o declarar contractualmente un único owner productor y un único owner consumidor y hacerlo cumplir mediante tokens/thread IDs.


## 10. Hay una carrera seria en la publicación del lease PMTP

Esta es de las más peligrosas.

El lector hace:

```
`CAS(FREE -\> ACTIVE)`
```

y **después** escribe:

```
`leases\[i\].pid = pid;`

`leases\[i\].process\_start\_time\_ns = start\_time\_ns;`

`leases\[i\].generation = ...`
```

Pero el reaper hace:

```
`state == ACTIVE`

`    -\> lee pid`

`    -\> decide si el proceso vive`
```

### Secuencia adversarial

```
`Reader:`

`    CAS FREE -\> ACTIVE`


`                          Reaper:`

`                          ve ACTIVE`

`                          lee pid antiguo / basura / 0`

`                          concluye "muerto"`

`                          reclama lease`


`Reader:`

`    escribe pid`

`    escribe generation`
```

Eso rompe el protocolo de ownership.

### Corrección

La transición debe ser:

```
`FREE`

`  ↓ CAS`

`RESERVED`

`  ↓ escribir metadata`

`ACTIVE`
```

La publicación de `ACTIVE` debe ser el último paso con `memory\_order\_release`.


## 11. El escritor puede obtener OK aunque todavía existan lectores activos

Este es un fallo directo y contundente.

El escritor intenta esperar hasta 5000 iteraciones.

Pero luego hace:

```
`header-\>owner\_pid = pid;`

`...`

`\*write\_bank = target;`

`return POLYDIM\_STATUS\_OK;`
```

**No verifica que hayan desaparecido los lectores.**

Por tanto:

```
`lectores activos siguen presentes`

`        ↓`

`se consumen 5000 retries`

`        ↓`

`acquire\_writer devuelve OK`

`        ↓`

`writer escribe banco`

`        ↓`

`lector sigue leyendo ese banco`
```

Eso contradice directamente el objetivo de RCU.

### Corrección

Debe ser:

```
`if (has\_active\_readers)`

`    return POLYDIM\_STATUS\_ERR\_WRITER\_BUSY;`
```

Nunca:

```
`return OK;`
```

cuando la precondición de seguridad no se cumplió.

Y `timeout\_ns` debe dejar de ser argumento decorativo.


## 12. El writer tampoco tiene recuperación robusta del proceso muerto

Se marca:

```
`writer\_active = 1`
```

pero el mecanismo de recuperación está orientado a leases de lectores.

No hay una ruta equivalente suficientemente fuerte para:

```
`writer muere`

`↓`

`writer\_active queda 1`

`↓`

`sistema permanentemente bloqueado`
```

### Corrección

Agregar lease de escritor:

```
`owner\_pid`

`owner\_start\_time`

`owner\_generation`

`heartbeat`

`lease\_state`
```

y reclamación condicionada a token/generación.


## 13. `kill(pid,0)` no demuestra identidad del proceso

El código almacena:

```
`pid`

`process\_start\_time\_ns`
```

pero `pmtp\_is\_process\_alive()` verifica esencialmente:

```
`kill(pid, 0)`
```

No enlaza la vida actual al `start\_time`.

Eso deja abierto el clásico problema:

```
`proceso A tenía PID 123`

`muere`

`PID 123 se reutiliza por proceso B`

`reaper ve PID 123 vivo`
```

El `pidfd` de Linux está precisamente pensado para referirse a la tarea y evitar depender sólo de un PID numérico; la documentación de Linux lo recomienda para un proceso ya existente. 

### Corrección

Linux:

```
`pidfd\_open()`

`poll/epoll`
```

Windows:

```
`HANDLE al proceso`

`+ creación del proceso`
```

y el lease guarda además un generation/token.


## 14. `commit\_writer()` no autentica al escritor

La función:

```
`pmtp\_banked\_slot\_commit\_writer(header, write\_bank)`
```

no valida:

- quién adquirió el lease, 

- que `writer\_active == 1`, 

- que el caller sea el owner, 

- que `write\_bank` sea 0/1. 

Un caller cualquiera que tenga el puntero puede intentar hacer commit.

### Corrección

La adquisición debe devolver un token:

```
`PmtpWriterToken`
```

y commit:

```
`commit\_writer(header, token)`
```

El token debe contener:

```
`slot`

`bank`

`generation`

`owner identity`
```


## 15. `recorded\_count++` es un punto de carrera

En el solver:

```
`telemetry-\>recorded\_count++`
```

es acceso normal, no atómico.

Si dos llamadas concurrentes comparten el mismo `PolydimTelemetryBuffer`, ambas pueden obtener el mismo índice.

### Corrección

O bien:

```
`TelemetryBuffer = single producer`
```

en el contrato, o:

```
`atomic\_fetch\_add`
```

con reserva de índice.


## 16. `omp\_set\_num\_threads()` es estado de configuración compartido

El código modifica la configuración OpenMP desde funciones de la librería.

`omp\_set\_num\_threads()` cambia el ICV relacionado con el número de threads de las regiones paralelas posteriores. 

### Problema

Una llamada de usuario puede cambiar el comportamiento de otra llamada.

### Corrección

Usar:

```
`\#pragma omp parallel for num\_threads(threads)`
```

cuando proceda, o mantener configuración de ejecución por contexto, no un setter global de la librería.


# PASS 3 — Estabilidad numérica e invariantes de Stiefel

## 17. El “fix Tikhonov” no garantiza Stiefel

Aquí está uno de los puntos centrales del encargo.

`apply\_shifted\_cholqr2()` hace:

```
`if (val \<= 1e-14)`

`    val += adaptive\_shift;`


`if (val \<= 0.0)`

`    val = 1e-15;`
```

Eso evita algunas divisiones por cero.

Pero **no demuestra**:

XTX=IX^T X = I 

ni siquiera aproximadamente en casos degenerados.

### Contraejemplo directo

Tomé la estructura matemática exacta del algoritmo y la apliqué a una matriz con dos columnas idénticas:

X=\[11111111\]X = \\begin\{bmatrix\} 1&1\\\\ 1&1\\\\ 1&1\\\\ 1&1 \\end\{bmatrix\} 

La matriz es rank-deficiente.

La regularización produce una segunda dirección prácticamente degenerada y la lógica termina anulando esa columna.

Resultado conceptual:

QTQ≈\[1000\]Q^TQ \\approx \\begin\{bmatrix\} 1&0\\\\ 0&0 \\end\{bmatrix\} 

La desviación de identidad es aproximadamente:

∥QTQ−I∥F=1\\|Q^TQ-I\\|\_F = 1 

No es un error de 10−1510^\{-15\}.

Es una ruptura macroscópica del invariante.

### Caso aún más brutal

Para:

X=0X=0 

el algoritmo devuelve esencialmente:

Q=0Q=0 

y por tanto:

QTQ=0Q^TQ=0 

no II.

### Corrección correcta

Primero decidir qué propiedad se quiere garantizar.

### Opción A — preservación estricta de Stiefel

Si el rango es insuficiente:

```
`ERR\_RANK\_DEFICIENT`
```

No fabricar una dirección artificial y luego certificar.

Usar Householder QR / TSQR con detección de rango.

### Opción B — regularización

Si deliberadamente se quiere:

Gλ=G+λIG\_\\lambda = G+\\lambda I 

entonces el contrato debe reconocer que el resultado ya no satisface necesariamente la ortonormalidad exacta respecto de GG.

En ese caso:

```
`status = REGULARIZED`
```

no:

```
`status = OK / manifold invariant preserved`
```


## 18. La regularización no impide NaNs frente a NaNs de entrada

No hay validación exhaustiva de:

```
`std::isfinite(X\[i\])`
```

Si entra:

```
`NaN`
```

entran NaNs en Gram:

```
`G = NaN`
```

y luego:

```
`trace = NaN`

`shift = NaN`

`sqrt = NaN`

`division = NaN`
```

Tikhonov no “cura” NaNs.

### Corrección

Antes de operar:

```
`for (...) \{`

`    if (!std::isfinite(x\[i\]))`

`        return ERR\_NONFINITE\_INPUT;`

`\}`
```

Y verificar también resultados intermedios.


## 19. No existe el supuesto “TwoSum en dos pasadas” que exige el mandato

El código sí tiene `knuth\_two\_sum()` y una reducción determinista para la Gramiana.

Pero el solver no implementa el contrato que describes como:

```
`Pass 1:`

`global reduction con Neumaier`


`Pass 2:`

`projection/update element-wise TwoSum`
```

El gradiente usa reducciones OpenMP convencionales y operaciones ordinarias.

Por tanto:

**TwoSum existe; el mecanismo completo que pretende certificar el invariante no.**


## 20. `g\_fp\_mode` no modifica el hardware FP

El nombre del API induce a pensar en un “modo IEEE” real:

```
`polydim\_set\_fp\_mode(...)`
```

pero el código sólo cambia:

```
`g\_fp\_mode`
```

Eso no configura:

- MXCSR, 

- FTZ, 

- DAZ, 

- rounding mode, 

- entorno de coma flotante. 

### Corrección

Definir explícitamente el contrato:

```
`FP mode = algorithmic mode`
```

o realmente gestionar el entorno FP y restaurarlo después.

Pero entonces hay que probarlo en cada plataforma.


## 21. No hay gestión de FTZ/DAZ

No encontré una comprobación/control efectivo de:

```
`Flush-To-Zero`

`Denormals-Are-Zero`

`MXCSR`
```

Por tanto no es válido afirmar que el bound numérico está blindado contra esas condiciones.


## 22. La reducción “determinista” no hace determinista todo el solver

La Gram puede usar una ruta TwoSum.

Pero el objetivo y ciertas reducciones del solver utilizan:

```
`reduction(+:current\_obj)`

`reduction(+:current\_grad\_norm)`
```

Eso deja una parte del pipeline en manos del orden de reducción paralelo.

### Corrección

Definir el determinismo por niveles:

```
`bitwise deterministic`

`numerically reproducible`

`statistically reproducible`

`throughput`
```

y probar cada contrato explícitamente.


## 23. Los productos `D\*K` y `K\*K` no están protegidos contra overflow

Ejemplos:

```
`std::vector\<double\> G(D \* K, 0.0);`

`std::vector\<double\> Gram(K \* K, 0.0);`
```

sin comprobar:

```
`D\*K \<= SIZE\_MAX`

`K\*K \<= SIZE\_MAX`

`bytes \<= available memory`

`bytes \<= isize limits where relevant`
```

### Corrección

Crear una función única:

```
`bool checked\_mul\_size(size\_t a, size\_t b, size\_t\* out);`

`bool checked\_bytes(size\_t elements, size\_t element\_size, size\_t\* out);`
```

y usarla en todas las asignaciones.


## 24. El coste físico a D=10.000.000 es enorme

Sólo:

DKD K 

elementos `double` ocupan:

### K = 32

107×32×8=2.56 GB10^7\\times32\\times8 =2.56\\text\{ GB\} 

una sola matriz.

El solver tiene, entre otras cosas, `X` + `G`, y si existe `problem\_data`, son más gigabytes.

### K = 256

107×256×8=20.48 GB10^7\\times256\\times8 =20.48\\text\{ GB\} 

una sola matriz.

No existe un budget de memoria que diga:

```
`D máximo + K máximo + workspace máximo \<= RAM permitida`
```

### Corrección

API previa al cálculo:

```
`estimate\_memory(D,K)`
```

y rechazo determinista si excede el presupuesto.


## 25. La dimensión objetivo y el FWHT entran en conflicto

`polydim\_structured\_lsm\_step()` exige:

```
`(D & (D - 1)) == 0`
```

Es decir, D debe ser potencia de 2.

Pero el target declarado:

```
`10.000 \<= D \<= 10.000.000`
```

incluye valores que no son potencia de 2.

Por ejemplo:

```
`10,000  -\> no potencia de 2`

`10,000,000 -\> no potencia de 2`
```

### Corrección

Elegir explícitamente:

```
`A) zero-padding hasta next\_pow2(D)`

`B) transformada no-potencia-de-2`

`C) eliminar restricción para ese componente`
```

y especificar qué significa geométricamente ese padding.


# PASS 4 — Fréchet, esfera y topología

Este bloque contiene probablemente el **falso certificado más importante de toda la arquitectura**.

## 26. El filtro no calcula la distancia intrínseca de la esfera

El código calcula:

```
`sqrt(sum((x\_i-x\_j)^2))`
```

Eso es distancia euclídea/chordal en el espacio ambiente.

Para puntos unitarios de una esfera, la distancia geodésica es:

d(x,y)=arccos⁡(⟨x,y⟩)d(x,y)=\\arccos(\\langle x,y\\rangle) 

con clipping del producto interno. Esa es precisamente la formulación usada en implementaciones de geometría Riemanniana de la esfera. 

Por tanto:

**el filtro no está operando intrínsecamente en SD−1S^\{D-1\}**.

### Corrección

Validar primero:

∥xi∥2≈1\\|x\_i\\|\_2 \\approx 1 

y usar:

```
`dot = clamp(dot(x,y), -1, 1)`

`distance = acos(dot)`
```

Para rendimiento se puede evitar `acos` en tests de umbral:

d(x,y)≤τ  ⟺  xTy≥cos⁡(τ)d(x,y)\\le\\tau \\iff x^Ty\\ge\\cos(\\tau) 

para vectores unitarios.


## 27. El “caso varianza cero” está implementado al revés desde el punto de vista de seguridad

El código hace:

```
`if variance \< 1e-6 \{`

`    copy candidate 0`

`    certified = true;`

`    return OK;`

`\}`
```

Esto convierte “pocos datos distintivos en la muestra” en:

```
`CONSENSO CERTIFICADO`
```

sin volver a comprobar:

- norma 1, 

- finitud, 

- todos los candidatos, 

- capacidad de salida, 

- pertenencia a esfera. 

### Contraejemplo real

Con:

```
`10 vectores de dimensión 128`

`todos = 0`
```

la varianza es 0.

El algoritmo devuelve:

```
`certified = true`

`consensus = \[0,...,0\]`
```

Pero:

∥0∥=0≠1\\|0\\|=0\\ne1 

Por tanto no es un punto de S127S^\{127\}.

**He reproducido exactamente esta condición con los datos del algoritmo.**

### Corrección

Una varianza pequeña sólo puede ser:

```
`fast path candidate`
```

nunca:

```
`certificate`
```

Un certificado requiere validación completa.


## 28. El muestreo de varianza permite ocultar outliers

La estimación usa:

```
`step = max(1, n/100)`
```

y examina sólo ciertos pares.

Eso significa que no todos los candidatos necesariamente participan.

### Ataque conceptual

Con `n=1000`,:

```
`step = 10`
```

por lo que muchos índices nunca aparecen en el muestreo como `i`.

Un atacante puede colocar el vector malicioso en una posición no muestreada de forma relevante.

La varianza muestreada puede parecer nula o pequeña.

### Corrección

Regla fundamental:

> **Un muestreo puede acelerar; nunca puede elevar privilegios ni certificar.**

Para certificar:

```
`validate all candidates`
```

Si el coste exacto O(n²D) es demasiado alto, utilizar una estructura aproximada, pero con un bound que garantice que ningún elemento queda sin inspección para la propiedad que se quiere certificar.


## 29. Encontré un ataque de “puente” que derrota el supuesto filtro bizantino

Construí:

- 10 nodos honestos muy cerca de dirección 0, 

- 5 nodos adversarios formando una cadena progresiva, 

- threshold = 0.35. 

Ángulos de los 5 adversarios:

```
`0.30`

`0.64`

`0.98`

`1.32`

`1.66 rad`
```

Cada par consecutivo está a distancia chordal:

```
`≈ 0.33836`
```

por tanto el DSU los conecta.

Resultado exacto de la lógica del algoritmo:

```
`active       = 15`

`rejected     = 0`

`components   = 1`

`edges        = 59`

`betti1       = 45`

`certified    = true`
```

Mientras que el último adversario está a:

```
`≈ 1.47586`
```

de distancia chordal del centro honesto.

### Traducción

Cinco nodos maliciosos no necesitan estar cerca del consenso.

Les basta con **construir un puente topológico** entre el consenso y la región adversaria.

Por tanto:

> “componente gigante + quorum 2/3 + β1” no constituye un mecanismo BFT.

### Corrección

Hay que separar tres conceptos:

```
`geometric clustering`

`robust estimation`

`Byzantine fault tolerance`
```

No son equivalentes.

Para robustez geométrica:

- validar esfera, 

- estimador robusto, 

- bound de contaminación, 

- radio residual, 

- análisis explícito del peor caso. 

Para BFT real se necesita además un modelo formal de adversario y un protocolo de identidad/consenso; no basta con conectividad geométrica.


## 30. La “mediana de Fréchet” tampoco es intrínseca a la esfera

La implementación hace:

1. mediana de distancias euclídeas en el espacio ambiente, 

2. Weiszfeld euclídeo, 

3. normalización final. 

Eso no es lo mismo que minimizar:

∑idSD−1(x,xi)\\sum\_i d\_\{S^\{D-1\}\}(x,x\_i) 

sobre la esfera.

La normalización posterior no transforma automáticamente un problema euclídeo en uno Riemanniano.

### Corrección

Elegir explícitamente una definición:

### Mediana geodésica

Minimizar:

F(x)=∑idSD−1(x,xi)F(x)=\\sum\_i d\_\{S^\{D-1\}\}(x,x\_i) 

usando iteraciones en espacio tangente.

o una opción operacional más simple y verificable:

### Spherical medoid

Elegir uno de los candidatos como representante y minimizar exactamente la suma de distancias geodésicas.

Eso hace la certificación mucho más auditable.


## 31. El caso `n=1` con NaN puede terminar certificado

Con:

```
`n = 1`

`vector = \[NaN,...,NaN\]`
```

no hay pares para que falle el test de variación.

La ruta de grafo puede dejar:

```
`components = 1`

`active = 1`

`betti1 = 0`
```

y el criterio final:

```
`active \>= quorum`

`betti1 \<= max`
```

puede resultar verdadero.

El vector de consenso sigue siendo NaN.

### Corrección

La primera fase debe ser:

```
`for every candidate:`

`    finite?`

`    norm?`

`    sphere tolerance?`
```

antes de cualquier topología.


## 32. `unsafe from\_raw\_parts()` no vuelve seguro el FFI

Rust hace:

```
`std::slice::from\_raw\_parts(candidates\_ptr, n\*d)`
```

El propio contrato de Rust exige que el puntero sea válido, correctamente alineado, inicializado, que la región completa pertenezca a una sola allocation y que el tamaño no exceda `isize::MAX`. 

El problema es que el ABI sólo proporciona:

```
`pointer + n + d`
```

sin:

```
`capacity`
```

No puede verificarse que el caller haya realmente reservado `n\*d` elementos.

Lo mismo afecta al output mutable. Rust documenta requisitos equivalentes para `from\_raw\_parts\_mut`. 

### Corrección

La firma debe incluir capacidades:

```
`const double\* candidates,`

`size\_t candidates\_len,`


`double\* consensus,`

`size\_t consensus\_capacity,`
```

y:

```
`required = checked\_mul(n,d)`

`required \<= candidates\_len`

`d \<= consensus\_capacity`
```


## 33. Betti-1 no es un invariante del manifold S^(D−1)

El código calcula:

β1=E−V+C\\beta\_1 = E-V+C 

sobre un grafo de umbral.

Eso es el **ciclo-rank de ese grafo**, no el primer Betti del manifold esfera que constituye el espacio de representación.

Por tanto hay dos topologías distintas:

```
`Topología del manifold`

`          ≠`

`Topología del grafo de conectividad`
```

### Corrección

Si el objetivo es inferir estructura topológica de los datos:

- definir complejos simpliciales, 

- distancia intrínseca, 

- homología persistente, 

- filtración bien definida. 

Si el objetivo es simplemente detectar cohesión:

```
`component count`

`diameter/radius`

`robust residual`
```

son métricas mucho más directas.


# PASS 5 — FFI, claims de certificación y pruebas

## 34. `catch\_unwind` sí ayuda, pero no hace memory-safe al código

Rust usa:

```
`catch\_unwind(...)`
```

Eso es correcto como mecanismo para capturar un panic que realmente realiza unwinding. La documentación de Rust deja claro que `catch\_unwind` captura panics por unwinding y que los detalles de ABI/unwinding importan. 

Pero no cubre:

- punteros FFI inválidos, 

- UB, 

- corrupción de memoria, 

- aliasing inválido, 

- excepciones C++ no controladas, 

- `panic=abort`. 

### Por tanto

```
`catch\_unwind != memory safety`
```

### Corrección

Reducir `unsafe` a wrappers mínimos y validar completamente:

```
`pointer`

`alignment`

`length`

`capacity`

`aliasing`

`overflow`

`output sizes`
```

antes de entrar en la parte matemática.


## 35. `AssertUnwindSafe` está siendo usado como afirmación, no como demostración

Esto:

```
`catch\_unwind(AssertUnwindSafe(|| \{ ... \}))`
```

dice al compilador:

> “asumo que esto es unwind-safe”.

No demuestra que lo sea.

Además puede haber efectos parciales sobre buffers antes del panic.

### Corrección

Diseño transaccional:

```
`calcular en buffers privados`

`↓`

`validar`

`↓`

`commit atómico al output`
```

No escribir parcialmente la salida pública antes de saber que la operación terminó correctamente.


## 36. El error TLS tiene un contrato pobre

`polydim\_last\_error\_v1()` devuelve un:

```
`\*const c\_char`
```

a una `CString` TLS.

Su contenido puede cambiar cuando el mismo thread genera otro error.

Es mejor que devolver memoria heap arbitrariamente, pero no es un contrato estable de interoperabilidad.

### Corrección

Usar:

```
`int32\_t polydim\_get\_last\_error(`

`    char\* buffer,`

`    size\_t capacity`

`);`
```


## 37. C++ no protege todas las excepciones de frontera FFI

Funciones `extern "C"` crean `std::vector`.

Eso significa que una excepción como `std::bad\_alloc` puede producirse dentro del cuerpo antes de que se convierta en un `PolydimStatus`.

### Corrección

Cada entry point FFI debe tener estructura:

```
`extern "C" int32\_t api(...) noexcept \{`

`    try \{`

`        ...`

`    \} catch (const std::bad\_alloc&) \{`

`        return ERR\_ALLOC;`

`    \} catch (...) \{`

`        return ERR\_INTERNAL;`

`    \}`

`\}`
```

Y nunca dejar una excepción C++ atravesar la frontera.


## 38. Las pruebas no pueden reproducirse con el material entregado

Busqué ejecutables:

```
`\*.dll`

`\*.so`

`\*.dylib`
```

y no hay ninguno en el archivo.

La suite hace:

```
`assert os.path.exists(CPP\_DLL\_PATH)`

`assert os.path.exists(RUST\_DLL\_PATH)`
```

Por tanto, ejecutarla con el material tal como fue entregado falla **antes de comenzar los tests**.

Sin embargo:

```
`05\_LOG\_RAW\_TESTS.txt`

`05\_LOGS\_Y\_CERTIFICACIONES\_TESTS.md`
```

afirman:

```
`7/7 TESTS PASS`

`EXIT CODE 0`
```

### Esto no demuestra que el log sea falso.

Pero sí demuestra algo más preciso:

> **el log no es reproducible a partir del paquete actual.**

Ese punto por sí mismo impide utilizar esos “7/7” como evidencia final de certificación del artefacto recibido.


## 39. La suite misma contiene una falsa sensación de ABI correcto

La prueba carga:

```
`ctypes.CDLL(...)`
```

pero construye layouts manualmente.

Eso es exactamente el lugar donde el sistema ya tiene inconsistencias.

### Corrección

El test de ABI debe existir **antes** de cualquier test funcional.

Primero:

```
`sizeof`

`alignof`

`offsetof`

`calling convention`

`symbol names`

`struct version`
```

Después:

```
`functional tests`
```


## 40. La prueba cuántica contiene una discrepancia conceptual

La suite llama:

```
`Clifford+T R\_y(pi/4)`
```

pero para `target\_axis == 1` el código genera:

```
`H T H`
```

Ese patrón corresponde a una conjugación de una rotación alrededor de **X**, no una implementación validada de Ry(π/4)R\_y(\\pi/4).

Al evaluar la matriz resultante:

```
`error frente a Rx(pi/4) ≈ 3.7e-16`

`error frente a Ry(pi/4) ≈ 7.65e-1`
```

### Corrección

O bien:

```
`target\_axis == X`
```

o implementar/sintetizar explícitamente:

Ry(θ)R\_y(\\theta) 

y verificar:

∥Ugenerated−Utarget∥≤ϵ\\|U\_\{\\text\{generated\}\}-U\_\{\\text\{target\}\}\\| \\le\\epsilon 

con equivalencia global de fase correctamente tratada.


# Otro problema teórico: la tesis “1D JSON destruye la geometría” está demasiado fuerte

Aquí también hay que atacar el problema conceptual, no sólo el código.

La DPI establece que para un procesamiento determinista:

I(X;g(Y))≤I(X;Y)I(X;g(Y)) \\le I(X;Y) 

pero eso **no implica** que “serializar un tensor como una secuencia 1D destruya su geometría”.

Una serialización puede ser completamente reversible:

```
`tensor multidimensional`

`        ↓`

`bytes`

`        ↓`

`tensor idéntico`
```

No se ha perdido necesariamente información.

Lo que sí puede destruir propiedades geométricas o información es:

```
`quantization`

`truncation`

`projection`

`lossy encoding`

`tokenization semántica`

`normalization incorrecta`
```

### Corrección

No justificar Morpho con:

> “1D = pérdida de geometría”.

Justificarlo con propiedades verificables:

```
`zero-copy`

`lossless`

`dtype exacto`

`shape exacto`

`stride exacto`

`alignment`

`ownership`

`lifetime`
```

Eso es mucho más sólido.


# Y otro problema con “O(1) transfer”

Pasar:

```
`SLAB\_ID`

`offset`

`length`

`tag`
```

puede ser O(1).

Pero eso no significa que:

```
`consumir el tensor de D elementos`
```

sea O(1).

La ventaja correcta sería:

O(1)O(1) 

para **publicar/transferir el descriptor**, evitando copiar los DD datos.

Después, leer/procesar el tensor sigue dependiendo de DD.

Además, el código V808 mostrado no contiene un descriptor completo:

```
`dtype`

`shape`

`stride`

`element count`

`byte size`

`owner`

`generation`

`CRC/version`
```

y no implementa por sí mismo un sistema completo de mmap/SHM de extremo a extremo.


# El arreglo estructural que yo impondría

No intentaría parchear estos defectos uno por uno.

Haría una V809 con cinco capas explícitas:

```
`                    ┌─────────────────────────┐`

`                    │     C ABI v9/809        │`

`                    │ opaque handles + DTOs   │`

`                    └────────────┬────────────┘`

`                                 │`

`             ┌───────────────────┼──────────────────┐`

`             ▼                   ▼                  ▼`

`          C++ core             Rust core          Python`

`             │                   │                  │`

`             └──────────────┬────┴──────────────────┘`

`                            ▼`

`                  Checked FFI boundary`

`                            │`

`             ┌──────────────┼──────────────┐`

`             ▼              ▼              ▼`

`          Memory          Numerics       Geometry`

`          safety         + FP contract   + topology`
```

## Contrato FFI

Todas las funciones deben validar:

```
`null`

`capacity`

`alignment`

`integer overflow`

`finite values`

`dimension bounds`

`ownership`

`generation`

`ABI version`
```

## Contrato matemático

Separar formalmente:

```
`sphere S^(D-1)`

`Stiefel St(D,K)`

`ambient Euclidean space`

`threshold graph`

`topological complex`
```

No mezclarlos bajo la etiqueta “manifold”.

## Contrato numérico

Definir qué significa exactamente:

```
`error \<= 4.44e-16`
```

y con qué tipo.

Ese bound no se puede reclamar alegremente desde una ruta que termina en `float`. El `stiefel\_math\_v808.cpp` trabaja con entrada/salida `float`; esa sola decisión ya hace incompatible un claim de precisión del orden de doble precisión para el resultado final.


# Orden de reparación que considero obligatorio

### BLOQUEADOR 1 — ABI

Primero corregir:

```
`C11/C23 alignment`

`Ring layout`

`Rust result layout`

`Python bindings`

`version handshake`

`opaque handles`
```

Hasta que esto no esté arreglado, cualquier benchmark o test funcional tiene valor limitado.

### BLOQUEADOR 2 — PMTP

Corregir:

```
`FREE -\> RESERVED -\> ACTIVE`

`reader metadata publication`

`writer timeout`

`writer authorization`

`orphan writer recovery`

`PID identity`

`destroy/quiescence`
```

El escritor **nunca** puede obtener `OK` mientras aún existan lectores incompatibles.

### BLOQUEADOR 3 — Stiefel

Reemplazar:

```
`"regularización =\> todo bien"`
```

por:

```
`finite input`

`↓`

`rank analysis`

`↓`

`stable QR`

`↓`

`orthogonality verification`

`↓`

`REGULARIZED / RANK\_DEFICIENT / OK`
```

Un punto degenerado no debe certificarse como Stiefel.

### BLOQUEADOR 4 — Fréchet/BFT

Eliminar de la ruta de certificación:

```
`if variance \< 1e-6 \{`

`    certified = true;`

`\}`
```

y sustituir el algoritmo por uno que tenga una especificación matemática clara en la esfera.

### BLOQUEADOR 5 — validación adversarial

Agregar obligatoriamente:

```
`NaN`

`+Inf`

`-Inf`

`zero vectors`

`non-unit vectors`

`duplicate vectors`

`rank deficiency`

`one-node swarm`

`bridge attack`

`Sybil-like attack`

`all-outlier attack`

`antipodal points`

`near-antipodal points`

`capacity underflow`

`capacity overflow`

`concurrent destruction`

`concurrent retain/release`

`dead writer`

`PID reuse`

`wrong ABI layout`

`wrong struct size`

`wrong version`
```


# Resultado de este asedio

No encontré un único “bug raro”. Encontré **fallos de varias clases que se refuerzan entre sí**:

| **Área** | **Estado encontrado** |
| :-: | :-: |
| ABI C11 | **FALLA** |
| ABI Ring C++/Python | **FALLA CRÍTICA** |
| ABI Rust/Python | **FALLA CRÍTICA** |
| SPSC lifetime | **NO SEGURO** |
| Refcount ABI | **NO SEGURO** |
| PMTP reader publication | **CARRERA REAL** |
| PMTP writer exclusion | **FALLA CRÍTICA** |
| PID identity | **INSUFICIENTE** |
| Tikhonov → Stiefel | **NO GARANTIZADO** |
| NaN containment | **FALLA** |
| FTZ/DAZ contract | **NO IMPLEMENTADO** |
| Two-pass invariant | **NO IMPLEMENTADO COMO SE DECLARA** |
| Sphere intrinsic geometry | **NO IMPLEMENTADA EN FRECHET** |
| Zero-variance certification | **FALSO POSITIVO** |
| Bridge/BFT attack | **DERROTADO** |
| FFI capacity validation | **INSUFICIENTE** |
| Reproducibilidad del paquete | **NO DEMOSTRADA** |
| Quantum `Ry` test | **INCONSISTENTE** |

## La corrección más importante

El cambio conceptual que más protege al arquitecto es éste:

> **No permitir que “OK”, “certified” o “invariant preserved” signifiquen simplemente que el algoritmo llegó al final sin crashear.**

Cada certificado debe venir acompañado de una demostración computacional de sus precondiciones:

```
`FINITE`

`+ VALID MEMORY`

`+ CORRECT ABI`

`+ VALID GEOMETRY`

`+ VALID DIMENSIONS`

`+ NUMERICAL RESIDUAL WITHIN BOUND`

`+ CONSISTENT OWNERSHIP`

`+ ADVERSARIAL CONDITION SATISFIED`

`= CERTIFIABLE`
```

En el estado actual, varias capas devuelven `OK` sin que esas precondiciones estén demostradas.

**Por tanto, cierro este tramo del bulldog con “NO CERTIFICAR”, no con “7/7 PASS”.** El siguiente asedio lógico debe centrarse en el rediseño verificable del **ABI/PMTP + Cholesky/QR + certificador esférico**, porque ésos son los puntos donde un parche superficial volvería a crear una falsa sensación de cierre.

