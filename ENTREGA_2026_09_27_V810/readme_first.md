# 📜 README FIRST — POLYDIM SERIE 800 (ENTREGA V810)

> **Fecha:** 27 de Septiembre de 2026  
> **Arquitectura:** POLYDIM V810 — Hiperdimensional $S^{D-1}$, PMTP Zero-Copy IPC, Stiefel Manifold Optimization, Guardián Topológico Dual Betti Rust y Síntesis Cuántica Discreta.  
> **Certificación:** 5/5 Suites Aprobadas con **Exit Code 0** en Silicio Real (AMD APU x86_64, MinGW GCC 14.2.0, Rustc 1.98.1).  
> **Auditoría:** Revisión adversaria línea por línea efectuada por el Tribunal de Enjambre Multi-IA (DeepSeek, Qwen, Kimi, Cerebras).

---

## 1. Composición de Archivos de Entrega (Regla 17)

Conforme a la Regla 17 de la Constitución Maestra, los archivos fuente desacoplados se entregan con doble extensión semántica (`.rs.txt`, `.cpp.txt`, `.cu.txt`) para prevenir truncamiento web, colisiones sintácticas y pérdidas de codificación:

| Archivo Físico | Doble Extensión Semántica | Rol Arquitectural |
|---|---|---|
| `kernel_cpp_v810.cpp` | `kernel_cpp_v810.cpp.txt` | Kernel monolítico C++: Stiefel CholQR2/Cayley-SMW, DSYRK TwoSum/SIMD, streaming NT y SPSC Ring 128B. |
| `kernel_rust_v810.rs` | `kernel_rust_v810.rs.txt` | Guardián Topológico Dual Rust: DSU iterativo $10^6$ nodos, filtro de consenso Fréchet-Betti BFT ($3a \ge 2n$), y cuantización Clifford+T. |
| `pmtp_rcu_v810.cpp` | `pmtp_rcu_v810.cpp.txt` | Banked RCU de 3 épocas: Lock de escritor 64-bit atómico `{writer_active, owner_pid}`, detección de zombis y purga de leases. |
| `ipc_futex_v810.cpp` | `ipc_futex_v810.cpp.txt` | Futex IPC cross-process: Auto-Reset Event contra livelocks de 100% CPU, validación de frontera de página (anti-underflow) y fallback a `WaitOnAddress`. |
| `graph_cuda.cpp` | `graph_cuda.cpp.txt` | Backend agnóstico de grafos y componentes conectados Afforest GConn (CPU OpenMP + CUDA GPU DLPack). |
| `graph_cuda.cu` | `graph_cuda.cu.txt` | Kernel nativo CUDA para aceleración en silicio NVIDIA. |
| `compile_v810.py` | — | Script de compilación cruzada GCC 14 + Rustc + G++ / Clang. |
| `run_all_tests_with_log.py` | — | Orquestador de pruebas que genera el log crudo con Exit Code 0. |

---

## 2. Vulnerabilidades Críticas Auditadas y Resueltas (V810)

Durante la auditoría adversarial línea por línea de las ~2,500 líneas de código, se detectaron y neutralizaron las siguientes fallas críticas:

1. **Livelock de 100% CPU en IPC Futex Windows (`ipc_futex_v810.cpp`):**
   - *Falla:* `CreateEventA(NULL, TRUE, FALSE, name)` (Manual-Reset) sin `ResetEvent` dejaba el evento señalado permanentemente, provocando que `WaitForSingleObject` retornara en bucle infinito de usuario consumiendo 100% de CPU.
   - *Solución:* Implementación de Auto-Reset Event (`CreateEventA(NULL, FALSE, FALSE, name)`) para sincronización cross-process, y delegación nativa en `WaitOnAddress` / `WakeByAddressAll` para hilos intra-proceso.

2. **Pointer Underflow con Violación de Acceso (`ipc_futex_v810.cpp`):**
   - *Falla:* `reinterpret_cast<PmtpFutexSharedHeader*>(addr - 24)` restaba 24 bytes de punteros arbitrarios pasados por el llamador. Si `addr` estaba al inicio de una página o bloque del heap, provocaba un fallo de segmentación (0xC0000005).
   - *Solución:* Validación estricta del offset de página (`page_offset >= 24`) y comprobación del magic `PMTP_FUTEX_MAGIC` antes de acceder a la cabecera. Si no existe cabecera compartida, se conmuta transparentemente a `WaitOnAddress` sin aritmética negativa.

