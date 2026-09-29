<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

## Evaluación ejecutiva

La propuesta V900 es **técnicamente plausible**, pero no erradica por sí sola los cuellos de botella: desplaza el problema desde la red hacia la **distorsión del embedding, el coste de proyección, la decodificación, la congestión TCP y la sincronización entre productor y consumidor**.

Hay dos correcciones importantes:

1. La cifra de **1,5 Gbit/s** solo es correcta bajo ciertos supuestos de representación.
2. `sendfile()` no es la solución general para tensores generados en RAM: está optimizado principalmente para transferir datos desde archivos hacia sockets. Para buffers de usuario convienen `MSG_ZEROCOPY`, `io_uring`, `splice/vmsplice` o, si hay GPU, **GPUDirect RDMA**.

## 1. Verificación del ancho de banda

Para un tensor de dimensión $D=3072$ a 60 FPS:


| Representación | Cálculo | Tráfico bruto |
| :-- | --: | --: |
| FP32 | $3072 \times 4 \times 60$ | 5,90 Mbit/s |
| FP16/BF16 | $3072 \times 2 \times 60$ | 2,95 Mbit/s |
| INT8 | $3072 \times 1 \times 60$ | 1,47 Mbit/s |
| 3072 valores FP32 por muestra con batch 1024 | $3072 \times 4 \times 1024 \times 60$ | 6,04 Gbit/s |

Por tanto, **1,5 Gbit/s corresponde aproximadamente a 3072 valores INT8 por muestra a 60 FPS**, no a un tensor FP32 individual. Si el tensor representa un lote, una secuencia temporal o varios tokens, hay que incluir explícitamente esos factores:

$$
B_{\text{red}} =
D \cdot b \cdot F \cdot S \cdot Q \cdot (1+\eta)
$$

donde:

- $D$: dimensión del vector.
- $b$: bytes por elemento.
- $F$: frecuencia de actualización.
- $S$: tamaño de lote o número de vectores simultáneos.
- $Q$: número de streams, capas o participantes.
- $\eta$: overhead de protocolo, cabeceras y retransmisiones.

La primera acción recomendada es sustituir la cifra fija de 1,5 Gbit/s por este modelo paramétrico y medir el **p99**, no solo el promedio.

## 2. Evaluación de la proyección 3072 → 1536

La proyección aleatoria puede preservar distancias de una variedad suave con alta probabilidad, pero la garantía no depende únicamente de que se reduzca la dimensión a la mitad. Depende de:

- dimensión intrínseca $K$ de la variedad;
- volumen y complejidad geométrica;
- número de muestras;
- número de puntos o pares que deben preservarse;
- condición geométrica y curvatura;
- distribución real de los tensores;
- semilla y matriz de proyección.

El trabajo de Baraniuk–Wakin establece condiciones bajo las cuales una proyección aleatoria preserva distancias euclídeas y geodésicas, pero **no implica automáticamente que $M=1536$ garantice $\Delta_{\max}<0.08$** para cualquier tensor de dimensión 3072. Esa afirmación necesita validación empírica y, preferiblemente, una cota teórica específica para el conjunto de datos.[^1_1][^1_2]

Además, si el receptor debe reconstruir el vector original, la proyección no es suficiente en general. Hay que distinguir dos escenarios:

### Cálculo directamente en el espacio proyectado

Es la opción más sólida. El modelo o algoritmo debe entrenarse o calibrarse para aceptar:

$$
y = \Phi x
$$

En este caso no se intenta reconstruir $x$, sino que se calcula sobre $y$. El objetivo debe medirse en términos de degradación de la tarea:

$$
\Delta_{\text{task}} =
\left| f(x) - \tilde f(\Phi x) \right|
$$

Esto suele ser preferible a exigir una reconstrucción casi exacta.

### Recuperación del tensor original

Para reconstruir $x$ desde $\Phi x$, hacen falta hipótesis adicionales, por ejemplo:

- $x$ es disperso o compresible;
- $x$ pertenece a una variedad de baja dimensión;
- existe un decodificador aprendido;
- se dispone de información lateral;
- se utiliza un esquema de compresión específico.

En ese caso, debe evaluarse el error de reconstrucción:

$$
\epsilon_x =
\frac{\lVert x-\hat{x}\rVert_2}{\lVert x\rVert_2}
$$

