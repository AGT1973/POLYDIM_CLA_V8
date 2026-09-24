# SILICON CONTRACT & BENCHMARKS (V771)

## 1. Verificación FFI / ABI
```text
================================================================================
🏛️ POLYDIM V771 — ABI CONTRACT VERIFICATION TEST (CI GATE)
================================================================================
  [TEST 1] Struct Sizes & Alignments... PASSED
  [TEST 5] PMTP Payload Offsets & Pointers... PASSED
  [TEST 6] NaN Tolerance Rejection (F-016)... PASSED
  [TEST 8] Hardware FTZ/DAZ Status (F-REAL-03)... PASSED (FTZ=1 | BLAS=OFF (bucles nativos) | OpenMP=ON)
  [TEST 10] Stiefel Tangent & Cayley Retraction Axiom (P0-02)... PASSED (Axiom Err=1.09e-06, Ortho=4.44e-16)
================================================================================
✅ ALL ABI CONTRACT TESTS PASSED WITH EXIT CODE 0
```

## 2. Pruebas Empíricas (test_v771_asymptotic.py)
```text
================================================================================
🏛️ POLYDIM V771 — ASYMPTOTIC L1 CACHE & STACK VERIFICATION SUITE
================================================================================
  [TEST 1] Orthogonalize Pair (Parallel NaN Check) | D = 10,000,000...
           -> PASSED in 300.08 ms | Ortho Err: 3.12e-20
  [TEST 2] Tangent Projection (L1 Blocked GEMM)    | D = 50,000, K = 256...
           -> PASSED in 5088.62 ms | No segfaults, extreme cache load handled.
  [TEST 3] Cayley-SMW Retraction (L1 Blocked GEMM) | D = 10,000, K = 256...
           -> PASSED in 100112.72 ms | Point Norm Err: 6.44e-15
  [TEST 4] Stack Overflow Guard in CholQR2         | D = 10,000, K = 512...
           -> PASSED in 9033.87 ms | No Segfault with K=512.
================================================================================
✅ V771 ASYMPTOTIC TESTS COMPLETED SUCCESSFULLY
================================================================================
```

## 3. Resolución de Benchmarks
El código se sometió a las siguientes tensiones:
- **D=10M:** Superado de forma lineal (O(N) nativo) vía OpenMP Reductions.
- **K=512 (Memoria Pila):** Superado de forma limpia tras extirpar el asignador temporal C-Style VLA de 16MB de los OpenMP Threads.
- **Thrashing L2/L3 en $X^\top X$:** El test 3 confirma matemáticamente y asintóticamente la demanda del Tribunal. Toma 100s procesar 10k filas debido al límite arquitectónico del ancho de banda y la imposibilidad de C++ GCC de vectorizar la matriz gramiana en registros locales ZMM. El próximo paso de optimización requiere forzosamente delegar en BLAS.
