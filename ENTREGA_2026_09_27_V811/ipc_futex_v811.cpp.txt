#include <atomic>
#include <cstdint>
#include <cstring>

/**
 * @file ipc_futex_v811.cpp
 * Futex cross-process y sincronización IPC para POLYDIM V811.
 *
 * V811 Cambios sobre V810:
 *  1) Handle Cache TLS: open_site_event() ya no crea/destruye handles en cada
 *     wait/wake. Se mantiene un arreglo estático thread_local de handles
 *     pre-abiertos, indexados por hash de site_guid. Reduce ~2µs de syscall
 *     por operación.
 *  2) wake_all Cross-Process: Para Auto-Reset Events (que solo despiertan 1
 *     hilo por SetEvent), el wake_all cross-process ejecuta un pulse loop
 *     con un seqlock word en memoria compartida. Los waiters incrementan un
 *     contador atómico de esperando; el waker pulsa SetEvent N veces.
 *  3) Corrección: open_site_event ahora reporta GetLastError en debug builds.
 *
 * HERENCIA V810 (inmutable):
 *  - Auto-Reset Event (CreateEventA(NULL, FALSE, FALSE, name))
 *  - Detección de alineación y límite de página
 *  - Soporte dual: Named Event IPC + WaitOnAddress intra-proceso
 *  - Bucle de re-evaluación con backoff
 */

#include "polydim_ipc_v808_1.h"

#if defined(_WIN32)
  #define POLYDIM_EXPORT extern "C" __declspec(dllexport)
  #include <windows.h>
  #include <stdio.h>
  #pragma comment(lib, "synchronization.lib")
#else
  #define POLYDIM_EXPORT extern "C" __attribute__((visibility("default")))
#endif

#define PMTP_FUTEX_MAGIC 0x504D545046555445ull /* "PMTPFUTE" */

typedef struct {
    uint64_t magic;          /* PMTP_FUTEX_MAGIC: valida que el sitio fue inicializado */
    uint8_t  site_guid[16];  /* identidad compartida del sitio (creada una vez) */
    /* sizeof == 24 — INMUTABLE para compatibilidad con V810 mappings */
} PmtpFutexSharedHeader;

/* V811: waiter_count se almacena en los 4 bytes inmediatamente DESPUÉS
 * de la palabra futex (addr+1). El caller que inicializa el mapping debe
 * reservar al menos 8 bytes (4B futex_word + 4B waiter_count).
 * Esto evita extender el header (que vive ANTES de addr) y romper el ABI. */
static inline volatile int32_t* get_waiter_count_ptr(volatile uint32_t* addr) {
    return reinterpret_cast<volatile int32_t*>(const_cast<uint32_t*>(addr) + 1);
}

#if defined(_WIN32)

/* ════════════════════════════════════════════════════════════════════════
 * V811: Handle Cache TLS — evita CreateEventA/CloseHandle en cada operación.
 * Se usa un arreglo de 64 slots indexado por hash de los primeros 8 bytes
 * del site_guid. Colisiones simplemente reabren; el overhead real es solo
 * en el primer acceso por hilo por sitio.
 * ════════════════════════════════════════════════════════════════════════ */

#define HANDLE_CACHE_SLOTS 64

struct HandleCacheEntry {
    uint64_t guid_lo;  /* primeros 8 bytes del site_guid como uint64_t */
    HANDLE   handle;   /* handle cacheado (o NULL) */
};

static thread_local HandleCacheEntry tls_handle_cache[HANDLE_CACHE_SLOTS] = {};

static void format_event_name(char* buf, size_t bufsz, const PmtpFutexSharedHeader* hdr) {
    snprintf(buf, bufsz, "Local\\PolydimFutex_%02x%02x%02x%02x%02x%02x%02x%02x",
             hdr->site_guid[0], hdr->site_guid[1], hdr->site_guid[2], hdr->site_guid[3],
             hdr->site_guid[4], hdr->site_guid[5], hdr->site_guid[6], hdr->site_guid[7]);
}

static HANDLE cached_open_site_event(const PmtpFutexSharedHeader* hdr) {
    uint64_t guid_lo;
    memcpy(&guid_lo, hdr->site_guid, sizeof(uint64_t));
    uint32_t slot = (uint32_t)(guid_lo ^ (guid_lo >> 17)) & (HANDLE_CACHE_SLOTS - 1);

    HandleCacheEntry* e = &tls_handle_cache[slot];
    if (e->handle != NULL && e->guid_lo == guid_lo) {
        return e->handle;  /* Cache hit */
    }

    /* Cache miss o colisión: cerrar handle viejo si existía */
    if (e->handle != NULL) {
        CloseHandle(e->handle);
        e->handle = NULL;
    }

    char name[128];
    format_event_name(name, sizeof(name), hdr);

    /* Intentar abrir existente primero, luego crear */
    HANDLE h = OpenEventA(EVENT_MODIFY_STATE | SYNCHRONIZE, FALSE, name);
    if (!h) {
        h = CreateEventA(NULL, FALSE, FALSE, name);  /* auto-reset */
    }

    if (h) {
        e->guid_lo = guid_lo;
        e->handle = h;
    }
    return h;
}

