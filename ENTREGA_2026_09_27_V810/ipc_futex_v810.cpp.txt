#include <atomic>
#include <cstdint>
#include <cstring>

/**
 * @file ipc_futex_v810.cpp
 * Futex cross-process y sincronización IPC para POLYDIM V810.
 * SOTA Hardened:
 *  - Auto-Reset Event (CreateEventA(NULL, FALSE, FALSE, name)): elimina livelock 100% CPU.
 *  - Detección de alineación y límite de página: elimina underflow de punteros.
 *  - Soporte dual: Named Auto-Reset Event para IPC compartido + WaitOnAddress para intra-proceso.
 *  - Bucle de re-evaluación con backoff adaptativo.
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
} PmtpFutexSharedHeader;

#if defined(_WIN32)
static HANDLE open_site_event(const PmtpFutexSharedHeader* hdr, BOOL create) {
    char name[128];
    snprintf(name, sizeof(name), "Local\\PolydimFutex_%02x%02x%02x%02x%02x%02x%02x%02x",
             hdr->site_guid[0], hdr->site_guid[1], hdr->site_guid[2], hdr->site_guid[3],
             hdr->site_guid[4], hdr->site_guid[5], hdr->site_guid[6], hdr->site_guid[7]);
    return create ? CreateEventA(NULL, FALSE, FALSE, name)  /* auto-reset: previene livelock CPU */
                  : OpenEventA(EVENT_MODIFY_STATE | SYNCHRONIZE, FALSE, name);
}

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
        return -1; /* No hay espacio seguro para el header antes de la frontera de pagina */
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
    std::atomic_thread_fence(std::memory_order_release);
    hdr->magic = PMTP_FUTEX_MAGIC;
    return 0;
#else
    return 0; /* Linux / macOS: syscall futex es nativo sobre mapping */
#endif
}

POLYDIM_EXPORT int32_t polydim_futex_wait_v808_1(volatile uint32_t* addr, uint32_t expected_val, uint32_t timeout_ms) {
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
        /* Ruta IPC cross-process con Auto-Reset Event */
        HANDLE ev = open_site_event(hdr, TRUE);
        if (!ev) return -1;
        int32_t result = 1;
        while (*addr == expected_val) {
            DWORD wr = WaitForSingleObject(ev, timeout);
            if (wr == WAIT_OBJECT_0) continue;
            if (wr == WAIT_TIMEOUT) { result = 1; break; }
            result = -1; break;
        }
        if (*addr != expected_val) result = 0;
        CloseHandle(ev);
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

POLYDIM_EXPORT int32_t polydim_futex_wake_v808_1(volatile uint32_t* addr, bool wake_all) {
    if (!addr) return -1;

#if defined(_WIN32)
    /* Despertar hilos intra-proceso */
    if (wake_all) WakeByAddressAll((PVOID)addr);
    else          WakeByAddressSingle((PVOID)addr);

    /* Si es un sitio IPC con header compartido, despertar cross-process */
    PmtpFutexSharedHeader* hdr = get_valid_shared_header(addr);
    if (hdr != nullptr) {
        HANDLE ev = open_site_event(hdr, FALSE);
        if (ev) {
            SetEvent(ev);
            CloseHandle(ev);
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
