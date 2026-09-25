# 🏛️ ESPECIFICACIÓN MAESTRA DE SEGURIDAD, CICLO DE VIDA Y CANAL ROBUSTO PMTP SOTA (V804+)

**Fecha:** 2026-09-25  
**Autor:** Ariel & Red Team Bulldog POLYDIM  
**Estado:** Inviolable — La memoria compartida transporta bytes, no confianza. El canal PMTP debe ser matemáticamente verificable, seguro ante fallos y de zero-copy estricto.

---

## 1. 🛡️ MODELO DE AMENAZAS Y MITIGACIONES PMTP

| Amenaza | Riesgo Físico | Mitigación Arquitectónica PMTP |
| :--- | :--- | :--- |
| **Name Squatting** | Un atacante pre-crea un objeto con nombre global esperado (`Global\`, `/dev/shm`). | **Objetos estrictamente anónimos** (`INVALID_HANDLE_VALUE` en Win32, `memfd_create` en Linux, Mach memory entry en macOS) y transferencia explícita de capability. |
| **Descriptor/Handle Leak** | Procesos hijos o no autorizados heredan el segmento. | Flags `MSG_CMSG_CLOEXEC`, handles Win32 sin herencia (`bInheritHandle = FALSE`), ACL/DACL restrictivas mínimas. |
| **Resize Malicioso** | Un peer reduce el segmento con `ftruncate(0)` causando `SIGBUS` al lector. | Tamaño inmutable antes de publicar; **Linux memfd seals** (`F_SEAL_SHRINK \| F_SEAL_GROW \| F_SEAL_SEAL`). |
| **Header Corrupto** | Lecturas fuera de límites, ABI mismatch, offsets absurdos. | Validación previa de `magic`, `abi_version`, `total_bytes`, límites de memoria y aritmética segura anti-overflow. |
| **Productor Caído (Dead Producer)**| Consumidor bloqueado esperando un slot reservado pero no publicado. | Sequence numbers de 64 bits por slot, heartbeat periódico, timeout, lease por slot o fail-stop con rotación de época. |
| **Consumidor Caído (Dead Consumer)**| El ring se llena permanentemente por falta de lectura (backpressure infinito). | Monitoreo de `consumer_heartbeat_ns` + `last_progress`, cancelación de sesión y purga de canal. |
| **ABA / Wraparound** | Reutilización rápida de un slot viejo aparenta ser un dato nuevo. | Contadores de secuencia y posición monotónicos de **64 bits (`uint64_t`)** por slot y canal. |
| **Lecturas Parciales / Torn Reads**| Consumidor lee datos antes de que el productor termine de volcar la memoria. | Semántica de memoria `release` en publicación del productor y `acquire` en lectura del consumidor. |
| **Peer No Autenticado** | Proceso local no autorizado obtiene el handle/FD. | Validación previa en control plane mediante `SO_PEERCRED` (Linux), tokens de seguridad SID/ACL (Win32), o auditoría XPC (macOS). |
| **DoS de Memoria** | Negociación de slabs gigantescos no respaldados. | Cuotas estrictas por peer, verificación de commit disponible y límites globales. |

---

## 2. 📐 CONTRATO DE MEMORIA BINARIA: `PmtpHeader` (128 Bytes Aislado)

```cpp
#include <cstdint>
#include <atomic>

struct alignas(128) PmtpHeader {
    uint64_t magic;                    // 0x504D545076303031ULL ("PMTPv001")
    uint32_t abi_version;              // Versión ABI (ej. 804)
    uint32_t header_bytes;              // sizeof(PmtpHeader) = 128
    uint64_t total_bytes;              // Tamaño total del segmento mmap
    uint64_t ring_offset;              // Offset hacia el área de datos (>= header_bytes)
    uint64_t ring_bytes;               // Bytes útiles para el ring buffer
    uint32_t slot_count;               // Cantidad de slots (potencia de 2 para SPSC/MPSC)
    uint32_t slot_stride;              // Tamaño en bytes de cada slot alineado
    uint64_t flags;                    // Flags de configuración y modos de precisión
    uint64_t session_id_hi;            // UUID de sesión (parte alta)
    uint64_t session_id_lo;            // UUID de sesión (parte baja)
    
    // Contadores atómicos con barreras y epochs
    std::atomic<uint64_t> producer_epoch;
    std::atomic<uint64_t> consumer_epoch;
    std::atomic<uint64_t> producer_heartbeat_ns;
    std::atomic<uint64_t> consumer_heartbeat_ns;
    
    uint64_t header_crc_or_mac;        // Checksum o firma SHA-256 de metadatos
    uint8_t  padding[16];              // Relleno a 128 bytes exactos
};
```

### Invariantes Obligatorios de Validación Previa:
1. `magic == 0x504D545076303031ULL`.
2. `abi_version == SUPPORTED_ABI_VERSION`.
3. `header_bytes >= sizeof(PmtpHeader)`.
4. `ring_offset >= header_bytes` y `ring_offset % 128 == 0`.
5. Comprobación de desbordamiento: `checked_add_u64(ring_offset, ring_bytes, &end) && end <= total_bytes`.
6. `slot_count > 0` y `checked_mul_u64(slot_count, slot_stride, &needed) && needed <= ring_bytes`.

---

## 3. 🔄 TOPOLOGÍA DE RING BUFFERS SPSC & MPSC

### A. SPSC (Single Producer Single Consumer) — El Estándar de Máxima Integridad
- **Aislamiento de Caché:** `write_pos` y `read_pos` se ubican en estructuras separadas alineadas a 128 Bytes (`alignas(128)`):
```cpp
struct alignas(128) ProducerState {
    std::atomic<uint64_t> write_pos;
    uint8_t reserved[120];
};

struct alignas(128) ConsumerState {
    std::atomic<uint64_t> read_pos;
    uint8_t reserved[120];
};
```
- **Publicación:** El productor escribe el payload, actualiza metadatos y hace `write_pos.store(new_pos, std::memory_order_release)`.
- **Consumo:** El consumidor lee `write_pos.load(std::memory_order_acquire)`, procesa el payload y actualiza `read_pos.store(new_pos, std::memory_order_release)`.

### B. MPSC (Multi-Producer Single Consumer) Robusto
- Contadores de secuencia de 64 bits por slot (`slot[i].sequence`):
  - Inicialización: `slot[i].sequence = i`.
  - Reserva productor: `p = global_tail.fetch_add(1)`. Espera a `slot[p % N].sequence == p`.
  - Publicación productor: `slot[p % N].sequence.store(p + 1, std::memory_order_release)`.
  - Consumo: Espera `slot[c % N].sequence == c + 1`, lee y marca libre con `slot[c % N].sequence.store(c + N, std::memory_order_release)`.
- **Mitigación de Productor Caído:** Arquitectura preferida: **un ring SPSC dedicado por cada productor** multiplexado en el consumidor mediante `epoll` / `futex_waitv` / Named Events Win32.

---

## 4. 🚪 BOOTSTRAP AUTENTICADO Y CONTROL PLANE POR SISTEMA OPERATIVO

| Sistema Operativo | Backing Store Físico | Transferencia de Capability | Control Plane Autenticado | Notificación / Wakeup |
| :--- | :--- | :--- | :--- | :--- |
| **Linux (POSIX)** | `memfd_create` (shm_mnt) con `F_SEAL_*` | Descriptor pasado por socket Unix con `SCM_RIGHTS` (`MSG_CMSG_CLOEXEC`) | Unix Domain Socket `SOCK_SEQPACKET` con `SO_PEERCRED` (valida UID/GID/PID) | `futex(FUTEX_WAIT/FUTEX_WAKE)` compartido (sin `_PRIVATE`) |
| **Windows (Win32)**| Sección anónima en pagefile (`CreateFileMappingW` con `INVALID_HANDLE_VALUE`) | `DuplicateHandle` hacia el PID destino autorizado | Named Pipe autenticado con ACLs/SIDs de proceso estrictos | Spin acotado + Win32 Named Event (`ReleaseSemaphore`) |
| **macOS (Darwin)** | `xpc_shmem` o Mach Memory Entry (`mach_make_memory_entry_64`) | Mensaje XPC / Mach Port | Conexión XPC con validación de entitlements y audit tokens | `os_sync_wait_on_address` con flag `_SHARED` (14.4+) o Mach IPC |
| **GPU (NVIDIA/Apple)**| `cudaIpcMemHandle` / `IOSurface` (`MTLStorageModeShared`) | IPC Handle por Control Plane | Control Plane OS correspondiente | Sincronización nativa por eventos CUDA o `MTLResidencySet` |

---

## 5. 🔄 MÁQUINA DE ESTADOS Y PROTOCOLO DE ROTACIÓN DE GENERACIÓN

```
[NEW] ──> [NEGOTIATING] ──> [INITIALIZING] ──> [READY] ──> [DRAINING] ──> [CLOSED]
                                  │
                                  └──> [PEER_SUSPECT] ──> [RECOVERING] ──> [FAILED / ROTATED]
```

### Regla de Oro de Recuperación: "Abandonar y Rotar"
1. **Cero Reparaciones In-Place:** Si un peer colapsa o un segmento se corrompe, **queda estrictamente prohibido intentar reparar la memoria compartida en caliente**.
2. **Rotación de Generación:**
   - El Control Plane crea un segmento anónimo nuevo: `Generation N+1`.
   - Se transfiere y verifica la capability con el peer sobreviviente.
   - Se confirma el estado `READY` en la nueva generación.
   - El segmento corrupto `Generation N` se drena/desmonta y se libera del sistema operativo.
