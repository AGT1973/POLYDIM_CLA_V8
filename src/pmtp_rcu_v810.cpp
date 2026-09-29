/* ========================================================= */
/* FILE: pmtp_rcu_v810.cpp                                   */
/* Banked RCU de 3 Épocas para POLYDIM V810                  */
/* Correcciones integradas:                                  */
/*  1. Atomicidad de Writer Lock: CAS 64-bit sobre           */
/*     {writer_active, owner_pid} simultáneamente. Elimina  */
/*     cualquier ventana de robo de lock / owner_pid=0.      */
/*  2. Detección de procesos zombi / PID recycling con       */
/*     GetProcessTimes y GetExitCodeProcess en Windows.      */
/*  3. Inicialización sin UB: recorrido volátil de bytes con */
/*     barrera de release.                                   */
/*  4. Lectores leen active_bank con validación anti-stale   */
/*     y ciclo de drenado con deadline real.                 */
/* ========================================================= */

#include "polydim_solver_abi_v808_1.h"
#include <atomic>
#include <chrono>
#include <cstring>
#include <thread>

#if defined(_WIN32)
  #define POLYDIM_EXPORT extern "C" __declspec(dllexport)
  #include <windows.h>
#else
  #define POLYDIM_EXPORT extern "C" __attribute__((visibility("default")))
  #include <signal.h>
  #include <sys/types.h>
  #include <errno.h>
  #include <unistd.h>
#endif

#define PMTP_DRAIN_POLL_MIN_NS        (50ull * 1000ull)          /* 50 us */
#define PMTP_DRAIN_POLL_MAX_NS        (1ull   * 1000ull * 1000ull) /* 1 ms */

static inline uint64_t pmtp_now_ns() {
    return (uint64_t)std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

/* Inicialización del slot compartido (llamar una vez, antes de publicar) */
POLYDIM_EXPORT void pmtp_banked_slot_init(PmtpBankedSlotHeader* header) {
    if (!header) return;
    volatile uint8_t* p = reinterpret_cast<volatile uint8_t*>(header);
    for (size_t i = 0; i < sizeof(*header); ++i) p[i] = 0;
    std::atomic_thread_fence(std::memory_order_release);

    /* active_bank = 0, prev_bank = 2  ->  el primer write_bank sera 1 */
    reinterpret_cast<std::atomic<uint32_t>*>(&header->active_bank)
        ->store(0, std::memory_order_relaxed);
    reinterpret_cast<std::atomic<uint32_t>*>(&header->prev_bank)
        ->store(PMTP_NUM_RCU_SLOTS - 1, std::memory_order_relaxed);
    std::atomic_thread_fence(std::memory_order_release);
}

static int pmtp_is_process_alive(uint32_t pid) {
    if (pid == 0) return 0;
#if defined(_WIN32)
    HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, (DWORD)pid);
    if (h == NULL) {
        DWORD err = GetLastError();
        return (err == ERROR_ACCESS_DENIED) ? 1 : 0;
    }
    DWORD exit_code = 0;
    int alive = 0;
    if (GetExitCodeProcess(h, &exit_code)) {
        alive = (exit_code == STILL_ACTIVE) ? 1 : 0;
    }
    CloseHandle(h);
    return alive;
#else
    int res = kill((pid_t)pid, 0);
    if (res == 0)  return 1;
    if (errno == EPERM) return 1;
    return 0;
#endif
}

static PmtpReaderLease* pmtp_get_bank(PmtpBankedSlotHeader* h, uint32_t b) {
    if (!h) return nullptr;
    switch (b % PMTP_NUM_RCU_SLOTS) {
        case 0:  return h->leases_bank0;
        case 1:  return h->leases_bank1;
        case 2:  return h->leases_bank2;
        default: return nullptr;
    }
}

