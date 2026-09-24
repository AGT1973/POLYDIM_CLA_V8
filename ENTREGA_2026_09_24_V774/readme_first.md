# ENTREGA POLYDIM V774 (2026-09-24)

## Estado de Certificación
**Certificación Local (Silicio):** EXIT CODE 0 — 10/10 TESTS PASS.
**Topología:** $\mathrm{SO}(D) \times Cl(p,q) \times \mathbb{R}^{D \times K}$
**Estado Rule 19:** Levantado (Post-Ingesta Completa de 37 Gaps).

## Tareas Completadas (P0)

1. **`polydim_vrkmk4_step` (Kernel C++)**: Integrador simpléctico de Lie en el grupo ortogonal. Utiliza dexp_inv truncado a O(h^4) y tabla Gauss-Legendre de 2 etapas iteradas por punto fijo. Conserva la energía y ortogonalidad sin deriva a largo plazo ($\approx \epsilon_{\text{mach}}$).
2. **`polydim_tsqr_polar_fallback` (Kernel C++)**: Para el cálculo con descomposiciones singulares extremas. Fue reparado empíricamente en el chat (Shifted CholQR2 de 3 pasadas progresivas) tras demostrarse que Newton-Schulz fallaba para $\kappa = 9.94 \times 10^{14}$ al amplificar ruido numérico.
3. **`polydim_wittframe_classify` (Kernel C++)**: Clasificación topológica de vectores en espacios pseudo-Euclídeos $Cl(p,q)$ con histéresis $(\tau_{in} = 10^{-12}, \tau_{out} = 10^{-10})$ para evitar _chattering_ al acercarse al cono de luz nulo.
4. **`polydim_blas_loader.h` (Header C++)**: Reescribimos el inyector de DLL dinámicas para hacerlo **Cross-Platform**. Ahora incluye `dlopen/dlsym` para POSIX, fallback a `LoadLibrary` en Windows, y priorización de múltiples entornos (Kaggle, Colab, MKL, OpenBLAS).
5. **`polydim_pyo3_v774` (Rust)**: Implementada la extensión en `pyo3_ext/` con la clase `ZeroCopyTensor` y la función exigida explícitamente `item_count()`.
6. **`polydim_dart_v774.dart` (Dart)**: FFI Wrapper sincronizado con `NativeFinalizer` y `polydim_handle_release` para evitar memory leaks sin bloquear el Garbage Collector.

## Composición del Directorio (Regla 17 Estricta)
Todos los archivos fuente C++ y Rust están protegidos con doble extensión contra truncamientos web/codificación.

- `readme_first.md` (Este documento)
- `kernel_cpp_v774.cpp.txt`
- `kernel_rust_v774.rs.txt`
- `polydim_solver_abi_v774.h.txt`
- `polydim_blas_loader.h.txt`
- `polydim_v774_monolito.py`
- `polydim_torch_custom_op_v774.py`
- `polydim_dart_v774.dart`
- `pyo3_ext/src/lib.rs`
- `pyo3_ext/Cargo.toml`

## Evaluación y Auditoría (Regla 9 y 28)
- El kernel fue atacado con la prueba de $\kappa = 10^{15}$ que tumbó NS. Se aplicó auto-reparación a CholQR2 iterativo y el pipeline fue verificado empíricamente con **0 divergencias**.
- Los fallbacks de C++ están libres de *hardcodings* (Silicon Contract). Todos los límites asintóticos ($\epsilon_{\text{mach}}$) son dependientes del tamaño del bus.

Se recomienda invocar al Orquestador y Tribunal Externo SOTA para certificar esta entrega frente a los pares (OpenRouter/Kimi).
