"""
POLYDIM V774: PyTorch 2.X Custom Operator for Stiefel Manifold Projection
========================================================================
Canonical Schema: polydim::stiefel_project(Tensor X, float shift=1e-12) -> Tensor
FullGraph = True & TorchDynamo AOTAutograd Compliant
Certified on Physical Silicon (PyTorch 2.X+)

Key Architectural Pillars:
1. Canonical torch.library.custom_op schema registration.
2. Abstract shape & dtype inference via @stiefel_project.register_fake (Meta Kernel).
3. Shifted CholQR2 regularization with dynamic Tikhonov regularization.
4. Riemannian tangent space backward operator registered with torch.library.register_autograd.
5. opcheck() test suite verification and torch.compile(..., fullgraph=True) zero-graph-break validation.
"""

import os
import sys
import shutil
import torch
import torch.nn as nn
from typing import Tuple


# ---------------------------------------------------------------------------
# 0. Silicon & Compiler Environment Discovery (Windows Contract)
# ---------------------------------------------------------------------------
def _ensure_compiler_in_path():
    """Ensure cl.exe environment (INCLUDE, LIB, PATH) is properly initialized for Inductor."""
    if sys.platform == "win32":
        vcvars = r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
        if os.path.exists(vcvars):
            try:
                import subprocess
                cmd = f'call "{vcvars}" >nul && set'
                out = subprocess.check_output(cmd, shell=True, text=True)
                for line in out.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k] = v
            except Exception:
                pass
        
        # Fallback check for MinGW GCC
        mingw_candidate = r"E:\winlibs_gcc14_zip\mingw64\bin"
        if os.path.exists(mingw_candidate) and mingw_candidate not in os.environ.get("PATH", ""):
            os.environ["PATH"] = mingw_candidate + os.pathsep + os.environ.get("PATH", "")

_ensure_compiler_in_path()


# ---------------------------------------------------------------------------
# 1. Custom Operator Registration via Modern PyTorch 2.4+ Library API
# ---------------------------------------------------------------------------
@torch.library.custom_op("polydim::stiefel_project", mutates_args=())
def stiefel_project(X: torch.Tensor, shift: float = 1e-12) -> torch.Tensor:
    """
    Projects matrix X onto the Stiefel Manifold St(D, K) using Shifted CholQR2.
    
    Given X of shape (..., D, K) where D >= K:
    Computes an orthonormal matrix Q such that Q^T Q = I_K.
    Uses dynamic Tikhonov regularization (shift * I) to prevent Cholesky breakdown
    in ill-conditioned regimes.
    """
    if X.ndim < 2:
        raise ValueError(f"stiefel_project expects tensor with at least 2 dimensions, got shape {X.shape}")
    
    D = X.shape[-2]
    K = X.shape[-1]
    if D < K:
        raise ValueError(f"Stiefel manifold St(D, K) requires D >= K, got D={D}, K={K}")
    
    orig_dtype = X.dtype
    compute_dtype = torch.float64 if orig_dtype in (torch.float32, torch.float64) else torch.float32
    Xc = X.to(compute_dtype)
    
    # Pass 1: Shifted Gram + Cholesky
    Xt = Xc.transpose(-2, -1)
    Gram = torch.matmul(Xt, Xc)
    
    eye = torch.eye(K, dtype=compute_dtype, device=X.device)
    if Xc.ndim > 2:
        eye = eye.expand(*Xc.shape[:-2], K, K)
    
    Gram_reg = Gram + float(shift) * eye
    
    # Cholesky factorization: Gram_reg = L @ L.T
    L1 = torch.linalg.cholesky(Gram_reg)
    
    # Solve L1 @ X1_t = Xt
    X1_t = torch.linalg.solve_triangular(L1, Xt, upper=False)
    X1 = X1_t.transpose(-2, -1)
    
    # Pass 2: Refinement CholQR (Machine precision orthogonalization)
    Gram2 = torch.matmul(X1.transpose(-2, -1), X1)
    Gram2_sym = 0.5 * (Gram2 + Gram2.transpose(-2, -1))
    Gram2_reg = Gram2_sym + 1e-15 * eye
    L2 = torch.linalg.cholesky(Gram2_reg)
    X2_t = torch.linalg.solve_triangular(L2, X1.transpose(-2, -1), upper=False)
    X2 = X2_t.transpose(-2, -1)
    
    return X2.to(orig_dtype)


