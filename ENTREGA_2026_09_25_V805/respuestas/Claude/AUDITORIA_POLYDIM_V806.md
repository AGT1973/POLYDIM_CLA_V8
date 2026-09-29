# Auditoría técnica POLYDIM V806

Fecha: 26 de septiembre de 2026. Formato de razonamiento adaptado por AGT, 2026: afirmación, evidencia, impacto, corrección y criterio de cierre.

## Dictamen

**NO APTO PARA CERTIFICACIÓN DE PRODUCCIÓN con esta entrega.** No se sostienen las afirmaciones globales de invariancia numérica, seguridad de memoria entre lenguajes, IPC multiplataforma ni consenso bizantino certificado. Hay errores de implementación, incompatibilidades de contrato y componentes esenciales ausentes. Esto no demuestra que toda la arquitectura sea inviable: demuestra que la certificación entregada excede la evidencia.

La memoria compartida y el intercambio tensorial pueden conservarse. Las correcciones propuestas no requieren convertir los tensores a texto ni sustituir PMTP por servicios web.

No se ofrece una certificación de ausencia de errores. No se modificó el código original ni se presenta una V807 supuestamente corregida: la solicitud es una auditoría con soluciones, y faltan componentes necesarios para validar una reparación integral.

## Alcance y trazabilidad

Se leyó `03_INSTRUCCIONES_PROMPT_IA.md`, los documentos adjuntos, los once archivos fuente, la suite Python y el consolidado. Se contrastaron sus secciones con los archivos individuales: el contenido fuente coincide; el último bloque del consolidado incorpora además el registro de pruebas y el cierre del documento.

SHA-256 de `auditoria_externa(1).zip`:

`9e22b0e28ce87a5b54d0bcc91c5f75a1b7e408fd6dda7cd336a35d2941fd51ac`

Las instrucciones solicitan cinco pasadas pero no las enumeran. Se adoptan: 1) integridad de entrega y construcción; 2) matemática y escala; 3) IPC y concurrencia; 4) FFI, dispositivos y criptografía; 5) evidencia y certificación. Las referencias de líneas corresponden a los archivos originales en `archivos_fuente/`, conservando el sufijo `.txt`; para la suite, a `pruebas_unitarias/`.

Estados de evidencia:

- **Ejecutado:** resultado observado en este entorno Linux x86-64 con GCC 13.3.0.
- **Estático:** consecuencia del código o incompatibilidad contractual; no implica reproducción nativa de un fallo de memoria.
- **Analítico:** deducción matemática con hipótesis explícitas.
- **Pendiente:** requiere componentes o plataformas ausentes.

No se ejecutaron pruebas de corrupción de memoria, explotación ni carreras forzadas. Rust no está disponible como `rustc` en PATH; tampoco se dispuso del entorno Windows/macOS ni de ejecución GPU/TPU. El registro aportado no se confunde con resultados obtenidos aquí.

## Pasada 1. Entrega, símbolos y compilación

### A01 — Bloqueante: falta el contrato ABI y el cargador BLAS

**Evidencia:** `polydim_monolith.cpp.txt:26–27` incluye `../include/polydim_solver_abi.h` y `../include/polydim_blas_loader.h`; ambos faltan. La compilación sintáctica real se detuvo en la primera cabecera ausente. La suite exige DLL C++ V805 y Rust V804 que tampoco están incluidas; ejecutarla termina con `AssertionError` antes del primer test.

**Impacto:** no es posible reconstruir el núcleo completo ni vincular los logs con los fuentes entregados. Las definiciones de ctypes no sustituyen un ABI normativo.

**Solución:** entregar árbol compilable, cabecera C versionada, cargador BLAS y sus fuentes, CMake/Cargo y dependencias fijadas. Generar manifiesto con hashes de fuente, binario, compilador y opciones. **Cierre:** compilación y pruebas desde extracción limpia, sin rutas del equipo del autor.

### A02 — Bloqueante para el desafío central: Rodrigues y el slab allocator no están implementados en el paquete

**Evidencia:** Dart busca `polydim_rodrigues_geodesic_f64`, funciones de proyección, ortonormalización y PMTP, pero no se entregan sus definiciones nativas. Tampoco se encontró la implementación de `PmtpSlabAllocator` ni creación/mapeo de memoria compartida en los fuentes.

