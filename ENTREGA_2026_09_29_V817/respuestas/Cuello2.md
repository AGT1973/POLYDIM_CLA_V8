<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# ⏱️2 CUELLOS DE BOTELLA DE RED Y CÓMO ERRADICARLOS B. Cuello de Botella de Latencia (Serialization \& Deserialization Overhead)

Problema: Serializar tensores a JSON o Protobuf toma ∼15–40 ms∼15–40 ms por mensaje.
Solución V900: Zero-Copy Network Pipelining (Ghost Protocol Network):
En Linux: llamada de sistema sendfile / vmsplice para transferir directamente desde la memoria compartida local al socket TCP sin copiar a espacio de usuario.
En Windows: TransmitFile / WSASend con buffers registrados I/O Completion Ports (IOCP).

El cuello de botella de latencia por serialización/deserialización (∼15–40 ms por mensaje al convertir tensores a JSON/Protobuf) se mitiga eliminando copias intermedias y evitando la conversión de formato mediante *zero-copy* y tuberías de red que operan directamente sobre memoria compartida.[^1_1][^1_2]

## Por qué aparece este cuello de botella

- **Serialización implica copiar y reformatear:** protocolos como Protobuf y Thrift requieren convertir datos nativos a tipos del protocolo, lo que añade latencia de creación de objetos y copias, especialmente en arreglos grandes (tensores).[^1_1]
- **Deserialización añade otra pasada:** después de transmitir, el receptor debe reconstruir objetos, lo que suma *deserialization latency* y puede anular beneficios de payloads más pequeños.[^1_1]
- **En pipelines de ML/IA, esto se multiplica:** incluso microsegundos por mensaje se acumulan a decenas de ms cuando hay muchas conversiones antes/durante la inferencia.[^1_2]


## Solución V900: Zero-Copy Network Pipelining (“Ghost Protocol Network”)

La idea central es **evitar copias a espacio de usuario** y **no serializar** cuando los extremos comparten un formato binario compatible (p. ej., tensores en buffers planos). En la práctica:

### En Linux: `sendfile` / `vmsplice` + memoria compartida

- **`sendfile(out_socket, in_fd, ...)`** mueve datos de un descriptor de archivo a un socket **dentro del kernel**, sin pasar por el proceso del usuario; con DMA scatter-gather, las páginas van directo a la NIC.[^1_3][^1_4][^1_5][^1_6]
- **`vmsplice` + `splice`** permiten tomar páginas de memoria de usuario y enlazarlas a una tubería (pipe) y luego al socket, pasando **referencias de página**, no bytes copiados.[^1_4][^1_5][^1_7][^1_8]
- **Patrón típico para tensores:**

1. Alojar el tensor en **memoria compartida** (p. ej., `mmap` de un archivo tmp o `shm_open`).
2. Usar `vmsplice` para mapear esas páginas en un pipe.
3. Usar `splice` del pipe al socket TCP.
4. El receptor lee y mapea la misma región compartida o reconstruye el tensor sin copiar (zero-copy recv con `recvmsg` + buffers pre-asignados).[^1_8][^1_9][^1_4]

Esto elimina las copias CPU-intensive del payload y reduce la latencia de transmisión, aunque el overhead de *serialización* desaparece si se envía el buffer binario tal cual (sin JSON/Protobuf).[^1_10][^1_4]

### En Windows: `TransmitFile` / `WSASend` + IOCP

- **`TransmitFile`** permite transferir datos desde el cache del sistema a un socket de alta performance, análogo a `sendfile`.[^1_11]
- **`WSASend` con buffers registrados** y **I/O Completion Ports (IOCP)** habilita E/S asíncrona de alto rendimiento y minimiza copias al mantener buffers fijados y reutilizables.[^1_11]
- **Patrón análogo:**

1. Usar memoria compartida (p. ej., *file mapping* con `CreateFileMapping`/`MapViewOfFile`).
2. Registrar buffers y usar `WSASend` sobre sockets no bloqueantes con IOCP para completar la transmisión sin copias adicionales.[^1_11]


## Cuándo esto “erradica” el problema

- **Si el emisor y receptor acuerdan un layout binario** (p. ej., encabezado pequeño + payload de tensor en row-major), puedes **prescindir de JSON/Protobuf** y enviar el buffer directamente; ahí el overhead de 15–40 ms por serializar/deserializar desaparece.[^1_2][^1_1]
- **Zero-copy reduce latencia de transmisión** y uso de CPU, pero no elimina por sí solo la conversión de formato; la combinación ganadora es: *formato binario preacordado* + *zero-copy send/recv*.[^1_7][^1_4][^1_10]


