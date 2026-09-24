# ==============================================================================
# REPORTE DE INGESTA Y EVALUACIÓN SOTA: GAPS DE PLATAFORMA WINDOWS ↔ LINUX
# (GAP-01 A GAP-04: BLAS LOADER, SHM DOCKER, HUGEPAGES, FUTEX)
# Fase 0: Ingesta Bruta Consolidada | Fase 1: Evaluación Red Team (Bulldog Critic)
# Fecha: 2026-09-24 | Versión Objetivo: POLYDIM V774
# ==============================================================================

## FASE 0: TEXTO ÍNTEGRO EN BRUTO INGRESADO POR ARIEL

```text
Soluciones SOTA para cada GAP
Aquí tienes las mejores prácticas actuales (2024–2026) para resolver cada uno de los gaps de portabilidad Windows ↔ Linux en entornos cloud como Kaggle/Colab.

GAP-01: Abstracción LoadLibraryExW ↔ dlopen
Patrón SOTA: usar macros de plataforma con una capa de abstracción minimalista.

cpp
// include/polydim_blas_loader.h
#ifdef _WIN32
  #include <windows.h>
  using LibHandle = HMODULE;
  #define LOAD_LIB(path) LoadLibraryExW(path, nullptr, LOAD_WITH_ALTERED_SEARCH_PATH)
  #define GET_SYM(lib, name) GetProcAddress(lib, name)
  #define UNLOAD_LIB(lib) FreeLibrary(lib)
#else
  #include <dlfcn.h>
  using LibHandle = void*;
  #define LOAD_LIB(path) dlopen(path, RTLD_NOW | RTLD_LOCAL)
  #define GET_SYM(lib, name) dlsym(lib, name)
  #define UNLOAD_LIB(lib) dlclose(lib)
#endif
Notas:
En Linux, enlazar con -ldl.
Para mayor portabilidad (macOS, BSD), añade #elif defined(__APPLE__) con la misma rama POSIX.

GAP-02: /dev/shm limitado a 64 MB en Docker (Kaggle)
Diagnóstico confirmado: Docker asigna 64 MB por defecto a /dev/shm; Kaggle no permite --shm-size ni --ipc=host.

Soluciones SOTA (orden de preferencia):
1. Fallback automático a mmap(MAP_ANONYMOUS | MAP_SHARED)
No usa /dev/shm; los slabs son memoria anónima compartida entre hilos (heredada en fork si fuera necesario).

cpp
#ifdef __linux__
  #include <sys/mman.h>
  void* allocate_slab(size_t size) {
      void* ptr = mmap(nullptr, size,
                       PROT_READ | PROT_WRITE,
                       MAP_ANONYMOUS | MAP_SHARED,
                       -1, 0);
      if (ptr == MAP_FAILED) throw std::bad_alloc();
      return ptr;
  }
#endif

2. Detección de tamaño de /dev/shm y fallback a /tmp
Si insistes en usar tmpfs, detecta el tamaño y, si < requerido, usa /tmp (respaldado por swap).

cpp
#include <sys/vfs.h>
bool shm_has_space(size_t needed) {
    struct statfs s;
    if (statfs("/dev/shm", &s) != 0) return false;
    size_t avail = s.f_bsize * s.f_bavail;
    return avail >= needed;
}
// Si false → mmap en /tmp o MAP_ANONYMOUS

3. Workaround en Kaggle (si tienes control del contenedor)
En entornos donde puedas pasar --shm-size o --ipc=host, úsalo. En Kaggle puro, no es posible; la única vía es evitar /dev/shm.

GAP-03: HugePages (Linux) vs Large Pages (Windows)
SOTA: unificar la abstracción con detección de privilegios y fallback transparente.

cpp
void* allocate_huge(size_t size) {
#ifdef _WIN32
    void* p = VirtualAlloc(nullptr, size,
                           MEM_COMMIT | MEM_RESERVE | MEM_LARGE_PAGES,
                           PAGE_READWRITE);
    if (!p) {
        p = VirtualAlloc(nullptr, size,
                         MEM_COMMIT | MEM_RESERVE,
                         PAGE_READWRITE);
    }
    return p;
#elif defined(__linux__)
    void* p = mmap(nullptr, size,
                   PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB,
                   -1, 0);
    if (p == MAP_FAILED) {
        p = mmap(nullptr, size,
                 PROT_READ | PROT_WRITE,
                 MAP_PRIVATE | MAP_ANONYMOUS,
                 -1, 0);
    }
    return p;
#endif
}
Notas:
En Linux, si el kernel es ≥ 2.6.32, MAP_HUGETLB funciona sin montar hugetlbfs.
Para tamaños específicos (2 MB vs 1 GB), usa MAP_HUGE_2MB / MAP_HUGE_1GB (Linux ≥ 3.8).

GAP-04: WaitOnAddress (Windows) ↔ futex (Linux)
SOTA: usar std::atomic + wait/notify (C++20) cuando sea posible; si no, abstracción nativa.

Opción A: C++20 std::atomic_ref::wait / notify_one
cpp
#include <atomic>
std::atomic<bool> flag{false};
// Thread 1
flag.store(true, std::memory_order_release);
flag.notify_one();
// Thread 2
flag.wait(false, std::memory_order_acquire);

Opción B: Abstracción nativa (si C++20 no está disponible)
cpp
#ifdef _WIN32
  #include <synchapi.h>
  void wait_on_address(std::atomic<bool>* addr, bool expected) {
      WaitOnAddress(addr, &expected, sizeof(bool), INFINITE);
  }
  void wake_address(std::atomic<bool>* addr) {
      WakeByAddressSingle(addr);
  }
#elif defined(__linux__)
  #include <sys/syscall.h>
  #include <unistd.h>
  #include <linux/futex.h>
  #include <atomic>

  void wait_on_address(std::atomic<bool>* addr, bool expected) {
      bool val = addr->load(std::memory_order_acquire);
      if (val == expected) {
          syscall(SYS_futex, addr.get(), FUTEX_WAIT, expected, nullptr, nullptr, 0);
      }
  }
  void wake_address(std::atomic<bool>* addr) {
      syscall(SYS_futex, addr.get(), FUTEX_WAKE, 1, nullptr, nullptr, 0);
  }
#endif

// Implementación robusta de LibLoader
cpp
namespace polydim {
class LibLoader { ... };
}

// Detección programática de shm
cpp
ShmInfo probe_shm() { ... }
enum class SlabBackend { SHM, ANONYMOUS, TMPFILE };
SlabBackend select_slab_backend(size_t required_size) { ... }
void* allocate_slab(SlabBackend backend, size_t size) { ... }

// HugePages alineado
cpp
void* allocate_huge_aligned(size_t size, size_t huge_size = 2 * 1024 * 1024) { ... }
bool has_large_page_privilege() { ... }

// Futex detallado
cpp
inline long futex_wait(std::atomic<int>* addr, int expected, const struct timespec* timeout = nullptr) { ... }
inline long futex_wake(std::atomic<int>* addr, int nwaiters = 1) { ... }
template<typename T> void atomic_wait(...) { ... }
```

