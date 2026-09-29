<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

## Evaluación general

La arquitectura propuesta es razonable, pero las tres afirmaciones necesitan matices importantes. El mayor riesgo no es solamente “desalinear memoria”: es que el contrato FFI no esté formalmente definido, que los errores/pánicos crucen la frontera de forma incorrecta y que el modelo de concurrencia de QSBR no tenga una semántica de memoria verificable.

Mi evaluación:


| Área | Evaluación | Riesgo |
| :-- | :-- | --: |
| Layout C++/Rust | Correcto como preocupación, incompleto como diagnóstico | Crítico |
| Pánico Rust en FFI | Correcto en esencia, pero `catch_unwind` no basta por sí solo | Crítico |
| False sharing en QSBR | Plausible y frecuente, pero depende del patrón de acceso | Medio-alto |
| `ctypes`/GIL | La descripción es demasiado simplificada | Alto |
| `v816_error_t` como firewall | Buena idea, si es realmente POD, versionado y validado | Bajo-medio |

## 1. Layout y padding de structs

La afirmación es correcta: `alignas(128)` en C++ y `#[repr(C, align(128))]` en Rust no garantizan por sí mismos que todos los campos tengan el mismo layout. Garantizan, principalmente, una alineación mínima del tipo; no garantizan que los tipos semánticamente equivalentes ocupen el mismo tamaño ni que los enums tengan la misma representación.

El caso del enum es especialmente importante:

```cpp
enum class error_kind : std::int32_t {
    none = 0,
    invalid_argument = 1
};

struct alignas(128) v816_error_t {
    std::int32_t code;
    error_kind kind;
    std::uint64_t detail;
};
```

La contraparte Rust debería fijar explícitamente la representación:

```rust
#[repr(i32)]
#[derive(Copy, Clone)]
pub enum ErrorKind {
    None = 0,
    InvalidArgument = 1,
}

#[repr(C, align(128))]
pub struct V816Error {
    pub code: i32,
    pub kind: ErrorKind,
    pub detail: u64,
}
```

Sin `#[repr(i32)]`, el enum Rust no debe considerarse parte de un ABI C estable. La recomendación más robusta es no exponer enums directamente en structs FFI. Usar enteros con constantes reduce el número de supuestos:

```rust
#[repr(C, align(128))]
pub struct V816Error {
    pub abi_version: u32,
    pub size: u32,
    pub code: i32,
    pub kind: i32,
    pub detail: u64,
}
```


### Mejora esencial: contrato verificable

El layout debe comprobarse en ambos lados durante compilación o en una prueba ABI.

En C++:

```cpp
static_assert(alignof(v816_error_t) == 128);
static_assert(sizeof(v816_error_t) % 128 == 0);
static_assert(offsetof(v816_error_t, code) == 0);
static_assert(offsetof(v816_error_t, kind) == 4);
static_assert(offsetof(v816_error_t, detail) == 8);
```

En Rust:

```rust
const _: () = assert!(std::mem::align_of::<V816Error>() == 128);
const _: () = assert!(std::mem::size_of::<V816Error>() % 128 == 0);
```

Para offsets, conviene usar una herramienta específica como `memoffset` o generar un archivo de descripción del ABI desde una sola fuente de verdad. No es suficiente revisar visualmente las declaraciones.

La documentación de C++ confirma que `alignas` controla la alineación, pero la compatibilidad FFI requiere verificar también tamaño, offsets, tipos y reglas de padding.[^1_1]

### Corrección sobre “corrupción silenciosa”

La corrupción silenciosa es posible, pero no debe afirmarse que ocurrirá simplemente porque “el orden o tamaño difiere”. El resultado depende de cómo se use el struct:

- Si Rust escribe según offsets diferentes y C++ lee el mismo bloque, puede haber corrupción.
- Si el objeto se pasa por valor, una diferencia de tamaño o alineación puede romper la llamada ABI.
- Si se pasa por puntero, puede producirse lectura incorrecta sin SIGSEGV.
- Si se accede fuera del bloque asignado, sí puede producirse un fallo inmediato, aunque no está garantizado.

La mejora principal es prohibir el paso de structs complejos por valor. Usar punteros a structs C ABI, tamaño explícito y capacidad explícita:

```c
typedef struct alignas(128) {
    uint32_t abi_version;
    uint32_t size;
    int32_t  code;
    int32_t  kind;
    uint64_t detail;
} v816_error_t;

int v816_run(
    const void* input,
    size_t input_len,
    void* output,
    size_t output_len,
    v816_error_t* error
);
```

También deben definirse:

- endianness;
- propiedad y duración de cada puntero;
- posibilidad de aliasing;
- nulabilidad;
- quién reserva y libera memoria;
- si los buffers pueden modificarse;
- número máximo de elementos;
- comportamiento ante tamaños inválidos.


## 2. Pánicos de Rust a través de FFI

La afirmación central es correcta, pero requiere precisión. Un `panic!` que escape de una función `extern "C"` no debe cruzar una frontera C normal. En las configuraciones habituales, Rust aborta cuando un pánico intenta escapar por esa ABI; no se debe depender de ese comportamiento como mecanismo de recuperación. La documentación oficial recomienda capturar el pánico dentro de Rust cuando la función puede ser llamada desde código extranjero.[^1_2][^1_3]

Un wrapper mínimo sería:

```rust
#[no_mangle]
pub extern "C" fn v816_run(
    input: *const u8,
    input_len: usize,
    output: *mut u8,
    output_len: usize,
    error: *mut V816Error,
) -> i32 {
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        run_inner(input, input_len, output, output_len, error)
    }));

    match result {
        Ok(code) => code,
        Err(_) => {
            write_error(error, ERROR_PANIC);
            ERROR_PANIC
        }
    }
}
```

Pero hay cuatro problemas frecuentes:

### `catch_unwind` no captura todo

No captura:

- aborts explícitos;
- procesos terminados por `abort`;
- pánicos compilados con `panic=abort`;
- errores de memoria;
- violaciones de invariantes de `unsafe`;
- comportamiento indefinido;
- algunos fallos provenientes de bibliotecas nativas.

La propia documentación aclara que `catch_unwind` captura pánicos con unwinding, no procesos abortados.[^1_3]