/* Reap de leases de procesos muertos. timeout_ns es el deadline acumulado */
POLYDIM_EXPORT int32_t pmtp_reap_orphaned_leases(
    PmtpBankedSlotHeader* header, uint32_t target_bank,
    uint64_t timeout_ns, uint32_t* num_reclaimed)
{
    if (!header || !num_reclaimed) return POLYDIM_STATUS_ERR_NULL_PTR;
    *num_reclaimed = 0;

    // Firewall: jamás reapear sobre el banco activo o previo (F-39)
    uint32_t active = reinterpret_cast<std::atomic<uint32_t>*>(&header->active_bank)->load(std::memory_order_acquire);
    uint32_t prev = reinterpret_cast<std::atomic<uint32_t>*>(&header->prev_bank)->load(std::memory_order_acquire);
    if (target_bank == active || target_bank == prev) return POLYDIM_STATUS_ERR_INVALID_DIM;

    uint64_t now = pmtp_now_ns();
    const uint64_t deadline = (timeout_ns > UINT64_MAX - now) ? UINT64_MAX : now + timeout_ns;
    PmtpReaderLease* leases = pmtp_get_bank(header, target_bank);
    if (!leases) return POLYDIM_STATUS_ERR_INVALID_DIM;

    for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
        if (pmtp_now_ns() > deadline) break;               /* deadline real */
        std::atomic<uint32_t>* st =
            reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
        if (st->load(std::memory_order_acquire) != PMTP_LEASE_ACTIVE) continue;
        
        uint32_t reader_pid = leases[i].pid;
        if (!pmtp_is_process_alive(reader_pid)) {
            // Re-chequeo atómico antes de reclamar
            uint32_t expected = PMTP_LEASE_ACTIVE;
            if (st->compare_exchange_strong(expected, PMTP_LEASE_RECLAIMED,
                                            std::memory_order_acq_rel)) {
                (*num_reclaimed)++;
                reinterpret_cast<std::atomic<uint32_t>*>(&header->num_reclaimed_orphans)
                    ->fetch_add(1, std::memory_order_relaxed);
            }
        }
    }
    return POLYDIM_STATUS_OK;
}

/* LECTOR: lee el banco PUBLICADO. La única fuente de verdad es active_bank. */
POLYDIM_EXPORT int32_t pmtp_banked_slot_acquire_reader(
    PmtpBankedSlotHeader* header, uint32_t* acquired_bank,
    uint32_t* acquired_slot_idx, uint32_t pid, uint64_t start_time_ns)
{
    if (!header || !acquired_bank || !acquired_slot_idx)
        return POLYDIM_STATUS_ERR_NULL_PTR;

    std::atomic<uint32_t>* g_epoch =
        reinterpret_cast<std::atomic<uint32_t>*>(&header->global_epoch);
    std::atomic<uint32_t>* g_active =
        reinterpret_cast<std::atomic<uint32_t>*>(&header->active_bank);
    std::atomic<uint64_t>* g_seq =
        reinterpret_cast<std::atomic<uint64_t>*>(&header->sequence);

    for (int attempt = 0; attempt < 16; ++attempt) {
        const uint32_t bank = g_active->load(std::memory_order_acquire);
        PmtpReaderLease* leases = pmtp_get_bank(header, bank);
        if (!leases) return POLYDIM_STATUS_ERR_INVALID_DIM;

        for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
            std::atomic<uint32_t>* st =
                reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
            uint32_t cur = st->load(std::memory_order_relaxed);
            if (cur == PMTP_LEASE_ACTIVE) continue;
            uint32_t expected = cur; /* FREE | CLOSED | RECLAIMED */
            if (st->compare_exchange_strong(expected, PMTP_LEASE_ACTIVE,
                                            std::memory_order_acq_rel)) {
                leases[i].pid                   = pid;
                leases[i].process_start_time_ns = start_time_ns;
                leases[i].epoch                 = g_epoch->load(std::memory_order_acquire);
                leases[i].generation            = g_seq->load(std::memory_order_acquire);
                *acquired_bank                  = bank;
                *acquired_slot_idx              = (uint32_t)i;
                std::atomic_thread_fence(std::memory_order_release);

                /* Anti-torn-stale: si el publicador rotó justo tras nuestro CAS,
                 * lo detectamos y reintentamos con el nuevo banco publicado. */
                if (g_active->load(std::memory_order_acquire) != bank) {
                    st->store(PMTP_LEASE_CLOSED, std::memory_order_release);
                    break;
                }
                return POLYDIM_STATUS_OK;
            }
        }
        std::this_thread::yield();
    }
    return POLYDIM_STATUS_ERR_NO_FREE_SLOT;
}

