# ADVERSARIAL AUDIT — MÓDULO 2: PMTP RCU & IPC FUTEX CONCURRENCY

**Auditor stance:** Hostile. Assume every comment is a lie until proven by memory-model reasoning. Assume every `__declspec(dllexport)` on Linux is a compile error until proven otherwise. Assume every "fix" comment is a regression.

**Scope note (pre-audit):** The file is named `pmtp_rcu_v810.cpp` but the header comment says `pmtp_rcu_v808_1.cpp (PATCH C1)`. Version drift is itself a finding — see F-0.

---

## F-0 — PRELIMINARY: BUILD-BREAKING / ABI-LEVEL DEFECTS

Before function-by-function, three global defects invalidate the "certified" claim on any platform other than MSVC:

1. **`__declspec(dllexport)` on GCC/Clang.** `__declspec` is a Microsoft extension. On Linux/macOS this is a hard compile error unless `-fdeclspec` is passed (Clang) or a macro shim exists. The header `polydim_solver_abi_v808_1.h` is not shown; if it does not `#define __declspec(x)` on non-Windows, **the entire module fails to compile on Linux/macOS**. The Linux/macOS branches of `ipc_futex_v810.cpp` are therefore dead code that has never been compiled. **VERDICT: VULNERABLE (build).**

2. **`#pragma comment(lib, "synchronization.lib")`** is MSVC-only. On MinGW this is ignored; `WakeByAddressAll`/`WakeByAddressSingle` are then unresolved. **VERDICT: VULNERABLE (link).**

3. **`PmtpFutexSharedHeader` is defined only inside `#if defined(_WIN32)`.** On Linux/macOS the struct does not exist, but `polydim_futex_wait_v808_1` on Linux does not reference it — OK. However `pmtp_futex_shared_init` on Linux is a no-op returning 0, which means **the "shared identifier" contract is silently violated on Linux**: the caller believes init succeeded, but no GUID is written. If any caller relies on `hdr->magic` being set (e.g., a portable wrapper), it will read garbage. **VERDICT: VULNERABLE (contract divergence).**

These are not "style" issues. They mean the module as written is **not portable** despite the `#if defined(__linux__)` branches. I will now audit assuming MSVC/Windows for the RCU file and both platforms for the futex file, flagging platform-specific defects.

---

## MODULE A — `pmtp_rcu_v810.cpp`

### A.1 — `pmtp_now_ns()`

1. **FUNCTION NAME:** `pmtp_now_ns`
2. **VERDICT:** CERTIFIED (with caveat)
3. **REASONING:** `steady_clock` is monotonic per C++ standard; `duration_cast<nanoseconds>` is exact (no rounding loss since steady_clock period ≤ ns on all mainstream platforms). No shared state, no ordering concerns. Caveat: on Windows, `steady_clock` is backed by `QueryPerformanceCounter`, whose resolution is typically ~100 ns but whose *granularity* can be coarser (e.g., 15.6 ms on some VMs without `timeBeginPeriod`). This affects the *deadline* semantics below, not this function.
4. **PATCH:** None required for this function.

---

### A.2 — `pmtp_banked_slot_init`

1. **FUNCTION NAME:** `pmtp_banked_slot_init`
2. **VERDICT:** VULNERABLE
3. **REASONING:**
   - `memset(header, 0, sizeof(*header))` zeroes the whole header, then sets `active_bank = 0`, `prev_bank = PMTP_NUM_RCU_SLOTS - 1`. If `PMTP_NUM_RCU_SLOTS == 0`, `prev_bank` underflows to `UINT32_MAX`. The header does not show the macro; **this is an unverified assumption**. If `PMTP_NUM_RCU_SLOTS < 3`, the writer's `wbank = (2*N - cur - prv) % N` logic (see A.8) degenerates.
   - **No memory fence after init.** The comment says "llamar una vez, antes de publicar" — but there is no `atomic_thread_fence(release)` and no `std::atomic` store. If another process/thread observes the header via shared memory before the memset completes, it sees torn state. The contract "before publishing" is a *caller obligation*, not enforced. This is acceptable only if the caller guarantees a happens-before edge (e.g., the segment is created and only then mapped by others). **Not proven.**
   - `memset` on a struct containing `std::atomic` members is technically UB per [atomics.types.generic]/p1 (atomics are not trivially copyable in the strict sense for `memset` purposes on all implementations). In practice MSVC/GCC/Clang tolerate it, but it is not standards-clean.
4. **PATCH:**
   ```cpp
   static_assert(PMTP_NUM_RCU_SLOTS >= 3, "banked RCU requires >=3 slots");
   extern "C" __declspec(dllexport) void pmtp_banked_slot_init(PmtpBankedSlotHeader* header) {
       if (!header) return;
       // Zero via volatile byte loop to avoid memset-on-atomics UB, or use
       // std::atomic_ref<uint8_t> per byte. Simplest portable fix:
       volatile uint8_t* p = reinterpret_cast<volatile uint8_t*>(header);
       for (size_t i = 0; i < sizeof(*header); ++i) p[i] = 0;
       std::atomic_thread_fence(std::memory_order_release);
       reinterpret_cast<std::atomic<uint32_t>*>(&header->active_bank)
           ->store(0, std::memory_order_relaxed);
       reinterpret_cast<std::atomic<uint32_t>*>(&header->prev_bank)
           ->store(PMTP_NUM_RCU_SLOTS - 1, std::memory_order_relaxed);
       std::atomic_thread_fence(std::memory_order_release);
   }
   ```

