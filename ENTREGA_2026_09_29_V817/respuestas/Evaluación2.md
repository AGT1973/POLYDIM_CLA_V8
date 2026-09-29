<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

## Evaluación

El bug está **bien orientado**, pero la explicación actual mezcla dos problemas distintos:

1. **Alineación del puntero** para usar cargas SIMD alineadas.
2. **Validez y seguridad de deserializar bytes de red como `f64`**, que no se resuelve únicamente reservando memoria alineada.

La afirmación “un casting directo a `*const f64` provoca necesariamente un `#GP` o segfault por desalineación” es demasiado categórica. En AVX/AVX2 existen cargas no alineadas, como `_mm256_loadu_pd`; sin embargo, `_mm256_load_pd` requiere una dirección alineada a 32 bytes, y `_mm512_load_pd` requiere una dirección alineada a 64 bytes según la documentación de Intel. AVX también permite muchas operaciones sobre direcciones no alineadas, aunque pueden tener una penalización de rendimiento; el fallo depende de la instrucción concreta, del acceso y de la arquitectura.[^1_1][^1_2][^1_3]

## Problemas de la solución V900

La solución propuesta —usar `posix_memalign` o `_aligned_malloc` con alineación de 64 bytes— puede ser válida para el **buffer de trabajo del kernel SIMD**, pero no garantiza por sí sola que el diseño sea correcto.

### 1. El buffer de red no debe tratarse como `f64` directamente

Los bytes recibidos por red son una secuencia de bytes, no necesariamente un arreglo válido de `f64`. El código debe verificar como mínimo:

- Que la longitud sea múltiplo de `sizeof(double)`.
- Que la cantidad de elementos esté dentro de los límites esperados.
- Que el formato de punto flotante sea el acordado.
- Que el endianness de la red y el de la máquina coincidan o se conviertan explícitamente.
- Que no existan valores inválidos, como `NaN` o infinitos, si el protocolo no los permite.
- Que el buffer no se lea más allá del tamaño recibido.

Además, en C/C++, un `reinterpret_cast<double*>` sobre bytes arbitrarios puede generar problemas de aliasing, lifetime u objeto mal formado. En Rust, convertir bytes externos directamente a `*const f64` también requiere validaciones de alineación, longitud, inicialización y representación.

### 2. Alinear a 64 bytes no siempre es necesario

La alineación necesaria depende de la carga utilizada:


| Kernel | Carga | Alineación exigida |
| :-- | :-- | --: |
| AVX2 | `_mm256_load_pd` | 32 bytes |
| AVX2 | `_mm256_loadu_pd` | No requiere 32 bytes |
| AVX-512 | `_mm512_load_pd` | 64 bytes |
| AVX-512 | `_mm512_loadu_pd` | No requiere 64 bytes |

La alineación de 64 bytes es una política conservadora y puede simplificar un allocator común para AVX2 y AVX-512, pero no debe presentarse como requisito universal. La documentación de `posix_memalign` exige que la alineación sea potencia de dos y múltiplo de `sizeof(void*)`; 64 bytes satisface esas condiciones en plataformas habituales.[^1_4]

### 3. La alineación del inicio no garantiza la de todos los accesos

Aunque el puntero base esté alineado, una dirección derivada puede dejar de estarlo:

```text
base + offset
```

Si `offset` no es múltiplo de 32 para AVX2 o de 64 para AVX-512, una carga alineada puede seguir siendo inválida. Esto también aplica a subarrays, slices, cabeceras antepuestas y estructuras con padding.

## Solución recomendada

La corrección debería dividirse en dos etapas:

### Etapa A: deserialización segura

Recibir los bytes en un buffer normal y convertirlos explícitamente a valores `f64`.

Pseudocódigo conceptual:

```text
if bytes.len() % 8 != 0:
    rechazar_paquete()

for cada bloque de 8 bytes:
    bits = leer_u64_en_endian_de_red(bloque)
    value = reinterpretar_bits_como_f64(bits)

    if protocolo_no_permite_nan_inf and !is_finite(value):
        rechazar_paquete()

    guardar value
```

En Rust, una alternativa clara es usar `chunks_exact(8)`, `from_be_bytes` o `from_le_bytes` según el protocolo, y `f64::from_bits`. Así se evita depender de que el buffer de red esté alineado.