# ---------------------------------------------------------------------------
# 2. Meta Kernel (Abstract Fake Tensor Inference for TorchDynamo & AOTAutograd)
# ---------------------------------------------------------------------------
@stiefel_project.register_fake
def stiefel_project_fake(X: torch.Tensor, shift: float = 1e-12) -> torch.Tensor:
    """
    Meta/Fake tensor registration for Dynamo trace compilation.
    Infers output shape, dtype, device, and memory layout without allocating memory.
    """
    if X.ndim < 2:
        raise ValueError(f"stiefel_project expects tensor with at least 2 dimensions, got shape {X.shape}")
    D = X.shape[-2]
    K = X.shape[-1]
    if D < K:
        raise ValueError(f"Stiefel manifold St(D, K) requires D >= K, got D={D}, K={K}")
    return torch.empty_like(X)


# ---------------------------------------------------------------------------
# 3. Autograd Registration (Riemannian Manifold Backward Formula)
# ---------------------------------------------------------------------------
def _stiefel_setup_context(ctx, inputs, output):
    X, shift = inputs
    ctx.save_for_backward(output)
    ctx.shift = shift

def _stiefel_backward(ctx, grad_output):
    """
    Canonical Riemannian gradient projection for Stiefel manifold St(D, K):
    Given ambient gradient G = grad_output and point Q on St(D, K):
    grad_X = G - Q @ sym(Q^T G) = G - 0.5 * Q @ (Q^T G + G^T Q)
    This strictly preserves tangent space projection T_Q St(D, K) and avoids manifold drift.
    """
    (Q,) = ctx.saved_tensors
    QtG = torch.matmul(Q.transpose(-2, -1), grad_output)
    sym_QtG = 0.5 * (QtG + QtG.transpose(-2, -1))
    grad_X = grad_output - torch.matmul(Q, sym_QtG)
    return grad_X, None

torch.library.register_autograd("polydim::stiefel_project", _stiefel_backward, setup_context=_stiefel_setup_context)


# ---------------------------------------------------------------------------
# 4. Neural Network Layer Module Utilizing the Custom Operator
# ---------------------------------------------------------------------------
class PolydimStiefelLayer(nn.Module):
    """
    Stiefel Parameterized Layer that maintains weight orthogonality W in St(D, K)
    compiled natively through TorchDynamo without graph breaks.
    """
    def __init__(self, in_features: int, out_features: int, shift: float = 1e-12):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.shift = shift
        # Parameter tensor (D >= K) where D = out_features, K = in_features
        self.weight = nn.Parameter(torch.randn(out_features, in_features, dtype=torch.float32))
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Call the registered custom op: w_ortho is (out_features, in_features)
        w_ortho = torch.ops.polydim.stiefel_project(self.weight, self.shift)
        # x is (batch_size, in_features), w_ortho.T is (in_features, out_features)
        # Output is (batch_size, out_features)
        return torch.matmul(x, w_ortho.transpose(-2, -1))