### `AssertUnwindSafe` no hace seguro el código

`AssertUnwindSafe` solo declara que el programador acepta la frontera de seguridad de unwind. No convierte referencias mutables, estado global, locks ni invariantes parcialmente actualizados en estructuras seguras.

Por eso, el kernel interno debería diseñarse para que un pánico no deje estado observable en una situación inválida:

1. validar todos los punteros y tamaños antes de modificar salida;
2. calcular en buffers temporales;
3. publicar resultados solo al final;
4. convertir errores previsibles en `Result`;
5. evitar mantener locks o guardas complejas durante operaciones que puedan entrar en código desconocido.

### No propagar mensajes de pánico como punteros Rust

No debe devolverse un `String`, `Box<dyn Any>`, `&str` ni un puntero a memoria administrada por Rust sin una función explícita de liberación. El firewall debería contener solamente códigos y datos ABI-estables:

```c
enum {
    V816_OK = 0,
    V816_INVALID_ARGUMENT = 1,
    V816_PANIC = 2,
    V816_INTERNAL_ERROR = 3
};
```


### `C-unwind` no es una solución general

`extern "C-unwind"` es apropiado cuando se ha diseñado deliberadamente una frontera que permite unwinding entre lenguajes compatibles. No debería utilizarse para dejar que un pánico llegue hasta Python. La especificación de Rust advierte que cruzar una frontera con la ABI equivocada puede producir comportamiento indefinido.[^1_4][^1_5]

Para Python, la política más segura es:

```text
Python → C ABI noexcept → Rust catch_unwind → código de error
```

Y, separadamente:

```text
C++ exceptions → catch (...) → código de error
```

Nunca conviene permitir que excepciones C++ o pánicos Rust lleguen a `ctypes`.

## 3. Python, `ctypes` y GIL

La capa mostrada como:

```text
Python ctypes / GIL
        ↓
paso por valor / punteros crudos
```

es demasiado imprecisa. `ctypes` no elimina automáticamente todos los riesgos de concurrencia ni garantiza que una operación nativa sea segura porque exista el GIL.

En CPython tradicional, el GIL protege el acceso interno a objetos Python, pero una biblioteca nativa puede:

- ejecutar trabajo en otros hilos;
- conservar punteros después del retorno;
- modificar buffers mientras Python los observa;
- liberar el GIL durante una llamada;
- interactuar con OpenMP o con su propio pool de hilos.

Además, las versiones modernas y los builds libres de GIL cambian las garantías. La documentación de Python indica que `ctypes` tiene garantías limitadas de acceso concurrente y que los builds free-threaded requieren considerar la seguridad de los objetos y de las llamadas explícitamente.[^1_6][^1_7][^1_8]

### Recomendación

No expongas objetos Python ni punteros a memoria Python a hilos nativos que sobrevivan a la llamada. Mejor:

```text
Python valida y construye buffers
→ llamada C ABI síncrona
→ C/Rust termina antes de retornar
→ Python recupera código, salida y diagnóstico
```

Si el kernel debe ser asíncrono:

- copia o adquiere explícitamente el buffer;
- conserva una referencia Python mientras sea necesario;
- define una operación `wait/join`;
- impide liberar o redimensionar el buffer mientras está en uso;
- ofrece cancelación y destrucción;
- documenta quién sincroniza la salida.

El paso por valor de structs también debe evitarse desde `ctypes`. Es preferible usar `POINTER`, `c_void_p` o arrays tipados, junto con funciones de creación y destrucción:

```c
v816_context_t* v816_create(void);
void v816_destroy(v816_context_t*);
int v816_run(v816_context_t*, const uint8_t*, size_t, uint8_t*, size_t,
             v816_error_t*);
```


## 4. False sharing en QSBR

La observación es técnicamente válida, pero hay dos correcciones:

1. La línea de caché suele ser de 64 bytes en muchas plataformas, pero no debe asumirse universalmente.
2. La alineación del tipo no siempre garantiza que cada elemento de un array empiece en una línea separada; el tamaño del elemento también debe ser suficientemente grande.

Una estructura correcta debe separar cada contador por al menos una línea de caché:

```cpp
struct alignas(64) thread_epoch_t {
    std::atomic<std::uint64_t> epoch{0};
    std::byte padding[64 - sizeof(std::atomic<std::uint64_t>)];
};

static_assert(sizeof(thread_epoch_t) == 64);
static_assert(alignof(thread_epoch_t) == 64);
```

En Rust:

```rust
#[repr(C, align(64))]
pub struct ThreadEpoch {
    pub epoch: std::sync::atomic::AtomicU64,
    _padding: [u8; 56],
}
```

Sin embargo, `alignas(128)` no resuelve automáticamente el problema. Si el tamaño del elemento es 128, sí se separan los elementos; si solo se alinea una instancia pero los objetos se empaquetan de otro modo, puede persistir la interferencia. La validación debe incluir:

```text
alignof(thread_epoch_t)
sizeof(thread_epoch_t)
offset(epoch)
dirección de cada elemento del array
```


### Más importante que el padding: el algoritmo QSBR

El false sharing puede degradar rendimiento, pero la corrección del algoritmo depende de:

- orden de memoria de las publicaciones;
- entrada y salida de las secciones de lectura;
- tratamiento de hilos inactivos;
- registro y desregistro de hilos;
- reclamación de nodos retirados;
- garantía de que ningún lector conserva un puntero después de anunciar quiescencia;
- progreso si un hilo queda bloqueado indefinidamente.

Por ejemplo, una publicación de época normalmente requiere como mínimo una operación atómica con semántica claramente definida. No es suficiente declarar un `uint64_t` como `volatile`; `volatile` no proporciona sincronización entre hilos.

También conviene medir antes y después:

- throughput del kernel;
- latencia de publicación;
- tráfico de coherencia;
- migración de hilos;
- número de lectores activos;
- tamaño de la cola de objetos pendientes;
- tiempo máximo de reclamación.


## 5. Diseño recomendado del firewall FFI

La frontera debería reducirse a una ABI C muy pequeña y no genérica:

