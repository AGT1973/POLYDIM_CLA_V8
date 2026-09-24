# 🔬 EVALUACIÓN ANALÍTICA DE INGESTA: SELF-TEST DE `run_and_log.py` (VALIDACIÓN CRUZADA ESTADÍSTICA)
**Fecha:** 2026-09-20 | **Módulo:** Test de Validación Cruzada Clopper-Pearson vs SciPy & Verificación de Inyección de Métricas
**Protocolo Activo:** Regla 19 (Ingesta y Evaluación Progresiva / Veto de Código)

---

## 🧭 1. Resumen del Bloque Ingestado

El script recibido es el harness de pruebas automáticas (`test_run_and_log.py`) que certifica la exactitud matemática y el comportamiento del inyector determinista `run_and_log.py`.

---

## 🔬 2. Puntos Críticos de Validación Demostrados

### 2.1 Validación Cruzada contra SciPy (`scipy.stats.beta.ppf`)
El test compara la función matemática propia `upper_bound(k, n, 0.95)` (basada en bisección sobre la serie gamma de la CDF binomial) contra la distribución de referencia cuantil de la distribución Beta:

$$\text{Clopper-Pearson UB}_{1-\alpha}(k, n) = \operatorname{BetaInv}(1-\alpha, k+1, n-k)$$

* **Casos evaluados:** $(0, 1098)$, $(0, 218417)$, $(1, 1098)$, $(5, 1000)$, $(37, 100000)$.
* **Tolerancia:** Discrepancia absoluta $< 10^{-9} \times \max(1, \text{ref}) + 10^{-12}$.
* **Regla de Tres:** Verifica que para $k=0, n=1098$, el límite superior es $\approx 3/1098 = 2.73 \times 10^{-3}$ con error $< 2 \times 10^{-5}$.

### 2.2 Validación de la Cadena de Inyección en Documentación (`run` & `fill`)
1. **Parseo Robusto de Contadores:** Detecta enteros, flotantes y notación científica (`ratio=1.31e-2` $\to$ `0.0131`).
2. **Criterios de Aceptación Rígidos:**
   - `--zero-bound torn_accepted:reads_accepted`: Falla incondicionalmente si $k > 0$.
   - `--min-counter reads_accepted=1000`: Falla si el número total de lecturas no alcanza la muestra mínima estadística.
3. **Formateo Automático con Separadores de Miles:**
   - `{{pmtp_stress.reads_accepted}}` $\longrightarrow$ `1,098`
   - `{{pmtp_stress.races}}` $\longrightarrow$ `82,548`
4. **Veto Estricto a Cifras Inventadas:**
   - Si un documento Markdown contiene placeholders como `{{pmtp_stress.does_not_exist}}` o `{{ghost.x}}`, `run_and_log.py fill` emite `NO VALUE` y aborta con código `rc = 1`.

---

## ⚖️ 3. Conclusión de Ingeniería

Este harness garantiza que:
1. El cálculo estadístico de tasa de desgarro cero en PMTP tiene rigor de estándar bioestadístico/criptográfico.
2. Ningún número o porcentaje en la tesis doctoral o en los dossiers de entrega puede divergir de los logs generados en tiempo de ejecución.
