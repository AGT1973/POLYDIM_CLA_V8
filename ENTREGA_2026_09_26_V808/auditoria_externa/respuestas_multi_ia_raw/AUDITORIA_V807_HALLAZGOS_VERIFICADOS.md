# AUDITORÍA POLYDIM V807 — hallazgos verificados con herramienta, no solo lectura

Regla aplicada en todo este documento: cada hallazgo dice si está **VERIFICADO
(tool)** — lo compilé y/o corrí de verdad, con evidencia pegada — o
**LECTURA (bloqueado)** — lo veo en el código pero no puedo compilarlo/probarlo
en este entorno porque falta una pieza (se explica cuál en cada caso). Nunca
mezclo los dos niveles de confianza.

Herramientas usadas: g++ 13.3 (ASan/UBSan/TSan), rustc 1.75 (instalado en este
sandbox desde el repo de Ubuntu), Python 3.12. Todo corrió en Linux x86_64,
1 core. Esto importa para la sección "qué queda bloqueado".

---

## 1. VERIFICADO (tool) — Filtro Fréchet-Betti devolvía `Ok` con memoria sin inicializar

**Archivo:** `polydim_monolith.rs.txt`, función `polydim_rust_frechet_betti_filter`, líneas ~270-277.

Compilé el `.rs` original tal cual (compila limpio, sin warnings) y lo llamé
desde un arnés en C (`verificacion_frechet_harness.c`) con 5 agentes
**idénticos** (varianza exacta = 0 — el caso de un swarm que ya convergió).

Resultado real, byte a byte:

```
NativeStatus devuelto: 0  (0 = Ok)
out_result.active_swarm_count = 3452816845   <- es 0xCDCDCDCD, el veneno que puse ANTES de llamar
out_result.is_consensus_certified (byte crudo) = 0xCD  <- tambien veneno intacto
```

El struct de salida no se tocó. El llamador recibe "éxito" y lee memoria sin
inicializar como si fuera un resultado válido. El comentario `// Was
MathError` y la rama muerta `if false { return NativeStatus::MathError; }`
que quedaron en el código confirman que esto se desactivó a propósito en
algún momento, probablemente para que un test dejara de fallar.

**Fix aplicado y verificado** (`polydim_monolith_v807.rs`): en el caso de
varianza degenerada, ahora se escribe el centroide real como consenso y se
llena el struct completo con valores explícitos, en vez de cortar camino.
Corrí el mismo arnés, sin tocarle una línea, contra la versión parcheada:

```
NativeStatus devuelto: 0  (0 = Ok)
out_consensus_vector: 1.00 1.00 1.00 1.00   <- correcto (centroide real)
out_result.active_swarm_count = 5           <- correcto, no veneno
out_result.is_consensus_certified = 0x01    <- true, correcto
```

**Pendiente, no incluido en el parche:** `INSTANCE_STATE` sigue sin tener
forma de resetearse tras un panic — un solo panic en cualquier llamada
envenena el motor para el resto de la vida del proceso. No lo toqué porque
la decisión de si eso debe ser recuperable o fatal-por-diseño es tuya, no
mía; te dejo la función `polydim_reset_engine_state()` como sugerencia en el
código, comentada, para que decidas.

---

## 2. VERIFICADO (tool) — Stiefel/CholQR: división por cero real con input rank-deficient

**Archivo:** `polydim_stiefel_v805.cpp.txt`, función `stiefel_cholqr`.

Compilé el `.cpp` original con `-fsanitize=undefined,float-divide-by-zero` y
lo alimenté con 2 columnas **idénticas** (rank-deficient — exactamente el
mismo tipo de caso degenerado que rompió el hallazgo anterior en Rust).

```
polydim_stiefel_orig.cpp:63:44: runtime error: division by zero
output[] = 0.070014 ... -nan -nan -nan -nan -nan -nan -nan -nan
*** NaN/Inf PRODUCIDO ***
```

Dos problemas reales, no uno:
- El reporte 04 dice "se añadió regularización de Tikhonov (+εI) para evitar
  NaN". Eso no está en el código: lo único que hay es `sqrt(max(0,x))`, que
  evita `sqrt` de negativo pero no evita que la diagonal de Cholesky termine
  en 0 para columnas linealmente dependientes.
