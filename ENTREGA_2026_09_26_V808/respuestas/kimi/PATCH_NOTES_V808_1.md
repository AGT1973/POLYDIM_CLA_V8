# PATCH NOTES V808 -> V808.1 (Bulldog Red Team)

## Entregado en este patch
| Archivo | Corrige | Qué hace |
|---|---|---|
| polydim_solver_abi_v808_1.h | C2, C5 | Options de 64B sin objective_tolerance; PmtpBankedSlotHeader con prev_bank + writer_heartbeat_ns (leases siguen en offset 128, static_asserts de sizeof); PolydimTelemetryEvent de 128B espejado |
| pmtp_rcu_v808_1.cpp | C1 | Lectores leen active_bank (no derivan de global_epoch); escritor escribe el unico banco ni activo ni previo; drain con deadline real y POLYDIM_STATUS_ERR_DRAIN_TIMEOUT; epoch avanza solo en commit; watchdog de escritor muerto (pid + heartbeat con re-verificacion de owner) |
| kernel_rust_v808_1.patch | C4, G5 | Quorum 3a > 2n (estricto para todo n); align(128) -> align(8) manteniendo sizeof 128 |
| test_v808_1_abi_and_ipc.py | C2 | Suite con layouts espejados, asercion sizeof == polydim_abi_probe(), resultados Rust en buffers 128-alineados, SPSC con payload coherente, test de rotacion RCU |

## Invariante RCU v808.1 (demostrado por simulacion)
write_bank = (3*2 - active_bank - prev_bank) % 3  ->  rota [1,2,0] y nunca
iguala un banco en uso. Lectores solo leen active_bank publicado tras
fence release; el escritor nunca muta un banco con leases ACTIVE.

## Pendiente (siguiente iteracion)
- G1/G2: firewall isfinite en el loop del solver + convergencia condicionada
  a pertenencia a Stiefel (ERR_RANK_DEFICIENT para X nulo).
- C3: futex con GUID del header compartido / handle duplicado + recheck loop.
- G3: usar beta en tiled_dsyrk o documentar contrato beta=0.
- G4: latch de panico Rust auto-recuperable.
- Regenerar 04/05 parseando 05_LOG_RAW_TESTS.txt, no a mano.


## Ronda 3 — pasada completa (todo lo que quedaba)
| ID | Archivo | Hallazgo | Estado |
|---|---|---|---|
| G1 | kernel_cpp | Sin firewall NaN: ERR_NUMERICAL_NAN definido y jamas retornado; X NaN iteraba al max y devolvia status 3 envenenado | CORREGIDO (firewall entrada + por iteración + final) |
| G2 | kernel_cpp | "Converged" certificaba puntos fuera de Stiefel (Ataque 1: X=0 con grad 0 -> CONVERGED con ortho err 4.0) | CORREGIDO (convergencia condicionada a manifold; X nulo -> ERR_RANK_DEFICIENT) |
| G3 | blas loader | tiled_dsyrk ignoraba beta; atomics innecesarios (cada (i,j) pertenece a 1 tile) | CORREGIDO (beta respetado, acumulación en registro, sin atómicas) |
| G6' | kernel_cpp | project_to_tangent_space/VtZ: O(D*K^2) atómicas = el cuello de los 16819 ms | CORREGIDO (scratch por hilo, merge O(K^2) una vez) |
| G7 | kernel_cpp | Shifted CholQR2: shift por-pivote corrompía off-diagonales en casi-singulares | CORREGIDO (Tikhonov real G+sigma*I antes de factorizar) |
| G8 | kernel_cpp | Umbral de pivote absoluto 1e-15 -> falsos singulares/falsos positivos según escala | CORREGIDO (umbral relativo a max|A|) |
| G9 | kernel_cpp | lsm_step: índices de permutación sin validar = OOB read silencioso | CORREGIDO (validación p1/p2 < D + firewall isfinite) |
| G11 | kernel_cpp | _aligned_malloc/posix_memalign exigen alineación múltiplo de sizeof(void*) | CORREGIDO |
| G12 | kernel_cpp | spsc_init: capacity*sizeof(Event) podía desbordar size_t | CORREGIDO |
| -- | kernel_cpp | step_tolerance/converged_step: campo muerto | IMPLEMENTADO |
| Q1 | kernel_rust | Síntesis axis=2 producía R_x, no R_y (fidelidad 0.8536 vs 1.0; verificado numéricamente) | REESCRITA: S·H·Rz·H·S†, nuevo opcode SDAG=8 |
| Q2 | kernel_rust | Test afirmaba R_y(π/4) pero llamaba axis=1 (R_x); jamás se verificaba la unitaria | CORREGIDO (test verifica |Tr(U·R_target†)|/2 = 1.0) |
| G4 | kernel_rust | Latch de pánico permanente = DoS silencioso | CORREGIDO (captura + recupera; last_error global) |
| G13 | kernel_rust | betti con edges NULL y count 0 devolvía NullPointer | CORREGIDO |
| G14 | kernel_rust | frechet_residual era pre-Weiszfeld (obsoleto); vector ~0 certificable | CORREGIDO (residual refinado + normalizable exigido) |
| -- | kernel_rust | last_error thread-local: inaccesible desde otro hilo | CORREGIDO (Mutex global) |
| C3 | ipc_futex | Named event keyed por VA local -> cross-process imposible; wake espurio sin recheck; ResetEvent race | REESCRITO (GUID compartido + recheck loop + sin ResetEvent) |
| -- | pmtp_rcu (mi propio patch) | Steal por heartbeat-stale podía robar a escritor vivo con payload largo -> corrupción | CORREGIDO (steal solo si proceso muerto) |
| -- | pmtp_rcu (mi propio patch) | Aritmética de puntero uint32_t* - 24 restaba 96 bytes | CORREGIDO (char*) |
| -- | tests | DSU: '31.78 ms' sin contar construcción de 10^6 edges en Python | CORREGIDO (test cronometra total) |
