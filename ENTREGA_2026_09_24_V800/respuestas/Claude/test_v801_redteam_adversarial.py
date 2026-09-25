import numpy as np
import ctypes
import os
import sys
import time
import math

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from polydim_v801_monolito import PolydimV801Kernel, PolydimError

# ============================================================================
# POLYDIM V801 - RED TEAM ADVERSARIAL ASYMPTOTIC SUITE
#
# CHANGELOG vs V800 (test methodology fixes -- these are as important as the
# code fixes, since a vacuous test hides real regressions forever):
#   [FIX-17] TEST 6 ("Non-Contiguous Memory Assertion") in V800 only checked
#            a raw NumPy .flags.c_contiguous property on an array that was
#            never passed into the actual POLYDIM code path. It would still
#            report [PASS] even if the real rejection logic in the
#            orchestrator were deleted entirely. It now actually calls
#            execute_cayley_smw with a Fortran-order array and asserts it
#            is rejected.
#   [FIX-18] TEST 7 ("Triton GPU Kernel") in V800 wrapped everything in a
#            bare `except Exception` and reported [PASS] even on
#            ModuleNotFoundError / ImportError -- meaning the GPU kernel
#            file was never actually validated even once across the whole
#            V800 dossier. Now distinguishes "no GPU present, legitimate
#            skip" from "the kernel code itself is broken", and only the
#            former is a [PASS].
#   [NEW] TEST 8: Inf injection (not just NaN). The audit protocol itself
#            (01_README) demanded +-inf coverage; V800's suite never
#            delivered it.
#   [NEW] TEST 9: ISA/silicon-contract guard (FIX-04). Confirms the runtime
#            CPUID probe returns 0 on this host for the flags this binary
#            was actually built with.
# ============================================================================