**Impacto:** la estabilidad de Rodrigues para ángulos pequeños, las dos pasadas compensadas y FTZ/DAZ permanecen **desconocidas en esta entrega**. No es legítimo atribuirles un fallo empírico ni certificarlas.

**Solución:** incorporar implementaciones, contratos y tests específicos. **Cierre:** medir norma, distancias y reversibilidad con referencia independiente, incluyendo ángulos pequeños y dimensiones 10⁴, 10⁶ y 10⁷.

### A03 — Alto: portabilidad declarada distinta de la implementación

**Evidencia:** `polydim_monolith.cpp.txt:337–345` usa `HMODULE`, `GetModuleHandleA` y `GetProcAddress` fuera de una guarda Windows; `immintrin.h` se incluye incondicionalmente. Crypto depende de Windows. El selector Python devuelve nombres de dispositivos, pero no incorpora kernels CUDA, HIP ni Pallas.

**Solución:** declarar una matriz real de soporte y separar plataformas. Un backend se anuncia disponible solo después de inicializar y ejecutar una operación mínima del backend. **Cierre:** builds y pruebas por plataforma; las no verificadas figuran como pendientes.

## Pasada 2. Matemática, invariantes y escala

### M01 — Alto: la explicación de DPI es incorrecta

Serializar una representación finita de un tensor mediante una función biyectiva no pierde información. Si Y puede recuperarse de g(Y), las dos aplicaciones de DPI dan `I(X;Y) = I(X;g(Y))`. Una secuencia de bytes puede representar un tensor multidimensional exactamente. Convertir un estado a una descripción lingüística generalmente pierde información, pero eso **obedece** a DPI; no la viola.

**Solución:** fundamentar Morpho en evitar decodificación lingüística, copias y conversiones innecesarias, preservando dtype, forma, métrica y valores. Separar codificación sin pérdida, cuantización y resumen semántico. El ahorro no depende de afirmar que una disposición lineal destruye geometría.

### M02 — Alto: compatibilidad semántica de latentes no demostrada

Compartir dimensión y norma no establece que dos modelos interpreten las coordenadas de la misma manera. Una transformación ortogonal preserva geometría y puede cambiar todas las coordenadas respecto del decodificador receptor.

**Solución:** versionar espacio latente, modelo productor, base, métrica y adaptadores. Validar tareas extremo a extremo y alineamiento entre modelos. **Cierre:** evidencia de que el receptor puede utilizar el estado transmitido, además de comprobar que recibe los mismos bytes.

### M03 — Alto: O(1) describe publicación de descriptor, no procesamiento del tensor

Con mappings existentes y una reserva ya concedida, publicar un descriptor pequeño puede ser O(1) respecto de D. Leer/producir D escalares cuesta Ω(D); autenticarlos o cifrarlos también. Page faults, coherencia de caché, NUMA y transferencias de dispositivo siguen teniendo costo. La adquisición de leases depende de lectores y espera.

**Solución:** medir publicación, adquisición, disponibilidad y consumo por separado. Informar bytes recorridos y copiados. Para D=10⁷, un vector FP64 ocupa 80 MB decimales. Cero tokens lingüísticos no significa costo físico cero.

### M04 — Alto, ejecutado: FP32 no satisface una cota uniforme de 4,44×10⁻¹⁶

Se compiló **sin modificar** `polydim_stiefel_v805.cpp.txt`, copiándolo a una extensión compilable, con `-std=c++17 -O2 -fno-fast-math`. Para una columna constante de unos, se evaluó la norma cuadrada de la salida usando acumulación `long double`:

| D | K | Error absoluto de norma cuadrada |
|---:|---:|---:|
| 10.000 | 1 | 4,470348308194×10⁻⁸ |
| 1.000.000 | 1 | 9,499489470239×10⁻⁸ |
| 10.000.000 | 1 | 1,279212439309×10⁻⁷ |

Estos son resultados del módulo FP32; **no son resultados del Rodrigues FP64 ausente**. En FP32, producto, acumulador y salida siguen siendo float. Neumaier no deshace el redondeo del producto ni el de la salida.

**Solución:** separar contratos FP32/FP64 y fijar cotas en función de dimensión, condición y operaciones. Acumular FP32 en FP64 cuando convenga. Para una garantía FP64 extremadamente estricta, especificar también la métrica del error y el algoritmo que lo mide; TwoSum por sí solo no es una demostración global.

### M05 — Alto, ejecutado: CholQR FP32 produce NaN en rango deficiente