```c
typedef struct {
    uint32_t abi_version;
    uint32_t struct_size;
    int32_t  code;
    int32_t  subsystem;
    uint64_t detail;
} v816_error_t;

int32_t v816_run(
    const uint8_t* input,
    size_t input_len,
    uint8_t* output,
    size_t output_len,
    v816_error_t* error
);
```

Características recomendadas:

- `extern "C"` en Rust y C++;
- funciones `noexcept` en C++;
- `catch (...)` en cada entrada C++;
- `catch_unwind` en cada entrada Rust;
- ningún destructor, excepción, `panic`, `Result` o tipo Rust/C++ cruza la frontera;
- structs con enteros de ancho fijo;
- `abi_version` y `struct_size`;
- validación de punteros, longitudes y alineación;
- funciones explícitas para liberar memoria;
- una política clara de ownership;
- pruebas ABI automatizadas en CI;
- sanitizers: AddressSanitizer, UndefinedBehaviorSanitizer, ThreadSanitizer cuando sean compatibles con el runtime;
- pruebas de estrés con múltiples hilos y builds con distintas optimizaciones.


## Veredicto

Las tres brechas están bien identificadas, pero las mejoras prioritarias son:

1. **Formalizar el ABI**, no solo añadir alineación.
2. **Impedir cualquier unwind hacia Python**, convirtiendo todo en códigos de error.
3. **Separar QSBR por líneas de caché y verificar sus atomics**, no solo añadir padding.
4. **Definir ownership y duración de buffers**, especialmente si OpenMP o hilos Rust continúan trabajando después de la llamada.
5. **Probar el contrato**, incluyendo `sizeof`, `alignof`, offsets, enums, excepciones, pánicos y cargas concurrentes.

La arquitectura puede ser sólida, pero en su forma actual todavía depende de demasiadas suposiciones implícitas sobre ABI, memoria y concurrencia.

<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://learn.microsoft.com/en-us/cpp/cpp/alignment-cpp-declarations?view=msvc-170

[^1_2]: https://doc.rust-lang.org/stable/nomicon/ffi.html

[^1_3]: https://doc.rust-lang.org/std/panic/fn.catch_unwind.html

[^1_4]: https://doc.rust-lang.org/reference/panic.html

[^1_5]: https://rust-lang.github.io/rfcs/2945-c-unwind-abi.html

[^1_6]: https://docs.python.org/3/library/ctypes.html

[^1_7]: https://docs.python.org/3/builtins/threadsafety.html

[^1_8]: https://docs.python.org/3/c-api/threads.html

[^1_9]: https://messervices.cyber.gouv.fr/documents-guides/anssi-guide-programming_rules_to_develop_secure_applications_with_rust-v1.0.pdf

[^1_10]: https://doc.rust-lang.org/nomicon/ffi.html?highlight=panic

[^1_11]: https://doc.rust-lang.org/beta/std/panic/fn.catch_unwind.html

[^1_12]: https://doc.rust-lang.org/nomicon/unwinding.html

[^1_13]: https://blog.rust-lang.org/inside-rust/2020/02/27/ffi-unwind-design-meeting/

[^1_14]: https://learn.microsoft.com/is-is/cpp/cpp/alignment-cpp-declarations?view=msvc-150

[^1_15]: https://en.cppreference.com/c/language/\_Alignas


---

## Idea central

Un *memory layout desync* ocurre cuando C++ y Rust creen que el mismo bloque de bytes tiene estructuras distintas. La incompatibilidad no depende únicamente de `alignas(128)` y `#[repr(C, align(128))]`; depende de cinco propiedades que deben coincidir exactamente:

$$
\text{ABI compatible} =
(\text{tamaño},\ \text{alineación},\ \text{offsets},\ \text{representación},\ \text{convención de llamada})
$$

En Rust, `#[repr(C)]` fija el orden y el algoritmo general de padding como lo haría C, pero no transforma automáticamente todos los tipos Rust en tipos ABI compatibles. La documentación especifica que el layout incluye tamaño, alineación y offsets relativos de campos.[^2_1][^2_2]

## Alineación no es padding

La alineación indica en qué direcciones puede comenzar un objeto. Si un tipo requiere alineación de 16 bytes, su dirección debe ser múltiplo de 16:

```text
0x1000  válido
0x1010  válido
0x1008  inválido
```

El padding son bytes insertados para respetar esa regla. Puede aparecer:

1. entre campos;
2. al final de la estructura;
3. alrededor de elementos de un array.

Ejemplo:

```cpp
struct A {
    std::uint8_t  tag;   // offset 0
    std::uint64_t value; // offset 8
};
```

Un layout típico es:

```text
offset 0: tag       1 byte
offset 1-7: padding 7 bytes
offset 8: value     8 bytes
sizeof(A): 16 bytes
alignof(A): 8 bytes
```

El tamaño final se redondea al múltiplo de la alineación del tipo porque los elementos de un array deben comenzar correctamente alineados. El mismo principio aparece en el algoritmo de layout `repr(C)` de Rust.[^2_1]

## Qué hace realmente `alignas(128)`

Considera:

```cpp
struct alignas(128) V816Error {
    std::int32_t code;
    std::int32_t kind;
    std::uint64_t detail;
};
```

Los campos podrían ocupar solo 16 bytes, pero el tipo completo tendrá:

```text
alignof(V816Error) = 128
sizeof(V816Error)  = 128
```

El padding final ocupa los bytes restantes:

```text
offset 0-3:   code
offset 4-7:   kind
offset 8-15:  detail
offset 16-127: padding final
```

La alineación elevada no cambia necesariamente los offsets internos. Cambia la alineación del objeto y normalmente aumenta su tamaño para que el siguiente elemento de un array también empiece en una dirección múltiplo de 128.

En Rust:

```rust
#[repr(C, align(128))]
pub struct V816Error {
    pub code: i32,
    pub kind: i32,
    pub detail: u64,
}
```

esto no soluciona discrepancias de tipos internos. Si `kind` no tiene la misma representación, el bloque sigue siendo incompatible.

## El error más peligroso: tipos “parecidos”

### Enteros

Nunca uses `int`, `long` o `unsigned long` en una ABI compartida si necesitas portabilidad. Sus tamaños dependen de la plataforma y del ABI.

Usa:


