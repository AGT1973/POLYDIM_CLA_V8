/* ========================================================= */
/* FILE: pmtp_rcu_v808_1.cpp  (PATCH C1)                      */
/* Reescritura del Banked RCU. Correcciones:                  */
/*  1. Lectores leen active_bank (publicado), NO derivan el   */
/*     banco de global_epoch -> elimina la carrera escritor/  */
/*     lector-nuevo del V808.                                 */
/*  2. Escritor escribe el unico banco que NO esta en uso     */
/*     (ni active_bank ni prev_bank), lo drena con deadline   */
/*     real y devuelve POLYDIM_STATUS_ERR_DRAIN_TIMEOUT.      */
/*  3. global_epoch avanza solo en commit_writer.             */
/*  4. Watchdog de escritor muerto via owner_pid / heartbeat. */
/* ========================================================= */

#include "polydim_solver_abi_v808_1.h"
#include <atomic>
#include <chrono>
#include <cstring>
#include <thread>

#if defined(_WIN32)
  #include <windows.h>
#else
  #include <signal.h>
  #include <sys/types.h>
  #include <errno.h>
  #include <unistd.h>
#endif

#define PMTP_WRITER_STEAL_TIMEOUT_NS  (5ull * 1000ull * 1000ull) /* 5 s */
#define PMTP_DRAIN_POLL_MIN_NS        (50ull * 1000ull)          /* 50 us */
#define PMTP_DRAIN_POLL_MAX_NS        (1ull   * 1000ull * 1000ull) /* 1 ms */

static inline uint64_t pmtp_now_ns() {
    return (uint64_t)std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

/* Inicializacion del slot compartido (llamar una vez, antes de publicar) */
extern "C" void pmtp_banked_slot_init(PmtpBankedSlotHeader* header) {
    if (!header) return;
    memset(header, 0, sizeof(*header));
    /* active_bank = 0, prev_bank = 2  ->  el primer write_bank sera 1 */
    header->active_bank = 0;
    header->prev_bank   = PMTP_NUM_RCU_SLOTS - 1;
}

static int pmtp_is_process_alive(uint32_t pid) {
    if (pid == 0) return 0;
#if defined(_WIN32)
    HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, (DWORD)pid);
    if (h == NULL) return (GetLastError() == ERROR_ACCESS_DENIED) ? 1 : 0;
    DWORD exit_code = 0;
    int alive = 0;
    if (GetExitCodeProcess(h, &exit_code)) alive = (exit_code == STILL_ACTIVE) ? 1 : 0;
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
    switch (b % PMTP_NUM_RCU_SLOTS) {
        case 1:  return h->leases_bank1;
        case 2:  return h->leases_bank2;
        default: return h->leases_bank0;
    }
}

/* Reap de leases de procesos muertos. timeout_ns ahora SI se usa:
 * es el deadline acumulado maximo que el caller permite gastar aqui. */
