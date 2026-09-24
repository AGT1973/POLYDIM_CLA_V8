# POLYDIM V762 — build endurecido
#
# A11: las banderas -fno-fast-math / -fno-associative-math NO son opcionales.
# Si se eliminan, la sumación de Neumaier se colapsa y polydim_selftest_all()
# devuelve POLYDIM_ERR_COMPENSATION_BROKEN. El target `verify` lo comprueba.

CXX      ?= g++
CXXSTD   ?= -std=c++17
OPT      ?= -O3 -march=native
# --- banderas numéricas obligatorias ---
FPFLAGS  := -fno-fast-math -fno-associative-math -fno-unsafe-math-optimizations \
            -ffp-contract=off -fno-reciprocal-math -fno-finite-math-only
WARN     := -Wall -Wextra -Wno-unused-parameter
CXXFLAGS := $(CXXSTD) $(OPT) $(FPFLAGS) $(WARN) -fopenmp -fPIC -Iinclude
LDFLAGS  := -fopenmp

# Nombre de biblioteca correcto por plataforma (A12: V761 emitía "polydim_kernel.so")
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
  LIBNAME := libpolydim.dylib
  SHARED  := -dynamiclib
else
  LIBNAME := libpolydim.so
  SHARED  := -shared
endif

BUILD := build
SRC   := src/polydim_kernel.cpp

.PHONY: all verify clean blas bench
all: $(BUILD)/$(LIBNAME) $(BUILD)/test_suite

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/$(LIBNAME): $(SRC) include/polydim.h | $(BUILD)
	$(CXX) $(CXXFLAGS) $(SHARED) -o $@ $(SRC)

$(BUILD)/test_suite: tests/test_suite.cpp $(SRC) include/polydim.h | $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ tests/test_suite.cpp $(SRC) $(LDFLAGS)

# Variante con BLAS/LAPACK: misma API, mismo contrato de errores.
blas: $(SRC) include/polydim.h | $(BUILD)
	$(CXX) $(CXXFLAGS) -DPOLYDIM_USE_BLAS $(SHARED) -o $(BUILD)/libpolydim_blas.so $(SRC) -llapack -lblas

# Prueba negativa: con -ffast-math el autodiagnóstico DEBE fallar.
$(BUILD)/test_fastmath: tests/test_suite.cpp $(SRC) | $(BUILD)
	$(CXX) $(CXXSTD) -O3 -ffast-math -fopenmp -Iinclude -o $@ tests/test_suite.cpp $(SRC) $(LDFLAGS)

verify: $(BUILD)/test_suite $(BUILD)/test_fastmath
	@echo "=== build correcto: debe pasar ==="
	@$(BUILD)/test_suite
	@echo "=== build con -ffast-math: el autodiagnostico debe RECHAZARLO ==="
	@! $(BUILD)/test_fastmath --selftest-only || (echo "FALLO: -ffast-math no fue detectado"; exit 1)
	@echo "OK: la guarda anti -ffast-math funciona."

clean:
	rm -rf $(BUILD)
