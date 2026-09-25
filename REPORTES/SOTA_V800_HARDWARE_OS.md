# 🏛️ INGESTA SOTA V800: HARDWARE & OS BOTTLENECKS (FASES 1-4 CONSOLIDADAS)
**Fecha:** 2026-09-24
**Estado:** Fase 0 (Unión en Bruto) y Fase 1 (Evaluación Activa) - CONSOLIDADO FINAL

## 1. Trampa de Paginación y TLB Misses (IOMMU/ATS)
- **SOTA 2025-2026:** HugePages 1GB con `madvise(MADV_HUGEPAGE)` + `MAP_POPULATE` desde Userspace para bypassear IOTLB misses masivos.
- **Validación:** `perf stat -e dTLB-load-misses,dTLB-loads` ($\le 0.1\%$).

## 2. Falsa Contención de Caché y el Peligro ABI (Compile-Time)
- **Diagnóstico Confirmado:** Usar `std::hardware_destructive_interference_size` ciegamente es un riesgo de ABI masivo. Compilar en Intel con GCC 12+ embebe "64B" en el binario; si se ejecuta en Apple Silicon o Intel Server (prefetcher agresivo), se destruye el rendimiento silenciosamente.
- **SOTA 2025-2026 (Patrón Híbrido "Folly/Google" + Fail-Fast):**
  - **Macro Condicional:** Uso de Feature-Test macro `__cpp_lib_hardware_interference_size` con **Fallback Conservador a 128B** para arquitecturas desconocidas.
  - **Runtime Probe (HardwareProbe):** Función `runtime_cache_line_size()` evalúa CPUID/SYSCTL en caliente. Si el tamaño de tiempo de ejecución es mayor al de compilación (causando False Sharing), POLYDIM emite un `LOG_FATAL` y llama a `std::abort()`. 
  - **Preferencia Asintótica:** Alinear a 128B gasta el doble de memoria (Over-allocation) pero garantiza portabilidad 100% y resistencia al prefetcher espacial.

## 3. Telemetría Lock-Free, Write-Combining y Non-Temporal Stores
- **El Handoff Perfecto (AVX-512 + SFENCE + Release):**
  - `_mm512_stream_pd` para bypassear caché completamente (Direct to WC/DRAM).
  - `_mm_sfence()` para ordenar los stores NT en el núcleo local.
  - Publicación del slot con `std::memory_order_release` en el flag atómico.
  - El consumidor ejecuta `std::memory_order_acquire` en el flag; al ser exitoso, puede leer pasivamente con temporal loads o NT loads.
- **Shadow Variables y Padding 128B:**
  - Separar productor y consumidor por al menos 128 bytes para derrotar al *spatial prefetcher*.
  - Usar copias sombra (`cached_head`, `cached_tail`) para aplastar el tráfico MESI por True Sharing.
- **HugePages + Write-Combined (MTRR/PAT):** 
  - El throughput salta de 65GB/s a 85GB/s si el buffer mmap se solicita con atributos WC (Write-Combine) donde el SO lo permita.

## Veredicto Arquitectónico Final V800 (SILICON CONTRACT)
Toda estructura concurrente `SEQLock` o `TelemetrySlot` debe usar `alignas(COMPILE_CACHE_LINE)` respaldado por el Fallback a 128B y validado con aborto duro en la rutina `POLYDIM_Init()`. La telemetría en anillo adopta el pipeline SOTA Lock-Free de 3 etapas (Stream $\to$ Fence $\to$ Release).