extern "C" int32_t pmtp_reap_orphaned_leases(
    PmtpBankedSlotHeader* header, uint32_t target_bank,
    uint64_t timeout_ns, uint32_t* num_reclaimed)
{
    if (!header || !num_reclaimed) return POLYDIM_STATUS_ERR_NULL_PTR;
    *num_reclaimed = 0;
    const uint64_t deadline = pmtp_now_ns() + timeout_ns;
    PmtpReaderLease* leases = pmtp_get_bank(header, target_bank);

    for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
        if (pmtp_now_ns() > deadline) break;               /* deadline real */
        std::atomic<uint32_t>* st =
            reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
        if (st->load(std::memory_order_acquire) != PMTP_LEASE_ACTIVE) continue;
        if (!pmtp_is_process_alive(leases[i].pid)) {
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

/* LECTOR: lee el banco PUBLICADO. La unica fuente de verdad es active_bank. */
extern "C" int32_t pmtp_banked_slot_acquire_reader(
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

    for (int attempt = 0; attempt < 8; ++attempt) {
        const uint32_t bank = g_active->load(std::memory_order_acquire);
        PmtpReaderLease* leases = pmtp_get_bank(header, bank);

        for (size_t i = 0; i < PMTP_MAX_READERS_PER_BANK; ++i) {
            std::atomic<uint32_t>* st =
                reinterpret_cast<std::atomic<uint32_t>*>(&leases[i].state);
            uint32_t cur = st->load(std::memory_order_relaxed);
            if (cur == PMTP_LEASE_ACTIVE) continue;
            uint32_t expected = cur; /* FREE | CLOSED | RECLAIMED */
            if (st->compare_exchange_strong(expected, PMTP_LEASE_ACTIVE,
                                            std::memory_order_acq_rel)) {
                leases[i].pid                 = pid;
                leases[i].process_start_time_ns = start_time_ns;
                leases[i].epoch               = g_epoch->load(std::memory_order_acquire);
                leases[i].generation          = g_seq->load(std::memory_order_acquire);
                *acquired_bank    = bank;
                *acquired_slot_idx = (uint32_t)i;
                std::atomic_thread_fence(std::memory_order_acquire);
                /* Anti-torn-stale: si el publicador rotó justo tras nuestro CAS,
                 * lo detectamos y reintentamos con el banco actual. */
                if (g_active->load(std::memory_order_acquire) != bank) {
                    st->store(PMTP_LEASE_CLOSED, std::memory_order_release);
                    break; /* reintentar con el nuevo banco */
                }
                return POLYDIM_STATUS_OK;
            }
        }
        /* banco lleno o rotado: reintento breve */
        std::this_thread::yield();
    }
    return POLYDIM_STATUS_ERR_NO_FREE_SLOT;
}

extern "C" int32_t pmtp_banked_slot_release_reader(
    PmtpBankedSlotHeader* header, uint32_t bank, uint32_t slot_idx)
{
    if (!header || slot_idx >= PMTP_MAX_READERS_PER_BANK)
        return POLYDIM_STATUS_ERR_NULL_PTR;
    reinterpret_cast<std::atomic<uint32_t>*>(
        &pmtp_get_bank(header, bank)[slot_idx].state)
        ->store(PMTP_LEASE_CLOSED, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}

/* Intenta reclamar el mutex de escritor, con watchdog de escritor muerto.
 * Devuelve POLYDIM_STATUS_OK si este thread quedo como owner. */
static int32_t pmtp_writer_lock(PmtpBankedSlotHeader* header,
                                uint32_t pid, uint64_t start_time_ns)
{
    std::atomic<uint32_t>* w =
        reinterpret_cast<std::atomic<uint32_t>*>(&header->writer_active);
    uint32_t expected = 0;
    if (w->compare_exchange_strong(expected, 1, std::memory_order_acq_rel))
        goto owned;

    /* Writer ocupado: ¿esta vivo? */
    {
        const uint32_t  opid   = header->owner_pid;               /* publicado antes que writer_active=1 */
        const uint64_t  ostart = header->owner_start_time_ns;
        const uint64_t  hb     = reinterpret_cast<std::atomic<uint64_t>*>(
                                     &header->writer_heartbeat_ns)
                                     ->load(std::memory_order_acquire);
        const int       dead   = !pmtp_is_process_alive(opid);
        (void)hb;   /* diagnostico; NO se roba por heartbeat: un escritor vivo
                       con payload largo (>5 s) seria victima de un steal
                       corruptor. Deadlock por escritor colgado = fallo de
                       liveness acceptable; escritor muerto = reclaim seguro. */

        if (dead) {
            /* Re-verificar identidad del owner para no robarle a un escritor
             * nuevo que re-adquirio el mutex legitimamente. */
            if (ostart == header->owner_start_time_ns) {
                uint32_t one = 1;
                if (w->compare_exchange_strong(one, 0, std::memory_order_acq_rel)) {
                    uint32_t zero = 0;
                    if (w->compare_exchange_strong(zero, 1, std::memory_order_acq_rel))
                        goto owned;
                }
            }
        }
    }
    return POLYDIM_STATUS_ERR_WRITER_BUSY;

owned:
    header->owner_pid            = pid;
    header->owner_start_time_ns  = start_time_ns;
    reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_heartbeat_ns)
        ->store(pmtp_now_ns(), std::memory_order_release);
    std::atomic_thread_fence(std::memory_order_seq_cst);
    return POLYDIM_STATUS_OK;
}

extern "C" int32_t pmtp_banked_slot_acquire_writer(
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

    /* Banco a escribir: el UNICO que no esta en uso.
     * Lectores actuales usan active_bank; lectores rezagados pueden
     * aun tener leases en prev_bank. */
    const uint32_t cur = g_active->load(std::memory_order_acquire);
    const uint32_t prv = g_prev->load(std::memory_order_acquire);
    uint32_t wbank = (PMTP_NUM_RCU_SLOTS * 2 - cur - prv) % PMTP_NUM_RCU_SLOTS;
    if (wbank == cur || wbank == prv) {   /* estado compartido corrupto: no escribir */
        reinterpret_cast<std::atomic<uint32_t>*>(&header->writer_active)
            ->store(0, std::memory_order_release);
        return POLYDIM_STATUS_ERR_ABI_MISMATCH;
    }

    /* Drain con deadline real: nunca escribimos sobre un lector vivo. */
    {
        const uint64_t deadline = pmtp_now_ns() + PMTP_DRAIN_POLL_MAX_NS * 1000; /* ~1 s */
        uint64_t backoff = PMTP_DRAIN_POLL_MIN_NS;
        for (;;) {
            hb->store(pmtp_now_ns(), std::memory_order_release);   /* latido */
            bool busy = false;
            PmtpReaderLease* leases = pmtp_get_bank(header, wbank);
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
                reinterpret_cast<std::atomic<uint32_t>*>(&header->writer_active)
                    ->store(0, std::memory_order_release);
                return POLYDIM_STATUS_ERR_DRAIN_TIMEOUT;   /* error real, no silencio */
            }
            std::this_thread::sleep_for(std::chrono::nanoseconds(backoff));
            backoff = (backoff * 2 > PMTP_DRAIN_POLL_MAX_NS)
                      ? PMTP_DRAIN_POLL_MAX_NS : backoff * 2;
        }

        /* Banco drenado: reciclar leases CERRADOS/RECLAMADOS a FREE para
         * la siguiente generacion de lectores. */
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

extern "C" int32_t pmtp_banked_slot_commit_writer(
    PmtpBankedSlotHeader* header, uint32_t write_bank)
{
    if (!header) return POLYDIM_STATUS_ERR_NULL_PTR;
    if (write_bank >= PMTP_NUM_RCU_SLOTS) return POLYDIM_STATUS_ERR_INVALID_DIM;

    std::atomic<uint32_t>* g_active =
        reinterpret_cast<std::atomic<uint32_t>*>(&header->active_bank);
    std::atomic<uint32_t>* g_prev =
        reinterpret_cast<std::atomic<uint32_t>*>(&header->prev_bank);

    /* La época y la publicación avanzan SOLO aqui, despues de que el
     * payload del banco esta completo y fenced. */
    std::atomic_thread_fence(std::memory_order_release);
    const uint32_t cur = g_active->load(std::memory_order_relaxed);
    g_prev->store(cur, std::memory_order_release);
    g_active->store(write_bank, std::memory_order_release);
    reinterpret_cast<std::atomic<uint32_t>*>(&header->global_epoch)
        ->fetch_add(1, std::memory_order_acq_rel);
    reinterpret_cast<std::atomic<uint64_t>*>(&header->sequence)
        ->fetch_add(1, std::memory_order_relaxed);
    reinterpret_cast<std::atomic<uint64_t>*>(&header->writer_heartbeat_ns)
        ->store(0, std::memory_order_release);
    reinterpret_cast<std::atomic<uint32_t>*>(&header->writer_active)
        ->store(0, std::memory_order_release);
    return POLYDIM_STATUS_OK;
}
