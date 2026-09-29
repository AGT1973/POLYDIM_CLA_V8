# QWEN REASONING ARCHITECTURE

We need answer user's request: line-by-line audit of all 2416 lines production code, for each function/method report bugs severity, line numbers, root cause, fix. They provided source code in prompt. Need produce compressed MD, no tutorials, no graphs, implementable fixes. Need be mathematically rigorous, zero tolerance, no hallucinate proofs. If no bugs state NO BUGS FOUND after 3-pass review. Need execute 5 passes conceptually. Need likely identify many bugs. Need be careful: We don't have actual line numbers? The source is pasted without line numbers. User says 2416 lines but we can approximate line ranges? Need report function name and line range. We can assign line ranges based on provided code? We need maybe use file sections and approximate line numbers. But they demand specific line numbers affected. We can state line numbers relative to provided source? We can count? We need produce credible audit. Need maybe not literally count all 2416 lines but can use function names and approximate ranges. But user expects line-by-line. We need be thorough. Need maybe include note: line numbers are 1-based within each file as pasted; if your build differs, map by function. But they asked no tutorials. Could include mapping. Need maybe count lines? We can manually approximate? Could use analysis to count? We can maybe not exact but enough. Need be rigorous. Let's inspect code deeply.

We need audit all functions/methods in files:
Header: macros, structs, static_asserts. Functions? None except static_assert. But need maybe audit structs? User says each function/method. But also bugs in header. We can include header items.

kernel_cpp_v813.cpp functions:
- polydim_abi_probe
- polydim_set_fp_mode
- polydim_get_fp_mode
- knuth_two_sum
- twosum_tree_reduce_inplace
- polydim_stream_copy_nt
- polydim_alloc_aligned
- polydim_free_aligned
- polydim_handle_create
- polydim_handle_retain
- polydim_handle_release
- polydim_spsc_init
- polydim_spsc_push
- polydim_spsc_pop
- polydim_spsc_destroy
- polydim_gram_dsyrk
- tiled_dsyrk_fixed
- solve_linear_system_general
- frobenius_diff
- compute_VtZ
- project_to_tangent_space
- polar_newton_refinement
- apply_shifted_cholqr2
- retract_cayley_smw_mixed
- polydim_stiefel_optimize
- fwht_normalized_inplace
- polydim_structured_lsm_step

kernel_rust_v813.rs:
- set_last_error
- polydim_last_error_v1
- polydim_get_last_error_v2
- polydim_reset_engine_state
- DisjointSet::new/find/union
- polydim_rust_betti_dual_guard
- polydim_rust_frechet_betti_filter
- polydim_rust_quantum_synthesize_discrete
- polydim_rust_quantum_quantize_clifford_grid
- polydim_rust_quantum_synthesize_rz_ross_selinger
- ffi_guard macro maybe.

pmtp_rcu_v813.cpp:
- pmtp_now_ns
- pmtp_banked_slot_init
- pmtp_is_process_alive
- pmtp_get_bank
- pmtp_reap_orphaned_leases
- pmtp_banked_slot_acquire_reader
- pmtp_banked_slot_release_reader
- pmtp_writer_lock
- pmtp_banked_slot_acquire_writer
- pmtp_banked_slot_commit_writer

ipc_futex_v813.cpp:
- get_waiter_count_ptr
- format_event_name
- cached_open_site_event
- flush_handle_cache
- _TlsHandleCacheGuard ctor/dtor
- get_valid_shared_header
- pmtp_futex_shared_init
- polydim_futex_wait_v813
- polydim_futex_wake_v813

Dart:
- PolydimHandle struct
- PolydimEdge
- PolydimBettiResult
- PolydimFrechetBettiResult
- GaussianSplatPoint3D
- PolydimV813 constructor
- projectLatentTo3DGS

Need identify bugs. Let's systematically analyze.

