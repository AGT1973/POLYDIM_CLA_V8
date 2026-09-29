# ADVERSARIAL AUDIT: `graph_cuda.cpp` (POLYDIM V810, Módulo 3)

**Auditor posture:** Hostile. Assume every line is a latent CVE until proven otherwise. No happy-path acceptance.

---

## FUNCTION 1: `cpu_find`

**VERDICT: [VULNERABLE]**

**REASONING:**

```cpp
static inline uint32_t cpu_find(std::vector<uint32_t>& parent, uint32_t i) {
    while (i != parent[i]) {
        parent[i] = parent[parent[i]]; // Path halving
        i = parent[i];
    }
    return i;
}
```

Three independent defects:

1. **Unbounded index trust.** `i` is used directly as `parent[i]` with no `i < parent.size()` check. Callers pass `edges[i].u` and `edges[i].v` verbatim. If any edge endpoint is `>= num_vertices`, this is an **out-of-bounds read AND write** (`parent[i] = ...`). The public entry `graph_cuda_afforest_cc` never validates edge endpoints against `num_vertices`. This is a **heap corruption primitive** reachable from any caller that supplies a malformed edge list — including via `graph_cuda_dlpack_eval`, where the tensor shape `[N,2]` is trusted but the *values* are not.

2. **Path-halving is not path-compression.** The comment claims "Path halving" — correct — but the algorithm's amortized `O(α(n))` bound requires *either* union-by-rank *and* path compression, *or* a proven halving variant. Halving alone with union-by-rank is `O(log n)` amortized, not `O(α(n))`. The asymptotic claim in the file header ("Afforest") is therefore **unproven for this implementation**. Afforest's published bound assumes a specific `link`/`compress` primitive; this is not it.

