# PMTP multiplataforma: análisis SOTA por componente

Revisión en profundidad de la matriz de compatibilidad (Windows / Linux / macOS) para un transporte de memoria compartida (PMTP) con sincronización tipo futex, carga FFI y memoria bloqueada. Para cada celda: veredicto, causa real, solución SOTA y código de referencia.

Fecha de revisión: septiembre de 2026.

---

## 0. Veredictos rápidos

| # | Afirmación original | Veredicto | Gravedad |
|---|---|---|---|
| 1 | Windows shm "sensible a SeLockMemoryPrivilege" | Incorrecto: solo aplica a large pages | Media |
| 2 | Linux shm limitado por `/dev/shm` de 64 MB en Docker | Correcto, pero hay solución estructural (`memfd_create`) | Alta |
| 3 | macOS: `mmap` restringido por codesign entre usuarios | Incorrecto: las restricciones reales son otras | Media |
| 4 | Windows futex con `WaitOnAddress` | Correcto en API, **pero no funciona entre procesos** | **Crítica** |
| 5 | Linux futex con `FUTEX_WAIT_PRIVATE` | **Incorrecto para IPC**: rompe el despertar entre procesos | **Crítica** |
| 6 | Linux: 32 bits "por endianness" | Causa incorrecta: es ABI + alineación a 4 bytes | Baja |
| 7 | macOS "carece de futex" | Obsoleto: `os_sync_wait_on_address` desde 14.4 | Alta |
| 8 | Windows FFI con `os.add_dll_directory` | Correcto; faltan soluciones de empaquetado | Media |
| 9 | Linux FFI exige `RTLD_GLOBAL` | Parche frágil; hay alternativas mejores | Media |
| 10 | macOS `dlopen` bloqueado por SIP, firma con `@rpath` | Incorrecto: es library validation + firma arm64 | Alta |
| 11 | Windows `VirtualLock` + working set | Correcto | — |
| 12 | Linux `mlock` + `limits.conf` | Parcial: `limits.conf` no aplica en contenedores | Alta |
| 13 | macOS mlock (fila cortada) | Faltante: `mlockall` no disponible, límites de wiring | Media |

Contexto numérico: con \(D \geq 10^7\) elementos de 8 bytes, un slab ocupa \(\geq 80\) MB. Eso ya supera el `/dev/shm` por defecto de Docker (64 MB) y el `RLIMIT_MEMLOCK` por defecto de Linux (8 MB). Los problemas 2 y 12 aparecen desde el primer día.

---

## 1. Memoria compartida (PMTP)

### 1.1 Windows