General issues:
- ABI header: PmtpReaderLease size? Let's compute: uint32 state (4), pid (4), uint64 process_start_time_ns (8) offset 8, uint64 generation offset 16, uint32 epoch offset 24, uint32 pad offset 28, total 32. OK.
PmtpBankedSlotHeader: offsets: global_epoch 0, active_bank 4, writer_active 8, owner_pid 12, sequence 16, owner_start_time_ns 24, num_reclaimed_orphans 32, prev_bank 36, writer_heartbeat_ns 40, header_padding[80] 48..128, leases_bank0 at 128. OK. But writer_active and owner_pid are separate 32-bit fields. In pmtp_writer_lock they reinterpret_cast std::atomic<uint64_t>* to &header->writer_active and CAS 64-bit over writer_active + owner_pid. Is that valid? writer_active at offset 8, owner_pid at offset 12, 8-byte aligned? offset 8 yes. But struct has no atomicity guarantee; concurrent readers may read owner_pid? They don't. But writer_active and owner_pid are non-atomic in header; using atomic reinterpret_cast on non-atomic object is technically UB in C++ if object not atomic? Strict aliasing? reinterpret_cast to atomic<uint64_t>* and access via atomic operations on object that is not atomic? In C++11, atomic operations on non-atomic object via reinterpret_cast is UB? Actually std::atomic<T> is not trivially copyable? But common practice. Need flag HIGH/LETHAL? For production, use std::atomic<uint64_t> in header or memory_order. Also PmtpBankedSlotHeader is in shared memory; C++ object model. But maybe acceptable? Need mention.
- PmtpBankedSlotHeader has writer_active uint32 and owner_pid uint32. pmtp_writer_lock desired = (pid << 32) | 1. If pid is 0? desired = 1. expected = 0. OK. But if pid > 0xFFFFFFFF? uint32. OK. But owner_pid field is 32 bits. If pid 0? writer lock with pid 0? desired low bit 1, high 0. Then dead check opid=0, dead false. OK. But process alive pid 0 false.
- pmtp_writer_lock: after CAS fail, expected is current 64-bit. It reads header->owner_start_time_ns non-atomic? It uses uint64_t ostart = header->owner_start_time_ns; not atomic. Could tear? 64-bit on 32-bit? But likely 64-bit. But no atomic. Also compare ostart == header->owner_start_time_ns after process alive check; but owner_start_time_ns may be updated by new writer? Race. If dead writer, CAS expected to desired. But expected includes old owner_pid and writer_active=1. If another writer already took it, CAS fails. OK. But if dead writer's owner_start_time_ns changed? It shouldn't unless new writer. But no atomic.
- pmtp_writer_lock uses goto owned; after CAS success, stores owner_start_time_ns and heartbeat. But writer_active 64-bit now contains pid and 1. owner_pid field is high 32 bits. OK. But commit_writer stores writer_active 0, but owner_pid remains? Since 64-bit store 0 clears both. OK.
- pmtp_banked_slot_acquire_writer: wbank = (3*2 - cur - prv) % 3 = (6 - cur - prv) % 3. If cur != prv, this gives third bank. If cur==prv? Could happen? init active=0 prev=2. commit sets prev=cur active=write_bank. If write_bank equals prev? It should not. But if bug, cur==prv then wbank = (6 - 2cur)%3 = (-2cur)%3? In C++ negative modulo negative? cur uint, 6 - cur - prv underflows if cur+prv >6? uint32. If cur=2,prv=2 => 6-4=2, wbank=2 equals cur/prv, then returns ABI_MISMATCH. OK. But if cur+prv >6? e.g. cur=2,prv=1 => 3; cur=1,prv=2 =>3; cur=0,prv=1=>5; cur=1,prv=0=>5; cur=0,prv=2=>4; cur=2,prv=0=>4. All <=6 except if invalid >2. If invalid active_bank >2, underflow. But should validate. Need flag: no validation of cur/prv < PMTP_NUM_RCU_SLOTS before arithmetic. If corrupted, underflow and wrong bank. HIGH.
- Drain: deadline = pmtp_now_ns() + PMTP_DRAIN_POLL_MAX_NS * 1000; PMTP_DRAIN_POLL_MAX_NS = 1,000,000 ns (1 ms). *1000 = 1,000,000,000 ns = 1s. OK. But no overflow check. pmtp_now_ns near UINT64_MAX could overflow. LOW.
- In drain loop: if busy, calls pmtp_reap_orphaned_leases(header, wbank, backoff, &n). But pmtp_reap_orphaned_leases checks target_bank != active and != prev. wbank is neither. OK. It uses timeout_ns as deadline? It sets deadline = now + timeout_ns. But called with backoff (50us to 1ms). It will break after deadline. OK. But it only reaps leases whose process dead. If live reader remains, drain timeout. OK.
- After drain, recycle leases: for each state != FREE, CAS to FREE. This can reclaim CLOSED/RECLAIMED. But what if a reader concurrently acquires a slot in wbank? Writer holds writer lock, but readers can acquire any bank? Reader acquire reads active_bank only. wbank is not active or prev, so readers should not acquire it. But if active_bank changes? Writer holds lock, no other writer. Readers only active. So safe. But if a reader had acquired wbank before it became prev? Wait wbank is not active nor prev at acquire_writer. It may have old leases from two commits ago. Readers should have released or been drained. OK.
- But release_reader: stores CLOSED without checking state. If slot was RECLAIMED by orphan reaper, release will set CLOSED, making it not FREE. Later writer recycle will CAS to FREE. OK. But if release after slot recycled to FREE and new reader acquired? Could happen if reader lost lease? Reader should release only its slot. If orphan reaper reclaimed dead process, no live release. If live process delayed release after writer recycled and new reader acquired same slot, release will overwrite new ACTIVE to CLOSED, causing lost lease. Is that possible? A live reader acquires bank B, then writer cannot write B until B is not active/prev and drained. If reader remains active, drain won't complete. If reader releases, state CLOSED. Writer can recycle to FREE. Later new reader acquires. Old reader cannot release again. But if old reader double-releases, it could close new lease. API doesn't prevent double release. Need flag MEDIUM: release_reader lacks state validation / generation check. Could corrupt lease. Also release doesn't clear pid etc.
- acquire_reader: It CAS state from cur (FREE/CLOSED/RECLAIMED) to ACTIVE. Then writes pid, start_time, epoch, generation. Then fence release. Then checks if active_bank changed; if changed, stores CLOSED and break. But there is a race: It acquires slot in bank B. If active_bank rotates from B to new bank after our CAS, we close. But what if active_bank rotates before our CAS? We read bank at top. If active_bank changes after read but before CAS, we may acquire in old bank that is no longer active. Then after CAS, check active_bank != bank and close. OK. But what if active_bank changes to another bank and then back to bank before check? Then we think OK but readers may read stale? Bank B was active, then not active, then active again? With 3 banks, commit sequence: active 0 prev 2 write 1 commit active 1 prev 0; next write 2 commit active 2 prev 1; next write 0 commit active 0 prev 2. Bank 0 can become active again after 3 commits. If reader acquired bank 0 during first active, then active changed to 1, then 2, then 0 before check? Check only immediate after CAS, not enough. But reader should read only active_bank at acquire time. If it acquired old bank and active later returns, it may read stale data? The protocol says readers read active_bank (published). But acquire_reader returns acquired_bank; caller likely uses that bank. If active_bank changed after acquire, they close. But if it changes away and back before check, they keep lease on bank that is active again but data may be new? Actually if bank 0 became active again, data in bank 0 was rewritten by writer after drain. But our lease was acquired before rewrite? Wait writer cannot rewrite bank 0 while it is active or prev. Sequence: bank0 active. Reader acquires bank0. Writer wants write bank1 (not active/prev). commit active1 prev0. Now bank0 is prev, not writable. Next writer write bank2, commit active2 prev1. Now bank0 is neither active nor prev, writer can drain and rewrite bank0. If our reader still holds lease on bank0, drain will see ACTIVE and not proceed unless dead. So writer cannot rewrite while live reader holds. If reader's process alive, drain timeout. If reader's process dead, reaper reclaims. If reader releases, CLOSED. So bank0 won't be rewritten while lease active. If active_bank returns to 0, it's after writer rewrote bank0 and committed; but our old lease would have had to be released/reclaimed before rewrite. So no live old lease. The check after CAS only handles rotation before writer drain? But if active_bank changes away and back before check, that would require two commits, which cannot happen while our lease active in bank0? Writer cannot commit bank0 rewrite until drain, which blocked by our active lease. But could active_bank change away from bank0 (commit bank1) while our lease active; then active_bank cannot return to bank0 until bank0 drained, blocked. So check immediate is enough? If active_bank changes away, it won't return before our check unless our lease reclaimed (dead) or released. If process dead, reaper can reclaim, but our thread still running? If process dead no. OK.
- But acquire_reader writes lease fields after CAS without atomic. Other readers may see state ACTIVE but pid/generation uninitialized? They don't read those except reaper reads pid after state ACTIVE. Reaper loads state acquire, then reads pid. Writer/reaper may read pid before writer thread writes it? In acquire_reader, CAS state to ACTIVE with acq_rel, then writes pid. There is no release after writing pid before making it visible? It does std::atomic_thread_fence(release) after writes, but state was already stored ACTIVE before writes. Reaper loads state acquire, sees ACTIVE, then reads pid non-atomic. The release fence after writes does not order the prior state store? Actually state store (CAS) happened before writes; release fence after writes does not make earlier state store release? For other thread to see pid, the writer must perform release after writes and the reader must acquire after seeing state. But state was set before writes, so reader can see state ACTIVE before pid written. This is a data race / visibility bug. Need set state to ACTIVE after writing metadata, or use a separate state value (e.g. CAS to ACTIVE after metadata with release). But CAS needs state transition. Could write metadata then CAS to ACTIVE with release. But need avoid ABA? Use state. Current: CAS to ACTIVE, then write pid, then fence release. The fence release after writes can make writes visible to subsequent acquire, but the synchronization edge is from state store? The state store is before writes, so no. In C++ memory model, a release fence orders preceding writes with subsequent release operations, but the state store is a release? CAS acq_rel includes release, but it occurs before writes, so it releases only preceding writes, not later. The later release fence has no corresponding acquire that saw the state store? If reader loads state acquire and sees ACTIVE, it synchronizes with the release sequence that made state ACTIVE. That release sequence is the CAS, which happened before pid writes. So pid writes not synchronized. LETHAL/HIGH. Fix: write pid/start/epoch/generation before CAS to ACTIVE, or use two-phase: CAS to ACTIVE_PENDING? But state only 4 values. Could store metadata in slot when FREE? But slot may be reused. Better: after CAS to ACTIVE, write metadata, then store state to ACTIVE? Can't because already ACTIVE. Could use state=PMTP_LEASE_CLOSED? No. Use a separate atomic flag? Or use CAS to ACTIVE with release after writing by first CAS to a temporary state? Could use state=PMTP_LEASE_RECLAIMED? Not safe. Simpler: use a 64-bit atomic lease token? Or set state to ACTIVE only after metadata by using CAS from cur to ACTIVE but with metadata written before CAS. But metadata may be overwritten while slot FREE; that's okay if no one reads until state ACTIVE. So: leases[i].pid=...; leases[i].process_start_time_ns=...; leases[i].epoch=...; leases[i].generation=...; then CAS state cur->ACTIVE with release. But if CAS fails, metadata written but state not ACTIVE; harmless. Need ensure no data race on metadata while state not ACTIVE? Other threads may write metadata for their own CAS attempts concurrently? Multiple readers may write same slot metadata before CAS; data race on non-atomic fields. But if state is not ACTIVE, they may concurrently write. That's a data race. Need avoid by using atomic store of metadata or a lock. Could pack metadata into atomic 64? Or use state=ACTIVE after CAS and accept? Hmm.
Alternative: Use a per-slot atomic uint64_t token: state in low bits, pid/generation? But ABI fixed. Could use seqlock? For audit, propose fix: make lease metadata atomic or use a per-slot mutex? But zero-copy. Maybe use state transition to ACTIVE only after writing, and protect metadata writes with a per-slot atomic CAS on a hidden field? Since ABI has pad. Could use pad as atomic uint32_t write_lock? But not enough.
Maybe simpler: Use a two-state protocol: state FREE -> CAS to CLOSED? No.
Could use state=PMTP_LEASE_ACTIVE as "reserved" and metadata written before? Data race on metadata among contenders. But if only one succeeds, others may write concurrently. To avoid, use a per-slot atomic uint32_t claim token in pad? PmtpReaderLease has pad uint32_t. Could use pad as atomic claim: CAS pad from 0 to 1, write metadata, then CAS state to ACTIVE, then pad=0. But pad currently for alignment; can use. But ABI? It's in struct. Need fix.
But maybe in practice, reaper only reads pid after state ACTIVE; if metadata not visible, could read garbage and kill wrong process? It checks process alive; if garbage pid maybe alive, then won't reclaim; if dead, could reclaim active lease. LETHAL.
- acquire_reader: after CAS success, if active_bank changed, st->store(CLOSED) and break. But it doesn't clear metadata. OK. But if active_bank changed, it breaks out of slot loop and then attempts yield and retry. It returns NO_FREE_SLOT after 16 attempts. OK.
- It doesn't validate pid/start_time. OK.
- release_reader: no check that state ACTIVE or that caller owns slot. Could release CLOSED/RECLAIMED. MEDIUM.
- pmtp_reap_orphaned_leases: reads leases[i].pid non-atomic after state ACTIVE. Same visibility issue. Also process_start_time_ns not used! It only checks pid alive, not start_time. PID recycling: if old dead pid reused by new process, kill(pid,0) alive, so won't reclaim. But if new process has same pid but different start_time, should reclaim? It doesn't compare start_time. The header has process_start_time_ns for anti PID recycling but unused. HIGH. Also on Windows, process start time not checked. Need fix: compare leases[i].process_start_time_ns with current process start time? But cross-process getting start time is OS-specific. At least use it: if pid alive but start_time mismatch, treat dead? Need OS API. For POSIX, /proc/[pid]/stat start_time. For Windows, GetProcessTimes? Need propose.
- pmtp_reap_orphaned_leases: timeout_ns used as deadline, but if timeout_ns=0, deadline=now, loop checks now > deadline? It does if (pmtp_now_ns() > deadline) break; if equal, may process one. OK.
- It increments num_reclaimed_orphans only on successful CAS. OK.
- pmtp_banked_slot_init: zeroes header byte-by-byte volatile, then stores active_bank=0 prev=2. But if header in shared memory and other processes may be reading? Should be called once before publish. OK. But zeroing entire header includes leases; if existing readers? Not safe. But init once.
- It doesn't set global_epoch/sequence? zero. OK.
- It doesn't set writer_heartbeat? zero.
- pmtp_is_process_alive: Windows OpenProcess with PROCESS_QUERY_LIMITED_INFORMATION. If access denied returns alive. OK. But if pid is current process? alive. If pid 0 false. POSIX kill(pid,0) can return EPERM for alive. OK. But if pid is zombie? kill returns 0? Zombie process still exists until reaped; kill(pid,0) returns 0. Could treat zombie as alive, preventing reclaim. Need maybe check /proc state. MEDIUM.
- pmtp_writer_lock: uses 64-bit CAS on writer_active/owner_pid. But header fields are uint32_t, not atomic. Also owner_pid is at offset 12, but 64-bit atomic at offset 8 spans writer_active (8-11) and owner_pid (12-15). OK. But other code reads header->owner_pid? Only writer_lock reads expected high bits. commit stores 0. OK.
- But pmtp_writer_lock dead check: uint64_t ostart = header->owner_start_time_ns; int dead = (opid != 0) && !pmtp_is_process_alive(opid); if (dead) { if (ostart == header->owner_start_time_ns) { CAS } } It reads owner_start_time_ns twice non-atomic. If owner_start_time_ns is updated by new writer between reads, condition may false. OK. But if dead writer and owner_start_time_ns unchanged, CAS. But what if expected changed due to another writer? CAS fails. OK.
- However, if writer process dies while holding lock, owner_start_time_ns remains. New writer can steal. But if dead writer's pid reused by live process, pmtp_is_process_alive returns true, so cannot steal. Need start_time check. HIGH.
- pmtp_banked_slot_acquire_writer: after lock, loads active/prev. But no validation active/prev < 3. If corrupted, wbank underflow. HIGH.
- It drains wbank. But it only checks leases in wbank. What about readers that acquired wbank when it was active, then active changed, but they haven't released? They are in wbank leases. Drain sees them. OK.
- It recycles all non-FREE to FREE after drain. But if a lease is ACTIVE due to a live reader that just acquired wbank? Readers only acquire active_bank. wbank not active. But what if active_bank is corrupted? no.
- commit_writer: no check that caller owns writer lock. Any process can call commit_writer and publish arbitrary write_bank, corrupting. It should verify writer_active contains its pid. HIGH/LETHAL. It also doesn't verify write_bank != active/prev? It only checks <3. If write_bank == active, then prev=active, active same, protocol broken. If write_bank == prev, prev=active, active=prev, two banks same, writer later wbank calculation may fail. Need fix: require writer lock and write_bank not active/prev. LETHAL.
- commit_writer: memory ordering: release fence, load active relaxed, store prev release, store active release. Readers load active acquire. OK. But sequence/epoch fetch_add after active store. Readers may see new active but old sequence? They load generation after acquiring lease, not during read. OK.
- It stores writer_heartbeat_ns=0 on commit. But writer lock dead check doesn't use heartbeat. OK.
- It stores writer_active=0 after epoch/sequence. If a new writer acquires lock between active store and writer_active store? It could, but commit not yet released lock. New writer could acquire and choose write_bank based on active/prev, maybe same as just committed? Let's see: commit sets active=write_bank, prev=old active, then fetch epoch/seq, then store writer_active=0. If new writer acquires after active/prev updated but before writer_active=0? It cannot because writer_active still 1. It will see busy, check owner pid alive (current process alive), cannot steal. OK. But if current process dies between active store and writer_active store? Then lock stuck? New writer can steal if pid dead. OK.
- But commit_writer doesn't clear owner_pid separately? 64-bit store 0 clears. OK.

