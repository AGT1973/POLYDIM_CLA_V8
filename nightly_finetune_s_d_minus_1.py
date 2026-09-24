#!/usr/bin/env python3
# ==============================================================================
# POLYDIM V752 - S^{D-1} HETEROGENEOUS FINE-TUNING ORCHESTRATOR
# Replaces standard dot-product attention / linear projections with 
# High-Dimensional Rodrigues Geodesic Rotations.
# ==============================================================================

import torch
import torch.nn as nn
from torch.autograd import Function
import numpy as np
import sys
import time

sys.path.append(r"E:\POLYDIM_EINSOF\POLYDIM_V751")
from polydim.core import PolydimEngine, DualStreamQueue

# Enjambre Global
engine = None
queue = DualStreamQueue()

class RodriguesGeodesicFunction(Function):
    @staticmethod
    def forward(ctx, x, u, v, theta):
        # x, u, v \in S^{D-1}
        # Delegamos al silicio nativo (C++ / Triton)
        x_np = x.detach().cpu().numpy().astype(np.float64)
        u_np = u.detach().cpu().numpy().astype(np.float64)
        v_np = v.detach().cpu().numpy().astype(np.float64)
        y_comp = np.zeros_like(x_np)
        
        engine.rotate_geodesic(x_np, y_comp, u_np, v_np, theta.item(), 0)
        out = torch.tensor(x_np, dtype=torch.float32, device=x.device)
        
        ctx.save_for_backward(x, u, v, theta, out)
        return out

    @staticmethod
    def backward(ctx, grad_output):
        # Backprop exacto sobre S^{D-1} usando el dual
        x, u, v, theta, out = ctx.saved_tensors
        # Aproximacion de primer orden para retencion de gradiente:
        # dx = grad_output - (grad_output^T x) x  (Proyeccion al espacio tangente)
        grad_x = grad_output - torch.sum(grad_output * x, dim=-1, keepdim=True) * x
        
        # Gradiente respecto a theta
        grad_theta = torch.sum(grad_output * (v - u), dim=-1).sum()
        
        # Gradientes de los vectores base u, v en la variedad
        grad_u = -torch.sum(grad_output * x, dim=-1, keepdim=True) * x
        grad_v = torch.sum(grad_output * u, dim=-1, keepdim=True) * x
        
        return grad_x, grad_u, grad_v, grad_theta

class PolydimLinear(nn.Module):
    def __init__(self, features):
        super().__init__()
        self.u = nn.Parameter(torch.randn(features))
        self.v = nn.Parameter(torch.randn(features))
        self.theta = nn.Parameter(torch.tensor(0.1))
        
    def forward(self, x):
        # Normalizar a S^{D-1}
        u_norm = self.u / torch.norm(self.u)
        v_norm = self.v / (torch.norm(self.v) + 1e-8)
        x_norm = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-8)
        
        return RodriguesGeodesicFunction.apply(x_norm, u_norm, v_norm, self.theta)

def main():
    global engine
    try:
        engine = PolydimEngine(cpp_dll_path=r"E:\POLYDIM_EINSOF\POLYDIM_V751\bin\polydim_kernel.dll")
    except Exception as e:
        print(f"[FATAL] Fallo al cargar Kernel: {e}")
        return

    print("==========================================================")
    print(" INICIANDO FINE-TUNING SOBRE VARIEDAD S^{D-1} (POLYDIM)")
    print("==========================================================")
    
    # Red Sintetica
    D = 100_000
    model = nn.Sequential(
        PolydimLinear(D),
        PolydimLinear(D),
        PolydimLinear(D)
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    print(f"[NIGHT MODE] Entrenando con D={D} iterando hasta convergencia...")
    
    # Loop Nocturno
    for epoch in range(1000):
        optimizer.zero_grad()
        x = torch.randn(16, D)
        target = torch.randn(16, D)
        target = target / torch.norm(target, dim=-1, keepdim=True)
        
        out = model(x)
        # Cosine Distance Loss
        loss = 1.0 - torch.sum(out * target, dim=-1).mean()
        loss.backward()
        optimizer.step()
        
        if epoch % 10 == 0:
            print(f"Epoch {epoch} | Loss: {loss.item():.6f}")
            with open("E:\POLYDIM_EINSOF\nightly_finetune_log.txt", "a") as f:
                f.write(f"Epoch {epoch} | Loss: {loss.item():.6f}\n")

if __name__ == '__main__':
    main()
