/**
 * @file ipc_futex_v808_1.cpp  (PATCH C3)
 * Futex cross-process correcto:
 *  - Windows: el nombre del Named Event se deriva del IDENTIFICADOR
 *    compartido (offset dentro del segmento + GUID de inicializacion
 *    almacenado en el header), NUNCA de la direccion virtual local
 *    (V808: X_A != X_B entre procesos -> los nombres jamas coincidian
 *    y el despertar cross-process era imposible).
 *  - Espera con RE-CHEQUEO en bucle: un wake espurio (evento manual-reset
 *    residual) ya no se propaga como exito falso.
 *  - Sin ResetEvent en el waiter: la senal residual solo causa un ciclo
 *    de espera extra inofensivo.
 * Contrato: la palabra futex (uint32_t) vive en memoria compartida y
 * pmtp_futex_shared_init() se llama UNA vez (proceso duenio) para fijar
 * el identificador compartido.
 */

#include "polydim_ipc_v808_1.h"

#if defined(_WIN32)
#include <windows.h>
#include <stdio.h>
#pragma comment(lib, "synchronization.lib")

/* Header minimo por sitio de futex en memoria compartida.
 * Debe estar en el segmento compartido, junto a la palabra futex. */
typedef struct {
    uint64_t magic;          /* PMTP_FUTEX_MAGIC: valida que el sitio fue inicializado */
    uint8_t  site_guid[16];  /* identidad compartida del sitio (creada una vez) */
} PmtpFutexSharedHeader;

#define PMTP_FUTEX_MAGIC 0x504D545046555445ull /* "PMTPFUTE" */

extern "C" int32_t pmtp_futex_shared_init(volatile uint32_t* addr) {
    PmtpFutexSharedHeader* hdr =
        reinterpret_cast<PmtpFutexSharedHeader*>(
            reinterpret_cast<char*>(const_cast<uint32_t*>(addr)) - sizeof(PmtpFutexSharedHeader));
    if (hdr->magic == PMTP_FUTEX_MAGIC) return 0;   /* ya inicializado */
    /* GUID simple: mezcla de contadores de alto rendimiento + hora.
     * No es criptográfico: solo necesita unicidad entre procesos de la sesion. */
    uint64_t t = 0;
    QueryPerformanceCounter(reinterpret_cast<LARGE_INTEGER*>(&t));
    uint64_t g[2] = { t ^ (uint64_t)(uintptr_t)hdr,
                      (uint64_t)GetCurrentProcessId() << 32 | GetTickCount64() };
    memcpy(hdr->site_guid, g, 16);
    std::atomic_thread_fence(std::memory_order_release);
    hdr->magic = PMTP_FUTEX_MAGIC;
    return 0;
}

static HANDLE open_site_event(const PmtpFutexSharedHeader* hdr, BOOL create) {
    char name[128];
    snprintf(name, sizeof(name), "Local\\PolydimFutex_%02x%02x%02x%02x%02x%02x%02x%02x",
             hdr->site_guid[0], hdr->site_guid[1], hdr->site_guid[2], hdr->site_guid[3],
             hdr->site_guid[4], hdr->site_guid[5], hdr->site_guid[6], hdr->site_guid[7]);
    return create ? CreateEventA(NULL, TRUE, FALSE, name)   /* manual-reset: broadcast */
                  : OpenEventA(EVENT_MODIFY_STATE | SYNCHRONIZE, FALSE, name);
}
#elif defined(__linux__)
#include <unistd.h>
#include <sys/syscall.h>
#include <linux/futex.h>
#include <time.h>
#include <limits.h>
extern "C" int32_t pmtp_futex_shared_init(volatile uint32_t*) { return 0; } /* no-op: futex ya es global */
#elif defined(__APPLE__)
extern "C" int32_t pmtp_futex_shared_init(volatile uint32_t*) { return 0; }
extern "C" int __ulock_wait(uint32_t operation, void *addr, uint64_t value, uint32_t timeout_us);
extern "C" int __ulock_wake(uint32_t operation, void *addr, uint64_t wake_value);
#define UL_COMPARE_AND_WAIT 1
#define ULF_WAKE_ALL 0x00000100
#else
extern "C" int32_t pmtp_futex_shared_init(volatile uint32_t*) { return 0; }
#endif

