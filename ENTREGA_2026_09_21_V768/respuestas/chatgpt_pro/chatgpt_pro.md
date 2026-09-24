hoy 21:13

Completé una primera auditoría Red Team profunda del ZIP y preparé un informe técnico de **1.136 líneas**, con hallazgos reproducidos, archivo/línea, causa, impacto y parche propuesto.

Descargar auditoría completa POLYDIM V768

La conclusión principal es que **V768 todavía no puede considerarse “cierre industrial”**. No por criterios subjetivos, sino porque encontré defectos que pude reproducir directamente.

Los P0 más importantes son:

1. **Stiefel sigue ocultando memoria Θ(DK)** en `kernel\_cpp\_v768.cpp:622` mediante `G\_proj`. Para `D=10^7, K=512`, son **40,96 GB adicionales** sólo para ese buffer. La afirmación de workspace O(K²) no coincide con la implementación. 

2. **Triton falla justamente en D=10^7**. En `polydim\_triton\_kernel\_v768.py:149-157`, el fallback utiliza `math.sin()` pero `math` no está importado. Con `D=10^7`, el código entra exactamente en esa rama. 

3. **El supuesto zero-sync GPU sigue haciendo `.item()`**, tanto en la ruta normal como en fallback. Hay sincronización GPU→CPU antes del segundo kernel. 

4. **La interfaz Dart PMTP pertenece a otro ABI**. Nombres de símbolos, cantidad de argumentos, tipos y tamaño de `PMTPControl` no coinciden con el C++ V768. El C++ necesita una estructura alineada de 64 bytes; Dart define esencialmente **1 byte**. 

5. **`PMTPSlabChannel` de Python nunca inicializa PMTP** mediante `polydim\_pmtp\_init()`. Después puede entrar en C++ con `num\_slots==0`. 

6. Y aun si lo inicializara, `write\_tensor()` contiene literalmente: 

```
`\# Omitted payload write for brevity`
```

Publica `TENSOR\_READY` sin haber escrito el tensor.

7. **PMTP tiene UB por alineación demostrada con UBSan.** `PMTP\_Control` usa `alignas(64)`, pero `polydim\_pmtp\_init()` no comprueba que el caller haya proporcionado una dirección alineada. Con un desplazamiento de 8 bytes UBSan abortó con: 

```
`runtime error: member access within misaligned address ...`

`for type 'struct PMTP\_Control', which requires 64 byte alignment`
```

8. **`polydim\_pmtp\_sizeof()` tiene overflow entero real.** Probé: 

```
`polydim\_pmtp\_sizeof(64, UINT64\_MAX) = 4096`
```

cuando debería rechazar la operación.

9. **El `memset` utilizado para inicializar estructuras que contienen `std::atomic` es incorrecto como diseño de lifetime C++.** GCC ya lo marca con `-Wclass-memaccess`. 

10. **Un commit/abort PMTP inválido puede dejar el writer lock adquirido permanentemente.** Hay rutas `return` que no hacen `pmtp2\_unlock()`. 

11. **`project\_sphere` tiene corrupción reproducible por overlap parcial.** Con entrada `\[3,4\]` y `y\_out=y+1`, devolvió `SUCCESS` pero produjo memoria equivalente a: 

```
`\[3.0, 0.6, 0.12\]`
```

en vez de preservar el vector fuente y producir `\[0.6,0.8\]`.

12. **Rodrigues tiene el mismo problema con overlap parcial `y/y\_out`.** Sólo `y\_out==y` exacto es seguro. 

13. **La compensación TwoSum prometida no existe en el update Rodrigues.** El código real es simplemente: 

```
`y\_out\[i\] = y\[i\] + alpha \* u\[i\] + beta \* v\[i\];`
```

Por tanto no puede atribuirse al kernel una garantía basada en TwoSum que éste no implementa.

14. **Las tolerancias NaN permiten saltarse los invariantes.** Inyecté tolerancias NaN y vectores/bases de norma 2; el kernel devolvió `SUCCESS`. 

15. **FTZ/DAZ no se desactiva realmente.** Cuando `POLYDIM\_ENABLE\_FTZ=0`, `set\_fp\_mode()` no limpia MXCSR: simplemente no hace nada. Si el proceso llega con FTZ/DAZ habilitado, permanece habilitado mientras `build\_info()` afirma lo contrario. 

16. **El LSM separado sigue siendo Θ(D²).** Hace: 

```
`nnz = int(dim \* sparsity)`
```

y crea esa cantidad de conexiones para cada una de D neuronas. Con `D=10^7` y 5% son aproximadamente `5×10^12` conexiones.

17. El LSM monolítico sí fija `nnz=16`, pero **normalizar cada fila no produce una matriz ortogonal ni garantiza radio espectral 1**. Lo comprobé construyendo la matriz efectiva. En pruebas pequeñas aparecieron errores de ortogonalidad del orden de `0.8–1.8` y radio espectral alrededor de `1.05–1.08`. 

18. **El “Clifford+T compiler” no es actualmente un compilador Clifford+T.** Genera: 

```
`ry(theta)`
```

y después añade una supuesta aproximación Clifford+T. Es decir, aplica ambas.

Además, `eps\_target` no controla realmente el error de síntesis.

19. La conversión: 

```
`q1 = p1 % num\_qubits`