IPC futex:
- get_waiter_count_ptr: returns pointer to uint32_t addr + 1, i.e. next 32-bit word. Assumes shared memory has at least 8 bytes and alignment. OK. But if addr is not 4-byte aligned? futex requires. Not checked.
- Windows handle cache: thread_local array. cached_open_site_event uses only guid_lo (first 8 bytes) as key, but event name uses first 8 bytes too? format_event_name uses site_guid[0..7] only. So site_guid high 8 bytes ignored. If two sites differ only high 8 bytes, same event name and cache key collision. But guid generation uses 16 bytes; event name only 8 bytes. HIGH. Also cache slot uses guid_lo, but if different guid_lo hash same slot, it closes existing handle and opens new; OK but if two different sites hash same slot, one handle evicted; not correctness but latency. But event name collision is correctness.
- format_event_name uses only 8 bytes, 16 hex chars. Could collide. Need use all 16.
- cached_open_site_event: OpenEventA then CreateEventA. If OpenEvent fails because event exists but access denied? It creates? CreateEventA with existing name returns handle to existing if exists, even if OpenEvent failed? If access denied, CreateEvent may also fail? OK. But if event was created by another process with no modify state? It requests EVENT_MODIFY_STATE|SYNCHRONIZE. OK.
- It caches handle in TLS. But if event object is closed by another thread? TLS per thread. OK.
- flush_handle_cache in TLS destructor. But thread_local guard destructor may run after other TLS? OK.
- get_valid_shared_header: checks page_offset < sizeof(header) return null. It assumes header is immediately before addr in same page. If addr is at page offset >=24. OK. But if addr not aligned to 4? no.
- pmtp_futex_shared_init: On Windows, if page_offset < header size return -1. It writes guid, sets addr+1=0, fence, magic. But no atomic CAS to prevent two processes initializing concurrently. If two processes call init simultaneously, both may see magic 0, generate different guids, write, last magic wins. Then events differ? Actually if both write different site_guid, one process may use its guid, other uses other; event names differ, wake lost. Need CAS on magic or use shared memory atomic. HIGH.
- It sets *const_cast<volatile uint32_t*>(addr + 1) = 0; This is waiter count. But if waiters already? init should be before. OK.
- polydim_futex_wait_v813: spin 4000 times checking *addr != expected. Then on Windows if hdr != null, uses event. It increments waiter count, then while *addr == expected_val: WaitForSingleObject(ev, timeout). If WAIT_OBJECT_0 continue. But auto-reset event: SetEvent by wake. If multiple waiters, wake_all loops SetEvent n times. But waiters may be in spin or not counted. Race: waiter increments wc after checking *addr? It increments before loop. Waker reads wc and sets event n times. If waiter increments after waker read, event may not be set. But waker also WakeByAddressAll? On Windows, it calls WakeByAddressAll/Single first, then event pulse. Waiters using event path only wait on event, not WaitOnAddress. If waker reads wc before waiter increments, no event. But waiter may have already passed spin and is about to WaitForSingleObject; if no event, it waits full timeout. Lost wakeup. Need atomic waiter count with proper protocol: increment, recheck value, if changed decrement; or use condition variable. LETHAL/HIGH.
- Also timeout handling: In event loop, timeout is used for each WaitForSingleObject, not total. If spurious wakeups, total wait can exceed timeout. MEDIUM.
- If WAIT_TIMEOUT, result=1 break. Then if *addr != expected result=0. OK.
- If event path, it doesn't use WaitOnAddress, so if value changes without event (e.g. waker failed to open event), it waits timeout. MEDIUM.
- Non-event path uses WaitOnAddress with timeout each loop; same total timeout issue.
- Linux futex wait: It spins 4000, then syscall FUTEX_WAIT with expected_val. But if value changed during spin, returns 0. If futex returns EAGAIN because value != expected, res !=0, then returns (*addr != expected)?0:1. OK. But timeout: uses relative timespec, not absolute. If spurious wake, it returns 1 even if value still expected and timeout not elapsed? Actually FUTEX_WAIT returns 0 if value changed, -EAGAIN if value != expected, -ETIMEDOUT if timeout. If spurious? futex can wake spuriously? It returns 0? The code treats any res==0 as success (value changed), else if *addr != expected 0 else 1. If spurious wake with value unchanged before timeout, returns 1 (timeout) incorrectly. Need loop until timeout absolute. HIGH.
- It doesn't handle EINTR. MEDIUM.
- polydim_futex_wake_v813: On Windows, WakeByAddressAll/Single then event pulse. But waiters in event path may not be woken by WakeByAddress. Event pulse as above. For wake_all, reads n = *wc, loops SetEvent n times. But auto-reset event: SetEvent sets state; if no waiter, event remains signaled? Auto-reset event: SetEvent makes signaled; if no waiter, it stays signaled until a waiter consumes. Multiple SetEvent on auto-reset event? If already signaled, SetEvent keeps signaled? Actually auto-reset event: SetEvent sets signaled; if multiple SetEvent, still one signal. Waiter consumes one. So looping SetEvent n times does not produce n signals; it just ensures signaled. For multiple waiters, only one will be woken per SetEvent if consumed immediately. But if no waiter consumes, extra SetEvent lost. Need manual-reset event or pulse with waiter count. LETHAL.
- Also SwitchToThread after SetEvent not enough.
- On Linux wake: FUTEX_WAKE. OK. But no check addr alignment.
- The futex value is volatile uint32_t; on Linux, futex requires 4-byte aligned. Not checked.
- pmtp_futex_shared_init on non-Windows returns 0 without initializing header. Then wait on Linux doesn't need header. OK. But on Windows, if addr page offset < header size, cannot use event; wait falls back WaitOnAddress. OK.

