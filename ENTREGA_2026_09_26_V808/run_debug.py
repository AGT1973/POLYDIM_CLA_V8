import sys, os, traceback
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import test_v808_ipc_suite as t

tests = [
    ('test_gram_dsyrk_dual', t.test_gram_dsyrk_dual),
    ('test_stiefel_shifted_cholqr_and_nt_stream', t.test_stiefel_shifted_cholqr_and_nt_stream),
    ('test_spsc_ring_buffer', t.test_spsc_ring_buffer),
    ('test_allocator_pairing_and_handle', t.test_allocator_pairing_and_handle),
    ('test_rust_iterative_dsu_ultra_scale', t.test_rust_iterative_dsu_ultra_scale),
    ('test_rust_frechet_betti_filter', t.test_rust_frechet_betti_filter),
    ('test_quantum_synthesis_and_lsm', t.test_quantum_synthesis_and_lsm),
]

for name, fn in tests:
    print(f"--> STARTING: {name}")
    try:
        fn()
        print(f"--> SUCCESS: {name}")
    except Exception as e:
        print(f"--> FAILED: {name} with error: {e}")
        traceback.print_exc()
        sys.exit(1)
print("ALL TESTS COMPLETED!")
