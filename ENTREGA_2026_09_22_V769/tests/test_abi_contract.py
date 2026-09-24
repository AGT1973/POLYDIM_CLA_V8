"""
POLYDIM V769 — ABI CONTRACT & MEMORY INVARIANT VERIFICATION SUITE
===================================================================
Rigorous verification of cross-language ABI boundaries (C++, Rust, Python ctypes)
and invariant contracts on S^(D-1).

Part of the CI gate to terminate the 600-iteration failure cycle.
"""

import sys
import os
import ctypes
import math
import numpy as np

# Locate DLLs
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TEST_DIR)
AUDIT_DIR = os.path.join(ROOT_DIR, "auditoria_externa")

dll_dir = AUDIT_DIR if os.path.exists(os.path.join(AUDIT_DIR, "polydim_kernel.dll")) else ROOT_DIR

if sys.platform == "win32":
    mingw_bin = r"E:\winlibs_gcc14_zip\mingw64\bin"
    if os.path.exists(mingw_bin):
        try:
            os.add_dll_directory(mingw_bin)
        except Exception:
            pass
    try:
        os.add_dll_directory(dll_dir)
    except Exception:
        pass

c_dll_path = os.path.join(dll_dir, "polydim_kernel.dll")
rust_dll_path = os.path.join(dll_dir, "polydim_rust.dll")

if not os.path.exists(c_dll_path):
    raise FileNotFoundError(f"polydim_kernel.dll not found in {dll_dir}")
if not os.path.exists(rust_dll_path):
    raise FileNotFoundError(f"polydim_rust.dll not found in {dll_dir}")

c_lib = ctypes.CDLL(c_dll_path, winmode=0 if sys.platform == "win32" else None)
rust_lib = ctypes.CDLL(rust_dll_path, winmode=0 if sys.platform == "win32" else None)

# --- STRUCT DEFINITIONS (Mirroring polydim.h) ---

class PMTPControl(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("num_slots", ctypes.c_uint32),
        ("payload_bytes", ctypes.c_uint64),
        ("pub_seq", ctypes.c_uint64),
        ("pub_slot", ctypes.c_uint32),
        ("wlock", ctypes.c_uint32),
        ("wticket", ctypes.c_uint32),
        ("reserved_", ctypes.c_uint8 * 28)
    ]

class PMTPSlotHeader(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("seq", ctypes.c_uint64),
        ("reserved_", ctypes.c_uint8 * 56)
    ]

class PolydimTolerances(ctypes.Structure):
    _fields_ = [
        ("basis_ortho", ctypes.c_double),
        ("point_norm", ctypes.c_double),
        ("gram_ortho", ctypes.c_double),
        ("pivot_rel", ctypes.c_double),
        ("reject_subnormal", ctypes.c_int32)
    ]

class PolydimReport(ctypes.Structure):
    _fields_ = [
        ("point_norm_err", ctypes.c_double),
        ("basis_uu_err", ctypes.c_double),
        ("basis_vv_err", ctypes.c_double),
        ("basis_uv_err", ctypes.c_double),
        ("out_norm_err", ctypes.c_double),
        ("pivot_min", ctypes.c_double),
        ("pivot_threshold", ctypes.c_double),
        ("ortho_err", ctypes.c_double),
        ("threads_used", ctypes.c_uint64)
    ]

class PolydimEdge(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("u", ctypes.c_uint32),
        ("v", ctypes.c_uint32),
        ("w", ctypes.c_float)
    ]

class PolydimBettiResult(ctypes.Structure):
    _fields_ = [
        ("betti0", ctypes.c_uint64),
        ("betti1", ctypes.c_uint64)
    ]

# Bind C++ functions
c_lib.polydim_build_info.restype = ctypes.c_char_p
c_lib.polydim_check_ftz.restype = ctypes.c_int32
c_lib.polydim_selftest_all.restype = ctypes.c_int32

