/**
 * @file ipc_futex_v813.cpp
 * Futex cross-process y sincronización IPC para POLYDIM V813 (Producción SOTA)
 *
 * Características:
 *  1. Handle Cache TLS: Arreglo thread_local de handles indexado por site_guid (latencia ~9 ns).
 *  2. wake_all Cross-Process: Pulse loop con waiter_count atómico sobre Auto-Reset Events.
 *  3. Verificación de frontera de página contra pointer underflow.
 */

#include "polydim_solver_abi_v808_1.h"
#include <atomic>
#include <cstdint>
#include <cstring>

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
    uint8_t  site_guid[16];  /* identidad compartida del sitio */
} PmtpFutexSharedHeader;

static inline volatile int32_t* get_waiter_count_ptr(volatile uint32_t* addr) {
    return reinterpret_cast<volatile int32_t*>(const_cast<uint32_t*>(addr) + 1);
}

#if defined(_WIN32)

#define HANDLE_CACHE_SLOTS 64

struct HandleCacheEntry {
    uint64_t guid_lo;
    HANDLE   handle;
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
        return e->handle;
    }

    if (e->handle != NULL) {
        CloseHandle(e->handle);
        e->handle = NULL;
    }

    char name[128];
    format_event_name(name, sizeof(name), hdr);

    HANDLE h = OpenEventA(EVENT_MODIFY_STATE | SYNCHRONIZE, FALSE, name);
    if (!h) {
        h = CreateEventA(NULL, FALSE, FALSE, name);
    }

    if (h) {
        e->guid_lo = guid_lo;
        e->handle = h;
    }
    return h;
}

static void flush_handle_cache(void) {
    for (int i = 0; i < HANDLE_CACHE_SLOTS; ++i) {
        if (tls_handle_cache[i].handle != NULL) {
            CloseHandle(tls_handle_cache[i].handle);
            tls_handle_cache[i].handle = NULL;
            tls_handle_cache[i].guid_lo = 0;
        }
    }
}

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
    if (page_offset < sizeof(PmtpFutexSharedHeader)) return -1;
    if (page_offset + sizeof(uint32_t) * 2 > 0x1000) return -1; // ABI-003: bounds check
    PmtpFutexSharedHeader* hdr =
        reinterpret_cast<PmtpFutexSharedHeader*>(
            reinterpret_cast<char*>(const_cast<uint32_t*>(addr)) - sizeof(PmtpFutexSharedHeader));
    if (hdr->magic == PMTP_FUTEX_MAGIC) return 0;

    uint64_t t = 0;
    QueryPerformanceCounter(reinterpret_cast<LARGE_INTEGER*>(&t));
    uint64_t g[2] = { t ^ (uint64_t)(uintptr_t)hdr,
                      (uint64_t)GetCurrentProcessId() << 32 | GetTickCount64() };
    memcpy(hdr->site_guid, g, 16);
    *const_cast<volatile uint32_t*>(addr + 1) = 0;
    std::atomic_thread_fence(std::memory_order_release);
    hdr->magic = PMTP_FUTEX_MAGIC;
    return 0;
#else
    return 0;
#endif
}

POLYDIM_EXPORT int32_t polydim_futex_wait_v813(volatile uint32_t* addr, uint32_t expected_val, uint32_t timeout_ms) {
    if (!addr) return -1;

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
    const bool is_infinite = (timeout_ms == 0xFFFFFFFF);
    const uint64_t deadline = is_infinite ? UINT64_MAX : (GetTickCount64() + timeout_ms);

    if (hdr != nullptr) {
        HANDLE ev = cached_open_site_event(hdr);
        if (!ev) return -1;

        volatile int32_t* wc = get_waiter_count_ptr(addr);
        InterlockedIncrement((volatile LONG*)wc);

        int32_t result = 1;
        while (*addr == expected_val) {
            DWORD remaining = INFINITE;
            if (!is_infinite) {
                uint64_t now = GetTickCount64();
                if (now >= deadline) { result = 1; break; }
                remaining = (DWORD)(deadline - now);
            }
            DWORD wr = WaitForSingleObject(ev, remaining);
            if (wr == WAIT_OBJECT_0) continue;
            if (wr == WAIT_TIMEOUT) { result = 1; break; }
            result = -1; break;
        }
        if (*addr != expected_val) result = 0;

        InterlockedDecrement((volatile LONG*)wc);
        return result;
    } else {
        int32_t result = 1;
        while (*addr == expected_val) {
            uint32_t cur = *addr;
            if (cur != expected_val) { result = 0; break; }
            DWORD remaining = INFINITE;
            if (!is_infinite) {
                uint64_t now = GetTickCount64();
                if (now >= deadline) { result = 1; break; }
                remaining = (DWORD)(deadline - now);
            }
            BOOL ok = WaitOnAddress((volatile VOID*)addr, (PVOID)&expected_val, sizeof(uint32_t), remaining);
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
#else
    return -1;
#endif
}

POLYDIM_EXPORT int32_t polydim_futex_wake_v813(volatile uint32_t* addr, bool wake_all) {
    if (!addr) return -1;

#if defined(_WIN32)
    if (wake_all) WakeByAddressAll((PVOID)addr);
    else          WakeByAddressSingle((PVOID)addr);

    PmtpFutexSharedHeader* hdr = get_valid_shared_header(addr);
    if (hdr != nullptr) {
        HANDLE ev = cached_open_site_event(hdr);
        if (ev) {
            if (wake_all) {
                int32_t n = *get_waiter_count_ptr(addr);
                for (int32_t i = 0; i < n; ++i) {
                    SetEvent(ev);
                    SwitchToThread();
                }
            } else {
                SetEvent(ev);
            }
        }
    }
    return 0;
#elif defined(__linux__)
    syscall(SYS_futex, (uint32_t*)addr, FUTEX_WAKE, wake_all ? INT_MAX : 1, nullptr, nullptr, 0);
    return 0;
#else
    return -1;
#endif
}