| C++ | Rust |
| :-- | :-- |
| `std::int32_t` | `i32` |
| `std::uint32_t` | `u32` |
| `std::int64_t` | `i64` |
| `std::uint64_t` | `u64` |
| `float` | `f32` |
| `double` | `f64` |
| `std::uint8_t` | `u8` |

En C ABI también puedes utilizar `int32_t`, `uint64_t`, etc.

### Booleanos

No asumas que `bool` de C++, `bool` de Rust y `ctypes.c_bool` forman automáticamente el mismo contrato semántico para estructuras complejas. Para una ABI estable, usa:

```cpp
std::uint8_t enabled;
```

y en Rust:

```rust
pub enabled: u8,
```

con valores documentados `0` y `1`.

### Enums

Este es uno de los puntos más peligrosos:

```cpp
enum class Status : std::int32_t {
    Ok = 0,
    Error = 1
};
```

Debe corresponder a:

```rust
#[repr(i32)]
pub enum Status {
    Ok = 0,
    Error = 1,
}
```

Sin `#[repr(i32)]`, no debes asumir una representación compatible. Incluso con representación fija, es preferible validar los valores al entrar:

```rust
fn valid_status(x: i32) -> bool {
    matches!(x, 0 | 1)
}
```

Para un “firewall” FFI, la alternativa más conservadora es exponer un `i32` y definir constantes, en lugar de exponer un enum:

```c
enum {
    V816_STATUS_OK = 0,
    V816_STATUS_ERROR = 1
};
```


### Punteros y tamaños

Un puntero no debe representarse como un entero fijo:

```cpp
void* data;
```

corresponde normalmente a:

```rust
*mut std::ffi::c_void
```

o a un puntero tipado:

```rust
*const u8
```

Para tamaños y longitudes:

```cpp
std::size_t len;
```

corresponde a:

```rust
usize
```

Pero `usize` solo es adecuado si ambos lados representan una longitud dependiente de la arquitectura. Para formatos persistentes o mensajes serializados, usa un tamaño fijo como `u64`.

### Arrays

Un array C embebido:

```cpp
struct Packet {
    std::uint8_t bytes[^2_32];
};
```

corresponde a:

```rust
#[repr(C)]
struct Packet {
    bytes: [u8; 32],
}
```

No corresponde a `Vec<u8>`, `String`, `Box<[u8]>` ni `&[u8]`. Esos tipos contienen punteros, tamaños y capacidades administrados por Rust, y no tienen layout C directo.

## `repr(C)` no significa “todo es seguro”

`#[repr(C)]` aporta garantías de layout para una estructura equivalente a C, pero no arregla:

- punteros inválidos;
- aliasing incorrecto;
- ownership;
- lifetime;
- tamaños incorrectos;
- enums inválidos;
- uniones mal interpretadas;
- datos no inicializados;
- carreras de datos.

Ejemplo peligroso:

```rust
#[repr(C)]
pub struct Buffer {
    pub ptr: *mut u8,
    pub len: usize,
}
```

El layout puede ser compatible, pero el contrato todavía debe responder:

- ¿puede `ptr` ser nulo?
- ¿quién asignó la memoria?
- ¿quién la libera?
- ¿es legible, escribible o ambas?
- ¿sigue viva durante toda la llamada?
- ¿puede el kernel conservarla después del retorno?
- ¿pueden solaparse input y output?

La compatibilidad de layout no equivale a seguridad de memoria.

## Uniones, campos opcionales y structs complejos

Las uniones merecen un tratamiento especial. Una unión C++ como:

```cpp
union Payload {
    std::uint64_t integer;
    double real;
};
```

no debe exponerse sin un discriminante externo:

```cpp
struct Value {
    std::int32_t kind;
    Payload payload;
};
```

Rust necesita una representación que refleje el contrato exacto:

```rust
#[repr(C)]
pub union Payload {
    pub integer: u64,
    pub real: f64,
}

#[repr(C)]
pub struct Value {
    pub kind: i32,
    pub payload: Payload,
}
```

El código debe leer únicamente el miembro indicado por `kind`. Leer el campo incorrecto puede ser semánticamente inválido aunque el layout sea idéntico.

Para campos opcionales, no uses directamente:

```rust
Option<T>
```

salvo que hayas verificado explícitamente su representación para ese `T`. En una ABI pública es más claro usar:

```c
struct OptionalU64 {
    uint8_t present;
    uint64_t value;
};
```

y reproducir ese layout de forma explícita en Rust.

## `packed` es una falsa solución

A veces se intenta eliminar la incertidumbre mediante:

```cpp
#pragma pack(push, 1)
struct Packed { ... };
#pragma pack(pop)
```

o:

```rust
#[repr(C, packed)]
struct Packed { ... }
```

Esto elimina padding, pero puede crear campos desalineados. En Rust, tomar una referencia normal a un campo desalineado puede ser una operación inválida; en C++ también puede causar penalizaciones, fallos en ciertas arquitecturas o accesos no portables.

`packed` solo debe usarse para formatos binarios concretos y con acceso mediante copias byte a byte o funciones especializadas. No es una buena solución para structs de trabajo compartidos directamente entre C++ y Rust.

## Padding no inicializado

El padding no forma parte necesariamente de los valores lógicos de los campos. Por tanto, comparar o serializar una estructura completa con `memcmp` puede ser incorrecto:

```cpp
if (std::memcmp(&a, &b, sizeof(a)) == 0) { ... }
```

Dos structs pueden tener campos idénticos y padding diferente.

También es peligroso copiar el padding a través de una frontera o incluirlo en un hash. Si necesitas representación determinista:

1. inicializa toda la estructura;
2. escribe campos explícitamente;
3. no uses `memcmp` como igualdad semántica;
4. serializa campo por campo;
5. si el formato lo exige, define padding reservado y ponlo a cero.

Ejemplo:

```cpp
struct alignas(128) V816Error {
    std::uint32_t abi_version;
    std::uint32_t struct_size;
    std::int32_t  code;
    std::int32_t  kind;
    std::uint64_t detail;
    std::uint8_t  reserved[^2_104];
};

static_assert(sizeof(V816Error) == 128);
```

El campo `reserved` convierte parte de lo que sería padding implícito en bytes explícitos y controlables.

## Verificación práctica del layout

### En C++