## Limitaciones y consideraciones prácticas

- **No todo es zero-copy:** en TCP, ciertas rutas aún implican copias internas del kernel (p. ej., socket-to-socket no es totalmente zero-copy).[^1_10]
- **Requiere coordinación de protocolos:** ambos lados deben conocer el esquema del tensor (dtype, shape, strides) para evitar serialización.
- **Seguridad y aislamiento:** memoria compartida entre procesos requiere cuidado en permisos y lifecycle (quién libera, cómo se versiona el esquema).

Si quieres, puedo bosquejar un ejemplo mínimo en Linux (C/Python) que envíe un tensor NumPy vía `vmsplice`/`splice` sin serializar a JSON/Protobuf.

<span style="display:none">[^1_12][^1_13][^1_14][^1_15]</span>

<div align="center">⁂</div>

[^1_1]: https://arxiv.org/html/2407.13494v2

[^1_2]: https://ai.wise.one/blog/serialization-ai-response-time-reduction

[^1_3]: https://netdevconf.info/0x15/papers/1/maio_netdev0x15.pdf

[^1_4]: https://crackingwalnuts.com/linux/zero-copy

[^1_5]: https://kernel-internals.org/io/splice-sendfile/

[^1_6]: https://netdevconf.org/2.1/papers/netdev.pdf

[^1_7]: https://www.sobyte.net/post/2022-11/zero-copy/

[^1_8]: https://codemonkeytips.blogspot.com/2011/07/zero-copy-network-transmission-with.html

[^1_9]: http://adrianchadd.blogspot.com/2013/12/experimenting-with-zero-copy-network-io.html

[^1_10]: https://learn.padho.ai/wiki/zero-copy-sendfile-splice-mmap

[^1_11]: https://www.codeproject.com/Articles/10330/A-simple-IOCP-Server-Client-Class?msg=5892041\&PageFlow=FixedWidth

[^1_12]: https://lwn.net/Articles/726917/

[^1_13]: https://netdevconf.info/0x14/pub/slides/62/Implementing TCP RX zero copy.pdf

[^1_14]: https://netdevconf.info/0x15/slides/1/maio_netdev0x15.pdf

[^1_15]: https://cmmon.medium.com/the-zero-copy-frontier-a7d2a4e05127


---

# profundiza sota soluciones, mejoras, actualizaciones

Aquí tienes un panorama SOTA (2024–2026) de soluciones y mejoras para erradicar el cuello de botella de latencia por serialización/deserialización de tensores, con énfasis en zero-copy, formatos sin copia y redes de baja latencia.[^2_1][^2_2][^2_3]

## 1) Zero-copy de red en Linux: más allá de `sendfile`/`vmsplice`

### `MSG_ZEROCOPY` (TX) y `io_uring` send_zc

- **`MSG_ZEROCOPY`** evita la copia por byte en `send()` fijando páginas y delegando la notificación de completado; es rentable típicamente para mensajes > ~10 KB.[^2_4][^2_5]
- **`io_uring`** (Linux 5.1+) añadió **send zero-copy** (`io_uring_prep_send_zc()`, 2022) y **receive zero-copy** (ZC Rx, Linux 6.15, 2025), integrando el modelo asíncrono y reduciendo cambios de contexto.[^2_3]
- **Benchmarks típicos** reportan: throughput cercano a línea en 10 Gbps con `sendfile`/`MSG_ZEROCOPY`, caída de uso de CPU de ~85% a ~25–30%, y latencia reducida (p. ej., de ~45 ms a ~10–12 ms en ciertos tests).[^2_3]

**Mejora práctica:** para tensores medianos/grandes, usar `sendmsg(..., MSG_ZEROCOPY)` o `io_uring` send_zc sobre buffers pre-asignados (y, si es posible, memoria compartida) reduce drásticamente la latencia de transmisión y libera CPU para cómputo.[^2_4][^2_3]

### RX zero-copy y buffers registrados

- **ZC Rx en `io_uring`** coloca payloads directamente en regiones de memoria registradas por el usuario, eliminando la copia kernel→usuario en recepción.[^2_3]
- Esto es clave en pipelines bidireccionales: si ambos lados usan buffers registrados y zero-copy TX/RX, el camino de datos evita casi todas las copias del kernel.[^2_3]


## 2) Formatos de serialización “zero-copy” y alternativas a JSON/Protobuf

Si el problema principal son los **15–40 ms por serializar/deserializar**, la mayor ganancia viene de **no serializar** o usar formatos que permitan lectura sin copia.

