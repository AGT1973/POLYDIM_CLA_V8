# ROADMAP DE ESCALABILIDAD FÍSICA Y HARDWARE (Post-V771)
*Documento Arquitectónico de Reserva Estratégica - POLYDIM Swarm*

Este documento registra los vectores de escalamiento de hardware evaluados para el enjambre POLYDIM, superada la V771. La arquitectura núcleo permanece en **C++/Rust (CPU Multi-Core + PMTP Zero-Copy)** para garantizar la asincronía y el control atómico del *Ghost Protocol*. 

No obstante, si la dimensionalidad asintótica ($D \gg 10^7$) o la frecuencia del enjambre superan los límites termodinámicos de la CPU y la RAM, estos son los protocolos de escalamiento listos para ser implementados:

---

## 1. Escalamiento de Memoria SO: Huge Pages (TLB Bypass)
Para mitigar el *TLB Thrashing* (fallos de traducción de caché virtual a física) en tensores masivos (>80 MB):
* **Linux (SOTA):** Sustituir el POSIX `shm_open` nativo de Python por un orquestador en C++ que utilice `memfd_create` + `mmap(MAP_SHARED)` + `madvise(MADV_HUGEPAGE)`. Esto delega al SO la promoción transparente de páginas de 4KB a 2MB (THP).
* **Windows:** Uso de `CreateFileMappingW` con el flag `SEC_LARGE_PAGES`.

## 2. Escalamiento de Cómputo: Offloading Híbrido GPU (cuSOLVER / rocSOLVER)
El cuello de botella computacional remanente en CPU es la inversión/resolución del sistema lineal $2K \times 2K$ en la transformada de Cayley-SMW.
* **Protocolo:** Mantener el anillo PMTP y los subagentes en la memoria RAM (CPU), pero externalizar la resolución de la matriz $2K \times 2K$ (aprox. 8MB para $K=512$).
* **NVIDIA (CUDA):** Transferencia Zero-Copy vía *Pinned Memory* (`cudaHostRegisterDefault`) e inversión masiva en paralelo usando `cusolverDnDgetrf` y `cusolverDnDgetrs`. Latencia proyectada: $< 400 \mu s$.
* **AMD (ROCm/HIP):** Mapeo isomórfico usando `hipBLAS` y `rocSOLVER` para instancias MI300X.

## 3. Escalamiento Distribuido: PMTP-RDMA (Multi-Node Swarm)
Actualmente, el PMTP está anclado a una única placa base (Memoria Compartida del SO). Para distribuir el enjambre a través de un clúster físico sin serializar datos (No-JSON):
* **Protocolo:** Puente de PMTP sobre **RDMA (Remote Direct Memory Access)** usando RoCEv2 o Infiniband nativo. 
* Esto permite que un subagente en el Nodo A escriba en la memoria RAM del Nodo B eludiendo el Kernel del SO y la CPU (Bypass), manteniendo la latencia de red bajo $1 \mu s$ y sosteniendo la telepatía tensorial nativa en todo el clúster.

## 4. Escalamiento Monolítico Alternativo: TPU / JAX (Observación)
* **Viabilidad:** Reescribir la base matemática a **JAX/XLA** para ejecución nativa en clústeres Google TPU (v4/v5p).
* **Trade-off Crítico:** Se gana una aceleración colosal en producto de tensores ($Y^T Y$), pero **se sacrifica la autonomía asincrónica del enjambre**, ya que todos los agentes quedan sujetos al grafo síncrono del compilador XLA en la memoria HBM. Solo recomendado si se abandona la topología Multi-Agente independiente en favor de un solver monolítico.

## 5. Cómputo Cuántico (QPU): Descartado (Research-Only)
* La verificación de ortogonalidad clásica-cuántica (midiendo solapamientos ⟨ψ_i|ψ_j⟩ en un QPU de 127 qubits tras aplicar Randomized SVD) es inviable para producción por el cuello de botella de *State Preparation* y la limitación severa de cúbits físicos actuales. Reservado estrictamente para experimentación topológica teórica.

---
*Veredicto fijado por Antigravity (Bulldog Mode) - 2026-09-22.*
