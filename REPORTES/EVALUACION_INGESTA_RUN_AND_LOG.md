# 🔬 EVALUACIÓN ANALÍTICA DE INGESTA: `run_and_log.py` (TELEMETRÍA DETERMINISTA Y VETO EMPÍRICO)
**Fecha:** 2026-09-20 | **Módulo:** Trazabilidad Criptográfica de Métricas y Erradicación de Cifras Hardcodeadas (Hallazgo E2)
**Protocolo Activo:** Regla 19 (Ingesta y Evaluación Progresiva / Veto de Código)

---

## 🧭 1. Resumen y Propósito del Componente

`run_and_log.py` es una herramienta de ingeniería de precisión diseñada para cerrar de raíz el **Hallazgo E2** de las auditorías externas: la presencia de números contradictorios, reciclados o introducidos manualmente en la documentación de entrega.

### 📐 Principio Rector: `ONE run -> ONE log -> ONE json`
Ningún documento Markdown de la tesis o del dossier de auditoría puede tener cifras numéricas escritas "a mano". El documento redacta plantillas semánticas como `{{pmtp_stress.reads_accepted}}` o `{{pmtp_stress.torn_accepted_rate_ub95}}`, las cuales son inyectadas automáticamente por `run_and_log.py fill` desde los archivos `.json` generados por las corridas físicas en silicio.

Si un solo placeholder no proviene de un log crudo certificado con Exit Code 0, el script falla con `exit 1`, **impidiendo la publicación de afirmaciones no sostenidas por silicio real (Regla 10 - Veto Empírico Anti-Alucinación)**.

---

## 🔬 2. Análisis Matemático y Algorítmico

### 2.1 Cota Superior Unilateral Exacta de Clopper-Pearson (`upper_bound`)
Para evaluar tasas de error cero ($k = 0$ desgarros en $n$ lecturas), el script no recurre a aproximaciones gaussianas simplistas (que colapsan para $p \approx 0$), sino a la **cota exacta de Clopper-Pearson al 95% de confianza**:

$$\text{Para } k = 0: \quad \text{Rate}_{\text{UB95}} = 1 - (1 - 0.95)^{1/n} = 1 - 0.05^{1/n} \approx \frac{3}{n} \quad (\text{"Rule of Three"})$$

Para $k > 0$, el script resuelve la CDF binomial acumulada en espacio logarítmico utilizando `lgamma` y bisección exacta sobre 200 iteraciones:
$$P(X \le k \mid n, p) = \sum_{i=0}^k \binom{n}{i} p^i (1-p)^{n-i} = \alpha$$

### 2.2 Registro Criptográfico y Telemetría del Binario (`cmd_run`)
Cada ejecución captura en el encabezado del log:
1. `started_utc`: Timestamp ISO 8601 estricto.
2. `elapsed_s`: Tiempo de ejecución medido con precisión de milisegundos.
3. `command` y `seed`: Reproducibilidad determinista.
4. `exe_sha256`: Hash SHA-256 del binario o script ejecutado, asegurando que el resultado pertenezca exactamente al ejecutable compilado.
5. `collect_env`: Telemetría del procesador, SO y núcleos lógicos.
6. `counters`: Extracción automática de todas las métricas en formato `clave=valor`.
7. `zero-bound` y `min-counter`: Verificación automática de aceptación (ej: certificar que $k = 0$ y que $n \ge 1000$).

---

## ⚖️ 3. Impacto en la Certificación de POLYDIM

* **Erradicación de Alucinaciones:** Ningún agente o autor humano puede inflar o alterar una métrica (ej. derivas de norma, lecturas de PMTP o tiempos de microsegundos).
* **Auditoría Transparente para Pares:** Los revisores externos reciben simultáneamente el binario, el `.log` crudo, el `.json` estructurado y el Markdown generado con trazabilidad criptográfica de extremo a extremo.
