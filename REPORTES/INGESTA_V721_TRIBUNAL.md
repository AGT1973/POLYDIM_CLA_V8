# REPORTE DE INGESTA TRIBUNAL (V721) - REGLA 19
**ESTADO:** FASE DE ACUMULACIÓN (CÓDIGO BLOQUEADO).

Se procesaron las respuestas crudas de los Sabuesos (Gemini, DeepSeek, Kimi, ChatGPT) respecto a la V721. 
El asedio asintótico ($D=10,000$ a $D=1,000,000$) y el mandato de cero-alucinación destaparon **11 VULNERABILIDADES CRÍTICAS (P0)** de nivel silicio y matemático que los LLMs promedios jamás detectarían.

## HALLAZGOS SOTA (DEDUPLICADOS Y ANALIZADOS)

### VECTORES FÍSICOS Y DE SILICIO (Hardware)
1. **Falso Zero-Copy (C++):** El uso de `thread_local std::vector<float>` en el kernel fuerza un OS Page Fault que asigna memoria en el Heap (hasta 4MB por hilo en $D=1M$), destruyendo el concepto de Zero-Copy y ahogando el ancho de banda PCI-e.
2. **Cuello de botella Kahan (CPU):** El sumador Kahan en C++/Rust es escalar, creando una dependencia de bucle que destruye el Instruction-Level Parallelism (ILP). Requiere desenrollarse en un SIMD 4-way manual.
3. **Fallas de Alineación de Punteros (LLVM/GCC):** Aunque la estructura de 64B es correcta, el compilador desconoce la alineación de los arrays entrantes y emite `vmovups` (lectura no alineada lenta) en vez de `vmovaps`. Faltan las macros `__builtin_assume_aligned`.
4. **Determinismo Roto (GPU Triton):** `tl.atomic_add` en flotantes concurrentes sobre GPU *no es determinista*. El orden altera el redondeo en las colisiones atómicas, destruyendo la homología Betti-1 en el largo plazo.

### VECTORES MATEMÁTICOS Y TOPOLÓGICOS (S^(D-1))
5. **Colapso FP32 en Normalización ($D=1,000,000$):** `sum_sq` en FP64 puede alcanzar $3.4e41$. Al castear `norm = (float)sqrt(sum_sq)`, esto hace overflow a `+inf`. Luego `1 / inf = 0`. El tensor entero se vuelve `0.0` *sin emitir error de NaN o infinito*, engañando al orquestador. Presente tanto en C++ como en Rust (`as f32`).
6. **Singularidad Matemática Cayley:** Para $10^{-7} < ||v|| < 10^{-4}$, el tensor explota por pérdida de bits flotantes en `cayley_step` (`sin_t / v_norm`). Faltaba inyectar la expansión simétrica de Sinc Taylor que sí existe en `exp_map`.
7. **Precondición Oculta en Geodésica:** `acos(clamp(<u,v>))` no normaliza; requiere que `||u||` y `||v||` sean *estrictamente 1*. Si sufrieron el más mínimo drift de FP32, la métrica produce derivadas espurias.
8. **Proyección Tangente Ilegal:** La ecuación $v_T = v - \langle S,v \rangle S$ solo pertenece a la esfera si $||S|| = 1$. Si hubo drift, proyecta a un plano secante. Requiere $\langle S,v \rangle / \langle S,S \rangle$ o abortar.
9. **Contrato de Normalización Roto:** Usar `max(norm, 1e-7)` escala los tensores de norma casi cero a un radio menor a 1, sacándolos de la variedad $S^{D-1}$. El contrato real para esferas debe abortar (colapsar) si la norma no es 1 o cercana, en vez de "suavizarla".
10. **Mutación No Transaccional:** `S_next` se sobreescribe y luego se normaliza. Si la normalización falla, `S_next` ya está corrompido en memoria compartida.

---

**ACCIÓN REQUERIDA:**
Según la **Regla 19**, la generación de código permanece VETADA. 
El orquestador espera la señal explícita del Arquitecto (ej. "finish rule 19" o "luz verde V722") para sintetizar la solución definitiva en silicio.
