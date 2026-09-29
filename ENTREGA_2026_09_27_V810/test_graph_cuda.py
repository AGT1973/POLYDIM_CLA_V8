import os
import sys
import numpy as np
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from polydim_hw_dispatcher import HardwareProbe, dispatch_graph_cc

def test_graph_cuda_afforest():
    print("\n--- [TEST GPU/AFFOREST] graph_cuda.dll Connected Components ---")
    info = HardwareProbe.probe()
    print(f"✓ HardwareProbe: Cores={info['cpu_cores']}, Optimal={info['optimal_device']}, DLL={info['has_graph_cuda_dll']}")
    assert info["has_graph_cuda_dll"], "graph_cuda.dll no existe en disco"

    # Graph with 100,000 vertices and 2 disconnected components
    # Component 1: 0..79999 (giant)
    # Component 2: 80000..99999
    V = 100000
    edges_part1 = np.column_stack([np.arange(0, 79999, dtype=np.uint32), np.arange(1, 80000, dtype=np.uint32)])
    edges_part2 = np.column_stack([np.arange(80000, 99999, dtype=np.uint32), np.arange(80001, 100000, dtype=np.uint32)])
    edges = np.vstack([edges_part1, edges_part2])

    t0 = time.perf_counter()
    comps, meta = dispatch_graph_cc(edges, V)
    t_el = time.perf_counter() - t0

    print(f"✓ Vértices: {meta['num_vertices']:,} | Aristas: {meta['num_edges']:,}")
    print(f"✓ Componentes detectados: {meta['num_components']} | Tamaño gigante: {meta['giant_component_size']:,}")
    print(f"✓ Backend ejecutado: {meta['backend']} | Tiempo: {meta['execution_time_ms']:.2f} ms")

    assert meta["num_components"] == 2, f"Esperado 2 componentes, obtenido {meta['num_components']}"
    assert meta["giant_component_size"] == 80000, f"Esperado tamaño 80,000, obtenido {meta['giant_component_size']}"
    assert comps[0] == comps[79999], "Fallo de conectividad en componente gigante"
    assert comps[80000] == comps[99999], "Fallo de conectividad en segundo componente"
    assert comps[0] != comps[80000], "Componentes disjuntos conectados erróneamente"

    print("[PASS] graph_cuda.dll Afforest/GConn validado con éxito.")

if __name__ == "__main__":
    test_graph_cuda_afforest()
