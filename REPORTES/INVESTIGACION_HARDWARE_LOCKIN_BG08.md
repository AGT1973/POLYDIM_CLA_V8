# INVESTIGACIÓN SOTA BG-08: RIESGO DE VENDOR LOCK-IN Y COLAPSO MULTI-HARDWARE

**Fecha de Ingesta:** 2026-09-18
**Nivel de Riesgo:** CRÍTICO (Bloqueo de Escalamiento Industrial)
**Veredicto:** ACEPTADO. POLYDIM V759 está mortalmente acoplado a la API de NVIDIA. La arquitectura matemática $S^{D-1}$ es universal, pero su implementación física actual sufre de miopía de silicio.

---

## 1. El Vector de Colapso (Vendor Lock-In)
Si el PMTP Bus intenta delegar una subrutina topológica a cualquier hardware que no sea NVIDIA, el orquestador sufrirá un colapso irrecuperable:
*   **AMD (Radeon/Instinct):** Utiliza código objeto `.hsaco` y la API HIP. Nuestro `cuLaunchKernel` fallará al enlazar.
*   **Google TPU (v4 / v5e):** No usa Triton CUBIN, opera sobre tensores XLA a través del compilador Pallas/JAX o XLA-HLO directo.
*   **AWS Trainium / Inferentia:** Utiliza el compilador NeuronCore.
*   **QPU / LPUs (Groq):** Tienen flujos de control de flujo de datos (Dataflow) radicalmente distintos a la arquitectura SIMT de CUDA.

## 2. La Solución Arquitectónica (Capa de Abstracción de Dispositivo)
Para la Fase Industrial (V760+), es obligatoria la eliminación del `cuda_cubin_runner` monolítico a favor de un patrón de diseño **Polimórfico FFI (Device Hardware Abstraction Layer)**.

El orquestador Python debe ejecutar un Hardware Probe (Detector de Silicio) durante el inicio y despachar al runner correspondiente usando una interfaz estándar en C++:

```cpp
// Interfaz Base (Agnóstica)
class IHardwareRunner {
public:
    virtual void init_context() = 0;
    virtual void load_binary(const char* path) = 0;
    virtual void launch(uint64_t* args, int num_args, const LaunchConfig& config) = 0;
    virtual void synchronize() = 0;
};

// Implementación NVIDIA
class CUDARunner : public IHardwareRunner { /* Usa cuLaunchKernel */ };

// Implementación AMD
class HIPRunner : public IHardwareRunner { /* Usa hipLaunchKernel */ };

// Implementación TPU
class XLARunner : public IHardwareRunner { /* Usa PJRT / XLA Client */ };
```

## 3. Contrato de Frontera FFI Refinado
El contrato FFI de Python cambia de:
`launch_triton_cubin(...)`
a:
`launch_accelerator_kernel(binary_type, binary_path, kernel_name, pointers)`

Donde `binary_type` es un enum: `0=NVIDIA_CUBIN`, `1=AMD_HSACO`, `2=TPU_XLA`, dictando dinámicamente qué backend asíncrono instanciar en C++.
