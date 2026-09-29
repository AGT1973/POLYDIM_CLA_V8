<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# busca solucionas sota para B. Eliminación del "Serialization Tax"

Serialización Tradicional (JSON / Protobuf): Costo de 15–40 ms15–40 ms por paquete a D≥105D≥105, requiriendo conversión binario →→ texto UTF-8 →→ binario, con hasta 4 copias intermedias en memoria RAM.
Pipeline Binario Directo PMTP/Arrow IPC: Costo de ≤1.2 μs≤1.2 μs mediante paso por punteros directos a memoria compartida y llamadas directas WSASend (Windows) / io_uring send_zc (Linux) sin pasar por buffers intermedios de usuario. busca soluciones sota, no me conformo con nada menoe al 95% si no las encuentra sigue buscando

La solución **SOTA** para eliminar el *serialization tax* no es simplemente cambiar JSON por Protobuf: es evitar por completo el ciclo objeto → serialización → buffer → deserialización. La arquitectura que más se acerca a tu objetivo es un **pipeline binario persistente en memoria compartida**, con *fixed buffers*, publicación por puntero/offset y transporte *zero-copy* únicamente cuando el tamaño del mensaje lo justifica.

Hay una salvedad importante: no encontré evidencia pública sólida que valide universalmente el valor exacto de **≤1,2 μs por paquete** para una ruta completa de aplicación a red. Además, `WSASend` normalmente no garantiza que desaparezca toda copia hacia buffers internos de Windows; Microsoft documenta principalmente *scatter/gather* y la obligación de mantener los buffers vivos hasta completar la operación.[^1_1][^1_2]

## Soluciones candidatas SOTA

| Solución | Serialización | IPC | Red | Adecuación |
| :-- | --: | --: | --: | :-- |
| **Memoria compartida + FlatBuffers/Cap’n Proto** | Casi cero en lectura | Zero-copy | `sendmsg`/`WSASend`/`io_uring` | Mejor opción general |
| **Apache Arrow Plasma / Arrow IPC** | Zero-copy para buffers columnares | `mmap`/shared memory | Requiere transporte externo | Excelente para tablas y lotes |
| **iceoryx2** | Zero-copy pub/sub | Shared memory | No sustituye al transporte WAN | Muy fuerte para IPC local |
| **Agnocast** | Zero-copy pub/sub | Shared memory + notificación | No es transporte de red | Excelente en sistemas distribuidos locales |
| **RDMA / libfabric / DPDK** | Buffer binario preconstruido | NIC → memoria | Zero-copy o kernel bypass | Mejor para red de baja latencia |
| **Cap’n Proto RPC** | Formato wire = layout en memoria | Puede evitar parseo | TCP/UDP/RDMA adaptables | Muy bueno para RPC estructurado |
| **FlatBuffers** | Construcción binaria | Lectura directa | Transporte independiente | Bueno si se requiere compatibilidad amplia |

### 1. Cap’n Proto sobre memoria compartida

Cap’n Proto está diseñado para que el formato binario pueda recorrerse directamente en memoria, evitando deserializar hacia objetos intermedios. Su implementación Rust describe explícitamente que puede omitirse la serialización y deserialización cuando el buffer ya está en el formato adecuado.[^1_3]

Arquitectura recomendada:

```text
Productor
  └─ reserva slot en ring compartido
  └─ escribe directamente el mensaje Cap’n Proto
  └─ publica {offset, length, generation}

Consumidor
  └─ lee descriptor
  └─ accede al buffer mediante offset
  └─ procesa campos sin parseo ni copia
```

Ventajas:

- Sin JSON.
- Sin conversión UTF-8.
- Sin reconstrucción de objetos.
- Lectura directa desde el buffer compartido.
- Adecuado para mensajes de tamaño fijo o acotado.
- Puede combinarse con `memfd`, huge pages, NUMA y rings lock-free.

Limitación: la construcción del mensaje aún puede copiar strings o bloques externos si no se usa una estrategia explícita de referencia a memoria externa. La propia documentación/comunidad de Cap’n Proto señala que el beneficio *zero-copy* es especialmente fuerte en lectura, mientras que la escritura necesita configurarse cuidadosamente.[^1_4]

### 2. FlatBuffers para lectura directa

FlatBuffers permite acceder a los datos serializados directamente desde el buffer, sin desempaquetarlos primero; su documentación oficial indica que el único espacio necesario para acceder a los datos es el del propio buffer.[^1_5]

Es una buena alternativa si necesitas:

- Esquemas versionados.
- Compatibilidad entre lenguajes.
- Acceso aleatorio a campos.
- Mensajes enviados por red sin conversión adicional.
- Lecturas parciales y *lazy access*.

La ruta óptima sería:

```text
Shared-memory arena
  → FlatBuffer ya construido
  → descriptor de 16–32 bytes
  → consumidor accede directamente
  → transmisión con scatter/gather
```

No conviene construir el FlatBuffer en un heap convencional y después copiarlo a la arena compartida. El *builder* debe escribir **directamente dentro del slot compartido**.

### 3. Arrow IPC para datos columnares

Arrow IPC es particularmente apropiado para datasets, vectores, matrices y lotes. Apache Arrow está optimizado para *zero-copy* y memoria mapeada, aunque puede asignar memoria adicional en algunos casos, por ejemplo cuando se activa compresión.[^1_6][^1_7]

Úsalo cuando el payload tenga forma de:

- Columnas numéricas.
- Series temporales.
- Vectores.
- Tablas.
- Batches de eventos.
- Datos que varios consumidores deben inspeccionar sin transformar.

Evita Arrow IPC comprimido si el objetivo principal es latencia mínima: la compresión introduce CPU, buffers temporales y posibles asignaciones. Para tu caso, usaría:

- Buffers Arrow no comprimidos.
- Alineación de 64 bytes.
- Huge pages cuando el payload sea grande.
- `mmap`/`memfd` para compartir.
- Metadatos mínimos fuera del payload.
- Pool de buffers por NUMA node.

Arrow no es necesariamente la mejor opción para mensajes diminutos de control; para esos casos, Cap’n Proto, FlatBuffers o una estructura binaria fija serán más eficientes.

## Transporte Linux

En Linux, la ruta de red recomendada sería híbrida:

```text
Mensaje < 8–10 KiB
  → io_uring regular send / sendmsg

Mensaje ≥ 10–100 KiB
  → io_uring send_zc

Mensajes críticos de latencia
  → AF_XDP, DPDK o RDMA
```

`IORING_OP_SEND_ZC` permite enviar sin copiar los datos del usuario a los buffers de socket del kernel, pero requiere mantener el buffer intacto hasta recibir la notificación de liberación. La operación puede producir dos CQE: uno indicando que el envío fue aceptado y otro indicando que las páginas ya se pueden reutilizar.[^1_8]

El umbral debe ser medido, no asumido. La documentación técnica disponible indica que para mensajes pequeños el coste de fijar páginas puede ser superior al de una copia normal; como regla inicial, usar envío convencional por debajo de aproximadamente 10 KiB, medir entre 10 y 100 KiB y aplicar *send zero-copy* sobre cargas grandes.[^1_8]

### Importante sobre `io_uring send_zc`

`send_zc` no elimina:

- Copias realizadas por el hardware o NIC.
- Segmentación TCP.
- Coste de checksum si no hay offload.
- Page pinning.
- Notificaciones de finalización.
- Coste de syscalls o CQE.
- Coste de asignar/construir el mensaje.
- Latencia de congestión y colas de red.

Por eso, “zero-copy” no significa automáticamente “≤1,2 μs extremo a extremo”.

## Transporte Windows

