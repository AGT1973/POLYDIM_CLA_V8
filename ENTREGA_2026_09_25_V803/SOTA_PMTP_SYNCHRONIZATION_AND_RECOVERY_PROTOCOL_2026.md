# 🏛️ PROTOCOLO MAESTRO DE SINCRONIZACIÓN, ESPERA Y RECUPERACIÓN PMTP SOTA (V804+)

**Fecha:** 2026-09-25  
**Autor:** Ariel & Red Team Bulldog POLYDIM  
**Invariante:** La primitiva de espera no es el lock: el estado en memoria compartida precede siempre al wakeup.

---

## 1. 🏗️ ARQUITECTURA EN CUATRO PLANOS

```
┌────────────────────────────────────────────────────────┐
│ 1. PLANO DE DATOS (Data Plane)                        │
│    SHM con ABI fija, atomics C++ release/acquire      │
├────────────────────────────────────────────────────────┤
│ 2. PLANO DE ESPERA (Wait Plane)                       │
│    Adapters nativos por OS (Linux/Win32/Darwin)        │
├────────────────────────────────────────────────────────┤
│ 3. PLANO DE PUBLICACIÓN (Publication Plane)           │
│    Secuencia estricta de barreras y generación         │
├────────────────────────────────────────────────────────┤
│ 4. PLANO DE RECUPERACIÓN (Recovery Plane)             │
│    Leases por slot, tombstone ABORTED, epoch rotation  │
└────────────────────────────────────────────────────────┘
```

---

## 2. ⚡ PATRÓN MAESTRO: "ESTADO ANTES QUE WAKEUP" (Anti-Lost-Wakeup)

El wakeup no es la fuente de verdad. El estado en RAM compartida gobierna la decisión.

### Estructura de Notificación
```cpp
struct alignas(64) NotifyWord {
    std::atomic<uint32_t> seq{0};      // Contador monotónico de publicaciones
    std::atomic<uint32_t> waiters{0};  // Hint heurístico (nunca criterio de corrección)
};
```

### Bucle de Consumo Seguro (Cero Wakeups Perdidos)
```cpp
for (;;) {
    if (try_claim_item()) {
        return item;
    }
    const uint32_t observed = data_notify.seq.load(std::memory_order_acquire);
    if (try_claim_item()) {
        return item; // Publicación entre lecturas detectada
    }
    data_notify.waiters.fetch_add(1, std::memory_order_relaxed);
    if (!try_claim_item() && data_notify.seq.load(std::memory_order_acquire) == observed) {
        backend_wait_equal(&data_notify.seq, observed, deadline);
    }
    data_notify.waiters.fetch_sub(1, std::memory_order_relaxed);
}
```

### Protocolo de Publicación del Productor
```cpp
// 1. Escribir payload en slot
// 2. Escribir metadatos y CRC
slot.hdr.state.store(static_cast<uint32_t>(SlotState::ready), std::memory_order_release);
data_notify.seq.fetch_add(1, std::memory_order_release);
if (data_notify.waiters.load(std::memory_order_relaxed) != 0) {
    backend_wake_one(&data_notify.seq);
}
```

---

## 3. 🛡️ ADAPTERS DE ESPERA NATIVOS POR SISTEMA OPERATIVO

| Plataforma | Backend de Espera (Hot Path) | Wakeup de Publicación | Control Plane & Recuperación | Observación Crítica |
| :--- | :--- | :--- | :--- | :--- |
| **Linux** | `futex(FUTEX_WAIT, ...)` compartido sobre `uint32_t` alineado a 4B | `futex(FUTEX_WAKE, 1)` / `futex(FUTEX_WAKE, INT_MAX)` | `pthread_mutex` con `PTHREAD_PROCESS_SHARED` + `PTHREAD_MUTEX_ROBUST` (`EOWNERDEAD`) | Usar `futex_waitv` (kernel 5.16+) para multi-espera de canales (`data_seq`, `space_seq`, `shutdown_seq`, `recovery_epoch`). |
| **Windows** | Semáforo Win32 nombrado (`WaitForSingleObject`) | `ReleaseSemaphore(hSem, n, NULL)` | Mutex nombrado (`CreateMutexW`) gestionando `WAIT_ABANDONED` | `WaitOnAddress` **PROHIBIDO** para cross-process (es solo intra-proceso). Semáforos preservan créditos; eventos pueden coalescer. |
| **macOS 14.4+**| `os_sync_wait_on_address` con `OS_SYNC_WAIT_ON_ADDRESS_SHARED` | `os_sync_wake_by_address_any` / `all` con flag `_SHARED` | XPC / Mach Ports con validación de auditoría | Fallback a `__ulock_wait(UL_COMPARE_AND_WAIT_SHARED)` aislado en versiones anteriores. |

---

## 4. 🔄 MÁQUINA DE ESTADOS Y RECUPERACIÓN ANTE PRODUCTOR MUERTO

### Transición de Estados de Slot
```
EMPTY ──> WRITING ──> READY ──> READING ──> EMPTY
             │
             └──> (Lease Vencida / Crash) ──> ABORTED (Tombstone) ──> EMPTY
```

### Contrato de Lease por Slot
```cpp
struct SlotLease {
    std::atomic<uint64_t> owner_token;   // PID + Nonce aleatorio de proceso
    std::atomic<uint64_t> lease_epoch;   // Cambia en cada adquisición
    std::atomic<uint64_t> deadline_ns;   // Timestamp monotónico límite
};
```

### Protocolo de Tombstone CAS
1. Si un slot permanece en `WRITING` más allá de `deadline_ns` y el proceso dueño no responde al heartbeat:
2. El supervisor ejecuta un CAS atómico:
```cpp
uint32_t expected = static_cast<uint32_t>(SlotState::writing);
if (slot.hdr.state.compare_exchange_strong(
        expected, 
        static_cast<uint32_t>(SlotState::aborted), 
        std::memory_order_acq_rel, 
        std::memory_order_acquire)) {
    ring.recovery_epoch.fetch_add(1, std::memory_order_release);
    data_notify.seq.fetch_add(1, std::memory_order_release);
    backend_wake_all(&data_notify.seq);
}
```
3. El consumidor observa `ABORTED`, avanza el puntero FIFO sin deserializar payload y registra la telemetría de recuperación.