### Apache Arrow IPC (tensores y tablas)

- **Arrow IPC** está diseñado para ser **predominantemente zero-copy**: el formato en disco/red coincide con el formato en memoria, permitiendo mmap y lectura sin deserializar.[^2_6][^2_7][^2_8]
- Soporta **tensores** como mensajes IPC con cuerpo alineado y metadatos, y ofrece APIs (`write_tensor`/`read_tensor`) para intercambio eficiente.[^2_9][^2_10]
- En escenarios de memoria compartida distribuida, se han extendido las APIs IPC para enviar solo el descriptor y referenciar datos en memoria compartida, evitando copiar el payload entre nodos.[^2_11][^2_12]

**Mejora práctica:** reemplazar JSON/Protobuf por **Arrow IPC + memoria compartida** (o mmap) elimina la fase de traducción de formato y permite acceso zero-copy en el receptor.[^2_8][^2_11]

### Cap’n Proto y FlatBuffers

- **Cap’n Proto** destaca por **serialización rápida y deserialización zero-copy**, aunque en algunos benchmarks de acceso/lectura queda por detrás de otros frameworks zero-copy.[^2_13]
- **FlatBuffers** ofrece **lectura zero-copy** (acceso directo a buffers binarios con offsets), con escrituras más lentas y un ecosistema menos amplio que Protobuf.[^2_2]

**Cuándo usarlos:** si necesitas esquemas evolutivos y RPC con lecturas frecuentes sin copiar, FlatBuffers/Cap’n Proto son superiores a JSON/Protobuf; si puedes acordar un layout fijo (como Arrow), Arrow IPC suele ser más directo para tensores.[^2_2][^2_13]

## 3) RDMA / GPUDirect RDMA (RoCE e InfiniBand) para clusters GPU

En sistemas distribuidos de ML/LLM, el cuello de botella de comunicación domina sobre el cómputo; ahí el SOTA es **bypassear CPU y kernel** con RDMA.

### GPUDirect RDMA sobre RoCEv2 / InfiniBand

- **RDMA** transfiere datos directamente entre regiones de memoria de distintas máquinas, sin pasar por CPU ni kernel, logrando latencias de pocos microsegundos y cientos de Gbps sostenidos.[^2_14][^2_15]
- **GPUDirect RDMA** permite DMA directo entre **VRAM de GPU y la NIC**, evitando copias GPU→CPU→red; en clusters RoCE bien afinados, operaciones All-Reduce de ~256 KB pueden lograr **< 3 µs** por transferencia.[^2_16][^2_1]
- Benchmarks en clusters GPU muestran que configurar RDMA sobre Ethernet (RoCE) puede reducir tiempos de entrenamiento de 5 h a ~1 h 40 min (factor ~3) respecto a TCP/IP tradicional.[^2_17]

**Mejora práctica:** en inferencia o entrenamiento distribuido con paralelismo de tensores, usar **NCCL + GPUDirect RDMA (RoCE/InfiniBand)** elimina la serialización en host y las copias intermedias, atacando de raíz la latencia de comunicación.[^2_15][^2_18][^2_1]

## 4) Pipelines híbridos: zero-copy local + RDMA entre nodos

Un patrón SOTA en sistemas de producción es:

- **Intra-nodo:** tensores en **memoria compartida** con Arrow IPC o buffers planos; envío local vía `vmsplice`/`splice` o `MSG_ZEROCOPY`/`io_uring` entre procesos.[^2_11][^2_3]
- **Inter-nodo:** cuando hay que cruzar la red, usar **RDMA** (RoCE/InfiniBand) con buffers registrados y, si es posible, **GPUDirect** para evitar pasar por CPU.[^2_18][^2_1]
- **Protocolo mínimo:** encabezado ligero (shape, dtype, strides) + payload binario; sin JSON/Protobuf, solo metadatos esenciales.[^2_10][^2_1]

Esto combina las ventajas de zero-copy en el host con latencia ultrabaja en la red, erradicando el overhead de 15–40 ms por mensaje que introduce la serialización clásica.[^2_1][^2_11]

## 5) Mejoras recientes y tendencias (2024–2026)

