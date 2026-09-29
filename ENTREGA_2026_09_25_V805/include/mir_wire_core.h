// ============================================================================
// POLYDIM V800 — MIR-WIRE RDMA ZERO-COPY IPC SPECIFICATION & NATIVE C++ HEADER
// Unified Multi-Node Fabric | IBV_WR_RDMA_WRITE_WITH_IMM | XRC / UCX Abstraction
// Target: RoCE v2 (100/200/400 GbE) & InfiniBand NDR/HDR | Pinned HugePages 2MB/1GB
// ============================================================================

#ifndef POLYDIM_MIR_WIRE_H
#define POLYDIM_MIR_WIRE_H

#include <cstdint>
#include <atomic>
#include <vector>
#include <string>
#include <memory>
#include <functional>

#if defined(_WIN32)
  #include <windows.h>
  #define MIR_EXPORT __declspec(dllexport)
  #define MIR_CALL __cdecl
#else
  #include <sys/mman.h>
  #include <unistd.h>
  #define MIR_EXPORT __attribute__((visibility("default")))
  #define MIR_CALL
#endif

// ============================================================================
// STATUS CODES & TRANSPORT ENUMS
// ============================================================================
enum MirStatusCode : int32_t {
    MIR_SUCCESS = 0,
    MIR_ERR_NULL_POINTER = -1,
    MIR_ERR_INVALID_DIMENSION = -2,
    MIR_ERR_DEVICE_NOT_FOUND = -3,
    MIR_ERR_PD_ALLOC_FAILED = -4,
    MIR_ERR_MR_REG_FAILED = -5,
    MIR_ERR_QP_CREATE_FAILED = -6,
    MIR_ERR_POST_SEND_FAILED = -7,
    MIR_ERR_POLL_CQ_FAILED = -8,
    MIR_ERR_BACKPRESSURE_FULL = -9,
    MIR_ERR_NUMA_NODE_MISMATCH = -10,
    MIR_ERR_TIMEOUT = -11
};

enum MirTransportBackend : uint32_t {
    MIR_BACKEND_LOCAL_SHM = 0,      // Local intra-node mmap fallback
    MIR_BACKEND_IBVERBS_ROCE = 1,   // Native RoCE v2 (Lossless Ethernet)
    MIR_BACKEND_IBVERBS_IB = 2,     // Native InfiniBand (HDR/NDR)
    MIR_BACKEND_UCX_FABRIC = 3      // Unified Communication X (EFA/Slingshot/OmniPath)
};

// ============================================================================
// 1. NUMA-AWARE PINNED HUGEPAGES ALLOCATOR
// ============================================================================
struct MirMemoryRegion {
    void* local_addr;
    uint64_t remote_addr;
    uint32_t rkey;
    uint32_t lkey;
    uint64_t length;
    uint32_t numa_node;
    bool is_hugepage;
};

class MirHugePageAllocator {
public:
    static MirMemoryRegion allocate_pinned_slab(uint64_t size_bytes, uint32_t numa_node = 0) {
        MirMemoryRegion mr = {nullptr, 0, 0, 0, size_bytes, numa_node, false};

#if defined(__linux__)
        // Linux 2MB HugePages allocation via mmap MAP_HUGETLB
        void* ptr = mmap(
            nullptr, 
            size_bytes, 
            PROT_READ | PROT_WRITE, 
            MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB | MAP_LOCKED, 
            -1, 
            0
        );

        if (ptr != MAP_FAILED) {
            mr.local_addr = ptr;
            mr.is_hugepage = true;
        } else {
            // Fallback to posix_memalign + mlock
            void* fallback_ptr = nullptr;
            if (posix_memalign(&fallback_ptr, 4096, size_bytes) == 0) {
                mlock(fallback_ptr, size_bytes);
                mr.local_addr = fallback_ptr;
            }
        }
#elif defined(_WIN32)
        // Windows VirtualLock allocation with 64KB page alignment
        void* ptr = VirtualAlloc(
            nullptr, 
            size_bytes, 
            MEM_COMMIT | MEM_RESERVE, 
            PAGE_READWRITE
        );
        if (ptr) {
            VirtualLock(ptr, size_bytes);
            mr.local_addr = ptr;
        }
#endif
        return mr;
    }

    static void free_pinned_slab(MirMemoryRegion& mr) {
        if (!mr.local_addr) return;
#if defined(__linux__)
        if (mr.is_hugepage) {
            munmap(mr.local_addr, mr.length);
        } else {
            munlock(mr.local_addr, mr.length);
            free(mr.local_addr);
        }
#elif defined(_WIN32)
        VirtualUnlock(mr.local_addr, mr.length);
        VirtualFree(mr.local_addr, 0, MEM_RELEASE);
#endif
        mr.local_addr = nullptr;
    }
};

// ============================================================================
// 2. BACKPRESSURE & FLOW CONTROL (CREDIT-BASED LEAPFROG QUEUE)
// ============================================================================
struct alignas(64) MirFlowControlHeader {
    alignas(64) std::atomic<uint32_t> credits_available; // Sender decrements, Receiver increments
    alignas(64) std::atomic<uint32_t> last_ack_seq;
    alignas(64) std::atomic<uint32_t> drop_count;
};

// ============================================================================
// 3. ABSTRACT TRANSPORT ENGINE (MIR-WIRE CORE)
// ============================================================================
class MirWireChannel {
public:
    virtual ~MirWireChannel() = default;
    virtual MirStatusCode initialize(const std::string& remote_endpoint, uint32_t port) = 0;
    
    // Asynchronous RDMA Write with 32-bit Immediate Sequence ID
    virtual MirStatusCode post_tensor_write_imm(
        const double* tensor_f64, 
        uint64_t dimension, 
        uint32_t sequence_id
    ) = 0;

    // Zero-Copy Polling for Inbound Immediate Data
    virtual MirStatusCode poll_inbound_imm(
        uint32_t* received_seq_id, 
        const double** out_tensor_ptr, 
        uint32_t timeout_us
    ) = 0;

    virtual MirStatusCode return_credits(uint32_t credits) = 0;
};

// ============================================================================
// 4. C-ABI EXPORTS FOR PYTHON / RUST / DART BINDINGS
// ============================================================================
extern "C" {

MIR_EXPORT void* MIR_CALL mir_create_channel(uint32_t backend_type, uint64_t max_dimension);
MIR_EXPORT int32_t MIR_CALL mir_connect(void* channel_handle, const char* remote_ip, uint32_t port);
MIR_EXPORT int32_t MIR_CALL mir_send_tensor_imm(void* channel_handle, const double* data, uint64_t d, uint32_t seq);
MIR_EXPORT int32_t MIR_CALL mir_poll_tensor_imm(void* channel_handle, uint32_t* out_seq, double** out_ptr, uint32_t timeout_us);
MIR_EXPORT void MIR_CALL mir_destroy_channel(void* channel_handle);

} // extern "C"

#endif // POLYDIM_MIR_WIRE_H
