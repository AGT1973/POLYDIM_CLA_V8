# POLYDIM EINSOF - ENTREGA V771

## Estado Constitucional y Matemático
Esta entrega V771 cristaliza la auditoría asintótica externa (SOTA Red Team) sobre la arquitectura C++ (V770), aplicando el protocolo de optimización asimétrica $S^{D-1}$ para $D \ge 10^6$ y $K = 512$.

### Brechas Resueltas (Luz Verde)
1. **Reducciones Secuenciales:** En Cayley-SMW (`XtG`), CholQR2 (matriz Gram `A`), y `polydim_orthonormalize_pair_f64` (control `NaN` / `std::isfinite`). Transformadas a regiones `#pragma omp parallel for schedule(static)` de índice exclusivo y barrera estricta (Zero Data Races).
2. **Escudo Zero Trust (Métrica de Cancelación):** Sustitución del falso "Zero Trust" por verificación iterativa empírica. Cálculo de $r_{cancel}$ y control de simetría $a_{sym}$ para detectar cancelación catastrófica de resta flotante en IEEE-754.
3. **L1 Cache Thrashing en $G_{out} = G - X \cdot \text{Sym}$:** Reemplazo de bucle de fila por un Blocked GEMM ($32 \times 32 \times 32$ con ordenamiento $p \to i \to c$) evitando que la lectura de la matriz `Sym` estrangule el bus a RAM para cada fila.
4. **L1 Cache Thrashing en Cayley Update $Y_{out}$:** Idéntica técnica Blocked GEMM sobre $Y_{out} = X \cdot W_X + G \cdot W_G$ evitando el arrastre ciego de las matrices completas de actualización.
5. **Riesgo de Pila (Stack Overflow):** Aborto de teselación local en CholQR2 ($X = X \cdot L^{-T}$) retornando a variable local `temp[512]`, suprimiendo la presión asintótica de 16 MiB sobre la pila de OpenMP de los hilos subyacentes.

## Ficheros
* `kernel_cpp_v771.cpp.txt`: Core aritmético endurecido con pragmas.
* `polydim_v771_monolito.py.txt`: Interfaz FFI C++ / Rust Python.
* `kernel_rust_v771.rs.txt`: Guardianes Betti-1 en Rust (sin cambios arquitectónicos desde V770).
* `polydim_triton_kernel_v771.py.txt`: Kernel PMTP para aceleradores hardware (sin cambios arquitectónicos desde V770).

## Instrucciones de Benchmark (Fase 1 / 2)
El binario DLL `polydim_kernel.dll` (construido con MinGW-w64 GCC 14) ya se encuentra compilado.
El evaluador debe instanciar `perf stat` u observar contadores de hardware (IPC, L1-dcache-load-misses) para validar empíricamente que la intensidad aritmética y el throughput compensan el overhead topológico.
