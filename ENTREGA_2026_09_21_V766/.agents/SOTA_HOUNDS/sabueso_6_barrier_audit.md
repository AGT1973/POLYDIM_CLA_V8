# [SABUESO RED TEAM] C-FFI SEQLOCK BARRIER AUDIT
**Target:** Apple Silicon (AArch64 / ARMv8)
**Primitive:** `std::atomic_thread_fence(std::memory_order_acquire)` -> Compiles to `DMB ISHLD`
**Verdict:** MATHEMATICALLY SUFFICIENT. CERRADO.

## 1. Topología del Riesgo (The "Sinking" Vector)
El vector de ataque en un Seqlock Reader sobre hardware AArch64 (Weakly Ordered) ocurre en la segunda validación de secuencia. Un código naive ejecuta:
1. `seq0 = load(acquire)` (Emite instrucción `LDAR`)
2. `payload = mmap_read()` (Instrucciones estándar `LDR`/`LDP`)
3. `seq1 = load(acquire)` (Emite instrucción `LDAR`)

**El Fallo Físico:** En ARMv8, una carga con semántica acquire (`LDAR` en el paso 3) previene de forma estricta que instrucciones **subsecuentes** suban antes de ella. Sin embargo, **NO previene que instrucciones precedentes (el `payload` del paso 2) se hundan (sink past) después de ella**. Si el procesador reordena las cargas del `mmap` para ejecutarse después de leer `seq1`, el lector validará una secuencia "limpia", pero leerá un payload corrupto sobreescrito por un escritor concurrente.

## 2. Resolución de la Barrera: `DMB ISHLD` vs `DMB SY`
Al inyectar explícitamente `std::atomic_thread_fence(std::memory_order_acquire)` entre la lectura del payload y la segunda secuencia, GCC/Clang emiten en AArch64 la barrera **`DMB ISHLD`** (Data Memory Barrier, Inner Shareable, Load-Load/Load-Store).

*   **Suficiencia Asintótica de `DMB ISHLD`:** La especificación arquitectónica ARMv8 garantiza que una barrera `DMB ISHLD` obliga a que todas las cargas previas en program order (`mmap_read`) sean completadas y observadas en el dominio coherente (Inner Shareable) **antes** de cualquier acceso a memoria subsecuente (la carga de `seq1`). Esto ancla físicamente el payload y bloquea matemáticamente el out-of-order execution hacia abajo.
*   **Rechazo Empírico de `DMB SY`:** `DMB SY` (Full System Barrier) sincroniza globalmente flujos de Store-Store y Store-Load. Dado que un Seqlock Reader pasivo **no emite stores** al bloque de memoria compartida IPC (sólo lee el struct y la secuencia), el uso de `DMB SY` es una tautología arquitectónica conservadora y un desperdicio neto de ciclos de reloj. `DMB ISHLD` proporciona la garantía estricta de Load-Load necesaria.

## 3. C-FFI / Python mmap Boundary
Dado que la memoria está mapeada vía IPC estándar (coherente con la caché CPU) y no como Non-Cacheable/Device Memory, el dominio `Inner Shareable` de la barrera cubre perfectamente los accesos C-FFI desde Python. 

**Veredicto Final:** El parche implementado es asintóticamente riguroso. La barrera es estructuralmente óptima. No hay alucinaciones de concurrencia. No es necesario matar ni reformular el approach.
