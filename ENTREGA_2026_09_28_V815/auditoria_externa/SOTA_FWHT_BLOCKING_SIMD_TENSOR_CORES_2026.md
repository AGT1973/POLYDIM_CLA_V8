# SOTA 2026: Transformada Rápida de Walsh-Hadamard (FWHT) Bloqueada y Aceleración Hardware
## Refutación del Algoritmo Recursivo Ingenuo en Altas Dimensiones ($D \ge 2^{20}$)

**Fecha:** Septiembre 2026  
**Clasificación:** Algoritmos Cache-Aware, Aceleración SIMD/Tensor Cores y Cuantización Vectorial  
**Iniciativa:** POLYDIM / EinsofOS Research Initiative  

---

## 1. Refutación del Enfoque Recursivo Ingenuo

### 1.1 El Cuello de Botella de Jerarquía de Memoria
El algoritmo tradicional de FWHT ejecuta $\log_2 D$ etapas de mariposas (butterflies). En las etapas superiores ($s > 14$ para $D = 2^{20}$), los saltos de memoria entre elementos emparejados alcanzan $\Delta = 2^{s-1} \times 8 \text{ bytes} \in [512\text{ KB}, 4\text{ MB}]$, excediendo ampliamente la capacidad de las cachés L1 (32–48 KB) y L2 (512 KB–1 MB) por núcleo.
- **Resultado:** Tráfico masivo a DRAM, latencia de ~50–80 ns por acceso no contiguo y saturación del bus de memoria. El throughput colapsa a menos del 15% del pico teórico de la CPU.

---

## 2. Paradigma SOTA (2024–2026): Arquitecturas Hardware-Aware

```
[Tensor de Entrada D=2^20]
          ↓
(1) Particionamiento en Bloques L1 (B = 512 elementos = 4 KB en FP64 / 2 KB en FP32)
          ↓
(2) Transformada Intra-Bloque Vectorizada (AVX-512 / AVX2 / NEON) -> 4-5 GOps/s
          ↓
(3) Transposición Contigua In-Place (Permutación sin Scatter/Gather)
          ↓
(4) Fusión de Etapas Superiores en GPU via Tensor Cores (HadaCore MMA 16x16)
          ↓
[Salida Proyectada en Espacio de Hadamard]
```

### 2.1 FWHT Bloqueada (Block-wise FWHT)
Al restringir la transformada recursiva a bloques de tamaño fijo $B \in \{128, 256, 512\}$:
$$\text{Complejidad Formal: } O(D \log_2 B) \approx O(D) \quad (\text{para } B = \text{constante})$$
- **Implementación (pyfwht):** Caso base de 512 elementos ejecutado completamente dentro de L1, con alineación estricta de 64 bytes (línea de caché) y prefetching de software por hardware threads.

### 2.2 Vectorización SIMD Avanzada (AVX-512 / AVX2 / NEON)
- Despliegue de 4 a 16 operaciones de mariposa por ciclo de CPU mediante instrucciones `_mm512_add_pd` y `_mm512_sub_pd`.
- Eliminación de dependencias read-after-write intermedias mediante registros extendidos.

### 2.3 Aceleración por Tensor Cores (HadaCore 2024, arXiv:2412.08832)
- **Mapeo a Primitivas MMA:** Reorganiza el caso base como multiplicación de matrices $16 \times 16$ densas ejecutadas directamente en los Tensor Cores de NVIDIA A100/H100.
- **Trade-off Aritmético (Sec. 3.4):** Requiere el **doble de operaciones aritméticas** ($4mn \log_2 n$ FLOPs frente a $2mn \log_2 n$ de la FWHT clásica) para forzar la geometría matricial requerida por los Tensor Cores.
- **Speedup Real Medido (Sec. 5):**
  - **Régimen Compute-Bound ($512\text{--}2048$ elementos):** Picos medidos de **$3.5\times$ en A100** y **$3.6\times$ en H100** (los datos residen en SRAM/L2).
  - **Régimen Memory-Bound de Producción ($8\text{K}\text{--}32\text{K}$ y $2^{25}\text{--}2^{28}$):** El speedup decae a **$1.1\times\text{--}1.4\times$ en A100** y **$1.0\times\text{--}1.3\times$ en H100** al topar contra el techo físico de ancho de banda de HBM (roofline limit).
- **Veredicto Teórico:** El claim de "8×" es falso e irrealizable físicamente para tensores de producción.

---

## 3. Matriz de Fact-Checking y Auditoría de Claims

| Afirmación Evaluada | Veredicto | Realidad Numérica / Evidencia |
| :--- | :---: | :--- |
| *"RSLM logra complejidad lineal $O(D)$"* | ⚠️ **Simplificación** | La complejidad exacta es $O(D \log B)$. Con $B=256$, $\log_2 B = 8$, comportándose linealmente con factor multiplicativo constante. |
| *"HadaCore ofrece 8× speedup con Tensor Cores"* | ❌ **Exagerado / Falso Teórico** | arXiv:2412.08832 (Sec. 4 y 5): en A100 reporta **$1.1\text{--}1.4\times$** y en H100 **$1.0\text{--}1.3\times$** (picos de $3.5\times$ en A100 y $3.6\times$ en H100 para vectores pequeños). FWHT en dimensiones típicas ($2^{25}\text{--}2^{28}$) es *memory-bandwidth bound*, haciendo físicamente imposible alcanzar $8\times$ por el techo roofline de HBM. |
| *"FWHT introduce zero-latency overhead en LLMs"* | ❌ **Exagerado** | Requiere cargas/almacenamientos adicionales que impactan pipelines de inferencia ultra-baja latencia. |
| *"pyfwht caso base 512 elementos satura L1"* | ✅ **Confirmado** | 512 elementos FP32 (2 KB) o FP64 (4 KB) operan con 0% de fallos de caché L1 en CPU modernas. |

---

## 4. Directiva de Implementación para el Kernel POLYDIM V816

1. **CPU Backend (WinLibs GCC 14 / OpenMP):** Adoptar caso base de 512 elementos con intrinsics AVX-512 (`zmm`) y alineación de 64 bytes para eliminar falsas comparticiones.
2. **GPU Backend (Triton / CUDA):** Implementar mariposas Radix-4 y Radix-8 con 64 threads por bloque en shared memory, evitando conflictos de bancos y ejecutando el tiling de 256 elementos para Tensor Cores.