En Windows, `WSASend` admite varios `WSABUF` y *scatter/gather*, por lo que puedes enviar un encabezado y un cuerpo sin concatenarlos en un buffer único.[^1_9][^1_1]

Sin embargo, `WSASend` no debería presentarse como una garantía absoluta de cero copias: documentación de Microsoft sobre Winsock describe que los datos pueden copiarse a buffers internos de AFD cuando se utiliza el camino convencional.[^1_2]

Para minimizar el coste:

1. Usa sockets overlapped con IOCP.
2. Mantén un pool de buffers preasignados.
3. Usa `WSABUF[]` para header + payload.
4. Evita `memcpy` de consolidación.
5. Usa buffers registrados si el proveedor y la ruta seleccionada lo permiten.
6. Evalúa **Registered I/O**, especialmente `RIOReceive`/`RIOSend`, para cargas sostenidas y muchos mensajes.
7. Mide con ETW/WPA y contadores de copias, no solo con el tiempo de aplicación.

Microsoft documenta `RIOSend` como la API para enviar datos en sockets TCP/UDP con Registered I/O.[^1_10]

## IPC local de menor latencia

Para comunicación entre procesos en la misma máquina, no uses TCP loopback como primera opción. Usa:

- **iceoryx2** para pub/sub con memoria compartida.
- **Agnocast** para pipelines de baja latencia con notificación eficiente.
- Ring buffers SPSC/MPSC en memoria compartida.
- `eventfd`, futexes o polling dedicado.
- Descriptores pequeños con `{offset, length, type, generation}`.
- Reclamación por epochs o reference counting.

Un estudio reciente sobre Agnocast e iceoryx2 reporta latencias de extremo a extremo de decenas de microsegundos bajo escenarios de carga, y muestra que el mecanismo de notificación puede dominar incluso cuando la operación de memoria compartida es mucho más rápida.[^1_11]

Esto es relevante para tu objetivo: aunque el acceso al buffer sea submicrosegundo, la notificación, scheduling, interrupciones, fences y wake-ups pueden llevar la latencia total a varios microsegundos.

## Diseño recomendado

### Ruta de datos

```text
[Productor]
    │
    │ escribe directamente
    ▼
[NUMA-local shared-memory arena]
    │
    │ publica descriptor lock-free
    ▼
[Consumidor local]
    │
    ├─ procesa sin deserializar
    │
    └─ si sale a red:
          ├─ < umbral: send normal
          ├─ grande: io_uring SEND_ZC
          ├─ Windows: RIO/WSASend + WSABUF
          └─ extremo ultra-low-latency: RDMA/DPDK/AF_XDP
```


### Descriptor sugerido

```c
struct MessageRef {
    uint64_t offset;
    uint32_t length;
    uint16_t schema_id;
    uint16_t flags;
    uint64_t sequence;
    uint64_t generation;
};
```

El descriptor debe ser pequeño y contener offsets, no punteros virtuales absolutos, porque los procesos pueden mapear la misma arena en direcciones distintas.

## Qué elegir

### Si el payload es estructurado

Elige **Cap’n Proto o FlatBuffers dentro de una arena de memoria compartida**.

- Cap’n Proto: mejor si controlas todo el ecosistema y quieres RPC/serialización integrada.
- FlatBuffers: mejor si necesitas interoperabilidad amplia y acceso directo muy simple.
- No conviertas a JSON salvo en el borde de observabilidad o compatibilidad.


### Si el payload es tabular o vectorial

Elige **Arrow IPC sin compresión**, compartiendo los buffers por `mmap`/`memfd` o una arena equivalente. Arrow está diseñado precisamente para reducir copias y permitir acceso mediante buffers mapeados.[^1_7][^1_6]

### Si el problema es IPC local

Elige **iceoryx2 o Agnocast**, con una política explícita de:

- tamaño de pool,
- backpressure,
- reclamación,
- afinidad NUMA,
- polling frente a notificación,
- número de consumidores.


### Si el cuello está en red

Elige:

- Linux: `io_uring` + `send_zc`, con fallback para mensajes pequeños.
- Windows: IOCP + `WSABUF`; prueba RIO para tráfico sostenido.
- Latencia extrema y hardware compatible: RDMA, DPDK o AF_XDP.


## Validación del objetivo del 95%

Si tu referencia es eliminar al menos el **95%** de un coste de 15–40 ms, el objetivo máximo sería aproximadamente:

- 15 ms → ≤0,75 ms.
- 40 ms → ≤2 ms.

Una ruta de memoria compartida con FlatBuffers/Cap’n Proto o Arrow puede superar ampliamente ese objetivo frente a una ruta JSON tradicional, porque elimina la conversión textual y varias copias. Pero si el objetivo real es reducir **todo el pipeline a ≤1,2 μs**, no debe aceptarse como afirmación teórica: hay que medirlo en el hardware final.

El benchmark mínimo debería separar:


| Etapa | Métrica |
| :-- | :-- |
| Construcción del mensaje | ns/op |
| Copias de memoria | bytes copiados |
| Publicación IPC | p50/p99/p99.9 |
| Notificación | p50/p99 |
| Lectura del consumidor | ns/op |
| Syscall de envío | ns/op |
| Tiempo hasta kernel/NIC | p50/p99 |
| RTT o entrega remota | p50/p99/p99.9 |
| CPU y memoria | ciclos/byte, RSS |
| Jitter | desviación y máximos |

### Criterio de aceptación

No consideraría válida una solución “95% mejor” si solo mide `deserialize()` aislado. Debe medirse:

```text
timestamp productor
→ mensaje listo
→ publicación
→ recepción consumidor
→ buffer entregado al socket
→ confirmación de finalización
```

La conclusión práctica es: **memoria compartida + FlatBuffers/Cap’n Proto para mensajes, Arrow para datos columnares, iceoryx2/Agnocast para IPC local, y un transporte adaptativo `send`/`send_zc`/RIO/RDMA para red**. Esa combinación es más sólida que afirmar que `WSASend` por sí solo elimina toda la serialización y toda copia.

<span style="display:none">[^1_12][^1_13][^1_14][^1_15][^1_16][^1_17][^1_18][^1_19][^1_20][^1_21][^1_22][^1_23][^1_24][^1_25][^1_26][^1_27][^1_28][^1_29][^1_30][^1_31][^1_32][^1_33][^1_34][^1_35][^1_36][^1_37][^1_38][^1_39][^1_40][^1_41][^1_42][^1_43][^1_44]</span>

<div align="center">⁂</div>

[^1_1]: https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-wsasend

[^1_2]: https://learn.microsoft.com/en-us/archive/msdn-magazine/2000/october/windows-sockets-2-0-write-scalable-winsock-apps-using-completion-ports

[^1_3]: https://github.com/capnproto/capnproto-rust/blob/master/README.md

[^1_4]: https://github.com/capnproto/capnproto/issues/2180

[^1_5]: https://flatbuffers.dev/

[^1_6]: https://arrow.apache.org/docs/cpp/api/ipc.html

[^1_7]: https://arrow.apache.org/docs/python/ipc.html

[^1_8]: https://kernel-internals.org/io-uring/networking/

[^1_9]: https://learn.microsoft.com/en-us/windows/win32/winsock/support-for-scatter-gather-input-output-in-the-spi-2

[^1_10]: https://learn.microsoft.com/en-us/windows/win32/winsock/winsock-functions

[^1_11]: https://arxiv.org/html/2605.04226v1

[^1_12]: https://arrow.apache.org/docs/11.0/python/ipc.html

[^1_13]: https://arrow.apache.org/docs/1.0/python/ipc.html

[^1_14]: https://dl.ifip.org/db/conf/networking/networking2020/1570620395.pdf