**Evidencia:** `polydim_stiefel_v805.cpp.txt:44–68` permite diagonal cero y termina dividiendo por esa diagonal. La rama comentada como Tikhonov solo pone un elemento fuera de diagonal a cero; no suma λI. Para entrada cero de 10.000×2, aparecieron **20.000 valores no finitos**.

**Solución:** devolver estado de rango deficiente, no una matriz supuestamente ortonormal. Para rango completo pero mal condicionado: QR Householder/TSQR o una variante CholeskyQR con hipótesis y refinamientos verificados. **Cierre:** rango cero, rango parcial, columnas casi dependientes y variaciones de escala con resultados finitos o rechazo explícito.

### M06 — Alto: `apply_shifted_cholqr2` no implementa dos pasadas CholQR

**Evidencia:** `polydim_monolith.cpp.txt:421–493` calcula una sola Gramiana, un factor y una transformación. Ajustar pivotes de forma local y recortarlos no equivale al procedimiento documentado de shifted CholeskyQR3. Para entrada cero, devuelve OK con salida cero.

Se verificó esto compilando las funciones numéricas extraídas literalmente, con una Gramiana escalar de referencia y constantes de estado locales. **Es una comprobación aislada de las funciones, no la compilación del producto.** Resultado: código 0, norma cuadrada 0.

**Solución:** implementar el algoritmo elegido completo, evitar la inversa triangular explícita y controlar rango/condición. Una regularización de rango deficiente no puede fabricar K columnas ortonormales preservando el mismo espacio columna.

### M07 — Alto, analítico y ejecutado aisladamente: Cayley elimina movimientos verticales válidos

**Evidencia:** `polydim_monolith.cpp.txt:495–598`. Sea `XᵀX=I` y `G=XΩ`, con `Ωᵀ=−Ω`, `Ω≠0`. Es una dirección tangente válida de Stiefel. En la fórmula entregada:

`XtG=Ω`, `GtG=ΩᵀΩ`, `GpGp=0`, `Z2=0`, `Z1=I`, `Coef_X=−Ω`.

Por tanto, la actualización previa al CholQR es `X−τXΩ+τXΩ=X`. Una retracción de Stiefel debe tener la derivada identidad sobre el espacio tangente; esta dirección queda anulada. Se compiló la función extraída y se obtuvo X=I sin modificación para un ejemplo ortonormal 2×2 y τ=0,1.

**Impacto:** puede conservar ortogonalidad mientras no avanza hacia el objetivo. El objetivo `0,5||X−Target||²` depende de la base; no se puede reinterpretar automáticamente como objetivo de Grassmann. La deducción vale igualmente para D grande agregando filas cero.

**Solución:** usar una retracción QR/polar válida como referencia o derivar Cayley con todos los términos de Stiefel. **Cierre:** verificar `R_X(0)=X` y derivada direccional para componentes horizontales y verticales, además de convergencia objetiva.

### M08 — Alto: convergencia aceptada antes de comprobar factibilidad

**Evidencia:** `polydim_monolith.cpp.txt:640–695,744–771`. El gradiente puede disparar convergencia antes de la retracción; el error de ortogonalidad final se calcula, pero no invalida ese estado. Una matriz cero con objetivo cero deja gradiente cero aunque no pertenece a Stiefel.

**Solución:** validar/retraer el punto inicial bajo contrato explícito y exigir simultáneamente factibilidad, finitud y criterio de estacionariedad. **Cierre:** ningún estado de convergencia con error de factibilidad superior al contrato.

### M09 — Medio: resultado y tolerancias no representan el estado final

Objetivo y gradiente se miden antes del último paso y se publican como finales (`641–689,749–753`). `step_tol` se carga y no se utiliza; `objective_tolerance` no guía el algoritmo. El conteo al salir por error tras una actualización también requiere semántica explícita.

**Solución:** recalcular métricas finales, implementar criterios anunciados y contar pasos aceptados. **Cierre:** comparar resultado publicado con evaluación independiente de X devuelto.

### M10 — Alto: el filtro no calcula una mediana intrínseca de la esfera

**Evidencia:** Rust `249–412`: distancias euclídeas, Weiszfeld ambiente durante cinco iteraciones y normalización posterior. Una mediana euclídea proyectada no es en general la mediana geodésica de Fréchet. El residuo publicado corresponde al medoide previo, no al vector final. La inicialización en un candidato y el recorte de distancia a 10⁻¹² pueden hacer dominar a ese candidato.

