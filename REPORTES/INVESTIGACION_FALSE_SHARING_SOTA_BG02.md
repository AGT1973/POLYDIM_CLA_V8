# INVESTIGACIÓN SOTA BG-02: FALSE SHARING Y REDUCCIÓN JERÁRQUICA EN D=10^8

**Fecha de Ingesta:** 2026-09-18
**Veredicto:** CONFIRMADO. `alignas(64)` es insuficiente por sí solo. Si `sizeof(FusedTileAcc)` no es exactamente múltiplo de 64, los arreglos contiguos en memoria solaparán hilos en la misma línea de caché (L1), destruyendo el bus de memoria (False Sharing).

---

## 1. El Peligro del Layout C++ y `sizeof`
Si un struct de Neumaier pesa, por ejemplo, 32 bytes (4 doubles), ponerle `alignas(64)` asegura que el *primer* elemento arranque en una línea de caché, pero el compilador puede empaquetar el siguiente en los 32 bytes restantes de esa misma línea.
**Solución:** Padding explícito para forzar el `sizeof`.

```cpp
#include <cstddef>

constexpr std::size_t CACHE_LINE = 64;
constexpr std::size_t round_up(std::size_t n, std::size_t alignment) {
    return ((n + alignment - 1) / alignment) * alignment;
}

struct NeumaierState {
    double sum;
    double y_comp;
    double correction;
    double error;
};

// Garantía Absoluta contra False Sharing
struct alignas(CACHE_LINE) FusedTileAcc {
    NeumaierState state;
    char padding[ round_up(sizeof(NeumaierState), CACHE_LINE) - sizeof(NeumaierState) ];
};

static_assert(alignof(FusedTileAcc) == CACHE_LINE);
static_assert(sizeof(FusedTileAcc) % CACHE_LINE == 0);
```

## 2. Topología de Reducción Jerárquica (Lane -> Block -> Tree)
1. **Acumulador Privado por Hilo:** Nunca usar `#pragma omp critical`.
2. **Stride del Vector de Parciales:** La indexación en un bucle anidado debe ser `tid * num_blocks + block` y **no** `block * num_threads + tid`. Si se usa este último, hilos distintos escriben en direcciones consecutivas (destrozando L1).
3. **OpenMP Declare Reduction:** Es preferible declarar la operación de Neumaier formalmente a nivel de OpenMP si el compilador soporta User Defined Reductions, o hacer la fase de reducción manual `final_acc = neumaier_combine(final_acc, partials[tid * ...])`.

## 3. Validación Requerida en V759
Se debe inyectar el código de validación estático en C++:
```cpp
// Valida direcciones base y strides
for (std::size_t i = 0; i + 1 < partials.size(); ++i) {
    auto a = reinterpret_cast<std::uintptr_t>(&partials[i]);
    auto b = reinterpret_cast<std::uintptr_t>(&partials[i + 1]);
    assert(a % CACHE_LINE == 0);
    assert((b - a) % CACHE_LINE == 0);
}
```

## 4. Fuentes SOTA 2026 Confirmadas
* [cppreference: hardware_destructive_interference_size](https://en.cppreference.com/w/cpp/thread/hardware_destructive_interference_size)
* [Especificación OpenMP 5.2 - User Defined Reductions](https://www.openmp.org/spec-html/5.2/openmpsu55.html)
* [Arm Server and Cloud Computing: False Sharing](https://learn.arm.com/learning-paths/servers-and-cloud-computing/false-sharing-arm-spe/how-to-1/)