```cpp
#include <cstddef>
#include <cstdint>
#include <type_traits>

struct alignas(128) V816Error {
    std::uint32_t abi_version;
    std::uint32_t struct_size;
    std::int32_t  code;
    std::int32_t  kind;
    std::uint64_t detail;
    std::uint8_t  reserved[^2_104];
};

static_assert(std::is_standard_layout_v<V816Error>);
static_assert(alignof(V816Error) == 128);
static_assert(sizeof(V816Error) == 128);
static_assert(offsetof(V816Error, abi_version) == 0);
static_assert(offsetof(V816Error, struct_size) == 4);
static_assert(offsetof(V816Error, code) == 8);
static_assert(offsetof(V816Error, kind) == 12);
static_assert(offsetof(V816Error, detail) == 16);
```

`std::is_standard_layout_v` es una comprobación útil, pero no sustituye la validación de offsets.

### En Rust

```rust
use core::mem::{align_of, size_of};

#[repr(C, align(128))]
pub struct V816Error {
    pub abi_version: u32,
    pub struct_size: u32,
    pub code: i32,
    pub kind: i32,
    pub detail: u64,
    pub reserved: [u8; 104],
}

const _: () = assert!(align_of::<V816Error>() == 128);
const _: () = assert!(size_of::<V816Error>() == 128);
```

Para los offsets, usa una macro o una biblioteca de offsets en pruebas. También puedes generar un programa C++ que exporte los offsets y compararlos con los valores esperados durante CI.

### Mejor opción: generación automática

Si C++ es la fuente del header, usa `bindgen` para generar las declaraciones Rust. `bindgen` puede generar pruebas de layout que verifican tamaño, alineación y offsets; su documentación describe este mecanismo y lo habilita por defecto en su configuración habitual.[^2_3][^2_4][^2_5]

La regla práctica es:

```text
Una única definición C ABI
→ header público
→ bindings Rust generados
→ bindings Python derivados del mismo header
```

No mantengas manualmente tres definiciones independientes del mismo struct.

## Prueba ABI en tiempo de ejecución

Además de las comprobaciones de compilación, añade una función de introspección:

```c
uint32_t v816_abi_version(void);
uint32_t v816_error_size(void);
uint32_t v816_error_align(void);
```

Y, si es necesario:

```c
int v816_check_abi(
    uint32_t caller_version,
    uint32_t caller_size,
    uint32_t caller_align
);
```

Python puede consultar la versión y el tamaño antes de invocar operaciones complejas. Esto no sustituye los tests, pero evita que una biblioteca incompatible se use silenciosamente.

## Caso específico: C++ y Rust con alineación 128

Una definición viable sería:

```cpp
struct alignas(128) V816Error {
    std::uint32_t abi_version;  // 0
    std::uint32_t struct_size;  // 4
    std::int32_t  code;         // 8
    std::int32_t  kind;         // 12
    std::uint64_t detail;       // 16
    std::uint8_t  reserved[^2_104];
};
```

```rust
#[repr(C, align(128))]
pub struct V816Error {
    pub abi_version: u32,
    pub struct_size: u32,
    pub code: i32,
    pub kind: i32,
    pub detail: u64,
    pub reserved: [u8; 104],
}
```

Propiedades esperadas:

```text
offset(abi_version) = 0
offset(struct_size) = 4
offset(code)        = 8
offset(kind)        = 12
offset(detail)      = 16
sizeof              = 128
alignof             = 128
```

La gran ventaja de los bytes `reserved` es que el contrato queda explícito. La desventaja es el mayor tamaño de cada elemento. Para errores ocasionales, 128 bytes es irrelevante; para millones de objetos, puede ser un coste considerable de memoria y caché.

## Diagnóstico final

La frase:

> “Si C++ usa `alignas(128)` y Rust usa `#[repr(C, align(128))]`, pero el orden o tamaño difiere, los offsets se desincronizan”

es correcta, pero incompleta. La versión técnicamente precisa sería:

> La alineación del tipo no garantiza por sí sola la compatibilidad ABI. La estructura solo es interoperable si ambos lados coinciden en representación de cada campo, orden, tamaño, alineación, offsets, tamaño total, reglas de paso y contrato de ownership. Cualquier discrepancia puede causar lecturas incorrectas, corrupción, errores de llamada ABI o comportamiento indefinido, incluso sin producir un SIGSEGV.

Para tu diseño, la mejora más importante es reemplazar structs manualmente duplicados por un **contrato C ABI único, con tipos de ancho fijo, versión, tamaño, campos reservados explícitos y pruebas automáticas de `sizeof`, `alignof` y `offsetof`**.

<span style="display:none">[^2_10][^2_11][^2_12][^2_13][^2_14][^2_15][^2_6][^2_7][^2_8][^2_9]</span>

<div align="center">⁂</div>

[^2_1]: https://doc.rust-lang.org/reference/type-layout.html?highlight=repr

[^2_2]: https://doc.rust-lang.org/reference/type-layout.html?highlight=str

[^2_3]: https://rust-lang.github.io/rust-bindgen/tutorial-5.html

[^2_4]: https://docs.rs/bindgen/latest/bindgen/struct.Builder.html

[^2_5]: https://github.com/rust-lang/rust-bindgen/blob/main/book/src/tutorial-4.md

[^2_6]: https://doc.rust-lang.org/beta/reference/type-layout.html

[^2_7]: https://doc.rust-lang.org/nomicon/other-reprs.html

[^2_8]: https://en.cppreference.com/c/language/object

[^2_9]: https://en.cppreference.com/cpp/language/objects

[^2_10]: https://en.cppreference.com/w/cpp/language/object.html

[^2_11]: https://web.mit.edu/rust-lang_v1.25/arch/amd64_ubuntu1404/share/doc/rust/html/nomicon/repr-rust.html

[^2_12]: https://github.com/rust-lang/rust-bindgen/blob/main/CONTRIBUTING.md

[^2_13]: https://docs.rs/bindgen/latest/src/bindgen/ir/layout.rs.html

[^2_14]: https://github.com/rust-lang/rust-bindgen

[^2_15]: https://rustyyellowpages.dev/syntax/attributes/repr.html


---

## Qué significa realmente

