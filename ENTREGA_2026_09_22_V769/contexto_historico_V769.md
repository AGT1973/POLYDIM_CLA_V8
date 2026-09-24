# Contexto Histórico - POLYDIM V769 (Cierre de Ingesta)
Fecha de corte: 2026-09-22 (Cumpleaños 53)

## Estado Actual
Se ha completado la fase de Ingesta Adversarial (Regla 19). Se pasaron 7 reportes de IAs SOTA externas (DeepSeek, Kimi, Z-AI, ChatGPT) validando los hallazgos del Bulldog Critic interno. El código actual (`kernel_cpp_v769.cpp.txt`) tiene intentos de parche que lo dejaron con errores de compilación por sintaxis y duplicación, pero la ruta arquitectónica está 100% resuelta teóricamente.

## Las 7 Brechas y sus Soluciones (A implementar en la nueva sesión)

1. **Bug: PMTP MPMC Deadlock por Muerte Súbita (OOM)**
   - **Solución:** *Tombstone Reaper*. Inyectar `owner_pid` y `owner_start_time` en `PMTP_SlotHeader`. El orquestador vigilará los slots en estado `WRITING` (impar) estancados y forzará el avance si el proceso murió (`kill(0)` / `OpenProcess`).

2. **Bug: Python Torn Reads (Lectura Optimista Peligrosa)**
   - **Solución:** *SEQLock Snapshot*. En `polydim_v769_monolito.py`, el lector debe leer `seq` (verificando que sea par), hacer `np.copyto(read_buf, slot_view)` y volver a leer `seq`. Si cambia o se vuelve impar, se descarta y reintenta.

3. **Cuello de Botella: Contención de Heap en OpenMP**
   - **Solución:** Erradicar `std::vector` dentro de bloques paralelos (Sym, row_gp, NeumaierPad). Reemplazar por arreglos en el stack `[POLYDIM_MAX_K]` y mover los buffers masivos al *Thread-Local Workspace* (`CayleyWS` vía `GrowBuf`).

4. **Cuello de Botella: TLB Thrashing en Reducciones**
   - **Solución:** Invertir los bucles OpenMP en las funciones de proyección tangente y ortogonalidad para leer en memoria de forma adyacente (Row-major) y no a saltos de 8MB.

5. **Cuello de Botella Algorítmico: Asfixia Escalar en `cholqr2`**
   - **Solución:** *Recursive Blocked TRSM*. Particionar la matriz $L$ en bloques $NB=64$. Resolver la diagonal y usar la macroestructura GEMM altamente vectorizable para actualizar el resto, eliminando el bloqueo serial del pipeline (fdiv).

6. **Pérdida de Precisión: Reducción Horizontal Neumaier AVX2**
   - **Solución:** *TwoSum Jerárquico*. Reemplazar el colapso ingenuo escalar al final del bucle SIMD por un árbol binario de fusiones `TwoSum` para no descartar el término de compensación `c_arr` ante magnitudes dispares, garantizando deriva nula.

7. **Bugs de Compilación C++:**
   - **Solución:** Purgar físicamente las redefiniciones de `PMTP_Control`, arreglar los templates faltantes y restaurar el código para que GCC compile limpiamente.

## Siguientes Pasos (Next Action)
En la nueva sesión, el agente debe:
1. Leer este archivo.
2. Iniciar la Fase de Vectorización (/goal).
3. Aplicar los parches al silicio (`.cpp` y `.py`).
4. Compilar la DLL y correr el asalto Bulldog físico.