### Etapa B: copiar al buffer SIMD

Una vez validados los valores, copiarlos a un buffer cuya alineación sea conocida:

```text
allocate buffer with 64-byte alignment
copy validated f64 values into it
invoke AVX-512 aligned kernel only if:
    CPU supports AVX-512
    base pointer is 64-byte aligned
    every accessed offset preserves 64-byte alignment
otherwise:
    use unaligned kernel or scalar fallback
```

En POSIX, `posix_memalign(&ptr, 64, size)` es apropiado; el resultado debe comprobarse y liberarse con `free`. En Windows, `_aligned_malloc(size, 64)` debe emparejarse con `_aligned_free`, no con `free`.

## Corrección propuesta del texto

Una formulación más precisa sería:

> **Bug 2: Riesgo de cargas SIMD alineadas sobre datos deserializados**
>
> Al convertir directamente bytes recibidos por red a `*const f64` y utilizar cargas alineadas como `_mm256_load_pd` o `_mm512_load_pd`, el código puede acceder a una dirección que no cumple la alineación requerida por la instrucción. `_mm256_load_pd` requiere alineación de 32 bytes y `_mm512_load_pd` de 64 bytes; una violación puede producir una excepción de protección general o un fallo de memoria, según la instrucción y la plataforma.[^1_2][^1_1]
>
> El problema también incluye riesgos de longitud, endianness, representación de `f64`, inicialización y límites del buffer. Por tanto, no se debe interpretar el buffer de red directamente como un arreglo SIMD.
>
> **Solución V900 revisada:** validar y deserializar los bytes de forma explícita, copiar los valores válidos a un buffer de trabajo alineado a 64 bytes mediante `posix_memalign` o `_aligned_malloc`, y utilizar cargas alineadas únicamente cuando la alineación del puntero y de todos los offsets esté garantizada. En caso contrario, utilizar `_mm256_loadu_pd`, `_mm512_loadu_pd` o una ruta escalar. La implementación debe incluir detección de capacidades SIMD y una ruta de fallback.

## Pruebas necesarias

Para cerrar el bug, añadiría estas pruebas:

- Buffer base alineado a 32 bytes con `_mm256_load_pd`.
- Buffer base alineado a 64 bytes con `_mm512_load_pd`.
- Buffer deliberadamente desalineado usando cargas `loadu`.
- Offset desalineado dentro de un buffer correctamente alineado.
- Paquete con longitud no divisible por 8.
- Paquete con endianess incorrecto.
- Paquete truncado o con tamaño excesivo.
- Valores `NaN` e infinitos, si el protocolo los restringe.
- Ejecución en CPU sin AVX2 o sin AVX-512.
- Sanitizers: AddressSanitizer, UndefinedBehaviorSanitizer y, si aplica, MemorySanitizer.
- Prueba bajo Valgrind o equivalente para detectar lecturas fuera de límites.

La mejora principal es cambiar el alcance de V900: **la memoria alineada es necesaria para ciertos kernels SIMD, pero no sustituye la deserialización segura ni la validación del protocolo**.

