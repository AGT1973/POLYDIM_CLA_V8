# Red Team Analysis: V808.1 Concurrency Primitives

## 1. `pmtp_banked_slot_acquire_writer` / `commit_writer` — 3-bank RCU rotation

### Structural hazard: bank index is not a linearization point

If the acquire path is of the form:

```cpp
bank = atomic_fetch_add(&rot, 1) % 3;   // or load(relaxed) + CAS
slot = &banks[bank];
```

then the *selection* of the bank and the *publication* of the writer's intent are two distinct operations. Under N=64 threads, two writers can observe the same `bank` value if the rotation counter is read with `memory_order_relaxed` and the modulo is applied post-hoc. The `% 3` is not atomic with the fetch — the counter is monotonic, but the *mapping* to a bank is a non-injective function of the counter under concurrent observation. This is a classic **ABA-adjacent aliasing** on a small modulus.

**Required fix:** the bank index must be the *value returned by the atomic RMW itself*, not a derived quantity. If `rot` is a 64-bit counter, `bank = (ret) % 3` is fine *only if* the acquire is a single `fetch_add(1, acq_rel)` and the slot's ownership is established by a per-bank `writer_epoch` CAS, not by the counter alone.

### Missing per-bank ownership token

RCU-style rotation across 3 banks requires that each bank carry an explicit `writer_epoch` (or `owner_tid`) that is CAS'd from `FREE → CLAIMED` before the slot is written. Without it, the rotation counter is a *hint*, not a *lock*. Under 64 threads the probability of two writers landing on the same bank within one rotation window is non-negligible (birthday bound: ~1 − exp(−64²/(2·3)) ≈ 1).

**Required:** `banks[i].owner.compare_exchange_strong(FREE, tid, acq_rel, acquire)` before any payload write. The rotation counter alone is insufficient.

### Commit ordering

`commit_writer` must publish in this exact order:

```cpp
// payload writes (non-atomic)
atomic_thread_fence(memory_order_release);          // or store-release on seq
banks[i].seq.store(epoch, memory_order_release);    // publication
banks[i].owner.store(FREE, memory_order_release);   // release ownership
```

If `owner` is cleared *before* `seq` is published, a reader can observe `owner==FREE` and read a torn payload. If `seq` is published with `relaxed`, ARM64 will reorder the payload stores past the seq store — x86 will not, which is exactly the x86-vs-ARM64 divergence you flagged.

**ARM64 requirement:** the payload stores must be ordered before the `seq` store via `stlr` (store-release) on `seq`, or an explicit `dmb ish` between payload and seq. A `relaxed` seq store is a bug on ARM64 and a latent bug on x86 (compiler reordering).

### Reader side (implied)

Readers must do `seq.load(acquire)` then payload reads, then re-check `seq` (seqlock pattern). With 3 banks and RCU grace periods, the re-check is mandatory — otherwise a writer rotating back to the same bank within the reader's critical section produces a torn read. The 3-bank depth only helps if the grace period is *bounded by the rotation rate*, which is not guaranteed under N=64.

---

## 2. SPSC Ring Buffer with 128-byte padding

### False sharing: 128 is not universally correct

128-byte padding assumes a 128-byte cache line. On x86 (64B lines) this wastes 64B per side but is safe. On ARM64 (typically 64B, some 128B on Apple/Ampere Altra), it is safe. **But** on Intel with adjacent-line prefetcher (spatial prefetcher fetching 128B pairs), two 64B lines are pulled together — padding to 128B does *not* prevent the prefetcher from co-fetching the producer's `head` with the consumer's `tail` if they are 128B apart and the prefetcher is active. The correct mitigation is `alignas(128)` **plus** placing the two indices in separate 128B-aligned regions with a ≥128B gap, or disabling the adjacent-line prefetcher via `wrmsr` (not portable).

### The real bug: `head`/`tail` are not the only shared state

If the ring stores `size`, `mask`, or a cached `cached_tail`/`cached_head` (common optimization to reduce cross-core loads), those fields must also be isolated. A cached tail on the producer side that is updated with `relaxed` and read by the consumer with `relaxed` is a **data race** under the C++ memory model — it must be `atomic<size_t>` with `relaxed` at minimum, and the *actual* publication still requires `release` on `head` / `acquire` on `tail`.

### Memory ordering: the canonical SPSC contract

Producer:
```cpp
slot[head & mask] = item;                    // payload
head.store(head+1, memory_order_release);    // publish
```

Consumer:
```cpp
h = head.load(memory_order_acquire);         // observe
if (h == tail) return empty;
item = slot[tail & mask];                    // payload read
tail.store(tail+1, memory_order_release);    // free slot
```

**x86:** `release` store compiles to plain `mov` (TSO gives store-store ordering); `acquire` load compiles to plain `mov` (TSO gives load-load ordering). Correct but *only* because x86 TSO is stronger than the C++ model requires. Do not rely on this — the compiler can still reorder non-atomic payload accesses past the atomic if the atomic is `relaxed`.

**ARM64:** `release` → `stlr`, `acquire` → `ldar`. These are the minimum. A `relaxed` head store on ARM64 allows the payload store to be observed *after* the head increment by another core — the consumer reads a stale slot. This is the single most common SPSC bug when porting x86 code to ARM64.

### N=64 contention

SPSC is single-producer/single-consumer by definition. If V808.1 instantiates 64 SPSC rings (one per thread pair), the padding is per-ring and the analysis holds. If it instantiates *one* ring with 64 producers, the `head` store is a contended RMW and the `release` semantics are insufficient — you need `fetch_add(acq_rel)` and a per-slot `ready` flag, which is no longer SPSC. **Verify which topology V808.1 actually uses.** The naming suggests SPSC, but N=64 in the prompt implies either 64 rings or a mislabeled MPSC.

### Cache-line ping-pong

Even with correct padding, the `head` line bounces between producer and consumer cores on every item. At 64 threads this is the dominant cost. The standard mitigation is batching: producer publishes every K items, consumer reads `head` once per batch. If V808.1 does not batch, the padding is cosmetic — the line still ping-pongs, just without false sharing.

---

## 3. Exact barrier requirements (summary)

| Operation | x86 | ARM64 | C++ |
|---|---|---|---|
| Bank claim | `lock cmpxchg` | `casal` | `compare_exchange(acq_rel, acquire)` |
| Payload → seq publish | `mov` + `sfence` (if WC) | `dmb ish` or `stlr` | `release` store on seq |
| Seq → owner free | `mov` | `stlr` | `release` store on owner |
| Reader seq check | `mov` | `ldar` | `acquire` load |
| Reader re-check | `mov` | `ldar` | `acquire` load |
| SPSC head publish | `mov` | `stlr` | `release` store |
| SPSC tail publish | `mov` | `stlr` | `release` store |
| Cached tail/head | `mov` | `mov` | `relaxed` atomic (mandatory) |

---

## 4. Verdict

- **Bank rotation:** the `% 3` derivation from a shared counter is not a linearization point. Without a per-bank `owner` CAS, this is a race under N=64. **Blocking.**
- **Commit ordering:** if `seq` is `relaxed`, ARM64 breaks. **Blocking on ARM64.**
- **128B padding:** necessary but not sufficient. Adjacent-line prefetcher on Intel defeats it; cached indices must be atomic. **Non-blocking but incorrect as stated.**
- **SPSC topology:** confirm 64 rings vs 1 MPSC. If MPSC, the entire SPSC analysis is void. **Blocking pending clarification.**

No proof of correctness is claimed for any of the above — these are hazard identifications, not verifications. The `% 3` aliasing and the `relaxed` seq store are the two items I would not ship.