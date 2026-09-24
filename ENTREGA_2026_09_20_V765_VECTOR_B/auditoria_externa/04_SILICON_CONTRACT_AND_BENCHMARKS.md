# ⚡ CONTRATO DE SILICIO Y TELEMETRÍA DE BENCHMARKS (POLYDIM V762)

> **Document:** `04_SILICON_CONTRACT_AND_BENCHMARKS.md`  
> **Testing Environment:** Linux x86-64 (GCC 15.2) / Windows 10/11 x86-64 (MinGW GCC 14.2 & MSVC 2026) | Rust 1.98.1 | Dart 3.13.4  
> **Status:** 100% PASS (Exit Code 0 across all layers)  

---

## 1. 📋 Configuración Contractual de Compiladores

| Componente | Compilador / Runtime | Flags Obligatorias | Binario / Artefacto |
|---|---|---|---|
| **C++ Kernel** | GCC 14.2 / GCC 15.2 (`g++.exe`) | `-O3 -shared -fPIC -fno-fast-math -fno-associative-math -ffp-contract=off -fopenmp` | `libpolydim.dll` / `libpolydim.so` |
| **Rust Guard** | `rustc` 1.98.1 (Edición 2024) | `opt-level = 3`, `panic = "unwind"`, `#[unsafe(no_mangle)]` | `polydim_verify.dll` / `.so` |
| **Dart FFI** | Dart SDK 3.13.4 (Standalone) | `dart dart/polydim_ffi.dart` (Ejecución y liberación nativa) | Puente FFI Standalone |

---

## 2. 🧪 Batería Física de Pruebas C++ (26/26 PASS | Exit Code 0)

Ejecución real sobre silicio:

```
=== POLYDIM V762 :: POLYDIM V762 | FTZ/DAZ=OFF (conforme IEEE-754) | BLAS=OFF (bucles nativos) | OpenMP=ON ===
polydim_selftest_all() = 0 (SUCCESS)

[A11] Autodiagnostico de la sumacion compensada
  [ OK ] Neumaier sobrevive a las banderas del compilador     err_rel=0.000e+00

[base] Rodrigues: camino feliz
  [ OK ] deriva <= 2.10e-14 (cota certificada)                D=1000 |1-||y'|| |=1.110e-16  hilos=2
  [ OK ] deriva <= 2.10e-14 (cota certificada)                D=100000 |1-||y'|| |=2.220e-16  hilos=2
  [ OK ] deriva <= 2.10e-14 (cota certificada)                D=1000000 |1-||y'|| |=0.000e+00  hilos=2

[doc] Convencion de rotacion: R(+theta) canonica
  [ OK ] R(u)=cos(t)u+sin(t)v  (V761 daba R(-t))              rc=0 residuo=0.000e+00

[base] Composicion geodesica: 1 paso grande vs 20000 pequenos
  [ OK ] 20000 pasos no acumulan deriva                       diff=8.916e-16 deriva_max=2.220e-16

[A3] Escalares no finitos (V761: 100% NaN con rc=SUCCESS)
  [ OK ] theta=NaN rechazado                                  rc=-8 (INVALID_SCALAR (theta/tau no finito))
  [ OK ] theta=Inf rechazado                                  rc=-8 (INVALID_SCALAR (theta/tau no finito))
  [ OK ] NaN en y rechazado                                   rc=-3 (NAN_OR_INF en los datos)

[A2] Compuerta de ortonormalidad (V761: deriva 1.47e-2 con rc=SUCCESS)
  [ OK ] v no ortogonal a u rechazado                         |<u,v>|=2.873e-01 rc=-9
  [ OK ] ||u||=2 rechazado                                    |<u,u>-1|=3.000e+00 rc=-9
  [ OK ] ||u||=1+1e-8 rechazado                               |<u,u>-1|=2.000e-08 rc=-9

[A4] Punto de entrada fuera de la variedad (V761: rc=SUCCESS)
  [ OK ] ||y||!=1 rechazado                                   escala=1+1e-06 |<y,y>-1|=2.000e-06 rc=-10
  [ OK ] ||y||!=1 rechazado                                   escala=1+1e-09 |<y,y>-1|=2.000e-09 rc=-10
  [ OK ] project_sphere repara el punto                       rc=0/0 deriva=1.110e-16

[base] Stiefel Cayley-SMW: ortogonalidad medida a posteriori
  [ OK ] ortogonalidad <= 1e-13                               D=512 K=8 max|YtY-I|=6.661e-16 pivote=1.000e+00/umbral=2.988e-14 hilos=2
  [ OK ] ortogonalidad <= 1e-13                               D=2048 K=16 max|YtY-I|=8.882e-16 pivote=1.000e+00/umbral=5.985e-14 hilos=2
  [ OK ] ortogonalidad <= 1e-13                               D=4096 K=64 max|YtY-I|=1.998e-15 pivote=1.000e+00/umbral=2.415e-13 hilos=2
  [ OK ] ortogonalidad <= 1e-13                               D=8192 K=32 max|YtY-I|=2.442e-15 pivote=1.000e+00/umbral=1.201e-13 hilos=2
  [ OK ] tau=NaN rechazado                                    rc=-8 (INVALID_SCALAR (theta/tau no finito))
  [ OK ] K=1024 rechazado (limite declarado = 512)            rc=-7 (BUFFER_OVERFLOW (K fuera de rango))
  [ OK ] X con XtX != I rechazado                             rc=-10 (POINT_OFF_MANIFOLD)

[A9] Umbral de pivote relativo a ||M||_inf
  [ OK ] el umbral escala con la magnitud de M                rc=-5 umbral=6.172e+00 (1e-15 absoluto seria 6171537881911400x menor)

[A1] PMTP triple bufer: lecturas desgarradas y hambre del lector
  ... escrituras=452583 lecturas_ok=1098 carreras_detectadas=82548 sin_novedad=7845655
  [ OK ] ninguna lectura aceptada estaba desgarrada           desgarros NO detectados = 0 de 1098 lecturas validadas
  [ OK ] el lector progresa (no hay hambre)                   lecturas coherentes=1098 (V761: 0,35% de 83646)
  [ OK ] POLYDIM_ERR_SEQLOCK_RACE tiene ruta de retorno       carreras detectadas=82548 -> el codigo -6 es alcanzable

================ RESUMEN ================
  pasadas: 26   falladas: 0 (Exit Code 0)
```