<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_5][^1_6][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://www.physics.ntua.gr/~konstant/HetCluster/intel12.1/compiler_c/main_cls/intref_cls/common/intref_bk_load_ops.htm

[^1_2]: http://portal.nacad.ufrj.br/online/intel/compiler_c/common/core/GUID-4B67D7A0-E1BE-411E-9833-557D14632A12.htm

[^1_3]: https://hpc.llnl.gov/sites/default/files/intelAVXintro.pdf

[^1_4]: https://pubs.opengroup.org/onlinepubs/9799919799/functions/posix_memalign.html

[^1_5]: https://pubs.opengroup.org/onlinepubs/9699919799/functions/posix_memalign.html

[^1_6]: https://www.intel.com/content/www/us/en/docs/cpp-compiler/developer-guide-reference/2021-8/mm256-stream-load-si256.html

[^1_7]: https://learn.microsoft.com/hu-hu/dotnet/api/system.runtime.intrinsics.x86.avx?view=net-10.0

[^1_8]: https://man.archlinux.org/man/posix_memalign.3

[^1_9]: https://manpages.ubuntu.com/manpages/lunar/man3/posix_memalign.3.html

[^1_10]: https://manpages.ubuntu.com/manpages/bionic/en/man3/aligned_alloc.3.html

[^1_11]: https://learn.microsoft.com/ca-es/dotnet/api/system.runtime.intrinsics.x86.avx.loadalignedvector256?view=net-9.0

[^1_12]: https://acl.inf.ethz.ch/teaching/fastcode/2020/slides/07-simd-avx.pdf

[^1_13]: https://kalk.dev/doc/api/intel/avx/

[^1_14]: https://acl.inf.ethz.ch/teaching/fastcode/2021/slides/07-simd-avx.pdf

[^1_15]: https://acl.inf.ethz.ch/teaching/fastcode/2022/slides/07-simd-avx.pdf


---

## Respuesta corta

**No exactamente.** La solución que te propuse es técnicamente más segura que la V900 original, pero “reservar el buffer de red con alineación de 64 bytes” **no es la mejor solución general**. La solución SOTA y más defendible es:

1. tratar la entrada de red como bytes;
2. validar longitud, formato, endianess y límites;
3. deserializar explícitamente a `f64`;
4. usar un buffer de trabajo alineado solo si el kernel requiere cargas alineadas;
5. preferir cargas no alineadas (`loadu`) cuando no exista una garantía real de alineación;
6. seleccionar AVX-512, AVX2 o fallback según las capacidades de la CPU.

Intel recomienda alinear datos al tamaño del vector para obtener mejores resultados con AVX-512, pero eso es una recomendación de rendimiento; no convierte la alineación de 64 bytes en requisito universal para toda la ruta de recepción.[^2_1]

## Qué corregiría de la propuesta anterior

La parte correcta es distinguir entre:

- `_mm256_load_pd`: carga alineada de 256 bits.
- `_mm256_loadu_pd`: carga no alineada de 256 bits.
- `_mm512_load_pd`: carga alineada de 512 bits.
- `_mm512_loadu_pd`: carga no alineada de 512 bits.

La documentación de Intel identifica explícitamente las variantes `load` y `loadu`; la variante `loadu` existe precisamente para acceder a direcciones que no tienen la alineación requerida por la variante alineada.[^2_2][^2_3]

La parte que no debe mantenerse como regla absoluta es:

> “El buffer receptor de red debe asignarse siempre con alineación de 64 bytes.”

Eso puede ser innecesario o incluso contraproducente si:

- el receptor usa un buffer gestionado por el sistema operativo;
- la carga inicial solo necesita copiar bytes;
- el kernel puede usar `loadu`;
- el desplazamiento dentro del buffer rompe la alineación;
- el tamaño de los paquetes no está controlado;
- se usa AVX2, donde el vector tiene 32 bytes;
- el código necesita funcionar en máquinas sin AVX-512.


## Solución SOTA recomendada

### Ruta de recepción

El buffer de red debe permanecer como `uint8_t` o `std::byte`. No debe convertirse directamente mediante un cast y desreferenciarse como `double*`.

Flujo recomendado:

```text
receive bytes
  -> verify packet size and bounds
  -> decode endianness explicitly
  -> reconstruct f64 values
  -> validate numeric/protocol constraints
  -> copy into compute buffer
  -> run selected SIMD kernel
```

Para C/C++, la conversión debe realizarse mediante una operación segura de representación, por ejemplo `memcpy` hacia un `uint64_t` y luego hacia `double`, o mediante una función equivalente bien definida. La desreferenciación directa de un puntero de otro tipo puede violar las reglas de aliasing y producir comportamiento indefinido.[^2_4]

### Ruta de cálculo

Usaría esta política:


| Situación | Implementación |
| :-- | :-- |
| No se garantiza alineación | `_mm256_loadu_pd` o `_mm512_loadu_pd` |
| Buffer de trabajo garantizado a 32 bytes | `_mm256_load_pd` |
| Buffer de trabajo garantizado a 64 bytes | `_mm512_load_pd` |
| CPU sin AVX2 | ruta escalar o SSE compatible |
| CPU con AVX2 pero sin AVX-512 | kernel AVX2 |
| CPU con AVX-512 | kernel AVX-512 |

La asignación alineada con `posix_memalign` o `_aligned_malloc` es recomendable para un **buffer de cómputo dedicado**, no necesariamente para el buffer de recepción. El contrato de propiedad también debe ser explícito: `posix_memalign` se libera con `free`; `_aligned_malloc` se libera con `_aligned_free`.

## Versión final recomendada para el bug

> **Bug 2: Uso de cargas SIMD alineadas sobre datos deserializados**
>
> La ruta de deserialización convierte datos recibidos por red en valores `f64` y posteriormente puede invocar cargas SIMD alineadas sobre direcciones cuya alineación no está garantizada. `_mm256_load_pd` y `_mm512_load_pd` deben utilizarse únicamente cuando la dirección efectiva cumpla la alineación requerida por la implementación. Para buffers sin esa garantía deben utilizarse `_mm256_loadu_pd` o `_mm512_loadu_pd`.[^2_3][^2_2]
>
> El cast directo del buffer de red también omite validaciones de longitud, límites, endianess, representación de `f64` y reglas de aliasing. Por tanto, el buffer de red debe tratarse como bytes y deserializarse explícitamente antes de entrar en el kernel.
>
> **Solución V900 revisada:** validar y deserializar la entrada en un buffer de bytes; convertirla explícitamente a `f64`; copiar los valores validados a un buffer de cómputo alineado cuando se utilicen cargas alineadas; y seleccionar entre kernels AVX-512, AVX2 y fallback según la capacidad de la CPU. Si no puede demostrarse la alineación de cada dirección efectiva, utilizar las variantes `loadu`.
>
> La alineación de 64 bytes puede adoptarse como requisito del buffer de trabajo AVX-512 para facilitar el contrato de implementación y optimizar accesos, pero no debe imponerse al buffer de red ni considerarse una condición suficiente para una deserialización segura. Intel recomienda alinear datos al tamaño del vector para obtener mejores resultados con AVX-512.[^2_1]

## Veredicto

**La mejor solución no es “`posix_memalign(64)` y listo”.** El diseño más robusto es:

- recepción como bytes;
- deserialización explícita;
- validación estricta;
- buffer de cálculo alineado si se usan cargas alineadas;
- `loadu` como opción segura cuando la alineación no está demostrada;
- detección de CPU y fallback.

Así se corrigen tanto el posible fallo SIMD como los problemas independientes de protocolo, memoria y comportamiento indefinido.

<span style="display:none">[^2_10][^2_11][^2_12][^2_13][^2_14][^2_15][^2_5][^2_6][^2_7][^2_8][^2_9]</span>

<div align="center">⁂</div>

[^2_1]: https://cdrdv2-public.intel.com/821613/355308-Optimization-Reference-Manual-050-Changes-Doc.pdf

[^2_2]: https://www.intel.com/content/www/us/en/docs/cpp-compiler/developer-guide-reference/2021-8/load-intrinsics-003.html

[^2_3]: https://learn.microsoft.com/en-za/dotnet/api/system.runtime.intrinsics.x86.avx512f.loadvector512?view=net-10.0

[^2_4]: http://www.man6.org/docs/cppreference-doc/reference/en.cppreference.com/w/c/language/object.html

[^2_5]: https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html

[^2_6]: https://www.intel.com/content/www/us/en/docs/cpp-compiler/developer-guide-reference/2021-9/mm256-set-pd.html

[^2_7]: https://www.intel.com/content/www/us/en/developer/articles/release-notes/intrinsics-guide-release-notes.html

[^2_8]: https://builders.intel.com/docs/networkbuilders/intel-avx-512-instruction-set-for-packet-processing-technology-guide-1645717553.pdf

[^2_9]: https://blog.rwth-aachen.de/hpc_import_20210107/attachments/3474975/3703397.pdf

[^2_10]: https://www.intel.com/content/www/us/en/docs/cpp-compiler/developer-guide-reference/2021-8/mm256-stream-load-si256.html

[^2_11]: https://www.physics.ntua.gr/~konstant/HetCluster/intel12.1/compiler_c/main_cls/intref_cls/common/intref_bk_load_ops.htm

[^2_12]: http://portal.nacad.ufrj.br/online/intel/compiler_c/common/core/GUID-4B67D7A0-E1BE-411E-9833-557D14632A12.htm

[^2_13]: https://kalk.dev/doc/api/intel/avx/

[^2_14]: https://acl.inf.ethz.ch/teaching/fastcode/2022/slides/07-simd-avx.pdf

[^2_15]: https://acl.inf.ethz.ch/teaching/fastcode/2021/slides/07-simd-avx.pdf


---

## Veredicto técnico

La solución SOTA no es imponer `posix_memalign(64)` al buffer de red. La solución robusta es separar:

1. **framing y validación del paquete**;
2. **deserialización explícita**;
3. **buffer de cómputo con contrato de alineación**;
4. **selección del kernel SIMD**;
5. **fallback y pruebas de seguridad**.

Hay una corrección importante: para las versiones alineadas, la especificación de Intel sí establece requisitos estrictos. Una carga EVEX de 512 bits como `VMOVAPD` puede generar `#GP` si la dirección no está alineada a 64 bytes; la versión AVX/256 requiere 32 bytes. Las variantes no alineadas (`VMOVUPD`, implementadas por `loadu`) no exigen esa alineación natural.[^3_1][^3_2]

## Qué era correcto y qué era una alucinación

### Correcto

Es correcto afirmar que:

- `_mm256_load_pd` debe recibir una dirección alineada a 32 bytes.
- `_mm512_load_pd` debe recibir una dirección alineada a 64 bytes.
- una carga alineada sobre una dirección inválida puede causar `#GP`, que normalmente se manifiesta como una señal de fallo de memoria en el proceso.
- `posix_memalign` puede crear un buffer con alineación explícita.
- `loadu` es la alternativa cuando no se puede probar la alineación.

Intel documenta la diferencia entre las cargas alineadas `VMOVAPD` y las no alineadas `VMOVUPD`. La documentación de `posix_memalign` también confirma que devuelve una dirección múltiplo de la alineación solicitada, siempre que esta cumpla las restricciones de la API.[^3_3][^3_4][^3_5]

### Debe matizarse

Estas afirmaciones serían imprecisas:

> “El casting directo siempre provoca un fallo.”

No necesariamente. El cast por sí solo no ejecuta una carga SIMD ni implica automáticamente un fallo. El problema aparece al desreferenciar el puntero bajo requisitos de alineación, tamaño, validez del objeto y límites que no estén garantizados.

> “El buffer de red debe ser de 64 bytes.”

No. El buffer de red puede ser un arreglo de bytes con alineación ordinaria. La alineación especial debe aplicarse al buffer que consume el kernel alineado.

> “Alinear la base a 64 bytes resuelve el problema.”

Solo resuelve la alineación de la base. También deben estar alineados todos los punteros derivados:

```text
effective_address = base + offset
```

Si `offset` no es múltiplo de 64 para AVX-512, la carga puede seguir siendo inválida. También hay que verificar que el rango completo de la carga esté dentro del objeto.

> “Usar `loadu` elimina todo riesgo.”

No. `loadu` evita el requisito de alineación natural, pero no corrige:

- punteros inválidos;
- lecturas fuera de límites;
- paquetes truncados;
- overflow al calcular tamaños;
- datos no inicializados;
- deserialización incorrecta;
- CPU sin la extensión SIMD correspondiente;
- errores de endianness o protocolo.


## Arquitectura recomendada

### 1. Entrada como bytes

La recepción debe usar `uint8_t`, `std::byte` o equivalente:

```cpp
std::vector<std::byte> packet;
```

No debe asumirse que los bytes recibidos:

- empiezan en una dirección de 32 o 64 bytes;
- tienen longitud múltiplo de 8;
- representan directamente objetos `double`;
- usan el endianness nativo;
- contienen únicamente valores numéricos válidos.


### 2. Validación previa

Antes de asignar o procesar, conviene comprobar:

```text
packet_size >= header_size
element_count <= configured_max_elements
payload_size == element_count * 8
element_count * 8 no desborda size_t
payload_size <= packet_size - header_size
```

El cálculo debe hacerse evitando overflow. No hay que calcular primero `element_count * sizeof(double)` y comprobar después si desbordó.

Además, el protocolo debe definir explícitamente:

- endianess;
- codificación de `f64`;
- versión del mensaje;
- cantidad de elementos;
- tamaño máximo;
- tratamiento de `NaN` e infinitos;
- checksum, autenticación o integridad, si corresponde.


### 3. Deserialización explícita

Un patrón portable para una representación IEEE-754 binaria es reconstruir un entero de 64 bits desde los bytes del protocolo y copiar sus bits a `double`. Conceptualmente:

```cpp
uint64_t bits = decode_u64_network_order(payload + i);
double value;
static_assert(sizeof(value) == sizeof(bits));
std::memcpy(&value, &bits, sizeof(value));
```

La interpretación exacta depende del protocolo. No debe afirmarse que el endianness de red es siempre el apropiado para `double`; eso debe estar especificado por el formato.

### 4. Buffer de trabajo

Después de validar y deserializar, hay dos diseños correctos:

#### Diseño A: buffer alineado y cargas alineadas

Adecuado cuando se desea un contrato fuerte de rendimiento:

```text
allocate compute_buffer with 64-byte alignment
copy validated doubles
run AVX-512 aligned kernel
```

En POSIX:

```cpp
void* raw = nullptr;
int rc = posix_memalign(&raw, 64, allocation_size);
if (rc != 0) {
    // tratar error
}
auto* data = static_cast<double*>(raw);

// usar data

std::free(raw);
```

`posix_memalign` requiere que la alineación sea potencia de dos y múltiplo de `sizeof(void*)`; 64 bytes satisface esa condición en los entornos POSIX habituales.[^3_4][^3_5]

En Windows:

```cpp
double* data = static_cast<double*>(_aligned_malloc(bytes, 64));
if (!data) {
    // tratar error
}

// usar data

_aligned_free(data);
```

No se debe liberar memoria de `_aligned_malloc` con `free`.

#### Diseño B: buffer normal y cargas no alineadas

Adecuado si la alineación no está garantizada o si simplifica la implementación:

```cpp
__m256d v = _mm256_loadu_pd(data + i);
```

o:

```cpp
__m512d v = _mm512_loadu_pd(data + i);
```

Esto elimina la precondición de alineación natural, pero sigue exigiendo que `data + i` apunte a al menos 32 o 64 bytes legibles, respectivamente.[^3_2][^3_3]

## Recomendación práctica SOTA

Para una biblioteca o servicio de producción, usaría este contrato:

```text
network buffer:
    byte-addressable
    no SIMD alignment assumption

deserializer:
    bounds checked
    endian explicit
    size checked
    finite/range checks according to protocol

compute buffer:
    owned allocation
    optional 64-byte alignment
    capacity and length tracked separately

kernel dispatch:
    AVX-512 only if CPU support is confirmed
    AVX2 otherwise when supported
    scalar fallback otherwise

SIMD loads:
    aligned loads only under an explicit alignment invariant
    unaligned loads otherwise
```

La alineación debe expresarse como un **invariante verificable**, no como una suposición:

```cpp
assert(reinterpret_cast<std::uintptr_t>(data) % 64 == 0);
assert(i % 8 == 0); // si cada elemento del kernel es un bloque de 8 doubles
```

El `assert` no reemplaza una garantía de diseño en producción, pero ayuda a detectar violaciones durante las pruebas.

## Validación de la afirmación del fallo

La descripción “`#GP / segfault`” debe escribirse con precisión:

- En el nivel de la CPU, una carga alineada que viola su requisito puede producir `#GP`.[^3_1]
- En un proceso de usuario, el sistema operativo puede entregar una señal o excepción equivalente, por ejemplo `SIGSEGV` en Unix.
- El resultado concreto depende del modo de ejecución, sistema operativo, instrucción generada y entorno.
- No debe afirmarse que toda desalineación de cualquier instrucción AVX produce necesariamente un fallo.

Una formulación segura sería:

> “El uso de cargas SIMD alineadas sin demostrar la alineación de la dirección efectiva puede producir una excepción de protección general en las instrucciones que imponen ese requisito; en espacio de usuario, esto puede observarse como un fallo de acceso. Las cargas `loadu` no requieren alineación natural, pero sí requieren una dirección válida y suficiente espacio legible.”

## Pruebas que realmente cerrarían el bug

### Pruebas funcionales

- Paquete vacío.
- Paquete menor que la cabecera.
- Payload truncado.
- Longitud no divisible por 8.
- Cantidad de elementos excesiva.
- Tamaño calculado con overflow.
- Endianness válido e inválido.
- `NaN`, infinito y valores fuera de rango, según contrato.
- Offset de inicio 0, 8, 32 y 64 bytes.
- Longitudes que no son múltiplos del ancho vectorial.


### Pruebas de alineación

- Base alineada a 64 bytes con AVX-512.
- Base alineada a 32 bytes con AVX2.
- Base deliberadamente desalineada con `loadu`.
- Base alineada, pero offset desalineado con `load`.
- Último bloque incompleto.
- Tamaño exactamente igual al requerido por una carga.
- Tamaño menor por un byte.


### Pruebas de plataforma

- CPU con AVX-512.
- CPU con AVX2.
- CPU sin AVX2.
- Ejecución bajo AddressSanitizer y UndefinedBehaviorSanitizer.
- Pruebas con compilaciones que habiliten y deshabiliten vectorización.
- Verificación del dispatch mediante CPUID o la abstracción equivalente.

No conviene ejecutar deliberadamente una carga alineada incorrecta dentro de la suite normal esperando “capturar” el `#GP`; es mejor probar contratos de alineación, usar sanitizers y aislar pruebas de bajo nivel si se necesita confirmar el comportamiento de la instrucción.

## Veredicto final

La corrección de mayor calidad sería reemplazar la V900 original por esto:

> **V900 — Deserialización segura y contrato explícito de alineación SIMD**
>
> Los datos de red se recibirán como bytes y se validarán antes de su interpretación. La conversión a `f64` se realizará explícitamente, respetando el formato y el endianness definidos por el protocolo. Los kernels SIMD no consumirán directamente el buffer de red.
>
> Cuando se utilicen cargas alineadas, los valores se copiarán a un buffer de cómputo cuya alineación y offsets estén garantizados: 32 bytes para AVX2 y 64 bytes para AVX-512. Si esa propiedad no puede demostrarse, se utilizarán cargas no alineadas (`loadu`) o una ruta alternativa. El sistema seleccionará el kernel según las capacidades de la CPU y mantendrá un fallback seguro.
>
> La implementación incluirá validaciones de límites, overflow de tamaños, longitud del payload, representación numérica, capacidad SIMD y pruebas con sanitizers.

**Conclusión técnica:** `posix_memalign(64)` es una pieza válida, pero no es la solución completa ni debe aplicarse obligatoriamente al buffer de red. La solución SOTA es un pipeline de deserialización validada más un contrato explícito entre allocator y kernel SIMD.

<span style="display:none">[^3_10][^3_11][^3_12][^3_13][^3_14][^3_15][^3_6][^3_7][^3_8][^3_9]</span>

<div align="center">⁂</div>

[^3_1]: https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2b-manual.pdf

[^3_2]: https://www.intel.com/content/dam/develop/external/us/en/documents/319433-024-697869.pdf

[^3_3]: https://www.intel.com/content/www/us/en/docs/cpp-compiler/developer-guide-reference/2021-9/intrinsics-for-load-and-store-operations-001.html

[^3_4]: https://www.gnu.org/software/libc/manual/html_node/Aligned-Memory-Blocks.html

[^3_5]: https://manpages.ubuntu.com/manpages/focal/man3/posix_memalign.3.html

[^3_6]: https://www.intel.com/content/www/us/en/docs/cpp-compiler/developer-guide-reference/2021-9/mm256-cvtps-pd.html

[^3_7]: https://www.cs.utexas.edu/~flame/laff/pfhp/week2-summary.html

[^3_8]: https://manpages.ubuntu.com/manpages/bionic/man3/posix_memalign.3.html

[^3_9]: https://www.physics.ntua.gr/~konstant/HetCluster/intel2021.7/HPC/cpp_compiler/cpp_compiler_classic_dev_guide/GUID-0A40CBDD-58FD-4F36-9C6D-F3D2355B5E44.html

[^3_10]: https://www.qnx.com/developers/docs/6.5.0SP1.update/com.qnx.doc.neutrino_lib_ref/p/posix_memalign.html

[^3_11]: http://portal.nacad.ufrj.br/online/intel/compiler_c/common/core/GUID-0A40CBDD-58FD-4F36-9C6D-F3D2355B5E44.htm

[^3_12]: https://www.unix.com/man_page/osx/3/posix_memalign/

[^3_13]: https://www.intel.com/content/www/us/en/docs/cpp-compiler/developer-guide-reference/2021-8/mm256-stream-load-si256.html

[^3_14]: https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html

[^3_15]: https://manpages.ubuntu.com/manpages/lunar/man3/posix_memalign.3.html