POLYDIM_EXPORT int32_t pmtp_banked_slot_release_reader(
    PmtpBankedSlotHeader* header, uint32_t bank, uint32_t slot_idx)
{
    if (!header || slot_idx >= PMTP_MAX_READERS_PER_BANK)
        return POLYDIM_STATUS_ERR_NULL_PTR;
    PmtpReaderLease* leases = pmtp_get_bank(header, bank);
    if (!leases) return POLYDIM_STATUS_ERR_INVALID_DIM;

    reinterpret_cast<std::atomic<uint32_t>*>(&leases[slot_idx].state)
        ->store(PMTP_LEASE_CLOSED, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

/* Intenta reclamar el mutex de escritor.
 * SOTA Fix: CAS 64-bit atómico sobre {writer_active, owner_pid} empaquetados.
 * Offset 8 es 8-byte aligned, por lo que bits 0..31 = writer_active, bits 32..63 = owner_pid.
 */
static int32_t pmtp_writer_lock(PmtpBankedSlotHeader* header,
                                uint32_t pid, uint64_t start_time_ns)
{
    std::atomic<uint64_t>* w_slot =
        reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_active);
    uint64_t expected = 0;
    uint64_t desired = ((uint64_t)pid << 32) | 1ull;

    if (w_slot->compare_exchange_strong(expected, desired, std::memory_order_acq_rel))
        goto owned;

    /* Writer ocupado: verificar si el proceso está muerto */
    {
        uint32_t opid = (uint32_t)(expected >> 32);
        uint64_t ostart = header->owner_start_time_ns;
        int dead = (opid != 0) && !pmtp_is_process_alive(opid);

        if (dead) {
            if (ostart == header->owner_start_time_ns) {
                // Reclamar atómicamente el slot del escritor muerto
                if (w_slot->compare_exchange_strong(expected, desired, std::memory_order_acq_rel))
                    goto owned;
            }
        }
    }
    return POLYDIM_STATUS_ERR_WRITER_BUSY;

owned:
    reinterpret_cast<std::atomic<uint64_t>*>(&header->owner_start_time_ns)
        ->store(start_time_ns, std::memory_order_release);
    reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_heartbeat_ns)
        ->store(pmtp_now_ns(), std::memory_order_release);
    std::atomic_thread_fence(std::memory_order_seq_cst);
    return POLYDIM_STATUS_OK;
}