c_lib.polydim_pmtp_sizeof.argtypes = [ctypes.c_uint32, ctypes.c_uint64]
c_lib.polydim_pmtp_sizeof.restype = ctypes.c_uint64
c_lib.polydim_pmtp_alignof.restype = ctypes.c_uint64

c_lib.polydim_pmtp_init.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
c_lib.polydim_pmtp_init.restype = ctypes.c_int32

c_lib.polydim_pmtp_payload_offset.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32]
c_lib.polydim_pmtp_payload_offset.restype = ctypes.c_uint64

c_lib.polydim_pmtp_payload_ptr.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32]
c_lib.polydim_pmtp_payload_ptr.restype = ctypes.c_void_p

c_lib.polydim_pmtp_write_begin.argtypes = [ctypes.POINTER(PMTPControl), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64)]
c_lib.polydim_pmtp_write_begin.restype = ctypes.c_int32

c_lib.polydim_pmtp_write_commit.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
c_lib.polydim_pmtp_write_commit.restype = None

c_lib.polydim_pmtp_write_abort.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
c_lib.polydim_pmtp_write_abort.restype = None

c_lib.polydim_pmtp_read_begin.argtypes = [ctypes.POINTER(PMTPControl), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64)]
c_lib.polydim_pmtp_read_begin.restype = ctypes.c_int32

c_lib.polydim_pmtp_read_validate.argtypes = [ctypes.POINTER(PMTPControl), ctypes.c_uint32, ctypes.c_uint64]
c_lib.polydim_pmtp_read_validate.restype = ctypes.c_int32

c_lib.polydim_rodrigues_geodesic_f64.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_double, ctypes.c_uint64,
    ctypes.POINTER(PolydimTolerances), ctypes.POINTER(PolydimReport)
]
c_lib.polydim_rodrigues_geodesic_f64.restype = ctypes.c_int32

c_lib.polydim_project_sphere_f64.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(PolydimReport)
]
c_lib.polydim_project_sphere_f64.restype = ctypes.c_int32

c_lib.polydim_project_tangent_stiefel_f64.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint32
]
c_lib.polydim_project_tangent_stiefel_f64.restype = ctypes.c_int32

c_lib.polydim_stiefel_cayley_smw_f64.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_uint64, ctypes.c_uint32, ctypes.c_double,
    ctypes.POINTER(PolydimTolerances), ctypes.POINTER(PolydimReport)
]
c_lib.polydim_stiefel_cayley_smw_f64.restype = ctypes.c_int32

c_lib.polydim_cholqr2_f64.argtypes = [
    ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint32
]
c_lib.polydim_cholqr2_f64.restype = ctypes.c_int32

# Bind Rust functions
rust_lib.polydim_rust_verify_invariants.argtypes = [
    ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_double)
]
rust_lib.polydim_rust_verify_invariants.restype = ctypes.c_int32

rust_lib.polydim_rust_betti1_guard.argtypes = [
    ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p
]
rust_lib.polydim_rust_betti1_guard.restype = ctypes.c_int32

# ==============================================================================
# TESTS
# ==============================================================================

def test_abi_struct_sizes():
    """Verify exact byte sizes for FFI structures."""
    print("  [TEST 1] Struct Sizes & Alignments...", end=" ")
    assert ctypes.sizeof(PMTPControl) == 64, f"PMTPControl size mismatch: {ctypes.sizeof(PMTPControl)} != 64"
    assert ctypes.sizeof(PMTPSlotHeader) == 64, f"PMTPSlotHeader size mismatch: {ctypes.sizeof(PMTPSlotHeader)} != 64"
    assert ctypes.sizeof(PolydimTolerances) == 40, f"PolydimTolerances size mismatch: {ctypes.sizeof(PolydimTolerances)} != 40"
    assert ctypes.sizeof(PolydimReport) == 72, f"PolydimReport size mismatch: {ctypes.sizeof(PolydimReport)} != 72"
    assert ctypes.sizeof(PolydimEdge) == 12, f"PolydimEdge size mismatch: {ctypes.sizeof(PolydimEdge)} != 12"
    assert ctypes.sizeof(PolydimBettiResult) == 16, f"PolydimBettiResult size mismatch: {ctypes.sizeof(PolydimBettiResult)} != 16"
    assert c_lib.polydim_pmtp_alignof() == 64, "PMTP alignof must be 64 bytes"
    print("PASSED")

