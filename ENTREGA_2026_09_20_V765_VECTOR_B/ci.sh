#!/usr/bin/env bash
# CI de POLYDIM V762. Un solo comando reproduce toda la verificación.
# Falla el build completo si cualquier capa falla.
set -euo pipefail
cd "$(dirname "$0")"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"

FP="-fno-fast-math -fno-associative-math -fno-unsafe-math-optimizations -ffp-contract=off"
CXXF="-std=c++17 -O3 -march=native $FP -Wall -Wextra -Wno-unused-parameter -fopenmp -Iinclude"

echo "############ 1/5  C++: build ############"
mkdir -p build
g++ $CXXF -fPIC -shared -o build/libpolydim.so src/polydim_kernel.cpp
g++ $CXXF -o build/test_suite   tests/test_suite.cpp   src/polydim_kernel.cpp
g++ $CXXF -o build/bench        tests/bench.cpp        src/polydim_kernel.cpp
g++ $CXXF -o build/bench_sphere tests/bench_sphere.cpp src/polydim_kernel.cpp

echo "############ 2/5  C++: bateria de invariantes ############"
./build/test_suite

echo "############ 3/5  C++: la guarda anti -ffast-math ############"
# Prueba NEGATIVA. Si esto pasa, el autodiagnostico no sirve.
g++ -std=c++17 -O3 -ffast-math -fopenmp -Iinclude \
    -o build/test_fastmath tests/test_suite.cpp src/polydim_kernel.cpp
if ./build/test_fastmath --selftest-only >/dev/null 2>&1; then
  echo "FALLO: el build con -ffast-math NO fue rechazado."; exit 1
fi
echo "OK: -ffast-math es detectado y rechazado (COMPENSATION_BROKEN)."

echo "############ 4/5  Rust: edicion 2024 + tests ############"
if command -v cargo >/dev/null 2>&1; then
  (cd rust && cargo test --release 2>&1 | tail -15)
else
  echo "OMITIDO: cargo no esta en el PATH."; exit 1
fi

echo "############ 5/5  Dart: el puente invoca de verdad ############"
if command -v dart >/dev/null 2>&1; then
  cp -f build/libpolydim.so dart/
  (cd dart && dart pub get >/dev/null 2>&1 && dart run polydim_ffi.dart)
else
  echo "OMITIDO: dart no esta en el PATH."; exit 1
fi

echo "############ rendimiento ############"
echo "--- S^(D-1) Rodrigues ---"; ./build/bench_sphere
echo "--- St(D,K) Cayley-SMW ---"; ./build/bench

echo
echo "TODO VERDE."
