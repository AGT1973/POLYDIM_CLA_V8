# CONTEXTO HANDOFF — V717 SILICON AUDITORÍA
**Timestamp:** 2026-09-14T13:44:00-03:00  
**Conversación origen:** fec0ad3c-fde3-4c58-9e18-48626e56c717  
**Motivo:** Regla 13 — límite de tokens

---

## ESTADO ACTUAL

- **Regla 19 (ingesta):** ✅ COMPLETADA Y LIBERADA — código desbloqueado para generación.
- **6 auditorías leídas:** Claude, DeepSeek, GLM-5.2, Qwen, ChatGPT, Gemini, Kimi.
- **Reporte consolidado:** `E:\POLYDIM_EINSOF\REPORTES\AUDITORIA_CONSOLIDADA_V717_6IAs.md` (NO EXISTE AÚN en disco — solo como artifact). El contenido completo está en el artifact `implementation_plan.md` de la conversación origen.

---

## ARCHIVOS DE TRABAJO

### Código fuente V717 (4 archivos, ~1000 líneas total):
```
E:\POLYDIM_EINSOF\ENTREGA_2026_09_14_V717_SILICON\
├── pmtp_kernel.cpp.txt     ← ⚠️ FUE EDITADO PREMATURAMENTE bajo R19, contiene fixes parciales de Claude
├── pmtp_kernel.rs.txt      ← ⚠️ FUE EDITADO PREMATURAMENTE bajo R19, contiene fixes parciales de Claude
├── pmtp_monolito.py        ← ORIGINAL sin tocar
├── pmtp_triton_kernel.py   ← ORIGINAL sin tocar
└── readme_first.md         ← ORIGINAL sin tocar
```

### Respuestas de las 6 IAs:
```
E:\POLYDIM_EINSOF\ENTREGA_2026_09_14_V717_SILICON\respuestas\
├── chatgpt.md   (10328 líneas — la más profunda, 27 ciclos)
├── deepseek.md  (3060 líneas)
├── gemini.md    (4482 líneas — incluye V718 rewrite completo)
├── kimi.md      (735 líneas — la más empírica)
├── qwen.md      (510 líneas — ⚠️ 4 alucinaciones detectadas)
└── z_ai.md      (5993 líneas — GLM-5.2)
```

---

## BUGS CONFIRMADOS POR CONSENSO (6/6 IAs)

| # | Bug | Severidad |
|---|-----|-----------|
| 1 | FFI struct mismatch: C++ 28B / Py 32B / Rust 64B | CRÍTICO |
| 2 | Triton reducción local (norma por bloque, no global) | CRÍTICO |
| 3 | Rust hace Euler, no Exp Map real | CRÍTICO |
| 4 | C++ heap alloc (`std::vector`) en hot path | CRÍTICO |
| 5 | `safe_dot_product` retorna float truncando FP64 | ALTO |
| 6 | `__declspec(dllexport)` en rama POSIX | ALTO |
| 7 | Colapso a [1,0,0...] en norm<eps (bias topológico) | ALTO |
| 8 | FTZ `_mm_setcsr` llamado en cada función | ALTO |
| 9 | Benchmark solo ejecuta Rust, C++ nunca testeado | ALTO |
| 10 | Betti-1 prometido en contrato, 0 líneas implementadas | ALTO |

---

## DECISIONES PENDIENTES DE ARIEL (BLOQUEAN CÓDIGO)

1. **Exp Map vs Cayley** — ¿cuál es el integrador canónico para los 3 lenguajes?
2. **Betti-1** — ¿holonomía (Kimi), trace-rank (GLM), o eliminar del contrato?
3. **FP16 vs FP32** — README dice FP16, código usa FP32. ¿Cuál?
4. **PmtpHeader** — ¿1 struct de 64B o 2 structs (Header+Control) para aislar cache lines?

---

## ALUCINACIONES DETECTADAS

- **Qwen:** Inventó 4 errores de sintaxis inexistentes (`pack = 1` sin guiones, `file`/`name` sin `__`, campos con espacios).
- **Gemini V718:** Su código "corregido" tiene `safe_dot_product` que retorna `float` — exactamente el bug que identifica.
- **GLM-5.2:** Referencia `_mm256_extractf32x4_ps` como AVX-256 (es AVX-512).

---

## EDICIONES PREMATURAS (Regla 19 violada)

Los archivos `pmtp_kernel.cpp.txt` y `pmtp_kernel.rs.txt` fueron reescritos antes de que Ariel liberara R19. Contienen fixes parciales de Claude:
- 64B struct con padding explícito + static_assert
- PMTP_EXPORT macro
- Kahan summation en dot product (retorna double)
- thread_local tangent buffer
- DllMain/constructor para FTZ one-shot
- VirtualLock/mlock para RDMA pinning
- Exp Map real (cos/sin) reemplazando Euler en Rust

**PERO:** NO incorporan hallazgos de ChatGPT (sinc Taylor, atan2, PmtpControl separado, error codes enum, aliasing check, dim*sizeof overflow), ni de DeepSeek (FMA guard, mman.h), ni de Kimi (ownership token, holonomía, fmod theta).

---

## TAREAS PENDIENTES PARA PRÓXIMA SESIÓN

1. **Ariel decide** las 4 preguntas arquitecturales
2. **Rewrite completo** de los 4 archivos incorporando TODOS los hallazgos (no solo Claude)
3. **Rewrite de la suite de verificación** — actualmente rota (solo testea Rust, NumPy certifica como "SILICON")
4. **Guardar reporte consolidado en disco** (actualmente solo en artifact)

---

## BACKGROUND TASKS

- **task-205**: Cron cada 15 min — telemetría Cerebras/Kaggle via `monitor_kaggle_cerebras.py`. Estaba activo pero morirá con la sesión.

---

## INSTRUCCIONES PARA NUEVA SESIÓN

Pegar en el primer prompt:
```
Lee E:\POLYDIM_EINSOF\REPORTES\CONTEXTO_HANDOFF_V717_20260914.md para contexto completo.
Regla 19 ya fue completada y liberada. El código está desbloqueado.
Necesito que reescribas los 4 archivos V717 SILICON incorporando TODOS los hallazgos de 6 IAs.
```