def test_abi_pmtp_field_offsets():
    """Verify byte-level offsets of PMTPControl fields."""
    print("  [TEST 2] PMTP Field Offsets...", end=" ")
    assert PMTPControl.magic.offset == 0, "magic offset != 0"
    assert PMTPControl.num_slots.offset == 4, "num_slots offset != 4"
    assert PMTPControl.payload_bytes.offset == 8, "payload_bytes offset != 8"
    assert PMTPControl.pub_seq.offset == 16, "pub_seq offset != 16"
    assert PMTPControl.pub_slot.offset == 24, "pub_slot offset != 24"
    assert PMTPControl.wlock.offset == 28, "wlock offset != 28"
    assert PMTPControl.wticket.offset == 32, "wticket offset != 32"
    assert PMTPControl.reserved_.offset == 36, "reserved_ offset != 36"
    print("PASSED")

def test_pmtp_sizeof_and_overflow_guards():
    """Verify sizeof calculations and overflow rejection (F-010)."""
    print("  [TEST 3] PMTP sizeof & Overflow Guard (F-010)...", end=" ")
    # Normal calculation
    sz = c_lib.polydim_pmtp_sizeof(4, 1000)
    expected = 64 + 4 * 64 + 4 * 1000
    assert sz == expected, f"sizeof mismatch: {sz} != {expected}"
    
    # Overflow rejection: UINT64_MAX payload must return 0, not wrap to 4096
    sz_ovf = c_lib.polydim_pmtp_sizeof(64, 0xFFFFFFFFFFFFFFFF)
    assert sz_ovf == 0, f"Overflow not rejected! Returned: {sz_ovf}"
    
    # Slot boundary enforcement
    assert c_lib.polydim_pmtp_sizeof(1, 1000) == 0, "num_slots < 2 must be rejected"
    assert c_lib.polydim_pmtp_sizeof(65, 1000) == 0, "num_slots > 64 must be rejected"
    assert c_lib.polydim_pmtp_sizeof(4, 0) == 0, "0 payload_bytes must be rejected"
    print("PASSED")

def test_pmtp_alignment_contract():
    """Verify 64-byte alignment rejection in polydim_pmtp_init (F-008)."""
    print("  [TEST 4] PMTP 64-byte Alignment Contract (F-008)...", end=" ")
    total_sz = c_lib.polydim_pmtp_sizeof(4, 8000)
    raw_buf = bytearray(total_sz + 128)
    addr = ctypes.cast((ctypes.c_char * len(raw_buf)).from_buffer(raw_buf), ctypes.c_void_p).value
    
    # 1. Aligned pointer
    aligned_addr = (addr + 63) & ~63
    ctrl_aligned = ctypes.cast(aligned_addr, ctypes.POINTER(PMTPControl))
    rc_ok = c_lib.polydim_pmtp_init(ctrl_aligned, 4, 8000)
    assert rc_ok == 0, f"Aligned init failed: {rc_ok}"
    
    # 2. Misaligned pointer (+8 bytes offset) -> Must be rejected with -11
    misaligned_addr = aligned_addr + 8
    ctrl_misaligned = ctypes.cast(misaligned_addr, ctypes.POINTER(PMTPControl))
    rc_err = c_lib.polydim_pmtp_init(ctrl_misaligned, 4, 8000)
    assert rc_err == -11, f"Misaligned pointer was not rejected with -11! Returned: {rc_err}"
    print("PASSED")