y no únicamente la preservación de distancias.

## 3. Soluciones SOTA para el cuello de botella de red

La mejor arquitectura depende de si se transmiten activaciones, embeddings, KV cache o tensores entre GPUs. Las alternativas actuales son:


| Solución | Ahorro o beneficio principal | Cuándo usarla | Riesgos |
| :-- | :-- | :-- | :-- |
| FP8/INT8 | 2–4× menos tráfico que FP16 | Activaciones y KV cache | Error de cuantización |
| INT4 con escalas por grupo | 4–8× frente a FP16 | Modelos tolerantes a cuantización | Mayor degradación |
| Proyección aprendida | Reduce dimensión optimizando la tarea | Embeddings y features | Requiere entrenamiento conjunto |
| Compresión residual | Envía solo cambios entre frames | Streams temporales | Pérdida ante cambios bruscos |
| Top-k/sparsificación | Transmite solo componentes relevantes | Activaciones dispersas | Overhead de índices |
| Compresión entropía | Reduce bits adicionales | Datos con distribución estable | Coste de CPU y latencia |
| RDMA/RoCE/InfiniBand | Menor latencia y menos copias | Centro de datos | No es residencial |
| GPUDirect RDMA | GPU ↔ NIC sin pasar por RAM/CPU | Multi-GPU o multi-nodo | Requisitos estrictos de hardware |

Para despliegues con GPU y red especializada, GPUDirect RDMA permite que el adaptador de red acceda directamente a la memoria de la GPU, evitando copias mediante la memoria del host y reduciendo la intervención de la CPU. NVIDIA documenta soporte mediante InfiniBand y RoCE, con requisitos de hardware, controlador y topología PCIe.[^1_3][^1_4][^1_5]

Para inferencia, conviene priorizar **cuantización y reducción semántica antes que una proyección aleatoria genérica**. TensorRT-LLM incorpora cuantización FP8, FP4, INT4 e INT8, además de KV cache cuantizada y paged KV caching. En particular, NVIDIA señala que FP8 para KV cache puede reducir memoria y permitir lotes mayores con menor impacto de precisión que INT8 en determinados escenarios.[^1_6][^1_7][^1_8]

## 4. ¿Es correcta la solución zero-copy?

La idea es correcta en principio, pero la selección de API debe ajustarse al origen del buffer.

### Linux

- `sendfile()` es apropiado cuando el origen es un archivo o una región gestionada por el kernel.
- `vmsplice()` puede introducir páginas de memoria de usuario en una tubería, pero exige controlar cuidadosamente la vida útil y modificación de esas páginas.
- `splice()` permite encadenar descriptores mediante una tubería.
- `MSG_ZEROCOPY` es más adecuado para enviar buffers de usuario directamente a un socket, con notificaciones de finalización mediante la cola de errores.
- `io_uring` puede reducir llamadas al sistema y facilitar operaciones asíncronas, aunque no elimina necesariamente todas las copias.
- Para GPU, la opción superior suele ser RDMA/GPUDirect, no TCP zero-copy convencional.

Linux ofrece estas rutas de zero-copy, pero cada una tiene restricciones distintas sobre memoria, archivos, páginas fijadas, finalización y soporte del dispositivo.[^1_9][^1_10][^1_11]

### Windows

`TransmitFile()` está orientado principalmente a archivos. Para tensores que ya existen en memoria, suele ser más apropiado:

- `WSASend()` con varios buffers;
- IOCP para finalización asíncrona;
- buffers registrados o preasignados;
- Winsock Registered I/O, cuando el hardware y el diseño lo justifican;
- RDMA sobre RoCE/InfiniBand en entornos compatibles.

El objetivo no debe ser únicamente “cero copias”, sino reducir el coste total:

$$
T_{\text{total}} =
T_{\text{proyección}}+
T_{\text{cuantización}}+
T_{\text{serialización}}+
T_{\text{copias}}+
T_{\text{kernel}}+
T_{\text{red}}+
T_{\text{cola}}+
T_{\text{deserialización}}
$$

Eliminar una copia puede no mejorar el p99 si la compresión, la congestión o la espera de sincronización dominan el tiempo.

## 5. Arquitectura recomendada

Para un sistema V900 de baja latencia, propondría este pipeline:

1. **Representación compacta local:** FP8 o INT8, con escala por tensor, canal o grupo.
2. **Proyección aprendida o estructurada:** sustituir la matriz aleatoria fija por una proyección entrenada para preservar la métrica de la tarea.
3. **Formato binario fijo:** cabecera pequeña con versión, tamaño, escala, semilla o identificador de proyección, timestamp y checksum.
4. **Buffers preasignados:** ring buffers lock-free, memoria alineada y doble o triple buffering.
5. **Transporte:** QUIC/UDP con control de pérdidas si se opera sobre redes residenciales; TCP/RDMA si la red es controlada.
6. **Zero-copy apropiado al origen:** `MSG_ZEROCOPY` o `io_uring` para RAM; GPUDirect RDMA para memoria GPU.
7. **Cálculo en el espacio comprimido:** evitar reconstruir el tensor salvo que sea estrictamente necesario.
8. **Control adaptativo:** cambiar entre FP8, INT8, INT4, dimensión proyectada y frecuencia de envío según ancho de banda y error observado.
9. **Telemetría:** medir throughput, p50/p95/p99 de latencia, jitter, pérdida, retransmisiones, CPU, GPU, copias DMA y error de tarea.

Una política adaptativa sencilla puede elegir el modo $m$ que minimice:

$$
J(m)=
\lambda_b B(m)+
\lambda_l L_{p99}(m)+
\lambda_e E_{\text{task}}(m)+
\lambda_c C_{\text{CPU}}(m)
$$

sujeto a:

$$
E_{\text{task}}(m)\leq E_{\max},
\qquad
L_{p99}(m)\leq L_{\max}
$$

## Veredicto

La proyección 3072→1536 puede ser una buena optimización, pero la garantía $\Delta_{\max}<0.08$ debe demostrarse para el conjunto concreto de tensores y la tarea concreta. No la presentaría como garantía general derivada de Baraniuk–Wakin.

La solución más robusta sería:

**FP8/INT8 + proyección aprendida validada + cálculo directamente en el embedding + buffers binarios preasignados + zero-copy adecuado al origen + RDMA/GPUDirect cuando exista infraestructura de centro de datos.**

En conexiones residenciales, RDMA normalmente no será viable; ahí conviene priorizar cuantización, actualización diferencial, reducción de frecuencia, tolerancia a pérdida y transporte basado en datagramas.

<span style="display:none">[^1_12][^1_13][^1_14][^1_15][^1_16][^1_17][^1_18][^1_19][^1_20][^1_21][^1_22][^1_23][^1_24][^1_25][^1_26][^1_27][^1_28][^1_29][^1_30]</span>

<div align="center">⁂</div>

[^1_1]: http://www.cs.columbia.edu/~verma/classes/uml/ref/dim_redux_nldr_jl_mfd_baraniuk_wakin.pdf

[^1_2]: https://people.mines.edu/mwakin/research/

[^1_3]: https://networking-docs.nvidia.com/gpudirectrdma/

[^1_4]: https://developer.nvidia.com/gpudirect?trk=public_post_comment-text

[^1_5]: https://docs.nvidia.com/cuda/gpudirect-rdma/

[^1_6]: https://developer.nvidia.com/tensorrt-llm

[^1_7]: https://nvidia.github.io/TensorRT-LLM/latest/features/quantization.html

[^1_8]: https://nvidia.github.io/TensorRT-LLM/blogs/quantization-in-TRT-LLM.html

[^1_9]: https://netdevconf.info/2.1/papers/debruijn-msgzerocopy-talk.pdf

[^1_10]: https://netdevconf.info/0x14/pub/slides/62/Implementing TCP RX zero copy.pdf

[^1_11]: https://kernel-internals.org/io/splice-sendfile/

[^1_12]: https://docs.nvidia.com/dsx/ncp/inference-ra/home

[^1_13]: https://en.wikipedia.org/wiki/Zero-copy

[^1_14]: https://www.pure.ed.ac.uk/ws/portalfiles/portal/30369902/1512.06906v3.pdf

[^1_15]: https://crackingwalnuts.com/linux/zero-copy

[^1_16]: https://coderivers.org/blog/efficient-linux-sockets-dma-zero-copy/

[^1_17]: http://archive.dimacs.rutgers.edu/Workshops/Advances/Slides/baraniuk.pdf

[^1_18]: https://latest2all.com/tutorial/advanced-zero-copy-networking-and-tail-call-optimization-zero-copy-kernel.html