**Solución:** decidir explícitamente entre mediana extrínseca e intrínseca. Para la segunda, usar distancia geodésica y optimización riemanniana con criterio de convergencia; gestionar coincidencias y antípodas. Para la primera, corregir nombre, singularidades de Weiszfeld y residuo. **Cierre:** referencia independiente para objetivo y estacionariedad, no solo similitud con un centro construido.

### M11 — Alto: Betti del grafo no certifica homología de S^(D−1)

`E−V+C` es β1 de un grafo tratado como complejo unidimensional. Un triángulo de aristas tiene β1=1; si se incluye su cara, β1=0. Para D≥3, la esfera S^(D−1) tiene β1=0, pero esto no identifica la homología de un grafo de proximidad con la de la esfera ni con la de una distribución de muestras.

**Solución:** si se mide conectividad de agentes, nombrarla así y conservar DSU. Si se busca inferencia topológica, especificar complejo, escala y muestreo; considerar persistencia con presupuesto explícito. **Cierre:** ejemplos con caras y escalas donde cambie la topología esperada.

### M12 — Alto: proximidad y quórum geométrico no equivalen a BFT

**Evidencia:** Rust `399–413` declara certificación según tamaño de la componente y ciclos. No hay protocolo de acuerdo distribuido, modelo de fallos, validación semántica, autenticidad de votos ni prueba de seguridad/liveness. La conectividad es transitiva; no impone diámetro acotado. Un cluster no determina verdad.

**Solución:** renombrar la salida a aceptación por criterio geométrico y especificar supuestos de contaminación. Si se exige BFT, diseñar y verificar por separado el protocolo y sus garantías. **Cierre:** la documentación distingue outliers, fallos bizantinos y errores semánticos correlacionados.

### M13 — Alto: complejidad multivariable omitida

| Operación | Tiempo relevante | Memoria adicional aproximada |
|---|---|---|
| Gramiana D×K | O(DK²) | O(K²), más O(D) en modo determinista |
| Retracción/solver por iteración | O(DK²+K³) | O(DK+K²) |
| Filtro n candidatos de D dimensiones | O(n²D), más refinamiento | O(n+D), sin contar entrada O(nD) |
| DSU de V vértices y E aristas | O((V+E)α(V)) amortizado | O(V) |
| Reservorio FWHT | O(D log D) | O(D) |

Decir O(D) requiere fijar K, n e iteraciones. Con D=10⁷ y K=32, una matriz FP64 ocupa 2,56 GB decimales; X, Target y G suman 7,68 GB antes de otros buffers. Un centenar de candidatos FP64 ocupa 8 GB. No se extrapola rendimiento de D=128 al dominio objetivo.

**Solución:** budgets por operación, número de agentes y memoria pico; benchmarks por backend y estado de caché. No confundir dimensión latente D con vértices V de DSU.

### M14 — Alto: LSM no mantiene el invariante esférico

`polydim_monolith.cpp.txt:935–970` combina tanh y fuga sin renormalizar. El log ya informa norma 0,8634. FWHT exige potencia de dos: D=10.000 y D=10.000.000 no cumplen directamente.

**Solución:** clasificar LSM como dinámica ambiente o diseñar una transición sobre esfera explícita. Si se usa padding, documentar embedding y proyección. **Cierre:** el contrato diferencia claramente reservorio y estado esférico; no llama invariantes a propiedades ausentes.

### M15 — Alto: síntesis cuántica sin garantía de epsilon

Rust `481–499` genera repeticiones heurísticas según el residuo; no mide error unitario ni converge según epsilon. Muchas tolerancias diferentes generan la misma secuencia. La suite llama eje 1 y lo rotula R_y, pero H-T-H corresponde a rotación X salvo fase global.

**Solución:** usar un sintetizador con garantía de aproximación o declarar discretización heurística. **Cierre:** componer matrices de puertas y medir distancia al objetivo módulo fase global para todos los ejes y tolerancias. Contar tres puertas no comprueba la operación.

## Pasada 3. IPC y concurrencia

Los siguientes son hallazgos estáticos defensivos. No se presenta reproducción operativa de corrupción de memoria.

### C01 — Crítico: reserva de lector no exclusiva

`polydim_monolith.cpp.txt:839–851` observa estado libre y escribe metadatos sin reservar atómicamente el slot. El protocolo no asegura propiedad exclusiva bajo concurrencia.