---

## FASE 1: EVALUACIÓN CRÍTICA RED TEAM (BULLDOG CRITIC)

### 1. EVALUACIÓN DE GAP-01: `LoadLibraryExW` ↔ `dlopen`

#### Elementos Válidos SOTA
1. **Identificación de la Causa Raíz:** En `include/polydim_blas_loader.h`, la inclusión directa de `<windows.h>` y `LoadLibraryExW` causa un fallo terminal inmediato en cualquier toolchain Linux (Kaggle/Colab).
2. **Flags de enlace y modo:** `RTLD_NOW | RTLD_LOCAL` en Linux es la combinación estricta correcta para evitar resolución diferida de símbolos durante bucles críticos y evitar colisiones de símbolos globales en procesos con múltiples módulos compartidos.
3. **Conversión UTF-8 ↔ UTF-16:** El manejo de encoding para Windows (`MultiByteToWideChar`) es mandatorio para rutas con caracteres no ASCII.

#### Defectos Críticos y Trampas Identificadas en el Código Propuesto
1. **Violación de Frontera FFI por Lanzamiento de Excepciones (`std::system_error` / `std::runtime_error`):**
   * *Falla:* `LibLoader` lanza excepciones C++ en el constructor y en `get_symbol`. 
   * *Impacto en Silicio:* `polydim_blas_loader.h` se invoca desde funciones con linkage `extern "C"` consumidas por ctypes en Python o FFI en Rust. Si `dlopen` falla (e.g. OpenBLAS no está instalado en el sistema), la excepción cruza la frontera de lenguaje sin ser capturada, invocando `std::terminate()` y matando el proceso del orquestador.
   * *Corrección Obligatoria:* La capa de carga debe retornar códigos de error de la taxonomía oficial (`PolydimStatus::POLYDIM_ERR_BLAS_NOT_FOUND` / `-15`) y almacenar el puntero al mensaje de error en un buffer thread-local o de logging, con firmas estrictamente `noexcept`.
2. **Bug de Longitud en `MultiByteToWideChar`:**
   * *Falla en el snippet:*
     ```cpp
     int len = MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, nullptr, 0);
     std::wstring wpath(len, L'\0');
     MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, &wpath[0], len);
     ```
   * *Impacto:* Al pasar `-1` en el tercer parámetro, `len` incluye el terminador nulo `\0`. Crear `std::wstring wpath(len, L'\0')` hace que `wpath.size() == len`, dejando un carácter nulo *dentro* de la cadena útil además del terminador propio de la clase. En ciertas versiones de Windows API o llamadas que utilicen `wpath.size()`, esto genera rutas corrompidas.
   * *Corrección Obligatoria:* `wpath.resize(len > 0 ? len - 1 : 0);` o pasar `path.length()` explícitamente.
