import sys

content = open('src/polydim_kernel.cpp').read()

start = content.find('struct PMTP_Control')
end = content.find('extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_free')
if end == -1: end = len(content)

new_pmtp = """struct alignas(64) PMTP_Control {
    std::atomic<uint64_t> seq[3];
    std::atomic<uint8_t> state;
};

extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_sizeof(void)  { return sizeof(PMTP_Control); }
extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_alignof(void) { return alignof(PMTP_Control); }

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c) {
    if (!c) return;
    c->state.store((0) | (1 << 2) | (2 << 4), std::memory_order_seq_cst);
    c->seq[0].store(0, std::memory_order_seq_cst);
    c->seq[1].store(0, std::memory_order_seq_cst);
    c->seq[2].store(0, std::memory_order_seq_cst);
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_begin_write(PMTP_Control* c, uint64_t* slot_out) {
    if (!c || !slot_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    uint64_t slot = (s >> 4) & 3; 
    c->seq[slot].fetch_add(1, std::memory_order_acquire); 
    *slot_out = slot;
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_commit_write(PMTP_Control* c, uint64_t slot) {
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    c->seq[slot].fetch_add(1, std::memory_order_release); 
    uint8_t current = c->state.load(std::memory_order_acquire);
    while (true) {
        uint8_t old_o = current & 3;
        uint8_t old_m = (current >> 2) & 3;
        uint8_t old_n = (current >> 4) & 3;
        uint8_t next_s = (old_m) | (old_n << 2) | (old_o << 4);
        if (c->state.compare_exchange_weak(current, next_s, std::memory_order_release, std::memory_order_relaxed)) break;
    }
    return POLYDIM_SUCCESS;
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_acquire_read(
    PMTP_Control* c, uint64_t* observed_seq, uint64_t* slot_out, uint64_t* ticket_out)
{
    if (!c || !observed_seq || !slot_out || !ticket_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    uint64_t slot = s & 3; 
    uint64_t seq = c->seq[slot].load(std::memory_order_acquire);
    *slot_out = slot;
    *ticket_out = seq;
    *observed_seq = seq;
    if (seq % 2 != 0) return 0; 
    return 1; 
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_validate_read(
    const PMTP_Control* c, uint64_t slot, uint64_t ticket)
{
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    std::atomic_thread_fence(std::memory_order_acquire);
    uint64_t current_seq = c->seq[slot].load(std::memory_order_acquire);
    if (current_seq != ticket || (current_seq % 2 != 0)) return POLYDIM_ERR_SEQLOCK_RACE;
    return POLYDIM_SUCCESS;
}

"""
content = content[:start] + new_pmtp + content[end:]
open('src/polydim_kernel.cpp', 'w').write(content)
print("PMTP block fully replaced.")
