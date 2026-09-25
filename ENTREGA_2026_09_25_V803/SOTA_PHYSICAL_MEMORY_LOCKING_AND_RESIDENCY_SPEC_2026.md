# 🏛️ ESPECIFICACIÓN MAESTRA DE BLOQUEO DE MEMORIA FÍSICA, RESIDENCIA Y DEFENSA ANTI-PAGING SOTA (V804+)

**Fecha:** 2026-09-25  
**Autor:** Ariel & Red Team Bulldog POLYDIM  
**Invariante:** Protección de Secreto $\ne$ Latencia Determinista $\ne$ Residencia GPU. Prohibido el bloqueo indiscriminado del heap.

---

## 1. 🛡️ CLASIFICACIÓN DE MEMORIA Y PRESUPUESTOS (Budgets)

```
┌────────────────────────────────────────────────────────┐
│ CLASE A: Secretos Efímeros (Claves / Nonces / Tokens)  │
│          Lock Obligatorio, Guard Pages, Zeroize Seguro │
├────────────────────────────────────────────────────────┤
│ CLASE B: Hot Path de Latencia (Ring Buffers / Slabs)   │
│          Prefault selectivo, mlock2(ONFAULT), Cap Fijo │
├────────────────────────────────────────────────────────┤
│ CLASE C: Caché Reconstruible (Índices / Lotes)         │
│          CERO Lock, sujeta a Reclaim y Eviction        │
├────────────────────────────────────────────────────────┤
│ CLASE D: Slabs Masivos Persistentes                    │
│          Large Pages (Win) / HugeTLB (Linux) Dedicadas │
└────────────────────────────────────────────────────────┘
```

### Regla de Admisión de Presupuesto:
$$B_{\text{locked}} + B_{\text{latency}} + B_{\text{gpu}} + B_{\text{runtime\_peak}} < B_{\text{host/cgroup\_safe}}$$
Si una nueva reserva excede el presupuesto admisible, se rechaza la solicitud con `RESOURCE_EXHAUSTED` antes de intentar la llamada al sistema.

---

## 2. ⚙️ ESTRATEGIA SOTA POR SISTEMA OPERATIVO

| Plataforma | Protección de Secreto (Clase A) | Hot Path de Latencia (Clase B) | Slabs Masivos (Clase D) | Gestión GPU |
| :--- | :--- | :--- | :--- | :--- |
| **Windows** | `SetProcessWorkingSetSizeEx(QUOTA_LIMITS_HARDWS_MIN_ENABLE)` + `VirtualAlloc` + `VirtualLock` + `SecureZeroMemory` | Working Set ampliado + `VirtualLock` sobre buffers materializados | `SEC_LARGE_PAGES` / `MEM_LARGE_PAGES` con `SeLockMemoryPrivilege` (ruta independiente de VirtualLock) | Direct3D12 Residency API |
| **Linux / Docker** | `mlock` sobre rango tocado + `MADV_DONTDUMP` | **`mlock2(addr, len, MLOCK_ONFAULT)`** selectivo (prohibido `mlockall(MCL_FUTURE)`) | `MAP_HUGETLB` / `MFD_HUGETLB` con páginas pre-reservadas en el cluster | IPC de CUDA / NVIDIA UVM |
| **macOS (Darwin)** | `mlock` sobre rangos mínimos privados de CPU | Prefault medido en buffers de CPU | Asignación estándar en memoria unificada (sin mlock masivo) | **`MTLResidencySet` (macOS 15+)** sobre `MTLBuffer` con `MTLStorageModeShared` |

---

## 3. 🏗️ DISEÑO DE LA ARENA SEGREGADA (`SecureArena`)

```
[Guard Page (PROT_NONE)]
  [Metadata de Control (No secreta)]
[Guard Page (PROT_NONE)]
  [Slot Crítico 1 (Páginas Bloqueadas + Zeroize)]
  [Slot Crítico 2 (Páginas Bloqueadas + Zeroize)]
[Guard Page (PROT_NONE)]
```

### Ciclo de Vida Transaccional:
1. **Verificación de Presupuesto:** Comprobar `locked_active_bytes + req <= B_admit`.
2. **Reserva y Mapeo:** Asignación privada con alineación a granularidad de página real (16 KB en Apple Silicon, 4 KB en x86-64).
3. **Páginas Guardia:** Delimitar bordes con `PAGE_NOACCESS` / `PROT_NONE` para atrapar *buffer overflows* lineales.
4. **Materialización y Bloqueo:**
   - Linux: `mlock2(p, size, MLOCK_ONFAULT)`.
   - Windows: `VirtualLock(p, size)` tras ajustar Working Set mínimo.
5. **Cero Silencio Operativo:** Si el bloqueo falla, se ejecuta `SecureZeroMemory`, se liberan las páginas y se devuelve el código de error estructurado (`EPERM`, `ENOMEM`, `ERROR_WORKING_SET_QUOTA`).
6. **Teardown Determinista:** `SecureZeroMemory` ➔ `VirtualUnlock` / `munlock` ➔ `VirtualFree` / `munmap`.

---

## 4. 🐳 CONTENCIÓN EN DOCKER Y KUBERNETES (Cgroups Defense)

1. **Monitoreo Proactivo de Cgroups:**
   - Inspección continua de `/sys/fs/cgroup/memory.current`, `memory.max`, `memory.high` y `memory.events` (`oom`, `oom_kill`).
   - Telemetría de `unevictable` para rastrear páginas fijadas por `mlock`.
2. **Configuración de Contenedor:**
   - `--cap-add=IPC_LOCK` y `--ulimit memlock=96m:96m` (calculado exactamente sobre el presupuesto de Clase A y B).
   - Prohibido `--ulimit memlock=-1:-1` ciego para evitar saturación del cgroup y ejecuciones violentas del OOM Killer.