3. **Mangled Names en BLAS (Fortran ABI vs C BLAS):**
   * *Falla:* Cargar `libopenblas.so` buscando únicamente `"sgemm_"` puede fallar si la biblioteca fue compilada sin soporte Fortran o con prefijo `cblas_`.
   * *Corrección:* El loader debe intentar secuencialmente: `cblas_dgemm` → `dgemm_` → `dgemm`.

---

### 2. EVALUACIÓN DE GAP-02: `/dev/shm` Limitado a 64 MB en Docker (Kaggle)

#### Elementos Válidos SOTA
1. **Diagnóstico Confirmado:** Los contenedores de Kaggle y Colab bloquean `/dev/shm` a 64 MB fijos. Para tensores $D=10^7$ en FP64 ($80\text{ MB}$ por tensor, $160\text{ MB}$ en double buffer), `/dev/shm` falla inmediatamente con `ENOSPC` o `SIGBUS`.
2. **Sondeo con `statvfs`:** El sondeo con `statvfs("/dev/shm", &s)` es eficiente ($<1\,\mu\text{s}$) y no invasivo.

#### Falacia Arquitectónica y Corrección Fundamental
1. **La Falacia de `MAP_ANONYMOUS | MAP_SHARED` para IPC Multi-Proceso:**
   * *Afirmación del texto ingresado:* *"No usa /dev/shm; los slabs son memoria anónima compartida entre hilos (heredada en fork si fuera necesario)."*
   * *Ataque Bulldog:* PMTP (**Polydim Memory Transfer Protocol**) es un bus de memoria compartida para **procesos independientes desvinculados** (e.g., un nodo Python de inferencia, un kernel C++ en background, un guardián Rust y un proceso de UI en Dart).
   * **`MAP_ANONYMOUS` NO tiene descriptor de archivo ni ruta en el sistema de archivos.** Dos procesos no emparentados (que no hayan nacido del mismo `fork()`) **no pueden enlazar a la misma memoria anónima**.
   * Si forzáramos `MAP_ANONYMOUS`, POLYDIM dejaría de ser un bus IPC universal y quedaría restringido a `multiprocessing.fork()`, el cual además está obsoleto/desalentado en Python 3.12+ y PyTorch por causar deadlocks con hilos de OpenMP/CUDA.
2. **Solución SOTA Real para Procesos Desvinculados en Kaggle Docker:**
   * La solución correcta y robusta cuando `/dev/shm` es insuficiente es **mapear un archivo en `/tmp`** (`/tmp/polydim_shm_<slab_id>`).
   * *¿Por qué `/tmp` es SOTA en Kaggle?:* En los entornos Docker de Kaggle y Colab, `/tmp` reside en un volumen espacioso (cientos de gigabytes). 
   * Al hacer `open(path, O_CREAT | O_RDWR)` + `ftruncate(fd, size)` + `mmap(..., MAP_SHARED, fd, 0)`, el kernel de Linux mantiene las páginas sucias en la memoria DRAM (Page Cache). La velocidad de lectura/escritura es **prácticamente idéntica a DRAM/tmpfs** siempre que no se fuerce `msync(MS_SYNC)`.
   * Cualquier proceso independiente en el contenedor puede abrir `/tmp/polydim_shm_<slab_id>` y vincularse con `MAP_SHARED`.
3. **Bug del `shm_unlink` / `close` Prematuro:**
   * En el snippet:
     ```cpp
     close(fd);
     shm_unlink(path.c_str());  // unlink inmediato
     ```
   * Si el proceso escritor hace `unlink` antes de que el proceso lector intente abrir el archivo, el lector recibirá `ENOENT` (archivo no encontrado). El archivo debe persistir hasta que finalice la sesión o sea eliminado por el Reaper al detectar que todos los PIDs han muerto.

---

### 3. EVALUACIÓN DE GAP-03: HugePages (Linux) vs. Large Pages (Windows)

#### Elementos Válidos SOTA
1. **Uso de Macros de Kernel:** `MAP_HUGE_2MB` (`21 << MAP_HUGE_SHIFT`) y `MAP_HUGE_1GB` (`30 << MAP_HUGE_SHIFT`) son el estándar POSIX moderno de Linux (kernel $\ge 3.8$).
2. **Estrategia de Fallback:** Degradar transparentemente a páginas de 4 KB estándar si el kernel no tiene HugePages configuradas.

