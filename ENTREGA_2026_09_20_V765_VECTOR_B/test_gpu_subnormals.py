import sys

# HardwareProbe / Hardware Agnosticism Guard (Rule 27)
try:
    import torch
    import triton
    import triton.language as tl
except ImportError:
    print("PyTorch / Triton no disponible en este entorno local (Windows). Ignorando canario GPU.")
    sys.exit(0)

# CANARIO NUMÉRICO: Detección de Flush-To-Zero (FTZ) en A100/H100
# Si el backend de Triton usa FTZ (add.ftz.f32), este kernel producirá ceros en vez de subnormales.

@triton.jit
def subnormal_canary_kernel(
    out_ptr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    # Generar un valor que garantice caer en el rango subnormal de float32
    # float32 min normal = 1.17549435e-38
    # float32 min subnormal = 1.40129846e-45
    
    # 1.0e-30 * 1.0e-12 = 1.0e-42 (Subnormal en FP32)
    val1 = 1.0e-20
    val2 = 1.0e-22
    
    # Casting a FP32 y multiplicacion
    res = tl.cast(val1, tl.float32) * tl.cast(val2, tl.float32)
    
    # Escribimos el resultado
    tl.store(out_ptr + pid, res)

def run_canary():
    if not torch.cuda.is_available():
        print("CUDA no disponible. Ignorando canario GPU.")
        sys.exit(0)
        
    out = torch.zeros(1, dtype=torch.float32, device='cuda')
    
    # Compilamos el kernel y forzamos opciones si es necesario.
    # En ramas recientes (>= 2.1) Triton respeta el flag de denorm_mode o `fast_math=False`
    grid = (1,)
    subnormal_canary_kernel[grid](out, BLOCK_SIZE=1)
    
    val = out[0].item()
    print(f"Valor Subnormal Calculado en GPU (FP32): {val:e}")
    
    if val == 0.0:
        print("PELIGRO: El backend de Triton colapsó el subnormal a CERO (FTZ ACTIVO).")
        print("La variedad S^(D-1) colapsará matemáticamente.")
        sys.exit(1)
    else:
        print("ÉXITO: Triton procesó el subnormal correctamente (Modo IEEE Strict, sin FTZ).")
        sys.exit(0)

if __name__ == '__main__':
    print("=== SABUESO RED TEAM: TRITON SUBNORMAL CANARY ===")
    run_canary()