[^1_19]: https://vabs.github.io/2026/05/08/zero-copy-networking-sendfile/

[^1_20]: https://kernel-internals.org/vfs/splice-sendfile/

[^1_21]: https://blog.prompt20.com/posts/disaggregated-inference/

[^1_22]: https://network.nvidia.com/products/GPUDirect-RDMA/

[^1_23]: https://networking-docs.nvidia.com/gpudirectrdma/installation

[^1_24]: https://docs.nvidia.com/cuda/pdf/GPUDirect_RDMA.pdf

[^1_25]: https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-rdma.html

[^1_26]: https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/24.3.0/gpu-operator-rdma.html

[^1_27]: https://docs.nvidia.com/ai-enterprise/release-8/latest/infra-software/vgpu/features/gpudirect.html

[^1_28]: https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/23.6.2/gpu-operator-rdma.html

[^1_29]: https://nvidia.github.io/TensorRT-LLM/features/quantization.html

[^1_30]: https://docs.nvidia.com/tensorrt/index.html


---

## Tesis SOTA

Para V900, la arquitectura de vanguardia no sería simplemente:

$$
3072 \rightarrow 1536 \rightarrow \text{TCP zero-copy}
$$

La estrategia SOTA sería:

$$
\text{tensor GPU}
\rightarrow
\text{transformación entrenada}
\rightarrow
\text{FP8/INT8 adaptativo}
\rightarrow
\text{paquetización parcial}
\rightarrow
\text{transporte con pérdidas controladas}
\rightarrow
\text{cómputo sin reconstrucción}
$$

La proyección lineal fija debe pasar a ser solo una opción de respaldo. En comunicaciones de tensores modernas, la mayor ganancia suele provenir de la combinación de **cuantización fina, transformación de distribución, sparsificación, actualización diferencial y transporte adaptativo**.

## 1. Reemplazar la proyección fija

### Problema de $3072 \rightarrow 1536$

Una matriz ortogonal fija:

$$
y=\Phi x,\qquad \Phi\in\mathbb{R}^{1536\times3072}
$$

reduce el tráfico al 50%, pero no necesariamente reduce el coste de cálculo global. El emisor debe ejecutar la multiplicación, el receptor puede necesitar un decodificador y la garantía geométrica no se traduce automáticamente en precisión de inferencia.

Además, para una matriz densa, la proyección requiere aproximadamente:

$$
3072 \times 1536 \approx 4.7 \times 10^6
$$

multiplicaciones por vector. Si se procesan muchos vectores por segundo, la proyección puede convertirse en el nuevo cuello de botella.

### Alternativas superiores

#### Proyección estructurada

Usar una transformación rápida, como:

$$
\Phi = P_2 H D P_1
$$

donde:

- $D$ es una matriz diagonal de signos;
- $H$ es Hadamard o una transformación rápida similar;
- $P_1,P_2$ son muestreos o permutaciones.

Esto puede reducir el coste de $O(DM)$ a aproximadamente $O(D\log D)$, aunque requiere validar la distorsión y la compatibilidad con GPU.

#### Proyección aprendida

Entrenar un codificador $E_\theta$ y un decodificador $G_\phi$:

$$
z=E_\theta(x),\qquad \hat{x}=G_\phi(z)
$$

Pero el objetivo no debe ser solo minimizar:

$$
\lVert x-\hat{x}\rVert_2
$$

sino preservar la salida de la tarea:

$$
\mathcal{L}
=
\lambda_x\lVert x-\hat{x}\rVert_2^2
+
\lambda_f\mathcal{L}_{\text{task}}(f(x),f(\hat{x}))
+
\lambda_b R(z)
$$

Esto permite que el codificador descarte información irrelevante para la inferencia.

Los sistemas de compresión aprendida de activaciones ya muestran que un autoencoder entrenado puede superar a PCA, SVD y autoencoders lineales en determinados escenarios WAN; un trabajo reciente reporta hasta 4,96× de mejora de latencia extremo a extremo bajo condiciones representativas de 10 Gbit/s y 10 ms RTT. Ese resultado es específico del sistema y no debe extrapolarse sin benchmark propio.[^2_1]

## 2. Cuantización: prioridad sobre la reducción geométrica

