# RED TEAM ATTACK REPORT: PMTP_Control ABA & Cache Spillage

**Target**: `E:\POLYDIM_EINSOF\ENTREGA_2026_09_20_V765_VECTOR_B\src\polydim_kernel.cpp` (Lines 900+)

## 1. Critical ABA Vulnerability (32-bit Seqlock)
**Attack Vector:** The implementation uses `std::atomic<uint32_t>` for sequence tracking. A 32-bit counter is fatally vulnerable to wrapping under high-frequency lock-free IPC (the ABA problem).

**Execution:**
1. A reader thread calls `polydim_pmtp_acquire_read` and obtains `slot = 0` and `ticket = 42`.
2. The reader begins copying the tensor but is suspended (e.g., OS scheduler preemption, page fault, or SIGSTOP).
3. The writer thread continues at high speed. It increments `seq` by 2 for every write cycle (1 in begin, 1 in commit). To increment `seq[0]` by $2^{32}$, it takes $2^{31}$ writes to `slot 0`. 
4. Because the writer strictly rotates between 3 slots in `commit_write`, it takes exactly $3 \times 2^{31} \approx 6.44 \times 10^9$ total writes to wrap `seq[0]` back to `42`. At 100M operations/second, this takes only **~64 seconds**.
5. The reader resumes and finishes copying from `slot 0`.
6. The reader calls `polydim_pmtp_validate_read`. Since `c->seq[0].load() == 42`, the validation returns `POLYDIM_SUCCESS`.
7. **Result:** Silent corruption. The reader accepts a catastrophically torn tensor (half from state $T_0$, half from state $T_{+64s}$), violating the Gram-Schmidt invariants without tripping the zero-trust safeguards.

**Remediation:** Elevate the sequence counters to `std::atomic<uint64_t>`. A 64-bit sequence would take over 8,000 years to wrap at 10ns per write.

## 2. Bonus Finding: Cache-Line Math Error & False Sharing
**Attack Vector:** The explicit padding calculation is mathematically flawed because it neglects compiler-injected alignment padding.

**Execution:**
```cpp
char _pad[64 - sizeof(std::atomic<uint8_t>) - 3*sizeof(std::atomic<uint32_t>)]; 
```
This formula evaluates to `64 - 1 - 12 = 51`. 
However, C++ alignment rules require `seq[3]` (a 4-byte type) to sit on a 4-byte boundary. The compiler injects 3 bytes of implicit padding right after `state`. 
Actual layout: `state(1) + pad(3) + seq(12) + _pad(51) = 67 bytes`. The compiler then rounds the struct size up to the nearest multiple of 4, yielding `sizeof(PMTP_Control) == 68 bytes`.

**Result:** The struct exceeds the typical 64-byte L1 cache line size. This causes cache-line spillage and severe **False Sharing** across adjacent PMTP controls in memory, effectively destroying the asymptotic throughput.

**Remediation:** Remove manual padding math. Group variables by alignment size and use C++17 `alignas`:
```cpp
struct alignas(64) PMTP_Control {
    std::atomic<uint64_t> seq[3]; // 24 bytes
    std::atomic<uint8_t> state;   // 1 byte
    // Compiler automatically pads the rest of the 64 bytes
};
```
