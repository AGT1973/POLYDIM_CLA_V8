# AUDIT2 — POLYDIM V769 Bulldog Red Team Pass

Fecha: 2026-09-22  
Base: archivos separados subidos en la segunda tanda (`kernel_cpp_v769.cpp.txt`, `kernel_rust_v769.rs.txt`, `polydim_v769_monolito.py.txt`, Dart FFI, Triton, LSM, MIR-Wire, QASM, logs).

## Resultado ejecutivo

Esta pasada encontró P0/P1 nuevos y verificables en la entrega separada.

Lo más importante: el C++ separado **sí compila**, pero el paquete original no arranca en Linux con el binario natural `libpolydim.so`; además, el C++ queda con FTZ/DAZ encendido por defecto mientras la suite Python exige FTZ/DAZ apagado para preservar subnormales.

Apliqué un parche mínimo sobre C++/header/Python que:

1. cambia `POLYDIM_ENABLE_FTZ` default de `1` a `0`;
2. expone `polydim_pmtp_payload_ptr`;
3. hace que Python encuentre `.dll`, `.so` y `.dylib`;
4. hace que el PMTP test escriba y lea el payload real dentro del slab nativo, no arrays Python externos;
5. declara `polydim_check_ftz` y `polydim_pmtp_payload_ptr` en el header público.

## Evidencia ejecutada

### Original

```text
original_lib_selftest_all= 0
original_lib_check_ftz= 1
================================================================================
🏛️ POLYDIM V769 — INDUSTRIAL VERIFICATION & RED TEAM MONOLITH
================================================================================
[HW_PROBE] OS: linux | CPU Cores: 5 | CUDA: False (None)
[HW_PROBE] IEEE-754 eps_mach: 2.22e-16
Traceback (most recent call last):
  File "/mnt/data/audit2_orig_run/polydim_v769_monolito.py", line 561, in <module>
    run_v769_global_suite()
    ~~~~~~~~~~~~~~~~~~~~~^^
  File "/mnt/data/audit2_orig_run/polydim_v769_monolito.py", line 374, in run_v769_global_suite
    binding = PolydimNativeBinding(build_dir)
  File "/mnt/data/audit2_orig_run/polydim_v769_monolito.py", line 159, in __init__
    raise FileNotFoundError(f"Cannot find polydim.dll in {dll_dir}")
FileNotFoundError: Cannot find polydim.dll in /mnt/data/audit2_orig_run/build
```

### Parche aplicado

```text
================================================================================
🏛️ POLYDIM V769 — INDUSTRIAL VERIFICATION & RED TEAM MONOLITH
================================================================================
[HW_PROBE] OS: linux | CPU Cores: 5 | CUDA: False (None)
[HW_PROBE] IEEE-754 eps_mach: 2.22e-16
[NATIVE_FFI] Loaded polydim.dll | Build Info: POLYDIM V769 | FTZ/DAZ=OFF (conforme IEEE-754) | BLAS=OFF (bucles nativos optimizados) | OpenMP=ON
[SELFTEST_ALL] Compensation & Manifold Autodiagnostic: Status = 0 (SUCCESS)
[F-03 IN-PLACE] D=100000 | y_out==y executed legally without UB | Drift: 0.00e+00 (OutNormErr: 0.00e+00)
[F-01 SEQLOCK] Starting Multi-Threaded Stress Test (1 Writer, 4 Concurrent Readers, 1000 Writes)...
[F-01 SEQLOCK RESULT] Total Reads: 9499 | Successful Validations: 4597 | Races Detected: 0
[F-01 SEQLOCK RESULT] Success Rate: 100.00% (Target: >99%) | Data Corruptions / Torn Reads: 0
[F-04 STIEFEL SMW] D=10000, K=16 | Ortho Error Real: 3.11e-15 (Reported: 4.00e-15) | Workspace O(K^2) Confined
[F-07 TANGENT ADAPTER] D=10000 | RecRelErr: 5.62e-16 | Stiefel OrthoErr: 6.66e-16 | Cond(W): 1.000000 (kappa=1 exact)
[SUBNORMAL CANARY] Host CPU IEEE-754 subnormal (4.9407e-324) processed with rc=0 | Preserved in FPU
[QUANTUM & LSM] SO(8) Rotor compiled (16 lines) | LSM 25 steps reservoir S^(D-1) Norm: 0.9999999999999999
================================================================================
🎯 TODOS LOS PARCHES P0/P1 Y ESTUDIOS ANALÍTICOS CERTIFICADOS CON ÉXITO
================================================================================
exit:0
```

## Hallazgos integrados

### P0 — Startup roto por loader Python no portable

`polydim_v769_monolito.py.txt` busca `polydim.dll` y `libpolydim.dll` dentro de `build`, pero en Linux el binario natural compilado es `libpolydim.so`. En ejecución real, el monolito falló antes de entrar a la suite.

Impacto: dead-on-arrival fuera de Windows o si el artefacto no se llama exactamente `polydim.dll`.

Parche: ver `AUDIT2_POLYDIM_V769_PATCHES_CLEAN.diff`, sección `PolydimNativeBinding._find_native_library`.

### P0 — Contrato FTZ/DAZ contradictorio

El C++ dice en comentario que FTZ/DAZ está apagado por defecto, pero define `POLYDIM_ENABLE_FTZ 1`. La suite Python inyecta el subnormal físico `4.9406564584124654e-324` y exige `ftz == 0`.

Impacto: el C++ original compila y `selftest_all()` pasa, pero deja MXCSR con FTZ/DAZ encendido. La suite completa termina castigando el modo numérico que el propio kernel activó.

Parche: `#define POLYDIM_ENABLE_FTZ 0`.

### P0 — PMTP test original no validaba slab real