class RedTeamAuditSuite:
    def __init__(self, delivery_dir: str):
        self.delivery_dir = delivery_dir
        self.cpp_dll_path = os.path.join(delivery_dir, "polydim_kernel_v801.so")
        self.rust_dll_path = os.path.join(delivery_dir, "polydim_rust_guard_v801.so")
        self.passed_tests = 0
        self.total_tests = 0
        self.kernel = PolydimV801Kernel(self.cpp_dll_path, self.rust_dll_path)

    def log_result(self, test_name: str, passed: bool, detail: str = ""):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print(f"  [PASS] {test_name} - {detail}", flush=True)
        else:
            print(f"  [FAIL] {test_name} - {detail}", flush=True)

    def test_abi_and_version(self):
        ver = self.kernel.cpp_lib.polydim_abi_version()
        self.log_result("TEST 1: C++ ABI Version", ver == 801, f"Expected 801, got {ver}")

    def test_isa_guard(self):
        # [NEW]
        ret = self.kernel.cpp_lib.polydim_check_isa_support_v801()
        self.log_result("TEST 2: Runtime ISA/Silicon-Contract Guard", ret == 0, f"polydim_check_isa_support_v801 returned {ret} (0 = binary ISA matches this CPU)")

    def test_rust_guard_validations(self):
        D, K = 1_000_000, 32
        expected_bytes = D * K * 8
        ret1 = self.kernel.rust_lib.polydim_validate_tensor_v801(D, K, expected_bytes)
        ret2 = self.kernel.rust_lib.polydim_validate_tensor_v801(D, K, expected_bytes - 100)

        self.kernel.rust_lib.polydim_higham_bound_v801.argtypes = [ctypes.c_int64]
        self.kernel.rust_lib.polydim_higham_bound_v801.restype = ctypes.c_double
        bound = self.kernel.rust_lib.polydim_higham_bound_v801(D)
        eps = sys.float_info.epsilon / 2.0
        expected_bound = 50.0 * math.ceil(math.log2(D)) * eps

        # [FIX-10 regression] d<=0 must now be a well-defined NaN, not a crash.
        bad_bound = self.kernel.rust_lib.polydim_higham_bound_v801(0)

        passed = (ret1 == 0 and ret2 == -3 and abs(bound - expected_bound) < 1e-18 and math.isnan(bad_bound))
        self.log_result("TEST 3: Rust Guard Safeguards", passed, f"Higham Bound D=1M: {bound:.4e}, D=0 -> NaN: {math.isnan(bad_bound)}")

    def test_asymptotic_happy_path(self):
        D, K = 1_000_000, 32
        X = np.full((D, K), 0.5); U = np.full((D, K), 0.25); V = np.full((D, K), 0.125); Y = np.zeros((D, K))
        t0 = time.perf_counter()
        self.kernel.execute_cayley_smw(X, U, V, Y)
        dt = (time.perf_counter() - t0) * 1000.0
        expected_val = 0.5 + (0.25 * 0.125)
        abs_err = abs(Y[0, 0] - expected_val)
        self.log_result("TEST 4: Asymptotic Happy Path D=1M, K=32", abs_err < 1e-12, f"Time: {dt:.2f} ms | Error: {abs_err:.4e}")

    def test_nan_poison_injection(self):
        D, K = 100_000, 32
        X = np.ones((D, K)); U = np.ones((D, K)); V = np.ones((D, K)); Y = np.zeros((D, K))
        U[50_000, 15] = np.nan
        try:
            self.kernel.execute_cayley_smw(X, U, V, Y)
            passed = False
            detail = "no exception raised"
        except PolydimError:
            # [FIX-03 regression] the poisoned cell must be explicit NaN, and
            # an unrelated cell must still hold a correct value.
            passed = np.isnan(Y[50_000, 15]) and abs(Y[0, 0] - 2.0) < 1e-12
            detail = f"Y at poisoned cell is NaN: {np.isnan(Y[50_000, 15])}, unrelated cell still correct: {abs(Y[0,0]-2.0)<1e-12}"
        self.log_result("TEST 5: NaN Poison Trap", passed, detail)

    def test_inf_poison_injection(self):
        # [NEW] the audit protocol demanded this; V800 never had it.
        D, K = 100_000, 32
        X = np.ones((D, K)); U = np.ones((D, K)); V = np.ones((D, K)); Y = np.zeros((D, K))
        V[77_000, 4] = np.inf
        try:
            self.kernel.execute_cayley_smw(X, U, V, Y)
            passed = False
            detail = "no exception raised"
        except PolydimError:
            passed = np.isnan(Y[77_000, 4])
            detail = f"Y at poisoned cell is NaN: {np.isnan(Y[77_000, 4])}"
        self.log_result("TEST 6: Inf Poison Trap", passed, detail)

    def test_subnormal_fpu_guard(self):
        D, K = 500_000, 32
        X = np.random.randn(D, K); U = np.full((D, K), 1e-308); V = np.full((D, K), 1e-308); Y = np.zeros((D, K))
        t0 = time.perf_counter()
        try:
            self.kernel.execute_cayley_smw(X, U, V, Y)
            ok = not np.isnan(Y[0, 0])
        except PolydimError:
            ok = False
        dt = (time.perf_counter() - t0) * 1000.0
        self.log_result("TEST 7: Subnormal FPU Guard", ok, f"Time: {dt:.2f} ms")

    def test_non_contiguous_rejection(self):
        # [FIX-17] now actually exercises execute_cayley_smw instead of just
        # reading a NumPy flag on an array nobody ever passed to POLYDIM.
        X_f = np.zeros((1000, 32), dtype=np.float64, order='F')
        U = np.zeros((1000, 32)); V = np.zeros((1000, 32)); Y = np.zeros((1000, 32))
        try:
            self.kernel.execute_cayley_smw(X_f, U, V, Y)
            passed = False
            detail = "non-contiguous tensor was NOT rejected"
        except ValueError:
            passed = True
            detail = "execute_cayley_smw correctly rejected the Fortran-order tensor"
        self.log_result("TEST 8: Non-Contiguous Memory Assertion (real call path)", passed, detail)

    def test_triton_gpu(self):
        # [FIX-18]
        try:
            import torch
        except ImportError as e:
            self.log_result("TEST 9: Triton GPU Kernel", True, f"torch not installed, legitimate CPU-only skip ({e})")
            return
        if not torch.cuda.is_available():
            self.log_result("TEST 9: Triton GPU Kernel", True, "No CUDA GPU present, legitimate skip. NOTE: kernel code is NOT validated by this skip.")
            return
        try:
            from polydim_triton_kernel_v801 import launch_polydim_triton_kernel
            D, K = 100_000, 32
            X = torch.randn((D, K), dtype=torch.float64, device='cuda')
            U = torch.randn((D, K), dtype=torch.float64, device='cuda')
            V = torch.randn((D, K), dtype=torch.float64, device='cuda')
            Y = torch.zeros((D, K), dtype=torch.float64, device='cuda')
            ret = launch_polydim_triton_kernel(X, U, V, Y)
            torch.cuda.synchronize()
            self.log_result("TEST 9: Triton GPU Kernel", ret == 0, f"GPU execution ret={ret}")
        except Exception as e:
            self.log_result("TEST 9: Triton GPU Kernel", False, f"GPU present but kernel raised: {e}")

    def run_all(self):
        print("=" * 75)
        print("POLYDIM V801 RED TEAM ADVERSARIAL ASYMPTOTIC SUITE")
        print("=" * 75)
        self.test_abi_and_version()
        self.test_isa_guard()
        self.test_rust_guard_validations()
        self.test_asymptotic_happy_path()
        self.test_nan_poison_injection()
        self.test_inf_poison_injection()
        self.test_subnormal_fpu_guard()
        self.test_non_contiguous_rejection()
        self.test_triton_gpu()
        print("=" * 75)
        print(f"VERDICT: {self.passed_tests}/{self.total_tests} TESTS PASSED")
        print("=" * 75)
        return 0 if self.passed_tests == self.total_tests else 1


if __name__ == "__main__":
    delivery_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(os.path.dirname(delivery_dir), "src")
    sys.path.insert(0, src_dir)
    suite = RedTeamAuditSuite(src_dir)
    sys.exit(suite.run_all())