[^1_15]: https://grpc.io/blog/mobile-benchmarks/

[^1_16]: https://science.lpnu.ua/sites/default/files/journal-paper/2024/dec/36976/vse-1-6.pdf

[^1_17]: https://science.lpnu.ua/sites/default/files/journal-paper/2024/dec/36976/1-acps-9-2-maltsev1-89-94.pdf

[^1_18]: https://github.com/inomera/proto-json-benchmark

[^1_19]: https://github.com/inomera/proto-json-benchmark/blob/main/README.md

[^1_20]: https://www.diva-portal.org/smash/get/diva2:1878772/FULLTEXT01.pdf

[^1_21]: https://www.emergentmind.com/topics/zero-copy-access-features

[^1_22]: https://github.com/ProgrammerAL/SerializationBenchmarks

[^1_23]: https://libriscv.no/assets/files/Emulator_remote_execution_using_merged_address_spaces-4-6ad2a2b8b543c0674e6643bcafbfe369.pdf

[^1_24]: https://docs.kernel.org/networking/iou-zcrx.html

[^1_25]: https://docs.kernel.org/next/networking/iou-zcrx.html

[^1_26]: https://docs.kernel.org/block/ublk.html

[^1_27]: https://docs.kernel.org/6.15/block/ublk.html

[^1_28]: https://learn.microsoft.com/en-us/windows/win32/api/Winsock2/nf-winsock2-wsasend

[^1_29]: https://www.kernel.org/doc/html/v7.3-rc3/filesystems/fuse/fuse-io-uring.html

[^1_30]: https://learn.microsoft.com/en-us/Windows/win32/winsock/winsock-functions

[^1_31]: https://learn.microsoft.com/en-us/windows/win32/winsock/overlapped-i-o-and-event-objects-2

[^1_32]: https://learn.microsoft.com/ja-jp/previous-versions/aa925642(v=msdn.10)

[^1_33]: https://lore.kernel.org/io-uring/

[^1_34]: https://lore.kernel.org/io-uring/d5568318-39ea-0c39-c765-852411409b68@kernel.dk/T/

[^1_35]: https://flatbuffers.dev/flatc/

[^1_36]: https://flatbuffers.dev/tutorial/

[^1_37]: https://flatbuffers.dev/languages/cpp/

[^1_38]: https://capnproto.org/cxx.html

[^1_39]: https://github.com/capnproto/capnproto-rust

[^1_40]: https://deepwiki.com/opentraffic/flatbuffers/6.1-memory-layout-and-performance

[^1_41]: https://deepwiki.com/google/flatbuffers/5.3-serialization-and-deserialization

[^1_42]: https://apis.io/providers/capn-proto/

[^1_43]: https://github.com/google/flatbuffers

[^1_44]: https://www.netguru.com/blog/flatbuffers-vs-protobufs


---

# profindiza en busca soluciones sota, no me conformo con nada menoe al 95% si no las encuentra sigue buscando

Sí: profundizando con un criterio estricto de **≥95% de reducción frente a una ruta de 15–40 ms**, sí existen soluciones que cumplen el objetivo en IPC local y en serialización/acceso a memoria. Pero **no es técnicamente defendible prometer ≤1,2 μs para todo el trayecto aplicación → red → aplicación** usando únicamente Arrow IPC y `WSASend`/`io_uring`; ese valor solo aparece en rutas muy específicas, normalmente dentro de la misma máquina, con mensajes pequeños, CPU fijada y buffers preasignados.

## Resultado de la búsqueda SOTA

### 1. iceoryx2: mejor candidato para IPC local

**iceoryx2** es actualmente uno de los candidatos más fuertes para eliminar el coste de serialización dentro de una máquina:

- El productor escribe una vez en memoria compartida.
- Los consumidores reciben referencias al mismo payload.
- No se copia el cuerpo del mensaje.
- No requiere hilos de fondo.
- Ofrece patrones publish/subscribe, request/response, eventos y blackboard.
- Declara latencia inferior a 1 μs y cero copias por mensaje en su material de rendimiento.[^2_1]

La documentación de sus benchmarks mide directamente la latencia entre publicación y recepción, y reporta comportamiento prácticamente independiente del tamaño del payload en el sistema de referencia.[^2_2][^2_3]

El material de ROSCon reporta aproximadamente 100 ns en una máquina moderna y pruebas en Linux con distintos procesadores, aunque estos valores deben considerarse **benchmarks del proyecto**, no garantías universales.[^2_4]

### Veredicto

Para IPC local, iceoryx2 puede superar ampliamente el umbral del 95%:

$$
15\text{ ms} \rightarrow <1\text{ μs}
$$

Eso equivale a una reducción superior al 99,99% en el tramo de transferencia local, siempre que:

- no haya conversión posterior a JSON;
- el consumidor procese el payload in situ;
- la aplicación no haga copias internas;
- el benchmark mida publicación hasta recepción y no solo una función aislada.


## 2. Aeron IPC: alternativa madura para trading y sistemas críticos

**Aeron IPC** utiliza memoria compartida para la comunicación dentro del mismo host y está orientado a baja latencia, alto throughput y comportamiento predecible. Su documentación oficial define como objetivo maximizar throughput y minimizar latencia tanto en IPC como en UDP unicast/multicast.[^2_5]

Hay resultados publicados de Aeron y Chronicle Queue alrededor de **0,25 μs de round trip** para mensajes pequeños en comunicación dentro de una máquina, aunque dichos resultados dependen fuertemente de afinidad de CPU, polling, tamaño de mensaje y hardware.[^2_6]

Aeron es especialmente adecuado si necesitas:

- Java, C++, Rust u otros lenguajes.
- Comunicación IPC y también transporte UDP.
- Multicast de baja latencia.
- Back pressure controlado.
- Integración con sistemas financieros o de mercado.


### Veredicto

Aeron IPC es un candidato serio cuando necesitas más madurez operativa y transporte de red integrado. Para payloads grandes, conviene utilizar un patrón híbrido:

```text
Aeron transporta el descriptor:
    {arena_id, offset, length, schema, sequence}

La memoria compartida contiene el payload:
    FlatBuffer / Cap’n Proto / Arrow
```

Así se evita que Aeron copie el payload completo.

## 3. Chronicle Queue: excelente para JVM y persistencia

Chronicle Queue ofrece IPC mediante memoria mapeada y está optimizado para mensajería de microsegundos. Su documentación publica, para mensajes de 40 bytes, latencias de percentil 99 de aproximadamente 0,78–1,2 μs bajo determinadas cargas.[^2_7]

También publica resultados entre máquinas muy superiores: aproximadamente 20–176 μs en p99 y con degradación importante en p99.9 bajo cargas mayores.[^2_7]

Esto demuestra una diferencia esencial:

- **IPC local:** puede llegar al rango submicrosegundo.
- **Red entre máquinas:** normalmente no puede conservar ese mismo límite.


### Veredicto

Chronicle Queue es una buena solución si el sistema está basado en Java y necesitas:

- Persistencia.
- Replay.
- Journal de eventos.
- IPC entre JVMs.
- Mensajes pequeños con latencia microsegundo.

No lo elegiría como primera opción para payloads grandes de alta frecuencia si iceoryx2 o una arena propia pueden compartir directamente el bloque de memoria.

## 4. FlatBuffers: mejor benchmark público para demostrar eliminación del parseo

Los benchmarks oficiales de FlatBuffers comparan un objeto con arrays, strings y escalares contra Protobuf y JSON. Para un millón de operaciones:


| Operación | FlatBuffers | Protobuf Lite | JSON rápido |
| :-- | --: | --: | --: |
| Decode + traverse + dealloc | 0,08 s | 302 s | 583 s |
| Encode | 3,2 s | 185 s | 650 s |
| Memoria temporal de decode | 0 KB | 1 KB | 131 KB |

[^2_8]

En ese benchmark, FlatBuffers es aproximadamente:

- $302 / 0,08 \approx 3.775\times$ más rápido que Protobuf en acceso/decodificación.
- $583 / 0,08 \approx 7.287\times$ más rápido que JSON.
- $650 / 3,2 \approx 203\times$ más rápido que JSON en encode.
- Sin memoria temporal de decode.

Esto supera con margen el objetivo del 95% para el **parseo y acceso**, pero no significa que FlatBuffers por sí solo elimine la copia de red o la construcción del buffer.

### Implementación correcta

No hagas esto:

```text
objeto → FlatBuffer en heap → memcpy a shared memory → send
```

Haz esto:

```text
slot preasignado en shared memory
        ↓
FlatBufferBuilder escribiendo directamente en el slot
        ↓
publicación de {offset, length}
        ↓
consumidor lee mediante accessors
```

Para mensajes dinámicos, usa arenas segregadas:

- clase 64–256 B;
- clase 512 B–4 KB;
- clase 8–64 KB;
- clase jumbo para Arrow o blobs.


## 5. Cap’n Proto: mejor si controlas el wire format completo

Cap’n Proto permite recorrer la estructura en el formato wire sin una fase clásica de decode hacia objetos. Para una arquitectura de memoria compartida, esto permite:

```text
arena compartida
    → segmento Cap’n Proto
    → offset/length
    → acceso directo a campos
```

Su principal ventaja sobre FlatBuffers aparece cuando el sistema necesita RPC, capacidades o estructuras anidadas. Su principal coste es que el layout puede ser menos compacto y que ciertos datos dinámicos todavía pueden requerir construcción o copia si no se diseñan como referencias controladas.

### Veredicto

- **FlatBuffers:** mejor para interoperabilidad, lectura directa y layouts simples.
- **Cap’n Proto:** mejor para RPC y estructuras complejas que deben permanecer en formato recorrible.
- **Ambos:** adecuados para eliminar deserialización en IPC.
- **Ninguno:** convierte por sí solo una red TCP común en una ruta de cero copias extremo a extremo.


## 6. Arrow IPC: correcto para batches, no para mensajes pequeños

Arrow es superior cuando el payload es columnar:

- series temporales;
- lotes de eventos;
- matrices;
- vectores;
- tablas;
- datos para SIMD o analítica.

La documentación oficial indica que Arrow está optimizado para zero-copy y memoria mapeada, aunque puede reservar memoria adicional en casos como compresión.[^2_9][^2_10]

Para el objetivo de latencia:

- usa IPC sin compresión;
- comparte buffers directamente;
- separa metadatos de datos;
- evita crear objetos de alto nivel;
- no conviertas cada registro pequeño en un `RecordBatch`.


### Recomendación

Usa Arrow para payloads de al menos varios kilobytes o lotes. Para mensajes de control de 32 B–1 KB, usa una estructura fija, FlatBuffers o Cap’n Proto.

## 7. io_uring ZC Rx: eliminación del copy en recepción

Una mejora especialmente relevante es **io_uring zero-copy receive**, que elimina la copia kernel → userspace en la recepción. La documentación actual del kernel indica que el payload puede recibirse directamente en memoria de usuario, mientras que los headers siguen siendo procesados por la pila TCP del kernel.[^2_11]

Requisitos importantes:

- NIC compatible.
- Header/data split.
- RSS y flow steering.
- Colas RX dedicadas.
- Memoria registrada para recepción.
- Reciclaje explícito de buffers.
- Configuración fuera de banda de la NIC.

Esto es más fuerte que `io_uring send_zc`, porque elimina el copy del lado receptor. La ruta potencial queda:

```text
NIC DMA
  → userspace receive area
  → parser zero-copy
  → consumidor
```

Sin embargo, es una característica condicionada por hardware y configuración. No puede tratarse como una API portable equivalente a `recv()`.

## 8. io_uring SEND_ZC: útil, pero no siempre más rápido

El envío zero-copy no es automáticamente superior para paquetes pequeños. Resultados de pruebas publicados indican que puede ser beneficioso en ciertos Xeon con buffers registrados de aproximadamente 12 KiB o más, mientras que en algunos AMD EPYC fue más lento que el envío normal en todas las pruebas evaluadas.[^2_12]

Por tanto, la política correcta es adaptativa:

```text
payload < 8–16 KiB:
    send normal o sendmsg

payload grande:
    SEND_ZC

alta concurrencia:
    buffers registrados + batching

hardware extremo:
    evaluar RDMA/DPDK/AF_XDP
```

El umbral debe calcularse en cada plataforma:

$$
T_{\text{zerocopy}} =
T_{\text{registro/pinning}} +
T_{\text{notificación}} +
T_{\text{reutilización}}
$$

Si ese coste supera el de una copia rápida `memcpy`, zero-copy empeora la latencia.

## 9. RDMA: la ruta de red con mayor probabilidad de acercarse a 95%

Para comunicación entre máquinas, RDMA es la alternativa más sólida cuando el objetivo es minimizar copias y CPU.

La ruta típica es:

```text
buffer registrado
    → NIC RDMA
    → memoria registrada del receptor
```

Ventajas:

- DMA directo entre NIC y memoria registrada.
- Menor intervención del kernel.
- Menor CPU por byte.
- Latencia mucho menor que TCP tradicional.
- `RDMA WRITE` permite escribir en memoria remota sin que el receptor ejecute una syscall por mensaje.

Desventajas:

- Hardware y switches compatibles.
- Complejidad operativa.
- Gestión de memory regions y claves.
- Seguridad y aislamiento más delicados.
- El protocolo de aplicación debe gestionar ownership, secuencias y reclamación.

Para payloads grandes, RDMA puede superar fácilmente una mejora del 95% frente a una ruta JSON con múltiples copias. No obstante, la latencia física de red sigue existiendo: no es razonable prometer 1,2 μs de extremo a extremo entre hosts separados por switches convencionales.

## 10. DPDK y AF_XDP: cuando el kernel deja de ser suficiente

**DPDK** y **AF_XDP** son adecuados si quieres controlar el camino de paquetes con mínimo overhead:

```text
NIC → DMA buffer → userspace packet processing
```

DPDK permite adjuntar buffers externos a `mbufs` y reutilizar referencias sin copiar el payload.[^2_13][^2_14][^2_15]

DPDK es apropiado para:

- appliances de red;
- brokers especializados;
- gateways de ultra bajo jitter;
- protocolos UDP propios;
- cargas de paquetes muy altas.

No es la mejor opción si necesitas TCP completo, portabilidad o facilidad de operación. Para TCP, `io_uring` ZC Rx ofrece un compromiso más práctico: conserva el stack TCP del kernel, pero puede entregar el payload directamente a userspace cuando la NIC y la configuración lo permiten.[^2_11]

## Arquitectura que recomendaría

### Nivel 1: IPC dentro del host

```text
iceoryx2
    +
arena de memoria compartida NUMA-local
    +
FlatBuffers o Cap’n Proto
    +
ring lock-free / referencia por offset
```

Objetivo:

- 0 copias de payload.
- \<1 μs para publicación/recepción bajo condiciones controladas.
- p99 y p99.9 medidos por separado.


### Nivel 2: red Linux

```text
payload < 8–16 KiB:
    io_uring send normal

payload grande:
    io_uring SEND_ZC

recepción compatible:
    io_uring ZC Rx

máxima exigencia:
    RDMA o DPDK/AF_XDP
```


