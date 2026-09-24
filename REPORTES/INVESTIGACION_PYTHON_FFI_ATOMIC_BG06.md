# INVESTIGACIÓN SOTA BG-06: BARRERAS DE MEMORIA Y PUBLICACIÓN ATÓMICA DESDE PYTHON

**Fecha de Ingesta:** 2026-09-18
**Veredicto:** ACEPTADO. El SeqLock en Python es una ilusión peligrosa y el estándar C++ dicta que leer datos concurrentemente mientras se escriben (incluso con validación SeqLock posterior) es Undefined Behavior (UB).

---

## 1. El Error del SeqLock Nativo en Tensores
Implementar un SeqLock clásico (contador impar/par) no es seguro para tensores de memoria compartida porque C++ considera que una "Data Race" (lectura concurrente de datos no-atómicos mientras otro hilo los escribe) rompe el estándar, independientemente de que el lector descarte el dato si detecta que la secuencia cambió.

## 2. Doble-Buffer y Relación Acquire/Release (Happens-Before)
La solución estricta es un esquema de doble-buffer donde la "publicación" del índice activo genera una barrera matemática de memoria `Happens-Before`:

1. Python posee el Buffer B exclusivamente.
2. Python escribe todo el tensor en el Buffer B (Sanitizado según BG-05).
3. Python llama a C++ FFI: `polydim_ffi.publish_write(buffer_index, next_sequence)`.

**El Lado C++ (FFI Writer):**
```cpp
void publish_write(uint32_t buffer, uint64_t next_sequence) {
    // Almacena el buffer activo (Relaxed porque lo que importa es la secuencia)
    active_buffer.store(buffer, std::memory_order_relaxed);
    
    // PUBLICA el tensor: std::memory_order_release garantiza que todas las
    // escrituras al tensor terminen físicamente ANTES de que la secuencia se actualice.
    sequence.store(next_sequence, std::memory_order_release);
}
```

**El Lado C++/Rust (Readers):**
```cpp
bool acquire_read(uint64_t& observed_sequence, uint32_t& buffer) {
    // std::memory_order_acquire garantiza que leemos la secuencia actualizada
    // y NINGUNA lectura del tensor ocurrirá antes de esta sincronización.
    uint64_t seq = sequence.load(std::memory_order_acquire);
    
    if (seq == observed_sequence) return false; // Nada nuevo
    
    buffer = active_buffer.load(std::memory_order_relaxed);
    observed_sequence = seq;
    return true; // Podemos leer del buffer activo con total seguridad
}
```

## 3. Contrato de Arquitectura (Regla Inquebrantable)
Python NUNCA modificará el bloque de control del PMTP por sí mismo. Solo escribirá tensores en la zona de datos que le pertenece (buffer inactivo). Toda gestión de estado (Publish, Acquire) pasa obligatoriamente por el FFI C++/Rust para heredar el modelo de memoria Acquire/Release del hardware x86/ARM.