**Corrección:** introducir reserva exclusiva antes de modificar metadatos, publicar el lease solo tras inicialización completa y ligar liberación a una generación/identidad. **Cierre:** verificación de máquina de estados y propiedad «un slot, un propietario vigente».

### C02 — Crítico: escritor autorizado pese a lectores pendientes

`879–898` agota el contador de espera y continúa devolviendo OK sin demostrar que desaparecieron los lectores. No es una mera sospecha de rendimiento: falta la condición de seguridad de reutilización.

**Corrección:** al agotar la espera, devolver BUSY/TIMEOUT y abandonar ordenadamente la propiedad del escritor; mantener intacto el banco. **Cierre:** nunca conceder escritura sobre un banco con leases vigentes.

### C03 — Crítico: adquisición sin revalidación de publicación

`836–850` toma banco activo y generación sin un protocolo completo de revalidación tras publicar el lease. `858–864` cierra un slot sin comprobar identidad/generación; commit admite banco sin validación suficiente en esta función.

**Corrección:** diseñar publicación y adquisición con generación estable, revalidación y tokens de propiedad. Probar el protocolo completo, no añadir únicamente fences. **Cierre:** no reutilizar una versión mientras exista lector autorizado; ningún token obsoleto libera una reserva nueva.

### C04 — Alto: recuperación de huérfanos incompleta

`778–825`: la rama POSIX considera muerto todo PID cuyo `kill(pid,0)` no devuelve cero; debe distinguir falta de permisos. No utiliza tiempo de inicio contra reutilización de PID ni `timeout_ns`. La transición a reclaimed no verifica una identidad de lease estable. La adquisición del escritor tampoco muestra recuperación robusta del propietario muerto.

**Corrección:** identidad de proceso con época de arranque, estados comparados atómicamente y tratamiento conservador de «desconocido». **Cierre:** recuperación especificada sin revocar procesos vivos.

### C05 — Alto: Windows conserva la espera intraproceso declarada corregida

`polydim_ipc_v805.cpp.txt:25–39,65–70` usa WaitOnAddress/WakeByAddress. No aparece el semáforo nombrado descrito en el reporte. Microsoft limita el despertar a hilos del mismo proceso [R1].

**Corrección:** mecanismo de espera realmente interproceso, con predicado atómico compartido y plazos, manteniendo el payload en memoria compartida. **Cierre:** pruebas entre procesos independientes en Windows, incluyendo notificación, timeout y terminación.

### C06 — Medio: contrato de espera inconsistente entre plataformas

Linux colapsa causas distintas en −1 y wake ignora errores. macOS multiplica milisegundos en uint32: existe desbordamiento aritmético para esperas grandes y el cero requiere semántica documentada. La corrección interproceso del uso de la API privada macOS queda pendiente de contraste y prueba nativa.

**Corrección:** estados explícitos, plazo monotónico y conversiones verificadas. No anunciar equivalencia entre ramas sin pruebas por plataforma.

### C07 — Alto: casting a `std::atomic` no establece por sí mismo contrato de objeto

Handle, ring y leases reinterpretan almacenamiento como objetos `std::atomic`. La cabecera C++ ausente impide comprobar todas las declaraciones; los mirrors ctypes usan enteros ordinarios. Deben resolverse lifetime, alineación, lock-free y soporte de IPC del ABI concreto.

**Corrección:** mantener objetos atómicos construidos nativamente detrás de handles opacos, o documentar y validar primitivas de plataforma sobre layouts compartidos. **Cierre:** contrato único verificable de tamaño, alineación, vida útil y atomics entre procesos. No basta que pase una ejecución x86.

### C08 — Medio: anillo SPSC local presentado como evidencia de IPC

`200–270` reserva heap local y guarda un puntero absoluto. La suite emplea dos hilos del mismo proceso. Eso no demuestra acceso entre procesos mapeados a direcciones diferentes.

**Corrección:** separar telemetría intraproceso y PMTP. Para IPC, utilizar descriptores relativos a mappings y ownership especificado. **Cierre:** prueba real entre procesos; progreso de la operación básica separado de bucles de reintento del cliente.

## Pasada 4. FFI, dispositivos y protección de datos

### F01 — Crítico: ABI Rust/ctypes incompatible en alineación y tamaño

Rust `82–107` declara ambos resultados con `repr(C, align(128))`. La suite declara `_pack_=8`. Evaluando solo las definiciones ctypes, sin llamar a Rust, se obtuvo:

| Tipo | sizeof ctypes | alignof ctypes | Contrato Rust declarado |
|---|---:|---:|---|
| PolydimBettiResult | 32 | 8 | alineación 128; tamaño redondeado a 128 |
| PolydimFrechetBettiResult | 56 | 8 | alineación 128; tamaño redondeado a 128 |

**Impacto:** pasar estos objetos no cumple las precondiciones de las escrituras Rust. No se afirma haber observado qué instrucciones de escritura emitió un compilador Rust concreto ni una corrupción concreta: la incompatibilidad de contrato basta para bloquear.

**Corrección preferida:** eliminar sobrealineación de los DTO públicos y conservarla en estructuras internas; alternativamente, asignación/destrucción nativa opaca. Generar bindings y verificar tamaño/alineación/offsets en cada lenguaje [R2].

### F02 — Alto: `Ok` sin resultado inicializado

Rust `270–276` retorna Ok cuando la varianza muestreada es pequeña, antes de escribir el vector y la estructura. Incluye código muerto `if false`. El caso de candidatos idénticos activa conceptualmente esta ruta, aunque es un consenso trivial válido.

**Corrección:** todo Ok debe producir una salida completa y validada; caso degenerado con semántica explícita. En error, invalidar claramente la salida. **Cierre:** contrato verificable para cada retorno.

### F03 — Alto: `catch_unwind` no es un firewall de memoria

Rust construye slices desde punteros y longitudes y escribe en salidas sin recibir su capacidad. Solo comprobar no-null no verifica validez, extensión, alineación ni exclusión de accesos concurrentes. `catch_unwind` no convierte UB ni aborts en errores recuperables [R3]. `mem::forget(e)` retiene intencionalmente el payload del primer panic; el estado global posterior limita repeticiones, por lo que no se afirma una fuga ilimitada por llamadas.

**Corrección:** handles de buffers confiables, longitudes/capacidades verificables, contratos de aliasing, operaciones aritméticas checked y política de panic explícita. Reducir el trabajo falible durante el manejo del error. **Cierre:** ABI y manejo de errores auditados independientemente del algoritmo.

### F04 — Alto: validación de tamaños, índices y finitud incompleta

Hay productos como D*K, K*K y capacidad*tamaño sin comprobaciones sistemáticas; el reservorio consume índices de permutación sin validar su dominio ni unicidad. C++ asigna vectores dentro de funciones públicas sin traducción consistente de excepciones a estados. El filtro no rechaza de forma global NaN/Inf.

**Corrección:** validar descriptores al registrarlos, usar multiplicaciones verificadas y límites de capacidad, comprobar permutaciones, finitud y no solapamiento donde corresponda. Contener excepciones en límites C. **Cierre:** ninguna operación entra al núcleo con un descriptor fuera de contrato.

### F05 — Alto: contigüidad no garantiza compatibilidad FFI

`polydim_bindings_v805.py:14–17` mueve a CPU solo `is_cuda`; los demás dispositivos no están cubiertos. Conserva dtype y no establece forma, mutabilidad, alineación ni vida útil del propietario. Además, el CholQR FP32 indexa columnas contiguas, mientras el helper promete orden C: se necesita especificar forma/layout antes de conectarlos.

**Corrección:** descriptor explícito de dtype, shape, strides, dispositivo y propietario. Adaptador CPU que transfiera cualquier tensor no-CPU bajo política visible. Retener el dueño durante toda la llamada y leases durante vistas compartidas. **Cierre:** contrato por función, sin reinterpretar silenciosamente buffers.

### F06 — Medio: detección de hardware incorrecta

`polydim_hw_dispatcher.py` asigna `xpu` a `hip` y deduce TPU de cualquier dispositivo XLA. Un backend XLA no implica necesariamente TPU; un nombre devuelto tampoco garantiza kernel disponible.

**Corrección:** separar dispositivo, runtime y capacidades; no traducir Intel XPU a AMD HIP. **Cierre:** la selección coincide con el kernel realmente inicializado.

### F07 — Alto: cifrado auxiliar no demuestra aislamiento PMTP

Las funciones BCrypt existen, pero no se ve integración con publicación/adquisición PMTP ni gestión de claves, nonces o protección de metadatos. La existencia de una función AES-GCM no certifica que los tensores circulen autenticados.