### Nivel 3: red Windows

```text
IPC:
    shared memory + ring lock-free

network:
    IOCP + WSASend con WSABUF

tráfico sostenido:
    Registered I/O / RIO

payload:
    buffer compartido o registrado
```

No usaría `WSASend` como prueba de “cero copias” por sí solo. Microsoft documenta que `WSASend` ofrece buffers y scatter/gather, pero el proveedor puede copiar a buffers internos; por eso la validación debe hacerse con ETW/WPA y con un benchmark de memoria y CPU.[^2_16][^2_17]

## Comparación con tu baseline

Tomando 15–40 ms como baseline:


| Ruta | Latencia típica objetivo | Mejora potencial frente a 15 ms | ¿Supera 95%? |
| :-- | --: | --: | :-- |
| JSON tradicional | 15–40 ms | 0% | No |
| Protobuf convencional | sub-ms a varios ms | Dependiente del caso | A veces |
| FlatBuffers decode local | decenas de ns–μs | >99% | Sí |
| Cap’n Proto en shared memory | sub-μs–μs | >99,9% | Sí |
| iceoryx2 IPC | sub-μs declarado | >99,99% | Sí, local |
| Aeron IPC | sub-μs–μs | >99,9% | Sí, local |
| Chronicle Queue IPC | alrededor de 1 μs para mensajes pequeños | >99,99% | Sí, local |
| io_uring SEND_ZC | normalmente μs, muy dependiente del hardware | >95% | Sí en ciertos escenarios |
| io_uring ZC Rx | eliminación del copy de recepción | >95% del coste de copia | Sí, si hardware compatible |
| RDMA | pocos μs entre hosts | >95% frente a 15–40 ms | Sí |
| DPDK/AF_XDP | muy bajo overhead | >95% | Sí, con red y aplicación adecuadas |

La evidencia pública más fuerte para **≤1,2 μs** corresponde a IPC local y mensajes pequeños, no a redes entre hosts. Chronicle publica p99 de 0,78–1,2 μs en ciertos escenarios locales, mientras que su comunicación entre máquinas aumenta a decenas o cientos de microsegundos. Aeron también se posiciona para RTT de pocos microsegundos, pero no elimina el límite de propagación y switching de la red.[^2_18][^2_7]

## Diseño de referencia

### Formato del mensaje

```c
struct MsgRef {
    uint64_t arena_offset;
    uint32_t payload_len;
    uint32_t schema_id;
    uint64_t sequence;
    uint64_t generation;
};
```

El payload debe ser uno de estos:

```text
control < 256 B:
    struct binario fijo

256 B–64 KiB:
    FlatBuffers o Cap’n Proto

batch/vector/table:
    Arrow IPC sin compresión

blob grande:
    buffer externo registrado
```


### Reglas obligatorias

- Nunca serializar a JSON en el hot path.
- Nunca copiar un payload compartido a un buffer de socket si puede enviarse mediante `iovec`/`WSABUF`.
- No usar punteros absolutos entre procesos; usar offsets.
- Separar control y datos.
- Fijar productor y consumidor a CPUs dedicadas.
- Alinear buffers a 64 bytes.
- Separar arenas por NUMA node.
- Desactivar compresión en el hot path.
- Utilizar huge pages solo después de medir TLB y latencia.
- Usar epochs o reference counting para liberar buffers.
- Aplicar backpressure sin bloquear el productor crítico.
- Mantener un fallback de copia para tamaños pequeños.


## Criterio de aceptación real

Aceptaría la solución únicamente si el benchmark completo muestra:

```text
p50 < objetivo
p99 < objetivo
p99.9 < objetivo
0 copias de payload verificadas
sin alloc/free en hot path
CPU y NUMA fijados
payloads pequeño, medio y jumbo
carga normal y saturada
```

Y mediría por separado:

1. creación del mensaje;
2. publicación IPC;
3. recepción local;
4. construcción del descriptor de red;
5. envío;
6. recepción remota;
7. acceso final del consumidor;
8. reclamación del buffer.

## Conclusión técnica

La solución con mayor probabilidad de cumplir tu umbral del 95% es:

```text
iceoryx2 o Aeron IPC
+ memoria compartida con offsets
+ FlatBuffers/Cap’n Proto para mensajes
+ Arrow sin compresión para batches
+ io_uring SEND_ZC y ZC Rx en Linux
+ RIO/IOCP/WSABUF en Windows
+ RDMA para inter-host exigente
+ DPDK/AF_XDP solo cuando el kernel sea el cuello de botella
```

Para **IPC local**, el objetivo de 95% e incluso el rango submicrosegundo es plausible y está respaldado por benchmarks públicos de iceoryx2, Aeron y Chronicle Queue.[^2_1][^2_4][^2_6][^2_7]

Para **red entre máquinas**, la opción SOTA es **RDMA**; `io_uring` zero-copy es el mejor compromiso si necesitas conservar TCP, pero su rendimiento depende de NIC, kernel, CPU, tamaño de buffer y arquitectura. No aceptaría una afirmación de ≤1,2 μs sin una medición extremo a extremo en tu hardware concreto.

<span style="display:none">[^2_19][^2_20][^2_21][^2_22][^2_23][^2_24][^2_25][^2_26][^2_27][^2_28][^2_29][^2_30][^2_31][^2_32][^2_33][^2_34][^2_35][^2_36][^2_37][^2_38][^2_39][^2_40][^2_41][^2_42][^2_43][^2_44][^2_45][^2_46][^2_47]</span>

<div align="center">⁂</div>

[^2_1]: https://iceoryx.io/

[^2_2]: https://github.com/eclipse-iceoryx/iceoryx2/blob/main/benchmarks/README.md

[^2_3]: https://github.com/eclipse-iceoryx/iceoryx2/blob/main/README.md

[^2_4]: https://roscon.ros.org/2024/talks/iceoryx2\_\_A_Journey_to_Becoming_a_First-Class_RMW_Alternative.pdf

[^2_5]: https://aeron.io/docs/

[^2_6]: https://www.man.com/technology/special-fx-execution-system-on-aeron

[^2_7]: https://chronicle.software/tech-hub/technical-information/chronicle-queue/what-is-chronicle-queue

[^2_8]: https://flatbuffers.dev/benchmarks/

[^2_9]: https://arrow.apache.org/docs/cpp/api/ipc.html

[^2_10]: https://arrow.apache.org/docs/python/ipc.html

[^2_11]: https://docs.kernel.org/networking/iou-zcrx.html

[^2_12]: https://lore.gnuweeb.org/io-uring/f1600745ba7b328019558611c1ad7684@yourcmc.ru/T/

[^2_13]: https://doc.dpdk.org/guides-25.11/prog_guide/ip_fragment_reassembly_lib.html

[^2_14]: https://doc.dpdk.org/api/rte\_\_mbuf_8h.html

[^2_15]: https://doc.dpdk.org/api-21.11/rte\_\_mbuf_8h.html

[^2_16]: https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-wsasend

[^2_17]: https://learn.microsoft.com/en-us/archive/msdn-magazine/2000/october/windows-sockets-2-0-write-scalable-winsock-apps-using-completion-ports

[^2_18]: https://aeron.io/aeron-open-source/

[^2_19]: https://arxiv.org/pdf/2504.06151.pdf

[^2_20]: https://pkg.go.dev/github.com/appnet-org/arpc/benchmark/serialization/kv-store

[^2_21]: https://martinuke0.github.io/posts/2026-03-07-optimizing-high-performance-distributed-systems-using-zero-copy-architecture-and-shared-memory-buffers/