3. **Data Race y Robo de Lock en Banked RCU (`pmtp_rcu_v810.cpp`):**
   - *Falla:* La publicación de `owner_pid` posterior al CAS en `writer_active = 1` permitía una ventana de carrera donde otro hilo observaba `writer_active == 1` con `owner_pid == 0`, permitiendo un robo espurio del lock.
   - *Solución:* CAS atómico de 64 bits sobre el par alineado `{writer_active:32, owner_pid:32}`, fijando ambos campos en una sola instrucción hardware; liberación atómica a 0 en el commit o rollback.

4. **Corrupción de Heap en Python por Deriva de ABI (`test_v810_ipc_suite.py`):**
   - *Falla:* `PolydimTelemetryEvent` estaba declarado en 64 bytes en el script de prueba mientras que la ABI C++ lo exigía en 128 bytes (`metrics[14]`). La función `polydim_spsc_pop` sobreescribía 64 bytes adyacentes del heap de Python en cada uno de los 50,000 eventos, desatando una violación de acceso al salir el intérprete.
   - *Solución:* Sincronización exacta del layout a 128 bytes y opciones del optimizador a 64 bytes (`sizeof(Options) == 64`), protegidas por aserciones duras de arranque.

5. **Piso de Deriva Cuántica $O(1)$ en Solovay-Kitaev (`kernel_rust_v810.rs`):**
   - *Falla:* La secuencia fija `(H,T,H,T†)` se presentaba como aproximación universal a tolerancia $\epsilon$, cuando en realidad producía una rotación de ángulo fijo con error constante $|\delta\theta| \le \pi/8$.
   - *Solución:* Exportación honesta de la cuantización de grilla Clifford finita (`polydim_rust_quantum_quantize_clifford_grid`) reportando el error angular exacto, aislando la cuantización finita de la síntesis continua universal.

6. **Bypass Bizantino y Falla de Normalización BFT (`kernel_rust_v810.rs`):**
   - *Falla:* El atajo `var < 1e-6` otorgaba certificado de consenso sin verificar el quórum de supermayoría ni proyectar el vector resultante a la esfera unitaria $S^{D-1}$.
   - *Solución:* Conjunción cerrada estricta: `Certified = (3a >= 2n) && (H1 <= tau) && (|norm - 1.0| <= eps)`. La varianza cero solo acelera la búsqueda de la mediana, jamás emite el certificado por sí sola.

---

## 3. Certificación Empírica en Silicio Físico (Exit Code 0)

La suite completa fue ejecutada localmente en la máquina del host sin emulaciones ni datos simulados (Regla 10):

```
================================================================================
POLYDIM V810 PHYSICAL SILICON VALIDATION LOG
Host: AMD APU x86_64, Windows, MinGW GCC 14.2.0, Rustc 1.98.1
================================================================================
▶ test_v810_abi_and_ipc.py               -> PASS (Exit Code 0) [128B SPSC, RCU 3-Bank Rotation]
▶ test_v810_quantum_and_honesty.py       -> PASS (Exit Code 0) [Clifford Fidelidad 1.0, DSU Handoff O(1)]
▶ test_v810_adversarial_destructive.py   -> PASS (Exit Code 0) [Ataques X=0, NaNs FFI, Grafo E=0]
▶ test_graph_cuda.py                     -> PASS (Exit Code 0) [Afforest GConn 100k nodos en 8.07 ms]
▶ test_v810_ipc_suite.py                 -> PASS (Exit Code 0) [7/7 Tests: DSYRK, Stiefel, SPSC, DSU, BFT, LSM]
================================================================================
CERTIFICACIÓN FINAL: 5/5 SUITES PASSED — EXIT CODE 0 — CERO ERRORES
================================================================================
```

El log crudo completo con marcas de tiempo e impresiones por terminal se encuentra archivado en:  
`auditoria_externa/05_LOG_RAW_TESTS.txt`

---

## 4. Instrucciones de Re-Compilación y Verificación

Para recompilar las librerías dinámicas desde cero:
```powershell
python compile_v810.py
```

Para ejecutar la batería completa y regenerar la certificación:
```powershell
python run_all_tests_with_log.py
```
