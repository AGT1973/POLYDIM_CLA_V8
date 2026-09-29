<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

## Evaluación

La hipótesis es **parcialmente correcta**, pero contiene una afirmación técnicamente imprecisa:

- La endianness afecta el **orden de los bytes**, no invierte los bits individualmente.
- IEEE 754 define la interpretación de los bits, pero no fija por sí solo cómo se ordenan esos bytes en memoria; al intercambiar datos binarios entre plataformas hay que especificar el orden de serialización. cite[^1_1]
- Una secuencia IEEE 754 válida interpretada con el byte order equivocado puede convertirse en un valor incorrecto, incluidos `NaN`, infinito o valores subnormales. Sin embargo, esto no ocurre necesariamente para todos los valores ni es correcto afirmar que los flotantes se convierten sistemáticamente en `NaN` y subnormales.

También conviene matizar el ejemplo de plataformas: ARM puede operar en distintos modos, pero los sistemas ARM modernos habituales no deben clasificarse automáticamente como big-endian. La propiedad relevante debe detectarse en tiempo de ejecución o en la configuración de compilación, no inferirse únicamente por la arquitectura.

## Evaluación de la solución V900

La solución propuesta es **válida y recomendable**:

> Todos los tensores PMTP en tránsito se serializan en un formato canónico explícito: IEEE 754 binary32/binary64, con orden little-endian.

Esto coincide con convenciones existentes: ONNX exige que los datos `raw_data` de ancho fijo se almacenen en little-endian y que los flotantes usen IEEE 754. cite La documentación de ONNX también muestra conversiones explícitas a little-endian para que los datos sean portables entre plataformas. cite[^1_2][^1_3]

No obstante, decir solamente “little-endian” deja algunos casos sin especificar. El contrato debe definir también:

- Tipo exacto: `float32` = IEEE 754 binary32; `float64` = IEEE 754 binary64.
- Orden de los elementos del tensor: row-major, column-major o el formato PMTP correspondiente.
- Forma, dimensiones y strides.
- Representación de `NaN`, infinitos, ceros negativos y subnormales.
- Compresión, alineación, padding y checksum.
- Versión del protocolo y tamaño total esperado.
- Qué hacer ante tipos no soportados o conversiones no exactas.


## Redacción corregida

### Bug 3: Endianness incorrecta en nodos heterogéneos

**Mecanismo de falla:**\
Si el emisor y el receptor interpretan de forma distinta el orden de bytes de los elementos binarios, los mismos cuatro u ocho bytes pueden decodificarse como otro valor IEEE 754. El resultado puede ser numéricamente incorrecto y, dependiendo de los bits resultantes, representar un número finito, cero, subnormal, infinito o `NaN`. La causa es una discrepancia de serialización, no una inversión bit a bit.

**Solución V900:**\
Definir en el contrato PMTP una representación de red independiente de la plataforma:

1. `float32`: IEEE 754 binary32.
2. `float64`: IEEE 754 binary64.
3. Serialización de cada elemento en little-endian canónico.
4. Conversión explícita al formato canónico antes de transmitir.
5. Conversión explícita desde el formato canónico al formato nativo al recibir.
6. Validación de longitud, tipo, dimensiones y checksum antes de interpretar el tensor.

## Implementación segura

En C/C++, no debería transmitirse directamente la memoria de un `float` mediante un cast de puntero ni asumirse que su representación nativa es portable. Es preferible:

```cpp
uint32_t bits;
static_assert(sizeof(float) == sizeof(uint32_t));

std::memcpy(&bits, &value, sizeof(bits));

buffer[^1_0] = static_cast<uint8_t>(bits);
buffer[^1_1] = static_cast<uint8_t>(bits >> 8);
buffer[^1_2] = static_cast<uint8_t>(bits >> 16);
buffer[^1_3] = static_cast<uint8_t>(bits >> 24);
```

El receptor debe reconstruir el entero de 32 bits desde esos bytes y copiarlo de vuelta al `float`, después de validar que el tipo nativo soporta el formato requerido. Para `float64`, el mismo patrón debe utilizar 64 bits.

Si PMTP usa Protocol Buffers, los campos `fixed32` y `fixed64` ya tienen codificación little-endian en el wire format, pero eso no sustituye la especificación del significado del tensor, su forma ni sus reglas de validación. cite[^1_4]

## Pruebas que faltan

Para demostrar que el arreglo funciona sin depender de la arquitectura local, añadiría pruebas de interoperabilidad con:

- Emisor little-endian y receptor little-endian.
- Emisor big-endian simulado y receptor little-endian.
- Conversión inversa.
- Valores `0`, `-0`, `1`, `-1`, máximos y mínimos normales.
- Subnormales.
- `+∞`, `-∞`, `NaN` y distintos payloads de `NaN`.
- Tensores de dimensiones múltiples y tamaños no alineados.
- Truncamiento, bytes extra, checksum inválido y versión desconocida.

El criterio principal debe ser comparar los **bits serializados**, no solo la igualdad aritmética, porque `NaN` no es igual a sí mismo y algunas plataformas pueden canonicalizar sus payloads.

**Veredicto:** conservar la solución V900, pero reemplazar “invertidos bit a bit” por “interpretados con un orden de bytes incompatible” y ampliar el contrato para fijar IEEE 754, tipos, layout, valores especiales y validaciones.

<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_5][^1_6][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://ethw.org/w/images/5/54/Handbook_Floating_Point_Chapter_3.pdf

[^1_2]: https://javadoc.io/static/com.yahoo.vespa/config-model/8.221.29/onnx/Onnx.TensorProtoOrBuilder.html

[^1_3]: http://onnx.ai/ir-py/api/generated/onnx_ir.TensorProtocol.html

[^1_4]: https://docs.ros.org/en/api/grpc/html/protobuf_2python_2google_2protobuf_2internal_2decoder_8py_source.html

[^1_5]: https://onnx.ai/onnx/intro/python.html

[^1_6]: https://onnx.ai/onnx/api/serialization.html

[^1_7]: http://onnx.ai/ir-py/api/generated/onnx_ir.Tensor.html

[^1_8]: https://deepwiki.com/onnx/ir-py/3.5-tensor-serialization-and-external-data

[^1_9]: https://deepwiki.com/onnx/onnx/4.3-numpy-conversion-and-data-handling

[^1_10]: https://github.com/microsoft/onnxruntime/discussions/10338

[^1_11]: https://fossies.org/linux/onnx/onnx/onnx.proto3

[^1_12]: https://leo-gan.github.io/GLD.SerializerBenchmark/theory/401/protobuf-wire-format/

[^1_13]: https://blog.crawlex.net/blog/reverse-engineering-binary-protocols/

[^1_14]: https://systeminternals.dev/grpc/

[^1_15]: https://www.codestudy.net/blog/are-there-any-modern-platforms-with-non-ieee-c-c-float-formats/

