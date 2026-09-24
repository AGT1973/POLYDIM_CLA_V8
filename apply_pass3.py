import re

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V768/auditoria_externa/kernel_cpp_v768.cpp.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# Include <fenv.h>
if '<fenv.h>' not in text:
    text = text.replace('#include <cmath>', '#include <cmath>\n#include <fenv.h>')

# Patch 1: Neumaier
old_neumaier = """struct Neumaier {
    double sum = 0.0;
    double c   = 0.0;"""

new_neumaier = """#if defined(__clang__)
#pragma clang fp reassociate(off)
#elif defined(__GNUC__)
#pragma GCC push_options
#pragma GCC optimize("no-associative-math")
#endif
struct Neumaier {
    double sum = 0.0;
    double c   = 0.0;"""

text = text.replace(old_neumaier, new_neumaier)

pop_gcc = """        sum = t;
    }
};"""
new_pop = """        sum = t;
    }
};
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC pop_options
#endif"""
if 'pop_options' not in text:
    text = text.replace(pop_gcc, new_pop)

# Patch 2: force_ieee754_strict
old_ieee = """inline void force_ieee754_strict() {
#if defined(POLYDIM_X86)
    _MM_SET_FLUSH_ZERO_MODE(_MM_FLUSH_ZERO_OFF);
    _MM_SET_DENORMALS_ZERO_MODE(_MM_DENORMALS_ZERO_OFF);
    _MM_SET_ROUNDING_MODE(_MM_ROUND_NEAREST);
#endif
}"""
new_ieee = """inline void force_ieee754_strict() {
#if defined(POLYDIM_X86)
    _MM_SET_FLUSH_ZERO_MODE(_MM_FLUSH_ZERO_OFF);
    _MM_SET_DENORMALS_ZERO_MODE(_MM_DENORMALS_ZERO_OFF);
    _MM_SET_ROUNDING_MODE(_MM_ROUND_NEAREST);
#endif
    fesetround(FE_TONEAREST);
}"""
text = text.replace(old_ieee, new_ieee)

# Patch 3: Versine
old_vers = """const double sh   = std::sin(0.5 * theta);
        const double vers = 2.0 * sh * sh;
        const double sn   = std::sin(theta);"""

new_vers = """double vers, sn;
        if (std::abs(theta) < 1e-5) {
            vers = 0.5 * theta * theta;
            sn = theta;
        } else {
            const double sh = std::sin(0.5 * theta);
            vers = 2.0 * sh * sh;
            sn = std::sin(theta);
        }"""
text = text.replace(old_vers, new_vers)

with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V768/auditoria_externa/kernel_cpp_v768.cpp.txt', 'w', encoding='utf-8') as f:
    f.write(text)
with open('E:/POLYDIM_EINSOF/ENTREGA_2026_09_21_V768/auditoria_externa/kernel_cpp_v768.cpp', 'w', encoding='utf-8') as f:
    f.write(text)

print('Applied Pass 3 C++ fixes')