- **`io_uring` ZC Rx (Linux 6.15, 2025)** cierra el camino zero-copy en recepción, complementando send_zc y reduciendo aún más latencia y CPU.[^2_3]
- **Extensiones de Arrow para memoria compartida distribuida** permiten “serializar solo el descriptor” y referenciar datos en memoria global, evitando copiar el tensor entre nodos dentro de un cluster.[^2_12][^2_11]
- **Afinamiento de RoCE (PFC + ECN/DCQCN)** en clusters GPU es ahora estándar para lograr latencias predecibles y alto throughput en colectivos NCCL.[^2_15][^2_18]
- **Benchmarks de TCP con mejoras del kernel** (p. ej., optimizaciones de throughput en WAN) muestran ganancias de hasta ~35% en ciertos escenarios, pero siguen muy por detrás de RDMA en latencia pequeña.[^2_19]


## 6) Recomendación concreta para “erradicar” el cuello de botella

Si tu objetivo es eliminar los **∼15–40 ms por mensaje**:

1. **Abandona JSON/Protobuf para tensores:** adopta un layout binario fijo o **Arrow IPC** con memoria compartida/mmap.[^2_8][^2_10]
2. **Habilita zero-copy en el host:** usa `MSG_ZEROCOPY` o `io_uring` send_zc/ZC Rx con buffers registrados; para pipes locales, `vmsplice`/`splice`.[^2_4][^2_3]
3. **En clusters GPU/ML:** migra a **RDMA (RoCE/InfiniBand) + GPUDirect RDMA** y NCCL para colectivos; esto lleva la latencia de transferencia a microsegundos.[^2_18][^2_1][^2_15]
4. **Coordina esquemas:** emisor y receptor deben acordar formato (shape/dtype/strides) para evitar cualquier deserialización costosa.[^2_10][^2_1]

Si me dices tu stack (lenguaje, SO, si hay GPUs y tipo de red), puedo proponer una arquitectura concreta y un ejemplo de código (p. ej., Arrow IPC + `io_uring` en Linux, o NCCL + GPUDirect RDMA en cluster).

<span style="display:none">[^2_20][^2_21][^2_22][^2_23][^2_24][^2_25][^2_26][^2_27][^2_28]</span>

<div align="center">⁂</div>

[^2_1]: https://mohashari.github.io/implementing-real-time-tensor-parallelism-rdma-rocev2-distributed-llm-inference/

[^2_2]: https://lik.ai/guides/data-serialization-formats/

[^2_3]: https://coderivers.org/blog/efficient-linux-sockets-dma-zero-copy/

[^2_4]: https://docs.kernel.org/networking/msg_zerocopy.html

[^2_5]: https://docs.kernel.org/translations/zh_CN/networking/msg_zerocopy.html

[^2_6]: https://arrow.apache.org/docs/cpp/api/ipc.html

[^2_7]: https://arrow.apache.org/docs/cpp/ipc.html

[^2_8]: https://arrow.apache.org/faq/

[^2_9]: https://arrow.apache.org/docs/python/api/ipc.html

[^2_10]: https://arrow.apache.org/docs/format/Other.html

[^2_11]: https://arxiv.org/pdf/2404.03030.pdf

[^2_12]: https://arxiv.org/html/2504.06151v1

[^2_13]: https://david.kolo.ski/blog/rkyv-is-faster-than/

[^2_14]: https://www.vcluster.com/blog/gpu-cluster-networking-infiniband-roce

[^2_15]: https://ai-infrastructure.net/rdma-roce-tuning/

[^2_16]: https://sivaro.in/articles/your-gpu-cluster-is-only-as-fast-as-its-slowest-packet/

[^2_17]: https://developers.redhat.com/articles/2025/04/29/accelerate-model-training-openshift-ai-nvidia-gpudirect-rdma

[^2_18]: https://docs.coreweave.com/products/networking/hpc-interconnect/use-gpudirect-rdma-roce

[^2_19]: https://fasterdata.es.net/assets/INDIS_2024_final.pdf

[^2_20]: https://cs.stanford.edu/~keithw/sigcomm2024/sigcomm24-final246-acmpaginated.pdf

[^2_21]: https://science.lpnu.ua/sites/default/files/journal-paper/2024/dec/36976/vse-1-6.pdf

[^2_22]: https://science.lpnu.ua/sites/default/files/journal-paper/2024/dec/36976/1-acps-9-2-maltsev1-89-94.pdf

[^2_23]: https://arrow.apache.org/docs/3.0/cpp/api/ipc.html

[^2_24]: https://arrow.apache.org/docs/8.0/

[^2_25]: https://github.com/apache/arrow

[^2_26]: https://learn.padho.ai/wiki/zero-copy-sendfile-splice-mmap

[^2_27]: https://crackingwalnuts.com/linux/zero-copy

[^2_28]: https://kernel-internals.org/io/splice-sendfile/