/* Espera: RE-CHEQUEA la condicion en bucle. Devuelve 0 solo si *addr != expected. */
extern "C" int32_t polydim_futex_wait_v808_1(volatile uint32_t* addr, uint32_t expected_val, uint32_t timeout_ms) {
    if (!addr) return -1;

#if defined(_WIN32)
    PmtpFutexSharedHeader* hdr =
        reinterpret_cast<PmtpFutexSharedHeader*>(
            reinterpret_cast<char*>(const_cast<uint32_t*>(addr)) - sizeof(PmtpFutexSharedHeader));
    if (hdr->magic != PMTP_FUTEX_MAGIC) return -1;   /* sitio no inicializado */

    for (uint32_t spin = 0; spin < 4000; ++spin) {
        if (*addr != expected_val) return 0;
        YieldProcessor();
    }
    HANDLE ev = open_site_event(hdr, TRUE);
    if (!ev) return -1;
    const DWORD timeout = (timeout_ms == 0xFFFFFFFF) ? INFINITE : timeout_ms;
    int32_t result = 1; /* timeout por defecto */
    while (*addr == expected_val) {                  /* bucle con recheck: wake espurio = otro ciclo */
        DWORD wr = WaitForSingleObject(ev, timeout);
        if (wr == WAIT_OBJECT_0) continue;           /* reevaluar la condicion */
        if (wr == WAIT_TIMEOUT) { result = 1; break; }
        result = -1; break;                          /* WAIT_FAILED u otro */
    }
    if (*addr != expected_val) result = 0;
    CloseHandle(ev);
    return result;
#elif defined(__linux__)
    struct timespec ts;
    struct timespec* pts = nullptr;
    if (timeout_ms != 0xFFFFFFFF) {
        ts.tv_sec  = timeout_ms / 1000;
        ts.tv_nsec = (timeout_ms % 1000) * 1000000;
        pts = &ts;
    }
    long res = syscall(SYS_futex, (uint32_t*)addr, FUTEX_WAIT, expected_val, pts, nullptr, 0);
    if (res == 0) return 0;
    return (*addr != expected_val) ? 0 : 1;          /* EAGAIN/ETIMEDOUT distinguidos por re-lectura */
#elif defined(__APPLE__)
    uint32_t timeout_us = (timeout_ms == 0xFFFFFFFF) ? 0 : timeout_ms * 1000;
    int res = __ulock_wait(UL_COMPARE_AND_WAIT, (void*)addr, expected_val, timeout_us);
    if (res < 0) return (*addr != expected_val) ? 0 : 1;
    return 0;
#else
    return -1;
#endif
}

extern "C" int32_t polydim_futex_wake_v808_1(volatile uint32_t* addr, bool wake_all) {
    if (!addr) return -1;

#if defined(_WIN32)
    PmtpFutexSharedHeader* hdr =
        reinterpret_cast<PmtpFutexSharedHeader*>(
            reinterpret_cast<char*>(const_cast<uint32_t*>(addr)) - sizeof(PmtpFutexSharedHeader));
    if (hdr->magic != PMTP_FUTEX_MAGIC) return -1;
    HANDLE ev = open_site_event(hdr, FALSE);
    if (ev) { SetEvent(ev); CloseHandle(ev); }       /* broadcast cross-process */
    if (wake_all) WakeByAddressAll((PVOID)addr);     /* intra-proceso, sin nombre */
    else          WakeByAddressSingle((PVOID)addr);
    return 0;
#elif defined(__linux__)
    syscall(SYS_futex, (uint32_t*)addr, FUTEX_WAKE, wake_all ? INT_MAX : 1, nullptr, nullptr, 0);
    return 0;
#elif defined(__APPLE__)
    uint32_t op = UL_COMPARE_AND_WAIT | (wake_all ? ULF_WAKE_ALL : 0);
    __ulock_wake(op, (void*)addr, 0);
    return 0;
#else
    return -1;
#endif
}
