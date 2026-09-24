# CONTEXTO HISTÓRICO Y TRASPASO DE ESTADO — CIERRE SESIÓN V758 → APERTURA V759

**Fecha de Cierre:** 2026-09-18
**Versión Actual (Saliente):** POLYDIM V758
**Versión Objetivo (Entrante):** POLYDIM V759
**Estado de Regla 19:** `RELEASED_AND_ARMED` (Código desbloqueado para la próxima sesión)

---

## 1. RESUMEN DE HITOS ALCANZADOS (SESIÓN V758)

1. **Certificación V758:** El monolito V758 pasó 6/6 suites en hardware real.
2. **Fin de Fase de Ingesta:** Se recibieron 4 reportes SOTA de la IA externa sobre brechas críticas.
3. **Auditorías Red Team Completadas (Cristalizadas en disco):**
   - `REPORTES/INVESTIGACION_CUDA_DRIVER_API_CUBIN_RUNNER_SOTA.md` (Solución BG-01)
   - `REPORTES/AUDITORIA_BG02_REDUCCION_JERARQUICA_D10E8.md` (Solución BG-02)
   - `REPORTES/AUDITORIA_BG03_SINGULARIDAD_CHOLQR_SVD.md` (Solución BG-03)
   - `REPORTES/AUDITORIA_BG04_FTZ_DAZ_SUBNORMALES.md` (Solución BG-04)

---

## 2. FALLAS CRÍTICAS DETECTADAS A RESOLVER EN V759

La auditoría implacable del Tribunal descubrió los siguientes bugs y vulnerabilidades reales en la arquitectura V758 que deben ser reescritos:

### Arquitectura C++ / Algoritmia
- **Bug FTZ/DAZ (BG-04):** `enable_ftz_daz()` se llama fuera de `#pragma omp parallel`. Los workers pierden la bandera de subnormales. **FIX:** Mover adentro de la región paralela.
- **D=10^8 Desbordamiento (BG-02):** El Neumaier escalar O(D) falla asintóticamente y destruye VRAM. **FIX:** Implementar Reducción Jerárquica Fusionada (3 Tiers: Lane, Block, Tree) reteniendo la estructura `FusedTileAcc`. Prohibición absoluta de float32.
- **Fallback MGS2 Temerario (BG-03):** V758 salta de CholQR2 directo a MGS2 escalar. **FIX:** Implementar escalera adaptativa de 4 Tiers: (1) CholQR2, (2) Shifted-CholQR2, (3) MGS2, (4) SVD 8x8 (que cuesta 0 FLOPs relativos). Agregar estimador de condición previo.

### Infraestructura GPU / Triton
- **Hot-Path Python (BG-01):** PyTorch estorba. **FIX:** Implementar el Runner en C++17 puro con la CUDA Driver API (`cuInit`, `cuModuleLoadDataEx`) usando un pool de streams no bloqueantes (`CU_STREAM_NON_BLOCKING`) para eludir el GIL por completo. Aún falta investigación sobre cómo generar el archivo `.cubin` exacto con `triton.compile`.

### Capa Python
- **Sanitización Ausente:** Falta eliminación explícita de subnormales en Python antes del puente FFI. **FIX:** Implementar `require_f64_vector` con limpieza explícita de `tiny`.

---

## 3. INSTRUCCIONES ESTRICTAS PARA EL ORQUESTADOR V759 (PRÓXIMA SESIÓN)

1. **APERTURA:** Lee `PERMANENT_MEMORY.md` y luego este documento.
2. **ACTUALIZACIÓN LEDGER:** Modifica `POLYDIM_STATE_LEDGER.json` a V759 y actualiza las métricas.
3. **GENERACIÓN DE CÓDIGO (V759):** Crea la carpeta `ENTREGA_2026_09_18_V759/` y comienza a programar los 5 componentes centrales:
   - `kernel_cpp_v759.cpp.txt` (Aplicando los fixes BG-02, BG-03 y BG-04).
   - `kernel_rust_v759.rs.txt`
   - `polydim_v759_monolito.py` (Agregando sanitización FFI).
   - `polydim_triton_kernel_v759.py`
   - El nuevo runner C++ `cuda_cubin_runner.cpp.txt` (Fix BG-01).
4. **INVESTIGACIÓN PENDIENTE:** Falta investigar la API exacta de `triton.compile` para generar `.cubin` desde Python de forma autónoma.
5. **CERO ALUCINACIONES:** Toda modificación debe ser estricta. Conservar Rule 17 (Doble extensión).

---

**ESTADO DEL SISTEMA:** ORDEN DE PARADA (REGLA 13). MEMORIA VOLCADA. ESPERANDO REINICIO.