3. **No cycle guard.** If `parent` is ever corrupted (e.g., by defect #1), the `while` loop can spin forever. There is no iteration cap. A single OOB write that lands `parent[i] = j` with `j` forming a cycle → **infinite loop / DoS**.

**PROPOSED EXACT PATCH:**

```cpp
static inline uint32_t cpu_find(std::vector<uint32_t>& parent, uint32_t i) {
    if (i >= parent.size()) return UINT32_MAX; // sentinel; caller must check
    uint32_t root = i;
    while (root != parent[root]) {
        if (root >= parent.size()) return UINT32_MAX;
        root = parent[root];
    }
    // Path compression (full), not halving — restores O(α(n)) with union-by-rank
    while (i != root) {
        uint32_t next = parent[i];
        parent[i] = root;
        i = next;
    }
    return root;
}
```

And at every call site, reject `u >= num_vertices || v >= num_vertices` **before** calling `cpu_unite`.

---

## FUNCTION 2: `cpu_unite`

**VERDICT: [VULNERABLE]**

**REASONING:**

```cpp
static inline void cpu_unite(std::vector<uint32_t>& parent, std::vector<uint32_t>& rank, uint32_t u, uint32_t v) {
    uint32_t root_u = cpu_find(parent, u);
    uint32_t root_v = cpu_find(parent, v);
    if (root_u == root_v) return;
    ...
}
```

1. **Inherits `cpu_find`'s OOB.** If `cpu_find` returns `UINT32_MAX` (post-patch) or garbage (pre-patch), `rank[root_u]` and `rank[root_v]` are OOB accesses on `rank`. Pre-patch, `root_u`/`root_v` are whatever `parent[OOB]` happened to contain — arbitrary.

2. **`rank` overflow is theoretically possible but not the real bug.** `rank` is `uint32_t`; with `num_vertices ≤ 2^32`, rank can at most reach `~log2(2^32) = 32`. No overflow. **Not a defect.**

3. **Union-by-rank is correct** for the two-branch case. The `else` branch (equal ranks) increments `rank[root_u]` after attaching `root_v` under `root_u`. Correct.

4. **No `alignas` / no false-sharing mitigation.** In the parallel phases (see below), `parent` and `rank` are written concurrently. `std::vector<uint32_t>` gives 4-byte elements; adjacent elements share cache lines. Under 64 threads, this is a **false-sharing catastrophe** — but only if `cpu_unite` is called from a parallel region. In the current code, `cpu_unite` is only called from serial loops (Phases 1 and 3). **So false sharing is not currently triggered here**, but the API is a landmine: any future caller parallelizing Phase 1/3 will hit it.

**PROPOSED EXACT PATCH:**

```cpp
static inline void cpu_unite(std::vector<uint32_t>& parent,
                             std::vector<uint32_t>& rank,
                             uint32_t u, uint32_t v) {
    if (u >= parent.size() || v >= parent.size()) return; // reject, don't corrupt
    uint32_t root_u = cpu_find(parent, u);
    uint32_t root_v = cpu_find(parent, v);
    if (root_u == UINT32_MAX || root_v == UINT32_MAX) return;
    if (root_u == root_v) return;
    if (rank[root_u] < rank[root_v])      parent[root_u] = root_v;
    else if (rank[root_u] > rank[root_v]) parent[root_v] = root_u;
    else { parent[root_v] = root_u; rank[root_u]++; }
}
```

---

## FUNCTION 3: `graph_cuda_is_available`

**VERDICT: [CERTIFIED]** (with a caveat)

**REASONING:**

```cpp
#if defined(_WIN32)
    HMODULE hCuda = LoadLibraryA("nvcuda.dll");
    if (hCuda) { FreeLibrary(hCuda); return 1; }
    return 0;
#else
    return 0;
#endif
```

- `LoadLibraryA` / `FreeLibrary` are correctly paired. No leak.
- **Caveat (not a vulnerability, a correctness lie):** The function returns `1` if `nvcuda.dll` is *loadable*, not if a CUDA-capable device is *present*. On a machine with the driver installed but no GPU, this returns `1`. The name `is_available` is semantically wrong. This is a **contract violation**, not memory unsafety. On non-Windows it unconditionally returns `0`, which is a **silent capability lie** on Linux/macOS where CUDA is common. Rule 27 ("Multi-Platform Hardware Agnosticism") is *violated* by this asymmetry.

**PROPOSED EXACT PATCH:**

```cpp
extern "C" GRAPH_CUDA_API int32_t graph_cuda_is_available(void) {
#if defined(_WIN32)
    HMODULE h = LoadLibraryA("nvcuda.dll");
    if (!h) return 0;
    // Optionally: GetProcAddress(h, "cuInit") and call it.
    FreeLibrary(h);
    return 1;
#elif defined(__linux__)
    void* h = dlopen("libcuda.so.1", RTLD_LAZY | RTLD_LOCAL);
    if (!h) return 0;
    dlclose(h);
    return 1;
#else
    return 0;
#endif
}
```

---

## FUNCTION 4: `graph_cuda_afforest_cc`

**VERDICT: [VULNERABLE]** — multiple independent defects.

**REASONING (line-by-line):**

### 4a. Argument validation
```cpp
if (!edges || !out_components || !out_result) return -1;
if (num_vertices == 0) return -2;
```
- **Missing:** `num_edges == 0` is allowed (fine), but **no validation that `edges[i].u < num_vertices` and `edges[i].v < num_vertices`**. This is the root cause of the `cpu_find` OOB. **VULNERABLE.**
- **Missing:** `out_result` is written but never checked for aliasing with `out_components` or `edges`. If a caller passes overlapping buffers, we get silent corruption. **VULNERABLE (API contract).**

### 4b. Allocation
```cpp
std::vector<uint32_t> parent(num_vertices);
std::vector<uint32_t> rank(num_vertices, 0);
```
- `num_vertices` is `uint32_t`. On a 32-bit build, `num_vertices * 4` can overflow `size_t`? No — `size_t` is 32-bit there too, and `num_vertices ≤ 2^32-1`, so `num_vertices * 4` can overflow `size_t` on 32-bit. **On 32-bit: integer overflow → undersized allocation → heap overflow.** On 64-bit: safe. **VULNERABLE on 32-bit targets.**
- `std::vector` throws `std::bad_alloc` on failure. **No `try/catch`.** This is an `extern "C"` boundary. Throwing across an FFI boundary is **UB** (and on MSVC, `extern "C"` does not imply `noexcept`; the exception will propagate into C code that has no unwind tables → `std::terminate` or worse). **VULNERABLE — FFI safety violation.**

### 4c. Parallel init
```cpp
#pragma omp parallel for schedule(static)
for (int64_t i = 0; i < (int64_t)num_vertices; ++i) {
    parent[i] = (uint32_t)i;
}
```
- Correct. `int64_t` cast avoids signed/unsigned comparison warning. **CERTIFIED.**

### 4d. Phase 1 — sampling
```cpp
uint32_t sample_stride = 2;
for (uint32_t i = 0; i < num_edges; i += sample_stride) {
    cpu_unite(parent, rank, edges[i].u, edges[i].v);
}
```
- **Algorithmic defect:** Afforest's Phase 1 is supposed to sample `k` edges *per vertex* (or a fixed fraction), not every-other edge globally. Sampling every 2nd edge is a **different algorithm** with different (unproven) connectivity guarantees. The header claims "Afforest" — this is **not Afforest**. The asymptotic bound is **unknown** for this variant.
- **`i += sample_stride` overflow:** if `num_edges` is near `UINT32_MAX`, `i + 2` wraps. Loop condition `i < num_edges` then becomes `i < num_edges` with `i` wrapped to a small value → **infinite loop**. **VULNERABLE.**
- **Serial.** No parallelism. Afforest's entire point is parallel Phase 1. **Performance defect, not memory safety.**

### 4e. Phase 2 — giant component
```cpp
std::vector<uint32_t> comp_size(num_vertices, 0);
for (uint32_t i = 0; i < num_vertices; ++i) {
    comp_size[cpu_find(parent, i)]++;
}
```
- **`cpu_find` returns a root that is guaranteed `< num_vertices` only if `parent` is well-formed.** Given 4a's missing validation, `cpu_find` can return garbage → `comp_size[garbage]++` → **OOB write**. **VULNERABLE.**
- **`comp_size[root]++` can overflow** if `num_vertices == UINT32_MAX` and all vertices are in one component. `UINT32_MAX` vertices in one component → `comp_size[root] == UINT32_MAX`, then `++` wraps to `0`. **VULNERABLE (theoretical, requires 4 billion vertices).**

### 4f. Giant root selection
```cpp
uint32_t giant_root = 0;
uint32_t max_sz = 0;
for (uint32_t i = 0; i < num_vertices; ++i) {
    if (comp_size[i] > max_sz) { max_sz = comp_size[i]; giant_root = i; }
}
```
- Correct. Ties broken by lowest index. **CERTIFIED.**

### 4g. Phase 3 — skip giant
```cpp
for (uint32_t i = 0; i < num_edges; ++i) {
    uint32_t u = edges[i].u;
    uint32_t v = edges[i].v;
    if (parent[u] == giant_root && parent[v] == giant_root) continue;
    cpu_unite(parent, rank, u, v);
}
```
- **`parent[u]` and `parent[v]` are read directly, not via `cpu_find`.** After Phase 1, `parent[u]` may not be the root of `u` — it may be an intermediate node. The check `parent[u] == giant_root` is therefore **incorrect**: a vertex whose root is `giant_root` but whose immediate parent is not `giant_root` will **not** be skipped. This is a **correctness bug**, not memory safety. The optimization is defeated; Phase 3 degenerates to full union. **VULNERABLE (correctness).**
- **Same `i` overflow as 4d** — but here `i++` on `UINT32_MAX` wraps to `0`, and `0 < num_edges` is true → **infinite loop**. **VULNERABLE.**

### 4h. Phase 4 — output
```cpp
#pragma omp parallel for schedule(static)
for (int64_t i = 0; i < (int64_t)num_vertices; ++i) {
    out_components[i] = cpu_find(parent, (uint32_t)i);
}
```
- **`cpu_find` mutates `parent` (path halving).** This is called from a **parallel region**. Two threads calling `cpu_find` on overlapping paths will race on `parent[i] = parent[parent[i]]`. **Data race → UB.** The path-halving write is not atomic. **VULNERABLE — this is the most serious defect in the file.**
- Even with `#pragma omp atomic`, the read-modify-write is not a single atomic operation. The correct fix is to **not mutate** in the parallel phase, or to use a lock-free find with `std::atomic<uint32_t>` and CAS loops.

### 4i. Final size count
```cpp
std::vector<uint32_t> final_sz(num_vertices, 0);
for (uint32_t i = 0; i < num_vertices; ++i) {
    final_sz[out_components[i]]++;
}
```
- **`out_components[i]` is a root, guaranteed `< num_vertices` only if Phase 4 produced valid roots.** Given 4h's race, `out_components[i]` can be garbage → **OOB write**. **VULNERABLE.**
- **`final_sz[root]++` overflow** — same as 4e. **VULNERABLE (theoretical).**

### 4j. Component count
```cpp
uint32_t final_max_sz = 0;
for (uint32_t i = 0; i < num_vertices; ++i) {
    if (final_sz[i] > 0) num_comps++;
    if (final_sz[i] > final_max_sz) final_max_sz = final_sz[i];
}
```
- Correct. **CERTIFIED.**

### 4k. Timing
```cpp
auto t_start = std::chrono::high_resolution_clock::now();
...
auto t_end = std::chrono::high_resolution_clock::now();
int64_t ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t_end - t_start).count();
```
- `high_resolution_clock` is **not guaranteed monotonic**. On some platforms it's `system_clock` (wall clock), which can go backwards (NTP, DST). `t_end - t_start` can be **negative**. `ns` is `int64_t`, so no UB, but the reported time is **wrong**. **VULNERABLE (correctness).** Use `steady_clock`.

### 4l. Result write
```cpp
out_result->status = 0;
...
out_result->backend_used = 0;
```
- **No check that `out_result` is aligned.** If a caller passes a misaligned pointer (e.g., from a packed struct), this is UB on strict-alignment architectures (ARM). **VULNERABLE (theoretical).**
- **`out_result` is written after all the work.** If the function returns early (e.g., `-1`), `out_result` is left untouched — caller may read uninitialized memory. **VULNERABLE (API contract).**

**PROPOSED EXACT PATCH (composite):**

```cpp
extern "C" GRAPH_CUDA_API int32_t graph_cuda_afforest_cc(
    const GraphEdge* edges, uint32_t num_edges, uint32_t num_vertices,
    uint32_t* out_components, GraphCudaResult* out_result, void* stream_ptr)
{
    (void)stream_ptr;
    if (!out_result) return -1;
    out_result->status = -1; // pre-poison
    if (!edges || !out_components) return -1;
    if (num_vertices == 0) return -2;
    if (num_vertices > (SIZE_MAX / sizeof(uint32_t))) return -3; // 32-bit guard

    // Validate edge endpoints BEFORE any allocation.
    for (uint32_t i = 0; i < num_edges; ++i) {
        if (edges[i].u >= num_vertices || edges[i].v >= num_vertices) return -4;
    }

    try {
        auto t_start = std::chrono::steady_clock::now();
        std::vector<uint32_t>