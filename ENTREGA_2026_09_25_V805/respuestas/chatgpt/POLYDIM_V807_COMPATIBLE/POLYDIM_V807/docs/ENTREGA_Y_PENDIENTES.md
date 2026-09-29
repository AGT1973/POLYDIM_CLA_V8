# Entrega V807: cambios, evidencias y deuda restante

Fecha: 26/09/2026. Se entrega una **migración de referencia**, no un parche binario compatible. El código original está archivado y excluido de la construcción. El núcleo nuevo reduce superficie no verificable, corrige defectos demostrados y permite mediciones reproducibles.

## Resultado ejecutado

- Núcleo C++17 construido realmente con GCC 13.3.0 en Linux x86-64.
- 16 pruebas de regresión funcional/numérica aprobadas.
- Las mismas 16 pruebas aprobadas con UndefinedBehaviorSanitizer (UBSan).
- 2 pruebas cuánticas aprobadas; una recorre tres ejes y 17 ángulos por eje y compara matrices módulo fase global.
- Rotación CPU comprobada en D=10⁴, 10⁶ y 10⁷, con oráculo analítico y norma acumulada en long double.
- En la ejecución registrada a D=10⁷: error de norma cuadrada 3,9465×10⁻¹⁷; tiempo de llamada aproximado 0,202 s. No es una comparación de rendimiento con otras implementaciones ni un límite universal.
- IPC comprobado entre procesos distintos mediante spawn: publicación íntegra, rollback de publicación incompleta y timeout acotado.
- Rust, Dart, Windows BCrypt, MSVC y macOS **no ejecutados**. El código de esos módulos no debe clasificarse como validado.

`test_results.txt`, `ubsan_results.txt`, `quantum_results.txt` y `scale_results.json` conservan los resultados. `tools/verify.py` permite reconstruir y genera otra evidencia con hashes de código.

## Estado de los 38 hallazgos

«Corregido en referencia» no significa garantía general de seguridad; significa que la nueva ruta evita el defecto identificado y tiene la evidencia indicada. «Retirado» significa no disponible, no reparado manteniendo la funcionalidad antigua.

| ID | Decisión V807 | Estado/límite |
|---|---|---|
| A01 | ABI C propia, build sin cargador BLAS externo, verificación de tamaño/alineación | Núcleo construido; ABI incompatible deliberadamente |
| A02 | Nueva rotación y normalización FP64; nuevo bus shared-memory | Rotación probada; allocator slab/seqlock original no reconstruido |
| A03 | Solo CPU declarada; plataformas opcionales separadas | Windows/macOS y aceleradores pendientes |
| M01 | DPI y serialización corregidas en teoría | Corrección conceptual |
| M02 | `space_id` explícito en bus y requisito de adaptación | No incorpora adaptadores entre modelos |
| M03 | Costos O(D) de inicializar/validar y costo de locks declarados | Retirada afirmación de transporte completo O(1) |
| M04 | FP32 con cálculo FP64 y salida FP32; contratos separados | Regresión FP32 aprobada; sin cota FP64 para salida FP32 |
| M05 | Rango deficiente devuelve PD_RANK | Regresión de matriz cero/dependiente aprobada |
| M06 | Sustitución de falso CholQR2 por Householder escalado | Ortogonalidad/span/escala comprobados; condición extrema pendiente |
| M07 | Cayley defectuoso retirado; retracción QR con diagonal positiva | Movimiento vertical y descenso comprobados |
| M08 | Inicialización QR obligatoria, rango y factibilidad verificados | Cero inicial rechazado |
| M09 | Métricas finales recalculadas y pasos aceptados contados | Comparación independiente de objetivo/gradiente aprobada |
| M10 | Filtro nuevo devuelve medoide extrínseco, sin Weiszfeld de cinco pasos | Rust fuente revisada, ejecución pendiente |
| M11 | β1 documentado como multigrafo unidimensional | Sin inferencia de homología de esfera |
| M12 | Eliminación de bandera «BFT certificado» | BFT no implementado |
| M13 | Presupuestos explícitos, costos multivariables, escala medida | No certifica enjambres grandes ni escala en K |
| M14 | LSM ambiente, potencia de dos, entrada/permutación validadas | Regresión contractual; no invariante esférico |
| M15 | Síntesis restringida a rejilla y comparación unitaria | Fuera de rejilla rechaza; no sintetizador aproximado |
| C01 | Leases RCU antiguos fuera del build; lock compartido exclusivo | Evita la ruta defectuosa; no lock-free |
| C02 | Timeout devuelve fallo, nunca habilita escritura forzada | Espera entre procesos comprobada |
| C03 | Banco/generación se publican bajo lock; vistas ligadas al contexto | Cooperativo: no revoca vistas escapadas |
| C04 | No se recuperan leases por PID ni se fuerza reclamación | Crash con lock exige retiro de bus por supervisor |
| C05 | No se usa WaitOnAddress como IPC; multiprocessing proporciona lock compartido | Spawn probado Linux; Windows pendiente |
| C06 | Timeout finito uniforme en bus nuevo; API privada ulock retirada | Futex portátil de bajo nivel no implementado |
| C07 | Se eliminan reinterpret_cast atómicos y estructuras nativas falsas | Nuevo bus no comparte std::atomic fabricados |
| C08 | Pruebas spawn reales; se retira anillo SPSC del núcleo | SPSC optimizado no migrado |
| F01 | DTO Rust sin align(128), tamaños/alineaciones consultables | Rust no ejecutado; no marcar ABI Rust como certificado |
| F02 | Toda salida exitosa del cluster se construye por completo | Test Rust para idénticos incluido, aún no ejecutado |
| F03 | Capacidades, ABI explícita, sin panic payload olvidado ni estado global envenenado | Punteros válidos siguen siendo obligación; OOM abort no capturable |
| F04 | Tamaños/productos, finitud, permutaciones y excepciones C++ controlados | Regresión y UBSan en casos válidos; no prueba formal |
| F05 | Adaptador CPU propietario, dtype float64 y layout C | Copias explícitas; no acelera ni acepta punteros GPU crudos |
| F06 | Solo backend implementado seleccionable | Detección simulada retirada |
| F07 | Cripto separada de PMTP y frontera de confianza documentada | Nonces/keys/integración PMTP pendientes |
| F08 | RAII BCrypt, salidas invalidadas en fallo, límites ULONG y ACL fail-closed | Fuente Windows endurecida, no ejecutada |
| F09 | Dart con ABI 807, Arena y punteros Size; control PMTP antiguo retirado | Dart pendiente de análisis/build nativo |
| V01 | Tests de unidad, escala y matrices; plazos en procesos; métricas consistentes | No se reutiliza suite V806 como certificación |
| V02 | Verificador genera logs/códigos/hashes desde subprocess | No genera PASS sin ejecutar |
| V03 | Matriz de evidencia por backend y módulo | Pendientes visibles; sin extrapolación de pruebas |