El método `PMTPSlabChannel.write_tensor()` hacía commit sin copiar payload. La prueba de estrés usaba `shared_payloads = [np.zeros(...)]` fuera del slab nativo. Eso prueba el contador seqlock, pero no prueba transporte zero-copy PMTP.

Impacto: una corrupción de offset, layout o payload PMTP podía pasar desapercibida.

Parche: se agregó `polydim_pmtp_payload_ptr` en C++/header y el test Python ahora escribe/lee el payload real dentro del slab.

### P1 — Dart FFI está desincronizado con C ABI actual

Dart busca símbolos `polydim_pmtp_begin_write`, `polydim_pmtp_commit_write`, `polydim_pmtp_acquire_read`, `polydim_pmtp_validate_read`, pero el C exporta `polydim_pmtp_write_begin`, `polydim_pmtp_write_commit`, `polydim_pmtp_read_begin`, `polydim_pmtp_read_validate`.

Además, los typedef PMTP de Dart usan firmas antiguas con `Uint64` donde C usa `uint32_t* slot` y `uint64_t* ver`.

Impacto: `DynamicLibrary.lookupFunction` falla en runtime o llama con ABI incorrecto.

Patch requerido: actualizar nombres y firmas en `polydim_ffi.dart.txt` y `test_pmtp.dart.txt`.

### P1 — Rust sigue marcado como V762 y tiene frontera `usize -> u32` no defendida

El archivo separado ya usa edge-list sparse, lo cual corrige la matriz densa del monolito anterior. Pero conserva banner `POLYDIM V762` y castea `num_vertices as u32` para construir DSU. Para `num_vertices > u32::MAX`, la representación se trunca.

Impacto: versión trazable rota; para dominios extremos, la guardia topológica puede fallar por overflow lógico antes de memoria.

Patch requerido: rechazar `num_vertices > u32::MAX as usize`; validar pesos `w.is_finite()`; documentar que `edges` ya viene filtrado por spanner/threshold.

### P1 — Triton GPU cae a `.item()` en D objetivo

La ruta Triton promete evitar reducción CPU, pero si `block_reduce > 4096` entra en fallback y usa `torch.sum(...).item()`. Para `D=10^7` y block típico 1024, `num_partials≈9766`, así que cae precisamente en fallback.

Impacto: sincronización GPU→CPU en la dimensión objetivo; contradice el claim “100% GPU”.

Patch requerido: mantener `alpha` y `beta` como tensores GPU y pasarlos a un pass2 que cargue `alpha_beta_ptr`.

### P1 — Quantum compiler emite `ry(...)` continuo y lo llama Clifford+T

El QASM generado contiene gates `ry(0.785398)`, `ry(1.570796)`, etc. Eso no es una síntesis pura Clifford+T discreta; es circuito híbrido con rotaciones analógicas continuas más comentarios de aproximación.

Impacto: certificación matemática incorrecta del compilador cuántico.

Patch requerido: o renombrar el módulo como “OpenQASM native rotation emitter”, o reemplazar `ry` por una descomposición discreta real con presupuesto de error.

### P2 — LSM ya no es el viejo patrón de listas Python, pero sigue mintiendo “O(1)”

El archivo separado usa DCT implícita y diagonal Rademacher. Eso elimina la muerte por millones de objetos Python, pero su propio docstring dice `O(D log D)` por paso. No debe titularse “O(1)”.

Impacto: claim asintótico incorrecto; riesgo de documentación falsa.

Patch requerido: cambiar título y prints a `O(D log D)` o reemplazar DCT por SORM/Householder/butterfly O(D) si la meta contractual es O(D).

### P2 — MIR-Wire es socket emulator, no RDMA zero-copy

El receptor aloca `bytearray(tensor_bytes)` y luego reconstruye `np.frombuffer`; el emisor usa `sock.sendall(memoryview(tensor))`. Eso evita JSON/texto, pero no es RDMA real ni zero-copy kernel-bypass.

Impacto: benchmark WAN/RDMA no puede presentarse como RoCE/IBV real.

Patch requerido: renombrar como emulator o implementar backend real `libibverbs`/`pyverbs` con MR registrado y completion queue.

## Parches incluidos

Archivo: `AUDIT2_POLYDIM_V769_PATCHES_CLEAN.diff`

Cubre:

- `kernel_cpp_v769.cpp`
- `polydim.h`
- `polydim_v769_monolito.py`

No cubre todavía Dart/Rust/Triton/Quantum/MIR porque requieren refactor separado y compiladores/runtimes no disponibles en este contenedor (`rustc` y `dart` no están instalados aquí).

## Comandos de verificación ejecutados

```bash
g++ -std=c++17 -O2 -fopenmp -shared -fPIC kernel_cpp_v769.cpp -o libpolydim.so

python - <<'PY'
import ctypes
lib=ctypes.CDLL('./libpolydim.so')
lib.polydim_selftest_all.restype=ctypes.c_int32
lib.polydim_check_ftz.restype=ctypes.c_int32
print(lib.polydim_selftest_all())
print(lib.polydim_check_ftz())
PY

python polydim_v769_monolito.py
```

Resultado con parche: suite completa exit code 0 en CPU local del contenedor.

## Limitaciones honestas

- Rust no pudo compilarse: `rustc` no está instalado.
- Dart no pudo compilarse: `dart` no está instalado.
- Triton no pudo validarse en GPU: no hay GPU/Triton runtime operativo en el contenedor.
- El resultado de D=10^7 sigue siendo REQUIERE SILICIO/EJECUCIÓN REAL. Esta pasada solo certifica que se corrigieron fallas P0 reproducibles de startup, FTZ y PMTP slab test en escala chica.

Formato de razonamiento adaptado por AGT_2026.
