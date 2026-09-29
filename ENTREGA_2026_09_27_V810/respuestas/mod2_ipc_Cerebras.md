**POLYDIM V810 – Adversarial Silicon‑Level Audit (Red‑Team)**  
*Module 2 – RCU Banked Slot + IPC Futex*  

Below is a **line‑by‑line, function‑by‑function** security & correctness review.  
For every exported or static routine the audit reports:

1. **FUNCTION NAME** – as it appears in the source.  
2. **VERDICT** – `[CERTIFIED]` if the implementation can be proved correct under the stated concurrency model, or `[VULNERABLE]` if a concrete flaw (memory‑order, out‑of‑bounds, overflow, data‑race, etc.) is demonstrated.  
3. **REASONING** – precise analysis of atomic ordering, pointer arithmetic, numerical limits, cache‑line effects, and any asymptotic cost.  
4. **PROPOSED PATCH** – exact code change (minimal, drop‑in) for every vulnerable routine.  

> **Scope of the audit** – The analysis is limited to the code fragment supplied.  All external symbols (`PMTP_NUM_RCU_SLOTS`, `PMTP_MAX_READERS_PER_BANK`, `PmtpBankedSlotHeader`, etc.) are assumed to be correctly defined and properly aligned (64‑byte cache‑line alignment is *not* guaranteed by the current code).  Where the proof cannot be completed asymptotically, the verdict is marked **UNKNOWN**.

---

## 1. Helper / Utility Functions

| # | FUNCTION | VERDICT | REASONING |
|---|----------|---------|-----------|
| 1 | `static inline uint64_t pmtp_now_ns()` | **CERTIFIED** | Purely reads `steady_clock`; no memory ordering required, no allocation, no overflow (steady_clock guarantees monotonic 64‑bit nanosecond count). |
| 2 | `extern "C" __declspec(dllexport) void pmtp_banked_slot_init(PmtpBankedSlotHeader* header)` | **CERTIFIED** | `memset` zeroes the whole header; the only subsequent writes (`active_bank = 0; prev_bank = PMTP_NUM_RCU_SLOTS‑1`) are to plain `uint32_t` fields that are not accessed concurrently during initialization. No pointer arithmetic, no arithmetic overflow. |
| 3 | `static int pmtp_is_process_alive(uint32_t pid)` | **CERTIFIED** | Platform‑specific system calls (`OpenProcess`, `kill`) are side‑effect‑free with respect to the shared memory region. No data races, no arithmetic issues. |
| 4 | `static PmtpReaderLease* pmtp_get_bank(PmtpBankedSlotHeader* h, uint32_t b)` | **CERTIFIED** | The modulo operation guarantees `b % PMTP_NUM_RCU_SLOTS ∈ {0,1,2}`; the switch returns one of the three statically‑declared pointer members. No out‑of‑bounds access, no atomic interaction. |

---

## 2. RCU‑Banked Slot – Reader Path

| # | FUNCTION | VERDICT | REASONING |
|---|----------|---------|-----------|
| 5 | `extern "C" __declspec(dllexport) int32_t pmtp_reap_orphaned_leases(...)` | **CERTIFIED** | *Array bounds*: iterates `i < PMTP_MAX_READERS_PER_BANK` – safe by definition. <br>*Atomic ordering*: loads `state` with `memory_order_acquire`; CAS uses `acq_rel`, guaranteeing that a reclaimed lease becomes visible only after the writer has observed the state change. <br>*Deadline*: `pmtp_now_ns()` is monotonic; the loop may break early but never overruns the deadline. <br>*Allocation*: none. <br>*Cache‑line*: `header->num_reclaimed_orphans` is updated with `relaxed` – acceptable because it is a pure counter. |
| 6 | `extern "C" __declspec(dllexport) int32_t pmtp_banked_slot_acquire_reader(...)` | **CERTIFIED** | *Correct RCU acquisition*: <br>1. `g_active` is loaded with `acquire`, establishing a happens‑before edge to any writer that later publishes a new `active_bank`. <br>2. Lease `state` is CAS‑ed from any non‑ACTIVE value to `ACTIVE` with `acq_rel`. This synchronizes the writer’s later `acquire` on the same `state`. <br>3. After writing the lease fields (`pid`, `epoch`, …) a `thread_fence(acquire)` guarantees that any subsequent read of those fields by a writer that sees the `ACTIVE` state observes the freshly written values. <br>4. The “anti‑torn‑stale” check (`g_active` re‑load) guarantees that a writer rotation that occurs *between* the CAS and the fence forces the lease to be closed and the reader to retry. <br>*Loop bound*: at most 8 attempts, each bounded by a `yield`. No allocation, no exponential back‑off → O(1) worst‑case. <br>*No under‑/over‑flow*: all indices are derived from `PMTP_MAX_READERS_PER_BANK`. |
| 7 | `extern "C" __declspec(dllexport) int32_t pmtp_banked_slot_release_reader(PmtpBankedSlotHeader* header, uint32_t bank, uint32_t slot_idx)` | **VULNERABLE** | **Bug** – the function validates `slot_idx` but **does not validate `bank`**. `bank` is used directly as an index into the three `leases_bankX` arrays via `pmtp_get_bank`. If a malicious caller supplies `bank ≥ PMTP_NUM_RCU_SLOTS` (or a negative value cast to unsigned), the pointer arithmetic will select an out‑of‑bounds `leases_bankX` pointer, and the subsequent `store` will corrupt adjacent memory (potentially the header itself or other process‑shared structures). <br>*Memory‑order*: the `store` uses `release`, which is correct, but the out‑of‑bounds write is a hard‑fault. |
|   | **Patch** |  | ```cpp\nextern "C" __declspec(dllexport) int32_t pmtp_banked_slot_release_reader(\n    PmtpBankedSlotHeader* header, uint32_t bank, uint32_t slot_idx)\n{\n    if (!header) return POLYDIM_STATUS_ERR_NULL_PTR;\n    if (bank >= PMTP_NUM_RCU_SLOTS) return POLYDIM_STATUS_ERR_INVALID_DIM; // <‑‑ added check\n    if (slot_idx >= PMTP_MAX_READERS_PER_BANK) return POLYDIM_STATUS_ERR_INVALID_SLOT;\n    reinterpret_cast<std::atomic<uint32_t>*>(&pmtp_get_bank(header, bank)[slot_idx].state)\n        ->store(PMTP_LEASE_CLOSED, std::memory_order_release);\n    return POLYDIM_STATUS_OK;\n}\n``` |
|   |   |   | The added guard eliminates the out‑of‑bounds write; the error code follows the existing convention (`POLYDIM_STATUS_ERR_INVALID_DIM`). |

---

## 3. RCU