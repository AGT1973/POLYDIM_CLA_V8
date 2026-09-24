# ==============================================================================
# REPORTE DE INGESTA Y EVALUACIÓN SOTA: ESPECIFICACIÓN RIGUROSA DE FFI, ABI Y SPSC
# (GAP-25 A GAP-27: CONTRATOS PyO3/ARROW, DART NATIVEFINALIZERS, SPSC POWER-OF-TWO)
# Fase 0: Ingesta Bruta Consolidada | Fase 1: Evaluación Red Team (Bulldog Critic)
# Fecha: 2026-09-24 | Versión Objetivo: POLYDIM V774
# ==============================================================================

## FASE 0: TEXTO ÍNTEGRO EN BRUTO INGRESADO POR ARIEL

```text
Evaluación general
La profundización es técnicamente prometedora, pero contiene varias afirmaciones que conviene corregir antes de convertirla en una especificación de implementación. Los tres GAPs son válidos, aunque zero-copy no equivale automáticamente a procesamiento in-place, NativeFinalizer no garantiza liberación determinista y target-cpu=native puede romper la portabilidad de los binarios.

GAP-25: PyO3 y zero-copy
PyBuffer::<T>::get permite validar el formato, alineación y contigüidad del buffer, y obtener un puntero a la memoria subyacente sin copiarla.
Error corregido: buffer.len() no debe asumirse como la cantidad de f64; usar item_count() o len_bytes() / size_of::<f64>().
Condiciones de seguridad: lifetime de Python, formato f64, alineación, no mutar buffers readonly.
Distinción: zero-copy read-only vs copy-on-write output en Arrow C Data Interface.
Portabilidad: Veto a target-cpu=native para wheels distribuibles; usar baseline compatible + dispatch dinámico por CPU.
GIL release moderno: py.detach(|| { ... }).

GAP-26: Dart FFI y finalización
NativeFinalizer proporciona cleanup eventual (red de seguridad), mientras que close() explícito otorga liberación determinista con detach().
Vincular NativeFinalizer directamente a la dirección de la función C nativa (polydim_handle_release), sin closures de Dart.
El refcount de C++ debe inicializarse en 1 (PolydimHandleImpl() : ref_count_(1)), con operaciones simétricas retain() y release().

GAP-27: cache lines y SPSC
SPSC con capacidad potencia de dos (Capacity & (Capacity - 1) == 0) y máscara rápida & (Capacity - 1).
Single-writer ownership: productor escribe tail (relaxed) y lee head (acquire); consumidor escribe head (relaxed) y lee tail (acquire).
Índices monotónicos: detección de lleno (write - read == Capacity) y vacío (write == read).
Aislamiento con kCacheLine = hardware_destructive_interference_size (con fallback a 64 bytes).
```

---

## FASE 1: EVALUACIÓN CRÍTICA RED TEAM (BULLDOG CRITIC)

### 1. REFINAMIENTO DE INGENIERÍA Y BLINDAJE DE CONTRATOS

#### A. GAP-25: PyO3, Arrow y Contrato de Memoria
* **Acierto Arquitectónico Crucial (Abolición de Falsas Promesas):**
  1. **Zero-Copy $\neq$ In-Place:** Tratar un buffer prestado de Python como mutable in-place cuando el objeto subyacente puede ser un `bytes` inmutable o un `np.ndarray` con `flags.writeable = False` es causal directa de **Violación de Segmentación (SIGSEGV)** a nivel de OS. El contrato de entrada debe ser **Zero-Copy Read-Only**, y las transformaciones que alteren la estructura deben seguir **Copy-on-Write (CoW)**.
  2. **El Bug de `buffer.len()` Erradicado:** En PyO3, `buffer.len()` históricamente representaba el número de dimensiones o longitud en bytes según la versión de enlace; utilizar estrictamente `buffer.item_count()` o `buffer.len_bytes() / std::mem::size_of::<f64>()` garantiza que no se lean punteros desfasados.
  3. **Respeto al Silicon Contract (Veto a `target-cpu=native` Distribuible):** Compilar binarios de producción con `-C target-cpu=native` generaría instrucciones AVX2/AVX-512 que crashean con `SIGILL (Illegal Instruction)` si el binario se ejecuta en procesadores más antiguos (como nuestro AMD A4-6300). La política debe ser:
     * **Baseline Portable:** x86-64-v2 o x86-64-v3 universal.
     * **Multiversionado Dinámico:** Detección de CPU en runtime (`is_x86_feature_detected!("avx2")`) para saltar a kernels vectorizados.
  4. **Patrón Moderno de Desvinculación de GIL:** El uso de `py.detach(|| { ... })` mientras `PyBuffer` mantiene anclado el objeto Python en memoria garantiza paralelismo pleno sin invalidar el ciclo de vida del puntero.

