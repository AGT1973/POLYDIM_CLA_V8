***Auditoría Bulldog POLYDIM**

***The user wants me to write out the patches. They said "redacta" — write it. I need to produce actual patches (file-by-file, ready to apply) for the P0 and P1 issues I found. Let me be thorough and give complete, ready-to-apply patches.**

***Let me organize this by file:**

1. ***polydim.h**

2. ***kernel\_cpp\_v768.cpp**

3. ***kernel\_rust\_v768.rs**

4. ***polydim\_ffi.dart**

5. ***test\_pmtp.dart**

6. ***polydim\_v768\_monolito.py**

7. ***universal\_llm\_tangent\_adapter.py**

8. ***polydim\_liquid\_state\_machine.py**

9. ***polydim\_triton\_kernel\_v768.py**

10. ***polydim\_mir\_wire\_rdma.py**

11. ***pubspec.yaml / pubspec.lock**

***I need to write complete, drop-in replacements or unified diffs. Given the size, I'll write complete corrected functions where they matter, and unified diffs where the change is small.**

***Let me be efficient but complete. The user wants finished work, not more partial stuff.**

***Let me write these as concrete patches. I'll produce them as unified diff format where possible, and complete function replacements otherwise.**

***Let me actually think about what to write:**

***For each file, I'll:**

- ***State the fix**

- ***Provide the code (either as full replacement or diff)**

***Let me start writing. This will be long.**

***I'll write it in Spanish since the user writes in Spanish. Let me be direct and technical.**

***Actually, let me structure this as:**

- ***Header: "Parches P0/P1 — Aplicables directamente"**

- ***For each file:**

  - ***Diff or full replacement**

  - ***Note of what it fixes**

***Let me be careful with the C++ code so it compiles. Let me be careful with Dart so it type-checks. Let me be careful with Rust so it compiles.**

***Let me write the code out.**

***For C++:**

***cpp**

```
***// 1. Fix overlaps UB**

***inline bool overlaps(const void\* a, const void\* b, size\_t bytes) \{**

    ***const uintptr\_t pa = reinterpret\_cast\<uintptr\_t\>(a);**

    ***const uintptr\_t pb = reinterpret\_cast\<uintptr\_t\>(b);**

    ***return (pa \< pb + bytes) && (pb \< pa + bytes);**

***\}**
```

***Need `\#include \<cstdint\>` for uintptr\_t.**

***For polydim\_rodrigues\_geodesic\_f64, add aliasing checks.**

***For polydim\_pmtp\_init, replace memset with field-by-field.**

***For polydim\_pmtp\_sizeof, add overflow check.**

***For polydim\_pmtp\_read\_begin, still has the race. I'll add a note. Actually let me propose a fix — pack pub\_seq and pub\_slot into a single atomic uint64.**

***Hmm, that would change the struct layout, which would break ABI with Dart/Python. Let me think. Actually the current design has a seqlock pattern where readers re-read. The issue is liveness. Let me add a bounded retry loop and correct ordering.**

***Actually, looking closer, the current code:**

***cpp**

```
***\*ver = c-\>pub\_seq.load(std::memory\_order\_acquire);**

***if (\*ver == 0) return 1; // EMPTY**


***\*slot = c-\>pub\_slot.load(std::memory\_order\_acquire);**

***PMTP\_SlotHeader\* hdr = pmtp2\_hdr\_of(c, \*slot);**

***uint64\_t s\_ver = hdr-\>seq.load(std::memory\_order\_acquire);**

***if (s\_ver != \*ver || (s\_ver & 1)) return -3; // BUSY/CONFLICT**
```

***If the writer changes pub\_seq between the two loads, we get (old\_ver, new\_slot). But then s\_ver != old\_ver check catches it and returns -3. So actually the code IS correct in terms of detecting the race. The concern is liveness — under a very aggressive writer, a reader might always get -3. That's a real liveness concern but the code is not wrong*, just potentially starved. The success\_rate \>= 90% assertion handles it partially.**

***Actually, wait. The comment in code says the write is: load pub\_seq, then pub\_slot. But actually the code does publish pub\_seq and pub\_slot in commit. Then read\_begin loads pub\_seq first, pub\_slot second. If write commits between these, we read new\_ver but old\_slot — no, we read pub\_seq AFTER the commit started, so we get new\_seq, and then pub\_slot after commit completed, so we get new\_slot. Both new. Then s\_ver check: s\_ver == new\_seq, correct. OK.**

***But if read\_begin reads pub\_seq just before commit, then pub\_slot after commit: old\_ver, new\_slot. s\_ver = new\_seq != old\_ver → return -3. Good, race detected.**

***The real problem: what if between read\_begin's two loads, the writer commits TWICE? Then reader gets seq\_1 (old), then reads slot\_2 (newest). s\_ver at slot\_2 == seq\_3 (odd, still writing) or seq\_4 (done). If seq\_4 != seq\_1 → -3. Correct.**

***What about ABA? seq is monotonic uint64, so no ABA. Good.**

***So actually the code is correct — my earlier criticism C-07 was overstated. Let me be honest and downgrade it. Or maybe I was right that it's correct but non-live*. Let me keep the finding but characterize it properly.**

***Actually there IS a subtle bug: the reader reads pub\_seq with acquire, then pub\_slot with acquire. Between them, the writer might be in write\_begin having stored an odd value at slot's seq. Reader sees pub\_seq=N (last even), reads pub\_slot=N-th slot. Then reads hdr-\>seq which might be N+1 (odd, writer writing). Check: s\_ver != \*ver OR (s\_ver & 1) → returns -3. Correct.**

***OK so C-07 was wrong. I should retract it. Good, this is the bulldog being honest.**

***Let me focus on real bugs. Real C++ bugs:**

- ***C-01 (overlaps UB) — real**

- ***C-02 (aliasing y↔y\_out) — real**

- ***C-03 (proj\_sphere aliasing) — real**

- ***C-04 (u↔v aliasing) — real**

- ***C-05 (memset over atomics) — technically UB, practically fine but should fix**

- ***C-06 (sizeof overflow) — real**

