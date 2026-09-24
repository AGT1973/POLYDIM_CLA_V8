import sys
import re

content = open('src/polydim_kernel.cpp').read()

old_struct_match = re.search(r'struct PMTP_Control \{.*?extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init\(PMTP_Control\* c\) \{', content, re.DOTALL)
if not old_struct_match:
    print("Could not find struct definition")
    sys.exit(1)

old_struct = old_struct_match.group(0)

new_struct = """struct PMTP_Control {
    std::atomic<uint8_t> state; // Oldest(0:2), Middle(2:2), Newest(4:2), Dirty(6:1)
    std::atomic<uint32_t> seq[3];
    char _pad[64 - 1sizeof(std::atomic<uint8_t>) - 3*sizeof(std::atomic<uint32_t>)]; // Approximate padding to 64 bytes
};

extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_sizeof(void)  { return sizeof(PMTP_Control); }
extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_alignof(void) { return alignof(PMTP_Control); }

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c) {"""
content = content.replace(old_struct, new_struct)

old_init_match = re.search(r'extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init\(PMTP_Control\* c\) \{.*?\}', content, re.DOTALL)
new_init = """extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c) {
    if (!c) return;
    c->state.store((0) | (1 << 2) | (2 << 4), std::memory_order_seq_cst);
    c->seq[0].store(0, std::memory_order_seq_cst);
    c->seq[1].store(0, std::memory_order_seq_cst);
    c->seq[2].store(0, std::memory_order_seq_cst);
}"""
content = content.replace(old_init_match.group(0), new_init)

old_begin_write = re.search(r'extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_begin_write\(PMTP_Control\* c, uint64_t\* slot_out\) \{.*?\}', content, re.DOTALL)
new_begin_write = """extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_begin_write(PMTP_Control* c, uint64_t* slot_out) {
    if (!c || !slot_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    uint64_t slot = (s >> 4) & 3; // Use newest slot
    c->seq[slot].fetch_add(1, std::memory_order_acquire); // Odd = writing
    *slot_out = slot;
    return POLYDIM_SUCCESS;
}"""
content = content.replace(old_begin_write.group(0), new_begin_write)


old_commit = re.search(r'extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_commit_write\(PMTP_Control\* c, uint64_t slot\) \{.*?\}', content, re.DOTALL)
new_commit = """extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_commit_write(PMTP_Control* c, uint64_t slot) {
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    c->seq[slot].fetch_add(1, std::memory_order_release); // Even = written
    uint8_t current = c->state.load(std::memory_order_acquire);
    while (true) {
        uint8_t old_o = current & 3;
        uint8_t old_m = (current >> 2) & 3;
        uint8_t old_n = (current >> 4) & 3;
        uint8_t next_s = (old_m) | (old_n << 2) | (old_o << 4);
        if (c->state.compare_exchange_weak(current, next_s, std::memory_order_release, std::memory_order_relaxed)) {
            break;
        }
    }
    return POLYDIM_SUCCESS;
}"""
content = content.replace(old_commit.group(0), new_commit)


old_acquire = re.search(r'extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_acquire_read\(.*?\}', content, re.DOTALL)
new_acquire = """extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_acquire_read(
    PMTP_Control* c, uint64_t* observed_seq, uint64_t* slot_out, uint64_t* ticket_out)
{
    if (!c || !observed_seq || !slot_out || !ticket_out) return POLYDIM_ERR_NULL_POINTER;
    uint8_t s = c->state.load(std::memory_order_acquire);
    uint64_t slot = s & 3; // Oldest
    uint32_t seq = c->seq[slot].load(std::memory_order_acquire);
    *slot_out = slot;
    *ticket_out = seq;
    *observed_seq = seq;
    if (seq % 2 != 0) return POLYDIM_ERR_SEQLOCK_RACE; // Currently writing
    return POLYDIM_SUCCESS;
}"""
content = content.replace(old_acquire.group(0), new_acquire)

old_validate = re.search(r'extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_validate_read\(.*?\}', content, re.DOTALL)
new_validate = """extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_validate_read(
    const PMTP_Control* c, uint64_t slot, uint64_t ticket)
{
    if (!c) return POLYDIM_ERR_NULL_POINTER;
    std::atomic_thread_fence(std::memory_order_acquire); // DMB ISHLD on ARM
    uint32_t current_seq = c->seq[slot].load(std::memory_order_acquire);
    if (current_seq != ticket || (current_seq % 2 != 0)) {
        return POLYDIM_ERR_SEQLOCK_RACE;
    }
    return POLYDIM_SUCCESS;
}"""
content = content.replace(old_validate.group(0), new_validate)

open('src/polydim_kernel.cpp', 'w').write(content)
print("PMTP Ghost Protocol patched.")