**Corrección:** definir frontera de confianza, unicidad del nonce por clave, metadatos autenticados y fallo cerrado. El cifrado recorre el payload: su costo es O(D). Documentar compatibilidad entre inmutabilidad, acceso zero-copy y ubicación del texto claro.

### F08 — Medio: salidas y recursos crypto requieren contrato de fallo

`polydim_crypto_v805.cpp.txt:124–133` deja el buffer de salida después de un fallo; no establece una salida vacía/invalidada. Conversiones `size_t→ULONG` requieren límites. `get_secure_attributes:147–151` retorna una estructura con descriptor nulo si falla la creación, sin obligar al consumidor a rechazarla. Un descriptor nulo selecciona seguridad por defecto; no se afirma que equivalga automáticamente a DACL abierta.

**Corrección:** limpiar/inutilizar resultados fallidos, validar longitudes antes de conversiones, usar RAII y devolver error explícito ante fallo de política de acceso. **Cierre:** ningún consumidor confunde fallo criptográfico con datos utilizables.

### F09 — Medio: puente Dart no acredita el ABI anunciado

`PMTPControl` contiene un único byte, pero no se entrega el contrato nativo correspondiente; no puede verificarse que sea el layout correcto. Las asignaciones de `rotate` se realizan antes de entrar al `try`, de modo que el fallo de una asignación posterior puede dejar anteriores sin liberar. La ruta también copia listas completas de entrada y salida.

**Corrección:** control nativo opaco, asignación con limpieza incremental y vistas persistentes para el camino masivo. **Cierre:** ABI generado y distinción entre demo con copias y camino de producción zero-copy.

## Pasada 5. Pruebas y certificación

### V01 — Alto: discrepancias concretas de la suite

- **Latencia:** línea 443 multiplica segundos por 10⁶ y rotula ns. 54.322 eventos/s implica aproximadamente 18,41 microsegundos por evento, o 18.409 ns, no 18,41 ns. Es tiempo agregado por evento, no distribución de latencia individual.
- **DSU:** líneas 497–512 anuncian 1.000.000 de vértices, pero pasan **50.001 vértices y 50.000 aristas**. Una cadena de aristas procesada con union-by-rank tampoco construye necesariamente un árbol interno de profundidad V.
- **Concurrencia:** `join()` del productor y consumidor carece de plazo efectivo global; el timeout del Event no impide bloqueo en join posterior.
- **Stiefel:** acepta estado de máximo de iteraciones y tolerancia 10⁻⁵; no exige disminución del objetivo ni convergencia, y no cubre Cayley.
- **Cuántica:** verifica cantidad de puertas, no matriz unitaria ni epsilon.
- **LSM:** admite normas entre 0,1 y sqrt(D), lo que no valida pertenencia a esfera unitaria.
- **Cobertura:** los siete tests no ejercitan las nuevas esperas multiplataforma, BCrypt, helper de dispositivo ni CholQR FP32.

**Solución:** vincular cada afirmación a una aserción y un artefacto reproducible; plazos globales para concurrencia y reportes de pruebas fallidas conservados.

### V02 — Alto: certificación escrita como texto, no derivada de ejecución

`generar_estructura_sota.py` escribe el documento de certificación con afirmaciones fijas; no ejecuta la suite para obtenerlas. Esto no prueba que el autor nunca ejecutó pruebas: prueba que ese documento no constituye por sí mismo evidencia automática de ejecución.

**Solución:** generar reportes únicamente desde resultados de CI con hash del binario, fuentes y entorno. El log suministrado es antecedente, no certificación reproducida aquí.

### V03 — Verificaciones realmente realizadas en esta auditoría

| Verificación | Resultado | Límite |
|---|---|---|
| Inventario y comparación del consolidado | Fuentes contrastados | No verifica repositorios no entregados |
| Compilación sintáctica del monolito | Bloqueada por cabecera ausente | No se fabricó una ABI sustituta |
| Ejecución de suite original | Falla antes de tests: DLL ausente | No se reporta 7/7 |
| Compilación del CholQR FP32 original | Correcta con GCC 13.3.0 | Módulo aislado |
| Norma FP32 en D=10⁴,10⁶,10⁷ | Errores documentados arriba | K=1; no certifica todo el dominio |
| CholQR FP32 con rango cero | 20.000 no finitos | Entrada válida en memoria; defecto numérico |
| Funciones FP64 extraídas | Cayley inmóvil y CholQR cero con OK | Gramiana escalar auxiliar; no producto completo |
| Inspección de ABI ctypes | Tamaños 32/56, alineación 8 | Sin llamadas Rust incompatibles |
| Windows/macOS/GPU/TPU | No ejecutado | Pendiente |
| Rodrigues, FTZ/DAZ, slab y seqlock completo | No verificable | Implementaciones faltantes |