**Qué está mal en la tabla.** `CreateFileMappingW` + `MapViewOfFile` no depende de `SeLockMemoryPrivilege`. Ese privilegio solo es necesario para crear mapeos con large pages (`SEC_LARGE_PAGES`) ([Microsoft Learn: large pages](https://learn.microsoft.com/en-us/windows/win32/memory/creating-a-file-mapping-using-large-pages)).

**Problemas reales:**

- **Espacio de nombres.** Crear un mapeo en `Global\` desde una sesión distinta de la 0 exige `SeCreateGlobalPrivilege` ([kernel object namespaces](https://learn.microsoft.com/en-us/windows/win32/termserv/kernel-object-namespaces), [privilege constants](https://learn.microsoft.com/en-us/windows/win32/secauthz/privilege-constants)). Un servicio y una app de usuario no se ven si uno usa `Local\` y el otro `Global\`.
- **Ciclo de vida.** No hay persistencia tipo `/dev/shm`: el objeto se destruye al cerrarse el último handle. Si el productor muere antes de que el consumidor abra, el segmento desaparece. Es un comportamiento seguro (no hay fugas), pero hay que diseñar el handshake alrededor de eso.
- **Commit charge.** Una sección de 80 GB respaldada por el pagefile (`INVALID_HANDLE_VALUE`) se descuenta completa del commit limit al crearse con `SEC_COMMIT` (el valor por defecto). Con slabs grandes y escasos conviene `SEC_RESERVE` y hacer commit por partes con `VirtualAlloc(MEM_COMMIT)`.
- **Tamaños mayores de 4 GB.** Se usan `dwMaximumSizeHigh` y `dwMaximumSizeLow`; es un bug clásico pasar solo la parte baja.

**SOTA:**

1. **Handles en vez de nombres**: crear la sección sin nombre y pasarla al otro proceso con `DuplicateHandle` (o heredarla). Así desaparecen las colisiones de nombres, el squatting y los problemas de `Global\`.
2. **`CreateFileMapping2` / `MapViewOfFile3`**: permiten elegir el nodo NUMA preferido ([CreateFileMapping2](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-createfilemapping2)) y, junto con `VirtualAlloc2(MEM_RESERVE_PLACEHOLDER)`, construir un **ring buffer con doble mapeo virtual** (el mismo buffer mapeado dos veces seguidas, así una escritura que cruza el final no necesita dividirse).
3. **Large pages** (opcional): `SEC_COMMIT | SEC_LARGE_PAGES`, tamaño múltiplo de `GetLargePageMinimum()`, privilegio "Lock pages in memory" asignado por política y activado con `AdjustTokenPrivileges`. Las large pages nunca se paginan, así que también resuelven el mlock (sección 4.1).

```c
// Productor: sección anónima + handle duplicado hacia el consumidor
HANDLE sec = CreateFileMappingW(INVALID_HANDLE_VALUE, NULL,
                                PAGE_READWRITE | SEC_RESERVE,
                                (DWORD)(size >> 32), (DWORD)size, NULL);
void *base = MapViewOfFile(sec, FILE_MAP_ALL_ACCESS, 0, 0, size);
VirtualAlloc(base, header_bytes, MEM_COMMIT, PAGE_READWRITE); // commit incremental
HANDLE remote;
DuplicateHandle(GetCurrentProcess(), sec, hConsumerProc, &remote,
                FILE_MAP_READ | FILE_MAP_WRITE, FALSE, 0);
// enviar el valor de `remote` al consumidor por pipe/socket
```

### 1.2 Linux

**Qué está bien.** Docker monta `/dev/shm` con 64 MB por defecto y se cambia con `--shm-size` ([Docker run reference](https://docs.docker.com/engine/containers/run/)).

**Qué falta:**

- `MAP_SHARED | MAP_ANONYMOUS` solo se comparte entre procesos emparentados por `fork`. No sirve para procesos independientes.
- **SIGBUS por truncado.** Si otro proceso hace `ftruncate` hacia abajo sobre el segmento, el lector recibe `SIGBUS` al tocar páginas fuera del nuevo tamaño. Con `/dev/shm` cualquiera con permisos puede hacerlo.
- **SIGBUS por tmpfs lleno.** En `/dev/shm` de 64 MB, `ftruncate(80 MB)` funciona (el archivo es disperso) pero la primera escritura que excede la capacidad da `SIGBUS`, no un error manejable. Por eso conviene hacer `fallocate` o `MAP_POPULATE` al crear, para fallar temprano con `ENOSPC`.
- **Fugas.** Los segmentos con nombre sobreviven al crash del proceso.

**SOTA: `memfd_create` + `SCM_RIGHTS` + sellos.**

- `memfd_create` crea un archivo anónimo que solo existe como fd ([man memfd_create](https://manpages.ubuntu.com/manpages/focal/man2/memfd_create.2.html)). No hay nombre global, y la memoria se libera sola cuando se cierra el último fd o mapeo ([análisis de IPC con shm](https://quant67.com/post/os/15-ipc-shm/ipc-shm.html)).
- Se pasa al otro proceso por un socket Unix con `SCM_RIGHTS`.
- Con `MFD_ALLOW_SEALING` y `F_SEAL_SHRINK | F_SEAL_GROW` nadie puede truncarlo, lo que elimina el SIGBUS provocado por un peer.
- Hasta donde sé, usa el montaje tmpfs interno del kernel y no `/dev/shm`, así que no le afecta `--shm-size`; el límite efectivo es el cgroup de memoria. Conviene verificarlo en el entorno destino con una prueba de 1 GB dentro del contenedor.
- Huge pages: `MFD_HUGETLB` (requiere páginas reservadas en `vm.nr_hugepages`) o THP para shmem vía `/sys/kernel/mm/transparent_hugepage/shmem_enabled`.

Así lo resolvió PyTorch: su estrategia por defecto `file_descriptor` pasa fds en lugar de nombres de archivo, y `file_system` queda como alternativa cuando se agotan los descriptores ([PyTorch multiprocessing](https://github.com/pytorch/pytorch/blob/main/docs/source/multiprocessing.rst)).

```c
int fd = memfd_create("pmtp", MFD_CLOEXEC | MFD_ALLOW_SEALING);
ftruncate(fd, size);
fallocate(fd, 0, 0, size);                        // falla con ENOSPC, no con SIGBUS
fcntl(fd, F_ADD_SEALS, F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_SEAL);
void *p = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_POPULATE, fd, 0);
// enviar fd con sendmsg + SCM_RIGHTS al consumidor
```

**Si se usa Python** (`multiprocessing.shared_memory`): en POSIX el `resource_tracker` puede hacer `unlink` de segmentos que el proceso no creó y emitir advertencias de fuga. Desde Python 3.13 existe el parámetro `track=False` para desactivarlo en los consumidores.

### 1.3 macOS

**Qué está mal en la tabla.** `codesign` no restringe `mmap` sobre `shm_open`. `MAP_SHARED | MAP_ANONYMOUS` funciona igual que en Linux (entre procesos emparentados por `fork`).

**Restricciones reales:**

- **Nombre de hasta 31 caracteres**, incluida la barra inicial, y con una sola barra ([notas de uso de shm_open en Mac](https://joe-cecil.com/things-i-learned-calling-shm_open-on-a-mac/)). Un nombre tipo `/pmtp-<uuid>` completo no entra; hay que usar un hash corto.
- **`ftruncate` una sola vez.** Un segundo `ftruncate` sobre el mismo objeto falla con `EINVAL`, aunque venga de otro `shm_open` ([mismo artículo](https://joe-cecil.com/things-i-learned-calling-shm_open-on-a-mac/), [análisis del EINVAL](https://coderivers.org/blog/ftruncate-not-working-on-posix-shared-memory-in-mac-os-x/)). El segmento no puede crecer: hay que dimensionarlo al crearlo o encadenar segmentos.
- **App Sandbox.** En apps con sandbox, el nombre debe llevar como prefijo el identificador del App Group ([Apple Developer Forums](https://developer.apple.com/forums/thread/751241)).
- **Páginas de 16 KB en Apple Silicon.** Los offsets de `mmap` y los buffers `bytesNoCopy` de Metal deben estar alineados a 16 KB, no a 4 KB. Hay que usar `getpagesize()` o `vm_page_size`, nunca la constante 4096.
- **Línea de caché.** En los chips M la línea reportada (`sysctl hw.cachelinesize`) es de 128 bytes; alinear contadores de productor y consumidor a 64 bytes deja false sharing.

**SOTA:**

1. **XPC shared memory**: `xpc_shmem_create` / `xpc_shmem_map` envuelven una región en un objeto XPC que se pasa por conexión, sin nombres globales ([Apple XPC objects](https://developer.apple.com/documentation/xpc/xpc-objects)).
2. **Mach memory entries**: `mach_make_memory_entry_64` + enviar el puerto. Es el mecanismo de bajo nivel que XPC usa por debajo. Para ring buffers con doble mapeo se usa `mach_vm_remap`.
3. **Datos de GPU**: `IOSurface` es la forma correcta de compartir memoria de textura entre procesos; el handle se envía por Mach IPC o XPC ([IOSurface en profundidad](https://www.macinternals.app/en/blog/iosurface-in-depth), [Russ Bishop](http://www.russbishop.net/cross-process-rendering)). Para buffers genéricos, `MTLBuffer` con `storageModeShared` sobre la memoria unificada.
4. **`newBufferWithBytesNoCopy`**: puntero alineado a página y longitud múltiplo de página ([cadena zero-copy mmap→Metal](https://lilting.ch/en/articles/wasm-metal-zero-copy-gpu-inference-apple-silicon)).

### 1.4 Recomendación transversal

Antes de mantener un transporte propio conviene evaluar [iceoryx2](https://github.com/eclipse-iceoryx/iceoryx2): IPC zero-copy y lock-free con núcleo en Rust, bindings para C, C++ y Python, y soporte para Linux, Windows y macOS ([iceoryx.io](https://iceoryx.io/)). Si PMTP tiene requisitos que iceoryx2 no cubre, al menos sirve como referencia de diseño para el layout, la detección de peers muertos y el ciclo de vida.

---

## 2. Concurrencia (futex)

### 2.1 Windows

**Problema crítico.** `WaitOnAddress` / `WakeByAddress*` son Windows 8+ y requieren `Synchronization.lib` (esto sí es correcto) ([shift.click: futex-like APIs](https://shift.click/blog/futex-like-apis/)), **pero solo funcionan dentro del mismo proceso** ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitonaddress), [comparativa](https://comcomponent.com/blog/2026/03/16/006-windows-timer-vs-event-wait/), [Raymond Chen](https://devblogs.microsoft.com/oldnewthing/20160823-00/?p=94145)). Si el productor escribe en la memoria compartida y llama a `WakeByAddressSingle`, un consumidor en otro proceso **nunca despierta**. Es un deadlock silencioso que puede no aparecer en pruebas si ambos lados corren en el mismo proceso.

**SOTA para IPC: contador de secuencia + contador de waiters + semáforo o evento con nombre.**

- Rápido: spin acotado sobre el atómico en memoria compartida (sin syscall).
- Lento: el consumidor declara que va a dormir (`waiters++`), vuelve a comprobar y espera en un objeto de kernel. El productor solo hace syscall si `waiters > 0`.
- Para SPSC basta un **auto-reset event** por consumidor; para MPMC, un **semáforo**.
- Bonus: un `Mutex` de kernel con nombre avisa con `WAIT_ABANDONED` si el dueño murió, algo que sirve para detectar peers caídos.

```c
typedef struct { _Alignas(128) atomic_uint seq; _Alignas(128) atomic_uint waiters; } pmtp_sync;

void pmtp_wait(pmtp_sync *s, unsigned seen, HANDLE sem, DWORD ms) {
    for (int i = 0; i < 2000; i++)                    // spin acotado
        if (atomic_load_explicit(&s->seq, memory_order_acquire) != seen) return;
    atomic_fetch_add(&s->waiters, 1);
    if (atomic_load(&s->seq) == seen)                 // re-chequeo tras anunciarse
        WaitForSingleObject(sem, ms);
    atomic_fetch_sub(&s->waiters, 1);
}
void pmtp_wake(pmtp_sync *s, HANDLE sem) {
    atomic_fetch_add_explicit(&s->seq, 1, memory_order_release);
    unsigned w = atomic_load(&s->waiters);
    if (w) ReleaseSemaphore(sem, (LONG)w, NULL);      // el semáforo cuenta: no hay wake perdido
}
```

`WaitOnAddress` sigue siendo la opción correcta para sincronización entre hilos de un mismo proceso (Boost.Atomic lo usa directamente desde Windows 8 ([Boost changelog](https://www.boost.org/doc/libs/1_85_0/libs/atomic/doc/html/atomic/changelog.html))).

### 2.2 Linux

**Problema crítico.** `FUTEX_WAIT_PRIVATE` / `FUTEX_WAKE_PRIVATE` identifican el futex por dirección virtual dentro del `mm` del proceso. Solo sirven cuando todos los participantes comparten espacio de memoria (hilos). Para compartir un futex entre procesos hay que usar las variantes sin `_PRIVATE` ([kernel.org futex2](https://docs.kernel.org/userspace-api/futex2.html), [man futex(2)](https://man.archlinux.org/man/futex.2.en)). Con `_PRIVATE` en memoria compartida, el wake del productor no encuentra al waiter del consumidor.

**Corrección de la causa.** La palabra es de 32 bits por ABI del syscall y debe estar alineada a 4 bytes (si no, `EINVAL`). La endianness no tiene nada que ver.

**SOTA:**

- `futex(FUTEX_WAIT/FUTEX_WAKE)` compartido con `FUTEX_WAIT_BITSET` y `FUTEX_CLOCK_REALTIME` o `MONOTONIC` para timeouts absolutos (evita drift al reintentar tras `EINTR`).
- `futex_waitv` (Linux 5.16) para esperar en varios futex a la vez, por ejemplo varios rings o "dato listo o shutdown" ([Collabora: futex_waitv](https://www.collabora.com/news-and-blog/blog/2022/02/08/landing-a-new-syscall-part-what-is-futex/)).
- **Robustez ante crash del peer.** Si se usan locks (no solo notificación), usar `pthread_mutex` con `PTHREAD_PROCESS_SHARED` + `PTHREAD_MUTEX_ROBUST`: el siguiente que lo toma recibe `EOWNERDEAD`. Para protocolos lock-free, contadores de generación + heartbeat.

```c
static inline void pmtp_futex_wait(uint32_t *a, uint32_t expected, const struct timespec *rel) {
    // SIN _PRIVATE: la clave del futex es (inode/página, offset), válida entre procesos
    syscall(SYS_futex, a, FUTEX_WAIT, expected, rel, NULL, 0);   // EAGAIN/EINTR -> re-chequear
}
static inline void pmtp_futex_wake(uint32_t *a, int n) {
    syscall(SYS_futex, a, FUTEX_WAKE, n, NULL, NULL, 0);
}
```

### 2.3 macOS

**Qué está obsoleto.** macOS 14.4 agregó una API pública tipo futex ([notas de macOS 14.4](https://developer.apple.com/documentation/macos-release-notes/macos-14_4-release-notes)) en `<os/os_sync_wait_on_address.h>` ([cabecera publicada](https://gist.github.com/BlackHoleFox/00ca98a94fc75e7c48418a0685f4d050)):

- `os_sync_wait_on_address(addr, value, size, flags)`, más variantes con timeout y deadline.
- `os_sync_wake_by_address_any` / `_all`.
- `size` de 4 u 8 bytes (a diferencia de Linux, admite 64 bits).
- **`OS_SYNC_WAIT_ON_ADDRESS_SHARED` / `OS_SYNC_WAKE_BY_ADDRESS_SHARED`** para direcciones en memoria compartida entre procesos.

Para versiones anteriores a 14.4 existe `__ulock_wait` / `__ulock_wake` (privada pero estable desde 10.12, usada por libc++, Rust y Zig) con la operación `UL_COMPARE_AND_WAIT_SHARED`. El patrón habitual es probar la API pública y caer en `__ulock` si no existe ([ejemplo kaze-core](https://deepwiki.com/starwing/kaze-core/6.2-synchronization-mechanisms)).

**Qué no usar:**

- `dispatch_semaphore_t`: no funciona entre procesos.
- `sem_init` (semáforos sin nombre): no está soportado en macOS; solo `sem_open` con nombre ([Stack Overflow](https://stackoverflow.com/questions/1413785/sem-init-on-os-x/1452182), [Medium](https://medium.com/helderco/semaphores-in-mac-os-x-fd7a7418e13b)).
- `pthread_mutex` robusto: macOS no implementa `PTHREAD_MUTEX_ROBUST`. La detección de peers muertos hay que hacerla con generación + heartbeat o con notificaciones de Mach (dead-name).

```c
#include <os/os_sync_wait_on_address.h>
extern int __ulock_wait(uint32_t op, void *addr, uint64_t val, uint32_t timeout_us);
extern int __ulock_wake(uint32_t op, void *addr, uint64_t wake_val);
#define UL_COMPARE_AND_WAIT_SHARED 3
#define ULF_WAKE_ALL 0x00000100

static inline void pmtp_wait(uint32_t *a, uint32_t expected) {
    if (__builtin_available(macOS 14.4, *))
        os_sync_wait_on_address(a, expected, 4, OS_SYNC_WAIT_ON_ADDRESS_SHARED);
    else
        __ulock_wait(UL_COMPARE_AND_WAIT_SHARED, a, expected, 0);
}
static inline void pmtp_wake_all(uint32_t *a) {
    if (__builtin_available(macOS 14.4, *))
        os_sync_wake_by_address_all(a, 4, OS_SYNC_WAKE_BY_ADDRESS_SHARED);
    else
        __ulock_wake(UL_COMPARE_AND_WAIT_SHARED | ULF_WAKE_ALL, a, 0);
}
```

Nota: `__ulock` es API privada; una app que va a la Mac App Store debería exigir 14.4+ y usar solo `os_sync`.

### 2.4 Abstracción portable

`std::atomic<T>::wait/notify` (C++20) y el crate `atomic-wait` de Rust dan futex portable **dentro de un proceso**. El estándar no garantiza que funcionen entre procesos y, en Windows, internamente usan `WaitOnAddress`, así que fallan en ese caso. Para PMTP hace falta un wrapper propio con tres backends:

| SO | Backend IPC |
|---|---|
| Linux | `FUTEX_WAIT`/`FUTEX_WAKE` compartidos (+ `futex_waitv`) |
| macOS | `os_sync_*` con `_SHARED` (14.4+) → `__ulock_*_SHARED` |
| Windows | spin + contador de waiters + semáforo o evento con nombre |

---

## 3. Carga FFI / bibliotecas dinámicas

### 3.1 Windows

**Qué está bien.** Desde Python 3.8, las dependencias de una DLL ya no se buscan en `PATH`: solo en ubicaciones confiables y en los directorios agregados con `os.add_dll_directory`. `CDLL` aceptó además un parámetro `winmode` para cambiar los flags de `LoadLibraryEx` ([What's New in Python 3.8](https://docs.python.org/3/whatsnew/3.8.html)).

**Detalles que suelen fallar:**

- `os.add_dll_directory` devuelve un handle: si se recolecta o se cierra, el directorio deja de estar en la búsqueda. Hay que guardarlo durante toda la vida del proceso.
- `winmode=0` restaura el comportamiento viejo (busca en `PATH`); funciona, pero reabre el DLL hijacking. No debería ser la solución por defecto.
- Si dos extensiones traen versiones distintas de `libgomp-1.dll` o `libstdc++-6.dll` con el mismo nombre, Windows carga la primera y la segunda extensión usa esa. Falla con errores de "procedimiento no encontrado" o crashes.

**SOTA:**

1. **Enlazar estático el runtime de MinGW**: `-static-libgcc -static-libstdc++ -Wl,-Bstatic -lwinpthread`. Así desaparecen `libgcc_s_seh-1.dll`, `libstdc++-6.dll` y `libwinpthread-1.dll`.
2. **[delvewheel](https://github.com/adang1345/delvewheel?tab=readme-ov-file)** para empaquetar las DLLs que quedan: las copia dentro del wheel, **les cambia el nombre agregando un hash** (evita choques entre paquetes) y parchea la carga. Es el equivalente de `auditwheel` y `delocate`. Las DLLs de plugins cargadas con `LoadLibrary` en runtime requieren `--analyze-existing` ([notas de tesseract_nanobind](https://tesseract-robotics.github.io/tesseract_nanobind/developer/windows-wheels/)).
3. **Un solo runtime de OpenMP en el proceso.** Mezclar libgomp (MinGW), vcomp (MSVC) y libiomp5 (Intel/LLVM) produce sobresuscripción de hilos o el error OMP #15. `KMP_DUPLICATE_LIB_OK=TRUE` solo silencia el error. Lo correcto es compilar todo contra el mismo runtime (con MSVC, `/openmp:llvm`) o exponer el pool de hilos del host.
4. En C/C++ nativo: `SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS)` + `AddDllDirectory`, o `LoadLibraryExW(path, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS)` para que las dependencias se busquen junto a la DLL.

### 3.2 Linux

**Qué está bien.** `ctypes.CDLL` carga con `RTLD_LOCAL` por defecto, así que los símbolos de una `.so` no quedan visibles para otras cargadas después.

**Por qué `RTLD_GLOBAL` es un parche frágil:** mete todos los símbolos en el espacio global. La interposición de símbolos hace que la primera definición gane: si dos extensiones traen versiones distintas de la misma biblioteca estática (protobuf, abseil, OpenSSL), una termina llamando código de la otra. Es la fuente clásica de crashes en `import torch` + `import tensorflow`.

**SOTA:**

1. **Biblioteca "core" compartida por dependencia, no por visibilidad global**: las extensiones enlazan contra `libpmtp_core.so` (`DT_NEEDED`) con `RPATH=$ORIGIN`. El loader deduplica por `SONAME`: una sola copia, sin `RTLD_GLOBAL`.
2. **Ocultar símbolos**: `-fvisibility=hidden` + version script (`-Wl,--version-script=pmtp.map`) que exporte solo la API C, y `-Wl,--exclude-libs,ALL` para no reexportar las estáticas. Si hace falta, `-Bsymbolic` para que la biblioteca resuelva primero sus propios símbolos.
3. **`auditwheel repair`**: copia las dependencias externas dentro del wheel, con nombres con hash, y ajusta el RPATH ([auditwheel](https://pypi.com.cn/project/auditwheel/), [maturin](https://deepwiki.com/PyO3/maturin/3.6-auditwheel-and-linux-compliance)). Consecuencia: dos paquetes que traen libgomp terminan con `libgomp-<hash>.so` distintos, es decir **dos pools OpenMP**. Se detecta con `threadpoolctl` y se limita con `OMP_NUM_THREADS` o con una API explícita.
4. **Rust**: cada `cdylib` incluye estáticamente su propia `std` y su propio allocator. No se pueden pasar `Vec`, `String` ni `Box` entre dos `.so` de Rust, y liberar en una lo que reservó otra es comportamiento indefinido. La regla es **ABI C en las fronteras** (o `abi_stable`), o bien un único `cdylib` que exporte todo.

### 3.3 macOS

**Qué está mal en la tabla.** SIP no bloquea `dlopen` de dylibs de usuario, y `@rpath` no tiene relación con la firma.

**Qué pasa en realidad:**

- **SIP** protege binarios del sistema y **borra las variables `DYLD_*`** (incluida `DYLD_LIBRARY_PATH`) al lanzar binarios protegidos. Trampa frecuente: un script con `#!/bin/sh` que exporta `DYLD_LIBRARY_PATH` y luego ejecuta Python pierde la variable, porque `/bin/sh` está protegido.
- **Library validation del Hardened Runtime**: un proceso firmado con Hardened Runtime solo carga dylibs firmadas por Apple o por el mismo Team ID, salvo que tenga el entitlement [`com.apple.security.cs.disable-library-validation`](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation) ([Hardened Runtime](https://developer.apple.com/documentation/security/hardened-runtime)). Esto afecta a hosts firmados (apps propias, algunos Python empaquetados) que cargan plugins.
- **Firma obligatoria en arm64**: todo código arm64 debe tener al menos firma ad-hoc. El linker la agrega, pero **`install_name_tool` la invalida** ([Apple Developer Forums](https://forums.developer.apple.com/forums/thread/747909)) y el proceso muere con `Killed: 9` o "code signature invalid" al cargarla.
- **Cuarentena (Gatekeeper)**: una dylib descargada lleva el atributo `com.apple.quarantine` y puede ser rechazada.

**SOTA (flujo de empaquetado):**

```bash
# 1. Install name relativo al rpath y rpath relativo al que carga
install_name_tool -id @rpath/libpmtp.dylib libpmtp.dylib
install_name_tool -add_rpath @loader_path _pmtp_ext.so
# 2. Volver a firmar tras modificar (obligatorio en arm64)
codesign --force --sign - libpmtp.dylib _pmtp_ext.so
# 3. Wheels: vendorizar dependencias y reescribir rutas
delocate-wheel -w fixed/ -v dist/pmtp-*.whl
# 4. Distribución fuera de la App Store: firma Developer ID + notarización
xattr -d com.apple.quarantine libpmtp.dylib   # solo en desarrollo
```

[delocate](https://pypi.org/project/delocate/) es el equivalente de auditwheel para macOS. Si se modifica cualquier binario después de firmar, la notarización falla ([Apple: notarization issues](https://developer.apple.com/documentation/security/resolving-common-notarization-issues)). Para distribuir, conviene generar wheels `arm64` y `x86_64` (o `universal2`) con cibuildwheel ([cibuildwheel FAQ](https://cibuildwheel.pypa.io/en/v2.16.1/faq/)).

---

## 4. Memoria bloqueada (mlock)

### 4.1 Windows

**Qué está bien.** Cada proceso tiene un límite de páginas bloqueables intencionalmente pequeño. Para bloquear más hay que subir antes el working set mínimo y máximo con `SetProcessWorkingSetSize`; el máximo bloqueable es el working set mínimo menos un pequeño overhead ([Microsoft Learn: VirtualLock](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtuallock)).

**Detalles:**

- Todas las páginas del rango deben estar comprometidas (committed); `PAGE_NOACCESS` no se puede bloquear ([VirtualLock](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtuallock)). Con `SEC_RESERVE` (sección 1.1) hay que hacer commit antes de bloquear.
- Usar `SetProcessWorkingSetSizeEx` con `QUOTA_LIMITS_HARDWS_MIN_ENABLE` si se quiere que el mínimo sea duro.
- Las páginas bloqueadas no se escriben al pagefile mientras sigan bloqueadas ([VirtualLock](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtuallock)).

**SOTA:** para slabs de \(D \geq 10^7\), las **large pages** (`SEC_LARGE_PAGES`, sección 1.1) resuelven dos cosas a la vez: nunca se paginan (bloqueo implícito, sin tocar el working set) y reducen los fallos de TLB. El costo es exigir el privilegio "Lock pages in memory" y reservar temprano, porque la memoria física contigua se fragmenta con el uptime.

```c
SIZE_T need = slab_bytes + (16u << 20);                       // margen
SetProcessWorkingSetSizeEx(GetCurrentProcess(), need, need + (64u << 20),
                           QUOTA_LIMITS_HARDWS_MIN_ENABLE | QUOTA_LIMITS_HARDWS_MAX_DISABLE);
if (!VirtualLock(base, slab_bytes)) { /* GetLastError(): ERROR_WORKING_SET_QUOTA */ }
```

### 4.2 Linux

**Qué cambió.** El `RLIMIT_MEMLOCK` por defecto pasó de 64 KB a 8 MB en el kernel 5.16 ([systemd #16300](https://github.com/systemd/systemd/issues/16300), [cryptsetup #749](https://gitlab.com/cryptsetup/cryptsetup/-/issues/749)). Sigue siendo muy poco para 80 MB.

**Qué está mal en la tabla.** `/etc/security/limits.conf` lo aplica `pam_limits` al abrir una sesión PAM (login, ssh, sudo). **No aplica** en contenedores, servicios de systemd ni procesos lanzados por orquestadores. Ahí hay que usar:

| Entorno | Mecanismo |
|---|---|
| Docker | `--ulimit memlock=-1:-1` o `--cap-add IPC_LOCK` |
| systemd | `LimitMEMLOCK=infinity` en la unidad |
| Kubernetes | `securityContext.capabilities.add: [IPC_LOCK]` (no hay campo de ulimit por pod) |
| Cualquiera | `CAP_IPC_LOCK` ignora el límite |

**Riesgos de `mlockall(MCL_CURRENT | MCL_FUTURE)`:**

- `MCL_FUTURE` bloquea (y rellena) cada mapeo futuro: pilas de hilos, arenas de malloc, mapeos de bibliotecas. Un `mmap` grande reservado "por si acaso" consume RAM real de inmediato o falla con `ENOMEM`.
- `mlockall` también bloquea memoria compartida y archivos mapeados ([man mlock(2)](https://man.archlinux.org/man/mlock.2.en)).
- La memoria bloqueada sigue contando para el cgroup de memoria: en vez de irse al swap, el contenedor muere por OOM.

**SOTA:**

- **`mlock2(addr, len, MLOCK_ONFAULT)`** (Linux 4.4): bloquea solo el slab, página a página a medida que se toca ([man mlock(2)](https://man.archlinux.org/man/mlock.2.en)). Equivalente global: `mlockall(MCL_CURRENT | MCL_ONFAULT)`.
- O prefault explícito: `MAP_POPULATE` + `mlock(slab)` al arrancar, para fallar temprano.
- Evitar `MAP_LOCKED`: si el bloqueo falla no devuelve error, solo lo intenta.
- Huge pages (`MAP_HUGETLB`, o `MFD_HUGETLB` en el memfd): las páginas hugetlbfs no van al swap, así que también funcionan como bloqueo implícito.

```c
void *slab = mmap(NULL, n, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_POPULATE, fd, 0);
if (mlock2(slab, n, MLOCK_ONFAULT) != 0) {
    // ENOMEM -> RLIMIT_MEMLOCK insuficiente: reportar getrlimit() y la solución por entorno
}
```

### 4.3 macOS (fila faltante)

- `mlock` funciona sin privilegios, limitado por los sysctl `vm.user_wire_limit` (por usuario) y `vm.global_user_wire_limit` (global). Se consultan con `sysctl vm.user_wire_limit`.
- **`mlockall` no está implementado en XNU** (devuelve error). Solo se puede bloquear rango por rango.
- Bloquear mucha memoria reduce lo que puede usar el compresor de memoria de macOS y degrada todo el sistema antes de llegar al límite.
- **En Apple Silicon (Metal):** la GPU y la CPU comparten memoria unificada, y Metal ya bloquea (wire) los recursos mientras la GPU los usa. En lugar de hacer `mlock` sobre slabs enormes, lo más adecuado es crear el slab como `MTLBuffer` compartido (o con `bytesNoCopy` sobre la región mmap, alineada a 16 KB) y controlar la residencia con `MTLResidencySet` (Metal, macOS 15+).

---

## 5. Diseño recomendado para PMTP

1. **Handles y no nombres:** `DuplicateHandle` (Windows), `memfd` + `SCM_RIGHTS` (Linux), `xpc_shmem` o Mach ports (macOS). Así se eliminan de raíz `/dev/shm`, el límite de 31 caracteres, `Global\` y las fugas.
2. **Cabecera del segmento:** `magic`, `abi_version`, `page_size` del creador, tamaño total, generación y PID/heartbeat de cada peer. Validar al mapear.
3. **Alineación:** contadores de productor y consumidor en líneas separadas de **128 bytes** (cubre Apple M e Intel con prefetch de pares de líneas). Offsets de datos alineados a `max(page_size) = 16 KB` para que el formato sea el mismo en los tres sistemas.
4. **Notificación:** backend de tres vías (sección 2.4) con spin acotado adelante. Nunca `_PRIVATE` ni `WaitOnAddress` entre procesos.
5. **Detección de peer muerto:** generación + heartbeat en el header; además `WAIT_ABANDONED` (Windows), `EOWNERDEAD` (Linux) y dead-name de Mach (macOS).
6. **Memoria bloqueada:** preferir huge/large pages; si no, `mlock2(ONFAULT)`, `VirtualLock` con working set ajustado, o residencia gestionada por Metal. Degradar con un aviso claro, nunca con SIGBUS ni un OOM silencioso.
7. **Empaquetado:** cibuildwheel + `auditwheel` / `delocate` / `delvewheel`, runtimes estáticos, ABI C en las fronteras y un único runtime de OpenMP.

## 6. Pruebas que deberían existir

| Prueba | Detecta |
|---|---|
| Productor y consumidor en **procesos distintos**, consumidor dormido, 10⁶ wakes | Error de `_PRIVATE` / `WaitOnAddress` (deadlock) |
| Contenedor Docker sin flags, slab de 1 GB | Límite de `/dev/shm` y SIGBUS por tmpfs lleno |
| Peer que hace `ftruncate(0)` sobre el segmento | SIGBUS (debe fallar por los sellos) |
| `kill -9` del productor a mitad de escritura | Detección de peer muerto y recuperación |
| Contenedor con `RLIMIT_MEMLOCK` por defecto | Mensaje de error de mlock accionable |
| Import de PMTP junto a numpy, torch y sklearn en el mismo proceso | Choques de OpenMP y de símbolos |
| macOS arm64: modificar dylib sin volver a firmar | Pipeline de firma (debe fallar en CI, no en el usuario) |
| Segmento creado en macOS y leído con layout x86_64 | Alineación de 16 KB en la cabecera |
