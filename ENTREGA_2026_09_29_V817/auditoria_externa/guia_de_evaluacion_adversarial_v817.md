# 📋 GUÍA DE EVALUACIÓN ADVERSARIAL Y REVISIÓN POR PARES — V817

---

## 1. 🎯 OBJETIVO DE LA EVALUACIÓN
La presente guía establece el marco metodológico para que evaluadores externos (humanos o IAs de frontera) sometan a prueba el release **POLYDIM V817**.

---

## 2. 🔬 PROCEDIMIENTO DE REPRODUCCIÓN EN SILICIO

### Paso 1: Compilación de Kernels Nativos
```bash
# Compilación Rust (MSVC / MinGW ABI)
rustc --crate-type cdylib -O -C opt-level=3 -C panic=unwind kernel_rust_v817.rs -o polydim_rust_v817.dll

# Compilación C++20 OpenMP / AVX2 (GCC 14.2 MinGW64)
g++ -std=c++20 -O3 -mavx2 -mfma -fopenmp -static-libgcc -static-libstdc++ -shared kernel_cpp_v817.cpp -o polydim_cpp_v817.dll
```

### Paso 2: Ejecución de la Suite Completa (10 Tests Físicos)
```bash
python test_v817_comprehensive_suite.py
```
**Criterio de Aceptación:** 10/10 PASS — Exit Code 0.

### Paso 3: Ejecución de la Batería Adversarial de Destrucción (3 Sabuesos)
```bash
python fuzz_v817_destructive_hounds.py
```
**Criterio de Aceptación:** Cero colisiones TLS, cero memoria corrupta bajo 100 hilos concurrentes y $D=1,000,000$.

---

## 3. 📊 MATRIZ DE ACEPTACIÓN EMPÍRICA (GROUND TRUTH)

| Test | Métrica Evaluada | Criterio de Éxito | Valor Medido en AMD A4 Floor |
| :--- | :--- | :--- | :--- |
| **TEST 1** | Separación de Secantes $\alpha_{\mathcal{K}}$ ($3072 \to 1536$) | $\alpha_{\mathcal{K}} > 0.5$, $\Delta_{\max} < 0.2$ | $\alpha_{\mathcal{K}} = 0.9289$, $\Delta_{\max} = 0.0711$ |
| **TEST 2** | Clamp Numérico Geodésico | Distancia en auto-identidad $< 10^{-10}$ rad | $0.0\text{ rad}$ (Sin NaNs) |
| **TEST 3** | Homología Simplicial $\beta_1$ | Anulación exacta $\beta_1 = 0$ con 2-símplices | $\beta_1 = 3 \to 0$ |
| **TEST 4** | Freno Espectral AuON ($|x|=100,000$) | $|\partial\mathcal{L}/\partial x| \le \lambda s = 4.5$ | $4.5000$ (Sin overflow) |
| **TEST 5** | Aislamiento FFI Thread-Local | Error copiado a memoria privada | String clonado inmediatamente |
| **TEST 6** | Concurrencia QSBR Copy-Out | Integridad de payload de 1 MB | $875.3\ \mu\text{s}$ (Zero UAF) |
| **TEST 7** | Desigualdad Shannon (DPI) | $I(\text{Task}; Z_{\text{lat}}) \ge I(\text{Task}; Z_{\text{txt}})$ | $3.0017 \ge 1.3968\text{ nats}$ |
| **TEST 8** | Throughput de Ruta de Datos en RAM | Ancho de banda $> 1.0\text{ GB/s}$ | $2.80\text{ GB/s}$ ($49.0\times$) |
| **TEST 9** | Cota Baraniuk–Wakin ($3072 \to 1536$) | $m_{\text{req}} \le 1536$ con $d_A \le 16$ | $m_{\text{req}} = 1215.73 < 1536$ |
| **TEST 10** | Gram-NS ($q \le 2$) & AuON Matrix RMS | Error ortogonalidad $< 0.2$, $\text{RMS} > 0$ | $\text{Err} = 0.12$, $\text{RMS} = 1.0005$ |
