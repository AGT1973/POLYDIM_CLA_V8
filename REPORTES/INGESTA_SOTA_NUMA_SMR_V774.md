# ==============================================================================
# REPORTE DE INGESTA Y EVALUACIÓN SOTA: MEMORIA NUMA Y DESCRIPTORES LOCK-FREE
# (GAP-23 A GAP-24: AFINIDAD DINÁMICA NUMA, FIRST-TOUCH Y RECLAMACIÓN SMR HYALINE)
# Fase 0: Ingesta Bruta Consolidada | Fase 1: Evaluación Red Team (Bulldog Critic)
# Fecha: 2026-09-24 | Versión Objetivo: POLYDIM V774
# ==============================================================================

## FASE 0: TEXTO ÍNTEGRO EN BRUTO INGRESADO POR ARIEL

```text
Soluciones SoTA para GAP-23 y GAP-24
Las soluciones de vanguardia para ambos gaps combinan asignación NUMA-aware con first-touch policy para GAP-23, y Hyaline/HazardEraPOP como esquemas de reclamación de memoria seguros más eficientes que Hazard Pointers clásicos para GAP-24.

GAP-23: Detección y Afinidad Dinámica NUMA
Estrategia recomendada:
Linux: numa_num_configured_nodes(), numa_node_size64(), numa_run_on_node(), mbind() con MPOL_BIND, numa_alloc_onnode().
Windows: GetNumaNodeProcessorMaskEx(), SetThreadIdealProcessorEx(), SetThreadAffinityMask().
First-touch policy: La primera escritura fija el nodo de residencia en DRAM.
Penalización medida (EPYC 9355P, 2025): 130 ns (local) vs 220 ns (remoto) -> +69% penalización.

GAP-24: Pool de Descriptores Lock-Free con SMR
Esquemas SMR: Hazard Pointers (alto overhead por memory fences), EBR (bajo overhead pero crecimiento ilimitado si un hilo se traba), Hyaline (PLDI'21, snapshot-free, sin fence en lectura, sin fugas), HazardEraPOP (2025, combina HP + EBR con Publish-on-Ping).

[... Texto íntegro de implementación en Linux libnuma, mimalloc, Windows SetThreadIdealProcessorEx, y clase HyalinePool / PolydimHandle ...]
```

---

## FASE 1: EVALUACIÓN CRÍTICA RED TEAM (BULLDOG CRITIC)

### 1. REFINAMIENTO DE INGENIERÍA Y ANÁLISIS DE RENDIMIENTO

#### A. GAP-23: Detección y Afinidad Dinámica NUMA
* **Acierto de Arquitectura y Rendimiento:**
  1. **La Realidad Física del Hardware Multi-Socket:** En servidores dual-socket (ej. 2x AMD EPYC o Intel Xeon en Cloud/Kaggle), acceder a memoria remota a través del bus Infinity Fabric o UPI añade $\approx 90\text{ ns}$ de latencia ($\approx 40\%$ de degradación de ancho de banda).
  2. **Combinación SOTA:** Afinidad de hilos previa (`numa_run_on_node` / `SetThreadIdealProcessorEx`) + `mbind(MPOL_BIND)` para forzar que las páginas DRAM se alojen en el socket local del hilo.
* **Trampas Críticas y Correcciones de Silicio:**
  1. **Peligro en Sistemas Mono-Socket / APU:**
     * En máquinas cliente (como nuestro host AMD A4-6300) o VMs mono-socket de Kaggle, `numa_num_configured_nodes()` devuelve 1.
     * Si el allocator asume múltiples nodos o invoca ciegamente `numa_alloc_onnode(size, 1)`, la llamada falla con `EINVAL` o `nullptr`.
     * *Corrección:* `HardwareProbe` debe evaluar `num_nodes > 1`. Si `num_nodes <= 1`, todas las llamadas NUMA deben degradar transparentemente a un `no-op` usando el asignador alineado estándar.
  2. **Falla en el First-Touch Parcial del Snippet:**
     * El snippet propuso:
       ```cpp
       memset(tensor_buffer, 0, 64 * 1024); // Tocar primeras páginas (el resto on-demand)
       ```
     * **¡Grave error de first-touch!** Si en un buffer de 1 GB solo se tocan los primeros 64 KB, las páginas restantes (999.9 MB) **no quedan vinculadas físicamente a ningún nodo**. Si posteriormente un hilo en el socket 1 escribe en el resto del buffer, esas páginas quedarán asignadas al socket 1, destruyendo la localidad NUMA deseada.
     * *Corrección Obligatoria:* El hilo asignador debe realizar un toque por zancada (*stride touch*) de 4 KB en todo el rango:
       ```cpp
       volatile char* p = static_cast<volatile char*>(tensor_buffer);
       for (size_t off = 0; off < total_size; off += 4096) {
           p[off] = 0;
       }
       ```

---

#### B. GAP-24: Pool de Descriptores Lock-Free con SMR (Hyaline vs. HazardEraPOP)
* **Acierto Arquitectónico SOTA:**
  1. **Abolición del Overhead de Hazard Pointers Clásicos:** Los Hazard Pointers tradicionales fuerzan una barrera de memoria pesada (`smp_mb()`) en cada lectura, penalizando el *fast-path*.
  2. **Superación del Límite de EBR Clásico:** El Epoch-Based Reclamation convencional no introduce fences en lectura, pero si un proceso o hilo de background se bloquea o muere, la época global se detiene y la memoria pendiente de liberación crece infinitamente (*unbounded growth*).
  3. **Hyaline (PLDI'21):** Utiliza contadores de referencia diferidos (`HRef` por lote y `NRef` por nodo), logrando reclamación por épocas sin barreras de lectura y garantizando que un hilo detenido no provoque fugas ilimitadas de descriptores.
* **Incompatibilidad de Plataforma en HazardEraPOP:**
  * El esquema HazardEraPOP depende de la señal POSIX `pthread_kill(thread.tid, SIGUSR1)` para forzar la publicación de punteros (*Publish-on-Ping*).
  * **En Windows, `SIGUSR1` y las señales POSIX asíncronas no existen.** Forzar HazardEraPOP en Windows rompería la portabilidad del monolito C++.
  * *Decisión SOTA de Ingeniería:* Implementar **Hyaline puro** en C++/Rust para `PolydimHandle`. Hyaline no requiere señales de sistema operativo, es 100% portable entre Windows y Linux, y ofrece un 10% más de rendimiento que EBR con overhead despreciable ($\le 8\%$).

---

## RESUMEN DE LA ARQUITECTURA DE MEMORIA REFINADA

1. **NUMA-Aware Engine:** Detección en `HardwareProbe`. Si `num_nodes > 1`, activación de `mbind(MPOL_BIND)` con first-touch de zancada de 4 KB. Si `num_nodes == 1`, degradación transparente a asignación alineada estándar.
2. **SMR Descriptores:** Implementación de `HyalinePool` portable sin señales POSIX, aislando la gestión de handles ligeros de los slabs masivos de memoria compartida PMTP.
