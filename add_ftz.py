import os
import re

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/kernel_cpp_v767.cpp', 'r', encoding='utf-8') as f:
    text = f.read()

func = """extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_check_ftz() {
#if defined(__x86_64__) || defined(_M_X64)
    unsigned int csr = _mm_getcsr();
    if ((csr & 0x8000) || (csr & 0x0040)) return 1;
#endif
    return 0;
}
"""

match = re.search(r'extern "C" POLYDIM_EXPORT int32_t POLYDIM_CALL polydim_selftest_all\(void\) \{', text)
if match:
    new_text = text[:match.start()] + func + text[match.start():]
    with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V767/kernel_cpp_v767.cpp', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Added check_ftz")
else:
    print("Could not find selftest_all")