`q2 = p2 % num\_qubits`
```

**no implementa una rotación Givens arbitraria entre amplitudes `|p1\>` y `|p2\>`**. Un índice de estado no es un índice de qubit.

20. **MIR-Wire no es RDMA en la implementación entregada.** Es TCP `SOCK\_STREAM`, `sendall`, `recv\_into` y `bytearray`. 

Eso es perfectamente válido como emulador funcional, pero no demuestra RDMA zero-copy físico.

21. Encontré además una corrupción lógica reproducible en MIR-Wire: anuncié un payload de 16 bytes y envié sólo 8. El receptor respondió: 

```
`ACK`
```

y aceptó:

```
`\[1.25, 0.0\]`
```

como tensor válido.

22. El servidor también acepta `tensor\_bytes` directamente desde la red y hace: 

```
`bytearray(tensor\_bytes)`
```

sin límite superior: vector de DoS de memoria.

23. **El Rust “Betti-1 guard” no verifica β₁.** Cuenta edges y componentes, pero nunca calcula o contrasta: 

β1=E−V+C\\beta\_1 = E - V + C 

Sólo certifica conectividad.

24. `catch\_unwind` **no protege contra punteros FFI inválidos**. Un `slice::from\_raw\_parts()` sobre memoria dangling es UB, no un panic capturable. 

25. **El Tangent Adapter no es biyectivo sobre todo RD\\mathbb\{R\}^D.** Matemáticamente, la representación: 

h→(h∥h∥,log⁡∥h∥)h\\rightarrow \\left(\\frac h\{\\|h\\|\},\\log \\|h\\|\\right) 

es biyectiva sólo para h≠0h\\neq0.

El código además hace que todos los vectores con norma inferior a epsilon colapsen en una representación artificial con `r=-100`.

26. Con un vector completamente finito: 

```
`\[1e308, 1e308, 0\]`
```

`np.linalg.norm()` desbordó y el adapter produjo `NaN/Inf`.

27. La afirmación teórica de que serializar texto/JSON **“viola DPI”** necesita corregirse. DPI no dice eso. Una codificación determinista puede ser inyectiva y no perder información; el argumento sólido contra tokenización debe basarse en cuantización, geometría, latencia, throughput y semántica del receptor. 

28. Una isometría global lineal `3072 → 1536` tampoco puede ser biyectiva: por rango–nulidad necesariamente existe kernel. La conservación puede sostenerse sólo sobre un subespacio/manifold de dimensión intrínseca ≤1536, que es una formulación mucho más defendible. 

29. **No se incluyeron los raw logs que el dossier cita.** Tampoco están `polydim.h`, `polydim\_kernel.h`, CMake/Cargo ni los `eval\_logs/...`. 

Por eso métricas como T4, TPU, Cerebras y “250.6×” quedan clasificadas como **no verificables desde el artefacto proporcionado**, no como falsas.

30. Hay además una inconsistencia de tráfico GPU: para el Triton actual, dos pasadas implican como mínimo unos **560 MB** de tráfico vectorial en D=10^7. El valor publicado de `70.51 GB/s × 4.538 ms ≈ 320 MB` parece contabilizar sólo cuatro vectores. La fórmula de bandwidth debería hacerse explícita. 

Un resultado positivo que sí confirmé técnicamente: compilé también el kernel con `-ffast-math`, y el self-test de compensación devolvió correctamente:

```
`POLYDIM\_ERR\_COMPENSATION\_BROKEN = -12`
```

Es decir, ese detector concreto funciona en la configuración probada. No extrapolé ese resultado a aquello que no pude demostrar.

La arquitectura de reparación que propongo en el informe empieza por **ABI único → PMTP v3 → kernels numéricos → Stiefel matrix-free real → LSM estructuralmente ortogonal → backend RDMA auténtico separado del simulador → quantum verificable → CI con evidencia reproducible**.

Mi prioridad inmediata sería cerrar primero los hallazgos **F-001 a F-019 y F-022/F-028/F-033/F-038**, antes de añadir ninguna feature nueva. Son los que pueden invalidar ejecución, memoria o resultados matemáticos.

Auditoría completa con los 55 hallazgos y parches

que has usado el formato de razonamiento adaptado por AGT\_2026

