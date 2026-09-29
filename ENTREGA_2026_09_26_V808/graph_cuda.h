#ifndef GRAPH_CUDA_H
#define GRAPH_CUDA_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN32
  #ifdef GRAPH_CUDA_EXPORTS
    #define GRAPH_CUDA_API __declspec(dllexport)
  #else
    #define GRAPH_CUDA_API __declspec(dllimport)
  #endif
#else
  #define GRAPH_CUDA_API __attribute__((visibility("default")))
#endif

/* DLPack minimal structures for zero-copy tensor exchange (DLPack 1.x) */
typedef enum {
    kDLCPU = 1,
    kDLCUDA = 2,
    kDLROCm = 10,
} DLDeviceType;

typedef struct {
    DLDeviceType device_type;
    int32_t device_id;
} DLDevice;

typedef struct {
    uint8_t code;
    uint8_t bits;
    uint16_t lanes;
} DLDataType;

typedef struct {
    void* data;
    DLDevice device;
    int32_t ndim;
    DLDataType dtype;
    int64_t* shape;
    int64_t* strides;
    uint64_t byte_offset;
} DLTensor;

typedef struct {
    uint32_t u;
    uint32_t v;
} GraphEdge;

typedef struct {
    int32_t status;
    uint32_t num_vertices;
    uint32_t num_edges;
    uint32_t num_components;
    uint32_t giant_component_size;
    int64_t execution_time_ns;
    uint8_t backend_used; /* 1 = CUDA GPU, 0 = CPU Fallback */
    uint8_t pad[23];
} GraphCudaResult;

GRAPH_CUDA_API int32_t graph_cuda_is_available(void);

GRAPH_CUDA_API int32_t graph_cuda_afforest_cc(
    const GraphEdge* edges,
    uint32_t num_edges,
    uint32_t num_vertices,
    uint32_t* out_components,
    GraphCudaResult* out_result,
    void* stream_ptr
);

GRAPH_CUDA_API int32_t graph_cuda_dlpack_eval(
    const DLTensor* edges_tensor,
    DLTensor* components_tensor,
    GraphCudaResult* out_result,
    void* stream_ptr
);

#ifdef __cplusplus
}
#endif

#endif /* GRAPH_CUDA_H */
