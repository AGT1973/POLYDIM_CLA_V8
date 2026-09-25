import torch

# ============================================================================
# POLYDIM V803 - TRITON GPU KERNEL (S^{D-1} CAYLEY-RODRIGUES MANIFOLD)
# ============================================================================

def launch_polydim_triton_kernel(x: torch.Tensor, u: torch.Tensor, v: torch.Tensor, y_out: torch.Tensor):
    """
    GPU PyTorch / Triton Fallback Launcher for S^{D-1} Cayley-Rodrigues Manifold Retraction
    """
    u_dot_x = (u * x).sum(dim=1, keepdim=True)
    v_dot_x = (v * x).sum(dim=1, keepdim=True)
    
    y_temp = x + u * v_dot_x - v * u_dot_x
    
    norm_x = torch.norm(x, p=2, dim=1, keepdim=True)
    norm_y = torch.norm(y_temp, p=2, dim=1, keepdim=True)
    
    scale = torch.where(norm_y > 1e-15, norm_x / norm_y, torch.ones_like(norm_x))
    y_out.copy_(y_temp * scale)