Si el tensor actual es FP16, pasar de 3072 a 1536 produce 2× de reducción. Pasar de FP16 a FP8 también produce 2×, pero conserva la dimensión completa:

$$
3072\cdot 2\ \text{bytes}
\rightarrow
3072\cdot 1\ \text{byte}
$$

Una combinación de ambas técnicas podría producir:

$$
3072\ \text{FP16}
\rightarrow
1536\ \text{FP8}
$$

lo que equivale a 4× menos bytes que el original.

### Cuantización recomendada

No usaría una escala única para todo el tensor salvo que la distribución sea muy estable. La jerarquía recomendada es:

1. escala por tensor;
2. escala por canal;
3. escala por grupo de 32–128 elementos;
4. tratamiento separado de outliers;
5. residual de alta precisión para los componentes críticos.

Para un grupo $g$:

$$
s_g=\frac{\max_{i\in g}|x_i|}{q_{\max}}
$$

$$
q_i=\operatorname{round}\left(\frac{x_i}{s_g}\right)
$$

y la reconstrucción:

$$
\hat{x}_i=s_gq_i
$$

La cuantización fina de activaciones comunicadas en tensor parallelism ha mostrado reducciones aproximadas de 3,5–4,5× y mejoras de hasta 2× en TTFT en determinados modelos y configuraciones.[^2_2][^2_3]

### FP8 adaptativo

La cuantización FP8 puede fallar cuando hay outliers persistentes. Una solución SOTA es aplicar una transformación antes de cuantizar:

$$
u=Hx
$$

donde $H$ es una transformación tipo Hadamard que redistribuye la energía entre canales, seguida de cuantización FP8. Un trabajo reciente propone una escala Hadamard adaptativa y escalas duales para evitar que valores extremos queden fuera del rango representable durante comunicaciones frecuentes.[^2_4]

La secuencia sería:

$$
x
\rightarrow
\text{Hadamard/adaptación}
\rightarrow
\text{FP8}
\rightarrow
\text{red}
\rightarrow
\text{FP8}^{-1}
\rightarrow
\text{transformación inversa}
$$

Esto es más prometedor que proyectar aleatoriamente si el receptor debe continuar ejecutando capas neuronales sensibles.

## 3. FP4, INT4 y formatos microscalados

Para ancho de banda extremadamente limitado, FP4 o INT4 pueden superar a FP8. Sin embargo, no deben aplicarse indiscriminadamente a todo el tensor.

La configuración recomendable es híbrida:


| Componente | Formato sugerido |
| :-- | :-- |
| Activaciones normales | FP8 |
| Canales con outliers | FP16/BF16 o FP8 con escala separada |
| Residual | INT8 o FP16 |
| KV cache | FP8; FP4 solo tras validación |
| Índices y metadatos | Enteros compactos |
| Señales críticas de control | FP16 o FP32 |

En modelos MoE, trabajos recientes exploran MXFP4 para activar y comunicar tensores en operaciones All-to-All, mientras mantienen cálculos centrales en FP8. El beneficio depende mucho de la distribución de las activaciones, del hardware y de la disponibilidad de soporte nativo.[^2_5]

La regla práctica es:

- FP8: primera opción para producción.
- INT8: opción robusta y sencilla.
- INT4/FP4: modo agresivo, con calibración y fallback.
- Proyección dimensional: solo si la tarea tolera pérdida semántica.


## 4. Compresión temporal y actualización diferencial

Si los tensores consecutivos son correlacionados, transmitir cada tensor completo es ineficiente. Definir:

$$
r_t=x_t-\hat{x}_{t|t-1}
$$

y transmitir solo el residual:

$$
q_t=Q(r_t)
$$

El receptor reconstruye:

$$
\hat{x}_t=\hat{x}_{t|t-1}+D(q_t)
$$

donde $\hat{x}_{t|t-1}$ puede ser:

- el tensor anterior;
- una predicción lineal;
- un predictor GRU/TCN pequeño;
- una predicción basada en movimiento o estado;
- un modelo residual entrenado.

Debe existir un keyframe cada cierto tiempo:

$$
x_{t_k}\rightarrow \text{keyframe}
$$

para limitar la acumulación de error. El período del keyframe debe depender del error:

$$
\text{si}\quad
\lVert x_t-\hat{x}_t\rVert > \tau,
\quad\text{enviar keyframe}
$$

