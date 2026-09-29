# POLYDIM V807 — entrega correctiva verificable

**Estado: base CPU de referencia, con ABI nueva. No certificada para producción.**

Esta entrega transforma los hallazgos V806 en cambios de código, contratos y pruebas. Mantiene comunicación de tensores por memoria compartida, sin generación de texto para transmitir sus valores. Prioriza corrección y trazabilidad; no anuncia rendimiento SOTA ni ausencia de errores.

## Inicio en Windows, sin WSL ni contenedores

Requisitos: Python 3.10 o posterior, NumPy y compilador C++17 (MinGW-w64 o LLVM) disponible en PATH. También hay CMake para MSVC; esa ruta no fue ejecutada en esta entrega.

```powershell
python -m pip install -r requirements.txt
python build.py
python tests/test_regression.py
python tests/test_quantum.py
```

O ejecutar `run_tests.bat`. Los fuentes se compilan localmente: el ZIP no incluye una DLL Windows sin verificar. La validación realizada fue Linux x86-64, GCC 13.3.0, NumPy 2.3.5. `requirements-validated.txt` registra la versión NumPy utilizada; no es una certificación de otras combinaciones.

Validación reproducible con logs y hashes:

```powershell
python tools/verify.py --scale
```

La prueba de escala llega a diez millones de coordenadas y necesita varios cientos de MB de RAM. UBSan en compiladores compatibles:

```powershell
python tools/verify.py --sanitize
```

Rust opcional, si Cargo está instalado:

```powershell
cargo test
cargo build --release
```

No se ejecutó Rust en el entorno de esta entrega. No habilitar el módulo en producción solo porque sus fuentes están presentes.

## Organización

- `include/polydim.h`: ABI C 807 con capacidades y estados explícitos.
- `src/polydim.cpp`: Gramiana compensada, QR Householder, normalización escalada, rotación de rango dos, optimizador Stiefel y reservorio ambiente.
- `python/polydim/native.py`: bindings CPU con validación ABI y propietarios de buffers.
- `python/polydim/shared.py`: bus de dos bancos de memoria compartida para procesos cooperantes creados mediante `spawn`.
- `src/guard.rs`: DSU y selección de medoide extrínseco; elimina certificación BFT y sobrealineación pública.
- `python/polydim/topology.py`: bindings Rust con handshake de tamaño/alineación.
- `python/polydim/quantum.py`: rotaciones en rejilla Clifford+T verificadas mediante matrices; fuera de rejilla devuelve no implementado.
- `src/crypto_windows.cpp`: endurecimiento opcional BCrypt, no probado en Windows; no habilitado por defecto.
- `dart/`: nuevo adaptador de rotación ABI 807, sin PMTPControl de tamaño desconocido; pendiente de ejecución Dart.
- `tests/`: regresión numérica, contratos funcionales, IPC entre procesos y escala.
- `docs/`: decisiones, migración, pendientes y registros reales.
- `reference_v806/`: fuentes originales solo para trazabilidad. **No compilarlos como parte de V807.**

## Uso del núcleo desde Python

Desde la raíz del proyecto, agregar `python` a PYTHONPATH o a sys.path:

```python
import sys
sys.path.insert(0, 'python')
from polydim import Kernel
import numpy as np

kernel = Kernel()
q = kernel.qr(np.random.default_rng(807).normal(size=(10000, 4)))
gram = kernel.gram(q)
```

`Kernel` copia entradas a buffers CPU propios para hacer explícita su vida útil. Ese adaptador **no es una API de cómputo sin copias**. El transporte `SharedTensor` sí ofrece vistas del mapping, sin serializar el payload. Las rutinas numéricas tienen buffers temporales y salida transaccional.

## Memoria compartida

Crear `SharedTensor` en el proceso padre y pasarlo a hijos con contexto `spawn`. Mantener el bloque `if __name__ == '__main__':` en Windows. Los ejemplos ejecutables completos están en la prueba entre procesos.

```python
with bus.write() as tensor:
    tensor[:] = valores_completos
# Solo la salida normal y finita publica el banco.
del tensor
with bus.read() as tensor:
    consumir(tensor)
del tensor
```

Las vistas no deben escapar del contexto. Es una API cooperativa; NumPy no permite revocar una vista retenida por un consumidor malicioso. No cerrar ni desvincular mientras existan vistas o procesos consumidores. Solo el creador desvincula después de unir los hijos.

La escritura inicia el banco inactivo con NaN para detectar escrituras parciales: tiene costo O(D), igual que la validación de finitud. No hay copia de payload entre procesos, pero tampoco publicación completa O(1). La adquisición está serializada por un lock compartido; no es lock-free ni multiproceso hostil.

Si muere un proceso con el lock adquirido, los demás agotan su plazo. **No recuperar forzadamente el banco:** retirar todo el bus y reiniciar la sesión desde el supervisor. La recuperación robusta automática permanece pendiente.

## Contratos esenciales

- ABI 807 no es compatible binariamente con V806. Regenerar consumidores.
- C: punteros válidos, alineados, vivos, capacidades verdaderas, sin mutación concurrente. Validar enteros no prueba que una dirección arbitraria sea segura.
- Matrices: float64, orden C, D filas y K columnas. `pd_qr_f32` convierte internamente a FP64 y devuelve FP32, con precisión FP32.
- QR rechaza rango numérico no resuelto; no fabrica una base ortonormal desde matriz cero.
- El optimizador inicializa mediante QR y usa gradiente tangente + retracción QR con búsqueda Armijo. `PD_OK` indica cómputo válido; `converged` indica estacionariedad. No garantiza óptimo global.
- Rotación: y unitario, u/v ortonormales dentro de 10⁻¹⁰. La verificación de salida usa esa tolerancia; **no se garantiza universalmente 4,44×10⁻¹⁶**.
- Se exige redondeo nearest y subnormales habilitados. Se rechaza fast-math en compilación y se detecta eliminación de subnormales en cada llamada protegida. No se modifica silenciosamente el entorno del llamante.
- LSM es dinámica ambiente y requiere potencia de dos. No mantiene norma unitaria.
- Grafo: β1=E−V+C del multigrafo unidimensional, no homología de la esfera.
- Clustering: medoide extrínseco de la componente mayor, sin normalización ni garantía de verdad/BFT. Empates resueltos determinísticamente por orden.
- Solo CPU implementada como backend central. CUDA/HIP/TPU/XPU son solicitudes no soportadas, no detecciones simuladas.

## Qué leer antes de integrar

`docs/ENTREGA_Y_PENDIENTES.md` mapea los 38 hallazgos; `docs/TEORIA_CORREGIDA.md` delimita las afirmaciones matemáticas. Los logs de pruebas pertenecen a esta entrega, no a los siete tests antiguos.

Formato de razonamiento adaptado por AGT, 2026: evidencia, decisión, cambio y criterio de cierre.
