# 🏛️ INGESTA SOTA V800: CONSENSO BIZANTINO (BFT) EN BUS PMTP
**Fecha:** 2026-09-24
**Módulo:** Guardián Topológico Rust / Fréchet-Betti BFT Filtration

## Arquitectura de 3 Fases del Guardián V800
1. **Fase 1 - Validación Atómica (StickyCAS):** ~2-5 µs. Primitiva CAS no corrompible ($n \ge 3f+1$). Impide escrituras bizantinas en memoria compartida.
2. **Fase 2 - Agregación Robusta (Garfield/Krum):** ~1-10 ms. Filtro estadístico (median, trimmed mean, Krum) que tolera $f < n/2$ nodos maliciosos.
3. **Fase 3 - Filtrado Topológico (TDA+Betti):** ~15-60 ms. Curvas de Betti $\beta_k(t)$ del tensor candidato comparadas contra Atlas de Consenso (media de Fréchet). Distancia bottleneck $d_B > \varepsilon_{max}$ → rechazo.

## Reputación Dinámica por Agente
Score $R_{t+1} = \alpha R_t + (1-\alpha) \cdot \mathbb{I}[\text{aceptado}]$. Si $R_t < R_{min}$, bloqueo de escrituras.

## Overhead Total Estimado
- Latencia: ~20-70 ms por tensor (aceptable para gating asíncrono).
- Throughput: ~100-500 tensores/segundo.

## Librerías Clave
- `gudhi` (C++/Python): Distancia bottleneck + Fréchet mean.
- `ripser` (C++): Homología persistente rápida en GPU.
- `hera` (C++): Distancia bottleneck optimizada.
- `torch-tda` (PyTorch): Betti curves con autodiff.