Esta estrategia puede proporcionar ganancias mayores que el 50% fijo cuando la señal cambia suavemente, pero empeora con cambios bruscos o pérdida de paquetes.

## 5. Sparsificación y codificación de outliers

En lugar de enviar todos los elementos cuantizados, puede transmitirse:

$$
x = x_{\text{top-k}} + r
$$

donde $x_{\text{top-k}}$ contiene los componentes de mayor magnitud. El paquete debe incluir:

- índices;
- valores;
- escala;
- máscara o codificación de índices;
- residual opcional.

El beneficio efectivo es:

$$
R_{\text{efectiva}}
=
\frac{\text{bytes originales}}
{\text{bytes de valores}+
\text{bytes de índices}+
\text{bytes de metadatos}}
$$

Por eso un “90% de sparsidad” no implica 10× de compresión si los índices dominan el paquete. La sparsificación es más atractiva cuando se emplean bloques estructurados, por ejemplo bloques de 16 o 32 elementos, porque se reduce el overhead de índices y mejora la eficiencia de GPU.

## 6. Transporte SOTA por entorno

### Red residencial o Internet público

No asumiría que TCP es óptimo para un stream de estado donde un paquete antiguo pierde valor rápidamente. Para estos datos, una arquitectura adecuada sería:

- QUIC para handshake, cifrado y control de conexión;
- QUIC DATAGRAM para actualizaciones no retransmitibles;
- stream fiable separado para keyframes y metadatos;
- secuencias, timestamps y expiración;
- FEC ligera para pérdidas moderadas;
- descarte de paquetes atrasados.

RFC 9221 define datagramas QUIC no fiables que no requieren retransmisión, manteniendo las ventajas de la conexión QUIC, como negociación criptográfica y multiplexación.[^2_6][^2_7]

El principio es:

- **datos frescos:** se pueden perder;
- **estado base:** debe llegar;
- **configuración y control:** fiable y ordenado.

No conviene retransmitir un tensor de $t-3$ cuando ya se está procesando $t$.

### Centro de datos con GPU

Para comunicación entre GPU, utilizaría NCCL antes que construir un protocolo TCP propio. NCCL ofrece operaciones como AllReduce, AllGather, ReduceScatter y All-to-All, con conciencia de topología y soporte para NVLink, PCIe, InfiniBand, RoCE e IP sockets.[^2_8][^2_9]

Para tráfico GPU ↔ NIC:

$$
\text{HBM GPU}
\rightarrow
\text{NIC}
\rightarrow
\text{red}
\rightarrow
\text{NIC}
\rightarrow
\text{HBM GPU}
$$

GPUDirect RDMA está diseñado precisamente para permitir acceso directo entre dispositivos de red y memoria de GPU, evitando copias innecesarias por la memoria del host.[^2_10][^2_11][^2_12]

### Host CPU con Linux

Para buffers de usuario:

- activar `SO_ZEROCOPY`;
- enviar con `MSG_ZEROCOPY`;
- procesar notificaciones de finalización;
- mantener vivos los buffers hasta la confirmación;
- utilizar `io_uring` para integración asíncrona;
- probar `io_uring_prep_send_zc()`.

La documentación del kernel indica que `MSG_ZEROCOPY` evita copias en envíos de sockets y es compatible con TCP, UDP y VSOCK, pero el coste de fijar páginas y las notificaciones de finalización hacen que no siempre sea más rápido para mensajes pequeños.[^2_13][^2_14]

Para recepción, `io_uring` incorpora mecanismos de zero-copy receive que pueden colocar datos directamente en memoria de usuario en escenarios compatibles.[^2_15]

### Windows

La ruta comparable sería:

- buffers preasignados;
- `WSASend()` con scatter/gather;
- IOCP;
- Registered I/O cuando esté disponible;
- RDMA si la infraestructura lo permite.

`TransmitFile()` no debería presentarse como la solución general para tensores generados dinámicamente en RAM.

## 7. Tamaño de paquete y fragmentación

Un tensor no debe enviarse como un único datagrama grande. El sistema debe fragmentarlo en unidades suficientemente pequeñas para evitar fragmentación IP y facilitar el descarte selectivo:

$$
\text{tensor}
\rightarrow
\{p_0,p_1,\ldots,p_n\}
$$

Cada fragmento debe contener:

