import os
import re

CPP_PATH = 'E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/kernel_cpp_v767.cpp'
with open(CPP_PATH, 'r', encoding='utf-8') as f:
    cpp_text = f.read()

cpp_api_new = """
struct alignas(64) PMTP_SlotHeader {
    std::atomic<uint64_t> seq;
    uint8_t reserved_[56];
};

struct alignas(64) PMTP_Control {
    uint32_t magic;
    uint32_t num_slots;
    uint64_t payload_bytes;
    std::atomic<uint64_t> pub_seq;
    std::atomic<uint32_t> pub_slot;
    std::atomic<uint32_t> wlock;
    std::atomic<uint32_t> wticket;
    uint8_t reserved_[28];
};

static inline PMTP_SlotHeader* pmtp2_hdr_of(PMTP_Control* c, uint32_t slot) {
    return reinterpret_cast<PMTP_SlotHeader*>(
        reinterpret_cast<char*>(c) + sizeof(PMTP_Control) + slot * sizeof(PMTP_SlotHeader)
    );
}

static void pmtp2_lock(PMTP_Control* c) {
    uint32_t t = c->wticket.fetch_add(1, std::memory_order_relaxed);
    while (c->wlock.load(std::memory_order_acquire) != t) {
#if defined(_M_X64) || defined(__x86_64__) || defined(_M_IX86) || defined(__i386__)
        _mm_pause();
#endif
    }
}

static void pmtp2_unlock(PMTP_Control* c) {
    uint32_t cur = c->wlock.load(std::memory_order_relaxed);
    c->wlock.store(cur + 1, std::memory_order_release);
}

extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_sizeof(uint32_t num_slots, uint64_t payload_bytes) {
    try { 
        return sizeof(PMTP_Control) + num_slots * sizeof(PMTP_SlotHeader) + num_slots * payload_bytes; 
    } catch (...) { return 0; }
}

extern "C" POLYDIM_EXPORT uint64_t POLYDIM_CALL polydim_pmtp_alignof(void) {
    try { return alignof(PMTP_Control); } catch (...) { return 0; }
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_init(PMTP_Control* c, uint32_t num_slots, uint64_t payload_bytes) {
    try {
        if (!c) return -1;
        if (num_slots < 2 || num_slots > 64) return -2;
        if (payload_bytes == 0) return -2;
        
        std::memset(c, 0, polydim_pmtp_sizeof(num_slots, payload_bytes));
        c->magic = 0x504D5432u;
        c->num_slots = num_slots;
        c->payload_bytes = payload_bytes;
        return 0;
    } catch (...) { return -1; }
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_write_begin(PMTP_Control* c, uint32_t* slot, uint64_t* ver) {
    try {
        if (!c || !slot || !ver) return -1;
        pmtp2_lock(c);
        
        uint64_t current_ver = c->pub_seq.load(std::memory_order_relaxed);
        *ver = current_ver + 1; // odd for locked
        *slot = (c->pub_slot.load(std::memory_order_relaxed) + 1) % c->num_slots;
        
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, *slot);
        hdr->seq.store(*ver, std::memory_order_release);
        
        return 0;
    } catch (...) { return -1; }
}

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_write_commit(PMTP_Control* c, uint32_t slot, uint64_t ver) {
    try {
        if (!c || slot >= c->num_slots) return;
        
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, slot);
        uint64_t new_ver = ver + 1; // even for unlocked
        hdr->seq.store(new_ver, std::memory_order_release);
        
        c->pub_slot.store(slot, std::memory_order_release);
        c->pub_seq.store(new_ver, std::memory_order_release);
        
        pmtp2_unlock(c);
    } catch (...) {}
}

extern "C" POLYDIM_EXPORT void POLYDIM_CALL polydim_pmtp_write_abort(PMTP_Control* c, uint32_t slot, uint64_t ver) {
    try {
        if (!c || slot >= c->num_slots) return;
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, slot);
        hdr->seq.store(ver + 1, std::memory_order_release); // unlock without updating pub_seq
        pmtp2_unlock(c);
    } catch (...) {}
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_read_begin(PMTP_Control* c, uint32_t* slot, uint64_t* ver) {
    try {
        if (!c || !slot || !ver) return -1;
        
        *ver = c->pub_seq.load(std::memory_order_acquire);
        if (*ver == 0) return 1; // EMPTY
        
        *slot = c->pub_slot.load(std::memory_order_acquire);
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, *slot);
        
        uint64_t s_ver = hdr->seq.load(std::memory_order_acquire);
        if (s_ver != *ver || (s_ver & 1)) return -3; // BUSY/CONFLICT
        
        return 0;
    } catch (...) { return -1; }
}

extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_pmtp_read_validate(PMTP_Control* c, uint32_t slot, uint64_t ver) {
    try {
        if (!c || slot >= c->num_slots) return -1;
        PMTP_SlotHeader* hdr = pmtp2_hdr_of(c, slot);
        uint64_t s_ver = hdr->seq.load(std::memory_order_acquire);
        if (s_ver != ver) return -4; // CONFLICT
        return 0;
    } catch (...) { return -1; }
}
"""

match = re.search(r'struct alignas\(64\) PMTP_SlotHeader.*?polydim_pmtp_validate_read.*?return POLYDIM_ERR_INTERNAL;\s*\}\s*\}', cpp_text, re.DOTALL)
if match:
    new_text = cpp_text[:match.start()] + cpp_api_new.strip() + cpp_text[match.end():]
    with open(CPP_PATH, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("kernel_cpp_v767.cpp updated")
else:
    print("Regex failed to match")
