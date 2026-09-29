# SILICON CONTRACT & REGLAS ASINTÓTICAS
1. **Agnosticismo de Hardware:** El código interroga dinámicamente si hay TPU (Pallas), CUDA o OpenMP CPU.
2. **Zero-Copy IPC:** Prohibido usar sockets, gRPC o JSON para movimiento masivo de datos. Uso exclusivo de memoria compartida PMTP.
3. **Asintótica O(N):** Todas las iteraciones sobre dimensiones  \ge 10^6$ deben evitar el Drift Numérico FP32 usando Suma de Neumaier-Kahan.
