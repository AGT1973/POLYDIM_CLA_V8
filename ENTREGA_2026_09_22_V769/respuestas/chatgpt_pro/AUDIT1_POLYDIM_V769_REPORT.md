# POLYDIM V769 — Bulldog Red Team Audit 1

## Resultado operativo

Se verificó el paquete adjunto contra código y contratos. La entrega no puede considerarse cerrada: hay fallos P0/P1 en compilación, complejidad, FFI, PMTP real vs test simulado, canario subnormal y coherencia documental.

Artefactos generados:

- `AUDIT1_POLYDIM_CPP.patch`: corrige el C++ de Stiefel para eliminar `G_proj` O(D*K) y mantener workspace streaming.
- `AUDIT1_POLYDIM_PY.patch`: corrige descubrimiento de DLL/SO, slab PMTP con tamaño real/payload real, y LSM sin D objetos Python.
- `AUDIT1_POLYDIM_V769_PATCHES.diff`: parche combinado.

## Verificación ejecutada en contenedor

```bash
g++ -std=c++17 -O2 -fopenmp -fPIC -shared /mnt/data/polydim_audit_fixednewline.cpp -o /mnt/data/build/polydim.dll
cd /mnt/data && python3 polydim_monolith_audit.py
```

La suite original pasó en escala pequeña, pero no detecta los problemas P0 porque:

- Stiefel se prueba en D=10_000, K=16, no en D=10^7/K alto.
- PMTP usa `shared_payloads` Python fuera del slab nativo.
- Rust guard es opcional: si no está la DLL/SO, no falla.
- La afirmación final de éxito es incondicional al cierre real de ABI y entrega.

También se ejecutó la suite tras los parches C++/Python principales:

```bash
g++ -std=c++17 -O2 -fopenmp -fPIC -shared /mnt/data/polydim_audit1.cpp -o /mnt/data/build/polydim.dll
cd /mnt/data && python3 polydim_monolith_audit1.py
```

Resultado: exit code 0 en la prueba pequeña. Esto NO certifica D=10^7; solo confirma que los parches no rompen la suite existente.

## Hallazgos críticos

1. C++ monolítico contiene `\ninline` literal en `set_fp_mode`; el archivo fuente original no compila. Usar la versión corregida o regenerar el monolito desde fuente canónica.
2. Rust guard dice V762 y Betti-1 usa matriz densa `n*n`; contradice V769, spanner O(N) y D>=10^7.
3. README/tribunal declaran Stiefel O(K^2), pero C++ reserva `G_proj` de tamaño D*K. A D=10^7,K=512 son ~40.96 GiB solo para ese buffer.
4. LSM declara SORM O(D), pero crea `dim` listas/ndarrays Python. A D=10^7 se destruye por GC antes de computar.
5. PMTP test no valida el slab IPC real: escribe en `shared_payloads` Python, no en la memoria retornada por el layout nativo.
6. `PMTPSlabChannel.write_tensor` confirma el bug: “Omitted payload write for brevity”; se publica un commit sin copiar tensor.
7. Canario subnormal contradice documentos: README/tribunal dicen `4.94e-324`, contrato empírico aún muestra `1.0005e-42`.
8. Política FTZ/DAZ contradictoria: C++ fuerza OFF por defecto y Python afirma OFF; el prompt/mandato real exige que V769 deliberadamente active FTZ.
9. Binding Rust es opcional, de modo que la suite puede declarar éxito sin ejecutar Betti-1 ni invariant guard.
10. Descubrimiento de librerías sigue hardcodeado a `polydim.dll` / `polydim_rust_guard.dll`, reproduciendo el patrón F-REAL-02.

## Estado

Entrega 1 lista para revisión. Siguiente ciclo recomendado: ABI completo C++/Rust/Python/Dart y prueba PMTP con payload dentro del slab real.