def test_pmtp_payload_offsets():
    """Verify payload offset and pointer helpers."""
    print("  [TEST 5] PMTP Payload Offsets & Pointers...", end=" ")
    total_sz = c_lib.polydim_pmtp_sizeof(4, 8000)
    raw_buf = bytearray(total_sz + 64)
    addr = ctypes.cast((ctypes.c_char * len(raw_buf)).from_buffer(raw_buf), ctypes.c_void_p).value
    aligned_addr = (addr + 63) & ~63
    ctrl = ctypes.cast(aligned_addr, ctypes.POINTER(PMTPControl))
    c_lib.polydim_pmtp_init(ctrl, 4, 8000)
    
    header_area = 64 + 4 * 64 # PMTP_Control + 4 * SlotHeader = 320
    assert c_lib.polydim_pmtp_payload_offset(ctrl, 0) == header_area
    assert c_lib.polydim_pmtp_payload_offset(ctrl, 1) == header_area + 8000
    assert c_lib.polydim_pmtp_payload_offset(ctrl, 2) == header_area + 16000
    assert c_lib.polydim_pmtp_payload_offset(ctrl, 3) == header_area + 24000
    assert c_lib.polydim_pmtp_payload_offset(ctrl, 4) == 0 # Out of bounds
    
    ptr0 = c_lib.polydim_pmtp_payload_ptr(ctrl, 0)
    assert ptr0 == aligned_addr + header_area
    print("PASSED")

def test_tolerances_nan_rejection():
    """Verify NaN/Inf tolerance validation in C++ kernel (F-016)."""
    print("  [TEST 6] NaN Tolerance Rejection (F-016)...", end=" ")
    D = 128
    y = np.ones(D, dtype=np.float64) / math.sqrt(D)
    u = np.zeros(D, dtype=np.float64); u[0] = 1.0
    v = np.zeros(D, dtype=np.float64); v[1] = 1.0
    out = np.zeros(D, dtype=np.float64)
    rep = PolydimReport()
    
    # Inject NaN in point_norm tolerance
    tol = PolydimTolerances(
        basis_ortho=1e-12, point_norm=float('nan'), gram_ortho=1e-12, pivot_rel=1e-12, reject_subnormal=0
    )
    rc = c_lib.polydim_rodrigues_geodesic_f64(
        y.ctypes.data, u.ctypes.data, v.ctypes.data, out.ctypes.data,
        ctypes.c_double(0.1), ctypes.c_uint64(D),
        ctypes.byref(tol), ctypes.byref(rep)
    )
    assert rc == -8, f"NaN tolerance was not rejected with ERR_INVALID_SCALAR (-8)! Returned: {rc}"
    
    # Inject negative tolerance
    tol_neg = PolydimTolerances(
        basis_ortho=-1.0, point_norm=1e-12, gram_ortho=1e-12, pivot_rel=1e-12, reject_subnormal=0
    )
    rc_neg = c_lib.polydim_rodrigues_geodesic_f64(
        y.ctypes.data, u.ctypes.data, v.ctypes.data, out.ctypes.data,
        ctypes.c_double(0.1), ctypes.c_uint64(D),
        ctypes.byref(tol_neg), ctypes.byref(rep)
    )
    assert rc_neg == -8, f"Negative tolerance was not rejected with -8! Returned: {rc_neg}"
    print("PASSED")

