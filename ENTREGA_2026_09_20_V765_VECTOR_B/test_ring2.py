# ============================================================================
# POLYDIM V765 — TEST RING 2: MULTI-AGENT LATENT TELEPATHY (IA-to-IA PMTP)
# Zero-Copy IPC | ND Latent State Transfer on S^(D-1) (D=10,000) | Ghost Protocol
# ============================================================================

import os
import sys
import time
import multiprocessing
import numpy as np

if sys.platform == "win32":
    os.add_dll_directory(r'E:\winlibs_gcc14_zip\mingw64\bin')

DIR_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(DIR_PATH)

from polydim_v764_monolito import PMTPSlabChannel

DLL_PATH = os.path.join(DIR_PATH, "build", "libpolydim.dll")
if not os.path.exists(DLL_PATH):
    DLL_PATH = os.path.join(DIR_PATH, "build", "libpolydim.so")

D_LATENT = 10000
HOPS = 1000

def agent_alpha_encoder(slab_in_tag, slab_out_tag, hops, dll_path):
    """Agent Alpha: Originates ND thoughts, passes them via PMTP to Agent Beta."""
    slab_out = PMTPSlabChannel(slab_out_tag, D_LATENT, dll_path, create=True)
    slab_in = PMTPSlabChannel(slab_in_tag, D_LATENT, dll_path, create=False)
    
    np.random.seed(42)
    state = np.random.randn(D_LATENT)
    state /= np.linalg.norm(state)
    
    latencies = []
    
    for h in range(hops):
        t0 = time.perf_counter_ns()
        slab_out.write_tensor(state)
        
        # Wait for Agent Beta's response
        while True:
            resp = slab_in.read_tensor()
            if resp is not None:
                t1 = time.perf_counter_ns()
                latencies.append((t1 - t0) / 1000.0) # microseconds
                
                # Check topological preservation
                norm = np.linalg.norm(resp)
                if abs(norm - 1.0) > 1e-7:
                    print(f"FATAL: Agent Alpha detected metric collapse! Norm = {norm}")
                    sys.exit(1)
                    
                # Evolve state for next thought cycle
                state = resp + np.random.randn(D_LATENT) * 1e-4
                state /= np.linalg.norm(state)
                break
            time.sleep(0.000005) # 5us yield
            
    avg_lat = np.mean(latencies)
    p99_lat = np.percentile(latencies, 99)
    print(f"[AGENT ALPHA] {hops} Hops Complete! Avg RTT Latency: {avg_lat:.2f} us | P99: {p99_lat:.2f} us")
    slab_out.close()
    slab_in.close()

def agent_beta_reasoner(slab_in_tag, slab_out_tag, hops, dll_path):
    """Agent Beta: Receives ND thoughts, applies Householder Riemannian reflection, returns."""
    slab_in = PMTPSlabChannel(slab_in_tag, D_LATENT, dll_path, create=False)
    slab_out = PMTPSlabChannel(slab_out_tag, D_LATENT, dll_path, create=True)
    
    v = np.ones(D_LATENT) / np.sqrt(D_LATENT)
    
    for h in range(hops):
        while True:
            thought = slab_in.read_tensor()
            if thought is not None:
                # Reason in ND: Apply Householder reflection across hyper-plane
                reflected = thought - 2.0 * np.dot(thought, v) * v
                reflected /= np.linalg.norm(reflected)
                
                # Return refined thought
                slab_out.write_tensor(reflected)
                break
            time.sleep(0.000005) # 5us yield
            
    slab_in.close()
    slab_out.close()

if __name__ == "__main__":
    print(f"\n============================================================================")
    print(f"POLYDIM V765 — TEST RING 2: MULTI-AGENT LATENT TELEPATHY (D={D_LATENT:,})")
    print(f"============================================================================")
    
    tag_ab = "telepathy_alpha_to_beta"
    tag_ba = "telepathy_beta_to_alpha"
    
    # Pre-create channels
    c1 = PMTPSlabChannel(tag_ab, D_LATENT, DLL_PATH, create=True)
    c2 = PMTPSlabChannel(tag_ba, D_LATENT, DLL_PATH, create=True)
    
    p_alpha = multiprocessing.Process(target=agent_alpha_encoder, args=(tag_ba, tag_ab, HOPS, DLL_PATH))
    p_beta = multiprocessing.Process(target=agent_beta_reasoner, args=(tag_ab, tag_ba, HOPS, DLL_PATH))
    
    p_beta.start()
    p_alpha.start()
    
    p_alpha.join()
    p_beta.join()
    
    if p_alpha.exitcode == 0 and p_beta.exitcode == 0:
        print("\n-> TEST RING 2 PASSED: 1,000 Zero-Copy Latent Telepathy Hops Certified (Exit Code 0).")
    else:
        print("\n-> TEST RING 2 FAILED!")
        sys.exit(1)
