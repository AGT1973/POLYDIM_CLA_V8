# 🏛️ INGESTA SOTA V800: RDMA MIR-WIRE (GPU-TO-GPU BYPASS)
**Fecha:** 2026-09-24
**Módulo:** Transferencia de Tensores Latentes Inter-Nodo

## Principio: GPUDirect RDMA
La NIC lee/escribe VRAM mediante PCIe/DMA-BUF sin pasar por CPU RAM ni stack TCP/IP.

## Stack Recomendado por Plataforma
| Plataforma | Stack | Latencia |
|------------|-------|----------|
| AWS P5/P5en/P6 | NIXL + libfabric + EFA + GDRCopy | ~1s TTFT vs ~98s TCP |
| Azure ND-H100 | NIXL + UCX + InfiniBand NDR | 20-50 GB/s, ~1 µs |
| Google A3 Ultra/A4 | NIXL + MRDMA/RoCE | 3600 Gbps |
| Bare metal | UCX + ConnectX-7/8 + InfiniBand | Máxima determinación |
| Kaggle | Solo baseline host-staged (sin RDMA real) | — |

## Protocolo MIR-Wire V800
1. Reservar pool persistente de buffers CUDA (nunca `cudaMalloc` por transferencia).
2. Registrar buffers una sola vez con NIXL/libfabric.
3. Producir tensor en stream CUDA → insertar evento de finalización.
4. Enviar descriptor remoto → ejecutar RDMA desde VRAM.
5. Notificar completion → esperar evento antes del kernel consumidor.
6. Reutilizar buffer mediante pool (doble/triple buffering).

## 3 Modos Verificables
- `MIR_CPU`: GPU → pinned host → red → pinned host → GPU (baseline).
- `MIR_RDMA`: GPU → RDMA NIC → red → RDMA NIC → GPU (objetivo SOTA).
- `MIR_GDA`: GPU kernel → NIC → red → NIC → GPU (GPUDirect Async, V2).

## Validación Anti-Fallback Silencioso
```bash
nvidia-smi topo -m     # Topología PCIe GPU↔NIC
ucx_info -d            # Debe mostrar "memory types: host, cuda"
ibv_devinfo            # Info RDMA
fi_info -p efa         # Info EFA
ls -l /dev/gdrdrv      # GDRCopy presente
```