[^2_22]: https://www.emergentmind.com/topics/io_uring-interface

[^2_23]: https://github.com/aeron-io/benchmarks

[^2_24]: https://josedavidbaena.com/blog/zero-copy/07-zero-copy-serialization-borrowed-memory

[^2_25]: https://www.reddit.com/r/cpp/comments/1ptyu8a/iceoryx2_v08_released/

[^2_26]: https://github.com/aeron-io/aeron/wiki/Performance-Testing

[^2_27]: https://www.pistack.xyz/posts/2026-06-19-schema-serialization-frameworks-protobuf-capnproto-flatbuffers-thrift/

[^2_28]: https://instatunnel.my/blog/beyond-epoll-architecting-ultra-low-latency-reverse-tunnels-with-linux-iouring

[^2_29]: https://doc.dpdk.org/api-20.11/structrte\_\_mbuf.html

[^2_30]: https://doc.dpdk.org/api-22.11/structrte\_\_mbuf.html

[^2_31]: https://doc.dpdk.org/guides-19.11/prog_guide/vhost_lib.html

[^2_32]: https://doc.dpdk.org/api-20.11/rte\_\_mbuf_8h.html

[^2_33]: https://doc.dpdk.org/guides/prog_guide/mbuf_lib.html

[^2_34]: https://doc.dpdk.org/guides-24.03/prog_guide/vhost_lib.html

[^2_35]: https://doc.dpdk.org/guides-22.11/prog_guide/index.html

[^2_36]: https://doc.dpdk.org/guides-20.11/prog_guide/index.html

[^2_37]: https://doc.dpdk.org/guides-20.08/prog_guide/vhost_lib.html

[^2_38]: https://doc.dpdk.org/guides-21.08/prog_guide/index.html

[^2_39]: https://doc.dpdk.org/api-18.08/rte\_\_mbuf_8h.html

[^2_40]: https://doc.dpdk.org/guides-23.11/prog_guide/vhost_lib.html

[^2_41]: https://fosdem.org/2026/events/attachments/M7TKVG-meet-iceoryx2/slides/266902/fosdem-mi_tra9vup.pdf

[^2_42]: https://chronicle.software/products/chronicle-queue

[^2_43]: https://github.com/OpenHFT/Chronicle-Queue

[^2_44]: https://github.com/eclipse-iceoryx/iceoryx2

[^2_45]: https://context7.com/eclipse-iceoryx/iceoryx2

[^2_46]: https://github.com/OpenHFT/Chronicle-Queue/blob/ea/README.adoc

[^2_47]: https://arxiv.org/html/2605.04226v1


---

# profundiza busca soluciones sota, no me conformo con nada menoe al 95% si no las encuentra sigue buscando

Encontré opciones adicionales de nivel SOTA que sí superan el umbral del **95%** en escenarios concretos. La conclusión más importante es que tu objetivo requiere separar tres casos: **IPC local**, **red entre hosts** y **memoria compartida entre hosts**. Cada uno tiene una solución óptima distinta.

## Hallazgo principal: CXL compartido

La alternativa más cercana a tu objetivo original de **≤1,2 μs sin serialización ni copias de payload entre hosts** es **CXL.mem con memoria compartida multi-host**.

CXL permite que varios hosts accedan a una región común mediante operaciones load/store, en lugar de enviar mensajes Ethernet que requieran marshalling y buffers de red. La especificación CXL 3.0 define precisamente memoria compartida coherente entre hosts.[^3_1][^3_2]

Un trabajo de Microsoft Research sobre pods CXL describe un caso ideal con aproximadamente **600 ns**, equivalente a una escritura CXL y una lectura CXL, y lo compara con latencias RDMA de decenas de microsegundos.[^3_3]

Otro estudio sobre comunicación CXL real reporta aproximadamente **790 ns para un mensaje de 8 bytes**, frente a **16–18 μs usando TCP**, una reducción superior al 95%.[^3_4]

### Arquitectura CXL recomendada

```text
Host A
  └─ escribe payload en región CXL compartida
  └─ publica doorbell/sequence

Host B
  └─ observa doorbell
  └─ lee el mismo payload desde CXL
```

No hay:

- JSON.
- Protobuf intermedio.
- buffer TCP.
- `memcpy` de aplicación.
- serialización tradicional.
- reconstrucción de objetos.

El descriptor puede ser:

```c
struct CxlMessage {
    uint64_t offset;
    uint32_t length;
    uint32_t schema_id;
    uint64_t sequence;
};
```


### Limitaciones reales de CXL

CXL es la única solución encontrada que puede acercarse simultáneamente a:

- memoria compartida entre servidores;
- acceso por load/store;
- latencia submicrosegundo en condiciones favorables;
- eliminación de la serialización de grandes estructuras.

Pero todavía no es una solución universal de producción:

- La disponibilidad comercial multi-host sigue siendo limitada.
- Muchos dispositivos comerciales continúan centrados en CXL 2.0 para expansión dentro de un servidor.
- Los sistemas multi-host requieren switches y dispositivos específicos.
- El acceso CXL puede ser más lento que DRAM local.
- Hay problemas de coherencia, orden de publicación y sincronización.
- La memoria compartida no elimina automáticamente el coste de coordinación.

Un estudio de CXL-CCL reporta **658 ns** de latencia de acceso al pool CXL frente a 214 ns de DRAM local. El trabajo también destaca que el hardware actual puede carecer de intercalado fino por cache line y que es necesario distribuir softwaremente los bloques para evitar hotspots.[^3_5]

### Veredicto CXL

**SOTA absoluto para tu objetivo cuando tienes control del hardware del datacenter.**

- Cumplimiento del 95% frente a 15–40 ms: sí, con enorme margen.
- Cumplimiento de ≤1,2 μs: plausible para operaciones simples.
- Producción general: todavía limitada.
- Mejor uso: clúster dedicado, trading, memoria distribuida, AI/HPC y sistemas donde se puede controlar NIC, switch y topología.


## Nuevo canal IPC de io_uring

Encontré también una propuesta de **canal IPC integrado en io_uring**. Añade un ring buffer compartido, productores lock-free, publicación por `mmap` y modos unicast, multicast y broadcast.[^3_6]

Sus resultados publicados son:


| Tamaño | io_uring unicast | io_uring broadcast, 16 receptores |
| --: | --: | --: |
| 64 B | 632 ns | 5.674 ns |
| 256 B | 597 ns | 6.600 ns |
| 1 KB | 640 ns | 6.095 ns |
| 4 KB | 848 ns | 6.367 ns |
| 16 KB | 1.893 ns | 7.592 ns |
| 32 KB | 3.185 ns | 8.202 ns |

Para 16 receptores y mensajes de 32 KB, el canal broadcast publicado es **10,9× más rápido que pipes** y **11,3× más rápido que shared memory + eventfd**, porque escribe el payload una sola vez en el ring común.[^3_6]

### Evaluación

Esta propuesta no necesariamente reemplaza a iceoryx2 en un caso punto a punto, porque para mensajes pequeños tiene el overhead adicional de pasar por la infraestructura io_uring. Sin embargo, es muy atractiva si necesitas unificar:

- IPC.
- operaciones de red;
- finalizaciones;
- batching;
- multiconsumidor;
- integración con rings kernel/userspace.


### Veredicto

- Punto a punto pequeño: iceoryx2 o ring propio puede ser más rápido.
- Broadcast a muchos consumidores: io_uring IPC es excepcional.
- Integración futura con red: muy prometedor.
- Estado: propuesta/RFC, no asumir que está disponible en una versión estable de kernel sin verificar el árbol exacto.


## Agnocast: cuidado con los números