- La función es `void`. No hay ningún canal para que el llamador se entere
  de que pasó esto. El NaN se propaga en silencio al resto del pipeline.

**Fix aplicado y verificado** (`polydim_stiefel_v805_v807.cpp`): Tikhonov
real (`+ε` en la diagonal de `G` antes de factorizar, con `ε` relativo a la
escala de la matriz) más guarda explícita en la división final. Mismo input
rank-deficient, mismo sanitizer, resultado:

```
output[] = 0.070014 ... 0.000049 0.000098 0.000146 0.000195 ...
sin NaN/Inf
```

**Lo que NO arreglé, a propósito:** dejé la firma `void` porque cambiarla
rompe el ABI hacia quien sea que llame esto desde C++/Rust/Python, y yo no
tengo ese call site en los archivos entregados. Mi recomendación real es que
esta función devuelva un status (igual que el patrón `NativeStatus` que ya
usás en Rust) para que "columna degenerada" sea un resultado reportable, no
un 0.0 silencioso — pero coordinar ese cambio de firma en las tres fronteras
de lenguaje te lo dejo a vos, con el riesgo de ABI desync que vos mismo
identificaste en el brief original.

---

## 3. VERIFICADO (código, no herramienta) — El número "62,000 eventos/seg" nunca salió de ningún test

**Archivo:** `generar_estructura_sota.py`, línea con `f.write(...)`.

Esto no necesita sanitizer, es lectura directa del script que genera el
propio certificado:

```python
f.write("- Anillo SPSC Wait-Free (62,000 eventos/seg)\n")
```

Es un string literal. El test 3 (`test_spsc_ring_buffer` en
`test_v805_ipc_suite.py`) **imprime** el throughput pero **no lo assertea**
— solo assertea cantidad de eventos y orden, nunca velocidad. El log crudo
real midió 54322 eventos/seg. El "62,000" de la certificación no viene de
ninguna corrida: alguien lo tipeó.

**Fix aplicado y verificado** (`generar_estructura_sota_v807.py`): reescribí
el generador para que parsee `05_LOG_RAW_TESTS.txt` con regex y arme el
certificado desde ahí. Si no encuentra el dato, **falla** en vez de rellenar
con un número — corrí el parser contra tu log real y esto es lo que produce
hoy:

```
- Anillo SPSC Wait-Free: 54322 eventos/seg (medido, no redondeado a una cifra de marketing)
- DSU Iterativo Rust: construccion anunciada V=1000000, evaluacion real V=50000

> ADVERTENCIA AUTOMATICA: el log anuncia construir V=1000000 nodos pero solo
evalua 50000. Esta discrepancia se deja explicita en vez de ocultarla;
corregir el test o el mensaje antes de certificar 'ultra escala' en el titulo.
- Stiefel Shifted CholQR: error de ortogonalidad final = 3.99e-15
```

Noten que el propio generador corregido te avisa de la segunda discrepancia
(1,000,000 anunciados vs 50,000 evaluados) automáticamente — ya no depende
de que un humano o una IA lo note leyendo.

---

## 4. VERIFICADO (código) — El objetivo teórico de precisión es matemáticamente imposible en FP32

Esto es el aporte a la teoría que pediste. El brief pide:

> `|y_final|² − 1.0 ≤ 4.44×10⁻¹⁶`

`4.44e-16 = 2 × DBL_EPSILON` exacto (verificado numéricamente: `2.220446e-16
× 2 = 4.440892e-16`). Es un límite estándar de la literatura de álgebra
lineal numérica **para aritmética de doble precisión**. El épsilon de
`float` (FP32, que es el tipo que usa `stiefel_cholqr` de punta a punta) es
`1.19e-7` — casi 4 mil millones de veces más grande. Ninguna técnica de
suma compensada (Kahan, Neumaier, TwoSum) puede bajar el error por debajo de
la precisión con la que están representados los propios números de entrada.
El objetivo, tal como está escrito, no es "difícil": es inalcanzable con el
tipo de dato elegido, sin excepción.

Coherente con esto: el propio test 2 del suite no exige `1e-16`, exige
`assert result.final_ortho_error <= 1e-5` — quien escribió el test ya sabía,
al menos implícitamente, que `1e-16` no es alcanzable en FP32. El brief
teórico y el test real no están de acuerdo entre sí.