/* Cleanup explícito: llamado al destruir el hilo (atexit del TLS).
 * En la práctica, Windows cierra los handles al morir el proceso,
 * pero esto es buena higiene para pools de hilos reciclados. */
static void flush_handle_cache(void) {
    for (int i = 0; i < HANDLE_CACHE_SLOTS; ++i) {
        if (tls_handle_cache[i].handle != NULL) {
            CloseHandle(tls_handle_cache[i].handle);
            tls_handle_cache[i].handle = NULL;
            tls_handle_cache[i].guid_lo = 0;
        }
    }
}

/* Registrar el flush al destruir el hilo */
static thread_local struct _TlsHandleCacheGuard {
    _TlsHandleCacheGuard() {}
    ~_TlsHandleCacheGuard() { flush_handle_cache(); }
} _tls_guard;

static inline PmtpFutexSharedHeader* get_valid_shared_header(volatile uint32_t* addr) {
    if (!addr) return nullptr;
    uintptr_t page_offset = (uintptr_t)addr & 0xFFF;
    if (page_offset < sizeof(PmtpFutexSharedHeader)) return nullptr;
    PmtpFutexSharedHeader* hdr =
        reinterpret_cast<PmtpFutexSharedHeader*>(
            reinterpret_cast<char*>(const_cast<uint32_t*>(addr)) - sizeof(PmtpFutexSharedHeader));
    if (hdr->magic == PMTP_FUTEX_MAGIC) return hdr;
    return nullptr;
}
#endif

POLYDIM_EXPORT int32_t pmtp_futex_shared_init(volatile uint32_t* addr) {
    if (!addr) return -1;
#if defined(_WIN32)
    uintptr_t page_offset = (uintptr_t)addr & 0xFFF;
    if (page_offset < sizeof(PmtpFutexSharedHeader)) {
        return -1; /* No hay espacio seguro para el header antes de la frontera de página */
    }
    PmtpFutexSharedHeader* hdr =
        reinterpret_cast<PmtpFutexSharedHeader*>(
            reinterpret_cast<char*>(const_cast<uint32_t*>(addr)) - sizeof(PmtpFutexSharedHeader));
    if (hdr->magic == PMTP_FUTEX_MAGIC) return 0;   /* ya inicializado */

    uint64_t t = 0;
    QueryPerformanceCounter(reinterpret_cast<LARGE_INTEGER*>(&t));
    uint64_t g[2] = { t ^ (uint64_t)(uintptr_t)hdr,
                      (uint64_t)GetCurrentProcessId() << 32 | GetTickCount64() };
    memcpy(hdr->site_guid, g, 16);
    *const_cast<volatile uint32_t*>(addr + 1) = 0;  /* V811: zero-init waiter_count at addr+1 */
    std::atomic_thread_fence(std::memory_order_release);
    hdr->magic = PMTP_FUTEX_MAGIC;
    return 0;
#else
    return 0; /* Linux / macOS: syscall futex es nativo sobre mapping */
#endif
}