La búsqueda encontró un resultado académico de 2026 que compara Agnocast e iceoryx2. A nivel extremo a extremo, Agnocast obtiene **21,6 μs p50**, frente a **54,3 μs para iceoryx2**, aproximadamente 2,5× menos en ese escenario concreto.[^3_7]

Esto contradice parcialmente las cifras submicrosegundo de materiales promocionales o microbenchmarks internos de algunos proyectos. La explicación probable es que se midió el pipeline completo, incluyendo:

- publicación;
- notificación;
- scheduling;
- recepción;
- reclamación;
- posiblemente serialización o gestión de ownership.


### Conclusión

No debes aceptar “submicrosecond latency” si solo se mide el acceso al buffer. Para comparar soluciones, exige:

```text
timestamp antes de publicar
→ consumer recibe
→ consumer valida sequence
→ consumer accede al primer campo
```

Agnocast puede ser excelente en sistemas ROS 2 y pub/sub, pero con evidencia pública actual **no lo pondría por delante de iceoryx2, Aeron IPC o un ring SPSC dedicado para el objetivo ≤1,2 μs extremo a extremo**.

## io_uring optimizado: cuándo sí supera 95%

Un estudio de 2026 sobre io_uring muestra que el rendimiento no mejora simplemente sustituyendo `epoll`. El cambio ingenuo produjo solo aproximadamente 1,10×; una arquitectura diseñada alrededor de batching, buffers registrados y ejecución asíncrona alcanzó alrededor de 2,31× en una carga de *network shuffle*.[^3_8]

El mismo trabajo reporta que:

- los buffers registrados reducen copias y page pinning repetido;
- `send_zc` transmite desde buffers fijados;
- zero-copy receive escribe directamente en memoria registrada;
- para mensajes grandes puede llegar a 3,5× menos ciclos por byte;
- para mensajes pequeños el coste de administrar buffers zero-copy puede superar el beneficio.

[^3_8]

### Configuración SOTA Linux

```text
io_uring_setup:
    IORING_SETUP_SQPOLL
    IORING_SETUP_DEFER_TASKRUN
    IORING_SETUP_COOP_TASKRUN

buffers:
    registered fixed buffers
    huge pages cuando sea beneficioso
    NUMA-local allocation

TX:
    send_zc para payloads grandes

RX:
    zero-copy receive para NIC compatible

control:
    CQ batching
    adaptive batching
    busy polling selectivo
```

Hay que tener cuidado con `SQPOLL`: un estudio midió aproximadamente **30 μs de coste al despertar el hilo de polling** cuando entra en suspensión. Por eso, para el objetivo de 1,2 μs, el ring debe mantenerse caliente o utilizar polling dedicado, no depender del wake-up del kernel.[^3_8]

### Umbral de payload

La política adecuada no es “siempre zero-copy”:


| Payload | Ruta recomendada |
| --: | :-- |
| < 1 KiB | copia normal optimizada |
| 1–8 KiB | medir `send` frente a `send_zc` |
| 8–32 KiB | buffers registrados + `send_zc` |
| > 32 KiB | `send_zc`/ZC Rx |
| Jumbo | RDMA, DPDK o AF_XDP |

La investigación disponible indica que `send_zc` empieza a ser interesante por encima de aproximadamente 1 KiB en algunos sistemas, pero otras pruebas encontraron beneficios solo alrededor de 12–16 KiB y resultados peores en ciertos EPYC.[^3_9][^3_10]

## io_uring IPC frente a iceoryx2

| Criterio | iceoryx2 | io_uring IPC | Ring propio |
| :-- | :-- | :-- | :-- |
| Punto a punto | Excelente | Bueno | Potencialmente máximo |
| Broadcast | Bueno | Excelente | Complejo |
| Integración con kernel I/O | Baja | Alta | Baja |
| Estado | Disponible | RFC/propuesta | Disponible |
| Control de memoria | Alto | Alto | Máximo |
| Complejidad | Media | Media/alta | Alta |
| Objetivo sub-μs | Plausible | Plausible en unicast | Más probable |
| Muchos consumidores | Bueno | Muy bueno | Difícil |

## RDMA: todavía fuerte, pero no el máximo

RDMA continúa siendo la solución práctica SOTA para red entre hosts cuando CXL no está disponible. Un benchmark de escritura RDMA reporta:

- mínimo: 1,2 μs;
- promedio: 1,8 μs;
- p50: 1,7 μs;
- p99: 3,5 μs;
- p99.9: 4,8 μs.

[^3_11]

Eso no cumple estrictamente tu valor de **≤1,2 μs p99**, pero sí supera sobradamente el objetivo de reducir al menos 95% frente a 15–40 ms.

### Ruta RDMA recomendada

```text
1. Registrar buffers una sola vez.
2. Preasignar memory regions.
3. Usar RDMA WRITE para publicar payload.
4. Usar una pequeña bandera/doorbell para disponibilidad.
5. Leer el payload directamente en la región destino.
6. Evitar RDMA SEND para el cuerpo grande.
7. Usar CQ polling dedicado.
8. Fijar procesos y colas a NUMA/NIC local.
```

El patrón más eficiente suele ser:

```text
RDMA WRITE payload
RDMA WRITE/WRITE_WITH_IMM doorbell
```

El receptor no necesita recibir y copiar un paquete de aplicación; solo valida el descriptor y procesa la región registrada.

## CXL frente a RDMA

| Propiedad | CXL shared memory | RDMA | io_uring ZC |
| :-- | --: | --: | --: |
| Semántica | Load/store | Verbs/one-sided | Socket I/O |
| Payload compartido | Sí | No, memoria registrada | No necesariamente |
| Latencia publicada | 0,6–0,8 μs en casos | 1,2–4,8 μs | Dependiente |
| TCP requerido | No | No | Sí si socket |
| Disponibilidad | Limitada | Alta en datacenter | Alta en Linux moderno |
| Complejidad | Hardware alta | Software/hardware alta | Media |
| Serialización | Evitable | Evitable | Evitable |
| Mejor escenario | Inter-host memoria compartida | Inter-host producción | TCP compatible |

## DPDK/AF_XDP

Para paquetes muy pequeños y tasas extremas, **AF_XDP zero-copy** o **DPDK** pueden ofrecer menos overhead que TCP y una ruta más determinista. Una implementación comercial publica alrededor de 1.200 ciclos por paquete en el camino convencional y aproximadamente 200 ciclos con AF_XDP.[^3_12]

Eso equivale aproximadamente a:

- 1.200 ciclos ≈ 300–400 ns en una CPU de 3–4 GHz.
- 200 ciclos ≈ 50–70 ns.

Pero esas cifras normalmente representan procesamiento del paquete dentro del host, no entrega completa extremo a extremo. No incluyen necesariamente:

- aplicación;
- protocolo de fiabilidad;
- ordenamiento;
- retransmisión;
- sincronización;
- procesamiento remoto;
- propagación de red.


### Veredicto

Usa AF_XDP o DPDK si:

- puedes abandonar TCP;
- controlas ambos extremos;
- aceptas polling;
- puedes dedicar cores;
- la aplicación utiliza UDP o protocolo propio;
- necesitas jitter muy bajo.

No lo usaría como reemplazo genérico de RPC.

## Solución final recomendada por escenario

### Escenario A: un solo servidor

```text
iceoryx2
+ arena shared-memory
+ FlatBuffers/Cap’n Proto
+ SPSC/MPSC lock-free
+ busy polling
+ CPU/NUMA pinning
```

Objetivo:

- p50 submicrosegundo.
- p99 bajo microsegundos.
- cero copias del payload.
- mejora muy superior al 95%.


### Escenario B: dos o más procesos con broadcast