- `stream_id`;
- `frame_id`;
- `chunk_id`;
- `chunk_count`;
- timestamp;
- formato;
- escala;
- checksum;
- prioridad;
- número de versión del modelo o proyección.

La unidad de retransmisión debe ser el chunk, no el tensor completo. Si llega tarde, debe descartarse según:

$$
t_{\text{ahora}}-t_{\text{timestamp}}>\text{deadline}
$$

Para datos en tiempo real, un tensor incompleto y reciente puede ser más útil que un tensor completo pero atrasado.

## 8. Esquema de control adaptativo

El emisor debe elegir modo de compresión según condiciones observadas. Un conjunto práctico de modos sería:


| Modo | Formato | Dimensión | Uso |
| :-- | :-- | --: | :-- |
| P0 | FP16 | 3072 | Máxima calidad |
| P1 | FP8 | 3072 | Producción normal |
| P2 | INT8 por grupo | 3072 | Red limitada |
| P3 | FP8 | 1536 | Red muy limitada |
| P4 | INT4/FP4 | 1536–3072 | Modo extremo |
| P5 | Residual INT8 | Variable | Alta correlación temporal |

La decisión puede optimizar:

$$
J_m =
\alpha L_{p99}(m)+
\beta B(m)+
\gamma E_{\text{task}}(m)+
\delta C_{\text{encode}}(m)
$$

sujeto a:

$$
L_{p99}(m)\leq L_{\max}
$$

y:

$$
E_{\text{task}}(m)\leq E_{\max}
$$

El controlador debe usar métricas de ventana corta, no una media larga:

- ancho de banda disponible;
- pérdida;
- jitter;
- RTT;
- edad del último tensor válido;
- error semántico;
- ocupación del buffer;
- tiempo de codificación.


## 9. Revisión de la garantía $\Delta_{\max}<0.08$

La garantía debe dividirse en tres métricas diferentes:

### Distorsión geométrica

$$
\Delta_{\text{geom}}
=
\sup_{x\neq y}
\left|
\frac{\lVert \Phi x-\Phi y\rVert_2}
{\lVert x-y\rVert_2}
-1
\right|
$$

### Error de reconstrucción

$$
\Delta_{\text{recon}}
=
\frac{\lVert x-\hat{x}\rVert_2}
{\lVert x\rVert_2}
$$

### Error de tarea

$$
\Delta_{\text{task}}
=
\left|
f(x)-f(\hat{x})
\right|
$$

El objetivo operativo debería ser algo como:

$$
\Delta_{\text{task}}\leq 0.01
$$

o una degradación máxima previamente definida en accuracy, recall, BLEU, reward, clasificación o TTFT. Una cota geométrica de 0,08 no demuestra por sí misma una degradación de tarea inferior al 8%.

### Protocolo de validación

Debe probarse con:

- datos fuera de distribución;
- diferentes longitudes de secuencia;
- lotes pequeños y grandes;
- outliers;
- pérdida de paquetes;
- jitter;
- degradación de ancho de banda;
- cambios de versión del modelo;
- saturación de CPU y GPU.

Reportaría:

- p50, p95 y p99 de latencia;
- throughput;
- bytes por tensor;
- coste de codificación y decodificación;
- error geométrico;
- error de reconstrucción;
- degradación de tarea;
- pérdida de paquetes;
- porcentaje de frames descartados;
- energía por tensor.


## 10. Diseño recomendado para V900

### Perfil residencial

$$
\text{activación}
\rightarrow
\text{FP8 por grupo}
\rightarrow
\text{residual temporal}
\rightarrow
\text{chunking}
\rightarrow
\text{QUIC DATAGRAM}
$$

Con keyframes fiables, expiración de frames, FEC ligera y fallback a INT8.

### Perfil centro de datos

$$
\text{GPU}
\rightarrow
\text{FP8/FP4 adaptativo}
\rightarrow
\text{NCCL}
\rightarrow
\text{GPUDirect RDMA}
$$

La proyección 3072→1536 solo se activaría si los benchmarks demuestran que la reducción del tráfico compensa el coste adicional y no aumenta el p99 de inferencia.

### Perfil híbrido

$$
\text{proyección aprendida}
+
\text{cuantización por grupo}
+
\text{residual}
+
\text{transporte adaptativo}
$$