---

### A.3 — `pmtp_is_process_alive`

1. **FUNCTION NAME:** `pmtp_is_process_alive`
2. **VERDICT:** VULNERABLE (PID-reuse TOCTOU)
3. **REASONING:**
   - **Windows:** `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, ...)` returns `NULL` with `ERROR_ACCESS_DENIED` for a *live* process we lack rights to → returns 1 (alive). Correct. But `ERROR_INVALID_PARAMETER` (PID does not exist) → returns 0. Correct. **However:** if the process exited and its PID was recycled by a new process, `OpenProcess` succeeds and `GetExitCodeProcess` returns `STILL_ACTIVE` → returns 1. **PID reuse is not detected.** The caller stores `process_start_time_ns` in the lease but `pmtp_is_process_alive` never compares it. This is a **classic PID-reuse TOCTOU**: a dead reader's lease can be "reclaimed" as alive, or worse, a live reader's lease can be reclaimed if the PID was recycled by a *different* process that then died.
   - **Linux:** `kill(pid, 0)` has the same PID-reuse problem. `EPERM` → alive (correct). `ESRCH` → dead. But PID recycling between the `kill` and the CAS in `pmtp_reap_orphaned_leases` is unguarded.
   - **Zombie processes:** on Linux, a zombie (exited but not reaped) returns 0 from `kill(pid,0)` → reported alive. A zombie reader will never release its lease → **permanent drain timeout**. This is a real liveness bug.
4. **PATCH:** Compare `process_start_time_ns` against the OS-reported start time. On Linux, read `/proc/<pid>/stat` field 22 (`starttime` in clock ticks since boot) and compare. On Windows, use `GetProcessTimes` and compare `lpCreationTime` against the stored value. If mismatch → treat as dead (PID recycled). Also treat zombies as dead on Linux by checking `/proc/<pid>/stat` state field `Z`.

---

### A.4 — `pmtp_get_bank`

1. **FUNCTION NAME:** `pmtp_get_bank`
2. **VERDICT:** VULNERABLE (silent aliasing on out-of-range `b`)
3. **REASONING:**
   - `b % PMTP_NUM_RCU_SLOTS` — if `PMTP_NUM_RCU_SLOTS == 0`, **division by zero** (UB, typically SIGFPE on x86). Not guarded.
   - The `default:` case returns `leases_bank0` for **any** `b % N` not in {1,2}. If `N > 3`, banks 3..N-1 all alias to bank0. If `N == 3`, `b%3 ∈ {0,1,2}` → correct. If `N == 4`, `b%4 == 3` → aliases to bank0. **Silent data corruption** if the caller ever passes a bank index ≥ 3 with N > 3.
   - The function is `static` and only called with `bank` from `active_bank`/`prev_bank`/`wbank`, all of which are `< N` by construction *if* the invariant holds. But `pmtp_banked_slot_release_reader` takes `bank` from the caller with **no validation** (see A.6).
4. **PATCH:**
   ```cpp
   static PmtpReaderLease* pmtp_get_bank(PmtpBankedSlotHeader* h, uint32_t b) {
       static_assert(PMTP_NUM_RCU_SLOTS == 3, "pmtp_get_bank only supports 3 banks");
       switch (b) {
           case 0: return h->leases_bank0;
           case 1: return h->leases_bank1;
           case 2: return h->leases_bank2;
           default: return nullptr;  // caller must handle
       }
   }
   ```
   And every caller must null-check.

---

### A.5 — `pmtp_reap_orphaned_leases`

1. **FUNCTION NAME:** `pmtp_reap_orphaned_leases`
2. **VERDICT:** VULNERABLE
3. **REASONING:**
   - **Deadline check placement:** `if (pmtp_now_ns() > deadline) break;` is checked *before* each iteration. If `timeout_ns == 0`, `deadline == now`, and the first check `now > now` is false → the loop runs at least one full iteration. Minor, but the contract "timeout_ns is the max time spent" is violated by up to one `pmtp_is_process_alive` call (which on Windows is a syscall, ~µs). Acceptable but not exact.
   - **`pmtp_is_process_alive` is called while holding no lock, but the lease's `pid` field is read non-atomically** (`leases[i].pid`). The reader writes `leases[i].pid = pid` *after* the CAS to `PMTP_LEASE_ACTIVE` (see A.6). So a reaper can observe `state == ACTIVE` (via acquire load) and then read a **stale or torn `pid`**. On x86-64, aligned 32-bit loads are atomic, so no tearing, but the *value* may be the previous reader's PID if the new reader's `pid` store hasn't propagated. The acquire load on `state` synchronizes-with the reader's release CAS, which happens-before the `pid` store — **wait, no**: the reader does `CAS(state, ACTIVE)` *then* `leases[i].pid = pid`. The CAS is `acq_rel`, so the reaper's acquire load of `state == ACTIVE` synchronizes-with the reader's release CAS, but the `pid` store happens *after* the CAS in program order and is **not** ordered by that release. The reaper can therefore read the *old* `pid`. **This is a real data race on `leases[i].pid`.**
   - **Consequence:** the reaper may call `pmtp_is_process_alive(old_pid)` and, if the old PID is dead, CAS `state` from ACTIVE → RECLAIMED, **killing a live reader's lease**. The live reader then writes to a bank the writer is about to overwrite → **use-after-free / torn read**.
   - **`num_reclaimed_orphans` fetch_add is `relaxed`** — fine for a counter, but the counter is in the shared header and may be read by another process; relaxed is acceptable for a monotonic counter.
   - **No fence between the `pmtp_is_process_alive` check and the CAS.** The CAS is `acq_rel`, which is sufficient for the state transition, but the *decision* to reclaim is based on a racy read of `pid`.