## Decisiones de implementación

### Núcleo de referencia primero

Se renuncia temporalmente a throughput BLAS, OpenMP y non-temporal stores para estabilizar semántica. Householder tiene costo O(DK²). C++ mantiene buffers propios y publica resultados al final; eso añade memoria y evita salidas parciales en errores numéricos. No se garantiza asignación en tiempo constante.

La optimización utiliza búsqueda Armijo con un máximo finito de retrocesos. Si no logra un paso, devuelve el mejor estado válido con `converged=0`; no confunde un estancamiento con convergencia. El punto inicial se ortonormaliza por contrato, por lo que no se preserva una entrada arbitraria como punto de partida exacto.

### Memoria compartida con garantías modestas y explícitas

El bus conserva dos bancos para que una excepción de aplicación no publique un tensor parcialmente escrito. Un lock protege lectores y escritor. Esta política sacrifica concurrencia de lectores/escritor y throughput, pero elimina el uso de un banco sin demostrar su disponibilidad.

No es apropiado para consumidores hostiles: una vista NumPy retenida puede seguir dando acceso a memoria compartida. La confianza, el alcance del contexto y el cierre del proceso forman parte del contrato. La recuperación robusta automática requiere una máquina de estados nativa y pruebas de lifecycle adicionales; se deja pendiente.

### Fuentes opcionales

Rust no depende de crates externos y mantiene presupuesto de trabajo. Su guardia trata solo grafos y medoid; no entra en razonamiento semántico ni consenso bizantino. Tiene tests Rust incorporados. El pipeline no los marca aprobados cuando Cargo falta.

Windows Crypto exige nonces de 12 bytes, tags de 16 y claves AES válidas. El llamante debe garantizar unicidad de nonce por clave, incluso tras reinicios. El código no incorpora almacén de claves, rotación, antirreplay ni autenticación de descriptores PMTP. No constituye una protección de IPC terminada.

## Siguiente lote: criterios concretos

1. **Validar Windows real:** build GCC/MSVC, spawn, cierres, timeout y pruebas BCrypt contra vectores conocidos. No aprobar con una compilación Linux.
2. **Compilar y ejecutar Rust:** `cargo test`, luego pruebas Python contra la biblioteca, con consulta de ABI en el mismo build. Añadir grafos con lazos/aristas paralelas y medoids con empate.
3. **Ejecutar Dart:** resolver dependencia ffi, analizar y correr una rotación contra la biblioteca correspondiente.
4. **Condición y precisión:** barrido de condición de QR, comparar Householder con referencia fiable, incorporar estimador de rango/condición y caracterizar drift de rotaciones repetidas. La tolerancia actual es política, no teorema óptimo.
5. **IPC industrial:** definir supervisor, crash recovery, quiescencia y revocación de handles. Si se exige consumidor no confiable, sustituir las vistas cooperativas por una frontera de permisos adecuada.
6. **Optimizar sin alterar contratos:** perfilar, introducir BLAS/OpenMP tras verificar equivalencia y reportar costo/memoria. Recuperar SPSC solo con contrato propio y evidencia nativa.
7. **Integración cognitiva:** adaptadores entre espacios latentes y tests de utilidad de tarea. No inferir éxito de agentes desde ortogonalidad.
8. **Aceleradores:** implementar backends uno por uno con contratos de residencia, sincronización y precisión; el selector actual rechaza esas rutas.

No se entregan todavía: garantías universales de dos ULP, comunicación lock-free certificada, BFT, homología persistente, generador cuántico aproximado ni portabilidad hardware verificada.

Formato de razonamiento adaptado por AGT, 2026.