Este sería el perfil más prometedor para V900 porque combina reducción semántica, reducción numérica y reducción temporal.

## Veredicto SOTA

La propuesta original tiene una buena intuición, pero está incompleta. La versión técnicamente más fuerte sería:

1. Sustituir la proyección aleatoria fija por una transformación estructurada o aprendida.
2. Aplicar FP8/INT8 por grupo antes de reducir dimensión.
3. Reservar FP4/INT4 para el modo extremo.
4. Explotar redundancia temporal mediante residual y keyframes.
5. Usar QUIC DATAGRAM para datos perecederos sobre Internet.
6. Usar NCCL y GPUDirect RDMA dentro de centros de datos.
7. Usar `MSG_ZEROCOPY` o `io_uring` para buffers CPU en Linux.
8. Medir error de tarea, no solo distorsión geométrica.
9. Cambiar dinámicamente de modo según p99, pérdida y error.
10. Demostrar la garantía $\Delta_{\max}<0.08$ sobre el conjunto real de tensores, no asumirla por teoría general.

<span style="display:none">[^2_16][^2_17][^2_18][^2_19][^2_20][^2_21][^2_22][^2_23][^2_24][^2_25][^2_26][^2_27][^2_28][^2_29][^2_30][^2_31][^2_32][^2_33]</span>

<div align="center">⁂</div>

[^2_1]: https://www.ertza.me/files/feather/feather.pdf

[^2_2]: https://openreview.net/pdf?id=YkttwLldEb

[^2_3]: https://bohrium.dp.tech/paper/arxiv/2411.09510

[^2_4]: https://arxiv.org/html/2604.24088v1

[^2_5]: https://www.alphaxiv.org/abs/2603.02731

[^2_6]: https://datatracker.ietf.org/doc/html/rfc9221

[^2_7]: https://datatracker.ietf.org/doc/html/rfc9000

[^2_8]: https://developer.nvidia.com/blog/enabling-fast-inference-and-resilient-training-with-nccl-2-27/

[^2_9]: https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/overview.html

[^2_10]: https://networking-docs.nvidia.com/gpudirectrdma/

[^2_11]: https://developer.nvidia.com/gpudirect?trk=public_post_comment-text

[^2_12]: https://docs.nvidia.com/cuda/gpudirect-rdma/

[^2_13]: https://docs.kernel.org/networking/msg_zerocopy.html

[^2_14]: https://man7.org/linux/man-pages/man3/io_uring_prep_send_zc.3.html

[^2_15]: https://docs.kernel.org/networking/iou-zcrx.html

[^2_16]: https://datatracker.ietf.org/wg/quic/documents/

[^2_17]: https://datatracker.ietf.org/doc/rfc9221/bibtex/

[^2_18]: https://www.ietf.org/archive/id/draft-pauly-quic-datagram-03.txt

[^2_19]: https://datatracker.ietf.org/doc/html/draft-ietf-quic-datagram-06

[^2_20]: https://datatracker.ietf.org/doc/draft-ietf-quic-datagram/01/

[^2_21]: https://www.ietf.org/proceedings/103/slides/slides-103-quic-unreliable-datagram-extension-00.pdf

[^2_22]: https://users.cs.duke.edu/~mlentz/papers/llm265_micro2025.pdf

[^2_23]: https://mailarchive.ietf.org/arch/browse/quic/

[^2_24]: https://docs.kernel.org/translations/zh_CN/networking/msg_zerocopy.html

[^2_25]: https://datatracker.ietf.org/doc/html/rfc8831

[^2_26]: https://www.kernel.org/doc/html/v6.4/networking/msg_zerocopy.html

[^2_27]: https://www.kernel.org/doc/html/v4.17/networking/msg_zerocopy.html

[^2_28]: https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/usage.html

[^2_29]: https://docs.nvidia.com/deeplearning/nccl/archives/nccl_2275/user-guide/docs/overview.html

[^2_30]: https://docs.nvidia.com/deeplearning/nccl/archives/nccl_2127/user-guide/docs/overview.html

[^2_31]: https://images.nvidia.com/events/sc15/pdfs/NCCL-Woolley.pdf

[^2_32]: https://docs.nvidia.com/deeplearning/nccl/archives/nccl_256/nccl-developer-guide/docs/overview.html

[^2_33]: https://blogs.oracle.com/linux/zero-copy-networking-in-uek6