def test_partial_overlap_rejection():
    """Verify partial buffer overlap rejection in Rodrigues & Sphere (F-018, F-019)."""
    print("  [TEST 7] Partial Overlap Rejection (F-018, F-019)...", end=" ")
    D = 128
    buf = np.zeros(D + 64, dtype=np.float64)
    buf[:D] = 1.0 / math.sqrt(D)
    rep = PolydimReport()
    
    # 1. Project Sphere partial overlap: out overlaps with y+1
    ptr_y = buf.ctypes.data
    ptr_y_shifted = buf[1:].ctypes.data
    rc_sphere = c_lib.polydim_project_sphere_f64(
        ptr_y, ptr_y_shifted, ctypes.c_uint64(D), ctypes.byref(rep)
    )
    assert rc_sphere == -11, f"Partial overlap in project_sphere not rejected with -11! Returned: {rc_sphere}"
    
    # 2. Exact in-place: out == y -> MUST BE SUCCESS (F-03)
    rc_inplace = c_lib.polydim_project_sphere_f64(
        ptr_y, ptr_y, ctypes.c_uint64(D), ctypes.byref(rep)
    )
    assert rc_inplace == 0, f"Exact in-place project_sphere failed! rc={rc_inplace}"
    
    # 3. Rodrigues partial overlap
    u = np.zeros(D, dtype=np.float64); u[0] = 1.0
    v = np.zeros(D, dtype=np.float64); v[1] = 1.0
    rc_rod = c_lib.polydim_rodrigues_geodesic_f64(
        ptr_y, u.ctypes.data, v.ctypes.data, ptr_y_shifted,
        ctypes.c_double(0.1), ctypes.c_uint64(D), None, ctypes.byref(rep)
    )
    assert rc_rod == -11, f"Partial overlap in Rodrigues not rejected with -11! Returned: {rc_rod}"
    print("PASSED")

def test_hardware_ftz_canary():
    """Verify FTZ/DAZ mode is actively enabled in hardware (F-015, F-REAL-03)."""
    print("  [TEST 8] Hardware FTZ/DAZ Status (F-REAL-03)...", end=" ")
    ftz = c_lib.polydim_check_ftz()
    assert ftz == 1, f"FTZ/DAZ is NOT enabled! ftz={ftz}"
    build_str = c_lib.polydim_build_info().decode('utf-8')
    assert "FTZ/DAZ=ON" in build_str, f"Build info does not show FTZ/DAZ=ON: {build_str}"
    print(f"PASSED (FTZ=1, {build_str})")

def test_rust_spanner_betti1():
    """Verify Rust Betti-1 Guard ABI and sparse spanner computation."""
    print("  [TEST 9] Rust Betti-1 Guard ABI & Spanner...", end=" ")
    # Build a simple triangle (3 vertices, 3 edges -> 1 cycle -> betti0=1, betti1=1)
    edges = (PolydimEdge * 3)(
        PolydimEdge(u=0, v=1, w=1.0),
        PolydimEdge(u=1, v=2, w=1.0),
        PolydimEdge(u=2, v=0, w=1.0)
    )
    res = PolydimBettiResult()
    rc = rust_lib.polydim_rust_betti1_guard(3, 3, edges, ctypes.byref(res))
    assert rc == 0, f"Rust Betti-1 guard failed with rc={rc}"
    assert res.betti0 == 1, f"Expected betti0=1, got {res.betti0}"
    assert res.betti1 == 1, f"Expected betti1=1 (cycle), got {res.betti1}"
    
    # Fragmented graph: 4 vertices, 1 edge -> 3 components -> Must return ErrTopologyFragmented (-5)
    edges_frag = (PolydimEdge * 1)(
        PolydimEdge(u=0, v=1, w=1.0)
    )
    res_frag = PolydimBettiResult()
    rc_frag = rust_lib.polydim_rust_betti1_guard(4, 1, edges_frag, ctypes.byref(res_frag))
    assert rc_frag == -6, f"Fragmented topology not rejected with -6! Returned: {rc_frag}"
    assert res_frag.betti0 == 3, f"Expected betti0=3 components, got {res_frag.betti0}"
    print("PASSED")

