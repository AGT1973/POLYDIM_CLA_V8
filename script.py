import sys

with open(r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V803\kernel_cpp_v804.cpp.txt', 'r', encoding='utf-8') as f:
    code = f.read()

old_fields = '''    std::atomic<uint64_t> producer_epoch;
    std::atomic<uint64_t> consumer_epoch;
    std::atomic<uint64_t> producer_heartbeat_ns;
    std::atomic<uint64_t> consumer_heartbeat_ns;'''

new_fields = '''    uint64_t producer_epoch;
    uint64_t data_seq;
    uint64_t space_seq;
    uint64_t _reserved;'''

code = code.replace(old_fields, new_fields)

old_init = '''    header->producer_epoch.store(1, std::memory_order_release);
    header->consumer_epoch.store(1, std::memory_order_release);
    header->producer_heartbeat_ns.store(0, std::memory_order_release);
    header->consumer_heartbeat_ns.store(0, std::memory_order_release);'''

new_init = '''    reinterpret_cast<std::atomic<uint64_t>*>(&header->producer_epoch)->store(1, std::memory_order_release);
    reinterpret_cast<std::atomic<uint64_t>*>(&header->data_seq)->store(0, std::memory_order_release);
    reinterpret_cast<std::atomic<uint64_t>*>(&header->space_seq)->store(0, std::memory_order_release);
    header->_reserved = 0;'''

code = code.replace(old_init, new_init)

last_brace = code.rfind('} // extern "C"')

seqlock_funcs = '''
POLYDIM_EXPORT void polydim_seqlock_write_payload(PmtpHeaderV804* header, void* payload_dst, const void* payload_src, size_t size) {
    auto seq = reinterpret_cast<std::atomic<uint64_t>*>(&header->data_seq);
    uint64_t s = seq->load(std::memory_order_relaxed);
    seq->store(s + 1, std::memory_order_release);
    std::memcpy(payload_dst, payload_src, size);
    seq->store(s + 2, std::memory_order_release);
}

POLYDIM_EXPORT void polydim_seqlock_read_payload(PmtpHeaderV804* header, void* payload_dst, const void* payload_src, size_t size) {
    auto seq = reinterpret_cast<std::atomic<uint64_t>*>(&header->data_seq);
    uint64_t s1, s2;
    do {
        s1 = seq->load(std::memory_order_acquire);
        std::memcpy(payload_dst, payload_src, size);
        s2 = seq->load(std::memory_order_acquire);
    } while((s1 & 1) != 0 || s1 != s2);
}
'''

code = code[:last_brace] + seqlock_funcs + code[last_brace:]

with open(r'E:\POLYDIM_EINSOF\ENTREGA_2026_09_25_V804\kernel_cpp_v804.cpp', 'w', encoding='utf-8') as f:
    f.write(code)