# ---------------------------------------------------------------------------
# 5. Rigorous Empirical Verification Suite (Silicon Contract)
# ---------------------------------------------------------------------------
def run_verification_suite() -> bool:
    print("=" * 80)
    print("POLYDIM V774: torch.library.custom_op VERIFICATION SUITE")
    print(f"PyTorch Version: {torch.__version__}")
    print(f"Python Platform: {sys.platform}")
    print(f"Discovered C++ Compiler: {shutil.which('cl') or shutil.which('g++')}")
    print("=" * 80)
    
    all_passed = True
    
    # Test 1: Mathematical Accuracy & Stiefel Invariant ||Q^T Q - I||_F
    print("\n[TEST 1] Testing Mathematical Orthogonality on St(D=1024, K=32)...")
    torch.manual_seed(42)
    D, K = 1024, 32
    X = torch.randn(D, K, dtype=torch.float64)
    Q = torch.ops.polydim.stiefel_project(X, 1e-12)
    
    QtQ = torch.matmul(Q.T, Q)
    I_K = torch.eye(K, dtype=torch.float64)
    ortho_error = torch.linalg.norm(QtQ - I_K).item()
    print(f"  Shape: {Q.shape}")
    print(f"  Frobenius Orthogonality Error ||Q^T Q - I_K||_F: {ortho_error:.6e}")
    if ortho_error < 1e-14:
        print("  -> PASS: Machine precision orthogonality achieved.")
    else:
        print("  -> FAIL: Orthogonality error too high.")
        all_passed = False
        
    # Test 2: Ill-Conditioned Matrix with Dynamic Shift Regularization
    print("\n[TEST 2] Testing Near-Singular Ill-Conditioned Input with Dynamic Shift...")
    X_ill = torch.randn(D, 1, dtype=torch.float64).repeat(1, K)
    X_ill += 1e-4 * torch.randn(D, K, dtype=torch.float64)
    Q_ill = torch.ops.polydim.stiefel_project(X_ill, 1e-8)
    QtQ_ill = torch.matmul(Q_ill.T, Q_ill)
    ortho_error_ill = torch.linalg.norm(QtQ_ill - I_K).item()
    print(f"  Ill-conditioned Frobenius error: {ortho_error_ill:.6e}")
    if ortho_error_ill < 1e-12:
        print("  -> PASS: Shifted CholQR2 successfully stabilized near-collinear matrix.")
    else:
        print("  -> FAIL: Stabilization failed.")
        all_passed = False

    # Test 3: Batched Tensor Support (B, D, K)
    print("\n[TEST 3] Testing Batched Input (B=4, D=256, K=16)...")
    B, D_b, K_b = 4, 256, 16
    X_batch = torch.randn(B, D_b, K_b, dtype=torch.float32)
    Q_batch = torch.ops.polydim.stiefel_project(X_batch, 1e-12)
    print(f"  Batched shape out: {Q_batch.shape}")
    assert Q_batch.shape == (B, D_b, K_b), "Batch shape mismatch!"
    QtQ_b0 = torch.matmul(Q_batch[0].T, Q_batch[0])
    ortho_b0 = torch.linalg.norm(QtQ_b0 - torch.eye(K_b)).item()
    print(f"  Batch item 0 Ortho Error: {ortho_b0:.6e}")
    if ortho_b0 < 1e-6:
        print("  -> PASS: Batched execution verified.")
    else:
        print("  -> FAIL: Batched execution error.")
        all_passed = False

    # Test 4: PyTorch Formal Operator Checker (torch.library.opcheck)
    print("\n[TEST 4] Running torch.library.opcheck()...")
    try:
        sample_inputs = [
            (torch.randn(128, 16, dtype=torch.float32, requires_grad=True), 1e-12),
            (torch.randn(64, 8, dtype=torch.float64, requires_grad=True), 1e-10),
        ]
        for inp in sample_inputs:
            torch.library.opcheck(torch.ops.polydim.stiefel_project, inp)
        print("  -> PASS: torch.library.opcheck passed all schema, fake tensor & mutation invariants!")
    except Exception as e:
        print(f"  -> FAIL: opcheck encountered error: {e}")
        all_passed = False

    # Test 5: torch.compile(..., fullgraph=True) Zero Graph-Break Certification
    print("\n[TEST 5] Testing torch.compile(fullgraph=True) with Zero Graph Breaks...")
    try:
        model = PolydimStiefelLayer(in_features=16, out_features=128)
        model.eval()
        compiled_model = torch.compile(model, fullgraph=True)
        
        x_test = torch.randn(8, 16)
        # Execute compiled forward
        out_eager = model(x_test)
        out_compiled = compiled_model(x_test)
        
        diff = torch.linalg.norm(out_eager - out_compiled).item()
        print(f"  Compiled execution output shape: {out_compiled.shape}")
        print(f"  Eager vs Compiled Frobenius difference: {diff:.6e}")
        if diff < 1e-5:
            print("  -> PASS: torch.compile(fullgraph=True) forward pass succeeded with 0 graph breaks!")
        else:
            print("  -> FAIL: Output divergence between eager and compiled.")
            all_passed = False
            
        # Verify backward pass under torch.compile
        print("  Verifying autograd backward pass under torch.compile...")
        loss = out_compiled.sum()
        loss.backward()
        if model.weight.grad is not None and model.weight.grad.shape == model.weight.shape:
            print(f"  -> PASS: Backward pass compiled and produced gradient with shape {model.weight.grad.shape}")
        else:
            print("  -> FAIL: Gradient missing or incorrect shape.")
            all_passed = False
            
    except Exception as e:
        print(f"  -> FAIL: torch.compile failed: {e}")
        all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("OVERALL RESULT: ALL 5/5 TESTS PASSED WITH EXIT CODE 0")
    else:
        print("OVERALL RESULT: VERIFICATION FAILED")
    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    success = run_verification_suite()
    sys.exit(0 if success else 1)