4. **PATCH:** The reader must publish `pid` and `process_start_time_ns` **before** the CAS to ACTIVE, using a two-phase protocol:
   ```cpp
   // Reader:
   leases[i].pid = pid;                       // plain store, but...
   leases[i].process_start_time_ns = start_time_ns;
   std::atomic_thread_fence(std::memory_order_release);
   uint32_t expected = cur;
   if (st->compare_exchange_strong(expected, PMTP_LEASE_ACTIVE,
                                   std::memory_order_acq_rel)) { ... }
   ```
   But this races with another reader trying the same slot. The correct fix is a **two-word CAS** (or a seqlock on the lease): pack `{state, pid}` into a single 64-bit atomic, or use a per-slot spinlock. Alternatively, make `pid` an `std::atomic<uint32_t>` and have the reaper load it with `acquire` *after* observing `state == ACTIVE` — but that still doesn't order the reader's `pid` store before the CAS. The only correct fix is to store `pid` **before** the CAS and accept that a concurrent reader may overwrite it — which requires the CAS to be the *only* writer of `state`, and `pid` to be written only by the CAS winner. Since the CAS winner is unique, the sequence is: CAS wins → write pid → fence. The reaper must then re-check `state` after reading `pid`:
   ```cpp
   if (st->load(acquire) != ACTIVE) continue;
   uint32_t p = leases[i].pid;  // may be stale
   if (!pmtp_is_process_alive(p)) {
       // re-validate: state must still be ACTIVE and pid unchanged
       if (st->load(acquire) == ACTIVE && leases[i].pid == p) {
           uint32_t exp = ACTIVE;
           st->compare_exchange_strong(exp, RECLAIMED, acq_rel);
       }
   }
   ```
   This is still racy (the reader could write `pid` between the two loads). **The only sound fix is to make the lease a single 64-bit atomic word** encoding `{state:2, pid:30, ...}` or to use a per-slot lock. I will not pretend a fence fixes this.

---

### A.6 — `pmtp_banked_slot_acquire_reader`

1. **FUNCTION NAME:** `pmtp_banked_slot_acquire_reader`
2. **VERDICT:** VULNERABLE (multiple defects)
3. **REASONING:**
   - **`g_epoch` and `g_seq` are loaded but never used for validation.** The reader stores `epoch` and `generation` into the lease, but nothing ever reads them back to detect a stale lease. Dead code, or a missing validation in the writer's drain. **The "anti-torn-stale" comment is misleading**: the actual anti-torn check is the `g_active` re-load after the CAS, not the epoch.
   - **The `g_active` re-check is insufficient.** After the CAS to ACTIVE, the reader loads `g_active` and compares to `bank`. If different, it stores `CLOSED` and breaks to retry. But between the CAS and the re-check, the writer may have:
     1. Observed the lease as ACTIVE (drain loop).
     2. Timed out or proceeded (if the reader's CAS was to a bank the writer is *not* draining — but the writer drains `wbank`, and the reader acquired `bank == active_bank`, which is *not* `wbank` by construction). So the writer is not draining this bank. **OK.**
     3. Committed: `prev = active; active = wbank`. Now `bank` is `prev`. The reader's re-check sees `g_active != bank` → stores CLOSED, retries. **But the reader has already written `pid`, `epoch`, `generation` into the lease.** The writer's next drain of `bank` (now `prev`) will see `state == CLOSED` and recycle it. **OK.**
   - **The real bug: the reader writes `leases[i].pid` etc. *after* the CAS, with no fence before the CAS.** As in A.5, the reaper can read a stale `pid`. Same defect.
   - **`std::atomic_thread_fence(std::memory_order_acquire)` after the stores is a no-op for ordering the stores relative to the CAS.** The CAS is `acq_rel`; the fence after it does nothing useful. The comment "Anti-torn-stale" is attached to the wrong operation.
   - **`break` inside the inner loop on bank rotation exits the inner loop, then `std::this_thread::yield()`, then the outer loop retries.** But the outer loop is bounded at 