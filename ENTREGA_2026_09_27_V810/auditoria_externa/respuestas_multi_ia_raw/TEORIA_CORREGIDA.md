# Contrato matemático revisado

## Información y representación

DPI se cumple: I(X;g(Y)) ≤ I(X;Y). Si g codifica biyectivamente un tensor finito, se conserva información. Una secuencia de bytes no convierte la geometría en una recta. Lo que puede perder semántica es sustituir el estado por un resumen lingüístico, cuantizarlo o eliminar coordenadas.

La propuesta tensorial evita la necesidad de generar lenguaje para mover estados. Debe conservar valores, forma, dtype y significado de coordenadas. Compartir norma o dimensionalidad no alinea modelos diferentes: el espacio latente debe identificarse y sus adaptadores validarse en tareas.

## Variedades separadas

Esfera: norma uno. Stiefel: XᵀX=I. Grassmann: subespacios, identificando bases equivalentes. El objetivo de aproximar un Target depende de la base; eliminar movimientos XΩ con Ω antisimétrica rompe la retracción de Stiefel. V807 sustituye la fórmula anterior por retracción QR con diagonal positiva.

El QR Householder escalado constituye la referencia. Su tolerancia de rango es conservadora y dependiente de dimensión; no sustituye un estimador de condición ni una SVD rank-revealing. Rango cercano al umbral puede ser rechazado aunque sea algebraicamente completo. Esa decisión es explícita y preferible a devolver NaN como éxito.

## Rotación y redondeo

Con u y v ortonormales, el operador modifica su plano mediante coseno/seno y conserva su complemento. Se evalúa versin como 2 sin²(θ/2), evitando restar coseno de uno cerca de cero. Los productos escalares usan Neumaier en FP64.

La suma compensada no vuelve exactos los productos ni garantiza una cota global independiente de entradas. V807 no implementa una expansión double-double persistente ni la presunta actualización TwoSum por coordenada. Por tanto, no afirma implementar el antiguo contrato de dos pasadas ni su límite de dos ULP. Tiene un contrato numérico medible más amplio.

Los benchmarks con un estado denso y base dispersa, y los tests adicionales con base densa, son evidencia de esos casos. No demuestran error uniforme para cualquier base, ángulo, compilador o hardware. Tampoco un valor de error pequeño en una muestra es una prueba de estabilidad asintótica.

## Homología y consenso

DSU cuenta componentes. E−V+C cuenta ciclos del complejo unidimensional. No infiere caras, persistencia ni homología intrínseca de S^(D−1). Las aristas repetidas y lazos se interpretan como multigrafo, por contrato.

Una componente de proximidad no certifica acuerdo bizantino ni veracidad. El medoide extrínseco devuelve un candidato y un costo euclídeo explícito. No se denomina mediana geodésica ni detector universal de alucinaciones.

## Costos

QR y Gramiana: O(DK²), con buffers O(DK+K²). Filtro: O(n²D) y entrada O(nD), sujeto a presupuesto. DSU: O((V+E)α(V)) amortizado. LSM: O(D log D). IPC: mappings persistentes y vistas compartidas; exclusión, inicialización y validación tienen costo. Publicar dos enteros es O(1); no lo es producir o validar D escalares.

Sin mediciones de energía no se atribuye ahorro térmico cuantitativo. Sin adaptadores de modelos no se certifica interoperabilidad cognitiva. El diseño permite investigar esas hipótesis sin confundirlas con propiedades ya probadas.

Referencias primarias usadas en la auditoría original: Microsoft WaitOnAddress; Rust Reference y catch_unwind; Fukaya et al., Shifted Cholesky QR, DOI 10.1137/18M1218212. V807 usa Householder y no atribuye a su código las garantías del algoritmo shiftedCholeskyQR3.