## Recomendación de arquitectura: orden de reparación

### Nivel 1 — Recuperar una entrega verificable

Una única ABI pública, versiones coherentes, build limpio y manifiesto. Retirar del reporte las garantías no comprobadas y declarar plataformas reales. Esto permite verificar las reparaciones posteriores.

### Nivel 2 — Cerrar propiedad y vida útil antes de optimizar

DTO sin sobrealineación pública; buffers registrados con capacidad; handles y generaciones; propiedad exclusiva de leases; publicación de bancos con revalidación; ninguna reutilización antes de quiescencia. Toda ruta devuelve un estado verificable. Estas condiciones son prerrequisitos del zero-copy seguro.

### Nivel 3 — Fijar el contrato matemático por operación

Separar esfera, Stiefel, Grassmann, reservorio ambiente y filtro de proximidad. Adoptar QR/TSQR como referencia robusta para rango completo y rechazo explícito de rango deficiente. Activar CholQR optimizado solo bajo condición admisible y validación posterior. Verificar Cayley por consistencia diferencial y objetivo.

Para Rodrigues, al incorporar su implementación: usar una evaluación estable de `versin(θ)=2 sin²(θ/2)`, comprobar ortonormalidad de la base y controlar norma de entrada. La corrección de versin evita una fuente de cancelación, pero no garantiza por sí sola la cota global. FTZ/DAZ, redondeo, FMA y opciones del compilador deben formar parte del contrato reproducible.

### Nivel 4 — Conservar la propuesta tensorial con garantías delimitadas

Descriptor nativo versionado con identidad del mapping, offset, capacidad, dtype, shape, generación y propietario. Espacio latente identificado y adaptador semántico explícito cuando corresponda. Plano de datos tensorial compartido y plano de control pequeño, sin generación lingüística obligatoria. Núcleo de referencia determinista y kernels optimizados sujetos al mismo contrato. Política de cifrado por frontera de confianza y costo medido.

La ruta CPU debe ser una implementación completa; CUDA/HIP/TPU son backends con contratos equivalentes y soporte declarado solo tras validación. La observabilidad debe medir norma, residuo, rango, fallos de leases, copias y tiempo de disponibilidad; no sustituir estas métricas por etiquetas «SOTA» o «certificado».

## Criterios mínimos para levantar el bloqueo

1. Build completo reproducible y ABI congruente en todos los consumidores.
2. Propiedades de ownership, publicación y reclamación documentadas y verificadas.
3. Pruebas numéricas con referencia independiente, rango/condición variados y contratos por dtype.
4. Métricas de objetivo, gradiente y factibilidad correspondientes al estado final.
5. Pruebas nativas entre procesos en cada plataforma soportada.
6. Medición de D, K, n y memoria pico; ningún millón de nodos inferido desde 50.001.
7. Certificación geométrica separada de corrección semántica y BFT.
8. Logs generados por ejecución y ligados a hashes de fuentes/binarios.

No se asigna un «100 % seguro» ni se promete una solución infalible: el criterio de cierre es evidencia verificable por propiedad.

## Fuentes primarias consultadas

[R1] Microsoft, WaitOnAddress y WakeByAddressSingle: semántica intraproceso y despertares.
https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitonaddress
https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-wakebyaddresssingle

[R2] Rust Reference, Type layout y comportamiento indefinido: alineación y representación.
https://doc.rust-lang.org/stable/reference/type-layout.html
https://doc.rust-lang.org/reference/behavior-considered-undefined.html

[R3] Rust, catch_unwind: límites de captura de pánicos.
https://doc.rust-lang.org/std/panic/fn.catch_unwind.html

[R4] Fukaya, Kannan, Nakatsukasa, Yamamoto y Yanagisawa, Shifted Cholesky QR for Computing the QR Factorization of Ill-Conditioned Matrices. La variante publicada y sus hipótesis no deben confundirse con recortar pivotes y aplicar una única transformación.
https://arxiv.org/abs/1809.11085
https://doi.org/10.1137/18M1218212