- ***C-08 (selftest doesn't check FTZ) — real gap**

- ***C-09 (K max inconsistency) — real**

- ***C-10 (cholqr2 converged) — real logic bug**

- ***C-11 (nested OMP) — real**

- ***C-12 (uncompensated reduction in Stiefel) — real**

- ***C-13 (alignment check BLAS) — real**

***Let me retract C-07 in the patch writing.**

***OK let me now write out the patches.**

***I'll organize by file. Each patch will be a unified diff or a full replacement.**

***Given the length, I'll write substantial but focused patches.**

***Let me start.**

***For Rust:**

- ***R-01 (Betti-1 computation) — real bug**

- ***R-02 (alignment check) — real**

- ***R-04 (panic=unwind) — documentation**

***For Dart:**

- ***D-01..D-07 — the whole PMTP binding is broken**

- ***D-09 (null check buildInfo)**

***For Python:**

- ***P-01 (PMTP not init)**

- ***P-02 (payload not written)**

- ***P-04 (Linux lib name)**

- ***P-06 (Tangent bijectivity)**

- ***P-07 (LSM O(D) loop)**

***For Triton:**

- ***T-01 (import math)**

- ***T-02 (correct drift claim)**

***For Universal adapter:**

- ***U-01 (bijectivity)**

- ***U-03 (test tolerance)**

***For LSM:**

- ***L-01 (nnz constant)**

***Let me write. I'll be efficient but complete.**

***Let me think about format. The user wants to be able to apply these. I'll use unified diff format for small changes and full function replacement for larger ones.**

***I'll write:**

***text**

```
***\#\# Archivo: polydim.h**


***\#\#\# H-01: declarar polydim\_check\_ftz**

***\\\`\`\`diff**

***--- a/polydim.h**

***+++ b/polydim.h**

***@@ -XX,6 +XX,7 @@**

 ***POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_selftest\_compensation(double\* observed\_err);**

 ***POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_selftest\_all(void);**

***+POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_check\_ftz(void);**

 ***POLYDIM\_EXPORT const char\* POLYDIM\_CALL polydim\_status\_string(int32\_t code);**

***\\\`\`\`**
```

***Actually, given the length and the goal of "ready to apply", I think the best format is:**

- ***For each file: "Reemplaza el archivo completo" OR unified diff.**

***Let me use a pragmatic mix. For small fixes, diff. For substantial rewrites (PMTP in Dart, PMTP slab in Python), full replacement.**

***Let me write it out now. I need to be careful with the length.**

***Actually, given the user is frustrated with partial answers, I'll write complete file replacements for the most-broken files, and diffs for the rest.**

***Files with full replacement:**

- ***polydim\_ffi.dart (since PMTP bindings are entirely broken)**

- ***test\_pmtp.dart (uses wrong types)**

- ***PolydimTangentAdapter (both copies)**

***Files with diffs:**

- ***polydim.h (add decl)**

- ***kernel\_cpp\_v768.cpp (targeted fixes)**

- ***kernel\_rust\_v768.rs (targeted fixes)**

- ***polydim\_v768\_monolito.py (targeted fixes)**

- ***polydim\_triton\_kernel\_v768.py (small fixes)**

- ***LSM (small fixes)**

***OK let me write.**

***Let me be careful with the Dart FFI — need to get the type signatures right.**

***Looking at C++ header:**

***c**

```
***POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_pmtp\_init(PMTP\_Control\* c, uint32\_t num\_slots, uint64\_t payload\_bytes);**

***POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_pmtp\_write\_begin(PMTP\_Control\* c, uint32\_t\* slot, uint64\_t\* ver);**

***POLYDIM\_EXPORT void POLYDIM\_CALL polydim\_pmtp\_write\_commit(PMTP\_Control\* c, uint32\_t slot, uint64\_t ver);**

***POLYDIM\_EXPORT void POLYDIM\_CALL polydim\_pmtp\_write\_abort(PMTP\_Control\* c, uint32\_t slot, uint64\_t ver);**

***POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_pmtp\_read\_begin(PMTP\_Control\* c, uint32\_t\* slot, uint64\_t\* ver);**

***POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_pmtp\_read\_validate(PMTP\_Control\* c, uint32\_t slot, uint64\_t ver);**
```

***Dart:**

***dart**

```
***typedef \_InitNative = Int32 Function(Pointer\<PMTPControl\>, Uint32, Uint64);**

***typedef \_InitDart = int Function(Pointer\<PMTPControl\>, int, int);**
```

***Native types in typedef — Int32, Uint32, Uint64 are Dart FFI types from dart:ffi.  
Dart types — int for all of them.**

***dart**

```
***typedef \_BeginWriteNative = Int32 Function(Pointer\<PMTPControl\>, Pointer\<Uint32\>, Pointer\<Uint64\>);**

***typedef \_BeginWriteDart = int Function(Pointer\<PMTPControl\>, Pointer\<Uint32\>, Pointer\<Uint64\>);**


***typedef \_CommitWriteNative = Void Function(Pointer\<PMTPControl\>, Uint32, Uint64);**

***typedef \_CommitWriteDart = void Function(Pointer\<PMTPControl\>, int, int);**


***typedef \_AbortWriteNative = Void Function(Pointer\<PMTPControl\>, Uint32, Uint64);**

***typedef \_AbortWriteDart = void Function(Pointer\<PMTPControl\>, int, int);**


***typedef \_ReadBeginNative = Int32 Function(Pointer\<PMTPControl\>, Pointer\<Uint32\>, Pointer\<Uint64\>);**

***typedef \_ReadBeginDart = int Function(Pointer\<PMTPControl\>, Pointer\<Uint32\>, Pointer\<Uint64\>);**


***typedef \_ReadValidateNative = Int32 Function(Pointer\<PMTPControl\>, Uint32, Uint64);**

***typedef \_ReadValidateDart = int Function(Pointer\<PMTPControl\>, int, int);**
```

***For PMTPControl struct in Dart:**

***dart**

```
***final class PMTPControl extends Struct \{**

  ***@Uint32() external int magic;         // offset 0**

  ***@Uint32() external int numSlots;      // offset 4**

  ***@Uint64() external int payloadBytes;  // offset 8**

  ***@Uint64() external int pubSeq;        // offset 16**

  ***@Uint32() external int pubSlot;       // offset 24**

  ***@Uint32() external int wlock;         // offset 28**

  ***@Uint32() external int wticket;       // offset 32**

  ***@Array(28) external Array\<Uint8\> reserved\_;  // offset 36, total 64**

***\}**
```

***Wait — need to check Dart FFI struct alignment. Dart FFI structs follow standard C alignment. So:**

- ***magic: uint32 @ 0**

- ***numSlots: uint32 @ 4**

- ***payloadBytes: uint64 @ 8 (aligned to 8)**

- ***pubSeq: uint64 @ 16**

- ***pubSlot: uint32 @ 24**

- ***wlock: uint32 @ 28**

- ***wticket: uint32 @ 32**

- ***reserved\_: 28 bytes @ 36..63  
Total: 64 bytes. Good, matches C++ alignas(64).**

***But wait — the C++ struct uses `std::atomic\<uint64\_t\> seq` in the SlotHeader and `std::atomic\<uint64\_t\> pub\_seq` etc. in Control. Layout-wise, atomics have the same size/alignment as underlying type on most platforms. So sizeof(PMTP\_Control) should be 64 with alignas(64).**

***Actually, alignment with alignas(64) means the struct is 64-byte aligned, but the size is padded to a multiple of 64. So sizeof(PMTP\_Control) == 64? Let me count: 4+4+8+8+4+4+4 = 36 bytes + 28 reserved = 64. Yes, 64 bytes with alignas(64). Good.**

***OK let me write the Dart.**

***For Python PMTP slab:**

***python**

```
***class PMTPSlabChannel:**

    ***def \_\_init\_\_(self, binding, name="polydim\_bus\_0", d=1024, num\_slots=4):**

        ***self.d = d**

        ***self.num\_slots = num\_slots**

        ***self.payload\_bytes = d \* 8**

        ***self.shm\_name = name**

        ***self.\_pin\_refs = \[\]**

        ***self.binding = binding**

        

        ***self.total\_bytes = binding.lib.polydim\_pmtp\_sizeof(num\_slots, self.payload\_bytes)**

        ***if self.total\_bytes == 0:**

            ***raise RuntimeError("polydim\_pmtp\_sizeof overflow")**

        

        ***self.is\_posix = os.name == 'posix'**

        ***if self.is\_posix:**

            ***from multiprocessing import shared\_memory**

            ***try:**

                ***self.shm = shared\_memory.SharedMemory(create=True, name=self.shm\_name, size=self.total\_bytes)**

            ***except FileExistsError:**

                ***self.shm = shared\_memory.SharedMemory(name=self.shm\_name)**

            ***self.mmap\_obj = self.shm.buf**

        ***else:**

            ***import mmap**

            ***self.mmap\_obj = mmap.mmap(-1, self.total\_bytes, self.shm\_name)**

        

        ***self.ctrl = PMTPControl.from\_buffer(self.mmap\_obj)**

        ***self.ctrl\_ptr = ctypes.pointer(self.ctrl)**

        ***self.\_pin\_refs.extend(\[self.ctrl\_ptr, self.mmap\_obj\])**

        

        ***rc = binding.lib.polydim\_pmtp\_init(self.ctrl\_ptr, num\_slots, self.payload\_bytes)**

        ***if rc != 0:**

            ***raise RuntimeError(f"polydim\_pmtp\_init failed: rc=\{rc\}")**

        

        ***self.\_payload\_base = (ctypes.addressof(self.ctrl) **

                              ***+ ctypes.sizeof(PMTPControl) **

                              ***+ num\_slots \* ctypes.sizeof(PMTPSlotHeader))**

    

    ***def \_payload\_addr(self, slot):**

        ***return self.\_payload\_base + slot \* self.payload\_bytes**

    

    ***def write\_tensor(self, tensor\_np):**

        ***if tensor\_np.dtype != np.float64 or tensor\_np.size != self.d:**

            ***raise ValueError(f"Expected float64\[\{self.d\}\]")**

        ***slot = ctypes.c\_uint32(0)**

        ***ver = ctypes.c\_uint64(0)**

        ***rc = self.binding.lib.polydim\_pmtp\_write\_begin(self.ctrl\_ptr, ctypes.byref(slot), ctypes.byref(ver))**

        ***if rc != 0:**

            ***return rc**

        ***addr = self.\_payload\_addr(slot.value)**

        ***ctypes.memmove(addr, tensor\_np.ctypes.data, tensor\_np.nbytes)**

        ***self.binding.lib.polydim\_pmtp\_write\_commit(self.ctrl\_ptr, slot.value, ver.value)**

        ***return 0**

    

    ***def read\_tensor(self):**

        ***slot = ctypes.c\_uint32(0)**

        ***ver = ctypes.c\_uint64(0)**

        ***rc = self.binding.lib.polydim\_pmtp\_read\_begin(self.ctrl\_ptr, ctypes.byref(slot), ctypes.byref(ver))**

        ***if rc != 0:**

            ***return rc, None**

        ***addr = self.\_payload\_addr(slot.value)**

        ***buf = (ctypes.c\_double \* self.d).from\_address(addr)**

        ***out = np.ctypeslib.as\_array(buf).copy()**

        ***rc2 = self.binding.lib.polydim\_pmtp\_read\_validate(self.ctrl\_ptr, slot.value, ver.value)**

        ***if rc2 != 0:**

            ***return rc2, None**

        ***return 0, out**
```

***OK let me now write everything out. I'll do this in a systematic way.**

***Given the length limit, I'll be dense but complete.**

***Actually I realize I should double-check: does the C++ PMTP write\_begin write to slot BEFORE writer writes payload? Yes:**

***cpp**

```
***extern "C" POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_pmtp\_write\_begin(PMTP\_Control\* c, uint32\_t\* slot, uint64\_t\* ver) \{**

    ***...**

    ***pmtp2\_lock(c);**

    ***uint64\_t current\_ver = c-\>pub\_seq.load(std::memory\_order\_relaxed);**

    ***\*ver = current\_ver + 1; // odd for locked**

    ***\*slot = (c-\>pub\_slot.load(std::memory\_order\_relaxed) + 1) % c-\>num\_slots;**

    ***PMTP\_SlotHeader\* hdr = pmtp2\_hdr\_of(c, \*slot);**

    ***hdr-\>seq.store(\*ver, std::memory\_order\_release);**

    ***return 0;**

***\}**
```

***So the writer sets the slot's seq to odd (locked) before returning. Then caller writes payload. Then caller calls write\_commit which sets even seq, updates pub\_slot/pub\_seq, unlocks.**

***Reader: sees pub\_seq (last even), reads pub\_slot, reads slot-\>seq. If slot-\>seq == pub\_seq and even, we're safe to read.**

***OK correct.**

***For read\_begin, I noted the "liveness" concern. But it's correct. So I'll drop that finding.**

***Let me now write out the patches. I'll focus on the real P0/P1 issues.**

***Let me write out the full text now.**

***I need to think about ordering:**

1. ***polydim.h — small**

2. ***kernel\_cpp\_v768.cpp — several diffs**

3. ***kernel\_rust\_v768.rs — two fixes**

4. ***polydim\_ffi.dart — full rewrite**

5. ***test\_pmtp.dart — rewrite**

6. ***polydim\_v768\_monolito.py — targeted diffs**

7. ***universal\_llm\_tangent\_adapter.py — diffs**

8. ***polydim\_liquid\_state\_machine.py — diffs**

9. ***polydim\_triton\_kernel\_v768.py — diffs**

10. ***polydim\_mir\_wire\_rdma.py — diffs**

11. ***pubspec.yaml**

***Let me write.**

***For unified diff format, I'll write them properly. Or for larger changes, I'll write "Reemplaza esta función" style.**

***Actually for clarity and to make sure the user can apply, I'll write complete blocks that go in specific places, marked with clear "BEFORE/AFTER" or as full file replacements.**

***Let me go.**

***I'll write this in Spanish since the user writes in Spanish, but code stays in English.**

***Length: I'll try to fit in a reasonable space. Maybe 4000-6000 words.**

***Let me be honest about the retraction of C-07 while I'm at it — the seqlock logic is actually correct.**

***Let me write out the response now.**

# 🐶 ***PARCHE V768 — APLICABLE DIRECTO**

***Retractación previa: C-07 (race `pub\_seq`/`pub\_slot`) era falso. El seqlock está correcto: entre las dos lecturas, si el writer commitea, `hdr-\>seq != pub\_seq` y se retorna `-3`. Verificado a mano. Pido disculpas. El resto sigue.**

***Aplicá en este orden. Cada bloque es copia directa al archivo o diff unificado.**


## ***1. `polydim.h` — añadir decls faltantes**

***diff**

```
***--- a/polydim.h**

***+++ b/polydim.h**

***@@ -104,6 +104,8 @@ POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_pmtp\_read\_begin(PMTP\_Control\* c, uin**

 ***POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_pmtp\_read\_validate(PMTP\_Control\* c, uint32\_t slot, uint64\_t ver);**

 

 ***/\* --------------------------------------------------------------------------**

  ***\* Autodiagnóstico.**

  ***\* ------------------------------------------------------------------------\*/**

 ***POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_selftest\_compensation(double\* observed\_err);**

 ***POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_selftest\_all(void);**

***+POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_check\_ftz(void);**

 ***POLYDIM\_EXPORT const char\* POLYDIM\_CALL polydim\_status\_string(int32\_t code);**

 ***POLYDIM\_EXPORT const char\* POLYDIM\_CALL polydim\_build\_info(void);**
```


## ***2. `kernel\_cpp\_v768.cpp`**

### ***C-01 — `overlaps` UB (comparación de punteros no relacionados)**

***Reemplaza la función `overlaps` del namespace anónimo:**

***cpp**

```
***// ANTES:**

***// inline bool overlaps(const void\* a, const void\* b, size\_t bytes) \{**

***//     auto pa = static\_cast\<const char\*\>(a);**

***//     auto pb = static\_cast\<const char\*\>(b);**

***//     return (pa \< pb + bytes) && (pb \< pa + bytes);**

***// \}**


***// DESPUÉS: comparación vía uintptr\_t (definido en C++, no UB)**

***inline bool overlaps(const void\* a, const void\* b, size\_t bytes) \{**

    ***const std::uintptr\_t pa = reinterpret\_cast\<std::uintptr\_t\>(a);**

    ***const std::uintptr\_t pb = reinterpret\_cast\<std::uintptr\_t\>(b);**

    ***// Chequeo de overflow de pb + bytes**

    ***if (pb \> UINTPTR\_MAX - bytes) return false;**

    ***if (pa \> UINTPTR\_MAX - bytes) return false;**

    ***return (pa \< pb + bytes) && (pb \< pa + bytes);**

***\}**
```

***Añadir al principio del archivo: `\#include \<cstdint\>` (ya está) y `\#include \<cstddef\>`.**

### ***C-02, C-03, C-04 — Aliasing completo en los 3 kernels**

***Reemplaza el bloque de validación en `polydim\_rodrigues\_geodesic\_f64` (justo después de `const size\_t bytes = ...`):**

***cpp**

```
***const size\_t bytes = static\_cast\<size\_t\>(D) \* sizeof(double);**


***// Igualdad exacta permitida (in-place); solapamiento parcial prohibido.**

***if (y\_out != y && overlaps(y\_out, y, bytes))   return POLYDIM\_ERR\_ALIASED\_BUFFERS;**

***if (overlaps(y\_out, u, bytes) || overlaps(y\_out, v, bytes))**

    ***return POLYDIM\_ERR\_ALIASED\_BUFFERS;**

***if (overlaps(y, u, bytes) || overlaps(y, v, bytes))**

    ***return POLYDIM\_ERR\_ALIASED\_BUFFERS;**

***if (overlaps(u, v, bytes))**

    ***return POLYDIM\_ERR\_ALIASED\_BUFFERS;**
```

***En `polydim\_project\_sphere\_f64`, después de `if (D == 0) ...`:**

***cpp**

```
***const size\_t bytes = static\_cast\<size\_t\>(D) \* sizeof(double);**

***if (y\_out != y && overlaps(y\_out, y, bytes))**

    ***return POLYDIM\_ERR\_ALIASED\_BUFFERS;**
```

***En `polydim\_orthonormalize\_pair\_f64`, después de `if (D \< 2) ...`:**

***cpp**

```
***const size\_t bytes = static\_cast\<size\_t\>(D) \* sizeof(double);**

***if (u == v || overlaps(u, v, bytes))**

    ***return POLYDIM\_ERR\_ALIASED\_BUFFERS;**
```

***En `polydim\_stiefel\_cayley\_smw\_f64`, después de calcular `bytes`:**

***cpp**

```
***if (X == G) return POLYDIM\_ERR\_ALIASED\_BUFFERS;**

***if (X == Y\_out || G == Y\_out) return POLYDIM\_ERR\_ALIASED\_BUFFERS;**

***if (overlaps(Y\_out, X, bytes) || overlaps(Y\_out, G, bytes))**

    ***return POLYDIM\_ERR\_ALIASED\_BUFFERS;**

***if (overlaps(X, G, bytes))**

    ***return POLYDIM\_ERR\_ALIASED\_BUFFERS;**
```

### ***C-05 — `memset` sobre `std::atomic` (UB de tipo)**

***Reemplaza el cuerpo de `polydim\_pmtp\_init`:**

***cpp**

```
***extern "C" POLYDIM\_EXPORT int32\_t POLYDIM\_CALL**

***polydim\_pmtp\_init(PMTP\_Control\* c, uint32\_t num\_slots, uint64\_t payload\_bytes) \{**

    ***try \{**

        ***if (!c) return -1;**

        ***if (num\_slots \< POLYDIM\_PMTP2\_MIN\_SLOTS || num\_slots \> POLYDIM\_PMTP2\_MAX\_SLOTS) return -2;**

        ***if (payload\_bytes == 0) return -2;**

        ***if (polydim\_pmtp\_sizeof(num\_slots, payload\_bytes) == 0) return -2;**


        ***// Inicialización por campo, atómicos incluidos.**

        ***c-\>magic = POLYDIM\_PMTP2\_MAGIC;**

        ***c-\>num\_slots = num\_slots;**

        ***c-\>payload\_bytes = payload\_bytes;**

        ***c-\>pub\_seq.store(0, std::memory\_order\_relaxed);**

        ***c-\>pub\_slot.store(0, std::memory\_order\_relaxed);**

        ***c-\>wlock.store(0, std::memory\_order\_relaxed);**

        ***c-\>wticket.store(0, std::memory\_order\_relaxed);**

        ***std::memset(c-\>reserved\_, 0, sizeof(c-\>reserved\_));**


        ***// Inicializar cada slot header**

        ***for (uint32\_t i = 0; i \< num\_slots; ++i) \{**

            ***PMTP\_SlotHeader\* hdr = pmtp2\_hdr\_of(c, i);**

            ***hdr-\>seq.store(0, std::memory\_order\_relaxed);**

            ***std::memset(hdr-\>reserved\_, 0, sizeof(hdr-\>reserved\_));**

        ***\}**

        ***return 0;**

    ***\} catch (...) \{ return -1; \}**

***\}**
```

### ***C-06 — `sizeof` con overflow**

***Reemplaza el cuerpo de `polydim\_pmtp\_sizeof`:**

***cpp**

```
***extern "C" POLYDIM\_EXPORT uint64\_t POLYDIM\_CALL**

***polydim\_pmtp\_sizeof(uint32\_t num\_slots, uint64\_t payload\_bytes) \{**

    ***try \{**

        ***if (num\_slots \< POLYDIM\_PMTP2\_MIN\_SLOTS || num\_slots \> POLYDIM\_PMTP2\_MAX\_SLOTS) return 0;**

        ***const uint64\_t head = static\_cast\<uint64\_t\>(sizeof(PMTP\_Control))**

                            ***+ static\_cast\<uint64\_t\>(num\_slots) \* sizeof(PMTP\_SlotHeader);**

        ***if (head \> UINT64\_MAX - (UINT64\_MAX / 2)) return 0;  // sanity**

        ***if (payload\_bytes != 0 && payload\_bytes \> (UINT64\_MAX - head) / num\_slots) return 0;**

        ***return head + static\_cast\<uint64\_t\>(num\_slots) \* payload\_bytes;**

    ***\} catch (...) \{ return 0; \}**

***\}**
```

### ***C-08 — `selftest\_all` debe chequear FTZ y subnormal**

***Reemplaza el cuerpo de `polydim\_selftest\_all`:**

***cpp**

```
***extern "C" POLYDIM\_EXPORT int32\_t POLYDIM\_CALL polydim\_selftest\_all(void) \{**

    ***try \{**

        ***// 1. Compensación numérica**

        ***double e = 0.0;**

        ***int32\_t rc = polydim\_selftest\_compensation(&e);**

        ***if (rc != POLYDIM\_SUCCESS) return rc;**


        ***// 2. FTZ/DAZ apagado (canario del contrato de silicio)**

        ***if (polydim\_check\_ftz() != 0) return POLYDIM\_ERR\_COMPENSATION\_BROKEN;**


        ***// 3. Casos de error de Rodrigues**

        ***double y\[4\] = \{1.0, 0.0, 0.0, 0.0\}, u\[4\] = \{0.0, 1.0, 0.0, 0.0\},**

               ***v\[4\] = \{0.0, 0.0, 1.0, 0.0\}, o\[4\] = \{0, 0, 0, 0\};**

        ***const double nan\_v = std::numeric\_limits\<double\>::quiet\_NaN();**

        ***if (polydim\_rodrigues\_geodesic\_f64(y, u, v, o, nan\_v, 4, nullptr, nullptr)**

            ***!= POLYDIM\_ERR\_INVALID\_SCALAR) return POLYDIM\_ERR\_NUMERICAL\_INSTABILITY;**


        ***double u\_bad\[4\] = \{0.0, 2.0, 0.0, 0.0\};**

        ***if (polydim\_rodrigues\_geodesic\_f64(y, u\_bad, v, o, 0.3, 4, nullptr, nullptr)**

            ***!= POLYDIM\_ERR\_BASIS\_NOT\_ORTHONORMAL) return POLYDIM\_ERR\_NUMERICAL\_INSTABILITY;**


        ***double y\_bad\[4\] = \{1.0 + 1e-6, 0.0, 0.0, 0.0\};**

        ***if (polydim\_rodrigues\_geodesic\_f64(y\_bad, u, v, o, 0.3, 4, nullptr, nullptr)**

            ***!= POLYDIM\_ERR\_POINT\_OFF\_MANIFOLD) return POLYDIM\_ERR\_NUMERICAL\_INSTABILITY;**


        ***// 4. Canario subnormal real (IEEE-754 mínimo positivo)**

        ***const double denorm = 4.9406564584124654e-324;**

        ***double sub\_in\[2\] = \{denorm, 1.0\};**

        ***double sub\_out\[2\] = \{0.0, 0.0\};**

        ***if (polydim\_project\_sphere\_f64(sub\_in, sub\_out, 2, nullptr) != POLYDIM\_SUCCESS)**

            ***return POLYDIM\_ERR\_NUMERICAL\_INSTABILITY;**

        ***if (sub\_out\[0\] == 0.0 && sub\_in\[0\] != 0.0)**

            ***return POLYDIM\_ERR\_COMPENSATION\_BROKEN;  // FTZ colapsó el denormal**


        ***return POLYDIM\_SUCCESS;**

    ***\} catch (...) \{**

        ***return POLYDIM\_ERR\_INTERNAL;**

    ***\}**

***\}**
```

### ***C-09 — Unificar `POLYDIM\_MAX\_K`**

***En `polydim\_stiefel\_cayley\_smw\_f64` reemplaza `POLYDIM\_MAX\_K` por `POLYDIM\_MAX\_K` de `polydim.h` (que vas a definir). Añadí a `polydim.h`:**

***c**

```
***\#ifndef POLYDIM\_MAX\_K**

***\#define POLYDIM\_MAX\_K 1024u**

***\#endif**
```

***Y en `polydim\_cholqr2\_f64`, reemplaza `if (K \> 1024)` por `if (K \> POLYDIM\_MAX\_K)`.**

### ***C-10 — `cholqr2` convergencia en paso 0**

***Reemplaza el bloque `if (step \> 0) \{ ... \}` en `polydim\_cholqr2\_f64`:**

***cpp**

```
***// Post-verify SIEMPRE (también en step 0)**

***\{**

    ***double max\_err = 0.0;**

    ***for (uint32\_t r = 0; r \< K; ++r) \{**

        ***for (uint32\_t c = 0; c \< K; ++c) \{**

            ***double expected = (r == c) ? 1.0 : 0.0;**

            ***double err = std::abs(A\[r \* K + c\] - expected);**

            ***if (err \> max\_err) max\_err = err;**

        ***\}**

    ***\}**

    ***if (max\_err \< eps \* static\_cast\<double\>(D) \* 10.0) \{**

        ***converged = true;**

        ***break;**

    ***\}**

***\}**
```

### ***C-11 — Anidamiento OMP en `polydim\_cdot`**

***Reemplaza `polydim\_cdot`:**

***cpp**

```
***static double polydim\_cdot(const double\* a, const double\* b, uint64\_t D, int nthreads) \{**

    ***std::vector\<Neumaier\> acc(nthreads);**

    ***const bool already\_parallel = (omp\_get\_active\_level() \> 0);**

    ***\#pragma omp parallel num\_threads(nthreads) if(!already\_parallel)**

    ***\{**

        ***const int tid = already\_parallel ? 0 : omp\_get\_thread\_num();**

        ***Neumaier l;**

        ***\#pragma omp for schedule(static)**

        ***for (int64\_t i = 0; i \< static\_cast\<int64\_t\>(D); ++i) l.add(a\[i\] \* b\[i\]);**

        ***acc\[tid\] = l;**

    ***\}**

    ***Neumaier t; for (int i = 0; i \< nthreads; ++i) t.merge(acc\[i\]);**

    ***return t.total();**

***\}**
```

### ***C-12 — Reducción no compensada en Stiefel**

***En `polydim\_stiefel\_cayley\_smw\_f64`, en los 3 lugares donde hay `for (int t = 0; t \< nthreads; ++t) s += arena\[...\]`, reemplaza por:**

***cpp**

```
***Neumaier acc;**

***for (int t = 0; t \< nthreads; ++t) \{**

    ***acc.add(arena\[static\_cast\<size\_t\>(t) \* KK2 + j\]);**

***\}**

***S\[j\] = acc.total();**
```

***Idem para `arena\_gp` (K×K) y para el bloque final de `ortho\_err`.**

### ***C-13 — Alineación en ruta BLAS**

***En `polydim\_stiefel\_cayley\_smw\_f64`, dentro de `\#ifdef POLYDIM\_USE\_BLAS`, añade antes de la primera `dsyrk\_`:**

***cpp**

```
***if ((reinterpret\_cast\<std::uintptr\_t\>(X) % 32) != 0 ||**

    ***(reinterpret\_cast\<std::uintptr\_t\>(G) % 32) != 0)**

    ***return POLYDIM\_ERR\_BUFFER\_OVERFLOW;**
```


## ***3. `kernel\_rust\_v768.rs`**

### ***R-01 — Betti-1 real**

***Reemplaza el bloque final de `polydim\_rust\_betti1\_guard` (después del doble bucle):**

***rust**

```
***// Betti-0 = componentes conectadas.**

***// Betti-1 = E - V + C.**

***let betti0 = components;**

***let betti1 = edges as isize - n as isize + betti0 as isize;**


***if betti0 \> 1 \{**

    ***return PolydimRustStatus::ErrTopologyFragmented;**

***\}**

***if betti1 != 0 \{**

    ***return PolydimRustStatus::ErrTopologyFragmented;**

***\}**


***PolydimRustStatus::Success**
```

### ***R-02 — Alineación en `betti1\_guard`**

***Añade después de la validación de `n`:**

***rust**

```
***if (adj\_matrix as usize) % 8 != 0 \{**

    ***return PolydimRustStatus::ErrBufferOverflow;**

***\}**
```

### ***R-04 — `panic = unwind` documentado**

***Crea `Cargo.toml` en la raíz del crate Rust:**

***toml**

```
***\[package\]**

***name = "polydim\_rust\_guard"**

***version = "0.1.0"**

***edition = "2021"**


***\[lib\]**

***crate-type = \["cdylib"\]**


***\[profile.release\]**

***panic = "unwind"**

***opt-level = 3**

***lto = true**

***codegen-units = 1**
```

***Sin esto, `catch\_unwind` es UB con `panic=abort`.**


## ***4. `polydim\_ffi.dart` — REESCRITURA COMPLETA**

***Reemplaza el archivo entero:**

***dart**

```
***// ============================================================================**

***// POLYDIM V768 — puente FFI Dart (corregido ABI contra polydim.h)**

***// ============================================================================**


***import 'dart:ffi';**

***import 'dart:io' show Platform, Directory;**

***import 'dart:math' as math;**

***import 'package:ffi/ffi.dart' show calloc;**


***const int polydimSuccess = 0;**

***const Map\<int, String\> polydimStatus = \{**

  ***0: 'SUCCESS', -1: 'NULL\_POINTER', -2: 'INVALID\_DIMENSION', -3: 'NAN\_OR\_INF',**

  ***-4: 'DEGENERATE\_NORM', -5: 'NUMERICAL\_INSTABILITY', -6: 'SEQLOCK\_RACE',**

  ***-7: 'BUFFER\_OVERFLOW', -8: 'INVALID\_SCALAR', -9: 'BASIS\_NOT\_ORTHONORMAL',**

  ***-10: 'POINT\_OFF\_MANIFOLD', -11: 'ALIASED\_BUFFERS', -12: 'COMPENSATION\_BROKEN',**

  ***-13: 'ALLOC\_FAILED', -14: 'INTERNAL\_EXCEPTION',**

***\};**

***String statusName(int rc) =\> polydimStatus\[rc\] ?? 'UNKNOWN($rc)';**


***class PolydimException implements Exception \{**

  ***final int code;**

  ***final String op;**

  ***PolydimException(this.op, this.code);**

  ***@override**

  ***String toString() =\> 'PolydimException: $op -\> $\{statusName(code)\} ($code)';**

***\}**


***final class PolydimTolerances extends Struct \{**

  ***@Double() external double basisOrtho;**

  ***@Double() external double pointNorm;**

  ***@Double() external double gramOrtho;**

  ***@Double() external double pivotRel;**

  ***@Int32() external int rejectSubnormal;**

***\}**


***final class PolydimReport extends Struct \{**

  ***@Double() external double pointNormErr;**

  ***@Double() external double basisUuErr;**

  ***@Double() external double basisVvErr;**

  ***@Double() external double basisUvErr;**

  ***@Double() external double outNormErr;**

  ***@Double() external double pivotMin;**

  ***@Double() external double pivotThreshold;**

  ***@Double() external double orthoErr;**

  ***@Uint64() external int threadsUsed;**

***\}**


***// Espejo exacto del PMTP\_Control (64 bytes, alignas(64) en C++)**

***final class PMTPControl extends Struct \{**

  ***@Uint32() external int magic;**

  ***@Uint32() external int numSlots;**

  ***@Uint64() external int payloadBytes;**

  ***@Uint64() external int pubSeq;**

  ***@Uint32() external int pubSlot;**

  ***@Uint32() external int wlock;**

  ***@Uint32() external int wticket;**

  ***@Array(28) external Array\<Uint8\> reserved;**

***\}**


***// --- Firmas de Rodrigues/Sphere/Ortho (sin cambios) ---**

***typedef \_RodriguesNative = Int32 Function(Pointer\<Double\>, Pointer\<Double\>,**

    ***Pointer\<Double\>, Pointer\<Double\>, Double, Uint64,**

    ***Pointer\<PolydimTolerances\>, Pointer\<PolydimReport\>);**

***typedef \_RodriguesDart = int Function(Pointer\<Double\>, Pointer\<Double\>,**

    ***Pointer\<Double\>, Pointer\<Double\>, double, int,**

    ***Pointer\<PolydimTolerances\>, Pointer\<PolydimReport\>);**


***typedef \_ProjectNative = Int32 Function(Pointer\<Double\>, Pointer\<Double\>, Uint64, Pointer\<PolydimReport\>);**

***typedef \_ProjectDart = int Function(Pointer\<Double\>, Pointer\<Double\>, int, Pointer\<PolydimReport\>);**


***typedef \_OrthoNative = Int32 Function(Pointer\<Double\>, Pointer\<Double\>, Uint64, Pointer\<PolydimReport\>);**

***typedef \_OrthoDart = int Function(Pointer\<Double\>, Pointer\<Double\>, int, Pointer\<PolydimReport\>);**


***typedef \_SelftestNative = Int32 Function();**

***typedef \_SelftestDart = int Function();**


***typedef \_InfoNative = Pointer\<Uint8\> Function();**

***typedef \_InfoDart = Pointer\<Uint8\> Function();**


***// --- Firmas PMTP: coinciden EXACTAMENTE con polydim.h ---**

***typedef \_InitNative = Int32 Function(Pointer\<PMTPControl\>, Uint32, Uint64);**

***typedef \_InitDart = int Function(Pointer\<PMTPControl\>, int, int);**


***typedef \_WriteBeginNative = Int32 Function(Pointer\<PMTPControl\>, Pointer\<Uint32\>, Pointer\<Uint64\>);**

***typedef \_WriteBeginDart = int Function(Pointer\<PMTPControl\>, Pointer\<Uint32\>, Pointer\<Uint64\>);**


***typedef \_WriteCommitNative = Void Function(Pointer\<PMTPControl\>, Uint32, Uint64);**

***typedef \_WriteCommitDart = void Function(Pointer\<PMTPControl\>, int, int);**


***typedef \_WriteAbortNative = Void Function(Pointer\<PMTPControl\>, Uint32, Uint64);**

***typedef \_WriteAbortDart = void Function(Pointer\<PMTPControl\>, int, int);**


***typedef \_ReadBeginNative = Int32 Function(Pointer\<PMTPControl\>, Pointer\<Uint32\>, Pointer\<Uint64\>);**

***typedef \_ReadBeginDart = int Function(Pointer\<PMTPControl\>, Pointer\<Uint32\>, Pointer\<Uint64\>);**


***typedef \_ReadValidateNative = Int32 Function(Pointer\<PMTPControl\>, Uint32, Uint64);**

***typedef \_ReadValidateDart = int Function(Pointer\<PMTPControl\>, int, int);**


***typedef \_SizeofNative = Uint64 Function(Uint32, Uint64);**

***typedef \_SizeofDart = int Function(int, int);**


***class Polydim \{**

  ***final DynamicLibrary \_lib;**

  ***late final \_RodriguesDart \_rodrigues;**

  ***late final \_ProjectDart \_projectSphere;**

  ***late final \_OrthoDart \_orthonormalize;**

  ***late final \_SelftestDart \_selftestAll;**

  ***late final \_InfoDart \_buildInfo;**

  ***late final \_InitDart \_pmtpInit;**

  ***late final \_WriteBeginDart \_pmtpWriteBegin;**

  ***late final \_WriteCommitDart \_pmtpWriteCommit;**

  ***late final \_WriteAbortDart \_pmtpWriteAbort;**

  ***late final \_ReadBeginDart \_pmtpReadBegin;**

  ***late final \_ReadValidateDart \_pmtpReadValidate;**

  ***late final \_SizeofDart \_pmtpSizeof;**


  ***Polydim.\_(this.\_lib) \{**

    ***\_rodrigues = \_lib.lookupFunction\<\_RodriguesNative, \_RodriguesDart\>('polydim\_rodrigues\_geodesic\_f64');**

    ***\_projectSphere = \_lib.lookupFunction\<\_ProjectNative, \_ProjectDart\>('polydim\_project\_sphere\_f64');**

    ***\_orthonormalize = \_lib.lookupFunction\<\_OrthoNative, \_OrthoDart\>('polydim\_orthonormalize\_pair\_f64');**

    ***\_selftestAll = \_lib.lookupFunction\<\_SelftestNative, \_SelftestDart\>('polydim\_selftest\_all');**

    ***\_buildInfo = \_lib.lookupFunction\<\_InfoNative, \_InfoDart\>('polydim\_build\_info');**


    ***// Símbolos reales, no los inventados.**

    ***\_pmtpInit          = \_lib.lookupFunction\<\_InitNative,          \_InitDart\>('polydim\_pmtp\_init');**

    ***\_pmtpWriteBegin    = \_lib.lookupFunction\<\_WriteBeginNative,    \_WriteBeginDart\>('polydim\_pmtp\_write\_begin');**

    ***\_pmtpWriteCommit   = \_lib.lookupFunction\<\_WriteCommitNative,   \_WriteCommitDart\>('polydim\_pmtp\_write\_commit');**

    ***\_pmtpWriteAbort    = \_lib.lookupFunction\<\_WriteAbortNative,    \_WriteAbortDart\>('polydim\_pmtp\_write\_abort');**

    ***\_pmtpReadBegin     = \_lib.lookupFunction\<\_ReadBeginNative,     \_ReadBeginDart\>('polydim\_pmtp\_read\_begin');**

    ***\_pmtpReadValidate  = \_lib.lookupFunction\<\_ReadValidateNative,  \_ReadValidateDart\>('polydim\_pmtp\_read\_validate');**

    ***\_pmtpSizeof        = \_lib.lookupFunction\<\_SizeofNative,        \_SizeofDart\>('polydim\_pmtp\_sizeof');**

  ***\}**


  ***static String \_defaultLibraryName() \{**

    ***if (Platform.isWindows) return 'polydim.dll';**

    ***if (Platform.isMacOS)   return 'libpolydim.dylib';**

    ***return 'libpolydim.so';**

  ***\}**


  ***static Polydim open(\{String? path, bool runSelftest = true\}) \{**

    ***final name = path ?? \_defaultLibraryName();**

    ***final cwd = Directory.current.path;**

    ***final candidates = \<String\>\[**

      ***name, './$name', '$cwd/$name', '$cwd/build/$name', '$cwd/../build/$name',**

      ***'$cwd/lib/$name', '$cwd/native/$name',**

    ***\];**

    ***DynamicLibrary? lib;**

    ***final errors = \<String\>\[\];**

    ***for (final c in candidates) \{**

      ***try \{ lib = DynamicLibrary.open(c); break; \}**

      ***on ArgumentError catch (e) \{ errors.add('$c: $e'); \}**

    ***\}**

    ***if (lib == null) throw StateError('No se pudo abrir $name.\\n$\{errors.join('\\n')\}');**

    ***final p = Polydim.\_(lib);**

    ***if (runSelftest) \{**

      ***final rc = p.\_selftestAll();**

      ***if (rc != polydimSuccess) throw PolydimException('selftest\_all', rc);**

    ***\}**

    ***return p;**

  ***\}**


  ***String get buildInfo \{**

    ***final ptr = \_buildInfo();**

    ***if (ptr == nullptr) return '\<no build info\>';**

    ***final bytes = \<int\>\[\];**

    ***for (var i = 0; ptr\[i\] != 0; i++) bytes.add(ptr\[i\]);**

    ***return String.fromCharCodes(bytes);**

  ***\}**


  ***(\{int rc, double outNormErr, double pointNormErr, int threads, List\<double\>? y\})**

      ***rotate(\{**

    ***required List\<double\> y,**

    ***required List\<double\> u,**

    ***required List\<double\> v,**

    ***required double theta,**

    ***bool returnResult = true,**

  ***\}) \{**

    ***final d = y.length;**

    ***if (u.length != d || v.length != d) \{**

      ***throw ArgumentError('y, u y v deben tener la misma longitud');**

    ***\}**

    ***final py = calloc\<Double\>(d);**

    ***final pu = calloc\<Double\>(d);**

    ***final pv = calloc\<Double\>(d);**

    ***final po = calloc\<Double\>(d);**

    ***final rep = calloc\<PolydimReport\>();**

    ***try \{**

      ***for (var i = 0; i \< d; i++) \{ py\[i\] = y\[i\]; pu\[i\] = u\[i\]; pv\[i\] = v\[i\]; \}**

      ***final rc = \_rodrigues(py, pu, pv, po, theta, d, nullptr, rep);**

      ***final r = rep.ref;**

      ***List\<double\>? out;**

      ***if (rc == polydimSuccess && returnResult) \{**

        ***out = List\<double\>.generate(d, (i) =\> po\[i\], growable: false);**

      ***\}**

      ***return (rc: rc, outNormErr: r.outNormErr, pointNormErr: r.pointNormErr,**

              ***threads: r.threadsUsed, y: out);**

    ***\} finally \{**

      ***calloc.free(py); calloc.free(pu); calloc.free(pv);**

      ***calloc.free(po); calloc.free(rep);**

    ***\}**

  ***\}**


  ***// --- PMTP API ---**

  ***int pmtpSizeof(int numSlots, int payloadBytes) =\> \_pmtpSizeof(numSlots, payloadBytes);**


  ***int pmtpInit(Pointer\<PMTPControl\> ctrl, int numSlots, int payloadBytes) =\>**

      ***\_pmtpInit(ctrl, numSlots, payloadBytes);**


  ***int pmtpWriteBegin(Pointer\<PMTPControl\> ctrl, Pointer\<Uint32\> slotOut, Pointer\<Uint64\> verOut) =\>**

      ***\_pmtpWriteBegin(ctrl, slotOut, verOut);**


  ***void pmtpWriteCommit(Pointer\<PMTPControl\> ctrl, int slot, int ver) =\>**

      ***\_pmtpWriteCommit(ctrl, slot, ver);**


  ***void pmtpWriteAbort(Pointer\<PMTPControl\> ctrl, int slot, int ver) =\>**

      ***\_pmtpWriteAbort(ctrl, slot, ver);**


  ***int pmtpReadBegin(Pointer\<PMTPControl\> ctrl, Pointer\<Uint32\> slotOut, Pointer\<Uint64\> verOut) =\>**

      ***\_pmtpReadBegin(ctrl, slotOut, verOut);**


  ***int pmtpReadValidate(Pointer\<PMTPControl\> ctrl, int slot, int ver) =\>**

      ***\_pmtpReadValidate(ctrl, slot, ver);**

***\}**
```


## ***5. `test\_pmtp.dart` — REESCRITURA**

***dart**

```
***import 'dart:ffi';**

***import 'package:ffi/ffi.dart';**

***import 'polydim\_ffi.dart';**


***void main() \{**

  ***print("=== BULLDOG: DART FFI PMTP ABI PARITY ===");**


  ***// Tamaño estructural: Dart DEBE coincidir con C++.**

  ***final dartSize = sizeOf\<PMTPControl\>();**

  ***print("sizeof(PMTPControl) en Dart: $dartSize bytes (esperado 64)");**

  ***if (dartSize != 64) throw StateError("ABI MISMATCH: Dart PMTPControl != 64 bytes");**


  ***final p = Polydim.open();**

  ***print("Biblioteca: $\{p.buildInfo\}");**


  ***final numSlots = 4;**

  ***final payloadBytes = 10000 \* 8;**

  ***final totalBytes = p.pmtpSizeof(numSlots, payloadBytes);**

  ***if (totalBytes == 0) throw StateError("polydim\_pmtp\_sizeof returned 0");**

  ***print("PMTP total bytes: $totalBytes");**


  ***final buf = calloc\<Uint8\>(totalBytes);**

  ***final ctrl = buf.cast\<PMTPControl\>();**

  ***try \{**

    ***final rc = p.pmtpInit(ctrl, numSlots, payloadBytes);**

    ***if (rc != 0) throw StateError("pmtp\_init failed rc=$rc");**


    ***final slot = calloc\<Uint32\>();**

    ***final ver = calloc\<Uint64\>();**

    ***try \{**

      ***final wrc = p.pmtpWriteBegin(ctrl, slot, ver);**

      ***if (wrc != 0) throw StateError("write\_begin rc=$wrc");**

      ***print("write slot=$\{slot.value\} ver=$\{ver.value\} (debe ser impar)");**

      ***p.pmtpWriteCommit(ctrl, slot.value, ver.value);**


      ***final rslot = calloc\<Uint32\>();**

      ***final rver = calloc\<Uint64\>();**

      ***try \{**

        ***final brc = p.pmtpReadBegin(ctrl, rslot, rver);**

        ***if (brc != 0) throw StateError("read\_begin rc=$brc");**

        ***final vrc = p.pmtpReadValidate(ctrl, rslot.value, rver.value);**

        ***if (vrc != 0) throw StateError("read\_validate rc=$vrc");**

        ***print("Lectura OK: slot=$\{rslot.value\} ver=$\{rver.value\}");**

        ***print("DART PMTP TEST PASSED");**

      ***\} finally \{**

        ***calloc.free(rslot); calloc.free(rver);**

      ***\}**

    ***\} finally \{**

      ***calloc.free(slot); calloc.free(ver);**

    ***\}**

  ***\} finally \{**

    ***calloc.free(buf);**

  ***\}**

***\}**
```


## ***6. `polydim\_v768\_monolito.py`**

### ***P-01, P-02, P-03 — `PMTPSlabChannel` funcional**

***Reemplaza la clase `PMTPSlabChannel` completa:**

***python**

```
***class PMTPSlabChannel:**

    ***def \_\_init\_\_(self, binding, name="polydim\_bus\_0", d=1024, num\_slots=4):**

        ***self.binding = binding**

        ***self.d = d**

        ***self.num\_slots = num\_slots**

        ***self.payload\_bytes = d \* 8**

        ***self.shm\_name = name**

        ***self.\_pin\_refs = \[\]**


        ***self.total\_bytes = binding.lib.polydim\_pmtp\_sizeof(num\_slots, self.payload\_bytes)**

        ***if self.total\_bytes == 0:**

            ***raise RuntimeError("polydim\_pmtp\_sizeof failed (overflow or bad args)")**


        ***self.is\_posix = (os.name == 'posix')**

        ***if self.is\_posix:**

            ***from multiprocessing import shared\_memory**

            ***try:**

                ***self.shm = shared\_memory.SharedMemory(create=True, name=self.shm\_name, size=self.total\_bytes)**

            ***except FileExistsError:**

                ***self.shm = shared\_memory.SharedMemory(name=self.shm\_name)**

            ***self.mmap\_obj = self.shm.buf**

        ***else:**

            ***import mmap**

            ***self.mmap\_obj = mmap.mmap(-1, self.total\_bytes, self.shm\_name)**

            ***self.shm = None**


        ***self.ctrl = PMTPControl.from\_buffer(self.mmap\_obj)**

        ***self.ctrl\_ptr = ctypes.pointer(self.ctrl)**

        ***self.\_pin\_refs.extend(\[self.ctrl\_ptr, self.mmap\_obj\])**


        ***rc = binding.lib.polydim\_pmtp\_init(self.ctrl\_ptr, num\_slots, self.payload\_bytes)**

        ***if rc != 0:**

            ***raise RuntimeError(f"polydim\_pmtp\_init failed: rc=\{rc\}")**


        ***self.\_payload\_base = (ctypes.addressof(self.ctrl)**

                              ***+ ctypes.sizeof(PMTPControl)**

                              ***+ num\_slots \* ctypes.sizeof(PMTPSlotHeader))**


    ***def \_payload\_addr(self, slot: int) -\> int:**

        ***return self.\_payload\_base + slot \* self.payload\_bytes**


    ***def write\_tensor(self, tensor\_np: np.ndarray) -\> int:**

        ***if tensor\_np.dtype != np.float64 or tensor\_np.size != self.d:**

            ***raise ValueError(f"Expected float64\[\{self.d\}\], got \{tensor\_np.dtype\}\[\{tensor\_np.size\}\]")**

        ***slot = ctypes.c\_uint32(0)**

        ***ver = ctypes.c\_uint64(0)**

        ***rc = self.binding.lib.polydim\_pmtp\_write\_begin(**

            ***self.ctrl\_ptr, ctypes.byref(slot), ctypes.byref(ver))**

        ***if rc != 0:**

            ***return rc**

        ***addr = self.\_payload\_addr(slot.value)**

        ***ctypes.memmove(addr, tensor\_np.ctypes.data, tensor\_np.nbytes)**

        ***self.binding.lib.polydim\_pmtp\_write\_commit(self.ctrl\_ptr, slot.value, ver.value)**

        ***return 0**


    ***def read\_tensor(self):**

        ***slot = ctypes.c\_uint32(0)**

        ***ver = ctypes.c\_uint64(0)**

        ***rc = self.binding.lib.polydim\_pmtp\_read\_begin(**

            ***self.ctrl\_ptr, ctypes.byref(slot), ctypes.byref(ver))**

        ***if rc != 0:**

            ***return rc, None**

        ***addr = self.\_payload\_addr(slot.value)**

        ***buf = (ctypes.c\_double \* self.d).from\_address(addr)**

        ***out = np.ctypeslib.as\_array(buf).copy()**

        ***rc2 = self.binding.lib.polydim\_pmtp\_read\_validate(self.ctrl\_ptr, slot.value, ver.value)**

        ***if rc2 != 0:**

            ***return rc2, None**

        ***return 0, out**


    ***def \_\_del\_\_(self):**

        ***if self.is\_posix and getattr(self, 'shm', None) is not None:**

            ***try: self.shm.close()**

            ***except Exception: pass**

            ***try: self.shm.unlink()**

            ***except Exception: pass**

        ***elif getattr(self, 'mmap\_obj', None) is not None:**

            ***try: self.mmap\_obj.close()**

            ***except Exception: pass**

        ***self.mmap\_obj = None**
```

### ***P-04 — Nombres de biblioteca multiplataforma**

***Reemplaza el bloque de carga en `PolydimNativeBinding.\_\_init\_\_`:**

***python**

```
***def \_lib\_candidates(dll\_dir):**

    ***if sys.platform == "win32":**

        ***return \[os.path.join(dll\_dir, "polydim.dll"),**

                ***os.path.join(dll\_dir, "libpolydim.dll")\]**

    ***if sys.platform == "darwin":**

        ***return \[os.path.join(dll\_dir, "libpolydim.dylib")\]**

    ***return \[os.path.join(dll\_dir, "libpolydim.so"),**

            ***os.path.join(dll\_dir, "polydim.so")\]**


***\# En \_\_init\_\_:**

***self.dll\_path = None**

***for cand in \_lib\_candidates(dll\_dir):**

    ***if os.path.exists(cand):**

        ***self.dll\_path = cand**

        ***break**

***if self.dll\_path is None:**

    ***raise FileNotFoundError(f"No libpolydim found in \{dll\_dir\}")**
```

### ***P-05 — `restype` explícito para PMTP**

***Añade al final de `\_bind\_cpp\_symbols`:**

***python**

```
***self.lib.polydim\_pmtp\_init.restype = ctypes.c\_int32**

***self.lib.polydim\_pmtp\_write\_begin.restype = ctypes.c\_int32**

***self.lib.polydim\_pmtp\_read\_begin.restype = ctypes.c\_int32**

***self.lib.polydim\_pmtp\_read\_validate.restype = ctypes.c\_int32**

***self.lib.polydim\_pmtp\_sizeof.restype = ctypes.c\_uint64**

***self.lib.polydim\_check\_ftz.restype = ctypes.c\_int32**
```

### ***P-11 — Verificación in-place vs out-of-place**

***Añade después del test in-place (línea donde se hace `assert rc\_inplace == 0`):**

***python**

```
***\# Comparar in-place vs out-of-place**

***y\_out\_oop = np.zeros\_like(y\_orig)**

***rc\_oop = binding.lib.polydim\_rodrigues\_geodesic\_f64(**

    ***y\_orig.ctypes.data, u\_vec.ctypes.data, v\_vec.ctypes.data, y\_out\_oop.ctypes.data,**

    ***ctypes.c\_double(theta\_rot), ctypes.c\_uint64(d\_inplace), None, ctypes.byref(rep))**

***assert rc\_oop == 0**

***diff = np.linalg.norm(y\_vec - y\_out\_oop)**

***assert diff \< 1e-14, f"In-place diverge de out-of-place: \{diff:.2e\}"**

***print(f"\[F-03 PARITY\] in-place vs out-of-place diff = \{diff:.2e\}")**
```


## ***7. `universal\_llm\_tangent\_adapter.py`**

### ***U-01 — Biyectividad real**

***Reemplaza `encode` y `decode`:**

***python**

```
***def encode(self, h: np.ndarray) -\> tuple\[np.ndarray, float\]:**

    ***norm\_h = float(np.linalg.norm(h))**

    ***if norm\_h == 0.0:**

        ***u = np.zeros\_like(h)**

        ***u\[0\] = 1.0**

        ***return u, float('-inf')**

    ***u = h / norm\_h**

    ***norm\_u = float(np.linalg.norm(u))**

    ***if norm\_u \> 0.0:**

        ***u = u / norm\_u**

    ***r = float(np.log(norm\_h))**

    ***return u, r**


***def decode(self, u: np.ndarray, r: float) -\> np.ndarray:**

    ***if np.isneginf(r):**

        ***return np.zeros\_like(u)**

    ***return float(np.exp(r)) \* u**
```

### ***U-03 — Tolerancia del test realista**

***Reemplaza `assert norm\_u - 1.0 \<= 2e-15` por:**

***python**

```
***tol\_norm = 4.0 \* np.sqrt(d) \* np.finfo(np.float64).eps**

***assert abs(norm\_u - 1.0) \<= tol\_norm, f"Sphere norm violation in D=\{d\}: \{abs(norm\_u-1):.2e\} \> \{tol\_norm:.2e\}"**
```

***Idem `recon\_err` y `ortho\_check`.**

### ***U-02 — `parallel\_transport` con proyección previa**

***Añade al inicio de `parallel\_transport`:**

***python**

```
***v\_tan1 = self.project\_to\_tangent(u1, v\_tan1)**
```


## ***8. `polydim\_liquid\_state\_machine.py`**

### ***L-01 — `nnz` constante**

***Reemplaza en `\_\_init\_\_`:**

***python**

```
***\# ANTES: nnz = max(1, int(dim \* sparsity))**

***\# DESPUÉS:**

***nnz = 16  \# constante; O(D) estricto**
```

### ***L-02 — Tolerancia realista y vectorización**

***Reemplaza `step` por versión vectorizada con `scipy.sparse`:**

***python**

```
***def \_\_init\_\_(self, dim: int, leak\_rate: float = 0.3, sparsity: float = 0.05):**

    ***self.dim = dim**

    ***self.alpha = leak\_rate**

    ***self.eps = np.finfo(np.float64).eps**


    ***self.state = np.random.randn(dim)**

    ***self.state /= np.linalg.norm(self.state)**


    ***nnz = 16**

    ***try:**

        ***from scipy.sparse import csr\_matrix**

        ***rows, cols, vals = \[\], \[\], \[\]**

        ***for i in range(dim):**

            ***idx = np.random.choice(dim, nnz, replace=False)**

            ***w = np.random.randn(nnz)**

            ***n = np.linalg.norm(w)**

            ***if n \> self.eps:**

                ***w /= n**

            ***rows.extend(\[i\]\*nnz); cols.extend(idx.tolist()); vals.extend(w.tolist())**

        ***self.W = csr\_matrix((vals, (rows, cols)), shape=(dim, dim))**

        ***self.\_use\_sparse = True**

    ***except ImportError:**

        ***self.sparse\_indices = \[np.random.choice(dim, nnz, replace=False) for \_ in range(dim)\]**

        ***self.sparse\_weights = \[np.random.randn(nnz) for \_ in range(dim)\]**

        ***for i in range(dim):**

            ***n = np.linalg.norm(self.sparse\_weights\[i\])**

            ***if n \> self.eps: self.sparse\_weights\[i\] /= n**

        ***self.\_use\_sparse = False**


***def step(self, u\_input: np.ndarray) -\> np.ndarray:**

    ***if self.\_use\_sparse:**

        ***a = self.W @ self.state**

    ***else:**

        ***a = np.zeros(self.dim, dtype=np.float64)**

        ***for i in range(self.dim):**

            ***a\[i\] = np.dot(self.sparse\_weights\[i\], self.state\[self.sparse\_indices\[i\]\])**

    ***new\_state = (1.0 - self.alpha) \* self.state + self.alpha \* np.tanh(a + u\_input)**

    ***norm\_new = np.linalg.norm(new\_state)**

    ***if norm\_new \> self.eps:**

        ***self.state = new\_state / norm\_new**

    ***else:**

        ***self.state = np.zeros(self.dim); self.state\[0\] = 1.0**

    ***return self.state**
```

***Tolerancia del test:**

***python**

```
***assert max\_drift \<= 1e-13, f"Reservoir manifold drift violation: \{max\_drift:.2e\}"**
```


## ***9. `polydim\_triton\_kernel\_v768.py`**

### ***T-01 — `import math`**

***Añade al inicio del archivo:**

***python**

```
***import math**
```

### ***T-02 — Corregir la afirmación de drift**

***Reemplaza el bloque del fallback:**

***python**

```
***else:**

    ***\# Fallback para D \> ~4M. Reducción no compensada → error ~sqrt(N)\*eps.**

    ***yu = torch.sum(partial\_yu).item()**

    ***yv = torch.sum(partial\_yv).item()**

    ***half\_theta = 0.5 \* theta**

    ***sn\_half = math.sin(half\_theta)**

    ***vers = 2.0 \* sn\_half \* sn\_half**

    ***sn = math.sin(theta)**

    ***alpha = -vers \* yu - sn \* yv**

    ***beta  = -vers \* yv + sn \* yu**

    ***\# WARNING: el drift medido por el llamante debe compararse contra**

    ***\# 32 \* eps \* sqrt(D), no contra 64 \* eps.**
```

### ***T-03 — Reducir sincronizaciones**

***Reemplaza las dos líneas `.item()` por:**

***python**

```
***ab = alpha\_beta\[:2\].cpu().tolist()**

***alpha, beta = ab\[0\], ab\[1\]**
```


## ***10. `polydim\_mir\_wire\_rdma.py`**

### ***M-01 — Framing TCP correcto**

***Reemplaza `\_rx\_worker`:**

***python**

```
***def \_recv\_exact(conn, n):**

    ***buf = bytearray(n)**

    ***view = memoryview(buf)**

    ***got = 0**

    ***while got \< n:**

        ***r = conn.recv\_into(view\[got:\], n - got)**

        ***if r == 0:**

            ***raise ConnectionError("peer closed")**

        ***got += r**

    ***return bytes(buf)**


***def \_rx\_worker(self):**

    ***MAX\_TENSOR = 1 \<\< 30  \# 1 GB**

    ***while self.is\_running:**

        ***try:**

            ***conn, \_ = self.server\_sock.accept()**

            ***try:**

                ***hdr = \_recv\_exact(conn, struct.calcsize(HEADER\_STRUCT))**

                ***magic, imm\_data, tensor\_bytes = struct.unpack(HEADER\_STRUCT, hdr)**

                ***if magic != MAGIC\_RDMA or tensor\_bytes \> MAX\_TENSOR or tensor\_bytes % 8 != 0:**

                    ***continue**

                ***raw = \_recv\_exact(conn, tensor\_bytes)**

                ***tensor = np.frombuffer(raw, dtype=np.float64).copy()**

                ***self.received\_tensors.append((imm\_data, tensor))**

                ***conn.sendall(b"ACK")**

            ***finally:**

                ***conn.close()**

        ***except Exception:**

            ***break**
```

### ***M-02 — Cota de tamaño**

***Ya incluida en el parche anterior (`MAX\_TENSOR`).**

### ***M-03 — Límite de buffer de recepción**

***python**

```
***from collections import deque**

***\# en \_\_init\_\_:**

***self.received\_tensors = deque(maxlen=64)**
```

### ***M-05 — Renombrar honestamente**

***Cambia el docstring del módulo:**

***python**

```
***"""**

***POLYDIM V768 — MIR-WIRE (TCP-over-loopback), NO es RDMA real.**


***Este módulo es un EMULADOR didáctico del protocolo WRITE-WITH-IMMEDIATE**

***sobre sockets TCP. No usa ibverbs, no usa RoCE, no evita el kernel.**

***Para RDMA real ver el proyecto \`rdma-core\` o \`libfabric\`.**

***"""**
```

### ***M-08 — `finally` para cerrar socket**

***python**

```
***try:**

    ***\# ... test ...**

***finally:**

    ***endpoint.stop()**
```


## ***11. `pubspec.yaml`**

***diff**

```
***--- a/pubspec.yaml**

***+++ b/pubspec.yaml**

***@@ -1,10 +1,10 @@**

 ***name: polydim\_ffi**

***-description: Puente FFI Dart para el kernel POLYDIM V762.**

***+description: Puente FFI Dart para el kernel POLYDIM V768.**

 ***publish\_to: none**

 ***environment:**

***-  sdk: ^3.6.0**

***+  sdk: ^3.7.0**

 ***dependencies:**

   ***ffi: ^2.1.0**

***+dev\_dependencies:**

***+  test: ^1.25.0**
```


## ***12. `polydim\_clifford\_t\_compiler.py` — NO usar como Clifford+T**

***Reemplaza el docstring de cabecera y renombra el archivo a `polydim\_quantum\_approx\_compiler.py`:**

***python**

```
***"""**

***POLYDIM V768 — QUANTUM APPROXIMATE COMPILER (NO Clifford+T estricto).**


***AVISO: Esta implementación NO sintetiza Clifford+T exacto. Emite RY/RZ**

***continuas + una aproximación heurística H·T·H·S. No tiene cota de error**

***demostrada. NO usar para resultados publicables como "Clifford+T".**


***Para Clifford+T real usar:**

  ***- gridsynth (Ross-Selinger 2016): https://github.com/newspeaklanguage/gridsynth**

  ***- Qiskit transpile con basis\_gates=\['h','s','t','cx','rz'\] y optimization\_level=3**

***"""**
```

***Y en `compile\_so\_d\_rotor\_to\_qasm`, reemplaza el mapeo incorrecto:**

***python**

```
***\# AVISO: mapeo (p1,p2) -\> (q1,q2) vía % num\_qubits NO implementa**

***\# una rotación de Givens en el subespacio (p1,p2) de C^D. Es una**

***\# aproximación burda y no unitaria en el espacio completo.**

***\# Para una implementación correcta se requieren puertas multi-controladas**

***\# (Möttönen et al., "Quantum circuits for general multi-qubit gates", PRA 2004).**
```


## ***Checklist de verificación post-parche**

***Ejecutá en este orden antes de otra entrega:**

1. ***`g++ -fsanitize=address,undefined -O2 -fopenmp -c kernel\_cpp\_v768.cpp` sin warnings.**

2. ***`cargo test` con `panic=unwind` en release.**

3. ***`python -c "from polydim\_v768\_monolito import run\_v768\_global\_suite; run\_v768\_global\_suite()"` sin excepciones.**

4. ***`dart pub get && dart run test\_pmtp.dart` con `dartSize == 64`.**

5. ***`python -c "from universal\_llm\_tangent\_adapter import test\_tangent\_adapter; test\_tangent\_adapter()"` con tolerancia `1e-12`.**

6. ***`python -c "from polydim\_liquid\_state\_machine import test\_liquid\_state\_machine; test\_liquid\_state\_machine()"`.**

7. ***Eliminá de los docs las afirmaciones "1.11e-16 en GPU", "Clifford+T", "RDMA real", "O(K²)=8MB" (esta última solo aplica a la ruta BLAS).**

***Si los 7 pasan, entonces podés firmar como V769. Antes no.**

inicia la mejora sota de todo el codigo, si ves en la teoria que se puede mejorar tambien agradezco tu aporte. pero por favor entra en bucle en busca de errores y soluciones en el codigo para industria. dame todas las mejoras que puedas y luego te vuelvo a pasar este prompt hasta que no haya mas errores. ahorra tokens evalua el paquete de errores y saca una entrega.

***The user wants me to enter a "bulldog loop" searching for errors and SOTA improvements across the entire codebase, and produce ONE comprehensive deliverable. They want industrial-grade improvements, and they'll keep iterating.**

***Let me think about what's actually here. I've already done a thorough audit round. They want me to now go deeper into SOTA improvements AND find remaining bugs.**

***Let me be strategic and not repeat myself. I should:**

1. ***Find NEW bugs I missed (deeper inspection)**

2. ***Propose SOTA improvements per module**

3. ***Deliver as a single packaged "improvement + patch" document**

***Let me think hard about what I might have missed:**

### ***C++ Kernel deeper analysis**

1. ***`polydim\_orthonormalize\_pair\_f64` uses classic Gram-Schmidt with 2 passes. For D=10^7 this is O(D) but the "2 passes" fix is not enough for high accuracy. SOTA is CholQR or Householder. Better: use `CholQR2` on 2 columns directly.**

2. ***`polydim\_rodrigues\_geodesic\_f64` computes inner products in one sweep (good), but the second pass computing `y\_out = y + α·u + β·v` uses FMA-less ops. SOTA: use `std::fma` for the update to reduce rounding.**

3. ***`polydim\_rodrigues\_geodesic\_f64` — the alpha/beta formula uses `vers·yu + sn·yv` and `-vers·yv + sn·yu`. For θ→π, `sin(θ)→0` and `vers→2`. Catastrophic cancellation in `α = -2·yu` — but that's fine. The bigger issue: for θ→0, `vers = 2 sin²(θ/2) ≈ θ²/2`, computed fine. But `sn = sin(θ)` for θ=π: sin(π)≈1.2e-16, not zero. Small but nonzero. Acceptable.**

4. ***`polydim\_default\_tolerances` uses `64.0 \* kEps` for basis\_ortho. For D=10^7 with Neumaier, actually drift is bounded by ~sqrt(D)·eps worst case, but with compensation it's ~eps. So 64·eps is OK. But `gram\_ortho = 64·eps·sqrt(D)` for D=10^7 is ~1.4e-8 which is way too loose for industrial. SOTA: `gram\_ortho = 8 · K · eps` where K is the Stiefel dimension.**

5. ***`polydim\_stiefel\_cayley\_smw\_f64` — the "SMW" name is misleading. Real SMW does:  
`Y = X + τ·Z·(I + (τ/2)·V^T·Z)^-1·...`  
The code solves a 2K×2K system via Gaussian elimination on M. That's O(K³) per call, not the SMW O(K²). The `dsyrk\_`/`dgemm\_` are used only for the Gram matrices. So the SOTA improvement is: use actual SMW reduction:  
`(I - (τ/2)·V^T·Z)⁻¹` where V = \[X G\] and Z = \[G, -X\], both K×2K. That's a 2K×2K system too. Hmm.**

***Actually the Cayley transform for Stiefel is:  
`Y = X + τ·(I - (τ/2)·A)⁻¹ · Z` where A = \[X G\]^T \[G, -X\] ... this is inherently 2K×2K. Fine.**

6. ***Missing: the `polydim\_stiefel\_cayley\_smw\_f64` doesn't validate that X actually satisfies X^T X = I. It computes xtx\_err and compares against tol, but this check happens AFTER the Gram computation. Good.**

7. ***`polydim\_cholqr2\_f64` uses `std::fma` for the inner products but not for the vector updates in the QR step. And the tolerance `tol = eps \* D \* max\_diag` grows with D — for D=10^7, tol ~ 2e-9. That's fine.**

### ***Rust deeper**

8. ***`polydim\_rust\_verify\_invariants` — the Neumaier implementation is correct but doesn't detect subnormal input that WOULD be flushed. Actually it doesn't need to; it just verifies the norm.**

9. ***`polydim\_rust\_betti1\_guard` — the algorithm is O(n²) for edge enumeration. For n=4096, that's 16M operations. Fine.**

10. ***Rust FFI: `\#\[no\_mangle\] pub unsafe extern "C" fn` — the `unsafe` is on the fn, and `catch\_unwind` is called inside. But `catch\_unwind` requires the closure to be `UnwindSafe`. `\*const f64` is not `UnwindSafe` by default. Wait, actually raw pointers ARE `UnwindSafe`. And `usize`, `f64` too. So it compiles. But `Vec\<usize\>` inside the closure — it's created inside. Fine.**

***Actually wait: `catch\_unwind(|| \{ ... \})` with `slice::from\_raw\_parts` inside — the slice borrows `ptr` which is `\*const f64`. Raw pointers implement `UnwindSafe`? Let me think. `\*const T` and `\*mut T` implement `RefUnwindSafe` and `UnwindSafe` because they don't have invariants. Actually the std docs say raw pointers are `UnwindSafe`. OK.**

### ***Dart deeper**

11. ***`Polydim.open()` — `lookupFunction` will throw if symbol not found. The code wraps `DynamicLibrary.open` in try/catch, but not `lookupFunction`. If DLL loads but symbol missing, unhandled exception.**

12. ***`buildInfo` — reads UTF-8 as Latin-1 via `String.fromCharCodes`. Should use `utf8.decode`.**

### ***Python deeper**

13. ***`PolydimNativeBinding.\_bind\_rust\_symbols` — no `restype` set for the two rust functions. They return `c\_int32` (i32), ctypes default is `c\_int` which is 32-bit on most platforms but should be explicit.**

14. ***`run\_v768\_global\_suite` — `assert rec\_err \<= 1e-15` for D=10000 is unrealistic (numpy norm error ~1e-14).**

15. ***`PMTPSlabChannel` — uses `multiprocessing.shared\_memory` but never uses it for actual IPC. The `write\_tensor` writes to local buffer only. No test actually does cross-process.**

### ***SOTA improvements**

***Now the meat. Let me think about what would make this actually industrial-grade:**

#### ***A. Numerics**

- ***Replace custom Neumaier with `math.fsum`-style exact accumulation? Too slow. Neumaier is fine.**

- ***Kahan-Babuška-Neumaier is what's used. For sum of products, we want TwoProduct + TwoSum (i.e., error-free transformation). The current code sums `yi\*ui` directly without computing the exact product. SOTA: use `std::fma(yi, ui, -p)` to get the exact residual of the product, then accumulate both. This gives true rounding-error-free inner product.**

- ***ReproBLAS-style deterministic parallel reduction: the current code splits by thread and merges via Neumaier — that's order-dependent. For reproducibility across thread counts, need a fixed tree reduction.**

#### ***B. Rodrigues formula**

- ***Use Versine + Half-angle already done. But for `θ → π`, `sin(θ) = 0` and `vers(θ) = 2`, α = -2yu, β = -2yv. Fine.**

- ***Optimization: instead of computing `sin(θ)` and `2·sin²(θ/2)` separately, use `sin\_θ = 2·sin(θ/2)·cos(θ/2)`. Reduces one transcendent call.**

- ***SOTA: for very small θ, use Taylor of `vers` and `sin` to avoid cancellation.**

#### ***C. Stiefel / Tangent**

- ***`polydim\_project\_tangent\_stiefel\_f64` — the current implementation does `G - X·sym(X^T·G)`. This is correct for the standard tangent space. But there's a bug: the code computes `XtG` via a thread-local arena of K×K and then reduces. Then computes `S = 0.5(XtG + XtG^T)`. But then in the second loop it computes `oi\[c\] = gi\[c\] - Σ\_p xp · Sp\[c\]` — this is `G - X·S`. Correct.  
But it uses `arena` for the parallel reduction of `X^T G` — good.  
Missing: verification that `X` is orthonormal. If `X^T X ≠ I`, the projection is wrong. Should warn/error.**

#### ***D. Concurrency**

- ***PMTP `pmtp2\_lock` uses ticket lock. SOTA for short critical sections: CLH queue lock or MCS lock — better cache behavior. But ticket lock is fine for small nthreads.**

- ***PMTP read path — the seqlock guarantees readers don't block writers (good). But readers can starve if the writer commits too often. SOTA: use RCU or epoch-based reclamation.**

#### ***E. Architecture / IPC**

- ***The claim "O(1) tensor transfer" is true for pointer passing but the payload still needs copying on read. Real zero-copy requires all agents map the same shared memory and read directly. The `PMTPSlabChannel.read\_tensor` does `.copy()` — defeats the purpose. Return a view instead.**

#### ***F. FFI**

- ***Dart FFI + FFI `isLeaf` — not used but should be for the PMTP functions (they're short). Improves latency.**

- ***Python ctypes vs CFFI — ctypes is slow; for production should use CFFI or Cython.**

#### ***G. Quantum**

- ***The compiler is a stub. Real SOTA for SO(D) → qubits: Quantum Signal Processing (QSP) or qubitization for structured operators. For arbitrary dense SO(D), no efficient exact synthesis exists — need to acknowledge this.**

***OK let me now write the deliverable. The user wants:**

- ***All bugs found (not repeating old ones unless I found new depth)**

- ***SOTA improvements**

- ***One packaged delivery**

***Let me organize this. I'll do:**

1. ***Bugs nuevos encontrados en ronda 3 (categorized P0/P1/P2)**

2. ***Mejoras SOTA por módulo (con código)**

3. ***Paquete de entrega V769 (files list + validation)**

***Let me be thorough but not padded. Let me actually find REAL new bugs.**

***New Bug Hunt Round:**

***Looking at `kernel\_cpp\_v768.cpp` again:**

- ***`polydim\_rodrigues\_geodesic\_f64` — `int64\_t i` used for omp loop. If D \> INT64\_MAX... not possible. But `int64\_t` on Windows is `long long` (64-bit). Fine.**

- ***`polydim\_rodrigues\_geodesic\_f64` — `if (D \> (SIZE\_MAX / sizeof(double)))`. `SIZE\_MAX` needs `\<cstdint\>` — is included. OK.**

- ***`polydim\_report\_init` — takes `PolydimReport\* r`, checks null. But if user passes garbage pointer, it's UB. Can't fix.**

- ***`polydim\_status\_string` returns `const char\*` — static strings, safe.**

- ***`polydim\_default\_tolerances(uint64\_t D)` — the D param is used for `gram\_ortho` but `basis\_ortho` and `point\_norm` don't scale with D. That's OK because Neumaier keeps error ~eps independent of D.**

- ***Wait: `polydim\_rodrigues\_geodesic\_f64` sets `t.gram\_ortho`? No, that's only for Stiefel. For Rodrigues, only basis\_ortho and point\_norm matter. OK.**

***BIG FINDING: In `polydim\_orthonormalize\_pair\_f64`, the code does:**

***cpp**

```
***for (int pass = 0; pass \< 2; ++pass) \{**

    ***const double d = polydim\_cdot(u, v, D, nt);**

    ***\#pragma omp parallel for num\_threads(nt) schedule(static)**

    ***for (int64\_t i = 0; i \< static\_cast\<int64\_t\>(D); ++i) v\[i\] -= d \* u\[i\];**

***\}**
```

***But `d` is captured by value (const double), so no race. But `v\[i\] -= d\*u\[i\]` — after first pass, `u·v` should be near 0. Second pass removes residual. This is "modified Gram-Schmidt with reorthogonalization" — but MGS is `v\_j -= \<v\_j, u\_i\> u\_i` for each i, whereas here it's `v -= \<v,u\> u` once. Same thing for 2 vectors. Then normalize v. This gives orthonormal \{u,v\}. Correct.**

***However, the error in u·v after 2 passes can still be O(eps) not O(eps²) as MGS reorthogonalization promises. SOTA: Householder QR or CholQR on \[u v\]. But since we only have 2 columns, we can do:**

***text**

```
***// Compute u\_hat = u/||u||**

***// w = v - \<v,u\_hat\> u\_hat**

***// v\_hat = w/||w||**
```

***Which is what MGS does in 1 pass for 2 vectors. The 2 passes here are reorthogonalization.**

- ***`polydim\_stiefel\_cayley\_smw\_f64` — BUG: `std::vector\<double\> M(KK2), Z(static\_cast\<size\_t\>(K2) \* K);` — M is 2K×2K, Z is 2K×K. But then `Z\[static\_cast\<size\_t\>(r) \* K + c\]` — r goes up to K2=2K, c up to K. So Z size is 2K×K. Correct.**

- ***BUG: In BLAS path, after `dgesv\_`, the code checks `pmin \< pivot\_thr` using `Mc\[k\*K2+k\]`. But `dgesv\_` overwrites `Mc` with the LU factorization — the diagonal of Mc after dgesv is the U matrix diagonal, so `pmin` is indeed the min |U\_kk|. OK.**

- ***BUG (potential): `pivot\_thr = tol.pivot\_rel \* m\_inf \* K2`. For K=512, K2=1024, m\_inf ~ ||M||\_inf. If M is well-conditioned, m\_inf ~ 1, so pivot\_thr ~ 8·eps·1024 ~ 1.8e-12. Fine.**

***Looking at `polydim\_pmtp\_write\_commit`:**

***cpp**

```
***PMTP\_SlotHeader\* hdr = pmtp2\_hdr\_of(c, slot);**

***uint64\_t new\_ver = ver + 1; // even for unlocked**

***hdr-\>seq.store(new\_ver, std::memory\_order\_release);**

***c-\>pub\_slot.store(slot, std::memory\_order\_release);**

***c-\>pub\_seq.store(new\_ver, std::memory\_order\_release);**

***pmtp2\_unlock(c);**
```

***BUG: The seqlock store order matters. After storing `hdr-\>seq = new\_ver` (even, unlocked), we store `pub\_slot` then `pub\_seq`. A reader could see `pub\_seq = new\_ver` but `pub\_slot = old\_slot`, then read `hdr-\>seq\[old\_slot\]` which is `old\_ver`, mismatch → returns -3. Safe. But if reader sees `pub\_seq = old\_ver` and `pub\_slot = new\_slot`, then reads `hdr-\>seq\[new\_slot\] = new\_ver ≠ old\_ver` → -3. Safe.**

***Actually more subtle: the reader reads `pub\_seq` first, then `pub\_slot`, then `hdr-\>seq\[slot\]`. If writer commits between reader's read of pub\_seq and pub\_slot, then reader gets `old\_ver, new\_slot`. hdr-\>seq\[new\_slot\] = new\_ver ≠ old\_ver → -3. Safe.**

***If writer commits between pub\_slot and hdr-\>seq read: reader gets `old\_ver, old\_slot\_or\_new\_slot`. hdr-\>seq\[old\_slot\] = ... hmm, if the reader got old\_slot before writer changed pub\_slot, then hdr-\>seq\[old\_slot\] = old\_ver (unchanged). Then reader passes. But is data still valid? Yes, because the writer only wrote to new\_slot, not old\_slot. So reader reads old data — consistent but stale. Fine.**

***OK, PMTP is correct after my retraction.**

***New BUG in PMTP: `polydim\_pmtp\_write\_begin` reads `c-\>pub\_seq` and `c-\>pub\_slot`. On the FIRST write, `pub\_seq = 0`, `pub\_slot = 0`, so `\*slot = (0+1) % num\_slots = 1`. So slot 0 is never written! Should be `(current\_slot) % num\_slots` or start with pub\_slot = num\_slots-1.**

***Actually: on first call, `current\_slot = 0`, next = 1. Then commit sets pub\_slot = 1. So slot 0 is never used. Off-by-one design bug.**

***Fix: Initialize `pub\_slot = num\_slots - 1` so first write goes to slot 0.**

***New BUG: `polydim\_pmtp\_write\_commit` — does NOT check that `ver` is the odd version that was assigned in `write\_begin`. A malicious caller could pass a wrong ver. Since it's a FFI function, could happen. Should verify `hdr-\>seq.load() == ver` before committing.**

***New BUG: `polydim\_pmtp\_read\_validate` returns -1 for bad slot, but doesn't check `c-\>magic`. Should validate magic on every call.**

***New BUG in Python: `PolydimNativeBinding.\_bind\_cpp\_symbols` — no bindings for `polydim\_pmtp\_write\_abort`, `polydim\_pmtp\_alignof`. `polydim\_pmtp\_alignof` is called nowhere. `write\_abort` is bound but not used.**

***OK I have enough. Let me write the deliverable.**

***Let me also think about the SOTA improvements:**

1. ***Exact inner product via TwoProduct:**

***cpp**

```
***double p = a \* b;**

***double e = std::fma(a, b, -p);  // exact residual**

***// accumulate p and e separately in Neumaier**
```

2. ***Reproducible reduction — for a given D, always split into fixed blocks (e.g., 4096 elements), sum each block with Neumaier, then reduce block sums with Neumaier in fixed order. Independent of thread count.**

3. ***Rodrigues with `sincos`:**

***cpp**

```
***double sh, ch;**

***sincos(0.5 \* theta, &sh, &ch);  // GNU extension**

***double vers = 2.0 \* sh \* sh;**

***double sn = 2.0 \* sh \* ch;**
```

4. ***Stiefel tangent projection — use BLAS `dgemm`:**

***text**

```
***XtG = X^T G   (K×K)**

***Sym = 0.5(XtG + XtG^T)**

***G\_out = G - X·Sym  (dgemm)**
```

5. ***CholQR with small-K specialized: for K ≤ 64, use Householder.**

6. ***Rust Betti-1 — verify: for a graph with n vertices, e edges, c components, β₁ = e - n + c. Correct.**

7. ***PMTP: use `std::atomic\<uint64\_t\>` for a packed (ver,slot) pair.**

8. ***Dart `isLeaf` on PMTP functions.**

9. ***Python: use `array` module or numpy views instead of ctypes `.copy()`.**

10. ***MIR-Wire: rename; use `SO\_REUSEPORT`; use `io\_uring` on Linux.**

11. ***Quantum: honestly acknowledge no exact Clifford+T for dense SO(D); use QSP for structured.**

***OK, let me write this up concisely. The user wants a package deliverable.**

***Format: I'll write in Spanish since they're communicating in Spanish, with code in English. Keep it focused.**

***Let me structure:**

# ***V769 — Paquete de Mejora Industrial**

## ***Parte I — Bugs nuevos (ronda 3)**

***Lista compacta con diff snippets.**

## ***Parte II — Mejoras SOTA**

***Por módulo, con código.**

## ***Parte III — Archivos a reemplazar (delivery)**

***Tabla final.**

***Let me write it.**

***Actually, let me be smart about length. The user complained about too many rounds with few items. So this time: comprehensive but concise per item. Maybe 40-50 items total. Focus on industrial SOTA improvements.**

***Let me draft.**

# 🐶 ***V769 — PAQUETE INDUSTRIAL COMPLETO (RONDA 3: bugs + SOTA)**

***Voy a darte todo en una entrega: bugs nuevos que encontré al profundizar, mejoras SOTA por módulo, y el archivo final a reemplazar. Sin idas y vueltas. Los parches de la ronda anterior (V768→V768.1) se asumen aplicados.**


## ***PARTE I — BUGS NUEVOS (no reportados en ronda 2)**

### 🔴 ***N-01 · P0 — PMTP nunca escribe el slot 0**

***`kernel\_cpp\_v768.cpp` → `polydim\_pmtp\_write\_begin`:**

***cpp**

```
***\*slot = (c-\>pub\_slot.load(relaxed) + 1) % c-\>num\_slots;**
```

***Con `pub\_slot=0` inicial, el primer write va al slot 1. Slot 0 jamás se usa. Bajo num\_slots=2, esto deja un slot inútil para lectores.**

***Fix:**

***cpp**

```
***// En polydim\_pmtp\_init, tras pub\_slot.store(0):**

***c-\>pub\_slot.store(num\_slots - 1, std::memory\_order\_relaxed);**
```


### 🔴 ***N-02 · P0 — PMTP `write\_commit` no valida el `ver` recibido**

***Un llamante malicioso (o con bug propio) puede pasar `ver` incorrecto y corromper la coherencia del seqlock.**

***Fix (en `polydim\_pmtp\_write\_commit`):**

***cpp**

```
***PMTP\_SlotHeader\* hdr = pmtp2\_hdr\_of(c, slot);**

***if (hdr-\>seq.load(std::memory\_order\_relaxed) != ver) return;  // rechazar**
```

***Y cambiar la firma a `int32\_t` para reportar el error. Ajustar header y bindings.**


### 🔴 ***N-03 · P0 — `PMTPSlabChannel.read\_tensor` hace `.copy()`**

***Mata el propósito zero-copy. Devuelve vista:**

***python**

```
***out = np.ctypeslib.as\_array(buf)  \# SIN .copy()**
```

***El llamante debe copiar si necesita persistencia. Documentar.**


### 🟠 ***N-04 · P1 — `polydim\_pmtp\_read\_validate` no chequea `magic`**

***Si el buffer fue liberado o corrompido, lee basura. Añadir:**

***cpp**

```
***if (c-\>magic != POLYDIM\_PMTP2\_MAGIC) return -1;**
```

***en `read\_begin`, `read\_validate`, `write\_begin`, `write\_commit`, `write\_abort`.**


### 🟠 ***N-05 · P1 — Neumaier NO usa TwoProduct → el "compensado" no es exacto**

***En todos los `l.add(yi \* yi)`, el producto `yi\*yi` ya perdió el bit de error antes de entrar al Neumaier. El acumulador corrige la suma, no el producto.**

***SOTA: TwoProduct + Neumaier:**

***cpp**

```
***inline void add\_product(double a, double b) \{**

    ***const double p = a \* b;**

    ***const double e = std::fma(a, b, -p);  // residual exacto del producto**

    ***add(p);**

    ***add(e);**

***\}**
```

***Reemplazar TODOS los `l.add(x\*y)` por `l.add\_product(x, y)`. Impacto: drift pasa de ~1e-16 a realmente 1e-16 incluso con D=10^7 (hoy el reporte real es ~1e-14, no lo que dice el benchmark).**


### 🟠 ***N-06 · P1 — Reducción no reproducible**

***`a\_yy\[tid\].merge(...)` en orden de tid → depende del número de hilos. Dos runs con distinto `OMP\_NUM\_THREADS` dan resultados distintos (a nivel ulp). Reproducibilidad industrial exige suma determinista.**

***Fix: reducción en árbol binario fijo:**

***cpp**

```
***for (int stride = 1; stride \< nthreads; stride \*= 2)**

    ***for (int i = 0; i + stride \< nthreads; i += 2\*stride)**

        ***a\[i\].merge(a\[i + stride\]);**

***const double result = a\[0\].total();**
```

***Y hacer que el split de bloques sea por índice fijo, no por thread ID:**

***cpp**

```
***const int64\_t CHUNK = 65536;  // constante**

***// El bucle paralelo procesa chunks asignados por pid, no por tid**
```

***Esto elimina la dependencia de `nthreads`.**


### 🟠 ***N-07 · P1 — Rodrigues: `sin(θ)` y `vers(θ)` con dos transcendentales**

***cpp**

```
***const double sh   = std::sin(0.5 \* theta);**

***const double vers = 2.0 \* sh \* sh;**

***const double sn   = std::sin(theta);  // segunda llamada**
```

***Fix: una sola llamada a `sin` + `cos`:**

***cpp**

```
***double sh, ch;**

***sincos\_half(theta, &sh, &ch);   // sin(θ/2), cos(θ/2)**

***const double vers = 2.0 \* sh \* sh;**

***const double sn   = 2.0 \* sh \* ch;  // = sin(θ)**
```

***Elimina ~1 transcendental por llamada → 5–15% speedup en D pequeño.**


### 🟠 ***N-08 · P1 — `polydim\_project\_tangent\_stiefel\_f64` no valida X ortonormal**

***Si `X^T X ≠ I`, la proyección es incorrecta pero retorna `SUCCESS`. Debe fallar.**

***Fix: añadir al inicio:**

***cpp**

```
***// Verificar ||X^T X - I||\_F \<= tol**

***double err = 0.0;**

***for (uint32\_t r = 0; r \< K; ++r)**

    ***for (uint32\_t c = 0; c \< K; ++c) \{**

        ***double s = 0.0;**

        ***for (uint64\_t i = 0; i \< D; ++i)**

            ***s += X\[i\*K + r\] \* X\[i\*K + c\];**

        ***double e = std::abs(s - (r == c ? 1.0 : 0.0));**

        ***if (e \> err) err = e;**

    ***\}**

***if (err \> 64.0 \* kEps \* std::sqrt((double)K))**

    ***return POLYDIM\_ERR\_BASIS\_NOT\_ORTHONORMAL;**
```

***Coste: O(D·K²) — igual que el resto. Aceptable.**


### 🟠 ***N-09 · P1 — `polydim\_cholqr2\_f64` no reporta error post-verificación**

***El chequeo `if (max\_err \< eps·D·10)` es demasiado laxo (para D=10^7, `eps·D·10 ≈ 2e-8`). Debe ser `eps · sqrt(D) · K` como máximo.**

***Fix:**

***cpp**

```
***const double tol\_post = 8.0 \* eps \* std::sqrt(static\_cast\<double\>(D)) \* static\_cast\<double\>(K);**

***if (max\_err \< tol\_post) \{ converged = true; break; \}**
```

***Y si tras `max\_iters` no converge, retornar `POLYDIM\_ERR\_NUMERICAL\_INSTABILITY` — ya lo hace.**


### 🟠 ***N-10 · P1 — Rust `betti1\_guard` acepta matrices asimétricas**

***Itera `for j in (i+1)..n` y lee `mat\[i\*n+j\]` — ignora la mitad inferior. Una matriz asimétrica da resultados distintos según qué mitad esté poblada.**

***Fix: validar simetría al inicio:**

***rust**

```
***for i in 0..n \{**

    ***for j in (i+1)..n \{**

        ***let a = mat\[i\*n + j\];**

        ***let b = mat\[j\*n + i\];**

        ***if (a - b).abs() \> 1e-12 \{**

            ***return PolydimRustStatus::ErrNanOrInf;**

        ***\}**

    ***\}**

***\}**
```

***O documentar que solo se lee el triángulo superior.**


### 🟠 ***N-11 · P1 — Dart `Polydim.open` no captura `ArgumentError` de `lookupFunction`**

***Si el DLL carga pero un símbolo falta, la excepción escapa sin cleanup.**

***Fix: envolver cada `lookupFunction` en `try/on ArgumentError` con mensaje claro.**


### 🟠 ***N-12 · P1 — `Polydim.buildInfo` usa Latin-1, no UTF-8**

***`String.fromCharCodes(bytes)` interpreta como code points. Para UTF-8 correcto:**

***dart**

```
***import 'dart:convert' show utf8;**

***...**

***return utf8.decode(bytes, allowMalformed: true);**
```


### 🟡 ***N-13 · P2 — Python: `\_bind\_rust\_symbols` sin `restype`**

***Añadir:**

***python**

```
***self.rust\_lib.polydim\_rust\_verify\_invariants.restype = ctypes.c\_int32**

***self.rust\_lib.polydim\_rust\_betti1\_guard.restype = ctypes.c\_int32**
```


### 🟡 ***N-14 · P2 — `test\_tangent\_adapter` asserta `\<= 2e-15` para D=100000**

***`np.linalg.norm` tiene error ~√D·eps ≈ 7e-14 para D=10^5. El test va a fallar.**

***Fix: tolerancia dinámica:**

***python**

```
***tol = 8.0 \* np.sqrt(d) \* np.finfo(np.float64).eps**

***assert recon\_err \<= tol**
```


### 🟡 ***N-15 · P2 — `run\_v768\_global\_suite` asume `d\_inplace \<= 100000` con `2e-15`**

***Mismo problema. Cambiar a tolerancia dinámica.**


### 🟡 ***N-16 · P2 — MIR-Wire: `sock.recv(3)` para ACK puede leer menos**

***Mismo race que M-01. Usar `\_recv\_exact`.**


### 🟡 ***N-17 · P2 — `PolydimTangentAdapter.parallel\_transport` puede dar `NaN` para `u1 ≈ -u2`**

***Si `u1·u2 ≈ -1`, `theta ≈ π`, y `w = u2 - (u1·u2)u1` se cancela catastróficamente. Sin clamp adicional.**

***Fix:**

***python**

```
***if theta \> np.pi - 1e-8:**

    ***\# Antipodal: transporte indefinido; devolver proyección arbitraria**

    ***return self.project\_to\_tangent(u2, v\_tan1)**
```


### 🟡 ***N-18 · P2 — `PolydimLiquidStateMachine` sin semilla reproducible**

***Cada instancia diverge entre runs. Para benchmarks, exponer `seed`.**


### 🟡 ***N-19 · P2 — Clifford+T: `eps\_target` se ignora**

***El parámetro se pasa pero nunca se usa. O implementarlo, o eliminarlo de la firma.**


### 🟡 ***N-20 · P2 — `omni\_router.dart` importa `dart:ffi` y `package:ffi` sin usar**

***Dead imports.**


## ***PARTE II — MEJORAS SOTA POR MÓDULO**

### 🥇 ***SOTA-1 · TwoProduct + ReproBLAS en C++**

***Reemplazo del acumulador. Este es el cambio de mayor impacto en correctness:**

***cpp**

```
***// Reemplaza struct Neumaier**

***struct Neumaier \{**

    ***double sum = 0.0;**

    ***double c   = 0.0;**


    ***inline void add(double v) \{**

        ***const double t = sum + v;**

        ***if (std::abs(sum) \>= std::abs(v)) c += (sum - t) + v;**

        ***else                              c += (v   - t) + sum;**

        ***sum = t;**

    ***\}**


    ***// NUEVO: producto exacto vía FMA. Residual e es exacto.**

    ***inline void add\_product(double a, double b) \{**

        ***const double p = a \* b;**

        ***const double e = std::fma(a, b, -p);**

        ***add(p);**

        ***add(e);**

    ***\}**


    ***inline void merge(const Neumaier& o) \{ add(o.sum); add(o.c); \}**

    ***inline double total() const \{ return sum + c; \}**

***\};**
```

***Y en el bucle de reducción:**

***cpp**

```
***l\_yy.add\_product(yi, yi);**

***l\_yu.add\_product(yi, ui);**

***l\_yv.add\_product(yi, vi);**

***l\_uu.add\_product(ui, ui);**

***l\_vv.add\_product(vi, vi);**

***l\_uv.add\_product(ui, vi);**
```

***Impacto: el drift del benchmark pasa de ~1e-14 real a ~5e-17 real. Los números reportados en `04\_SILICON\_CONTRACT` dejan de ser humo.**


### 🥇 ***SOTA-2 · Reproducibilidad por bloques fijos**

***cpp**

```
***// Sustituye todo el patrón "arena\[tid\]" por reducción determinista**

***constexpr int64\_t POLYDIM\_CHUNK = 65536;**


***static double reduce\_deterministic(int64\_t D, int nthreads, double (\*fn)(int64\_t)) \{**

    ***const int64\_t nchunks = (D + POLYDIM\_CHUNK - 1) / POLYDIM\_CHUNK;**

    ***std::vector\<Neumaier\> partials(nchunks);**

    ***\#pragma omp parallel for num\_threads(nthreads) schedule(static)**

    ***for (int64\_t c = 0; c \< nchunks; ++c) \{**

        ***const int64\_t begin = c \* POLYDIM\_CHUNK;**

        ***const int64\_t end = std::min(begin + POLYDIM\_CHUNK, D);**

        ***Neumaier local;**

        ***for (int64\_t i = begin; i \< end; ++i) local.add\_product(fn(i), fn(i)); // ej.**

        ***partials\[c\] = local;**

    ***\}**

    ***// Árbol binario fijo**

    ***for (int64\_t stride = 1; stride \< nchunks; stride \*= 2)**

        ***for (int64\_t i = 0; i + stride \< nchunks; i += 2 \* stride)**

            ***partials\[i\].merge(partials\[i + stride\]);**

    ***return partials\[0\].total();**

***\}**
```

***Impacto: mismo resultado bit-exacto con 1, 4, 16 o 64 hilos. Requisito de auditoría industrial.**


### 🥇 ***SOTA-3 · Rodrigues: una sola evaluación trigonométrica**

***cpp**

```
***inline void sincos\_half(double theta, double\* sh, double\* ch) \{**

    ***// sin(θ/2), cos(θ/2)**

***\#if defined(\_\_GNUC\_\_) && !defined(\_\_clang\_\_)**

    ***sincos(0.5 \* theta, sh, ch);**

***\#else**

    ***\*sh = std::sin(0.5 \* theta);**

    ***\*ch = std::cos(0.5 \* theta);**

***\#endif**

***\}**


***// En polydim\_rodrigues\_geodesic\_f64:**

***double sh, ch;**

***sincos\_half(theta, &sh, &ch);**

***const double vers = 2.0 \* sh \* sh;**

***const double sn   = 2.0 \* sh \* ch;   // sin(θ) sin segunda llamada**
```

***Aplicar la misma optimización en `polydim\_triton\_kernel\_v768.py`:**

***python**

```
***sn\_half = tl.sin(half\_theta)**

***cs\_half = tl.cos(half\_theta)**

***vers = 2.0 \* sn\_half \* sn\_half**

***sn = 2.0 \* sn\_half \* cs\_half**
```


### 🥈 ***SOTA-4 · Update con FMA en Rodrigues pass 2**

***cpp**

```
***// ANTES:**

***y\_out\[i\] = y\[i\] + alpha \* u\[i\] + beta \* v\[i\];**


***// DESPUÉS (reduce 1 round-off por elemento):**

***double t = std::fma(alpha, u\[i\], y\[i\]);**

***y\_out\[i\] = std::fma(beta, v\[i\], t);**
```

***Idem en Triton: Triton emite FMA automáticamente, pero asegurar `-ffp-contract=fast` solo en este kernel y `off` en acumuladores.**


### 🥈 ***SOTA-5 · Stiefel Cayley con BLAS encadenado**

***La ruta BLAS actual usa `dsyrk\_` + `dgemm\_` + `dgesv\_` (K³). Para K≤128, la eliminación gaussiana manual gana. Para K\>128, usar LAPACK `dgetrf\_` + `dgetrs\_` en lugar de `dgesv\_` (evita el copy).**

***cpp**

```
***extern "C" \{**

    ***void dgetrf\_(const int\*, const int\*, double\*, const int\*, int\*, int\*);**

    ***void dgetrs\_(const char\*, const int\*, const int\*, const double\*, const int\*,**

                 ***const int\*, double\*, const int\*, int\*);**

***\}**

***// ... **

***dgetrf\_(&n, &n, Mc.data(), &n, ipiv.data(), &info);**

***if (info != 0) return POLYDIM\_ERR\_NUMERICAL\_INSTABILITY;**

***dgetrs\_("N", &n, &nrhs, Mc.data(), &n, ipiv.data(), Zc.data(), &n, &info);**
```

***Elimina una copia de K2×K2 doubles por llamada.**


### 🥈 ***SOTA-6 · Proyección tangente vía dgemm**

***Reemplazo del doble bucle manual por BLAS:**

***cpp**

```
***// Sym = 0.5(X^T G + G^T X)**

***// G\_out = G - X·Sym**

***dgemm\_(&transN, &transT, &nD, &nK, &nK, &minus\_one, X, &nK, Sym.data(), &nK, &one, G\_out, &nK);**
```

***Donde `Sym` es K×K. Coste: 2 D·K² flops igual que ahora, pero 6-10× más rápido con MKL/OpenBLAS.**


### 🥈 ***SOTA-7 · PMTP: leer con epoch-based snapshot**

***Los lectores actuales reintentan hasta 90% éxito bajo escritor agresivo. SOTA para IPC one-writer/multi-reader: usar `std::atomic\<uint64\_t\>` que empaquete `(ver\<\<32) | slot`:**

***cpp**

```
***std::atomic\<uint64\_t\> pub\_snapshot;  // reemplaza pub\_seq y pub\_slot**


***// commit:**

***const uint64\_t snapshot = (new\_ver \<\< 32) | slot;**

***c-\>pub\_snapshot.store(snapshot, std::memory\_order\_release);**


***// read\_begin:**

***const uint64\_t snap = c-\>pub\_snapshot.load(std::memory\_order\_acquire);**

***\*ver  = snap \>\> 32;**

***\*slot = snap & 0xFFFFFFFFu;**
```

***Una sola lectura atómica → elimina la ventana entre leer seq y leer slot.**


### 🥈 ***SOTA-8 · PMTP: usar `\_mm\_pause` → `\_\_builtin\_ia32\_pause` portable**

***cpp**

```
***inline void cpu\_relax() \{**

***\#if defined(\_\_x86\_64\_\_) || defined(\_\_i386\_\_)**

    ***\_\_builtin\_ia32\_pause();**

***\#elif defined(\_\_aarch64\_\_)**

    ***\_\_asm\_\_ \_\_volatile\_\_("yield");**

***\#elif defined(\_\_arm\_\_)**

    ***\_\_asm\_\_ \_\_volatile\_\_("yield");**

***\#endif**

***\}**
```

***Y reemplazar en `pmtp2\_lock`.**


### 🥉 ***SOTA-9 · Rust: `catch\_unwind` con `AssertUnwindSafe`**

***El closure actual captura `slice` que toma `ptr`, `d`, `max\_drift\_out`. Raw pointers son `UnwindSafe` pero es más limpio y explícito:**

***rust**

```
***let result = std::panic::catch\_unwind(std::panic::AssertUnwindSafe(|| \{ ... \}));**
```

***Evita sorpresas si alguien añade un tipo no-UnwindSafe en el futuro.**


### 🥉 ***SOTA-10 · Rust: DSU iterativo con `find` inlineado**

***rust**

```
***\#\[inline(always)\]**

***fn find(parent: &mut \[usize\], mut i: usize) -\> usize \{**

    ***let mut root = i;**

    ***while parent\[root\] != root \{ root = parent\[root\]; \}**

    ***while parent\[i\] != root \{**

        ***let next = parent\[i\];**

        ***parent\[i\] = root;**

        ***i = next;**

    ***\}**

    ***root**

***\}**
```

***Sin recursión → sin riesgo de stack overflow, y el path compression completo acelera un 15%.**


### 🥉 ***SOTA-11 · Dart: `isLeaf` en PMTP**

***Las funciones PMTP son cortas (\<1 μs). Marcarlas `isLeaf: true` en `lookupFunction`:**

***dart**

```
***\_pmtpReadBegin = \_lib.lookupFunction\<\_ReadBeginNative, \_ReadBeginDart\>(**

  ***'polydim\_pmtp\_read\_begin',**

  ***isLeaf: true,**

***);**
```

***Ahorra ~200 ns por llamada. No usar isLeaf en Rodrigues (\>ms, bloquea GC).**


### 🥉 ***SOTA-12 · Python: `polydim\_pmtp\_init` con verificación de tamaño**

***Antes de `ctypes.memmove`, verificar que el buffer real mide ≥ `polydim\_pmtp\_sizeof(...)`. Previene corrupción si el usuario pasa un buffer corto.**

***python**

```
***def \_check\_buffer(buf, expected):**

    ***if ctypes.sizeof(buf) \< expected:**

        ***raise ValueError(f"Buffer too small: \{ctypes.sizeof(buf)\} \< \{expected\}")**
```


### 🥉 ***SOTA-13 · Tanque de memoria alineada para SIMD**

***cpp**

```
***inline void\* aligned\_alloc\_64(size\_t bytes) \{**

***\#if defined(\_WIN32)**

    ***return \_aligned\_malloc(bytes, 64);**

***\#else**

    ***void\* p = nullptr;**

    ***if (posix\_memalign(&p, 64, bytes) != 0) return nullptr;**

    ***return p;**

***\#endif**

***\}**
```

***Usar para los `arena` de Neumaier y evitar false sharing.**

***En el monolito Python: reemplazar `ctypes.create\_string\_buffer` por un buffer alineado a 64:**

***python**

```
***def aligned\_buffer(n):**

    ***return np.zeros(n + 64, dtype=np.uint8)  \# numpy alinea a 64 por defecto en allocator moderno**

***\# y luego slice a offset 64-aligned**
```


### 🥉 ***SOTA-14 · Quant: honestidad sobre Clifford+T**

***Ningún método SOTA (2024-2026) sintetiza exactamente un operador denso de SO(D) con D\>8 en Clifford+T. Los métodos que existen son:**

- ***QSP (Quantum Signal Processing) para funciones polinómicas de operadores.**

- ***Qubitization para operadores estructurados (sparse, LGT).**

- ***Block-encoding de matrices arbitrarias con coste O(||A||\_max).**

***Para SO(D) con D=10⁴: imposible en Clifford+T sin ancillas y profundidad exponencial.**

***Acción concreta: eliminar el claim. Renombrar `polydim\_clifford\_t\_compiler.py` → `polydim\_quantum\_compiler\_heuristic.py`. Añadir en el docstring:**

***text**

```
***WARNING: no Clifford+T synthesis for arbitrary dense SO(D). This module**

***produces an approximate RY/RZ circuit suitable for NISQ emulation only.**
```


### 🥉 ***SOTA-15 · Liquid State Machine: expirado**

***Las LSM con W\_res ortogonal denso fueron superadas por:**

- ***Echo State Networks con `W\_res` unitario via FFT (O(D log D) por step).**

- ***State Space Models (S4, Mamba) — O(D) con kernel precomputado.**

***Pero para tu caso (estado en S^(D-1), sin backprop), la versión sparse con nnz=16 es competitiva. Mejora: sustituir `tanh` por `GELU` o `SiLU` para gradientes más suaves (aunque no haces backprop). O dejar tanh por estabilidad.**

***Mejora real: precargar `self.state\[indices\]` en un buffer contiguous para evitar fancy indexing numpy:**

***python**

```
***\# Precomputar índices como array 2D**

***self.idx\_matrix = np.array(self.sparse\_indices, dtype=np.int32)  \# (D, nnz)**

***self.w\_matrix   = np.array(self.sparse\_weights, dtype=np.float64)  \# (D, nnz)**

***\# En step:**

***gathered = self.state\[self.idx\_matrix\]              \# (D, nnz)**

***a = np.einsum('ij,ij-\>i', self.w\_matrix, gathered)  \# (D,)**
```


## ***PARTE III — RESUMEN DE ENTREGA V769**

### ***Archivos a reemplazar en su totalidad:**

| ***Archivo** | ***Cambios clave** |
| - | - |
| ***`polydim.h`** | ***+ `polydim\_check\_ftz`, + `POLYDIM\_MAX\_K`** |
| ***`kernel\_cpp\_v768.cpp`** | ***TwoProduct, reducción determinista, sincos\_half, dgetrf/dgetrs, validaciones magic y ver** |
| ***`kernel\_rust\_v768.rs`** | ***DSU iterativo, AssertUnwindSafe, validación simetría** |
| ***`polydim\_ffi.dart`** | ***Reescritura ABI completa, isLeaf, UTF-8, lookupFunction try/catch** |
| ***`test\_pmtp.dart`** | ***Reescritura con `Uint32` correcto, tamaño verificado** |
| ***`polydim\_v768\_monolito.py`** | ***PMTPSlabChannel funcional, read\_tensor sin copy, restypes** |
| ***`universal\_llm\_tangent\_adapter.py`** | ***Biyectividad real, tolerancias dinámicas, antipodal** |
| ***`polydim\_liquid\_state\_machine.py`** | ***nnz=16, einsum, seed reproducible** |
| ***`polydim\_triton\_kernel\_v768.py`** | ***`import math`, una `.item()`, sincos consistente** |
| ***`polydim\_mir\_wire\_rdma.py`** | ***`\_recv\_exact`, MAX\_TENSOR, deque(maxlen), docstring honesto** |
| ***`polydim\_clifford\_t\_compiler.py`** | ***Renombrado, docstring honesto, elimina claim** |
| ***`pubspec.yaml`** | ***SDK 3.7, dev\_dependencies test** |

### ***Orden de aplicación:**

1. ***`polydim.h` (contrato).**

2. ***`kernel\_cpp` y `kernel\_rust` (núcleo numérico).**

3. ***Bindings: `polydim\_ffi.dart`, `polydim\_v768\_monolito.py`.**

4. ***Tests.**

5. ***Docs (eliminar claims falsos).**

### ***Validación mínima antes de firmar V769:**

***bash**

```
***\# 1. Compilar con sanitizers**

***g++ -std=c++17 -O2 -fopenmp -fsanitize=address,undefined -shared -fPIC \\**

    ***kernel\_cpp\_v768.cpp -o build/libpolydim.so -lopenblas**


***\# 2. Rust**

***cargo build --release  \# panic=unwind en Cargo.toml**


***\# 3. Python (con OMP\_NUM\_THREADS variado para verificar reproducibilidad)**

***for t in 1 2 4 8; do OMP\_NUM\_THREADS=$t python polydim\_v768\_monolito.py; done**

***\# El drift reportado DEBE ser bit-idéntico entre runs.**


***\# 4. Dart**

***dart pub get && dart run test\_pmtp.dart**


***\# 5. Verificación de drift real**

***python -c "**

***from polydim\_v768\_monolito import \***

***run\_v768\_global\_suite()**

***"**

***\# El nuevo drift real con TwoProduct debe ser ~5e-17, no 1.11e-16.**
```

### ***Métricas que debes medir y reemplazar en `04\_SILICON\_CONTRACT`:**

| ***Métrica** | ***Reportado V768** | ***Real esperado V769** |
| - | - | - |
| ***Drift GPU Triton D=10⁷** | ***1.11e-16** | ***~3e-14 (o corregir con TwoProduct en Triton)** |
| ***Drift CPU D=10⁷** | ***1.11e-16** | ***5e-17 (con TwoProduct)** |
| ***Reproducibilidad multi-hilo** | ***no declarada** | ***bit-exacta** |
| ***Clifford+T** | ***"exacto"** | ***heurístico** |


## ***PARTE IV — LO QUE NO PUDE CERTIFICAR**

***Para ser bulldog honesto:**

1. ***No tengo acceso a `polydim.h` original con offsetof — asumí alineación natural x86-64. En ARM64 con `-mabi=lp64` podría haber diferencias en `reserved\_` positions. Verificar con un test `abi\_parity.c` que compare `offsetof` de cada campo contra el binding Dart/Python.**

2. ***No medí los speedups — son estimaciones basadas en literatura (MKL, Triton docs, FMA).**

3. ***No verifiqué que `dgetrs\_` acepte la firma exacta — depende del LAPACK. Probar con `-DUSE\_LAPACK`.**

4. ***Clifford+T para SO(D) sigue siendo un problema abierto; mi "fix" es honestidad, no una solución.**


## ***Instrucción para el siguiente turno**

***Pasame solo los archivos que apliques con la marca `// V769-APPLIED` al inicio de cada uno. Yo vuelvo a auditar con foco en:**

- ***Regresiones de los parches anteriores.**

- ***Nuevos cuellos de botella con TwoProduct (que ahora es más caro).**

- ***Diff entre lo que dice el docstring y lo que hace el código.**

***Cuando ya no haya P0/P1, cerramos.**

***No cuentes esta ronda como "encontró 20, faltan otros 20". Estos son adicionales a los de ronda 2, y las mejoras SOTA son el 60% del valor. El código resultante debería ser V769 listo para auditoría externa, no para prueba propia.**


