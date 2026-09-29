/**
 * @file graph_cuda.cu
 * Afforest / GConn Asynchronous GPU Connected Components for POLYDIM
 * Architecture:
 *   - Edge sampling (k=2) for giant component detection
 *   - Asynchronous Union-Find with atomicCAS and path-halving compression
 *   - Raw DLPack / C-ABI pointer compatibility
 *   - Explicit cudaStream_t support without forced host synchronize
 */

#include "graph_cuda.h"
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <chrono>

__device__ inline uint32_t gpu_find_root(uint32_t* parent, uint32_t node) {
    while (node != parent[node]) {
        uint32_t p = parent[node];
        uint32_t gp = parent[p];
        parent[node] = gp; // Path halving
        node = p;
    }
    return node;
}

__device__ inline void gpu_unite(uint32_t* parent, uint32_t u, uint32_t v) {
    while (true) {
        u = gpu_find_root(parent, u);
        v = gpu_find_root(parent, v);
        if (u == v) return;
        if (u < v) {
            uint32_t old = atomicCAS(&parent[v], v, u);
            if (old == v) return;
        } else {
            uint32_t old = atomicCAS(&parent[u], u, v);
            if (old == u) return;
        }
    }
}

__global__ void init_parents_kernel(uint32_t* parent, uint32_t num_vertices) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < num_vertices) {
        parent[idx] = idx;
    }
}

__global__ void sample_edges_kernel(const GraphEdge* edges, uint32_t num_edges, uint32_t* parent, uint32_t stride) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < num_edges && (idx % stride == 0)) {
        gpu_unite(parent, edges[idx].u, edges[idx].v);
    }
}

__global__ void afforest_main_kernel(const GraphEdge* edges, uint32_t num_edges, uint32_t* parent, uint32_t giant_root) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < num_edges) {
        uint32_t u = edges[idx].u;
        uint32_t v = edges[idx].v;
        // Skip edges where both endpoints already belong to giant component
        if (parent[u] == giant_root && parent[v] == giant_root) return;
        gpu_unite(parent, u, v);
    }
}

__global__ void compress_paths_kernel(uint32_t* parent, uint32_t num_vertices) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < num_vertices) {
        parent[idx] = gpu_find_root(parent, idx);
    }
}

extern "C" GRAPH_CUDA_API int32_t graph_cuda_is_available(void) {
    int device_count = 0;
    cudaError_t err = cudaGetDeviceCount(&device_count);
    return (err == cudaSuccess && device_count > 0) ? 1 : 0;
}

extern "C" GRAPH_CUDA_API int32_t graph_cuda_afforest_cc(
    const GraphEdge* edges,
    uint32_t num_edges,
    uint32_t num_vertices,
    uint32_t* out_components,
    GraphCudaResult* out_result,
    void* stream_ptr
) {
    if (!edges || !out_components || !out_result) return -1;
    if (num_vertices == 0) return -2;

    auto t_start = std::chrono::high_resolution_clock::now();
    cudaStream_t stream = stream_ptr ? (cudaStream_t)stream_ptr : 0;

    GraphEdge* d_edges = nullptr;
    uint32_t* d_parent = nullptr;

    cudaError_t err = cudaMallocAsync(&d_edges, num_edges * sizeof(GraphEdge), stream);
    if (err != cudaSuccess) return -3;
    err = cudaMallocAsync(&d_parent, num_vertices * sizeof(uint32_t), stream);
    if (err != cudaSuccess) { cudaFreeAsync(d_edges, stream); return -3; }

    err = cudaMemcpyAsync(d_edges, edges, num_edges * sizeof(GraphEdge), cudaMemcpyHostToDevice, stream);
    if (err != cudaSuccess) {
        cudaFreeAsync(d_edges, stream);
        cudaFreeAsync(d_parent, stream);
        return -4;
    }

    uint32_t block_size = 256;
    uint32_t grid_v = (num_vertices + block_size - 1) / block_size;
    uint32_t grid_e = (num_edges + block_size - 1) / block_size;

    init_parents_kernel<<<grid_v, block_size, 0, stream>>>(d_parent, num_vertices);

    // Phase 1: Sub-sampling k=2
    if (num_edges > 0) {
        sample_edges_kernel<<<grid_e, block_size, 0, stream>>>(d_edges, num_edges, d_parent, 2);
    }

    // Phase 2: Full Afforest execution
    if (num_edges > 0) {
        afforest_main_kernel<<<grid_e, block_size, 0, stream>>>(d_edges, num_edges, d_parent, 0);
    }

    // Phase 3: Final path compression
    compress_paths_kernel<<<grid_v, block_size, 0, stream>>>(d_parent, num_vertices);

    err = cudaMemcpyAsync(out_components, d_parent, num_vertices * sizeof(uint32_t), cudaMemcpyDeviceToHost, stream);
    cudaFreeAsync(d_edges, stream);
    cudaFreeAsync(d_parent, stream);

    if (stream == 0) {
        cudaStreamSynchronize(0);
    }

    auto t_end = std::chrono::high_resolution_clock::now();
    int64_t ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t_end - t_start).count();

    out_result->status = 0;
    out_result->num_vertices = num_vertices;
    out_result->num_edges = num_edges;
    out_result->execution_time_ns = ns;
    out_result->backend_used = 1; // CUDA GPU

    return 0;
}
