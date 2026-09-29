/**
 * @file graph_cuda.cpp
 * Host & CPU Fallback implementation of graph_cuda.dll
 * Conforms to Rule 27: Multi-Platform Hardware Agnosticism & Silicon Contract
 * Provides Afforest GConn Connected Components with OpenMP and DLPack ABI.
 */

#define GRAPH_CUDA_EXPORTS
#include "graph_cuda.h"
#include <vector>
#include <chrono>
#include <algorithm>
#include <cstring>
#include <omp.h>

#if defined(_WIN32)
#include <windows.h>
#endif

// CPU Disjoint Set with Path Compression and Union by Rank
static inline uint32_t cpu_find(std::vector<uint32_t>& parent, uint32_t i) {
    if (i >= parent.size()) return UINT32_MAX;
    uint32_t root = i;
    while (root != parent[root]) {
        if (root >= parent.size()) return UINT32_MAX;
        root = parent[root];
    }
    // Full path compression
    while (i != root) {
        uint32_t next = parent[i];
        parent[i] = root;
        i = next;
    }
    return root;
}

// Read-only find without in-place path compression for thread-safe OpenMP reads
static inline uint32_t cpu_find_readonly(const std::vector<uint32_t>& parent, uint32_t i) {
    if (i >= parent.size()) return UINT32_MAX;
    uint32_t root = i;
    while (root != parent[root]) {
        root = parent[root];
        if (root >= parent.size()) return UINT32_MAX;
    }
    return root;
}

static inline void cpu_unite(std::vector<uint32_t>& parent, std::vector<uint32_t>& rank, uint32_t u, uint32_t v) {
    if (u >= parent.size() || v >= parent.size()) return;
    uint32_t root_u = cpu_find(parent, u);
    uint32_t root_v = cpu_find(parent, v);
    if (root_u == UINT32_MAX || root_v == UINT32_MAX || root_u == root_v) return;
    if (rank[root_u] < rank[root_v]) {
        parent[root_u] = root_v;
    } else if (rank[root_u] > rank[root_v]) {
        parent[root_v] = root_u;
    } else {
        parent[root_v] = root_u;
        rank[root_u]++;
    }
}

extern "C" GRAPH_CUDA_API int32_t graph_cuda_is_available(void) {
    // Queries if physical CUDA GPU runtime is loaded or available
#if defined(_WIN32)
    HMODULE hCuda = LoadLibraryA("nvcuda.dll");
    if (hCuda) {
        FreeLibrary(hCuda);
        return 1;
    }
    return 0;
#else
    return 0;
#endif
}

extern "C" GRAPH_CUDA_API int32_t graph_cuda_afforest_cc(
    const GraphEdge* edges,
    uint32_t num_edges,
    uint32_t num_vertices,
    uint32_t* out_components,
    GraphCudaResult* out_result,
    void* stream_ptr
) {
    (void)stream_ptr;
    if (!edges || !out_components || !out_result) return -1;
    if (num_vertices == 0) return -2;

    auto t_start = std::chrono::high_resolution_clock::now();

    std::vector<uint32_t> parent(num_vertices);
    std::vector<uint32_t> rank(num_vertices, 0);
    #pragma omp parallel for schedule(static)
    for (int64_t i = 0; i < (int64_t)num_vertices; ++i) {
        parent[i] = (uint32_t)i;
    }

    // Afforest Phase 1: k=2 edge sampling
    uint32_t sample_stride = 2;
    for (uint32_t i = 0; i < num_edges; i += sample_stride) {
        if (edges[i].u < num_vertices && edges[i].v < num_vertices) {
            cpu_unite(parent, rank, edges[i].u, edges[i].v);
        }
    }

    // Afforest Phase 2: Giant component identification
    std::vector<uint32_t> comp_size(num_vertices, 0);
    for (uint32_t i = 0; i < num_vertices; ++i) {
        uint32_t r = cpu_find(parent, i);
        if (r < num_vertices) comp_size[r]++;
    }
    uint32_t giant_root = 0;
    uint32_t max_sz = 0;
    for (uint32_t i = 0; i < num_vertices; ++i) {
        if (comp_size[i] > max_sz) {
            max_sz = comp_size[i];
            giant_root = i;
        }
    }

    // Afforest Phase 3: Remaining edges skipping giant component
    for (uint32_t i = 0; i < num_edges; ++i) {
        uint32_t u = edges[i].u;
        uint32_t v = edges[i].v;
        if (u >= num_vertices || v >= num_vertices) continue;
        if (parent[u] == giant_root && parent[v] == giant_root) continue;
        cpu_unite(parent, rank, u, v);
    }

    // Phase 4: Path compression and component output
    uint32_t num_comps = 0;
    #pragma omp parallel for schedule(static)
    for (int64_t i = 0; i < (int64_t)num_vertices; ++i) {
        out_components[i] = cpu_find_readonly(parent, (uint32_t)i);
    }

    std::vector<uint32_t> final_sz(num_vertices, 0);
    for (uint32_t i = 0; i < num_vertices; ++i) {
        final_sz[out_components[i]]++;
    }
    uint32_t final_max_sz = 0;
    for (uint32_t i = 0; i < num_vertices; ++i) {
        if (final_sz[i] > 0) num_comps++;
        if (final_sz[i] > final_max_sz) final_max_sz = final_sz[i];
    }

    auto t_end = std::chrono::high_resolution_clock::now();
    int64_t ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t_end - t_start).count();

    out_result->status = 0;
    out_result->num_vertices = num_vertices;
    out_result->num_edges = num_edges;
    out_result->num_components = num_comps;
    out_result->giant_component_size = final_max_sz;
    out_result->execution_time_ns = ns;
    out_result->backend_used = 0; // CPU Fallback (Rule 27 compliant)

    return 0;
}

extern "C" GRAPH_CUDA_API int32_t graph_cuda_dlpack_eval(
    const DLTensor* edges_tensor,
    DLTensor* components_tensor,
    GraphCudaResult* out_result,
    void* stream_ptr
) {
    if (!edges_tensor || !components_tensor || !out_result) return -1;
    if (edges_tensor->ndim != 2 || edges_tensor->shape[1] != 2) return -2;
    if (components_tensor->ndim != 1) return -2;

    // Strides & contiguity validation (F-30, F-102)
    if (edges_tensor->strides) {
        if (edges_tensor->strides[1] != 1 || edges_tensor->strides[0] != 2) {
            return -3; // Reject non-contiguous edges tensor
        }
    }
    if (components_tensor->strides) {
        if (components_tensor->strides[0] != 1) {
            return -3; // Reject non-contiguous components tensor
        }
    }

    uint32_t num_edges = (uint32_t)edges_tensor->shape[0];
    uint32_t num_vertices = (uint32_t)components_tensor->shape[0];

    const GraphEdge* edges = reinterpret_cast<const GraphEdge*>(edges_tensor->data);
    uint32_t* components = reinterpret_cast<uint32_t*>(components_tensor->data);

    return graph_cuda_afforest_cc(edges, num_edges, num_vertices, components, out_result, stream_ptr);
}