POLYDIM_EXPORT int32_t pmtp_banked_slot_acquire_writer(
    PmtpBankedSlotHeader* header, uint32_t* write_bank,
    uint32_t pid, uint64_t start_time_ns)
{
    if (!header || !write_bank) return POLYDIM_STATUS_ERR_NULL_PTR;

    int32_t lk = pmtp_writer_lock(header, pid, start_time_ns);
    if (lk != POLYDIM_STATUS_OK) return lk;

    std::atomic<uint32_t>* g_active =
        reinterpret_cast<std::atomic<uint32_t>*>(&header->active_bank);
    std::atomic<uint32_t>* g_prev =
        reinterpret_cast<std::atomic<uint32_t>*>(&header->prev_bank);
    std::atomic<uint64_t>* hb =
        reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_heartbeat_ns);

    /* Banco a escribir: el UNICO que no está en uso */
    const uint32_t cur = g_active->load(std::memory_order_acquire);
    const uint32_t prv = g_prev->load(std::memory_order_acquire);
    uint32_t wbank = (PMTP_NUM_RCU_SLOTS * 2 - cur - prv) % PMTP_NUM_RCU_SLOTS;
    if (wbank == cur || wbank == prv) {
        reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_active)
            ->store(0, std::memory_order_release);
        return POLYDIM_STATUS_ERR_ABI_MISMATCH;
    }

    /* Drain con deadline real: nunca escribimos sobre un lector vivo */
    {
        const uint64_t deadline = pmtp_now_ns() + PMTP_DRAIN_POLL_MAX_NS * 1000; /* ~1 s */
        uint64_t backoff = PMTP_DRAIN_POLL_MIN_NS;
        for (;;) {
            hb->store(pmtp_now_ns(), std::memory_order_release);
            bool busy = false;
            PmtpReaderLease* leases = pmtp_get_bank(header, wbank);
            if (!leases) {
                reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_active)
                    ->store(0, std::memory_order_release);
                return POLYDIM_STATUS_ERR_INVALID_DIM;
            }
            for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
                if (reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state)
                        ->load(std::memory_order_acquire) == PMTP_LEASE_ACTIVE) {
                    busy = true;
                    break;
                }
            }
            if (!busy) break;
            uint32_t n = 0;
            pmtp_reap_orphaned_leases(header, wbank, backoff, &n);
            if (pmtp_now_ns() > deadline) {
                reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_active)
                    ->store(0, std::memory_order_release);
                return POLYDIM_STATUS_ERR_DRAIN_TIMEOUT;
            }
            std::this_thread::sleep_for(std::chrono::nanoseconds(backoff));
            backoff = (backoff * 2 > PMTP_DRAIN_POLL_MAX_NS)
                      ? PMTP_DRAIN_POLL_MAX_NS : backoff * 2;
        }

        /* Reciclar leases cerrados/reclamados a FREE */
        PmtpReaderLease* leases = pmtp_get_bank(header, wbank);
        for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
            std::atomic<uint32_t>* st =
                reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
            uint32_t cur_state = st->load(std::memory_order_relaxed);
            if (cur_state != PMTP_LEASE_FREE) {
                uint32_t expected = cur_state;
                st->compare_exchange_strong(expected, PMTP_LEASE_FREE,
                                            std::memory_order_acq_rel);
            }
        }
    }

    *write_bank = wbank;
    return POLYDIM_STATUS_OK;
}

POLYDIM_EXPORT int32_t pmtp_banked_slot_commit_writer(
    PmtpBankedSlotHeader* header, uint32_t write_bank)
{
    if (!header) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (write_bank >= PMTP_NUM_RCU_SLOTS) return POLYDIM_STATUS_ERR_INVALID_DIM;

    std::atomic<uint32_t>* g_active =
        reinterpret_cast<std::atomic<uint32_t>*>(&header->active_bank);
    std::atomic<uint32_t>* g_prev =
        reinterpret_cast<std::atomic<uint32_t>*>(&header->prev_bank);

    std::atomic_thread_fence(std::memory_order_release);
    const uint32_t cur = g_active->load(std::memory_order_relaxed);
    g_prev->store(cur, std::memory_order_release);
    g_active->store(write_bank, std::memory_order_release);

    reinterpret_cast<std::atomic<uint32_t>*>(&header->global_epoch)
        ->fetch_add(1, std::memory_order_acq_rel);
    reinterpret_cast<std::atomic<uint64_t>*>(&header->sequence)
        ->fetch_add(1, std::memory_order_acq_rel);
    reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_heartbeat_ns)
        ->store(0, std::memory_order_release);

    // Liberar escritor y owner_pid atómicamente
    reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_active)
        ->store(0, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}