Un pánico Rust a través de FFI ocurre cuando una función expuesta a C, C++ o Python provoca `panic!` y el pánico intenta salir de la función exportada. Esa frontera no debe tratarse como una función Rust ordinaria: C no conoce la semántica de `panic`, C++ espera excepciones diferentes y `ctypes` no ofrece un mecanismo para recibir unwinding.

Para una API consumida desde Python, el principio correcto es:

```text
panic interno
→ captura dentro de Rust
→ conversión a código de error C
→ retorno normal a Python
```

No debe llegar ningún pánico, excepción C++ ni objeto Rust hasta `ctypes`.

## `extern "C"` no es recuperación

Una función como esta:

```rust
#[no_mangle]
pub extern "C" fn v816_run() -> i32 {
    risky_operation();
    0
}
```

tiene una ABI C, pero `extern "C"` no convierte automáticamente el pánico en un error recuperable. Es una frontera que no debe permitir unwinding. La documentación del lenguaje clasifica `"C"` como ABI no-unwinding, mientras que `"C-unwind"` pertenece a las ABI que permiten el desenrollado.[^3_1][^3_2]

Con `panic=unwind`, si un pánico intenta atravesar una frontera `"C"`, Rust lo convierte en abort; el comportamiento exacto de los destructores que se ejecutan antes del abort no debe utilizarse como garantía del programa.[^3_1]

Con `panic=abort`, el pánico aborta directamente y `catch_unwind` no puede recuperarlo. La referencia de Rust distingue explícitamente entre ambos modos.[^3_3][^3_1]

Por tanto, esta afirmación necesita precisión:

> “Un pánico no atrapado en `extern "C"` causa inmediatamente `std::process::abort()`”.

La conclusión operativa es correcta —el proceso puede terminar—, pero el mecanismo exacto depende de `panic=unwind`, `panic=abort`, la ABI y la versión/configuración del runtime. No conviene describirlo siempre como una llamada literal a `std::process::abort()`.

## Patrón correcto de entrada

Separa la función FFI pública de la lógica interna:

```rust
#[repr(C)]
pub struct V816Error {
    pub abi_version: u32,
    pub struct_size: u32,
    pub code: i32,
    pub detail: u64,
}

const V816_OK: i32 = 0;
const V816_INVALID_ARGUMENT: i32 = 1;
const V816_PANIC: i32 = 2;
const V816_INTERNAL_ERROR: i32 = 3;

#[no_mangle]
pub unsafe extern "C" fn v816_run(
    input: *const u8,
    input_len: usize,
    output: *mut u8,
    output_len: usize,
    error: *mut V816Error,
) -> i32 {
    let result = std::panic::catch_unwind(
        std::panic::AssertUnwindSafe(|| {
            run_checked(input, input_len, output, output_len, error)
        })
    );

    match result {
        Ok(code) => code,
        Err(_) => {
            write_error(error, V816_PANIC, 0);
            V816_PANIC
        }
    }
}
```

La función `run_checked` debe:

1. validar punteros;
2. validar longitudes;
3. comprobar overflow en cálculos de tamaños;
4. convertir los punteros en slices solo después de validar;
5. ejecutar el kernel;
6. escribir la salida;
7. devolver un código, nunca un pánico deliberado.

Ejemplo conceptual:

```rust
unsafe fn run_checked(
    input: *const u8,
    input_len: usize,
    output: *mut u8,
    output_len: usize,
    error: *mut V816Error,
) -> i32 {
    if input.is_null() || output.is_null() || error.is_null() {
        write_error(error, V816_INVALID_ARGUMENT, 0);
        return V816_INVALID_ARGUMENT;
    }

    let input_slice = std::slice::from_raw_parts(input, input_len);
    let output_slice = std::slice::from_raw_parts_mut(output, output_len);

    match run_inner(input_slice, output_slice) {
        Ok(()) => {
            write_error(error, V816_OK, 0);
            V816_OK
        }
        Err(code) => {
            write_error(error, code, 0);
            code
        }
    }
}
```

Esto requiere que `write_error` también sea segura ante un puntero nulo. En el ejemplo anterior, debe comprobarlo internamente antes de escribir.

## `AssertUnwindSafe` no arregla la seguridad

Este patrón es habitual:

```rust
catch_unwind(AssertUnwindSafe(|| {
    run_inner(...)
}))
```

Pero `AssertUnwindSafe` no prueba que el estado sea seguro. Solo le dice al compilador que aceptas envolver el cierre aunque contenga valores cuya seguridad ante unwind no pueda demostrar automáticamente.

Puede quedar estado inconsistente si el pánico ocurre después de:

```text
1. modificar una estructura global;
2. actualizar parcialmente un contador;
3. adquirir un lock;
4. insertar un nodo en una cola;
5. publicar un puntero;
6. escribir solo parte de la salida.
```

La protección correcta es transaccional en lo posible:

```text
validar → calcular en temporal → verificar → publicar resultado
```

Por ejemplo, evita generar directamente en el buffer que Python proporcionó si el cálculo puede fallar a mitad:

```rust
fn run_inner(input: &[u8], output: &mut [u8]) -> Result<(), i32> {
    let temporary = compute_result(input)?;
    if temporary.len() > output.len() {
        return Err(V816_INVALID_ARGUMENT);
    }

    output[..temporary.len()].copy_from_slice(&temporary);
    Ok(())
}
```

Para buffers grandes, puedes usar doble buffer, regiones reservadas o una fase de commit, según el rendimiento requerido.

## Pánicos de destructores

Un caso menos evidente ocurre en `Drop`. Un pánico durante el desenrollado puede provocar un segundo pánico y terminar en abort.

Ejemplo conceptual:

```rust
struct Guard;

impl Drop for Guard {
    fn drop(&mut self) {
        panic!("panic during cleanup");
    }
}
```

La frontera FFI debe evitar que el cleanup pueda volver a entrar en una ruta de pánico. Recomendaciones:

- no hacer `panic!` en `Drop`;
- no llamar callbacks extranjeros desde `Drop`;
- usar destructores simples y no fallibles;
- no liberar recursos externos con operaciones que puedan lanzar excepciones;
- convertir fallos de cleanup en métricas o errores de estado, no en pánicos.


## Qué ocurre con `Result` y `unwrap`

