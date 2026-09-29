# 02. SILICON CONTRACT & REGLAS ASINTÓTICAS V807

1. **Agnosticismo de Hardware**: El código interroga dinámicamente el silicio en tiempo de ejecución (`HardwareProbe`, `np.finfo`) sin asumir constantes fijas de arquitectura.
2. **Aislamiento de Caché (128B)**: Todas las estructuras concurrentes (SPSC Ring, PolydimBettiResult, PolydimFrechetBettiResult, BankedSlotHeader) están alineadas a 128 bytes para evitar False Sharing entre núcleos.
3. **Manejo Estricto de Memoria**: Strict Allocator Pairing (`polydim_alloc_aligned` / `polydim_free_aligned`) y Refcounting atómico en `PolydimHandle` para prevenir Use-After-Free y dobles liberaciones en fronteras FFI.
4. **Verificación Empírica Automatizada**: Todos los valores de métricas en los reportes se derivan directamente del log crudo `05_LOG_RAW_TESTS.txt` con Exit Code 0.
