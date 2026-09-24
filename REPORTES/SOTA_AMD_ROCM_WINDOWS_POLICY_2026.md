# POLÍTICA DE ARQUITECTURA SOTA: AMD ROCm / HIP EN WINDOWS VS LINUX (2026)
**Fecha:** 2026-09-19  
**Módulo:** Silicon Contract & HardwareProbe Dynamic Dispatcher (Reglas 19 y 27)  
**Consenso Multi-IA & Tribunal SOTA:** Ariel + Red Team

---

## 1. Diagnóstico del Ecosistema AMD ROCm (Estado 2026)

Con el lanzamiento del **ROCm Core SDK 10.0**, AMD unificó la cadencia de lanzamientos (ciclos de 6 semanas) y retiró el antiguo HIP SDK para Windows, integrando a Windows 11 (25H2) como target secundario de inferencia. Sin embargo, la brecha operativa frente a Linux para HPC y tensor communication de alta dimensión sigue siendo crítica.

### Matriz Comparativa Linux vs Windows

| Dimensión Operativa | Linux / WSL2 / Cloud Enterprise | Windows 11 Nativo (2026) |
| :--- | :--- | :--- |
| **Soporte de Stack** | **Completo:** HIP, Runtime, ROCm Communication Libs, Tuned Kernels | **Parcial:** Core SDK tarball, PyTorch 2.13 oficial, Runtime en consolidación |
| **Instalación y Runtime** | APT / YUM / Pacman / Contenedores OCI | Tarball manual (instalador gestionado previsto fin 2026) |
| **Frameworks LLM** | `vLLM` (Full paged-attention), `llama.cpp`, `Ollama`, `Triton HIP` | `llama.cpp`, `Ollama` funcionales; `vLLM` es **Linux-Only** |
| **Entrenamiento ML / Backprop** | Soportado oficialmente | **No soportado oficialmente** |
| **Concurrencia / Batching** | Multi-stream, multi-batching dinámico | Oficialmente restringido a **Batch Size = 1** |
| **Hardware Validado** | Instinct MI300/MI350, Radeon RX 7000/9000, Ryzen AI Max (`gfx1100`, `gfx1201`, `gfx1151`) | Radeon RX 7000/9000, Ryzen AI seleccionados con PyTorch wheels |

---

## 2. Política Determinista de HardwareProbe (Regla 27)

Para evitar caídas de proceso, memory leaks de DLLs no administradas y fallos de inicialización en tiempo de carga (`hipModuleLoadData`), el módulo `hardware_probe_v761.py` aplica la siguiente política:

```
                       [HardwareProbe: Detección AMD Radeon]
                                         |
               +-------------------------+-------------------------+
               |                                                   |
        [OS == Linux / WSL2]                               [OS == Windows]
               |                                                   |
      [ROCm Runtime Activo?]                              [Entorno de Ejecución]
        /              \                                   /                   \
      (Sí)             (No)                           [WSL2 Activo]      [Windows Nativo]
       |                |                                  |                    |
  [HIP_HSACO]      [CPU_OPENMP]                       [HIP_HSACO]      [Validar HIP SDK]
                                                                        /              \
                                                                      (Sí)             (No)
                                                                       |                |
                                                            [GPU Validada RX 9000] [CPU_OPENMP Default]
```

---

## 3. Matriz de Decisión Operativa POLYDIM

1. **Windows Nativo (Default de Producción):**
   - **Ruta:** Fallback automático y determinista a `CPU_OPENMP` (Neumaier TwoSum compensado + FTZ/DAZ).
   - **Rendimiento Físico:** Certificado $D=10^6$ en **46 ms** (Dart FFI / C++ 14.2.0) con Deriva $= 0.00\times 10^0$. Cero riesgo de kernel panic o cuelgue del driver de pantalla.
2. **Windows Nativo (Opt-In Estricto):**
   - HIP `.hsaco` / Driver API activado **únicamente** si se detecta SDK formal instalado y GPU en lista blanca (RDNA 4 `gfx1200+` / RX 9000).
3. **Linux / WSL2 / Cloud (Kaggle GPU / TPU / Enterprise Cluster):**
   - Despacho prioritario directo a `HIP_HSACO` / ROCm full stack con asignación de buffers DMA pinned.