Dart:
- Struct definitions: Need check ABI alignment/size.
PolydimHandle: Pointer<Void> (8), @Size() int bytes (8), @Int32() refcount (4), @Uint32() flags (4), @Uint64() allocationId (8). Total 32? C struct: void* 8, size_t 8, int32 4, uint32 4, uint64 8 => 32. Dart: Pointer 8, Size 8, Int32 4, Uint32 4, Uint64 8 => 32. OK.
PolydimEdge: 8.
PolydimBettiResult: C: i32 4, u32 4, i64 8 (offset 8), u32 16, u32 20, u8 24, u8 25, pad 102 => 128? Let's compute: status 0-3, components 4-7, cycles 8-15, num_vertices 16-19, num_edges 20-23, is_crit 24, is_opt 25, pad 26..127 = 102. Total 128. Dart: Int32 4, Uint32 4, Int64 8, Uint32 4, Uint32 4, Uint8 1, Uint8 1, Array(102) 102 => 128. Alignment? Int64 requires 8; after two 4s offset 8 OK. Dart struct alignment likely 8. OK.
PolydimFrechetBettiResult: C: status 0, num_candidates 4, dimension 8? Wait C struct:
pub struct PolydimFrechetBettiResult {
    pub status: i32,
    pub num_candidates: u32,
    pub dimension: u32,
    pub connected_components_betti0: u32,
    pub cycles_betti1: i64,
    pub consensus_node_idx: u32,
    pub active_swarm_count: u32,
    pub rejected_outliers_count: u32,
    pub frechet_residual: f64,
    pub is_consensus_certified: u8,
    pub pad: [u8; 79],
}
Offsets: status 0, num_candidates 4, dimension 8, connected 12, cycles i64 requires 8 alignment -> offset 16? Let's compute: after connected at 12-15, next i64 at 16-23, consensus 24, active 28, rejected 32, frechet_residual f64 requires 8 -> offset 40? Wait rejected 32-35, next f64 at 40? There is 4 bytes padding after rejected? Let's layout: 0 status, 4 num_candidates, 8 dimension, 12 connected, 16 cycles (8), 24 consensus, 28 active, 32 rejected, 36? f64 align 8 => offset 40, 40-47 residual, 48 is_consensus, pad 79 => 49..127? 48+1+79=128. Yes total 128. Dart struct: Int32, Uint32, Uint32, Uint32, Int64, Uint32, Uint32, Uint32, Double, Uint8, Array(79). Dart will insert padding for Int64 and Double. Should match 128. OK.
GaussianSplatPoint3D: @Float() external double? In Dart ffi, @Float() is 32-bit float, but type double? Actually in Dart, external double with @Float() is allowed? It represents 32-bit float? I think @Float() external double is 32-bit float stored as double? In Dart FFI, @Float() is 32-bit float, but Dart double is 64-bit; it can be used with @Float() to represent 32-bit float? Yes. But C struct likely float? They didn't provide C struct. If C uses float, OK. If C uses double, mismatch. The name says 3D Gaussian, likely float. But @Float() external double may be okay. Need check size: 14 floats? pos 3, scale 3, rot 4, opacity 1, rgb 3 =14 floats =56 bytes. If C uses float. OK.
- PolydimV813 constructor: lookupFunction signatures.
_gramDsyrk: C++ polydim_gram_dsyr

---