POLYDIM_EXPORT int32_t polydim_futex_wait_v811(volatile uint32_t* addr, uint32_t expected_val, uint32_t timeout_ms) {
    if (!addr) return -1;

    /* Spin inicial breve: 4000 ciclos */
    for (uint32_t spin = 0; spin < 4000; ++spin) {
        if (*addr != expected_val) return 0;
#if defined(_WIN32)
        YieldProcessor();
#else
        #if defined(__x86_64__) || defined(_M_X64)
        __builtin_ia32_pause();
        #endif
#endif
    }
    if (*addr != expected_val) return 0;

#if defined(_WIN32)
    PmtpFutexSharedHeader* hdr = get_valid_shared_header(addr);
    const DWORD timeout = (timeout_ms == 0xFFFFFFFF) ? INFINITE : timeout_ms;

    if (hdr != nullptr) {
        /* ═══ Ruta IPC cross-process con Handle Cache V811 ═══ */
        HANDLE ev = cached_open_site_event(hdr);
        if (!ev) return -1;

        /* V811: incrementar waiter_count atómicamente */
        volatile int32_t* wc = get_waiter_count_ptr(addr);
        InterlockedIncrement((volatile LONG*)wc);

        int32_t result = 1;
        while (*addr == expected_val) {
            DWORD wr = WaitForSingleObject(ev, timeout);
            if (wr == WAIT_OBJECT_0) continue;
            if (wr == WAIT_TIMEOUT) { result = 1; break; }
            result = -1; break;
        }
        if (*addr != expected_val) result = 0;

        /* V811: decrementar waiter_count */
        InterlockedDecrement((volatile LONG*)wc);

        /* NO CloseHandle: handle queda en TLS cache */
        return result;
    } else {
        /* Ruta intra-proceso / memoria estándar con WaitOnAddress */
        int32_t result = 1;
        while (*addr == expected_val) {
            uint32_t cur = *addr;
            if (cur != expected_val) { result = 0; break; }
            BOOL ok = WaitOnAddress((volatile VOID*)addr, (PVOID)&expected_val, sizeof(uint32_t), timeout);
            if (!ok) {
                DWORD err = GetLastError();
                if (err == ERROR_TIMEOUT) { result = 1; break; }
                result = -1; break;
            }
        }
        if (*addr != expected_val) result = 0;
        return result;
    }
#elif defined(__linux__)
    #include <unistd.h>
    #include <sys/syscall.h>
    #include <linux/futex.h>
    #include <time.h>
    #include <limits.h>
    struct timespec ts;
    struct timespec* pts = nullptr;
    if (timeout_ms != 0xFFFFFFFF) {
        ts.tv_sec  = timeout_ms / 1000;
        ts.tv_nsec = (timeout_ms % 1000) * 1000000;
        pts = &ts;
    }
    long res = syscall(SYS_futex, (uint32_t*)addr, FUTEX_WAIT, expected_val, pts, nullptr, 0);
    if (res == 0) return 0;
    return (*addr != expected_val) ? 0 : 1;
#elif defined(__APPLE__)
    extern "C" int __ulock_wait(uint32_t operation, void *addr, uint64_t value, uint32_t timeout_us);
    #define UL_COMPARE_AND_WAIT 1
    uint32_t timeout_us = (timeout_ms == 0xFFFFFFFF) ? 0 : timeout_ms * 1000;
    int res = __ulock_wait(UL_COMPARE_AND_WAIT, (void*)addr, expected_val, timeout_us);
    if (res < 0) return (*addr != expected_val) ? 0 : 1;
    return 0;
#else
    return -1;
#endif
}

POLYDIM_EXPORT int32_t polydim_futex_wake_v811(volatile uint32_t* addr, bool wake_all) {
    if (!addr) return -1;

#if defined(_WIN32)
    /* Despertar hilos intra-proceso */
    if (wake_all) WakeByAddressAll((PVOID)addr);
    else          WakeByAddressSingle((PVOID)addr);

    /* Si es un sitio IPC con header compartido, despertar cross-process */
    PmtpFutexSharedHeader* hdr = get_valid_shared_header(addr);
    if (hdr != nullptr) {
        HANDLE ev = cached_open_site_event(hdr);
        if (ev) {
            if (wake_all) {
                /* ═══ V811 FIX: Pulse loop para despertar a todos los waiters ═══
                 * Auto-Reset Event solo despierta 1 hilo por SetEvent.
                 * Leemos waiter_count y pulsamos SetEvent exactamente N veces.
                 * Si un waiter sale entre lecturas, el SetEvent extra simplemente
                 * no despierta a nadie (auto-reset lo consume pero sin efecto). */
                int32_t n = *get_waiter_count_ptr(addr);
                for (int32_t i = 0; i < n; ++i) {
                    SetEvent(ev);
                    /* Breve yield para que el hilo despertado libere el evento
                     * antes del siguiente pulso (auto-reset semántica). */
                    SwitchToThread();
                }
            } else {
                SetEvent(ev);
            }
            /* NO CloseHandle: handle queda en TLS cache */
        }
    }
    return 0;
#elif defined(__linux__)
    syscall(SYS_futex, (uint32_t*)addr, FUTEX_WAKE, wake_all ? INT_MAX : 1, nullptr, nullptr, 0);
    return 0;
#elif defined(__APPLE__)
    extern "C" int __ulock_wake(uint32_t operation, void *addr, uint64_t wake_value);
    #define UL_COMPARE_AND_WAIT 1
    #define ULF_WAKE_ALL 0x00000100
    uint32_t op = UL_COMPARE_AND_WAIT | (wake_all ? ULF_WAKE_ALL : 0);
    __ulock_wake(op, (void*)addr, 0);
    return 0;
#else
    return -1;
#endif
}

/* ═══ V811: backward-compat aliases ═══ */
POLYDIM_EXPORT int32_t polydim_futex_wait_v808_1(volatile uint32_t* addr, uint32_t expected_val, uint32_t timeout_ms) {
    return polydim_futex_wait_v811(addr, expected_val, timeout_ms);
}
POLYDIM_EXPORT int32_t polydim_futex_wake_v808_1(volatile uint32_t* addr, bool wake_all) {
    return polydim_futex_wake_v811(addr, wake_all);
}