`Result` es seguro internamente, pero no debe cruzar la frontera:

```rust
fn run_inner(...) -> Result<(), Error>;
```

Eso es correcto dentro de Rust. La función FFI debe convertirlo:

```rust
match run_inner(...) {
    Ok(()) => V816_OK,
    Err(error) => {
        write_error(...);
        error.code()
    }
}
```

En cambio, estas operaciones son peligrosas en código alcanzable desde FFI:

```rust
value.unwrap();
items[index];
slice.get_unchecked(index);
assert!(condition);
unreachable!();
```

No todos los pánicos se pueden eliminar estáticamente, especialmente en kernels complejos. Por eso necesitas dos defensas:

1. evitar pánicos previsibles mediante validación;
2. mantener `catch_unwind` en la entrada pública.

`catch_unwind` es una barrera de último recurso, no una sustitución de validación.

## `catch_unwind` tiene limitaciones

`catch_unwind` captura pánicos basados en unwinding, pero no captura:

- `abort`;
- `std::process::abort`;
- violaciones de memoria;
- comportamiento indefinido;
- corrupción producida por `unsafe`;
- segmentation faults normales;
- terminación externa del proceso;
- pánicos cuando el binario usa `panic=abort`.

La documentación oficial describe `catch_unwind` como una captura de un pánico que realiza unwinding; no convierte fallos de memoria ni aborts en errores recuperables.[^3_4]

Además, un pánico puede contener una carga cuyo destructor también provoque problemas. El wrapper puede reducir el riesgo usando un mensaje simple o ignorando la carga:

```rust
let result = std::panic::catch_unwind(|| {
    run_inner(...)
});
```

No conviene guardar directamente el objeto de pánico en una estructura global ni intentar transportarlo a Python.

## `panic=unwind` frente a `panic=abort`

### `panic=unwind`

Ventajas:

- permite que `catch_unwind` capture pánicos;
- facilita convertir pánicos inesperados en códigos de error;
- permite cleanup normal dentro del límite capturado.

Desventajas:

- añade metadata y coste potencial de unwind;
- no cubre errores de memoria;
- requiere disciplina con destructores y estado parcial.


### `panic=abort`

Ventajas:

- binario más simple;
- menor coste de unwind;
- comportamiento directo ante pánicos.

Desventajas:

- `catch_unwind` no ofrece recuperación;
- un `unwrap` accidental puede matar el proceso Python;
- no es apropiado si el contrato exige convertir pánicos en errores.

Si el objetivo es que Python sobreviva a un pánico inesperado, la biblioteca debe compilarse con una estrategia compatible con unwinding y usar `catch_unwind` en sus entradas. La estrategia exacta debe probarse en el pipeline de build; no basta con asumir que el perfil de Cargo usado en desarrollo también se aplica al artefacto distribuido.

## `extern "C-unwind"`: cuándo sí y cuándo no

`extern "C-unwind"` indica que una frontera permite que el callee haga unwinding. La referencia de Rust lo distingue explícitamente de `"C"`.[^3_2]

Puede ser apropiado para una frontera diseñada específicamente entre Rust y C++ cuando:

- ambos lados soportan unwinding compatible;
- se controla exactamente el compilador y la plataforma;
- se han definido las reglas de excepciones;
- se sabe qué destructores deben ejecutarse;
- se han probado todas las combinaciones de runtime.

No es apropiado como solución para:

```text
Rust → Python ctypes
```

Python no debe recibir un unwind Rust. Tampoco debería utilizarse para “evitar” escribir un wrapper de errores.

La arquitectura recomendada sigue siendo:

```text
Python/ctypes
    ↓ extern "C"
Rust FFI wrapper
    ↓ catch_unwind
Rust inner function
    ↓ Result
código de error + salida
```

Si existe C++:

```text
Python
    ↓
C++ extern "C" noexcept
    ↓ catch (...)
Rust extern "C"
    ↓ catch_unwind
kernel
```

Cada lenguaje captura sus propios mecanismos de fallo antes de cruzar la frontera.

## Excepciones C++ y pánicos Rust juntos

Una función C++ pública no debería dejar salir excepciones:

```cpp
extern "C" int v816_run(...) noexcept {
    try {
        return v816_run_impl(...);
    } catch (const std::bad_alloc&) {
        return V816_OUT_OF_MEMORY;
    } catch (...) {
        return V816_CPP_EXCEPTION;
    }
}
```

Si `v816_run_impl` llama a Rust, Rust también debe capturar sus pánicos. El objetivo es que la función visible para Python tenga esta propiedad:

```text
no excepciones
no pánicos
no callbacks inesperados
solo return code
```

La palabra `noexcept` documenta y refuerza el contrato C++, pero no convierte automáticamente un fallo en un valor. Si se produce una excepción dentro de una función `noexcept`, C++ termina llamando a `std::terminate`. Por eso aún necesitas `try/catch`.

## Callbacks desde Rust

Los callbacks son otra ruta de fuga:

```rust
type Callback = extern "C" fn(*const u8, usize);

fn run(callback: Callback) {
    callback(ptr, len);
}
```

Un callback extranjero puede:

- lanzar una excepción C++;
- reentrar en Python;
- modificar un buffer;
- provocar una condición de carrera;
- almacenar el puntero para uso posterior.

Nunca llames un callback Python desde un hilo Rust sin adquirir correctamente el estado de Python. Para máxima robustez, acumula eventos en Rust y haz que Python los consuma después en el hilo apropiado.

Si el callback puede ser C++, su tipo debe documentar si permite unwind. Una función de callback C normal no debe lanzar excepciones a través de Rust.

## Hilos internos y pánicos

Un `catch_unwind` alrededor de la función principal no captura automáticamente un pánico que ocurre en otro hilo:

```rust
std::thread::spawn(|| {
    panic!("fallo");
});
```

El wrapper FFI puede retornar normalmente mientras el hilo hijo falla, dependiendo de cómo se gestione el `JoinHandle`.

La estrategia correcta es conservar y unir todos los hilos:

```rust
let handle = std::thread::spawn(|| run_worker());

match handle.join() {
    Ok(result) => result,
    Err(_) => Err(V816_PANIC),
}
```