**Recomendación (no es un parche de código, es una decisión de diseño
tuya):** o (a) el pipeline crítico de ortogonalización pasa a `double` donde
de verdad importa la cota de `1e-16`, o (b) se corrige el brief para pedir
un objetivo realista en FP32 (algo en el rango `1e-6` a `1e-5` dependiendo
de `D` y el condicionamiento, que es lo que el test real ya asume). Mezclar
"prometemos 1e-16" en la teoría con "aceptamos 1e-5" en el test es la
brecha que hace parecer terminado algo que no lo está.

---

## 5. VERIFICADO (código) — Intel XPU mapeado como si fuera AMD HIP

**Archivo:** `polydim_hw_dispatcher.py`:

```python
if hasattr(torch, 'xpu') and torch.xpu.is_available():
    return "hip" # Mapping XPU/HIP based on prompt instructions
```

`torch.xpu` es el backend de Intel (oneAPI/Level Zero). `"hip"` es AMD ROCm.
Son stacks de kernels binarios completamente distintos. El comentario
("Mapping XPU/HIP based on prompt instructions") es la prueba de que esta
rama se escribió para satisfacer un prompt, no el hardware real. En una
máquina con GPU Intel, esto le pide al orquestador C++ kernels ROCm que no
van a correr ahí.

**Fix aplicado** (`polydim_hw_dispatcher_v807.py`): rama `"xpu"` propia en
vez de mentirle a `"hip"`. No puedo verificar esto con sanitizer porque
depende de hardware Intel real que este sandbox no tiene — queda marcado
como fix de lectura, no de herramienta.

---

## 6. LECTURA (bloqueado) — Todavía no pude compilar `polydim_monolith.cpp` completo

Busqué la definición de `Header`, `Lease`, `Ring` en los 22 archivos del zip,
incluido el consolidado de 2429 líneas. **No están en ningún lado.** Sin esa
definición no puedo armar un build real del núcleo de concurrencia C++
completo ni correrle TSan encima — lo que vi (uso de
`reinterpret_cast<std::atomic<T>*>` con `memory_order` explícito en el
swap de bancos) es más sólido de lo que asumí en la ronda anterior, pero no
lo pude poner bajo sanitizer sin inventar un layout de struct, y "no quiero
alucinaciones" fue tu pedido explícito — así que no lo inventé.

Si me pasás ese header (o confirmás que nunca se escribió y querés que lo
reconstruya yo, marcado como no verificado), sigo con esto en la próxima
entrega sin volver a preguntar nada más.

**Tampoco pude tocar:** las rutas específicas de Windows (`BCrypt`,
`WaitOnAddress`) ni macOS (`__ulock_wait/wake`) — este sandbox es Linux, y
por diseño no hay forma de correr sanitizers sobre código que solo compila
en otro sistema operativo. Eso no es una limitación mía de esta sesión: es
estructural, y explica por qué ninguna auditoría hecha desde una sola
máquina/SO puede certificar el sistema completo sin CI real en las tres
plataformas.

---

## Archivos entregados en esta ronda

- `polydim_monolith_v807.rs` — parche verificado (sección 1)
- `polydim_stiefel_v805_v807.cpp` — parche verificado (sección 2)
- `generar_estructura_sota_v807.py` — parche verificado (sección 3)
- `polydim_hw_dispatcher_v807.py` — parche de lectura (sección 5)
- `verificacion_frechet_harness.c` / `verificacion_stiefel_harness.cpp` —
  los arneses que usé, para que los corras vos mismo y no tengas que
  confiar en mi palabra

## Lo que de verdad rompería el ciclo de 600 rondas

No es "otra ronda de lectura". Es que el propio repo tenga, a partir de
ahora: (1) el header de tipos que falta, para que exista un build real;
(2) estos mismos arneses corriendo en CI cada vez que alguien toca estos
archivos, no como algo que una IA arma una vez y se pierde; (3) el test 3
(SPSC) y el objetivo de `1e-16` corregidos como se explica arriba, porque
hoy certifican cosas que no miden. Sin eso, la próxima IA que audite esto
—yo en otra sesión, u otra— va a volver a encontrar estas mismas tres cosas
de cero, porque nada en el repo deja constancia de que ya se encontraron.
