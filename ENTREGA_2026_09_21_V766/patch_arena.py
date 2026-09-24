import sys

content = open('src/polydim_kernel.cpp').read()

old_arena = """    std::vector<double> arena;
    try { arena.assign(static_cast<size_t>(nthreads) * KK2, 0.0); }
    catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }"""

new_arena = """    // Pad thread arena to 64 bytes (8 doubles) to strictly prevent false sharing
    const size_t stride_doubles = (static_cast<size_t>(KK2) + 7) & ~7ULL;
    std::vector<double> arena;
    try { arena.assign(static_cast<size_t>(nthreads) * stride_doubles, 0.0); }
    catch (const std::bad_alloc&) { return POLYDIM_ERR_BUFFER_OVERFLOW; }"""

content = content.replace(old_arena, new_arena)

old_tid = "double* L = arena.data() + static_cast<size_t>(tid) * KK2;"
new_tid = "double* L = arena.data() + static_cast<size_t>(tid) * stride_doubles;"
content = content.replace(old_tid, new_tid)

old_sum = "for (int t = 0; t < nthreads; ++t) s += arena[static_cast<size_t>(t) * KK2 + j];"
new_sum = "for (int t = 0; t < nthreads; ++t) s += arena[static_cast<size_t>(t) * stride_doubles + j];"
content = content.replace(old_sum, new_sum)

open('src/polydim_kernel.cpp', 'w').write(content)
print("Arena padded successfully")