```text
io_uring IPC broadcast
+ shared ring
+ descriptor por consumidor
+ payload escrito una sola vez
```

Es la opción más interesante cuando el payload debe llegar a muchos receptores. A 16 receptores y 32 KB, el benchmark publicado muestra 8,2 μs del lado emisor, frente a 89,4 μs para pipes.[^3_6]

### Escenario C: hosts Linux en datacenter

```text
RDMA WRITE
+ registered memory
+ doorbell
+ CQ polling
+ Cap’n Proto/FlatBuffers en memoria registrada
```

Objetivo:

- p99 de pocos microsegundos;
- reducción superior al 95% frente a 15–40 ms;
- sin serialización textual;
- sin copia intermedia del payload.


### Escenario D: hardware dedicado extremo

```text
CXL.mem shared pool
+ DAX mapping
+ offset-based allocator
+ doorbells
+ explicit visibility protocol
```

Esta es la única opción encontrada con potencial real de mantener el concepto de **memoria compartida entre hosts** y obtener operaciones cercanas o inferiores a 1,2 μs. La disponibilidad comercial todavía es la barrera principal.[^3_3][^3_4][^3_5]

### Escenario E: red Ethernet con TCP obligatorio

```text
io_uring
+ registered buffers
+ SEND_ZC para payload grande
+ ZC Rx cuando la NIC sea compatible
+ DEFER_TASKRUN
+ batching adaptativo
+ fallback send normal para mensajes pequeños
```

Objetivo:

- > 95% frente a una ruta de 15–40 ms;
- no necesariamente ≤1,2 μs extremo a extremo;
- mejor eficiencia de CPU y memoria que `epoll` + `read/write`.


## Dictamen definitivo

La solución con mayor probabilidad de cumplir **simultáneamente** tu exigencia de ≥95% y el límite de ≤1,2 μs es:

```text
CXL.mem shared memory
+ acceso load/store
+ payload preconstruido en arena compartida
+ doorbell/sequence de 64 bits
+ sincronización explícita
```

Si CXL no está disponible:

```text
IPC local:
    iceoryx2 o ring dedicado

inter-host:
    RDMA WRITE + registered memory

TCP obligatorio:
    io_uring SEND_ZC + ZC Rx

broadcast:
    io_uring shared-ring IPC
```

El dato más importante de la búsqueda es que **la serialización no es el único problema**. Después de eliminar JSON/Protobuf aparecen como nuevos límites:

- notificación;
- coherencia y fences;
- page pinning;
- wake-ups;
- CQ processing;
- NUMA;
- scheduling;
- ownership de buffers;
- congestión;
- propagación física.

Por eso, para afirmar que se cumplen tus ≤1,2 μs, el benchmark debe medir el pipeline completo y reportar p50, p99 y p99.9. Los resultados públicos sí muestran mejoras superiores al 95% para CXL, RDMA, shared-memory IPC y zero-copy I/O, pero no justifican una garantía universal de ≤1,2 μs para una ruta TCP completa.

<span style="display:none">[^3_13][^3_14][^3_15][^3_16][^3_17][^3_18][^3_19][^3_20][^3_21][^3_22][^3_23][^3_24][^3_25][^3_26][^3_27][^3_28][^3_29][^3_30][^3_31][^3_32][^3_33][^3_34][^3_35][^3_36][^3_37][^3_38][^3_39]</span>

<div align="center">⁂</div>

[^3_1]: https://computeexpresslink.org/wp-content/uploads/2023/12/CXL_3.0_white-paper_FINAL.pdf

[^3_2]: https://computeexpresslink.org/wp-content/uploads/2023/12/CXL_3.0-Webinar_FINAL.pdf

[^3_3]: https://www.microsoft.com/en-us/research/wp-content/uploads/2026/04/nsdi2026_cxl_octopus.pdf

[^3_4]: https://arxiv.org/html/2510.05476v2

[^3_5]: https://arxiv.org/html/2602.22457v3

[^3_6]: https://lwn.net/Articles/1062825/

[^3_7]: https://arxiv.org/pdf/2605.04226.pdf

[^3_8]: https://arxiv.org/html/2512.04859v1

[^3_9]: https://lore.gnuweeb.org/io-uring/f1600745ba7b328019558611c1ad7684@yourcmc.ru/T/

[^3_10]: https://www.alphaxiv.org/abs/2512.04859

[^3_11]: https://documentation.alluxio.io/ee-ai-en/performance/rdma-networking

[^3_12]: https://www.zerocopy.systems/docs/architecture/zero-copy

[^3_13]: https://lore.gnuweeb.org/io-uring/20260116233044.1532965-25-joannelkoong@gmail.com/

[^3_14]: https://github.com/ringline-rs/ringline

[^3_15]: https://blog.tohojo.dk/2026/02/the-inner-workings-of-tcp-zero-copy.html

[^3_16]: https://www.phoronix.com/news/IO-uring-zcrx-Large-RX

[^3_17]: https://martinuke0.github.io/posts/2026-05-27-deep-dive-into-io_uring-and-epoll-internal-architecture-performance-tradeoffs-and-system-call-evolution/

[^3_18]: https://hpi.de/oldsite/fileadmin/user_upload/fachgebiete/rabl/publications/2025/p10_weisgut_cxlbench.pdf

[^3_19]: https://www.snia.org/sites/default/files/2025-05/SNIA-SDC23-CXL-Enabling-an-interoperable-ecosystem.pdf

[^3_20]: https://computeexpresslink.org/wp-content/uploads/2025/12/CXL_4.0-Webinar_December-2025_FINAL.pdf

[^3_21]: https://arxiv.org/html/2609.10790

[^3_22]: https://computeexpresslink.org/wp-content/uploads/2026/09/CXL_FMS-2026-Panel-Presentation_FINAL.pdf

[^3_23]: https://mug.mvapich.cse.ohio-state.edu/static/media/mug/presentations/25/mug25-HooyoungAhn.pdf

[^3_24]: https://codemia.io/blog/path/CXL-30-Redefining-Zero-Copy-Memory-for-In-Memory-Databases

[^3_25]: https://rodhat.com/tips/2026-09-23-io-uring-attack-surface-and-restrictions/

[^3_26]: http://pasalabs.org/papers/2025/IPDPS25_cxl_eval.pdf

[^3_27]: https://www.insidedeeptech.com/cxl-memory-pooling-full-guide/

[^3_28]: https://rodhat.com/tips/2026-08-25-io-uring-zero-syscall-io/

[^3_29]: https://martinuke0.github.io/posts/2026-05-29-deep-dive-into-io_uring-and-epoll-architecture-performance-trade-offs-and-production-implementation-patterns/

[^3_30]: https://ecrionix.org/cxl/day-11-memory-pooling-disaggregation/

[^3_31]: https://www.computer.org/csdl/journal/tc/2026/04/11435996/2eVUQ7tbMf6

[^3_32]: https://www.sciopen.com/local/article_pdf/10.26599/TST.2025.9010010.pdf

[^3_33]: https://www.wing.vc/content/what-is-cxl

[^3_34]: https://arxiv.org/html/2412.20249v1

[^3_35]: https://pages.cs.wisc.edu/~markhill/papers/ieeetoc2026_cxl_practice.pdf

[^3_36]: https://docs.kernel.org/networking/iou-zcrx.html

[^3_37]: https://martinuke0.github.io/posts/2026-03-07-optimizing-high-performance-distributed-systems-using-zero-copy-architecture-and-shared-memory-buffers/

[^3_38]: https://www.emergentmind.com/topics/io_uring-interface

[^3_39]: https://github.com/aeron-io/benchmarks