Con OpenMP, el control debe hacerse en la capa C++ y cualquier excepción debe capturarse antes de salir del equipo paralelo. No debe suponerse que un `catch` externo convierte automáticamente un fallo ocurrido dentro de un worker en un estado coherente.

Para kernels Rust y C++ combinados:

```text
worker panic/exception
→ registrar fallo atómico
→ detener o cancelar el trabajo
→ join de todos los workers
→ convertir a código de error
```

No publiques resultados parciales como si fueran válidos.

## Errores de memoria disfrazados de pánico

Un pánico atrapable no significa que el proceso esté sano. Por ejemplo:

```rust
let index = attacker_controlled_value;
let x = slice[index]; // panic atrapable si index está fuera de rango
```

Eso es relativamente manejable. Pero:

```rust
let x = *raw_ptr.add(index); // unsafe
```

puede leer memoria inválida y causar comportamiento indefinido, no un pánico atrapable.

Por eso la secuencia correcta es:

```text
puntero extranjero
→ validar null
→ validar longitud
→ validar overflow
→ crear slice válido
→ usar índices comprobados
→ ejecutar unsafe mínimo
```

Nunca uses `catch_unwind` como sustituto de AddressSanitizer, Miri en componentes aplicables, revisión de `unsafe` o ThreadSanitizer.

## Contrato de errores recomendado

Usa códigos estables y separa categorías:

```c
enum {
    V816_OK = 0,
    V816_INVALID_ARGUMENT = 1,
    V816_BUFFER_TOO_SMALL = 2,
    V816_OUT_OF_MEMORY = 3,
    V816_CPP_EXCEPTION = 100,
    V816_RUST_PANIC = 101,
    V816_WORKER_FAILURE = 102,
    V816_INTERNAL_ERROR = 103
};
```

El struct de error puede contener:

```c
typedef struct {
    uint32_t abi_version;
    uint32_t struct_size;
    int32_t  code;
    int32_t  subsystem;
    uint64_t detail;
} v816_error_t;
```

No pongas en él:

- `std::string`;
- `String`;
- `Box`;
- referencias;
- slices;
- excepciones;
- `Any`;
- punteros a mensajes temporales.

Si deseas un mensaje, expón una segunda función controlada:

```c
size_t v816_error_message(
    int32_t code,
    char* buffer,
    size_t capacity
);
```

Así no transfieres ownership ambiguo.

## Pruebas que realmente necesitas

### Pruebas de pánico

Crea tests que provoquen intencionadamente:

- `panic!` directo;
- `unwrap()` fallido;
- índice fuera de rango;
- pánico en un helper profundo;
- pánico en `Drop`;
- pánico en un hilo worker;
- error durante una operación concurrente.

Verifica que:

```text
la función retorna V816_RUST_PANIC
Python sigue vivo
el buffer de salida no se declara válido
el estado global puede reutilizarse
no quedan locks tomados
todos los workers terminan
```


### Pruebas de excepción C++

Prueba:

- `throw std::runtime_error`;
- `throw std::bad_alloc`;
- excepción desde un worker;
- excepción durante cleanup;
- excepción en callback.

Cada una debe terminar en un código de error, no en una excepción que llegue a Python.

### Configuraciones de build

Prueba como mínimo:

```text
debug + panic=unwind
release + panic=unwind
release + panic=abort
AddressSanitizer
UndefinedBehaviorSanitizer
ThreadSanitizer
```

Si `panic=abort` es una configuración soportada, debes documentar que no ofrece recuperación ante pánicos. Si la seguridad del proceso Python requiere recuperación, no distribuyas esa configuración como artefacto principal.

## Recomendación final

Para tu diseño, la regla más segura es:

```rust
#[no_mangle]
pub unsafe extern "C" fn v816_entry(...) -> i32 {
    match std::panic::catch_unwind(
        std::panic::AssertUnwindSafe(|| v816_entry_inner(...))
    ) {
        Ok(result) => result,
        Err(_) => {
            write_error_code(V816_RUST_PANIC);
            V816_RUST_PANIC
        }
    }
}
```

Pero esta estructura solo es fiable si además:

- el crate se compila con una estrategia que permita capturar pánicos;
- ningún pánico cruza la frontera;
- los hilos se esperan y sus fallos se propagan;
- C++ captura todas sus excepciones;
- los buffers se validan antes de usarse;
- el estado se publica de forma transaccional;
- los destructores no generan pánicos;
- los tests verifican que Python continúa ejecutándose después del fallo.

La mejora conceptual más importante es no pensar en `catch_unwind` como “protección total”. Es únicamente el último cortafuegos contra pánicos Rust basados en unwinding. La seguridad completa requiere combinarlo con validación de `unsafe`, control de hilos, captura de excepciones C++, ownership explícito y una política de errores estable.

<span style="display:none">[^3_10][^3_11][^3_12][^3_13][^3_14][^3_15][^3_5][^3_6][^3_7][^3_8][^3_9]</span>

<div align="center">⁂</div>

[^3_1]: https://doc.rust-lang.org/reference/items/functions.html

[^3_2]: https://doc.rust-lang.org/reference/items/external-blocks.html

[^3_3]: https://doc.rust-lang.org/beta/reference/panic.html

[^3_4]: https://doc.rust-lang.org/std/panic/fn.catch_unwind.html

[^3_5]: https://doc.rust-lang.org/beta/reference/items/functions.html

[^3_6]: https://doc.rust-lang.org/reference/items/functions.html?highlight=target\_

[^3_7]: https://doc.rust-lang.org/src/std/panic.rs.html

[^3_8]: https://doc.rust-lang.org/reference/linkage.html

[^3_9]: https://doc.rust-lang.org/src/core/panic.rs.html

[^3_10]: https://doc.rust-lang.org/beta/reference/items/external-blocks.html

[^3_11]: https://doc.rust-lang.org/rustc/lints/listing/allowed-by-default.html

[^3_12]: https://doc.rust-lang.org/nightly/reference/items/external-blocks.html

[^3_13]: https://doc.rust-lang.org/stable/rustc/lints/listing/allowed-by-default.html?highlight=abi

[^3_14]: https://doc.rust-lang.org/reference/panic.html

[^3_15]: https://doc.rust-lang.org/nomicon/ffi.html?highlight=panic