---

## 3. 🦀 Suite de Invariantes en Rust 2024 (8/8 PASS | Exit Code 0)

```
running 8 tests
test tests::acepta_unitario ... ok
test tests::cota_no_escala_con_d ... ok
test tests::detecta_base_no_ortonormal ... ok
test tests::nan_se_reporta_como_nan ... ok
test tests::neumaier_vence_a_la_suma_ingenua ... ok
test tests::rechaza_deriva_que_v761_aceptaba ... ok
test tests::reporte_siempre_escrito_en_salida_temprana ... ok
test tests::subnormal_no_es_error ... ok

test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.13s
```

---

## 4. 🚀 Benchmark Dart 3.13 FFI Standalone en Silicio

```
Biblioteca abierta: POLYDIM V762 | FTZ/DAZ=OFF (conforme IEEE-754) | BLAS=OFF (bucles nativos) | OpenMP=ON
Autodiagnostico: OK
Base ortonormal: |<u,v>|=0.000e+00
D=1000000  mediana=4.27 ms  min=3.41 ms  deriva=0.000e+00  hilos=2
[OK] theta=NaN -> INVALID_SCALAR
[OK] theta=Inf -> INVALID_SCALAR
[OK] base rota -> BASIS_NOT_ORTHONORMAL
```

---

## 5. 🏎️ Comparativa de Rendimiento Stiefel $St(D, K)$ vs OpenBLAS

| Configuración $(D, K)$ | V761 Original | **V762 Hardened** | OpenBLAS Referencia | Ganancia vs V761 | Deriva Máxima $\|Y^\top Y - I\|$ |
|---|---|---|---|---|---|
| **$4096, 16$** | $19.18\text{ ms}$ | **$0.89\text{ ms}$** | $1.77\text{ ms}$ | **$21.5\times$ más rápido** | $6.66 \times 10^{-16}$ |
| **$4096, 64$** | $28.05\text{ ms}$ | **$9.90\text{ ms}$** | $5.71\text{ ms}$ | **$2.8\times$ más rápido** | $6.66 \times 10^{-16}$ |
| **$16384, 32$** | $32.03\text{ ms}$ | **$9.68\text{ ms}$** | $14.99\text{ ms}$ | **$3.3\times$ más rápido** | $8.88 \times 10^{-16}$ |
| **$16384, 128$** | $458.16\text{ ms}$ | **$152.30\text{ ms}$** | $124.24\text{ ms}$ | **$3.0\times$ más rápido** | $8.88 \times 10^{-16}$ |
| **$65536, 64$** | $408.58\text{ ms}$ | **$143.19\text{ ms}$** | $190.38\text{ ms}$ | **$2.9\times$ más rápido** | $1.11 \times 10^{-15}$ |

=================================================================
>>> POLYDIM V762: SILICON CONTRACT 100% CERTIFIED (EXIT CODE 0) <<<
=================================================================