#### Defectos Críticos y Trampas Identificadas
1. **Bandera `MAP_PRIVATE` Incompatible con PMTP:**
   * El código del snippet usa:
     ```cpp
     int flags = MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB;
     ```
   * En PMTP, el bus es de memoria compartida entre procesos (`MAP_SHARED`). Si se crea un slab con `MAP_PRIVATE`, cualquier escritura genera una copia privada (Copy-On-Write) y los otros procesos jamás verán las actualizaciones tensoriales. Debe usar `MAP_SHARED`.
2. **Alineación Obligatoria en Windows para `MEM_LARGE_PAGES`:**
   * En Windows, `VirtualAlloc(..., MEM_LARGE_PAGES, ...)` **rechaza** cualquier tamaño que no sea un múltiplo exacto de `GetLargePageMinimum()` devolviendo error 87 (`ERROR_INVALID_PARAMETER`).
   * El snippet pasa `size` sin redondear, lo que causará que falle el 100% de las veces para tensores cuyo tamaño en bytes no sea múltiplo exacto de 2 MB.
   * *Corrección:* Redondear: `size = (size + page_min - 1) & ~(page_min - 1)`.
3. **Realidad en Kaggle / Cloud:**
   * En Kaggle Docker, `/proc/sys/vm/nr_hugepages` suele ser 0 y los contenedores no tienen `CAP_IPC_LOCK` para reservar HugePages. Por lo tanto, el camino de fallback a páginas normales debe ser el camino predeterminado sin registrar advertencias molestas.

---

### 4. EVALUACIÓN DE GAP-04: `WaitOnAddress` (Windows) ↔ `futex` (Linux)

#### Elementos Válidos SOTA
1. **C++20 `std::atomic::wait` / `std::atomic::notify_one`:** Es la solución dorada canónica SOTA. WinLibs GCC 14.2.0 y MSVC 19.51 soportan C++20 plenamente con `-std=c++20`. En Linux, `std::atomic::wait` compila internamente a `futex`, y en Windows compila a `WaitOnAddress`.
2. **Uso directo de syscall `SYS_futex` para FFI/C ABI:** Es necesario cuando se opera sobre buffers de memoria cruda compartida donde no se puede instanciar la clase `std::atomic`.

#### Errores de Sintaxis y Bugs en el Código Propuesto
1. **Error de Compilación `addr.get()`:**
   * El snippet propone:
     ```cpp
     inline long futex_wait(std::atomic<int>* addr, int expected, ...) {
         return syscall(SYS_futex, addr.get(), FUTEX_WAIT, expected, ...);
     }
     ```
   * `std::atomic<int>` **NO tiene método `.get()`** en C++. Esto produce un fallo terminal de compilación: `error: 'class std::atomic<int>' has no member named 'get'`.
   * El puntero a la palabra de 32 bits es simplemente `reinterpret_cast<int*>(addr)` o la dirección del valor subyacente.
2. **Peligro en Tipos Menores a 32 bits (`bool`, `uint8_t`):**
   * El snippet intenta aplicar `futex` a `bool` mediante casting:
     ```cpp
     static_assert(sizeof(T) <= sizeof(int), "T must be <= 4 bytes for futex");
     auto addr = reinterpret_cast<std::atomic<int>*>(obj);
     futex_wait(addr, static_cast<int>(old));
     ```
   * **¡Gravísimo bug de memoria en Linux!** El kernel de Linux en `SYS_futex` desreferencia estrictamente una palabra completa de 32 bits (`uint32_t`). Si `T` es `bool` (1 byte), el kernel lee 3 bytes adyacentes en la memoria. Si esos 3 bytes cambian (por variables vecinas o alineación), la comparación atómica en el kernel falla falsamente devolviendo `EWOULDBLOCK`, o peor aún, si el `bool` está al final de una página de memoria, desreferenciar 4 bytes produce un **Segmentation Fault (SIGSEGV)** al cruzar el límite de la página.
   * *Regla Inviolable:* Toda variable de sincronización Futex/WaitOnAddress **DEBE ser exactamente de 32 bits (`uint32_t` o `int32_t`)**.

---

## CONCLUSIÓN DE EVALUACIÓN Y DECISIÓN DE INGENIERÍA

1. **Veto de Código Activo (Regla 19):** No se ha modificado ningún archivo de código fuente del proyecto (`src/` o `include/`).
2. **Veredicto Técnico:** La ingesta aporta la arquitectura conceptual exacta para cerrar los 4 gaps (GAP-01 a GAP-04), pero los snippets en crudo contenían 4 bugs críticos (lanzamiento de excepciones C++ a través de FFI, imposibilidad de IPC multi-proceso con `MAP_ANONYMOUS`, violación de alineación en Windows Large Pages, y el error de compilación/corte de 1 byte en `SYS_futex`).
3. **Diseño Consolidado Listo:** Los parches han sido refinados con correcciones rigurosas y quedan listos para su integración tan pronto como se dé la orden de desbloqueo de código.
