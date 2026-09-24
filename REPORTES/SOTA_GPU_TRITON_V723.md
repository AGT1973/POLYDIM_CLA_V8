# REPORTE SOTA: KERNELS UNIVERSALES EN GPU Y TRITON (V723)
**PROTOCOLO**: POLYDIM Core
**FECHA DE CORTE**: Septiembre 2026

---

## 1. `torch.compile(mode="reduce-overhead")` como Reemplazo o Fallback a Triton

Históricamente, la creación de "kernels universales" (portables, sin compilación C++ nativa) dependía de escribir rutinas puras en Triton. Sin embargo, con la evolución de TorchInductor, `torch.compile(mode="reduce-overhead")` se presenta como un reemplazo primario altamente competitivo para la orquestación en GPU, permitiendo que código Python vectorizado alcance velocidades asintóticas equivalentes sin escribir Triton manualmente.

### Mecanismo de Aceleración y CUDA Graphs
El modo `reduce-overhead` está diseñado para erradicar el cuello de botella de la CPU (launch overhead). 
- **CUDA Graphs**: Captura la topología estática del grafo de ejecución de PyTorch y repite las secuencias de lanzamiento de kernels como una única operación de GPU. Esto es crucial cuando el tamaño de los tensores es moderado o pequeño, donde el overhead de Python domina.
- **Inductor como Generador**: Al compilar, Inductor traduce automáticamente las operaciones de PyTorch en kernels Triton altamente optimizados (y frecuentemente fusionados). Por lo tanto, escribir operaciones tensorizadas limpias y compilarlas actúa como un **kernel universal de facto**, ya que Inductor gestiona la reducción a Triton en el backend.

### Estrategia de Fallback (Graph Breaks)
Cuando `torch.compile` encuentra operaciones que no puede "bajar" (lower) a Triton (control flow dinámico complejo, tipos no soportados o llamadas a librerías de terceros sin registrar), ocurre un **Graph Break**.
- **Comportamiento**: El compilador retrocede (fallback) al modo *eager* (ATen) para ejecutar esa sección del grafo y luego vuelve a intentar compilar el resto.
- **Mitigación POLYDIM**: Para evitar que el compilador rompa el grafo y pierda el rendimiento del CUDA Graph, cualquier operación personalizada debe registrarse apropiadamente usando `torch.library.custom_op` o `torch.library.triton_op`. Esto vuelve al kernel "opaco pero amigable" para el JIT, permitiendo que `reduce-overhead` rastree la topología sin romper el contexto de compilación.

---

## 2. Manejo de Valores Escalares en Triton (Anti-AttributeError)

El error `AttributeError: "tl.constexpr"` y problemas similares (como `TypeError: 'type' object is not subscriptable` en versiones antiguas) ocurren por una colisión entre el sistema de tipos de tiempo de ejecución de Python y el sistema de evaluación de constantes en tiempo de compilación (AST) de Triton.

### Origen del Error
Triton especializa (JIT-compila) un kernel por cada combinación de tipos y valores marcados como constantes. Si se le instruye a Triton que una variable dictará la geometría de la memoria (ej. `tl.arange`, unroll loops) pero el valor es dinámico o le falta la anotación, el compilador AST colapsa porque no puede resolver el tamaño estático.

### Reglas Estrictas de Resolución

1. **Uso Mandatorio de `tl.constexpr` (Para Geometría y Bloques)**:
   - Todo parámetro escalar que se utilice para inicializar rangos (`tl.arange`, `tl.static_range`), máscaras de memoria dependientes del tamaño del bloque, o configuraciones de hardware (tamaño SIMD, block limits), **debe** llevar la anotación `: tl.constexpr` en la firma del kernel.
   ```python
   @triton.jit
   def mi_kernel(..., BLOCK_SIZE: tl.constexpr):
       offsets = tl.arange(0, BLOCK_SIZE) # BLOCK_SIZE debe ser constexpr
   ```

2. **Escalares de Tiempo de Ejecución (Runtime Scalars)**:
   - Si el escalar desde Python es un hiperparámetro dinámico (ej. un valor de `alpha`, `learning_rate` o un offset dinámico) que cambiará en cada llamada, **NO debe marcarse** con `constexpr`.
   - Simplemente páselo como argumento (ej. `alpha: tl.float32` o sin tipo). Triton lo recibirá y lo promoverá automáticamente a un tensor escalar 0D de GPU (`i32` o `f32`), permitiendo operaciones matemáticas normales sin forzar una recompilación JIT en cada ciclo.

3. **Inmutabilidad en Ciclos**:
   - Una causa común de `AttributeError` o error de compilación es reasignar una variable dentro de un ciclo `while` o `for` que previamente fue inferida como `constexpr`. Si un escalar va a mutar en tiempo de ejecución, su estado inicial no debe estar atado al árbol de AST estático.

### Conclusión para LatentMAS / POLYDIM
Para mantener el *Zero-Waste Execution* y evitar fallas asintóticas en el runtime, los parámetros de hardware y límites topológicos ($D \ge 10,000$) deben extraerse dinámicamente en Python pero inyectarse en el kernel Triton estrictamente como `tl.constexpr`. Los tensores latentes continuos y gradientes deben fluir libres sin anotaciones restrictivas que rompan el AST en el modo de deformación.
