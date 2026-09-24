# 🧠 REPORT: Native InfiniBand Verbs (RDMA) for POLYDIM
**Author:** Antigravity Bulldog / Red Team
**Target:** Overcoming TCP Emulation in POLYDIM V769

## 1. The V769 Vulnerability: The TCP Emulator Illusion
In POLYDIM V769, the `MIR-Wire` protocol claimed "RDMA" but physically implemented a TCP emulator using standard `socket.sendall()` and `socket.recv()`. 
**Critical Asymptotic Flaws Found:**
- **Framing Fragmentation:** `conn.recv(header_size)` in TCP does not guarantee `header_size` bytes. A fragmented header silently corrupted the state.
- **Data Processing Inequality (DPI) Violation:** Using TCP meant bouncing the tensor through the OS kernel network stack (copy_to_user, copy_from_user), destroying the zero-copy aspiration and wasting CPU cycles.
- **Not RDMA:** There was no HCA (Host Channel Adapter) bypass, no memory pinning, and no RDMA verbs.

## 2. SOTA Solution: Native InfiniBand Verbs (libibverbs)
To achieve true zero-copy across physical nodes, POLYDIM must implement **Native InfiniBand Verbs** (`ibv_reg_mr`, `IBV_WR_RDMA_WRITE_WITH_IMM`) through the C++/Rust engine, completely bypassing the Python interpreter in the data path.

### 2.1 Memory Registration (`ibv_reg_mr`)
The `PMTPBus` already uses a `PmtpSlabAllocator` for Shared Memory. To extend this to cross-node RDMA:
1. **Pre-pinning:** The C++ daemon allocates the slab and immediately calls `ibv_reg_mr(pd, buffer, length, IBV_ACCESS_LOCAL_WRITE | IBV_ACCESS_REMOTE_WRITE)`.
2. **Key Exchange:** The Local Key (`lkey`), Remote Key (`rkey`), and base virtual address are exchanged *once* over a control channel (TCP is acceptable here for initialization only).
3. **Zero Overhead Data Path:** Because the memory is pre-pinned and registered, the data path avoids the massive performance penalty of dynamic memory registration calls.

### 2.2 RDMA `WRITE_WITH_IMM`
Instead of using two-sided Send/Recv (which requires CPU involvement on the receiver to post Recv WRs), POLYDIM should use **one-sided RDMA Writes**.
- **The Transfer:** Node A uses the `rkey` and remote address to issue an `IBV_WR_RDMA_WRITE_WITH_IMM` work request. The HCA performs a direct DMA read from Node A's RAM and a direct DMA write to Node B's RAM over the PCIe bus.
- **The Immediate Data (`imm_data`):** Node A embeds the `SLAB_ID` (or a tag) in the 4-byte `imm_data`.
- **The Receiver:** Node B's HCA writes the tensor to RAM and generates a Completion Queue Entry (CQE) containing the `imm_data`. Node B's orchestrator strictly polls the Completion Queue (`ibv_poll_cq` / `_mm_pause`) without touching the tensor floats.

## 3. Implementation Stack

### C++ Native Layer
```cpp
// 1. Register PMTP Slab
struct ibv_mr* mr = ibv_reg_mr(pd, pmtp_slab_ptr, slab_size, 
                               IBV_ACCESS_LOCAL_WRITE | IBV_ACCESS_REMOTE_WRITE);

// 2. Post RDMA Write with Immediate
struct ibv_sge sge;
sge.addr = (uintptr_t)pmtp_slab_ptr;
sge.length = tensor_size;
sge.lkey = mr->lkey;

struct ibv_send_wr wr, *bad_wr;
memset(&wr, 0, sizeof(wr));
wr.wr_id = (uint64_t)task_id;
wr.sg_list = &sge;
wr.num_sge = 1;
wr.opcode = IBV_WR_RDMA_WRITE_WITH_IMM;
wr.send_flags = IBV_SEND_SIGNALED;
wr.imm_data = htonl(SLAB_ID); // 32-bit tag
wr.wr.rdma.remote_addr = remote_address_from_exchange;
wr.wr.rdma.rkey = rkey_from_exchange;

ibv_post_send(qp, &wr, &bad_wr);
```

### Python / Rust Integration (FFI)
- Do NOT use Python `pyverbs` for the critical data-path polling. 
- The Rust/C++ FFI should expose a method `pmtp_poll_completion_strict(cq)` that spins on the NIC using `_mm_pause`.
- Once the CQE arrives, Rust reads `wc.imm_data` to get the `SLAB_ID` and wakes up the local GPU orchestrator to compute the tensor, fulfilling the **Ghost Protocol** (Zero-Copy IPC).

## 4. Conclusion
Replacing the V769 TCP Emulator with `WRITE_WITH_IMM` ensures deterministic framing (handled by hardware), kernel bypass, and $O(1)$ CPU overhead. The tensor geometry ($S^{D-1}$) remains physically intact from Node A's VRAM/RAM to Node B's VRAM/RAM.
