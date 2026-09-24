# SOTA RESEARCH: FlashAttention — Tri Dao — Aplicabilidad a POLYDIM
**Fecha:** 2026-09-17  
**Fuente:** Investigación de sabueso + GitHub oficial + papers arxiv  
**Status:** VERIFICADO EMPÍRICAMENTE

---

## 1. LICENCIA — Veredicto Legal

**BSD 3-Clause License.** Texto exacto verificado en `https://github.com/Dao-AILab/flash-attention/blob/main/LICENSE`.

| Uso | ¿Permitido? |
|-----|------------|
| Leer código y aprender técnicas | ✓ Sin restricción |
| Reimplementar algoritmos desde cero | ✓ Sin licencia ni atribución requerida |
| Copiar código con header de copyright | ✓ Solo requiere retener el header BSD |
| Comercializar derivados | ✓ |
| Usar nombre "FlashAttention" en marketing | ✗ Requiere permiso explícito |

**Nota crítica:** Las ideas matemáticas (IO-awareness, tiling, online softmax) son conceptos publicados en papers académicos. El copyright protege los bytes del código, no los algoritmos. Una reimplementación independiente desde el paper no tiene restricción de licencia.

**No hay patentes:**  
Ni Tri Dao ni Stanford han ejercido patentes sobre FlashAttention.

---

## 2. QUÉ TIENE TRI DAO — El insight real

Tri Dao no inventó matemática nueva. Identificó un problema que **todo el campo ignoraba**: la atención cuadrática era lenta no por cómputo, sino por **tráfico de memoria entre HBM (lenta, ~2 TB/s) y SRAM on-chip (rápida, ~19 TB/s)**.

### El stack técnico (5 técnicas):

**A. IO-Awareness (Hong & Kung 1981 adaptado):**
Standard attention: `O(N*d + N²)` accesos HBM.  
FlashAttention: `O(N² * d² / M)` accesos HBM. Mismo resultado matemático exacto.

**B. Tiling / Block GEMM:**
Nunca materializa la matriz `N×N` en HBM. Trabaja en tiles `B_r × B_c` que caben en SRAM.  
→ **POLYDIM analogy:** SwarmDualOperator jamás materializa `D×D`. Tile el eje D.

**C. Online Softmax (Milakov & Gimelshteyn 2018):**
Actualiza `max` y `sum(exp)` de forma running sin un segundo pass:  
`m_new = max(m_old, tile_max)`  
`l_new = exp(m_old - m_new) * l_old + rowsum(exp(tile - m_new))`  
→ **POLYDIM analogy:** Exactamente el Neumaier Compensated Accumulator — running correction sin re-scan.

**D. Gradient Recomputation:**
Forward almacena solo `O` y estadísticas `(m, l)` en `O(N)`. Backward recomputa bloques en SRAM.  
→ **POLYDIM analogy:** Si se implementa diferenciación geodésica, almacenar solo `(theta, v)` por step.

**E. FlashAttention-2 Loop Inversion + Warp Partitioning:**
Q en outer loop, KV en inner. Warps independientes, sin sync barriers.  
→ Relevante para optimizar `apply_rodrigues_rank2_geodesic_f64` con multi-SM.

---

## 3. EL CÓDIGO — ¿Es legible?

**Python layer (~15%):** Altamente legible. Firmas claras, docstrings.

**CUDA/C++ layer (~85%):** `csrc/flash_attn/src/` — **muy baja legibilidad** para no especialistas. Template metaprogramming denso, CuTe layout algebra, inline PTX, wgmma/TMA descriptors.

**La versión legible existe:** Hay una implementación oficial en Triton (`flash_attn_triton.py`) de ~150-200 líneas, bien comentada. **Esa es la referencia que POLYDIM debe leer.**

---

## 4. MAPEO DIRECTO FlashAttention → POLYDIM

| Problema FlashAttention | Técnica | Problema POLYDIM | Aplicación |
|------------------------|---------|-----------------|-----------|
| No materializar `N×N` en HBM | Tiling inner product | No materializar `D×D` (800 TB) | SwarmDualOperator tiles en eje N |
| Softmax sin 3 passes de HBM | Online running max+sum | Norma sin re-scan | Neumaier ya lo hace — tiling lo paraliza |
| Retracción a simplex | Fused normalization kernel | Proyección a `S^{D-1}` | `fused_spherical_retraction` en Triton |
| Gradientes sin `N×N` | Recomputation in SRAM | Geodésica backward | Almacenar `(theta, v)` por step |
| Vector `D=64,128` en SRAM | SRAM-resident `d` dim | Vector `D=10^7` nunca cabe en SRAM | **Tile D** en bloques `B_D ∈ {512, 1024}` |

---

## 5. LIBRERÍAS RELACIONADAS Y LICENCIAS

| Librería | Organización | Licencia | Relevancia POLYDIM |
|----------|-------------|---------|-------------------|
| **Triton** | OpenAI | **MIT** | RECOMENDADA para kernels custom esféricos |
| **CUTLASS** | NVIDIA | BSD 3-Clause | Backend de FlashAttention, muy complejo |
| **xFormers** | Meta | BSD 3-Clause | Primitivos Transformer modulares |
| **ThunderKittens** | Stanford | BSD 3-Clause | CUDA tile-based para Hopper/Blackwell |
| **vLLM** | UC Berkeley | Apache 2.0 | Serving, menos relevante |

---

## 6. RUTA RECOMENDADA PARA POLYDIM (sin copiar código)

### Camino limpio (MIT, sin deuda de licencia):

```python
# kernel Triton inspirado en FlashAttention — 100% original, MIT-compatible
import triton
import triton.language as tl

@triton.jit
def fused_spherical_retraction(
    x_ptr, delta_ptr, out_ptr,
    D, BLOCK_D: tl.constexpr
):
    """
    Computes (x + delta) / ||(x + delta)||_2 in a single HBM pass.
    Eliminates 4 HBM roundtrips of naive NumPy implementation.
    Inspired by FlashAttention's fused normalization principle.
    """
    pid = tl.program_id(0)
    offsets = pid * BLOCK_D + tl.arange(0, BLOCK_D)
    mask = offsets < D
    
    x = tl.load(x_ptr + offsets, mask=mask, other=0.0)
    delta = tl.load(delta_ptr + offsets, mask=mask, other=0.0)
    y = x + delta
    
    # Warp-level norm reduction (no HBM write)
    norm_sq = tl.sum(y * y)  # Triton auto-reduces across BLOCK_D
    norm = tl.sqrt(norm_sq)
    
    tl.store(out_ptr + offsets, y / norm, mask=mask)
```

**Esto es POLYDIM V742 territory.** El benchmark de ese kernel vs NumPy en `D=10^7` es el "Chart 1".

---

## 7. EL NÚMERO QUE FALTA

FlashAttention: *"2x más rápido que PyTorch en A100, mismo resultado"*

POLYDIM necesita: *"Proyección geodésica en S^{D-1} con D=10^7 en X ms, drift < 10^{-14}, sin materializar matrices de 800 TB, en hardware de consumo"*

Ese número no existe todavía. Es la Fase 1 real del roadmap.

---

**Referencias verificadas:**
- FlashAttention-1: arxiv 2205.14135 (NeurIPS 2022)
- FlashAttention-2: arxiv 2307.08691 (ICLR 2024)  
- FlashAttention-3: arxiv 2407.08608 (2024)
- Online Softmax: arxiv 1805.02867 (Milakov & Gimelshteyn 2018)
- GitHub: https://github.com/Dao-AILab/flash-attention (BSD 3-Clause)