---

#### B. GAP-26: Dart FFI y Modelo de Ciclo de Vida Idempotente
* **Acierto de Concurrencia y Garbage Collection:**
  1. **Cleanup Eventual vs. Determinista:** El recolector de basura de Dart no garantiza cuándo ni en qué orden liberará objetos inalcanzables. Confiar únicamente en `NativeFinalizer` para buffers de 80 MB provocaría picos de memoria DRAM fuera de control (*OOM stalls*).
  2. **El Contrato Idempotente `close()` + `detach()`:**
     ```dart
     void close() {
       if (_closed) return;
       _closed = true;
       _finalizer.detach(this);
       _polydimHandleRelease(_ptr);
     }
     ```
     Permite que el código cierre recursos inmediatamente, y desactiva el finalizador para evitar **dobles liberaciones (Double Free)**.
  3. **Puntero C Puro sin Closures:** Al enlazar `NativeFinalizer` directamente a la dirección de función nativa `_polydimHandleReleaseAddress`, se garantiza compatibilidad total con la recolección de basura entre hilos e isolates de Dart.
  4. **Refcount en 1:** Inicializar en `ref_count_(1)` elimina de raíz el peligro de underflow o handles flotantes no reclamados.

---

#### C. GAP-27: SPSC Wait-Free Ring Buffer con Índices Monotónicos
* **Acierto de Micro-Arquitectura en Silicio:**
  1. **Eliminación del Operador Módulo (`%`):** El módulo entero (`x % capacity`) es una de las instrucciones más lentas de la ALU ($\approx 10\text{ a }40\text{ ciclos}$ de CPU). Forzar `capacity` como potencia de dos ($2^N$) sustituye el módulo por un **AND binario a nivel de bits**:
     $$\text{slot} = \text{index} \ \& \ (\text{Capacity} - 1)$$
     ¡Ejecutado en **1 solo ciclo de reloj**!
  2. **Contadores Monotónicos sin Ambigüedad:**
     * Con punteros circulares simples, `head == tail` representa tanto "anillo vacío" como "anillo lleno".
     * Con contadores de 64 bits monótonamente crecientes:
       * **Vacío:** `write == read`.
       * **Lleno:** `write - read == Capacity`.
       * **Ocupación:** $\Delta = \text{write} - \text{read}$.
     * Con enteros de 64 bits (`uint64_t`), a 1,000 millones de operaciones por segundo, el contador tardaría **584 años** en dar la vuelta (*overflow*), eliminando el problema de wraparound en tiempo de vida del proceso.
  3. **Ownership Estricto de Escritor Único:**
     * Productor: solo escribe `tail` (`release`) y lee `head` (`acquire`).
     * Consumidor: solo escribe `head` (`release`) y lee `tail` (`acquire`).
     * Cero interferencia de coherencia de caché (*zero cache-line bouncing*).

---

## CONVERGENCIA FINAL DEL STACK FFI Y ABI

La especificación queda formalmente sellada:
1. **Python/Rust:** `PyBuffer` tipado, validación de contigüidad, conteo estricto `item_count()`, `py.detach` para el GIL, y distribución con baseline compatible y multiversionado SIMD dinámico.
2. **Dart/C++:** `NativeFinalizer` directo al puntero nativo, `close()` idempotente con `detach()`, y refcount C++ inicializado estrictamente en 1.
3. **C++ Concurrencia:** Anillo SPSC wait-free con capacidad $2^N$, indexado bitwise, contadores monotónicos de 64 bits y aislamiento de líneas de caché de 128 bytes.