def test_stiefel_tangent_and_retraction():
    """Verify Stiefel tangent projection and Cayley retraction first-order axiom."""
    print("  [TEST 10] Stiefel Tangent & Cayley Retraction Axiom (P0-02)...", end=" ")
    D, K = 64, 4
    np.random.seed(42)
    # Generate random orthonormal matrix X on St(D, K)
    A = np.random.randn(D, K)
    q, r = np.linalg.qr(A)
    X = np.ascontiguousarray(q[:, :K], dtype=np.float64)
    
    # Generate unconstrained Euclidean gradient G
    G = np.ascontiguousarray(np.random.randn(D, K), dtype=np.float64)
    G_proj = np.zeros((D, K), dtype=np.float64)
    
    # 1. Tangent projection
    rc = c_lib.polydim_project_tangent_stiefel_f64(
        X.ctypes.data, G.ctypes.data, G_proj.ctypes.data,
        ctypes.c_uint64(D), ctypes.c_uint32(K)
    )
    assert rc == 0, f"polydim_project_tangent_stiefel_f64 failed: rc={rc}"
    
    # Check skew-symmetry: X^T G_proj + G_proj^T X == 0
    XtGp = X.T @ G_proj
    sym_check = np.max(np.abs(XtGp + XtGp.T))
    assert sym_check <= 1e-14, f"Tangent projection skew-symmetry violation: {sym_check}"
    
    # 2. Retraction first-order axiom: dY/dtau|_{tau=0} = G_proj
    tau = 1e-7
    Y1 = np.zeros((D, K), dtype=np.float64)
    Y2 = np.zeros((D, K), dtype=np.float64)
    rep = PolydimReport()
    
    rc1 = c_lib.polydim_stiefel_cayley_smw_f64(
        X.ctypes.data, G_proj.ctypes.data, Y1.ctypes.data,
        ctypes.c_uint64(D), ctypes.c_uint32(K), ctypes.c_double(tau),
        None, ctypes.byref(rep)
    )
    assert rc1 == 0, f"stiefel_cayley_smw step 1 failed: rc={rc1}"
    
    rc2 = c_lib.polydim_stiefel_cayley_smw_f64(
        X.ctypes.data, G_proj.ctypes.data, Y2.ctypes.data,
        ctypes.c_uint64(D), ctypes.c_uint32(K), ctypes.c_double(2.0 * tau),
        None, ctypes.byref(rep)
    )
    assert rc2 == 0, f"stiefel_cayley_smw step 2 failed: rc={rc2}"
    
    # Velocity finite difference error
    vel = (Y2 - Y1) / tau
    max_vel_err = np.max(np.abs(vel - G_proj))
    rel_vel_err = max_vel_err / np.max(np.abs(G_proj))
    assert rel_vel_err <= 1e-5, f"Retraction velocity axiom failed: rel_err={rel_vel_err}"
    
    # Orthogonality on Stiefel manifold
    ortho_err1 = np.max(np.abs(Y1.T @ Y1 - np.eye(K)))
    ortho_err2 = np.max(np.abs(Y2.T @ Y2 - np.eye(K)))
    assert ortho_err1 <= 1e-14, f"Y1 Stiefel orthogonality violated: {ortho_err1}"
    assert ortho_err2 <= 1e-14, f"Y2 Stiefel orthogonality violated: {ortho_err2}"
    print(f"PASSED (Axiom Err={rel_vel_err:.2e}, Ortho={ortho_err1:.2e})")

# ==============================================================================
# MAIN RUNNER
# ==============================================================================

def run_all_tests():
    print("=" * 80)
    print("🏛️ POLYDIM V769 — ABI CONTRACT VERIFICATION TEST (CI GATE)")
    print("=" * 80)
    test_abi_struct_sizes()
    test_abi_pmtp_field_offsets()
    test_pmtp_sizeof_and_overflow_guards()
    test_pmtp_alignment_contract()
    test_pmtp_payload_offsets()
    test_tolerances_nan_rejection()
    test_partial_overlap_rejection()
    test_hardware_ftz_canary()
    test_rust_spanner_betti1()
    test_stiefel_tangent_and_retraction()
    print("=" * 80)
    print("✅ ALL ABI CONTRACT TESTS PASSED WITH EXIT CODE 0")
    print("=" * 80)

if __name__ == "__main__":
    run_all_tests()
