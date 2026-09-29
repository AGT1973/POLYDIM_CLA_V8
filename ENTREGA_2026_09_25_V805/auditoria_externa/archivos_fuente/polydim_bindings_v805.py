import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

def ensure_c_contiguous(tensor):
    """
    Ensures that a tensor (PyTorch or NumPy) is C-contiguous before passing to C++/Rust FFI.
    """
    if HAS_TORCH and isinstance(tensor, torch.Tensor):
        return tensor.cpu().contiguous() if tensor.is_cuda else tensor.contiguous()
    elif isinstance(tensor, np.ndarray):
        return np.ascontiguousarray(tensor)
    else:
        raise TypeError("Input must be a PyTorch tensor or NumPy array.")
