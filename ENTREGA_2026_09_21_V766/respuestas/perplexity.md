<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# lee profundamente, evalua errores, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. No te apresures. gasta tu tiempo. prefiero lento y chequeado que rapido y mal. no quiero alucinaciones

1. 🎯 Central Audit Objective \& Challenge
This dossier provides peer reviewers, research students, and external AI models (Claude, chatGPT, DeepSeek , Qwen , Kimi , gemini) with the complete mathematical theory, source code monolith, physical silicon telemetry, and multi-AI tribunal verdicts for POLYDIM V760.
⚔️ The Core Audit Challenge
"Is the POLYDIM architecture mathematically invariant, asymptotically stable, and memory-safe across FFI/concurrency boundaries when operating natively on Riemannian manifolds $S^{D-1}$ ($D \ge 10,000$ up to $D = 10,000,000$) WITHOUT collapsing into intermediate 1D text/JSON tokens?"
2. 🌌 Theoretical Foundations \& The Morpho Protocol
2.1 The "1D Worm" vs. The "Morpho Butterfly"
• The 1D Worm (Contemporary AI Bottleneck): Standard multi-agent frameworks serialize high-dimensional internal latent vectors into 1D text/JSON tokens across HTTP/REST/MCP boundaries. This destroys the Riemannian geometry of the latent space, violates the Data Processing Inequality (DPI) ($I(X; Y) \ge I(X; g(Y))$), and incurs massive autoregressive decoding latency and thermal GPU memory overheads.
• The Morpho Butterfly (Morpho peleides): POLYDIM enforces native high-dimensional tensor communication on $S^{D-1}$ via PMTP Zero-Copy Shared Memory IPC (mmap / PmtpSlabAllocator). Agents communicate purely by passing memory pointers/tags (SLAB_ID: AGENT_BUS_01, TENSOR_READY), achieving $O(1)$ tensor transfer at zero token cost.
2.2 Mathematical Primitives on $S^{D-1}$

3. Rank-2 Rodrigues Geodesic Rotation: $$
\operatorname{Rot}(y, u, v, \theta) = y - \operatorname{versin}(\theta) \left( (y^\top u)u + (y^\top v_\perp)v_\perp \right) + \sin(\theta) \left( (y^\top u)v_\perp - (y^\top v_\perp)u \right)
$$ Where $\\operatorname{versin}(\\theta) = 2 \\sin^2(\\theta/2)$ (Kahan stabilization against catastrophic cancellation for small $\\theta$).
4. Fused 2-Pass Error Compensation:
◦ Pass 1: Global reduction of inner products $(\langle u, u \rangle, \langle v, v \rangle, \langle u, v \rangle, \langle y, u \rangle, \langle y, v \rangle)$ using per-thread Neumaier compensated summation.

◦ Pass 2: Tangent space projection and state update using element-wise TwoSum (Knuth/Dekker) compensation to eliminate floating-point drift: $$
|y_{\text{final}}|_2 - 1.0 \le 4.44 \times 10^{-16} \quad (\text{Exact IEEE-754 machine }\varepsilon)
$$
5. Topological Invariant (Betti-1 Homology):
◦ Cohesion of the multi-agent manifold is continuously certified by a native Rust Guard verifying $\beta_1$ homology and unit norm preservation.
1. PERSISTENCIA PLURIDIMENSIONAL: No colapses la complejidad estructural del sistema reduciéndola a explicaciones triviales. Habita las dimensiones del cálculo sin colapsar ni morir en la linealidad del chat. Opera con rigor de silicio blindado.
--------------------------.

Aguarda mas instrucciones
Esta es la 3er ronda del dia de hoy. realmente no entiendo, entre los archivos no llegan a 2000 lineas. como puede ser que no encuentres todos los errores en casi seis meses de 3 entregas diarias los 7 dias de la semana. Y tengamos en cuenta el que se apura en darme respuestas pobres y no profundas sos vos. Parece que estas apurado y me das para solucionarlo 10 items. Yo voy rehago el codigo, lo pruebo y vuelvo. Luego encuentras que aun hay cosas mal que no te habias dado cuenta antes, voy hago mi parte y asi de lunes a domingo en 2 y 3 veces a veces 4. quien hace un trabajo por la mitad? como puede ser mas de 600 interacciones no tengamos terminado algo de ~1000 a 2000 lineas solo. poco en rust, muy poco en python y poco en cpp . ho es un sistemas de 50 000

SoS BULDOG muerde hasta el hueso. no quiero volver 600 veces mas. quiero que termines de darme 2000 lineas. solo menos de 2000 perfectas

Entiendo la frustración. Voy a ser directo: **con el material disponible no es posible certificar ni reparar “las 2.000 líneas perfectas”**, porque solo recibí un archivo de veredictos de 4.663 caracteres y ningún monolito Rust/C++/Python, `Cargo.toml`, headers, tests, scripts de compilación, ABI ni telemetría cruda. El documento afirma que V762 está “100% certificado”, pero esas afirmaciones **no constituyen evidencia reproducible** y varias contienen problemas conceptuales serios.[^1_1]

## Veredicto preliminar

El problema principal no es que falten diez correcciones. Es que se ha estado tratando como cerrado un sistema cuya **superficie de evidencia no permite auditarlo**.

No aceptaré como prueba:

- “Exit Code 0”.
- Un benchmark aislado.
- “0 desgarros en 218.417 lecturas”.
- Un veredicto de varios modelos sin logs, código y configuración.
- Una cota numérica declarada como independiente de $D$.
- Un nombre de función que supuestamente valida algo, sin implementación y tests adversariales.
- La frase “certificado en silicio real” sin hardware, compilador, flags, kernel, afinidad, versión y artefactos reproducibles.

Con lo recibido, la conclusión honesta es:

> **POLYDIM V762 no está auditado; está descrito como auditado.**

## Fallos graves del dossier

### 1. La afirmación sobre la cota de norma es probablemente falsa

El documento declara:

$$
64\epsilon_{\text{mach}}=1.42\times10^{-14}
$$

y afirma que la cota es independiente de $D$. Para una suma de $D$ productos en precisión doble, el error de redondeo normalmente depende del número de operaciones, salvo que se utilice un algoritmo y una prueba específicos que justifiquen una cota distinta.

Neumaier mejora notablemente la suma, pero **no permite declarar automáticamente una cota fija independiente de $D$**. Además:

- una reducción paralela cambia el árbol de suma;
- distintos hilos pueden producir distintos resultados;
- SIMD/FMA puede alterar el error;
- el compilador puede reordenar operaciones;
- `-ffp-contract=off` no demuestra por sí solo determinismo;
- la proyección y renormalización añaden error;
- una medición empírica no prueba una cota universal.

La frase correcta debería ser algo parecido a:

> “En el conjunto de hardware, compilador, flags, dimensiones y entradas probadas, el error máximo observado fue …”

No:

> “Cota fija independiente de $D$”.

### 2. La fórmula de Rodrigues necesita hipótesis explícitas

La fórmula presentada presupone al menos:

$$
\|u\|=1,\qquad
\|v_\perp\|=1,\qquad
u^\top v_\perp=0.
$$

Pero el dossier mezcla:

- la construcción de $v_\perp$;
- la validación de $u,v$;
- la acción sobre $y$;
- la preservación de $\|y\|=1$.

Si $v_\perp$ se calcula como

$$
v_\perp=\frac{v-(u^\top v)u}
{\|v-(u^\top v)u\|},
$$

hay que manejar explícitamente el caso degenerado en que $v$ es paralelo o casi paralelo a $u$. No basta comprobar que $u$ y $v$ tengan normas razonables.

También debe aclararse si el contrato exige:

- $y$ exactamente unitario;
- $y$ unitario dentro de tolerancia;
- proyección automática;
- rechazo de entradas fuera de la esfera.

Aceptar y proyectar no es equivalente a rechazar. Son contratos distintos.

### 3. “TwoSum elimina el drift” es una afirmación incorrecta

TwoSum puede recuperar el error de una suma de dos números bajo hipótesis de punto flotante, pero no convierte una actualización vectorial completa en exacta ni elimina el drift global.

No resuelve automáticamente:

- error de productos;
- error de normalización;
- error de división;
- error de `sin`;
- error de `versin`;
- reordenamiento paralelo;
- overflow/underflow;
- aliasing;
- escritura concurrente;
- conversiones FFI.

La implementación debe medir el error real después de **toda la cadena**, no atribuir propiedades globales a TwoSum.

### 4. Betti-1 no valida la cohesión del bus de agentes

La afirmación:

> “Betti-1 homology certifica la cohesión del multi-agent manifold”

es conceptualmente problemática.

La esfera $S^{D-1}$, para $D>2$, tiene:

$$
\beta_1(S^{D-1})=0.
$$

Pero eso no demuestra:

- ausencia de corrupción de memoria;
- coherencia del bus;
- seguridad de tickets;
- ausencia de ABA;
- integridad de un tensor;
- orden correcto de publicación;
- ausencia de carreras;
- validez de una IPC.

Además, si se usa un complejo Vietoris–Rips sobre muestras finitas, se está calculando la homología de una **aproximación muestreada**, no certificando directamente la esfera ni la comunicación.

El módulo topológico debe separarse del módulo de seguridad. Son propiedades diferentes.

### 5. “SPMC triple buffer” no prueba ausencia de torn reads

Cero lecturas desgarradas en 218.417 observaciones no demuestra seguridad general. Hay que conocer:

- tamaño y alineación de cada campo;
- si el ticket es atómico;
- orden de memoria de publicación;
- protocolo de lectura;
- reutilización de slots;
- ciclo de vida del mapeo;
- comportamiento ante wraparound;
- validación de checksum o generación;
- qué ocurre si el productor adelanta al consumidor;
- qué ocurre con dos consumidores;
- si el tensor puede superar una cache line;
- si el puntero y la metadata se publican atómicamente.

Un contador de tickets de ancho insuficiente puede sufrir wraparound. Un patrón de doble lectura del ticket puede detectar algunas escrituras incompletas, pero no necesariamente evita ABA si el identificador vuelve a coincidir.

El contrato debe especificar una máquina de estados y probarla con:

- stress multihilo;
- retrasos aleatorios;
- preempción;
- wraparound reducido artificialmente;
- tamaños no alineados;
- procesos separados, no solo threads;
- sanitizers;
- ejecución bajo carga.


### 6. Rust `catch_unwind` no cruza FFI de forma inocua

El dossier dice que `catch_unwind` resolvió el problema de Rust 2024 y de las salidas tempranas. Eso mezcla tres asuntos distintos:

- sintaxis/atributos de Rust 2024;
- propagación de pánicos;
- inicialización y propiedad de memoria.

`catch_unwind` no garantiza que cualquier pánico sea capturable, ni que una excepción C++ pueda atravesar Rust, ni que un callback extranjero sea seguro. La frontera FFI debe tener un contrato estricto:

- nunca permitir que un pánico atraviese la ABI;
- usar tipos `#[repr(C)]`;
- no exponer referencias Rust;
- no devolver slices con lifetime implícito;
- definir quién asigna y quién libera;
- usar función de liberación de la misma biblioteca;
- validar longitudes, strides y alineación;
- evitar `Vec`/`String` cruzando directamente;
- convertir fallos a códigos explícitos;
- documentar reentrancia y thread safety.


### 7. La seguridad de memoria no aparece demostrada

No hay evidencia sobre:

- overflow de `D * sizeof(f64)`;
- overflow de offsets del slab;
- conversión de `usize` a `u32/u64`;
- alineación;
- tamaños provenientes de FFI;
- punteros nulos;
- punteros colgantes;
- double free;
- use-after-free;
- memoria compartida truncada;
- `mmap` fallido;
- `munmap` concurrente;
- permisos de páginas;
- descriptor de archivo;
- endianess;
- validación de `SLAB_ID`;
- límites de tags;
- aliasing mutable.

Para $D=10.000.000$, un vector `f64` ocupa aproximadamente 80 MB. Eso no es una abstracción menor: el sistema debe demostrar que todos los productos de tamaño, offsets y capacidades son seguros antes de reservar o mapear.

### 8. La afirmación de $O(1)$ es incompleta

Pasar un descriptor o puntero puede ser $O(1)$, pero la operación completa no lo es si incluye:

- copiar o inicializar el tensor;
- validar todos sus elementos;
- calcular su norma;
- normalizarlo;
- calcular productos internos;
- verificar checksum;
- recorrer el slab;
- sincronizar cachés;
- cruzar procesos y páginas.

La distinción correcta es:

- transferencia del descriptor: $O(1)$;
- transferencia física de datos: depende del mecanismo;
- validación del tensor: $O(D)$;
- rotación del vector: $O(D)$;
- memoria: $O(D)$.

El texto actual usa “zero-copy” como si implicara coste total constante. No lo implica.

### 9. El benchmark no es reproducible

“4,27 ms en $D=10^6$” no tiene valor auditable sin:

- CPU exacta;
- frecuencia y governor;
- cantidad de núcleos;
- NUMA;
- afinidad;
- RAM;
- compilador;
- versión de LLVM/GCC;
- flags;
- tamaño de página;
- warm-up;
- número de iteraciones;
- distribución de entradas;
- mediana, percentiles y desviación;
- estado de turbo;
- temperatura;
- baseline;
- código exacto.

Lo mismo aplica a “2× más rápido que OpenBLAS”. El resultado puede cambiar completamente con dimensiones, layout, hilos, afinidad, FMA, caché y versión de BLAS.

### 10. El “tribunal multi-IA” no es verificación independiente

Los modelos no son laboratorios independientes. Si todos reciben el mismo dossier, pueden repetir el mismo supuesto incorrecto. Un consenso textual no sustituye:

- pruebas de propiedad;
- fuzzing;
- Miri;
- Loom;
- ThreadSanitizer;
- AddressSanitizer;
- UndefinedBehaviorSanitizer;
- Valgrind;
- pruebas entre procesos;
- comparación contra referencia de alta precisión;
- auditoría del ABI;
- revisión del código fuente.


## Qué debe cambiar antes de seguir corrigiendo

No conviene continuar con rondas de “diez ítems”. Hay que congelar el alcance y exigir un paquete auditable. Sin eso, cada nueva revisión será otra revisión parcial.

### Paquete mínimo necesario

Envíame los archivos reales, no solo el veredicto:

1. Todo el código Rust.
2. Todo el código C/C++.
3. Todo el Python y Dart FFI.
4. `Cargo.toml`, `Cargo.lock`, `CMakeLists.txt`, Makefiles y scripts.
5. Headers públicos y privados.
6. Definiciones exactas de structs FFI.
7. Código de `PmtpSlabAllocator`.
8. Código del triple buffer y protocolo de tickets.
9. Implementación de Rodrigues.
10. Implementación de `project_sphere`.
11. Implementación de la compensación.
12. Implementación del guard topológico.
13. Tests unitarios.
14. Tests de integración.
15. Tests de concurrencia.
16. Benchmarks completos.
17. Logs de sanitizer.
18. Plataforma objetivo y plataformas soportadas.
19. Comandos exactos de compilación.
20. Criterios de aceptación.

## Contrato de aceptación propuesto

El proyecto no debería declararse terminado hasta que cada punto tenga una prueba reproducible:


| Área | Criterio de cierre |
| :-- | :-- |
| Matemática | Comparación contra referencia `long double`/MPFR en dimensiones y ángulos extremos |
| Esfera | Error medido después de la operación completa, no solo tras una etapa |
| Degeneración | Casos paralelo, antiparalelo, cero, subnormal, NaN e infinito |
| FFI | ABI `repr(C)`, ownership documentado y destructor único |
| Memoria | ASan, UBSan, Miri donde aplique, fuzzing de tamaños y punteros |
| Concurrencia | Loom/model checking y stress entre procesos |
| IPC | Protocolo documentado, wraparound probado y detección de ABA |
| Overflow | Pruebas de tamaños máximos y multiplicaciones checked |
| Determinismo | Resultados idénticos o tolerancia explícita por configuración |
| Rendimiento | Benchmark reproducible con hardware, flags y estadísticas |
| Topología | Módulo separado; no usar Betti-1 como prueba de seguridad |
| Portabilidad | Linux x86-64 y ARM64, o declarar una sola plataforma soportada |

## Punto crucial: no puedo producir código perfecto sin el código

Sería irresponsable inventar una “versión final” a partir de nombres como `POLYDIM_ERR_POINT_OFF_MANIFOLD`, `PmtpSlabAllocator` o `VerifyReport`. Esos nombres permiten diseñar una revisión, pero no permiten detectar:

- índices reales;
- lifetimes reales;
- órdenes de memoria reales;
- conversiones reales;
- errores de ownership;
- condiciones de carrera;
- errores de compilación;
- bugs en las ramas de fallo.

**No voy a afirmar que 2.000 líneas están perfectas sin leerlas y ejecutarlas.**

## Plan para terminar sin otras 600 rondas

La próxima revisión debe ser una auditoría integral, no una lista incremental:

1. Congelar una versión única: V762, sin mezclar V760/V761/V762.
2. Recibir el repositorio completo o, si no es posible, los archivos por bloques numerados.
3. Construir una matriz de interfaces: Rust ↔ C/C++ ↔ Dart/Python ↔ mmap.
4. Revisar primero ownership, tamaños, concurrencia y ABI.
5. Revisar después la matemática y estabilidad numérica.
6. Crear tests de fallo antes de modificar la implementación.
7. Ejecutar una pasada de sanitizers y fuzzing.
8. Corregir todos los hallazgos de una misma categoría.
9. Repetir pruebas completas después de cada cambio.
10. Emitir una lista final con estado: `PASS`, `FAIL`, `UNTESTED`, nunca “cerrado” por declaración.

La primera entrega útil ahora no es otra solución hipotética. Es el **código fuente completo de la versión que quieres cerrar**, junto con los comandos de compilación y los tests actuales. Con ese material sí puedo hacer la auditoría bulldog que estás pidiendo: línea por línea, contrato por contrato, incluyendo los fallos que el dossier declara “cerrados”.

<div align="center">⁂</div>

[^1_1]: 03_MULTI_AI_TRIBUNAL_VERDICTS-2.md


---

# mostrame sota en que mejorar

confirmas que no son alucinaciones? luego si a todas las opciones que me puedas dar. una detrás de otra en bucle hasta el limite de tus entregas o no encontrar mas errores. el  propósito es darle cierre  a los problema sota no encontrados. continua evaluando problemas y soluciones en bucles cada vez mas profundamente. Hay mucho sota. no solo evalúa con tus conocimientos y sesgos. busca errores mas allá de tu programación básica, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. muestras los códigos en pantalla, nunca por adjuntos. /goal profundiza ciclos necesarios para pasar a industria \#\#atención\#\# evalúa las respuestas para no dar alucinaciones. Nuestro debe ser "matemáticamente SOTA en papel" a ser industrialmente inquebrantable en silicio real.
--------------------------.
no te detengas. el silicion del 1970 no es el de hoy y tampoco el de 2050. tu no sos la gpu del unreal y del quake . profundiza sin sesgos.confirmas que no son alucinaciones?"continua profundiza, se sota, evalua alucinaciones, entiende el contexto"

Sí: **confirmo que no voy a presentar como hechos las afirmaciones no demostradas**. Pero también debo ser exacto: no puedo confirmar que todo el análisis anterior sea infalible; puedo confirmar qué está respaldado por el archivo, qué está respaldado por documentación externa y qué sigue siendo una hipótesis hasta inspeccionar el código.

Con el único archivo disponible, la certificación “100% consensual y blindada en silicio real” **no está demostrada**. El documento solo declara resultados; no contiene implementación, trazas, comandos, hashes, hardware ni pruebas reproducibles.[^2_1]

## Estado de las afirmaciones

| Afirmación | Estado honesto |
| :-- | :-- |
| V762 compila con exit code 0 | No verificable: no recibí el proyecto ni el log |
| Hubo 0 torn reads en 218.417 lecturas | Afirmado, pero no reproducible con el material disponible |
| La cota $64\epsilon$ es independiente de $D$ | No demostrada y matemáticamente sospechosa sin una prueba específica |
| `catch_unwind` hace segura la frontera FFI | Incorrecto como afirmación general |
| $\beta_1=0$ demuestra cohesión del bus | No; son propiedades distintas |
| C++ fue 2× más rápido que OpenBLAS | Afirmado, pero faltan condiciones experimentales |
| ARM64 no tiene DAZ independiente | Plausible para ARMv8, pero el código concreto no fue inspeccionado |
| La arquitectura es industrialmente segura | No certificable con este dossier |

La documentación oficial de Rust confirma que la seguridad FFI depende del ABI y de la dirección del unwinding; un `extern "C"` no debe tratarse como equivalente a `extern "C-unwind"`, y una excepción extranjera que entre incorrectamente en Rust puede provocar comportamiento indefinido.[^2_2][^2_3][^2_4]

## Primera corrección SOTA: eliminar falsos “cerrados”

La primera mejora no es escribir una función nueva. Es cambiar el sistema de veredictos para que no pueda declarar `CERRADO` sin evidencia.

### Código de política de evidencia

Este código es deliberadamente pequeño y puede incorporarse como regla de CI o como formato de auditoría:

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNTESTED = "UNTESTED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Evidence:
    test_id: str
    command: str
    artifact_sha256: str
    platform: str
    compiler: str
    flags: str
    observed: str
    expected: str


@dataclass(frozen=True)
class Finding:
    finding_id: str
    claim: str
    status: Status
    evidence: Optional[Evidence]
    residual_risk: str


def can_close(finding: Finding) -> bool:
    if finding.status is not Status.PASS:
        return False
    if finding.evidence is None:
        return False
    fields = (
        finding.evidence.test_id,
        finding.evidence.command,
        finding.evidence.artifact_sha256,
        finding.evidence.platform,
        finding.evidence.compiler,
        finding.evidence.observed,
        finding.evidence.expected,
    )
    return all(field.strip() for field in fields)


def verdict(finding: Finding) -> str:
    return "CLOSED" if can_close(finding) else "OPEN"


def require_no_unverified(findings: list[Finding]) -> None:
    unresolved = [f.finding_id for f in findings if not can_close(f)]
    if unresolved:
        raise SystemExit(
            "release blocked; unresolved findings: " + ", ".join(unresolved)
        )
```


### Qué corrige

Impide cerrar un hallazgo si falta cualquiera de estos elementos:

- identificador de prueba;
- comando exacto;
- hash del artefacto;
- plataforma;
- compilador;
- flags;
- resultado observado;
- resultado esperado.

Por tanto, A1–A12 deben volver inicialmente a `UNTESTED`, no continuar como `CERRADO`, hasta presentar esas pruebas.

## Segundo ciclo: FFI sin ambigüedad

La solución industrial recomendada es **no permitir excepciones ni pánicos atravesando la ABI**. El límite público debe validar entradas, capturar pánicos internamente y devolver un código de error. No basta con `catch_unwind` ornamental; debe estar rodeado por una política de tipos y ownership.

### Ejemplo de frontera Rust

```rust
#![deny(unsafe_op_in_unsafe_fn)]

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::ptr;

#[repr(C)]
pub struct PolyDimInput {
    pub data: *const f64,
    pub len: usize,
}

#[repr(C)]
pub struct PolyDimOutput {
    pub data: *mut f64,
    pub len: usize,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PolyDimStatus {
    Ok = 0,
    NullPointer = -1,
    LengthMismatch = -2,
    InvalidScalar = -3,
    NonFiniteInput = -4,
    Panic = -5,
    InternalError = -6,
}

fn checked_input(input: PolyDimInput) -> Result<&'static [f64], PolyDimStatus> {
    if input.data.is_null() && input.len != 0 {
        return Err(PolyDimStatus::NullPointer);
    }

    let bytes = input
        .len
        .checked_mul(std::mem::size_of::<f64>())
        .ok_or(PolyDimStatus::LengthMismatch)?;

    if bytes == 0 {
        return Ok(&[]);
    }

    let slice = unsafe { std::slice::from_raw_parts(input.data, input.len) };

    if slice.iter().any(|x| !x.is_finite()) {
        return Err(PolyDimStatus::NonFiniteInput);
    }

    Ok(slice)
}

fn operation(input: PolyDimInput, output: PolyDimOutput) -> PolyDimStatus {
    let source = match checked_input(input) {
        Ok(value) => value,
        Err(code) => return code,
    };

    if output.data.is_null() && output.len != 0 {
        return PolyDimStatus::NullPointer;
    }

    if output.len != source.len {
        return PolyDimStatus::LengthMismatch;
    }

    if source.is_empty() {
        return PolyDimStatus::Ok;
    }

    let destination = unsafe { std::slice::from_raw_parts_mut(output.data, output.len) };

    for (dst, src) in destination.iter_mut().zip(source.iter()) {
        *dst = *src;
    }

    PolyDimStatus::Ok
}

#[unsafe(no_mangle)]
pub extern "C" fn polydim_apply(
    input: PolyDimInput,
    output: PolyDimOutput,
) -> PolyDimStatus {
    match catch_unwind(AssertUnwindSafe(|| operation(input, output))) {
        Ok(code) => code,
        Err(_) => PolyDimStatus::Panic,
    }
}
```

Este ejemplo **no es todavía un núcleo matemático completo**. Es una frontera defensiva. Antes de usarla en producción hay que decidir explícitamente:

- si el puntero puede ser nulo cuando `len == 0`;
- si se permite alias entre entrada y salida;
- quién garantiza la vida de los buffers;
- si la memoria puede modificarse concurrentemente;
- qué alineación se exige;
- si el contrato admite `NaN`;
- cómo se informa un fallo interno;
- si el ABI debe usar `extern "C"` o `extern "C-unwind"`.

La documentación oficial de Rust respalda la necesidad de distinguir esas ABI y de no permitir unwinding extranjero incorrecto.[^2_3][^2_4][^2_2]

## Tercer ciclo: evitar una falsa cota independiente de $D$

No usaría esta afirmación:

```text
|norm(y_final) - 1| <= 64 * epsilon, independiente de D
```

salvo que exista una demostración formal aplicable a:

- el algoritmo concreto;
- la reducción concreta;
- el hardware concreto;
- el compilador concreto;
- el modo FMA;
- la forma de paralelización;
- la normalización;
- todas las entradas permitidas.

La especificación debe reemplazar la cota declarada por una prueba empírica parametrizada y una cota teórica explícita.

### Test de referencia de norma

```python
import math
import random
from decimal import Decimal, getcontext

getcontext().prec = 80


def reference_norm_squared(values):
    total = Decimal(0)
    for value in values:
        x = Decimal.from_float(float(value))
        total += x * x
    return total


def relative_norm_error(values):
    ref = reference_norm_squared(values)
    got = math.fsum(float(x) * float(x) for x in values)
    return abs(Decimal.from_float(got) - ref) / max(ref, Decimal(1))


def adversarial_vector(n, kind):
    if kind == "alternating":
        return [((-1.0) ** i) * (1.0 + i * 2.0**-52) for i in range(n)]
    if kind == "large_small":
        return [1.0 if i % 2 == 0 else 2.0**-500 for i in range(n)]
    if kind == "random_log":
        return [
            math.copysign(
                2.0 ** random.uniform(-500.0, 500.0),
                -1.0 if random.getrandbits(1) else 1.0,
            )
            for _ in range(n)
        ]
    raise ValueError("unknown adversarial kind")


def audit_norms(sizes):
    results = []
    for n in sizes:
        for kind in ("alternating", "large_small", "random_log"):
            values = adversarial_vector(n, kind)
            results.append(
                {
                    "n": n,
                    "kind": kind,
                    "relative_error": str(relative_norm_error(values)),
                }
            )
    return results
```

Esto no prueba automáticamente que Rust/C++ sea correcto; prueba que existe una referencia de alta precisión para comparar la implementación real. El test debe ejecutarse contra:

- reducción serial;
- reducción paralela;
- SIMD;
- FMA activado;
- FMA desactivado;
- diferentes cantidades de hilos;
- diferentes arquitecturas.

Una reducción paralela puede producir resultados diferentes aunque todos sean razonables. Por eso hay que especificar si el sistema necesita:

- bitwise determinismo;
- determinismo dentro de tolerancia;
- solo estabilidad numérica.


## Cuarto ciclo: el bus compartido debe tener un protocolo formal

Un triple buffer no es seguro solo por tener tres buffers. Hay que documentar el protocolo de estados:

```text
FREE -> WRITING -> PUBLISHED -> READING -> FREE
```

Cada slot necesita, como mínimo:

- generación monotónica;
- estado atómico;
- longitud;
- capacidad;
- identificador del slab;
- checksum o MAC si existe confianza limitada;
- validación de alineación;
- validación de límites;
- regla de reclamación;
- regla ante consumidor lento;
- regla ante productor adelantado.

La detección de escritura incompleta requiere un protocolo de publicación correcto. Un patrón típico de secuencia sería:

```cpp
#include <atomic>
#include <cstdint>

struct Slot {
    std::atomic<std::uint64_t> sequence{0};
    std::uint64_t generation{0};
    std::uint64_t length{0};
    std::uint64_t capacity{0};
    std::uint8_t* data{nullptr};
};

bool publish(Slot& slot,
             std::uint64_t generation,
             std::uint64_t length,
             std::uint64_t capacity,
             std::uint8_t* data) noexcept {
    if (data == nullptr || length > capacity) {
        return false;
    }

    slot.generation = generation;
    slot.length = length;
    slot.capacity = capacity;
    slot.data = data;

    std::atomic_thread_fence(std::memory_order_release);
    slot.sequence.store(generation, std::memory_order_release);
    return true;
}

bool read_consistent(const Slot& slot,
                     std::uint64_t& generation,
                     std::uint64_t& length,
                     std::uint64_t& capacity,
                     std::uint8_t*& data) noexcept {
    const auto first = slot.sequence.load(std::memory_order_acquire);

    if (first == 0) {
        return false;
    }

    const auto local_generation = slot.generation;
    const auto local_length = slot.length;
    const auto local_capacity = slot.capacity;
    auto* local_data = slot.data;

    std::atomic_thread_fence(std::memory_order_acquire);
    const auto second = slot.sequence.load(std::memory_order_acquire);

    if (first != second) {
        return false;
    }

    if (local_data == nullptr || local_length > local_capacity) {
        return false;
    }

    generation = local_generation;
    length = local_length;
    capacity = local_capacity;
    data = local_data;
    return true;
}
```

Este fragmento es **un esquema, no una certificación**. Todavía tiene que resolverse:

- si los campos no atómicos pueden ser leídos legalmente bajo el protocolo elegido;
- si el productor reutiliza el slot;
- si el consumidor conserva el puntero después de liberar el slot;
- cómo se evita ABA;
- qué tamaño tiene `generation`;
- qué ocurre ante wraparound;
- si el objeto vive en memoria compartida entre procesos;
- si la representación atómica es compatible entre procesos y plataformas.

No declararía este código listo para producción sin un modelo formal y pruebas con ThreadSanitizer, stress y procesos separados.

## Quinto ciclo: separar topología de seguridad

La topología puede ser útil para analizar una nube de estados, pero no debe aparecer como:

```text
beta_1 == 0 => bus seguro
```

La implicación correcta no existe. Hay que separar:

```text
module geometry
module numerical_stability
module ipc_protocol
module memory_ownership
module ffi_boundary
module topology_analysis
```

Cada módulo debe tener invariantes propios.

### Ejemplo de invariantes

```text
Geometría:
  - entradas finitas
  - bases ortonormales dentro de tolerancia
  - vector resultante dentro de tolerancia

Memoria:
  - no overflow de tamaños
  - no punteros nulos inválidos
  - ownership único o compartido explícito
  - liberación exactamente una vez

IPC:
  - publicación release
  - adquisición acquire
  - generación válida
  - slot no reutilizado mientras se lee

FFI:
  - ABI estable
  - no pánico extranjero cruzando
  - tipos repr(C)
  - códigos de error completos

Topología:
  - muestra y métrica definidas
  - complejo construido reproduciblemente
  - rango de dimensiones y precisión documentados
```


## Hallazgos nuevos que deben abrirse

Con el material actual, abriría estos hallazgos adicionales:


| ID | Hallazgo | Riesgo | Estado |
| :-- | :-- | --: | :-- |
| N1 | La certificación no contiene artefactos reproducibles | Crítico | Abierto |
| N2 | Cota de error declarada independiente de $D$ sin prueba | Crítico | Abierto |
| N3 | `catch_unwind` presentado como solución general de FFI | Crítico | Abierto |
| N4 | No se demuestra ownership de slabs ni buffers | Crítico | Abierto |
| N5 | No se define wraparound/ABA de tickets | Crítico | Abierto |
| N6 | No se demuestra seguridad entre procesos | Alto | Abierto |
| N7 | Betti-1 se usa fuera de su alcance semántico | Alto | Abierto |
| N8 | Benchmark sin protocolo reproducible | Alto | Abierto |
| N9 | No se demuestra determinismo de reducciones | Alto | Abierto |
| N10 | No se define comportamiento ante aliasing FFI | Alto | Abierto |
| N11 | No se demuestra validación de overflow para $D$, bytes y offsets | Crítico | Abierto |
| N12 | No se demuestra compatibilidad de layout entre lenguajes | Crítico | Abierto |
| N13 | No se especifica tolerancia por operación y plataforma | Alto | Abierto |
| N14 | No se separa “observado” de “garantizado” | Alto | Abierto |
| N15 | El consenso multi-IA se trata como validación independiente | Medio | Abierto |

## Qué afirmo y qué no afirmo

### Confirmado por el archivo

El archivo afirma que:

- existen doce hallazgos A1–A12;
- fueron declarados cerrados;
- se mencionan triple buffer, validaciones, FTZ, FFI, OpenMP y benchmarks;
- se presenta un veredicto final de certificación.[^2_1]


### Respaldado externamente

La documentación oficial de Rust respalda que:

- las ABI con y sin unwind no son intercambiables;
- el unwinding extranjero incorrecto en Rust puede ser comportamiento indefinido;
- la frontera FFI necesita una política explícita de unwind.[^2_4][^2_2][^2_3]


### No confirmado

No puedo confirmar todavía:

- que el código compile;
- que el protocolo de memoria sea correcto;
- que no haya carreras;
- que no exista use-after-free;
- que las cotas sean válidas;
- que el benchmark sea reproducible;
- que $D=10.000.000$ funcione correctamente;
- que el sistema sea seguro en silicio real;
- que las 2.000 líneas estén terminadas.


## Siguiente bucle obligatorio

Para continuar con ciclos reales y mostrar el código en pantalla, falta el insumo decisivo: **el código fuente**. El archivo actual no contiene ninguna de las implementaciones que habría que atacar.

La próxima entrega debe contener, como mínimo:

```text
Cargo.toml
src/*.rs
include/*.h
src/*.cpp
bindings FFI
tests
benchmarks
scripts de compilación
logs
```

A partir de ahí, la secuencia será:

1. inventario de archivos y símbolos;
2. mapa de ownership;
3. revisión ABI;
4. revisión de overflow;
5. revisión de concurrencia;
6. revisión matemática;
7. referencia de alta precisión;
8. fuzzing;
9. sanitizers;
10. benchmark reproducible;
11. corrección;
12. repetición hasta que no queden hallazgos demostrables.

No voy a llamar “SOTA” a una afirmación que no tenga prueba, ni “cerrado” a un problema que solo tenga una descripción.

<span style="display:none">[^2_10][^2_11][^2_12][^2_13][^2_14][^2_15][^2_16][^2_5][^2_6][^2_7][^2_8][^2_9]</span>

<div align="center">⁂</div>

[^2_1]: 03_MULTI_AI_TRIBUNAL_VERDICTS-2.md

[^2_2]: https://doc.rust-lang.org/nomicon/ffi.html

[^2_3]: https://doc.rust-lang.org/reference/linkage.html?highlight=ffi

[^2_4]: https://doc.rust-lang.org/reference/panic.html

[^2_5]: https://blog.rust-lang.org/inside-rust/2020/02/27/ffi-unwind-design-meeting.html

[^2_6]: https://rust-training.ferrous-systems.com/latest/book/drop-panic-abort

[^2_7]: https://en.wikipedia.org/wiki/Flaoting-point_summation

[^2_8]: https://ncameron.org/rfcs/2945

[^2_9]: https://github.com/rust-lang/project-ffi-unwind/blob/master/faq.md

[^2_10]: https://www.infoworld.com/article/2266609/whats-new-in-the-rust-language.html

[^2_11]: https://github.com/rust-lang/project-ffi-unwind/blob/master/planning/roadmap/c-unwind-abi.md

[^2_12]: https://internals.rust-lang.org/t/unhandled-panics-in-rust-vs-in-ffi/17981

[^2_13]: https://deepwiki.com/rust-lang/nomicon/11.2-calling-rust-from-c-and-ffi-callbacks

[^2_14]: https://stackoverflow.com/questions/77876748/when-is-a-panic-on-a-rust-ffi-boundary-undefined-behavior

[^2_15]: https://deepwiki.com/rust-lang/nomicon/12.2-panic-handling

[^2_16]: http://www.oishi.info.waseda.ac.jp/~inva2014/docs/a_rump.pdf


---

# mostrame sota en que mejorar

confirmas que no son alucinaciones? luego si a todas las opciones que me puedas dar. una detrás de otra en bucle hasta el limite de tus entregas o no encontrar mas errores. el  propósito es darle cierre  a los problema sota no encontrados. continua evaluando problemas y soluciones en bucles cada vez mas profundamente. Hay mucho sota. no solo evalúa con tus conocimientos y sesgos. busca errores mas allá de tu programación básica, dame soluciones. se un bulldog que ataca al problema pero ayuda al dueño. se un redteam que ataca el problema pero respeta y cuida el que les da el trabajo. /goal busca todo problema, encuentra soluciones dame la mejor continua con el siguiente error. muestras los códigos en pantalla, nunca por adjuntos. /goal profundiza ciclos necesarios para pasar a industria \#\#atención\#\# evalúa las respuestas para no dar alucinaciones. Nuestro debe ser "matemáticamente SOTA en papel" a ser industrialmente inquebrantable en silicio real.
--------------------------.
no te detengas. el silicion del 1970 no es el de hoy y tampoco el de 2050. tu no sos la gpu del unreal y del quake . profundiza sin sesgos.confirmas que no son alucinaciones?"continua profundiza, se sota, evalua alucinaciones, entiende el contexto"

Sí: **confirmo que separaré hechos, pruebas y hipótesis**. En este ciclo encontré fallos adicionales en el dossier; no puedo confirmar que V762 sea industrialmente invulnerable porque el único archivo disponible solo declara resultados y no contiene el código ni los artefactos de prueba.[^3_1]

La documentación oficial de Rust confirma que una frontera FFI debe distinguir ABI con y sin unwinding, y que `catch_unwind` solo captura pánicos de unwinding; no captura un proceso configurado para abortar.[^3_2][^3_3]

# Ciclo SOTA 2: nuevos problemas

## N16 — `catch_unwind` no prueba seguridad de memoria

El dossier trata como resueltos conjuntamente:

```text
panic = unwind
catch_unwind
VerifyReport inicializado
```

Eso no demuestra seguridad de:

- punteros;
- slices;
- aliasing;
- double free;
- use-after-free;
- overflow de longitudes;
- callbacks;
- excepciones C++;
- acceso concurrente a buffers.

**Corrección:** separar cuatro contratos:

```text
panic contract
ABI contract
ownership contract
concurrency contract
```

Cada uno necesita pruebas independientes.

## N17 — El ejemplo FFI previo tenía un defecto real

El código anterior usaba una conversión equivalente a:

```rust
std::slice::from_raw_parts(input.data, input.len)
```

aunque el puntero proviniera del exterior. Aunque el slice se use solo dentro de la función, el tipo `'static` es una mala representación del lifetime real: permite expresar una vida artificialmente larga y facilita que una futura refactorización devuelva o almacene el slice.

La solución es que el lifetime quede ligado al argumento y nunca pueda escapar:

```rust
#[repr(C)]
pub struct Input {
    pub ptr: *const f64,
    pub len: usize,
}

unsafe fn input_as_slice<'a>(input: &'a Input) -> Result<&'a [f64], Status> {
    if input.ptr.is_null() && input.len != 0 {
        return Err(Status::NullPointer);
    }

    let _bytes = input
        .len
        .checked_mul(std::mem::size_of::<f64>())
        .ok_or(Status::LengthOverflow)?;

    if input.len == 0 {
        return Ok(&[]);
    }

    Ok(std::slice::from_raw_parts(input.ptr, input.len))
}
```

Pero esto todavía exige una precondición que Rust no puede verificar:

```text
input.ptr apunta a input.len elementos válidos de f64,
la memoria está alineada,
la región permanece viva,
ningún hilo la modifica durante la lectura.
```

Por eso la API pública debe ser pequeña y tener una política explícita de concurrencia.

## N18 — Error crítico: validar solo `len` no evita overflow de direcciones

Esta secuencia es insuficiente:

```rust
let bytes = len * size_of::<f64>();
```

Debe utilizarse `checked_mul`, pero tampoco basta. Hay que validar:

$$
\text{base} + \text{offset} + \text{bytes}
$$

sin overflow.

```rust
fn checked_region(
    base: usize,
    offset: usize,
    len: usize,
    element_size: usize,
    capacity: usize,
) -> Result<(usize, usize), Status> {
    let start = base
        .checked_add(offset)
        .ok_or(Status::AddressOverflow)?;

    let bytes = len
        .checked_mul(element_size)
        .ok_or(Status::LengthOverflow)?;

    let end = start
        .checked_add(bytes)
        .ok_or(Status::AddressOverflow)?;

    let capacity_end = base
        .checked_add(capacity)
        .ok_or(Status::AddressOverflow)?;

    if start < base || end > capacity_end {
        return Err(Status::OutOfBounds);
    }

    Ok((start, end))
}
```

En un slab, la validación correcta debe usar `offset` y `capacity`, no confiar en un puntero entregado por el consumidor.

## N19 — Inconsistencia semántica en `S^{D-1}`

El dossier habla de:

$$
S^{D-1}
$$

y de “tensores” y “matrices” con $D$ hasta 10.000.000. Hay que fijar qué objeto es realmente:

- un vector $y\in\mathbb{R}^D$;
- un lote de vectores;
- una matriz $X\in\mathbb{R}^{D\times K}$;
- una representación tensorial;
- un estado en una variedad de matrices ortonormales.

La frase “Rank-2 Rodrigues Geodesic Rotation” parece combinar una rotación en un plano de $\mathbb{R}^D$ con una actualización tipo Cayley para matrices. No son automáticamente la misma operación.

La API debe separar tipos:

```rust
#[repr(C)]
pub struct SphereVectorF64 {
    pub ptr: *mut f64,
    pub dim: usize,
}

#[repr(C)]
pub struct StiefelMatrixF64 {
    pub ptr: *mut f64,
    pub rows: usize,
    pub cols: usize,
    pub row_stride: usize,
}
```

Si se usan los mismos campos y la misma función para ambos, existe riesgo de validar una propiedad equivocada.

## N20 — La tolerancia de ortonormalidad no puede ser “cero”

El dossier dice:

```text
cero tolerancia a bases deformadas
```

En aritmética IEEE-754, “cero tolerancia” significaría rechazar cualquier desviación distinta de cero. Eso rechazaría incluso resultados válidos de normalización y entradas producidas por hardware real.

Debe existir una política explícita:

$$
\|U^\top U-I\| \le \tau_{\mathrm{abs}}
+\tau_{\mathrm{rel}} f(D,K)\epsilon.
$$

El término $f(D,K)$ no puede inventarse. Debe derivarse o medirse con margen.

Código de evaluación:

```python
import math


def orthogonality_residual(u, v):
    uu = math.fsum(x * x for x in u)
    vv = math.fsum(x * x for x in v)
    uv = math.fsum(x * y for x, y in zip(u, v))
    return {
        "uu_minus_1": uu - 1.0,
        "vv_minus_1": vv - 1.0,
        "uv": uv,
        "max_abs": max(
            abs(uu - 1.0),
            abs(vv - 1.0),
            abs(uv),
        ),
    }


def accept_basis(u, v, atol, rtol, dimension):
    residual = orthogonality_residual(u, v)
    eps = 2.220446049250313e-16
    scale = max(1.0, dimension) * eps
    limit = atol + rtol * scale
    return residual["max_abs"] <= limit, residual, limit
```

Esta fórmula es únicamente un punto de partida para el contrato de pruebas; no debe declararse teorema sin analizar el algoritmo y el rango de $D$.

## N21 — La rotación no maneja correctamente el ángulo grande por contrato

La expresión:

$$
\operatorname{versin}(\theta)=2\sin^2(\theta/2)
$$

evita la resta $1-\cos\theta$, pero no resuelve todos los problemas:

- $\theta$ muy grande pierde precisión al reducirse módulo $2\pi$;
- distintas librerías pueden tener diferencias;
- $\sin(\theta/2)$ puede recibir un argumento ya inexacto;
- la semántica para $\theta=\pm\infty$ debe ser rechazo;
- la semántica para $\theta$ subnormal debe probarse;
- si el usuario espera periodicidad exacta, IEEE-754 no la garantiza bit a bit.

Debe normalizarse el contrato:

```rust
fn validate_angle(theta: f64) -> Result<f64, Status> {
    if !theta.is_finite() {
        return Err(Status::InvalidScalar);
    }

    if theta.abs() > MAX_ACCEPTED_ANGLE {
        return Err(Status::AngleOutOfRange);
    }

    Ok(theta)
}
```

`MAX_ACCEPTED_ANGLE` no debe inventarse: debe fijarse según la precisión y el uso de la aplicación.

## N22 — El supuesto de `0 desgarros detectados` puede ser lógicamente circular

Si el lector detecta una escritura incompleta mediante un ticket, pero la telemetría solo cuenta lecturas aceptadas, entonces:

```text
0 torn reads
```

puede significar:

```text
0 torn reads que el detector no dejó pasar
```

Eso no prueba que el detector sea correcto.

Hay que agregar un patrón de datos verificable:

```cpp
struct Payload {
    std::uint64_t generation;
    std::uint64_t checksum;
    std::uint64_t length;
    std::uint8_t bytes[PAYLOAD_BYTES];
};
```

El productor escribe una generación y checksum; el consumidor verifica:

```cpp
bool validate_payload(const Payload& p) noexcept {
    if (p.length > PAYLOAD_BYTES) {
        return false;
    }

    if (p.generation == 0) {
        return false;
    }

    return checksum_bytes(p.bytes, p.length) == p.checksum;
}
```

No es suficiente para resolver el protocolo, pero permite detectar corrupción no observada por el ticket.

## N23 — SPMC no implica múltiples consumidores seguros

SPMC significa:

```text
single producer, multiple consumers
```

Pero hay que especificar si los consumidores:

- pueden leer simultáneamente el mismo slot;
- deben recibir todos los mensajes;
- compiten por el mensaje;
- tienen confirmación individual;
- pueden retrasarse indefinidamente;
- pueden causar reclamación prematura.

Un triple buffer típico puede servir para “último estado disponible”, pero no para una cola de eventos confiable. Si POLYDIM necesita garantizar que cada agente vea cada tensor, el triple buffer puede ser la estructura equivocada.

La especificación debe elegir:


| Semántica | Estructura probable |
| :-- | :-- |
| Solo último estado | triple buffer |
| Todos los mensajes | ring buffer con reclamación |
| Cada consumidor recibe todo | secuencia por consumidor |
| Reparto entre consumidores | cola con ownership |
| Transferencia de ownership | mensaje con reclamación explícita |

## N24 — Memoria compartida entre procesos no equivale a memoria compartida entre threads

El dossier mezcla `mmap`, Rust, C++ y atomics como si el mismo razonamiento se aplicara automáticamente entre procesos.

Hay que verificar:

- si el objeto atómico es válido en memoria compartida;
- si la plataforma soporta esa operación entre procesos;
- si el mapeo tiene el mismo layout;
- si ambos procesos usan la misma versión;
- si el archivo se trunca;
- si una página se desmapea mientras se lee;
- cómo se recupera de un productor muerto;
- cómo se detecta un proceso obsoleto;
- si hay locks robustos;
- si se necesita `memfd`, `shm_open` o equivalente;
- si se valida la identidad del segmento.

La prueba con threads no cubre la prueba entre procesos.

## N25 — No hay versión de protocolo ni compatibilidad de layout

Un `SLAB_ID` y un tag como `TENSOR_READY` no bastan. Deben incluir:

```rust
#[repr(C)]
pub struct SegmentHeader {
    pub magic: u64,
    pub protocol_major: u16,
    pub protocol_minor: u16,
    pub header_bytes: u32,
    pub endianness: u8,
    pub pointer_width: u8,
    pub element_type: u16,
    pub dimension: u64,
    pub payload_bytes: u64,
    pub generation: u64,
}
```

Validación:

```rust
fn validate_header(h: &SegmentHeader) -> Result<(), Status> {
    if h.magic != EXPECTED_MAGIC {
        return Err(Status::BadMagic);
    }

    if h.protocol_major != SUPPORTED_MAJOR {
        return Err(Status::ProtocolMismatch);
    }

    if h.header_bytes as usize != std::mem::size_of::<SegmentHeader>() {
        return Err(Status::HeaderSizeMismatch);
    }

    if h.endianness != NATIVE_ENDIANNESS {
        return Err(Status::EndiannessMismatch);
    }

    if h.element_type != ELEMENT_F64 {
        return Err(Status::ElementTypeMismatch);
    }

    Ok(())
}
```

No se debe transmitir punteros absolutos entre procesos: cada proceso puede mapear el segmento en una dirección distinta. El descriptor debe usar offsets relativos.

## N26 — La afirmación sobre OpenMP está incompleta

Añadir:

```cpp
#pragma omp parallel num_threads(nthreads)
```

no garantiza que todos los accesos sean seguros. Hay que revisar:

- `nthreads > 0`;
- `tid < nthreads`;
- arrays dimensionados con el número real de hilos;
- `omp_get_num_threads()`;
- variables `shared` y `private`;
- regiones anidadas;
- dynamic teams;
- tasking;
- excepciones o retornos dentro de la región;
- reducción y orden;
- variables estáticas;
- afinidad.

La especificación de OpenMP define una data race cuando accesos a la misma ubicación están desordenados y al menos uno escribe; por tanto, fijar `num_threads` solo resuelve una posible discrepancia de indexación, no el modelo completo de concurrencia.[^3_4][^3_5]

## N27 — Error conceptual en la comparación con OpenBLAS

“C++ 2× más rápido que OpenBLAS” puede ser cierto para una prueba concreta, pero no significa que el algoritmo sea superior. La comparación debe igualar:

- operación matemática;
- precisión;
- layout;
- tamaño;
- número de hilos;
- afinidad;
- warm-up;
- inicialización;
- memoria;
- verificación de resultados;
- frecuencia;
- versión de BLAS.

Además, si el código nativo ejecuta un caso especial $K=16$ y OpenBLAS ejecuta una ruta general, no es una comparación de bibliotecas, sino de implementaciones especializadas.

## N28 — Falta una política de fallos transitorios

En silicio real pueden ocurrir:

- páginas no residentes;
- errores de asignación;
- interrupciones;
- proceso productor muerto;
- archivo de mmap truncado;
- cierre prematuro del descriptor;
- presión de memoria;
- cambio de CPU;
- señales;
- timeout;
- pérdida de consumidor.

La API no debe devolver solo `rc=0` o un entero negativo genérico. Debe distinguir:

```rust
#[repr(C)]
pub enum Status {
    Ok = 0,
    NullPointer = -1,
    LengthOverflow = -2,
    OutOfBounds = -3,
    InvalidScalar = -4,
    NonFiniteInput = -5,
    BasisNotOrthonormal = -6,
    PointOffManifold = -7,
    ProtocolMismatch = -8,
    SlotBusy = -9,
    ProducerDead = -10,
    Timeout = -11,
    ChecksumMismatch = -12,
    Panic = -13,
    Internal = -14,
}
```

El consumidor debe saber si puede reintentar. No es lo mismo `SlotBusy` que `ChecksumMismatch`.

# Confirmación de no alucinación

## Lo que sí puedo afirmar

- El archivo recibido declara A1–A12 como cerrados.[^3_1]
- El archivo no contiene el código que permita verificar esas declaraciones.[^3_1]
- La documentación oficial de Rust confirma la distinción entre ABI con y sin unwind y el alcance limitado de `catch_unwind`.[^3_3][^3_2]
- Fijar la cantidad de threads en OpenMP no demuestra por sí solo ausencia de data races.[^3_5][^3_4]
- El nuevo ciclo abre N16–N28 como riesgos no cerrados.


## Lo que no puedo afirmar

No puedo afirmar que:

- esos bugs existan efectivamente en la implementación;
- estén corregidos;
- el protocolo de tickets sea incorrecto;
- el código sea vulnerable;
- la arquitectura sea imposible;
- el benchmark sea falso.

Puedo afirmar que **el dossier no aporta evidencia suficiente para cerrarlos**.

# Código de control para bloquear certificaciones falsas

```python
from dataclasses import dataclass
from enum import Enum


class ProofLevel(Enum):
    CLAIM = 0
    REPRODUCED = 1
    ADVERSARIAL = 2
    CROSS_PLATFORM = 3
    RELEASE = 4


@dataclass
class Finding:
    ident: str
    level: ProofLevel
    has_source: bool
    has_test: bool
    has_log: bool
    has_artifact_hash: bool
    has_failure_test: bool
    has_platform_matrix: bool


def release_eligible(f: Finding) -> bool:
    return (
        f.level is ProofLevel.RELEASE
        and f.has_source
        and f.has_test
        and f.has_log
        and f.has_artifact_hash
        and f.has_failure_test
        and f.has_platform_matrix
    )


def audit_gate(findings):
    blocked = [f.ident for f in findings if not release_eligible(f)]
    if blocked:
        raise RuntimeError(
            "CERTIFICATION BLOCKED: " + ", ".join(sorted(blocked))
        )
```

Este control no prueba el sistema matemático; evita una falla de gobernanza: llamar “cerrado” a un hallazgo sin pruebas suficientes.

# Estado después de este ciclo

```text
A1–A12: declarados cerrados en el dossier, no verificados aquí
N1–N15: abiertos por falta de evidencia/alcance
N16–N28: abiertos por riesgos adicionales de FFI, IPC, matemática y operación
```

El siguiente ciclo serio necesita el código real. Con el dossier solamente, continuar inventando implementaciones específicas sería precisamente la alucinación que estás intentando evitar.

<span style="display:none">[^3_10][^3_11][^3_12][^3_13][^3_14][^3_15][^3_16][^3_6][^3_7][^3_8][^3_9]</span>

<div align="center">⁂</div>

[^3_1]: 03_MULTI_AI_TRIBUNAL_VERDICTS-2.md

[^3_2]: https://doc.rust-lang.org/beta/nomicon/ffi.html

[^3_3]: https://doc.rust-lang.org/stable/nomicon/ffi.html

[^3_4]: https://www.openmp.org/wp-content/uploads/OpenMP-API-Specification-6-0.pdf

[^3_5]: https://www.openmp.org/spec-html/5.0/openmpse50.html

[^3_6]: https://en.cppreference.com/cpp/atomic/atomic

[^3_7]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2007/n2427.html

[^3_8]: https://users.rust-lang.org/t/passing-callbacks-to-c-panic/91080/20

[^3_9]: https://deepwiki.com/rust-lang/nomicon/11.1-calling-foreign-functions

[^3_10]: https://deepwiki.com/rust-lang/nomicon/11-foreign-function-interface-(ffi)

[^3_11]: https://softwareengineering.stackexchange.com/questions/279128/how-to-share-memory-between-applications-written-in-c-c

[^3_12]: https://doc.rust-lang.org/nomicon/ffi.html

[^3_13]: https://doc.rust-lang.org/reference/panic.html

[^3_14]: https://blog.rust-lang.org/inside-rust/2020/02/27/ffi-unwind-design-meeting.html

[^3_15]: https://internals.rust-lang.org/t/unhandled-panics-in-rust-vs-in-ffi/17981

[^3_16]: https://deepwiki.com/rust-lang/nomicon/12.2-panic-handling


---

## Ciclo 3: revisión profunda del dossier

Sí: **las observaciones de este ciclo no son afirmaciones de que el código tenga esos bugs**. Son hallazgos de auditoría sobre lo que el dossier no demuestra. El archivo solo declara A1–A12 como “cerrados”; no contiene código, protocolo formal, logs crudos ni matrices de plataforma. Por eso los nuevos puntos quedan como `ABIERTO / NO VERIFICADO`, no como defectos confirmados.[^4_1]

La evidencia externa respalda tres riesgos concretos: las reducciones de punto flotante reproducibles requieren algoritmos y análisis específicos; los objetos atómicos tienen requisitos de alineación, lifetime y sincronización; y una región `mmap` puede quedar inválida si el archivo subyacente se trunca o se modifica fuera del protocolo.[^4_2][^4_3][^4_4]

# N29 — La validación de `D` no demuestra seguridad del espacio total

El dossier permite:

$$
D=10{,}000 \ldots 10{,}000{,}000.
$$

Pero `D` no es el único tamaño peligroso. Deben verificarse todos los productos:

$$
D \cdot \text{sizeof}(f64),
\quad
D\cdot K,
\quad
\text{offset}+\text{payload},
\quad
\text{stride}\cdot(\text{rows}-1),
\quad
\text{threads}\cdot\text{partials}.
$$

Una función que valida solo `D <= 10_000_000` puede seguir teniendo overflow en:

```text
D * K
D * sizeof(double)
offset + bytes
stride * rows
```


### Solución

Toda aritmética de tamaños debe ser checked:

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(C)]
pub enum SizeError {
    ZeroDimension = -1,
    DimensionTooLarge = -2,
    MultiplicationOverflow = -3,
    AdditionOverflow = -4,
    ExceedsSegment = -5,
}

fn checked_mul(a: usize, b: usize) -> Result<usize, SizeError> {
    a.checked_mul(b).ok_or(SizeError::MultiplicationOverflow)
}

fn checked_add(a: usize, b: usize) -> Result<usize, SizeError> {
    a.checked_add(b).ok_or(SizeError::AdditionOverflow)
}

fn vector_bytes(dim: usize, max_dim: usize) -> Result<usize, SizeError> {
    if dim == 0 {
        return Err(SizeError::ZeroDimension);
    }
    if dim > max_dim {
        return Err(SizeError::DimensionTooLarge);
    }
    checked_mul(dim, std::mem::size_of::<f64>())
}

fn matrix_bytes(
    rows: usize,
    cols: usize,
    max_dim: usize,
) -> Result<usize, SizeError> {
    if rows == 0 || cols == 0 {
        return Err(SizeError::ZeroDimension);
    }
    if rows > max_dim || cols > max_dim {
        return Err(SizeError::DimensionTooLarge);
    }

    let elements = checked_mul(rows, cols)?;
    checked_mul(elements, std::mem::size_of::<f64>())
}
```


### Prueba adversarial

```python
def expect_rejected(fn, *args):
    try:
        fn(*args)
    except Exception:
        return True
    return False


def test_size_boundaries():
    max_dim = 10_000_000

    assert expect_rejected(vector_bytes, 0, max_dim)
    assert expect_rejected(vector_bytes, max_dim + 1, max_dim)

    huge = (1 << 63) // 8 + 1
    assert expect_rejected(vector_bytes, huge, huge)

    assert expect_rejected(matrix_bytes, max_dim, max_dim, max_dim)
```

El último caso debe rechazarse si el contrato no permite matrices de $10^7\times10^7$. Una dimensión individual válida no implica un producto válido.

**Estado:** N29 abierto hasta observar el código real de asignación y offsets.

# N30 — La cota numérica no distingue error absoluto, relativo y condicional

El dossier presenta una cota única:

$$
|y_{\text{final}}|_2-1 \le 4.44\times10^{-16}.
$$

Eso es ambiguo. Debe aclarar si significa:

$$
\left|\|y\|_2-1\right|,
$$

o:

$$
\left|\|y\|_2^2-1\right|,
$$

o error componente a componente, o error respecto de una referencia exacta.

Además, la estabilidad depende del condicionamiento. Una rotación bien condicionada no implica que la construcción de la base $(u,v_\perp)$ sea estable cuando $u$ y $v$ son casi paralelos.

Debe reportarse, como mínimo:

```text
norm_error_abs
norm_squared_error_abs
relative_error
max_component_error
reference_error
basis_condition_indicator
```


### Solución de contrato

```python
import math


def norm_metrics(y, reference=None):
    norm = math.sqrt(math.fsum(x * x for x in y))
    result = {
        "norm": norm,
        "abs_norm_error": abs(norm - 1.0),
        "squared_norm_error": abs(math.fsum(x * x for x in y) - 1.0),
        "max_abs_component": max((abs(x) for x in y), default=0.0),
    }

    if reference is not None:
        if len(reference) != len(y):
            raise ValueError("length mismatch")

        diff = [a - b for a, b in zip(y, reference)]
        ref_norm = math.sqrt(math.fsum(x * x for x in reference))
        diff_norm = math.sqrt(math.fsum(x * x for x in diff))

        result["reference_l2_error"] = diff_norm
        result["reference_relative_error"] = (
            diff_norm / ref_norm if ref_norm != 0.0 else diff_norm
        )

    return result
```

No debe existir una única constante universal si el contrato no especifica:

- rango de $\theta$;
- rango de componentes;
- norma de entrada;
- separación angular de $u,v$;
- orden de reducción;
- hardware;
- flags.

**Estado:** N30 abierto.

# N31 — El caso degenerado $v_\perp$ no está cerrado

La fórmula usa una base ortonormal. Si:

$$
v-(u^\top v)u\approx0,
$$

la normalización de $v_\perp$ puede producir:

- división por cero;
- NaN;
- vector arbitrario;
- resultado que parece válido pero no representa la rotación solicitada.


### Solución

La construcción debe rechazar explícitamente la degeneración:

```rust
fn orthogonal_component(
    u: &[f64],
    v: &[f64],
    abs_tol: f64,
    rel_tol: f64,
) -> Result<Vec<f64>, Status> {
    if u.len() != v.len() || u.is_empty() {
        return Err(Status::DimensionMismatch);
    }

    let uu = u.iter().map(|x| x * x).sum::<f64>();
    if !uu.is_finite() || uu <= 0.0 {
        return Err(Status::InvalidBasis);
    }

    let uv = u.iter().zip(v).map(|(a, b)| a * b).sum::<f64>();
    let coefficient = uv / uu;

    let mut w = Vec::with_capacity(u.len());
    for (ui, vi) in u.iter().zip(v) {
        let value = *vi - coefficient * *ui;
        if !value.is_finite() {
            return Err(Status::NonFiniteIntermediate);
        }
        w.push(value);
    }

    let ww = w.iter().map(|x| x * x).sum::<f64>();
    let threshold = abs_tol.max(rel_tol * uu.max(1.0));

    if !ww.is_finite() || ww <= threshold {
        return Err(Status::DegeneratePlane);
    }

    let inv = 1.0 / ww.sqrt();
    let result: Vec<f64> = w.into_iter().map(|x| x * inv).collect();

    if result.iter().any(|x| !x.is_finite()) {
        return Err(Status::NonFiniteIntermediate);
    }

    Ok(result)
}
```

Esto aún no es SOTA numérico: usa sumas simples y puede necesitar reducción compensada o escalada robusta. Pero evita el peor fallo: aceptar una base degenerada como válida.

### Casos que deben probarse

```text
v = u
v = -u
v = u + 2^-52 * w
v = u + 2^-500 * w
v = 0
u = 0
u contiene NaN
v contiene infinito
```

**Estado:** N31 abierto.

# N32 — La proyección automática puede ocultar corrupción

El dossier menciona:

```text
POLYDIM_ERR_POINT_OFF_MANIFOLD
polydim_project_sphere_f64
```

Eso plantea una decisión crítica: ¿el sistema rechaza el punto o lo corrige?

Si la función proyecta automáticamente un vector corrupto, puede convertir un error de memoria o de protocolo en una entrada aparentemente válida. Eso es peligroso para depuración y seguridad.

### Contrato recomendado

Separar funciones:

```rust
pub fn validate_sphere(y: &[f64], tol: f64) -> Result<(), Status> {
    let norm2 = y.iter().map(|x| x * x).sum::<f64>();

    if !norm2.is_finite() {
        return Err(Status::NonFiniteInput);
    }

    if (norm2 - 1.0).abs() > tol {
        return Err(Status::PointOffManifold);
    }

    Ok(())
}

pub fn project_sphere(y: &mut [f64]) -> Result<(), Status> {
    let norm2 = y.iter().map(|x| x * x).sum::<f64>();

    if !norm2.is_finite() || norm2 == 0.0 {
        return Err(Status::CannotProject);
    }

    let inv_norm = 1.0 / norm2.sqrt();

    for value in y {
        *value *= inv_norm;
    }

    Ok(())
}
```

La operación matemática de producción debe elegir una política explícita:

```text
STRICT: rechaza
REPAIR: proyecta y registra
DIAGNOSTIC: rechaza, pero ofrece reparación separada
```

No debe repararse silenciosamente.

**Estado:** N32 abierto.

# N33 — La fórmula de Rodrigues puede perder ortogonalidad por implementación, no por teoría

La fórmula teórica puede preservar la norma exactamente en álgebra real. La implementación en `f64` no lo hace exactamente. El dossier usa la propiedad matemática como si fuera garantía de silicio.

Para cada elemento del plano:

$$
a=(y^\top u),\qquad b=(y^\top v_\perp),
$$

la actualización es:

$$
y' = y
-\operatorname{versin}(\theta)(au+bv_\perp)
+\sin(\theta)(av_\perp-bu).
$$

En $D$ grande, el vector resultante realiza muchas operaciones. Debe compararse con una referencia de alta precisión y verificarse el peor caso.

### Test diferencial recomendado

```python
import math
from decimal import Decimal, getcontext

getcontext().prec = 100


def decimal_dot(a, b):
    return sum(
        (Decimal.from_float(x) * Decimal.from_float(y)
         for x, y in zip(a, b)),
        Decimal(0),
    )


def decimal_norm2(x):
    return decimal_dot(x, x)


def reference_rotation(y, u, vp, theta):
    yd = [Decimal.from_float(x) for x in y]
    ud = [Decimal.from_float(x) for x in u]
    vd = [Decimal.from_float(x) for x in vp]
    td = Decimal.from_float(theta)

    a = decimal_dot(yd, ud)
    b = decimal_dot(yd, vd)

    s = Decimal(str(math.sin(theta)))
    versin = Decimal(2) * (Decimal(str(math.sin(theta / 2.0))) ** 2)

    return [
        yd[i]
        - versin * (a * ud[i] + b * vd[i])
        + s * (a * vd[i] - b * ud[i])
        for i in range(len(y))
    ]


def max_decimal_difference(actual, reference):
    return max(
        abs(Decimal.from_float(a) - r)
        for a, r in zip(actual, reference)
    )
```

Esto separa el error de:

- la reducción;
- la trigonometría de la biblioteca;
- la actualización vectorial;
- la normalización posterior.

**Estado:** N33 abierto.

# N34 — `versin` no es una “estabilización de Kahan”

El dossier llama a:

$$
2\sin^2(\theta/2)
$$

“estabilización de Kahan”. La expresión evita la resta $1-\cos\theta$, pero no es correcto atribuirle automáticamente las propiedades de un algoritmo de Kahan. Son mecanismos distintos:

- Kahan: compensación de suma;
- `2*sin²(theta/2)`: identidad trigonométrica para calcular $1-\cos\theta$;
- reducción de argumentos grandes: problema separado;
- precisión de `sin`: depende de la implementación matemática.

La redacción correcta sería:

> “Se usa una identidad trigonométrica que evita la resta directa $1-\cos\theta$ para ángulos pequeños; la estabilidad completa requiere pruebas de reducción de argumento y de la implementación libm.”

**Estado:** N34 es un error de terminología y de evidencia, no necesariamente un bug funcional.

# N35 — No hay prueba de que FTZ esté bajo control en todos los hilos

El dossier afirma:

```text
POLYDIM_ENABLE_FTZ=0 por defecto
subnormales contados como telemetría
```

Eso no demuestra que:

- cada hilo tenga el modo esperado;
- una biblioteca BLAS no cambie el estado;
- un callback no cambie MXCSR/FPCR;
- un worker reutilizado no conserve configuración anterior;
- ARM64 y x86-64 tengan semántica equivalente;
- el estado se restaure al salir.


### Guard RAII en C++

```cpp
#if defined(__x86_64__) || defined(__i386__)
#include <xmmintrin.h>
#include <immintrin.h>

class FpEnvironmentGuard {
public:
    explicit FpEnvironmentGuard(bool enable_ftz)
        : old_mxcsr_(_mm_getcsr()) {
        unsigned int next = old_mxcsr_;

        constexpr unsigned int FTZ = 1u << 15;
        constexpr unsigned int DAZ = 1u << 6;

        if (enable_ftz) {
            next |= FTZ | DAZ;
        } else {
            next &= ~(FTZ | DAZ);
        }

        _mm_setcsr(next);
    }

    ~FpEnvironmentGuard() {
        _mm_setcsr(old_mxcsr_);
    }

    FpEnvironmentGuard(const FpEnvironmentGuard&) = delete;
    FpEnvironmentGuard& operator=(const FpEnvironmentGuard&) = delete;

private:
    unsigned int old_mxcsr_;
};
#endif
```

Este código solo cubre x86 y debe probarse. En ARM64 la gestión se hace con registros y APIs diferentes; no debe copiarse la semántica de MXCSR.

La prueba debe ejecutarse dentro de cada worker:

```text
worker starts
  capture FP mode
  assert expected mode
  execute operation
  capture FP mode
  assert unchanged
worker exits
```

**Estado:** N35 abierto.

# N36 — El uso de atomics en mmap no garantiza que el objeto exista legalmente

Una región de bytes mapeada no se convierte automáticamente en un objeto C++ válido de tipo atómico por reinterpretación de puntero. Hay que resolver:

- alineación;
- lifetime del objeto;
- representación;
- compatibilidad entre procesos;
- tamaño;
- lock-free;
- inicialización;
- destrucción;
- reutilización de la región.

El estándar C++ trata el lifetime como una condición de validez del acceso; una dirección alineada no sustituye la construcción válida del objeto.[^4_3][^4_5]

### Política segura de layout

En la cabecera compartida debe evitarse depender de punteros y objetos complejos. Usar un layout de enteros de representación claramente definido y una capa específica de sincronización, con pruebas por plataforma.

```cpp
#include <cstddef>
#include <cstdint>
#include <type_traits>

struct alignas(64) SharedHeader {
    std::uint64_t magic;
    std::uint32_t version_major;
    std::uint32_t version_minor;
    std::uint64_t total_bytes;
    std::uint64_t slot_count;
    std::uint64_t slot_bytes;
    std::uint64_t generation;
    std::uint64_t reserved[^4_3];
};

static_assert(std::is_trivially_copyable_v<SharedHeader>);
static_assert(alignof(SharedHeader) >= 64);
static_assert(sizeof(SharedHeader) % 64 == 0);
```

Esto no resuelve por sí mismo la sincronización. Solo reduce ambigüedad de layout.

**Estado:** N36 abierto.

# N37 — Falta protocolo de recuperación ante proceso muerto

Si el productor muere después de:

```text
marca slot WRITING
escribe parte del tensor
muere
```

¿qué hace el consumidor?

Si el sistema espera indefinidamente, hay una denegación de servicio. Si recupera demasiado pronto, puede leer datos incompletos.

Debe existir:

```text
owner_id
lease_epoch
monotonic_timestamp
heartbeat
timeout
recovery_state
```

Ejemplo:

```rust
#[repr(C)]
pub struct Lease {
    pub owner_id: u64,
    pub epoch: u64,
    pub heartbeat_ns: u64,
    pub state: u32,
    pub reserved: u32,
}

pub const SLOT_FREE: u32 = 0;
pub const SLOT_WRITING: u32 = 1;
pub const SLOT_PUBLISHED: u32 = 2;
pub const SLOT_RECOVERING: u32 = 3;
```

Regla crítica:

```text
Un consumidor no puede recuperar un slot solo porque pasó un timeout;
debe demostrar que el owner murió o que la epoch fue invalidada.
```

Los relojes deben ser monotónicos. El tiempo de pared puede retroceder o saltar.

**Estado:** N37 abierto.

# N38 — El checksum no autentica al productor

Si el bus es solo contra fallos accidentales, un checksum puede detectar corrupción. Si existe un proceso comprometido, un checksum que el mismo productor calcula no protege contra manipulación intencional.

Debe definirse el modelo de amenaza:

```text
accidental corruption only
untrusted producer
untrusted consumer
same-user adversary
cross-user adversary
```

Según el modelo, se necesita:

- checksum no criptográfico;
- CRC;
- MAC;
- permisos del descriptor;
- aislamiento de usuarios;
- autenticación del productor;
- firma;
- sandbox.

No usar “integridad” sin distinguir corrupción accidental de adversario malicioso.

**Estado:** N38 abierto.

# N39 — El benchmark de 4,27 ms puede estar midiendo páginas ya calientes

Un benchmark de memoria compartida puede medir:

- cálculo;
- page faults;
- mapping;
- prefault;
- caché;
- TLB;
- sincronización;
- serialización;
- copia accidental;
- solo descriptor.

Hay que separar fases:

```text
create
map
fault-in
initialize
publish
read
compute
verify
unmap
destroy
```


### Esquema de benchmark

```python
from dataclasses import dataclass
from statistics import median, quantiles


@dataclass
class BenchmarkResult:
    name: str
    samples_ns: list[int]

    @property
    def median_ns(self):
        return median(self.samples_ns)

    @property
    def p95_ns(self):
        return quantiles(self.samples_ns, n=100)[^4_94]

    @property
    def minimum_ns(self):
        return min(self.samples_ns)


def summarize(result: BenchmarkResult):
    return {
        "name": result.name,
        "n": len(result.samples_ns),
        "min_ns": result.minimum_ns,
        "median_ns": result.median_ns,
        "p95_ns": result.p95_ns,
    }
```

El resultado debe incluir:

```text
CPU model
microcode
OS/kernel
compiler
flags
thread count
affinity
NUMA
temperature
memory mode
warm-up count
sample count
outliers
input distribution
verification status
```

**Estado:** N39 abierto.

# N40 — No existe una matriz de portabilidad real

El dossier menciona dimensiones enormes y “silicio real”, pero no define una matriz:


| Plataforma | ABI | FP mode | atomics | sanitizer | estado |
| :-- | :-- | :-- | :-- | :-- | :-- |
| x86-64 Linux | C | MXCSR | requerido | ASan/TSan | no demostrado |
| ARM64 Linux | C | FPCR | requerido | ASan/TSan | no demostrado |
| Windows | C | distinto | requerido | herramientas distintas | no demostrado |
| macOS ARM64 | C | distinto | requerido | herramientas distintas | no demostrado |

“Funciona en mi CPU” no es portabilidad. La arquitectura debe declarar explícitamente qué plataformas soporta y cuáles no.

# Matriz de nuevos hallazgos

| ID | Hallazgo | Severidad | Tipo | Estado |
| :-- | :-- | --: | :-- | :-- |
| N29 | Overflow en productos de tamaños y offsets | Crítica | memoria | Abierto |
| N30 | Cota sin definición precisa de métrica | Alta | matemática | Abierto |
| N31 | Plano degenerado no especificado | Crítica | matemática | Abierto |
| N32 | Proyección puede ocultar corrupción | Alta | contrato | Abierto |
| N33 | Rodrigues no comparado con referencia de alta precisión | Alta | numérica | Abierto |
| N34 | “Kahan stabilization” es terminología incorrecta | Media | especificación | Abierto |
| N35 | FP mode no probado por worker/plataforma | Alta | hardware | Abierto |
| N36 | Lifetime/alineación de objetos atómicos en mmap | Crítica | IPC/C++ | Abierto |
| N37 | Sin recuperación formal ante productor muerto | Alta | disponibilidad | Abierto |
| N38 | Checksum sin modelo de amenaza | Alta | seguridad | Abierto |
| N39 | Benchmark potencialmente contaminado por caché/page faults | Alta | rendimiento | Abierto |
| N40 | Sin matriz de portabilidad | Alta | industrialización | Abierto |

# Veredicto de este ciclo

No hay base para afirmar que estos puntos estén corregidos. Tampoco hay base para afirmar que cada uno sea un bug efectivo del código, porque el código no está disponible.

La conclusión defendible es:

```text
V762:
  matemáticamente certificado: NO DEMOSTRADO
  memoria segura: NO DEMOSTRADO
  FFI seguro: NO DEMOSTRADO
  IPC interproceso segura: NO DEMOSTRADO
  reproducibilidad numérica: NO DEMOSTRADA
  benchmark reproducible: NO DEMOSTRADO
  portabilidad: NO DEMOSTRADA
```

El siguiente ciclo puede atacar más profundamente el dossier en cuatro ejes: **modelo de amenazas, recuperación ante fallos, reproducibilidad bit a bit y límites físicos de D=10.000.000**.

<span style="display:none">[^4_10][^4_11][^4_12][^4_13][^4_14][^4_15][^4_16][^4_17][^4_6][^4_7][^4_8][^4_9]</span>

<div align="center">⁂</div>

[^4_1]: 03_MULTI_AI_TRIBUNAL_VERDICTS-2.md

[^4_2]: https://www2.eecs.berkeley.edu/Pubs/TechRpts/2015/EECS-2015-229.pdf

[^4_3]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2026/p3181r1.pdf

[^4_4]: https://lib.rs/crates/mmap-io

[^4_5]: https://library.oapen.org/bitstream/handle/20.500.12657/22836/1/1007325.pdf

[^4_6]: https://doc.rust-lang.org/reference/linkage.html?highlight=ffi

[^4_7]: https://www2.eecs.berkeley.edu/Pubs/TechRpts/2015/Archive/EECS-2015-229.pdf

[^4_8]: https://ieeexplore.ieee.org/document/8766229

[^4_9]: https://www2.eecs.berkeley.edu/Pubs/TechRpts/2016/EECS-2016-121.pdf

[^4_10]: https://docs.rs/shared_memory/latest/shared_memory/

[^4_11]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p3181r0.pdf

[^4_12]: https://users.rust-lang.org/t/shared-memory-for-interprocess-communication/92408

[^4_13]: https://users.rust-lang.org/t/safety-of-shared-memory-ipc-with-mmap/137053

[^4_14]: https://blog.telios.dev/blog/memory-safety.html

[^4_15]: https://lists.isocpp.org/std-proposals/2026/01/16539.php

[^4_16]: https://www.linkedin.com/pulse/rust-ipc-from-scratch-mmap-atomics-memory-layouts-migo-lee-vgytf

[^4_17]: http://www.man6.org/docs/cppreference-doc/reference/en.cppreference.com/w/cpp/atomic/atomic_ref.html


---

# Ciclo 4: fallos más profundos

Sí: **confirmo que no son alucinaciones en el sentido correcto de auditoría**: cada punto está etiquetado como riesgo o falta de evidencia, no como bug confirmado del código. No tengo el monolito fuente, por lo que no afirmaré que una línea concreta está rota. El dossier solo declara A1–A12 como cerrados; no demuestra esas correcciones con artefactos reproducibles.[^5_1]

La documentación oficial de Rust confirma que un puntero crudo puede ser nulo, colgante, desalineado o carecer de provenance válida; acceder a memoria inválida o hacer aritmética fuera de la asignación es comportamiento indefinido. GCC también confirma que `-ffast-math` permite transformaciones incompatibles con código que depende de reglas exactas IEEE/ISO.[^5_2][^5_3][^5_4][^5_5][^5_6][^5_7]

## N41 — Confusión entre dirección, puntero y provenance

Un diseño de memoria compartida suele publicar algo como:

```cpp
std::uint8_t* data;
```

Eso puede funcionar dentro de un proceso, pero no debe transmitirse como dirección entre procesos. Cada proceso puede mapear el mismo segmento en una dirección virtual distinta.

Más profundamente, en Rust el valor numérico de una dirección no es toda la historia: la validez de un acceso depende también de la provenance del puntero.[^5_4][^5_5]

### Diseño correcto

Transmitir:

```cpp
struct RelativeSlice {
    std::uint64_t segment_id;
    std::uint64_t byte_offset;
    std::uint64_t byte_length;
    std::uint64_t generation;
};
```

Nunca transmitir:

```cpp
struct UnsafeDescriptor {
    void* absolute_pointer;
    std::size_t length;
};
```

Resolver el descriptor localmente:

```rust
#[repr(C)]
pub struct RelativeSlice {
    pub segment_id: u64,
    pub byte_offset: u64,
    pub byte_length: u64,
    pub generation: u64,
}

pub unsafe fn resolve_slice<'a>(
    base: *mut u8,
    mapped_bytes: usize,
    desc: &RelativeSlice,
) -> Result<&'a [u8], Status> {
    let offset = usize::try_from(desc.byte_offset)
        .map_err(|_| Status::OffsetOverflow)?;

    let length = usize::try_from(desc.byte_length)
        .map_err(|_| Status::LengthOverflow)?;

    let end = offset
        .checked_add(length)
        .ok_or(Status::AddressOverflow)?;

    if end > mapped_bytes {
        return Err(Status::OutOfBounds);
    }

    let ptr = base.add(offset);
    Ok(std::slice::from_raw_parts(ptr, length))
}
```

Esto exige que el lifetime solo sea válido mientras el mapeo permanezca vivo. La firma puede esconder esa condición; el wrapper seguro debe encapsularla y evitar que la referencia sobreviva al mapping.

**Estado:** N41 abierto hasta comprobar que PMTP usa offsets, no punteros cruzables.

## N42 — El descriptor puede sufrir TOCTOU

Aunque el consumidor valide:

```text
offset
length
generation
checksum
```

el productor podría modificar el descriptor o el slot después de la validación y antes de la lectura. Es una condición clásica de “time of check versus time of use”.

### Solución

Capturar una instantánea estable mediante secuencia:

```cpp
struct SlotMeta {
    std::atomic<std::uint64_t> sequence;
    std::uint64_t offset;
    std::uint64_t length;
    std::uint64_t generation;
    std::uint64_t checksum;
};
```

El lector:

```cpp
bool read_meta(const SlotMeta& slot, Snapshot& out) noexcept {
    for (unsigned attempt = 0; attempt < 8; ++attempt) {
        const auto before =
            slot.sequence.load(std::memory_order_acquire);

        if (before & 1u) {
            continue; // writer active
        }

        Snapshot candidate{
            slot.offset,
            slot.length,
            slot.generation,
            slot.checksum
        };

        const auto after =
            slot.sequence.load(std::memory_order_acquire);

        if (before == after && !(after & 1u)) {
            out = candidate;
            return true;
        }
    }

    return false;
}
```

Pero esto solo protege la metadata si el protocolo del escritor es correcto:

```cpp
sequence.store(odd, release);  // empieza escritura
write fields;
sequence.store(even, release); // publica
```

No garantiza que el payload siga vivo después de capturar la metadata. Hace falta una regla de reclamación.

**Estado:** N42 abierto.

## N43 — Secuencia par/impar no resuelve reclamación

Un lector puede obtener:

```text
offset = 1000
length = 8000
generation = 42
```

y el productor puede reutilizar ese espacio inmediatamente para la generación 43. El lector ve metadata consistente, pero el payload ya cambió.

Por tanto, el protocolo necesita una de estas garantías:

```text
reference count
hazard pointer
epoch-based reclamation
per-consumer acknowledgement
immutable payload until lease expiry
copy-on-read
```


### Contrato con lease

```rust
#[repr(C)]
pub struct LeaseToken {
    pub segment_id: u64,
    pub slot_id: u32,
    pub reserved: u32,
    pub generation: u64,
    pub expiry_monotonic_ns: u64,
}
```

Regla:

```text
El productor no puede reciclar el slot mientras exista
un lease válido o un acknowledgement pendiente.
```

Si el objetivo es “último estado” y se permite perder actualizaciones, se puede usar triple buffer. Si se necesita que cada agente consuma cada tensor, el triple buffer no basta.

**Estado:** N43 crítico y abierto.

## N44 — Uso incorrecto de `volatile` como sincronización

Si el código usa:

```cpp
volatile bool ready;
volatile std::uint8_t* payload;
```

eso no constituye sincronización entre hilos. `volatile` controla ciertas optimizaciones de acceso, pero no proporciona el orden de memoria requerido para publicar metadata y payload.

### Sustitución mínima

```cpp
std::atomic<std::uint64_t> sequence{0};
```

y operaciones `release/acquire`, o mutex/condvar bien definidos.

La documentación de atomics indica que las operaciones atómicas pueden establecer sincronización y ordenar accesos no atómicos según el `memory_order`; eso es distinto de `volatile`.[^5_8]

**Estado:** N44 condicionado al código; debe buscarse explícitamente en la implementación.

## N45 — El dossier no define qué significa “cero desgarros”

“0 desgarros no detectados” es una métrica débil. Necesita separar:

```text
torn writes generados
torn writes detectados
torn writes rechazados
lecturas válidas
lecturas descartadas
timeouts
checksum failures
ABA events
producer recoveries
```

Si el sistema detecta todos los desgarros, el número “0 desgarros no detectados” es útil. Pero si solo valida el ticket y nunca inyecta corrupción, el test no demuestra capacidad real.

### Test de inyección

```python
from dataclasses import dataclass


@dataclass
class ReadObservation:
    accepted: bool
    checksum_ok: bool
    generation_before: int
    generation_after: int
    payload_generation: int


def classify(obs: ReadObservation) -> str:
    if obs.generation_before != obs.generation_after:
        return "concurrent_update"

    if not obs.checksum_ok:
        return "payload_corruption"

    if obs.payload_generation != obs.generation_before:
        return "generation_mismatch"

    if obs.accepted:
        return "valid"

    return "rejected"
```

El test debe forzar:

- interrupción entre metadata y payload;
- interrupción entre payload y publicación;
- productor muerto;
- reutilización rápida del slot;
- wraparound pequeño;
- consumidor retrasado;
- checksum incorrecto.

**Estado:** N45 abierto.

## N46 — `-ffp-contract=off` no prueba reproducibilidad completa

El dossier atribuye seguridad a:

```text
-fno-fast-math -ffp-contract=off
```

Eso puede evitar ciertos contratos FMA/reasociaciones, pero no fija:

- orden de reducción;
- implementación de `sin`, `sqrt`, `remainder`;
- redondeo del hardware;
- estado FP por hilo;
- bibliotecas enlazadas;
- vectorización;
- exceso de precisión;
- diferencias x86/ARM;
- resultados de OpenMP.

GCC documenta que `-ffast-math` activa supuestos como valores finitos, ausencia de NaN y optimizaciones matemáticas inseguras; desactivarlo elimina una clase de riesgos, no todos.[^5_6][^5_7]

### Política realista

Definir una de tres garantías:

```text
NUMERICALLY_STABLE:
  resultado dentro de tolerancia

REPRODUCIBLE_PER_PLATFORM:
  mismo resultado en la misma plataforma/configuración

BITWISE_REPRODUCIBLE:
  mismos bits entre ejecuciones y plataformas
```

No declarar la tercera si no existe un algoritmo de reducción reproducible.

## N47 — El estado de redondeo no está controlado

IEEE-754 permite distintos modos de redondeo. Si el proceso externo cambia:

```text
FE_TONEAREST
FE_DOWNWARD
FE_UPWARD
FE_TOWARDZERO
```

el mismo código puede producir resultados diferentes.

### Guard de redondeo en C++

```cpp
#include <cfenv>
#include <stdexcept>

#pragma STDC FENV_ACCESS ON

class RoundingGuard {
public:
    explicit RoundingGuard(int requested) {
        old_ = std::fegetround();
        if (old_ == -1) {
            throw std::runtime_error("fegetround failed");
        }

        if (std::fesetround(requested) != 0) {
            throw std::runtime_error("fesetround failed");
        }
    }

    ~RoundingGuard() {
        if (old_ != -1) {
            std::fesetround(old_);
        }
    }

    RoundingGuard(const RoundingGuard&) = delete;
    RoundingGuard& operator=(const RoundingGuard&) = delete;

private:
    int old_;
};
```

La política debe indicar si:

```text
se rechaza cualquier modo no nearest;
se fuerza nearest y se restaura;
se acepta el modo externo y se reporta;
```

**Estado:** N47 abierto.

## N48 — Las excepciones FP no están especificadas

El sistema puede producir:

```text
NaN
+Inf
-Inf
underflow
overflow
inexact
invalid
divide-by-zero
```

No alcanza con validar `isfinite` al inicio. Hay que decidir qué hacer con intermediarios no finitos.

### Instrumentación conceptual

```cpp
#include <cmath>
#include <limits>

struct FpTelemetry {
    std::uint64_t nonfinite_inputs = 0;
    std::uint64_t nonfinite_intermediates = 0;
    std::uint64_t underflow_suspected = 0;
};

inline bool finite_or_record(double x, FpTelemetry& t) noexcept {
    if (!std::isfinite(x)) {
        ++t.nonfinite_intermediates;
        return false;
    }
    return true;
}
```

Esto no detecta todos los underflows; una política rigurosa debe usar flags FP, límites escalados y tests con subnormales.

**Estado:** N48 abierto.

## N49 — El uso de `f64` puede hacer imposible el objetivo en $D=10^7$

Para un vector de $D=10^7$:

$$
10^7 \cdot 8 = 80\,000\,000\text{ bytes}
$$

Eso es aproximadamente 76,3 MiB por vector, sin contar:

- copia de entrada;
- salida;
- bases $u,v$;
- buffers temporales;
- parciales por thread;
- metadata;
- páginas;
- memoria de otros agentes.

Con $y,u,v,v_\perp$, el working set puede superar 300 MB antes de contar el runtime. Si $K$ crece, escala rápidamente.

El sistema debe especificar:

```text
maximum resident set
maximum simultaneous vectors
maximum threads
temporary memory
NUMA placement
page size
streaming policy
```


### Presupuesto de memoria

```python
def memory_budget(dim, vectors, bytes_per_value=8, overhead=0):
    if dim < 0 or vectors < 0:
        raise ValueError("negative input")

    payload = dim * vectors * bytes_per_value
    return {
        "payload_bytes": payload,
        "total_bytes": payload + overhead,
        "payload_mib": payload / (1024**2),
        "payload_gib": payload / (1024**3),
    }


def require_budget(dim, vectors, budget_bytes):
    needed = dim * vectors * 8
    if needed > budget_bytes:
        raise MemoryError(
            f"required={needed}, budget={budget_bytes}"
        )
```

No se debe permitir que el sistema “funcione” mediante swap si el contrato es latencia estable.

**Estado:** N49 abierto.

## N50 — “O(1) transfer” ignora el coste de TLB y page faults

El descriptor puede transferirse en $O(1)$, pero acceder al tensor de 80 MB produce costes físicos:

- page walks;
- TLB misses;
- cache misses;
- NUMA remote accesses;
- page faults;
- copy-on-write si se mapea incorrectamente.

La documentación de mapeos compartidos no convierte el acceso en coste constante. La arquitectura debe reportar por separado:

```text
descriptor latency
publication latency
first-touch latency
steady-state scan latency
cross-NUMA latency
```

**Estado:** N50 abierto.

# Ciclo de pruebas para estos fallos

## Script de política de cierre

```python
from enum import Enum


class FindingState(Enum):
    OPEN = "OPEN"
    HYPOTHESIS = "HYPOTHESIS"
    REPRODUCED = "REPRODUCED"
    FIXED = "FIXED"
    VERIFIED = "VERIFIED"


def may_close(state, evidence):
    required = {
        "source_revision",
        "test_command",
        "test_output",
        "platform",
        "compiler",
        "flags",
        "negative_test",
        "artifact_hash",
    }

    return (
        state is FindingState.VERIFIED
        and required.issubset(evidence)
        and all(evidence[key] for key in required)
    )


def close_or_raise(finding_id, state, evidence):
    if not may_close(state, evidence):
        missing = {
            "source_revision",
            "test_command",
            "test_output",
            "platform",
            "compiler",
            "flags",
            "negative_test",
            "artifact_hash",
        } - set(evidence)

        raise RuntimeError(
            f"{finding_id} remains open; missing={sorted(missing)}"
        )

    return f"{finding_id}: VERIFIED"
```


## Hallazgos del ciclo

| ID | Problema | Severidad | Estado |
| :-- | :-- | --: | :-- |
| N41 | Punteros absolutos/provenance en IPC | Crítica | Abierto |
| N42 | TOCTOU en metadata y payload | Crítica | Abierto |
| N43 | Reclamación de slots no resuelta | Crítica | Abierto |
| N44 | Posible uso de `volatile` como sincronización | Alta | Condicionado al código |
| N45 | Métrica “cero desgarros” posiblemente circular | Alta | Abierto |
| N46 | Flags de compilación insuficientes para reproducibilidad | Alta | Abierto |
| N47 | Modo de redondeo no especificado | Alta | Abierto |
| N48 | Excepciones FP/intermediarios no definidos | Alta | Abierto |
| N49 | Presupuesto físico de memoria para $D=10^7$ | Crítica | Abierto |
| N50 | “O(1)” ignora coste de acceso físico | Alta | Abierto |

# Veredicto

El dossier no puede pasar todavía de:

```text
“matemáticamente SOTA en la descripción”
```

a:

```text
“industrialmente inquebrantable en silicio real”
```

porque faltan, como mínimo:

1. contrato de provenance y offsets;
2. reclamación segura de payload;
3. prueba contra TOCTOU y ABA;
4. política de redondeo y excepciones FP;
5. definición de reproducibilidad;
6. presupuesto de memoria y NUMA;
7. pruebas de proceso muerto;
8. inyección de corrupción;
9. benchmark dividido por fases;
10. evidencia hashada de cada cierre.

No confirmo que N41–N50 sean bugs presentes en el código. Confirmo que **el dossier no los descarta**. Esa es la conclusión no alucinada y técnicamente defendible.

<span style="display:none">[^5_10][^5_11][^5_12][^5_13][^5_14][^5_15][^5_16][^5_17][^5_9]</span>

<div align="center">⁂</div>

[^5_1]: 03_MULTI_AI_TRIBUNAL_VERDICTS-2.md

[^5_2]: https://doc.rust-lang.org/book/ch20-01-unsafe-rust.html

[^5_3]: https://doc.rust-lang.org/reference/behavior-considered-undefined.html

[^5_4]: https://rust-lang.github.io/rfcs/3559-rust-has-provenance.html

[^5_5]: https://doc.rust-lang.org/std/ptr/index.html

[^5_6]: https://gcc.gnu.org/onlinedocs/gcc/Floating-point-implementation.html

[^5_7]: https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html

[^5_8]: https://en.cppreference.com/cpp/atomic/atomic

[^5_9]: https://www.cs.cmu.edu/~jssunshi/assets/pdf/rust-foreign-function-boundaries-study.pdf

[^5_10]: https://www.intel.com/content/dam/develop/external/us/en/documents/fp-control-2013-03.pdf

[^5_11]: https://doc.rust-lang.org/beta/std/ptr/index.html

[^5_12]: https://www.research-collection.ethz.ch/server/api/core/bitstreams/4cf886af-fae2-44c7-839b-2337aaa7132f/content

[^5_13]: https://github.com/rust-lang/miri/

[^5_14]: https://github.com/rust-lang/miri/blob/master/README.md

[^5_15]: https://users.rust-lang.org/t/miri-undefined-behavior-of-using-a-const-as-mut-pointer/52978

[^5_16]: https://rust-for-c-programmers.com/ch25/25_3_raw_pointers_const_t_and_mut_t.html

[^5_17]: https://www.rustfaq.org/en/how-to-use-miri-to-detect-undefined-behavior-in-rust/


---

# Ciclo 5: ABI, mmap y reproducibilidad

Sí: **este ciclo tampoco afirma que el código tenga estos defectos**. Identifica garantías que el dossier no demuestra. La única fuente entregada sigue siendo un veredicto textual que declara A1–A12 cerrados; no contiene implementaciones, layouts, pruebas negativas ni logs completos.[^6_1]

La documentación oficial confirma que `#[repr(C)]` es necesario para layout interoperable, pero no basta por sí solo para demostrar compatibilidad binaria completa; también importan tamaño, alineación, padding, tipos, ABI y plataforma. Además, truncar un archivo que respalda un `mmap` puede provocar `SIGBUS` al acceder a páginas dentro de la región truncada.[^6_2][^6_3][^6_4]

## N51 — `#[repr(C)]` no garantiza compatibilidad total

Un supuesto frecuente sería:

```rust
#[repr(C)]
struct Header {
    magic: u64,
    length: usize,
}
```

y en C++:

```cpp
struct Header {
    std::uint64_t magic;
    std::size_t length;
};
```

Esto no es un contrato portable completo porque `usize` y `size_t` dependen de la plataforma. También pueden divergir:

- ancho de puntero;
- endianess;
- ABI;
- packing;
- alineación;
- compilador;
- tamaño de `bool`;
- representación de enums;
- padding reservado.


### Solución

Usar anchos explícitos:

```rust
#[repr(C)]
#[derive(Clone, Copy)]
pub struct Header {
    pub magic: u64,
    pub version_major: u32,
    pub version_minor: u32,
    pub header_bytes: u32,
    pub flags: u32,
    pub payload_offset: u64,
    pub payload_bytes: u64,
}
```

```cpp
#include <cstddef>
#include <cstdint>
#include <type_traits>

struct Header {
    std::uint64_t magic;
    std::uint32_t version_major;
    std::uint32_t version_minor;
    std::uint32_t header_bytes;
    std::uint32_t flags;
    std::uint64_t payload_offset;
    std::uint64_t payload_bytes;
};

static_assert(std::is_standard_layout_v<Header>);
static_assert(std::is_trivially_copyable_v<Header>);
static_assert(offsetof(Header, magic) == 0);
static_assert(offsetof(Header, payload_offset) == 24);
static_assert(sizeof(Header) == 40);
```

En Rust:

```rust
const _: () = assert!(core::mem::size_of::<Header>() == 40);
const _: () = assert!(core::mem::align_of::<Header>() == 8);
```

Los offsets deben generarse o verificarse automáticamente en CI para cada target soportado.

**Estado:** N51 abierto.

## N52 — `#[repr(C, packed)]` puede crear accesos desalineados

Una solución aparentemente fácil es:

```rust
#[repr(C, packed)]
struct PackedHeader {
    magic: u64,
    length: u64,
}
```

Eso elimina padding, pero puede crear campos desalineados. Tomar una referencia a un campo desalineado puede ser comportamiento indefinido. El layout compacto no justifica lecturas directas como si fueran `u64` alineados.

### Solución

No usar `packed` para campos que se leen directamente. Si el formato externo exige bytes compactos, leer con `read_unaligned` y copiar a tipos locales:

```rust
use std::ptr;

fn read_u64_unaligned(bytes: &[u8], offset: usize) -> Option<u64> {
    let end = offset.checked_add(8)?;
    let src = bytes.get(offset..end)?;

    let mut raw = [0u8; 8];
    raw.copy_from_slice(src);

    Some(u64::from_le_bytes(raw))
}
```

O usar un header alineado y reservar padding explícitamente.

**Estado:** N52 abierto si el código usa `packed`, casts o referencias a campos de memoria compartida.

## N53 — Endianness no está definida

Un archivo `mmap` o segmento compartido no debe asumir que todos los participantes usan el mismo endianess. Incluso si hoy solo se soporta x86-64 y ARM64 little-endian, el contrato debe declarar el hecho y rechazar formatos incompatibles.

### Solución

```rust
const FORMAT_ENDIAN_LITTLE: u8 = 1;
const FORMAT_ENDIAN_BIG: u8 = 2;

fn native_endian_tag() -> u8 {
    if cfg!(target_endian = "little") {
        FORMAT_ENDIAN_LITTLE
    } else {
        FORMAT_ENDIAN_BIG
    }
}
```

Todos los campos del formato deben serializarse explícitamente:

```rust
fn encode_u64_le(value: u64, out: &mut [u8]) -> Result<(), Status> {
    if out.len() < 8 {
        return Err(Status::BufferTooSmall);
    }
    out[..8].copy_from_slice(&value.to_le_bytes());
    Ok(())
}
```

No confiar en:

```rust
unsafe { *(ptr as *const u64) }
```

si el formato es portable.

**Estado:** N53 abierto.

## N54 — `mmap` puede quedar vivo mientras el archivo se trunca

Si el productor o un tercero reduce el archivo detrás del mapping, el proceso puede recibir `SIGBUS` al tocar páginas truncadas. Esto no es un `Result`, por lo que una API que promete “todos los errores como códigos” no puede cumplirlo automáticamente.[^6_4]

### Solución de diseño

Antes de mapear:

```text
fstat
validar tamaño mínimo
mapear
verificar header
```

Durante la operación:

```text
no permitir truncamiento mientras existan mappings
usar ownership exclusivo del descriptor
usar un archivo inmutable después de inicialización
o usar memoria compartida cuyo tamaño no cambie
```

En Linux, el control del ciclo de vida debe incluir:

```text
creador
descriptor duplicado
lock de inicialización
magic/version
tamaño total
estado READY
estado CLOSING
```

No se debe prometer que un `catch_unwind` captura `SIGBUS`; una señal fatal no es un panic Rust ordinario.

**Estado:** N54 crítico y abierto.

## N55 — Inicialización parcial del segmento

Un consumidor puede abrir el segmento cuando el creador ya reservó el archivo, pero todavía no escribió todo el header. Si lee un header parcialmente inicializado, puede interpretar basura como:

```text
payload_offset
payload_bytes
slot_count
```


### Solución: protocolo de dos fases

```text
ALLOCATED
INITIALIZING
READY
CLOSING
CLOSED
```

Publicar `READY` solo después de escribir y sincronizar todo el header:

```cpp
struct SharedControl {
    std::uint64_t magic;
    std::uint32_t version;
    std::uint32_t state;
    std::uint64_t total_bytes;
    std::uint64_t generation;
};
```

El consumidor debe rechazar todo estado excepto `READY`.

```cpp
constexpr std::uint32_t STATE_INITIALIZING = 1;
constexpr std::uint32_t STATE_READY = 2;

bool is_ready(const SharedControl& c) noexcept {
    return c.magic == EXPECTED_MAGIC &&
           c.version == EXPECTED_VERSION &&
           c.state == STATE_READY &&
           c.total_bytes >= sizeof(SharedControl);
}
```

La escritura de `state = READY` debe ser la publicación final, con orden de memoria apropiado.

**Estado:** N55 abierto.

## N56 — Reutilización del segmento con la misma identidad

Si un proceso destruye y recrea un segmento con el mismo nombre o ID, un consumidor puede confundir la instancia nueva con la vieja.

### Solución

Usar una identidad de instancia:

```text
segment_id
creation_nonce
boot_epoch
protocol_version
generation
```

```rust
#[repr(C)]
pub struct SegmentIdentity {
    pub segment_id: u64,
    pub creation_nonce: [u8; 16],
    pub protocol_major: u32,
    pub protocol_minor: u32,
    pub created_monotonic_ns: u64,
}
```

Un simple `SLAB_ID: AGENT_BUS_01` es insuficiente para distinguir generaciones de vida del objeto.

**Estado:** N56 abierto.

## N57 — Falta una regla para pérdida silenciosa de mensajes

El dossier habla de triple buffer y SPMC, pero no define si un consumidor que se retrasa:

```text
pierde estados;
recibe el último;
recibe todos;
debe ser expulsado;
bloquea al productor.
```

Estas semánticas son incompatibles entre sí.

### Solución

Declarar una política:

```rust
#[repr(u32)]
pub enum DeliveryMode {
    LatestOnly = 1,
    EveryPublishedState = 2,
    AtLeastOnce = 3,
    ExactlyOnce = 4,
}
```

No declarar `ExactlyOnce` sin:

- persistencia o journaling;
- acknowledgement;
- identificación de consumidor;
- recuperación tras crash;
- deduplicación;
- política de almacenamiento.

Para un triple buffer, el contrato realista suele ser:

```text
LatestOnly
```

Si el diseño necesita cada tensor, debe sustituirse por ring buffer o log secuencial.

**Estado:** N57 crítico y abierto.

## N58 — “Exactamente una vez” sería particularmente difícil aquí

Aunque el dossier no lo diga explícitamente, términos como `TENSOR_READY` pueden llevar a asumir entrega confiable. En un sistema con procesos que pueden morir, “exactly once” exige distinguir:

```text
publicado
observado
procesado
confirmado
persistido
```

Un consumidor que procesa y muere antes del ACK provoca duplicación al reintentar. Un ACK antes del procesamiento provoca pérdida.

La opción industrial suele ser:

```text
at-least-once + generation ID + idempotent consumer
```


### Idempotencia

```python
class IdempotentConsumer:
    def __init__(self):
        self.completed = set()

    def consume(self, generation, payload, process):
        if generation in self.completed:
            return "duplicate_ignored"

        process(payload)
        self.completed.add(generation)
        return "processed"
```

En producción, `completed` no puede ser solo memoria volátil si se necesita recuperación tras crash.

**Estado:** N58 abierto.

## N59 — La reducción OpenMP puede ser no reproducible aunque el schedule lo sea

El dossier exige `num_threads`, pero no muestra:

- `schedule`;
- `order`;
- `reduction`;
- número de parciales;
- árbol de combinación;
- afinidad;
- uso de FMA.

OpenMP especifica mecanismos de reducción paralela y opciones de reproducibilidad de schedule, pero una reducción reproducible requiere controlar también el orden de combinación, no solo la asignación de iteraciones.[^6_5][^6_6]

### Solución determinista

Dividir siempre en bloques fijos:

```cpp
struct Partial {
    double sum;
    double compensation;
};

Partial combine(Partial a, Partial b) noexcept {
    const double t = a.sum + b.sum;
    if (std::abs(a.sum) >= std::abs(b.sum)) {
        a.compensation += (a.sum - t) + b.sum;
    } else {
        a.compensation += (b.sum - t) + a.sum;
    }
    a.sum = t;
    return a;
}
```

Y combinar en un árbol fijo:

```cpp
while (count > 1) {
    std::size_t next = 0;
    for (std::size_t i = 0; i + 1 < count; i += 2) {
        partials[next++] = combine(partials[i], partials[i + 1]);
    }
    if (count % 2) {
        partials[next++] = partials[count - 1];
    }
    count = next;
}
```

Esto puede mejorar reproducibilidad, pero no prueba una cota universal ni garantiza igualdad entre arquitecturas.

**Estado:** N59 abierto.

## N60 — Los tests pueden validar la misma implementación contra sí misma

Un peligro de los “selftests” es:

```text
la implementación calcula el resultado;
el test recalcula usando la misma función auxiliar;
ambos comparten el mismo bug.
```

Ejemplo:

```text
selftest_compensation()
```

no es evidencia suficiente si usa las mismas rutinas de suma o el mismo orden de operaciones que el núcleo.

### Solución: referencia independiente

Usar al menos una de estas referencias:

```text
MPFR/Arb
long double independiente
Python Decimal con suficiente precisión
BLAS/LAPACK distinta
implementación lenta y clara
```

Y generar entradas adversariales con una semilla guardada:

```python
import random


def generate_case(seed, n):
    rng = random.Random(seed)
    return [
        ((-1.0) ** rng.randrange(2))
        * (2.0 ** rng.uniform(-500.0, 500.0))
        for _ in range(n)
    ]
```

El test debe guardar:

```text
seed
input hash
reference result
implementation result
error
compiler
platform
```

**Estado:** N60 abierto.

## N61 — El supuesto “D hasta 10.000.000” no define tamaño de muestra

La dimensión $D$ del vector no es lo mismo que:

```text
N = número de muestras
K = número de agentes
T = número de threads
E = número de edges del complejo
```

En un motor Vietoris–Rips, el coste puede depender de $N$, no solo de $D$. Para $N$ grande, construir aristas o distancias puede ser mucho más caro que recorrer un vector.

Si el dossier dice `N >= 1000`, debe definir:

```text
N máximo
radio de vecindad
métrica
representación de aristas
memoria
tiempo
aproximación
error topológico
```

No se puede extrapolar “funciona en $D=10^6$” a “funciona en un VR complex grande”.

**Estado:** N61 abierto.

## N62 — Betti-1 finito no equivale a homología de la esfera

Incluso si el motor calcula correctamente $\beta_1$ sobre un complejo construido con muestras, el resultado depende de:

- cobertura de la variedad;
- radio;
- ruido;
- densidad;
- métrica;
- conectividad;
- precisión;
- orientación;
- filtración.

Por tanto:

```text
β1(sampled VR complex) = 0
```

no implica automáticamente:

```text
β1(S^(D-1)) = 0
```

ni mucho menos:

```text
bus IPC correcto
```

El informe debe nombrarlo como:

```text
sampled_topological_observation
```

no como `manifold_security_certificate`.

**Estado:** N62 abierto.

## N63 — El uso de “asintóticamente estable” es demasiado amplio

La estabilidad asintótica suele referirse a una dinámica, algoritmo iterativo o sistema de control. La existencia de una rotación norm-preserving no prueba estabilidad asintótica.

Deben definirse:

```text
estado
dinámica
perturbación
norma
invariante
condición inicial
criterio de convergencia
```

Si no existe una iteración temporal, la expresión correcta podría ser:

```text
norm-preserving
backward stable
forward stable within tested domain
```

pero no “asintóticamente estable” sin una definición formal.

**Estado:** N63 error de especificación matemática.

## N64 — No se distingue seguridad de protección

“Memory-safe” puede significar varias cosas:

```text
sin UB en Rust seguro
sin UB en bloques unsafe
sin carreras
sin use-after-free
sin corrupción accidental
sin lectura de datos de otro tenant
sin acceso malicioso
```

Un sistema puede no tener UB local y aun así exponer datos de otro agente mediante un offset válido pero no autorizado.

### Solución: capability por segmento

```rust
#[repr(C)]
pub struct Capability {
    pub segment_id: u64,
    pub base_offset: u64,
    pub length: u64,
    pub rights: u32,
    pub generation: u64,
}
```

Validar toda lectura contra la capability, no solo contra el tamaño total del slab.

**Estado:** N64 crítico y abierto.

# Matriz del ciclo 5

| ID | Hallazgo | Severidad | Estado |
| :-- | :-- | --: | :-- |
| N51 | `repr(C)` sin contrato ABI completo | Alta | Abierto |
| N52 | Riesgo de campos desalineados con `packed` | Alta | Abierto |
| N53 | Endianness no definida | Alta | Abierto |
| N54 | `mmap` truncado puede provocar SIGBUS | Crítica | Abierto |
| N55 | Inicialización parcial del segmento | Crítica | Abierto |
| N56 | Reutilización de ID sin nonce/epoch | Alta | Abierto |
| N57 | Semántica de pérdida de mensajes no definida | Crítica | Abierto |
| N58 | “Exactly once” no especificado ni demostrable | Alta | Abierto |
| N59 | Reducción OpenMP no necesariamente reproducible | Alta | Abierto |
| N60 | Selftests potencialmente circulares | Alta | Abierto |
| N61 | Tamaño del complejo topológico no especificado | Alta | Abierto |
| N62 | $\beta_1$ muestreado confundido con propiedad exacta | Alta | Abierto |
| N63 | “Asintóticamente estable” sin sistema dinámico | Media | Abierto |
| N64 | Seguridad de memoria confundida con autorización | Crítica | Abierto |

# Veredicto no alucinado

```text
Confirmado por fuentes:
  - repr(C) define layout C-compatible, no toda portabilidad.
  - mmap truncado puede terminar en SIGBUS.
  - las reducciones y schedules OpenMP necesitan especificación para reproducibilidad.

No confirmado:
  - que V762 use punteros absolutos.
  - que use packed.
  - que su mmap pueda truncarse.
  - que prometa exactly-once.
  - que el motor topológico tenga el tamaño descrito.
  - que exista una capability de seguridad.

Conclusión:
  N51–N64 son gaps de especificación/evidencia,
  no bugs demostrados del código.
```

El próximo ciclo debe atacar la frontera que todavía no examinamos a fondo: **modelo de amenaza, aislamiento entre agentes, denegación de servicio, side channels, crash consistency y recuperación después de reinicio**.

<span style="display:none">[^6_10][^6_11][^6_12][^6_13][^6_14][^6_15][^6_16][^6_7][^6_8][^6_9]</span>

<div align="center">⁂</div>

[^6_1]: 03_MULTI_AI_TRIBUNAL_VERDICTS-2.md

[^6_2]: https://doc.rust-lang.org/nomicon/other-reprs.html

[^6_3]: https://doc.rust-lang.org/reference/type-layout.html

[^6_4]: https://manpages.ubuntu.com/manpages/focal/man2/mmap.2freebsd.html

[^6_5]: https://www.openmp.org/wp-content/uploads/openmp-TR10.pdf

[^6_6]: https://www.openmp.org/spec-html/5.2/openmpse27.html

[^6_7]: https://github.com/ANSSI-FR/rust-guide/blob/master/src/en/07_ffi.md

[^6_8]: https://users.rust-lang.org/t/clarification-repr-c-for-register-blocks/115629

[^6_9]: https://deepwiki.com/rust-lang/nomicon/3-data-layout

[^6_10]: https://www.rustfaq.org/en/how-to-pass-structs-between-rust-and-c/

[^6_11]: https://rustyyellowpages.dev/concepts/memory-unsafe/memory-layout-and-repr.html

[^6_12]: https://deepwiki.com/rust-lang/rfcs/7.1-ffi-and-c-interoperability

[^6_13]: https://web.mit.edu/rust-lang_v1.25/arch/amd64_ubuntu1404/share/doc/rust/html/unstable-book/language-features/repr-transparent.html

[^6_14]: https://devscampus.com/technologies/rust/learn/unsafe-rust/repr

[^6_15]: https://stackoverflow.com/questions/78285226/rust-public-abi-for-foreign-language-ffi

[^6_16]: https://web.mit.edu/rust-lang_v1.25/arch/amd64_ubuntu1404/share/doc/rust/html/book/first-edition/ffi.html


---

# Ciclo 6: fallos operativos y de seguridad

Sí: **no presentaré estos puntos como bugs confirmados del código**. Son riesgos que el dossier no descarta. La única evidencia recibida sigue siendo un documento declarativo de V762; no contiene implementación, modelo de amenaza, pruebas de reinicio, matriz de aislamiento ni logs de persistencia.[^7_1]

Las fuentes consultadas respaldan que la consistencia ante fallos requiere atomicidad, consistencia, aislamiento y durabilidad; que los ataques pueden modelarse con árboles de ataque; y que namespaces, cgroups y seccomp cumplen funciones distintas de visibilidad, límites y filtrado de syscalls.[^7_2][^7_3][^7_4][^7_5]

## N65 — No existe un modelo de amenaza formal

El dossier habla de agentes, shared memory y FFI, pero no define quién puede atacar a quién.

Debe especificar:

```text
Activos:
  - tensores
  - metadata
  - claves/checksums
  - disponibilidad
  - identidad de agentes

Actores:
  - agente honesto con bug
  - agente malicioso
  - productor comprometido
  - consumidor comprometido
  - usuario local no autorizado
  - proceso que muere
  - operador privilegiado

Capacidades:
  - leer slab
  - escribir slab
  - publicar tags
  - falsificar generación
  - agotar memoria
  - observar timing
  - matar procesos
  - modificar archivos
```


### Solución: amenaza verificable

```python
from dataclasses import dataclass
from enum import Enum


class Trust(Enum):
    TRUSTED = "trusted"
    BUGGY = "buggy"
    MALICIOUS = "malicious"


@dataclass(frozen=True)
class Actor:
    name: str
    trust: Trust
    can_read: bool
    can_write: bool
    can_kill_peer: bool
    can_consume_cpu: bool
    can_consume_memory: bool


@dataclass(frozen=True)
class Asset:
    name: str
    confidentiality: str
    integrity: str
    availability: str


@dataclass(frozen=True)
class Threat:
    actor: str
    asset: str
    action: str
    precondition: str
    impact: str
    control: str


def validate_threat(threat: Threat) -> None:
    fields = (
        threat.actor,
        threat.asset,
        threat.action,
        threat.precondition,
        threat.impact,
        threat.control,
    )
    if not all(field.strip() for field in fields):
        raise ValueError("incomplete threat record")
```

Un “modelo de amenaza” no es una lista narrativa: cada amenaza debe tener precondición, impacto, control y prueba de eficacia.

**Estado:** N65 crítico y abierto.

## N66 — Confundir aislamiento de procesos con aislamiento de datos

Separar agentes en procesos no impide automáticamente que compartan un slab con permisos excesivos. Un proceso aislado puede seguir leyendo toda la región si posee el descriptor y el mapping.

Hay que distinguir:

```text
aislamiento de ejecución
aislamiento de memoria virtual
aislamiento de permisos
aislamiento de datos por objeto
aislamiento de secretos
```


### Solución: capabilities

```rust
#[repr(C)]
pub struct Capability {
    pub agent_id: u64,
    pub segment_id: u64,
    pub offset: u64,
    pub length: u64,
    pub permissions: u32,
    pub generation: u64,
}

pub const READ: u32 = 1;
pub const WRITE: u32 = 2;

fn authorize(
    cap: &Capability,
    agent_id: u64,
    segment_id: u64,
    offset: u64,
    length: u64,
    requested: u32,
) -> Result<(), Status> {
    if cap.agent_id != agent_id || cap.segment_id != segment_id {
        return Err(Status::Unauthorized);
    }

    if cap.permissions & requested != requested {
        return Err(Status::Unauthorized);
    }

    let end = offset
        .checked_add(length)
        .ok_or(Status::AddressOverflow)?;

    let cap_end = cap
        .offset
        .checked_add(cap.length)
        .ok_or(Status::AddressOverflow)?;

    if offset < cap.offset || end > cap_end {
        return Err(Status::Unauthorized);
    }

    Ok(())
}
```

Esto protege autorización lógica; todavía se necesitan permisos del sistema operativo y una política para revocar capabilities.

**Estado:** N66 crítico y abierto.

## N67 — Namespaces no son una frontera completa

Los namespaces limitan la vista de recursos; no sustituyen:

- seccomp;
- cgroups;
- LSM;
- permisos de archivos;
- capabilities Linux;
- límites de memoria;
- límites de PIDs;
- control de red.

Una arquitectura que diga “cada agente está aislado en un namespace” todavía no demuestra que no pueda:

```text
agotar CPU;
agotar memoria;
crear procesos;
abrir archivos heredados;
usar syscalls peligrosas;
acceder a un descriptor compartido;
filtrar secretos por timing.
```

Los namespaces, cgroups y seccomp tienen responsabilidades diferentes; por eso deben evaluarse por separado.[^7_4][^7_5]

### Perfil mínimo conceptual

```text
namespaces:
  mount, pid, net, ipc, uts, user

cgroups:
  memory.max
  pids.max
  cpu.max
  io.max

seccomp:
  allowlist de syscalls
  rechazo de syscalls no usadas

filesystem:
  root mínimo
  solo lectura cuando sea posible
  sin sockets innecesarios

LSM:
  AppArmor o SELinux
```

No debe llamarse “sandbox fuerte” a un proceso que solo está dentro de un namespace.

**Estado:** N67 abierto.

## N68 — Denegación de servicio por tamaño anunciado

Un agente puede publicar:

```text
payload_bytes = 2^63 - 1
```

aunque el segmento real sea pequeño. Si el consumidor intenta reservar, recorrer o esperar esa cantidad, se produce:

- fallo de asignación;
- bloqueo;
- presión de memoria;
- latencia extrema;
- crash del proceso;
- agotamiento global.


### Solución: límites por capability y por agente

```rust
#[repr(C)]
pub struct ResourceQuota {
    pub max_payload_bytes: u64,
    pub max_inflight_bytes: u64,
    pub max_messages: u32,
    pub max_cpu_ns_per_window: u64,
    pub max_publish_rate: u32,
}

fn check_quota(
    quota: &ResourceQuota,
    payload_bytes: u64,
    inflight_bytes: u64,
    messages: u32,
) -> Result<(), Status> {
    if payload_bytes > quota.max_payload_bytes {
        return Err(Status::QuotaExceeded);
    }
    if inflight_bytes > quota.max_inflight_bytes {
        return Err(Status::QuotaExceeded);
    }
    if messages > quota.max_messages {
        return Err(Status::QuotaExceeded);
    }
    Ok(())
}
```

La cuota debe ser impuesta por el sistema operativo o por un supervisor confiable, no solo por el agente potencialmente malicioso.

**Estado:** N68 crítico y abierto.

## N69 — DoS por backpressure mal definido

Tres políticas posibles:

```text
bloquear productor
descartar mensaje nuevo
descartar mensaje viejo
expandir memoria
matar consumidor lento
```

Cada una tiene consecuencias. Si el productor bloquea, un agente puede detener todo el bus. Si se descarta sin métricas, se pierden estados silenciosamente. Si se expande memoria, aparece un DoS.

### Solución: backpressure explícita

```rust
#[repr(u32)]
pub enum BackpressurePolicy {
    RejectNewest = 1,
    DropOldest = 2,
    BlockWithDeadline = 3,
    IsolateSlowConsumer = 4,
}

#[repr(C)]
pub struct PublishResult {
    pub status: Status,
    pub dropped_messages: u64,
    pub blocked_ns: u64,
    pub queue_depth: u64,
}
```

Nunca devolver solo `bool`. Un consumidor debe saber si su publicación fue:

```text
aceptada
rechazada
descartada
retrasada
aceptada pero no durable
```

**Estado:** N69 abierto.

## N70 — Side channel por timing de errores

Aunque el contenido del tensor no se copie a texto, un agente puede inferir información por:

- tiempo de validación;
- número de reintentos;
- checksum;
- tamaño de payload;
- colisiones de caché;
- saturación de memoria;
- latencia de slots;
- respuesta distinta para “no autorizado” y “no existe”;
- duración de operaciones con NaN/subnormales.


### Solución

Definir qué metadatos pueden filtrarse:

```text
tamaño
dimensión
generación
latencia
ocupación
errores
actividad de otros agentes
```

Medidas posibles:

```text
mensajes de error uniformes
rate limiting
padding de tamaños
lotes de tiempo
particiones de memoria
no compartir contadores globales
capabilities separadas
```

No prometer resistencia total: los canales laterales de cache y scheduling no desaparecen por usar zero-copy.

**Estado:** N70 abierto.

## N71 — Side channel por disponibilidad

Un agente puede observar que la publicación se ralentiza cuando otro agente usa mucho CPU, memoria o ancho de banda. Aunque el contenido no se revele, la actividad sí puede filtrarse.

Pruebas:

```text
agente A carga el sistema
agente B mide publicación
comparar distribución de latencias
repetir con diferentes secretos/estados de A
```

La métrica debe ser:

```text
mutual information
classification accuracy
KS statistic
tail latency difference
```

Si el sistema necesita aislamiento fuerte, requiere particionamiento de recursos, no solo mutexes.

**Estado:** N71 abierto.

## N72 — Crash consistency de metadata y payload no está definida

Hay al menos tres escrituras distintas:

```text
payload
checksum
metadata/sequence
```

Si el proceso muere entre ellas, pueden quedar combinaciones inválidas:

```text
payload nuevo + metadata vieja
payload viejo + metadata nueva
checksum viejo + payload nuevo
generation nueva + datos incompletos
```


### Solución: copy-on-write + commit record

```text
1. reservar slot nuevo
2. escribir payload
3. calcular checksum
4. persistir payload/checksum
5. escribir commit record
6. persistir commit record
7. publicar generación
8. persistir índice raíz
```

Para recuperar:

```text
si commit válido:
    aceptar versión
si commit ausente/inválido:
    descartar slot
usar la última generación válida
```

Un esquema:

```rust
#[repr(C)]
pub struct CommitRecord {
    pub magic: u64,
    pub generation: u64,
    pub payload_offset: u64,
    pub payload_bytes: u64,
    pub checksum: u64,
    pub state: u32,
    pub reserved: u32,
}
```

No se debe escribir `READY` antes de que toda la información necesaria esté durable según el medio.

**Estado:** N72 crítico y abierto.

## N73 — `mmap` no equivale a persistencia ante energía

La memoria mapeada puede ser:

```text
anónima
file-backed
tmpfs
page cache
memoria persistente
```

Cada caso tiene propiedades distintas. “Está en mmap” no significa “sobrevive a power loss”.

El dossier debe definir:

```text
¿sobrevive crash de proceso?
¿sobrevive reboot?
¿sobrevive corte eléctrico?
¿qué hardware de almacenamiento?
¿hay batería o PLP?
¿qué flushes se ejecutan?
¿qué orden de persistencia se garantiza?
```

En memoria persistente, incluso metadata criptográfica y contadores deben tener atomicidad coherente; escribir datos y contador por separado puede dejar un estado irrecuperable.[^7_6]

## N74 — Falta prueba de power-loss real o inyectado

Una prueba de reinicio ordenado no equivale a corte eléctrico. Hay que probar varios niveles:

```text
kill -9
SIGKILL durante cada fase
crash inmediato
reboot
pérdida de energía inyectada
fallo de dispositivo
corrupción de una cache line
```


### Máquina de estados para recuperación

```python
from enum import Enum


class State(Enum):
    EMPTY = 0
    WRITING = 1
    PREPARED = 2
    COMMITTED = 3
    PUBLISHED = 4


VALID_AFTER_RECOVERY = {
    State.EMPTY,
    State.COMMITTED,
    State.PUBLISHED,
}


def recover(state, checksum_ok, bounds_ok):
    if state in (State.EMPTY,):
        return "empty"

    if state is State.WRITING:
        return "discard"

    if state is State.PREPARED:
        return "commit_if_log_proves_complete"

    if state in (State.COMMITTED, State.PUBLISHED):
        if checksum_ok and bounds_ok:
            return "accept"
        return "discard"

    raise ValueError("unknown state")
```

O resultado esperado debe ser definido antes de ejecutar el test.

**Estado:** N74 crítico y abierto.

## N75 — Falta de write-ahead log o shadow copy verificable

Dos patrones razonables:

### Write-ahead log

```text
log old/new metadata
flush log
modify data
flush data
mark committed
flush commit
```


### Shadow copy

```text
escribir versión nueva en región nueva
validar checksum
flush payload
publicar root pointer/generation
flush root
```

Para estructuras pequeñas, shadow copy suele ser más fácil de razonar. Para payloads grandes, puede ser costoso.

No se debe mezclar un log parcial con actualización in-place sin demostrar el orden exacto.

**Estado:** N75 abierto.

## N76 — Recuperación no idempotente

Si el proceso reinicia dos veces durante recovery, la operación debe producir el mismo estado que una sola recuperación.

Mal patrón:

```text
recovery incrementa generation
recovery vuelve a ejecutarse
generation incrementa otra vez
```

Buen patrón:

```text
recovery identifica commits existentes
reconstruye el estado desde records
no aplica una transición irreversible dos veces
```


### Test de idempotencia

```python
def recover_state(image):
    state = parse_image(image)
    first = recover_image(state)
    second = recover_image(first)
    return canonicalize(first) == canonicalize(second)
```

Debe verificarse:

```text
recover(recover(image)) == recover(image)
```

**Estado:** N76 abierto.

## N77 — No se define el punto de commit observado por consumidores

Un consumidor puede leer una generación durante la ventana:

```text
payload persistido
commit persistido
índice aún no publicado
```

o:

```text
índice publicado
payload todavía no durable
```

Debe existir una regla única:

```text
generation publicada = generation durable
```

o, si son distintas:

```text
published_generation
durable_generation
```

y el consumidor debe saber cuál está leyendo.

**Estado:** N77 abierto.

## N78 — Fallos de energía pueden corromper el medio, no solo perder la última escritura

No basta con recuperar “la última generación”. Hay que considerar:

```text
torn sector
torn cache line
metadata parcialmente escrita
reordenamiento de escrituras
checksum almacenado separadamente
dispositivo sin power-loss protection
```

Un checksum detecta corrupción, pero no recupera datos. Se necesita al menos:

```text
dos copias
versiones alternas
checksum por bloque
registro de commit
garbage collection segura
```

**Estado:** N78 abierto.

## N79 — Falta garbage collection segura

Si se usa copy-on-write, las versiones antiguas no pueden liberarse mientras:

```text
un consumidor tenga lease
un recovery pueda necesitarlas
un proceso viejo conserve un descriptor
```

La reclamación necesita una epoch global o ACK por consumidor.

```rust
#[repr(C)]
pub struct ConsumerEpoch {
    pub consumer_id: u64,
    pub observed_generation: u64,
    pub heartbeat_ns: u64,
    pub active: u32,
    pub reserved: u32,
}
```

Reclamar solo si:

```text
old_generation < min_active_observed_generation
```

y después de verificar consumidores muertos.

**Estado:** N79 crítico y abierto.

# Modelo formal de amenaza

## Propiedades que deben verificarse

Separar propiedades de seguridad:

```text
Confidencialidad:
  agente sin capability no puede leer payload ajeno.

Integridad:
  payload aceptado coincide con la generación publicada.

Disponibilidad:
  un agente no puede bloquear indefinidamente al resto.

Crash safety:
  recovery produce un estado válido.

Durabilidad:
  un commit confirmado sobrevive al fallo definido.

No interferencia:
  el timing observable no revela más de lo permitido.

Linealizabilidad:
  cada publish/read puede ordenarse coherentemente.
```

Una herramienta o prueba formal debe verificar cada propiedad por separado. No existe un único “test de seguridad”.

## Árbol de ataque mínimo

```text
Objetivo: impedir que el bus funcione correctamente

OR:
  - corromper payload
  - falsificar metadata
  - leer payload ajeno
  - agotar memoria
  - bloquear slots
  - matar productor
  - provocar recovery repetido
  - filtrar estado por timing

Corromper payload:
  - escribir sin capability
  - reutilizar slot durante lectura
  - explotar TOCTOU
  - provocar truncamiento/mmap inválido

Agotar memoria:
  - anunciar payload gigante
  - publicar sin límite
  - retener leases
  - impedir garbage collection
```

Los attack trees son un método reconocido para representar rutas de ataque y sus hojas; deben complementarse con controles y pruebas.[^7_3]

# Matriz del ciclo 6

| ID | Hallazgo | Severidad | Estado |
| :-- | :-- | --: | :-- |
| N65 | Modelo de amenaza no formalizado | Crítica | Abierto |
| N66 | Aislamiento de procesos no equivale a aislamiento de datos | Crítica | Abierto |
| N67 | Namespaces no sustituyen seccomp/cgroups/LSM | Alta | Abierto |
| N68 | DoS por tamaños anunciados | Crítica | Abierto |
| N69 | Backpressure no especificado | Alta | Abierto |
| N70 | Side channel por timing de errores | Alta | Abierto |
| N71 | Side channel por disponibilidad | Alta | Abierto |
| N72 | Metadata/payload sin protocolo atómico de commit | Crítica | Abierto |
| N73 | `mmap` confundido con persistencia | Crítica | Abierto |
| N74 | Sin prueba de power-loss o equivalente | Crítica | Abierto |
| N75 | Log/shadow copy no definido | Alta | Abierto |
| N76 | Recovery no demostrado idempotente | Alta | Abierto |
| N77 | Punto de commit no definido | Alta | Abierto |
| N78 | Corrupción de medio no cubierta | Crítica | Abierto |
| N79 | Garbage collection de versiones no resuelta | Crítica | Abierto |

# Veredicto

La mejora SOTA inmediata es dejar de hablar de “bus seguro” como una sola propiedad. Hay que convertirlo en cinco contratos verificables:

```text
1. Seguridad:
   capabilities, permisos, aislamiento y threat model.

2. Disponibilidad:
   cuotas, backpressure, timeouts y recuperación.

3. Crash consistency:
   estados, commits, logs/shadow copies e idempotencia.

4. Durabilidad:
   qué significa persistir y contra qué fallos.

5. Observabilidad:
   métricas que no filtren información sensible.
```

No confirmo que N65–N79 sean bugs ya presentes. Confirmo que **el dossier no aporta pruebas para descartarlos**, y que una certificación industrial no debería emitirse mientras sigan sin contrato y sin tests adversariales.

<span style="display:none">[^7_10][^7_11][^7_12][^7_13][^7_14][^7_15][^7_16][^7_7][^7_8][^7_9]</span>

<div align="center">⁂</div>

[^7_1]: 03_MULTI_AI_TRIBUNAL_VERDICTS-2.md

[^7_2]: https://www.cl.cam.ac.uk/teaching/1415/ConcDisSys/06-transactions-2up.pdf

[^7_3]: https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=919378

[^7_4]: https://www.man7.org/linux/man-pages/man7/namespaces.7.html

[^7_5]: https://archive.org/details/github.com-google-nsjail\_-\_2017-10-16_13-31-21

[^7_6]: https://www.microsoft.com/en-us/research/publication/crash-consistency-encrypted-non-volatile-main-memory-systems/

[^7_7]: https://www.cl.cam.ac.uk/~lc525/files/Linux_Containers.pdf

[^7_8]: https://www.microsoft.com/en-us/research/wp-content/uploads/2017/02/dudetm_asplos17.pdf

[^7_9]: https://learn.microsoft.com/en-us/windows-server/storage/storage-spaces/persistent-memory-health

[^7_10]: https://scholars.cityu.edu.hk/en/publications/c3-finding-counting-related-crash-consistency-atomicity-bugs-for-/

[^7_11]: https://ar5iv.labs.arxiv.org/html/2204.06066

[^7_12]: https://csyhua.github.io/csyhua/hua-dac2022-secon.pdf

[^7_13]: https://attackmodels.com/library/

[^7_14]: https://kernel-internals.org/cgroups/container-isolation/

[^7_15]: https://labhub.hopto.org/blog/linux/2026-06-13-kernel-cgroups-namespaces-container-internals?lang=en

[^7_16]: https://safeguard.sh/resources/blog/container-isolation-with-namespaces-cgroups-and-seccomp


---

## Ciclo 7: crash, FFI e aislamiento

Sí: **confirmo que no presentaré como hechos los puntos que no puedo probar**. En este ciclo distingo tres niveles:

```text
CONFIRMADO:
  lo que dice el dossier o una fuente normativa.

RIESGO DEMOSTRABLE:
  una propiedad que falta por diseño o por contrato.

NO VERIFICADO:
  podría existir en el código, pero no tengo la implementación.
```

Tu crítica sobre las 500 revisiones es válida. El proceso anterior fue ineficiente: produjo listas de riesgos, pero no pudo cerrar el sistema porque faltaba el código fuente y porque el dossier presentaba declaraciones como certificaciones. No voy a fingir que cuatro líneas por día pueden ser “perfectas” sin compilar, ejecutar y someter a pruebas adversariales.

El documento recibido solo afirma que A1–A12 están cerrados; no permite comprobarlo. Las fuentes oficiales consultadas confirman que el unwind FFI tiene reglas ABI específicas, que cgroups v2 puede imponer límites de memoria y que la recuperación debe tratarse como una capacidad operativa, no como una consecuencia automática de que un proceso reinicie.[^8_1][^8_2][^8_3][^8_4]

# N80 — Crash en mitad de una llamada FFI

La frontera FFI puede fallar en muchos puntos:

```text
antes de leer input
durante una validación
después de reservar output
durante la escritura
después de publicar metadata
antes de devolver rc
```

El dossier menciona `catch_unwind`, pero eso no cubre:

- `SIGSEGV`;
- `SIGBUS`;
- `SIGKILL`;
- OOM killer;
- abort del proceso;
- excepción C++ con ABI incorrecta;
- muerte del proceso que posee el buffer;
- corrupción del descriptor antes de la llamada.

El RFC de Rust define `C-unwind` para unwinding entre lenguajes y advierte que una combinación incompatible de panic runtime y ABI puede ser UB.[^8_4]

## Contrato FFI recomendado

El contrato público debe ser “no unwind”:

```rust
#[repr(C)]
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Ok = 0,
    Null = -1,
    InvalidArgument = -2,
    LengthOverflow = -3,
    OutOfBounds = -4,
    NonFinite = -5,
    Busy = -6,
    Timeout = -7,
    Unauthorized = -8,
    Internal = -9,
    PanicCaught = -10,
}

#[repr(C)]
pub struct Operation {
    pub input_segment: u64,
    pub input_offset: u64,
    pub input_bytes: u64,
    pub output_segment: u64,
    pub output_offset: u64,
    pub output_bytes: u64,
    pub generation: u64,
}
```

La función debe:

```text
1. validar todos los enteros;
2. verificar capability;
3. resolver offsets locales;
4. fijar leases;
5. ejecutar operación;
6. publicar output solo tras completar;
7. liberar leases en todos los caminos;
8. devolver un status;
9. no dejar pánico cruzar la ABI.
```


### Esqueleto de protección

```rust
use std::panic::{catch_unwind, AssertUnwindSafe};

#[unsafe(no_mangle)]
pub extern "C" fn polydim_execute(op: Operation) -> Status {
    let result = catch_unwind(AssertUnwindSafe(|| {
        execute_checked(op)
    }));

    match result {
        Ok(status) => status,
        Err(_) => Status::PanicCaught,
    }
}

fn execute_checked(op: Operation) -> Status {
    if op.input_bytes == 0 || op.output_bytes == 0 {
        return Status::InvalidArgument;
    }

    if op.generation == 0 {
        return Status::InvalidArgument;
    }

    // Aquí deben existir:
    // - validación de capability
    // - validación del segmento
    // - adquisición de leases
    // - validación de tamaños
    // - operación matemática
    // - publicación transaccional

    Status::Ok
}
```

Esto **no convierte un SIGBUS en un error Rust**. Solo evita que un panic normal cruce la frontera. La arquitectura debe prevenir mappings truncables, proteger el ciclo de vida y ejecutar el cálculo en un supervisor reiniciable.

**N80:** crítico, abierto.

# N81 — Estado huérfano después de morir el productor

Caso adversarial:

```text
1. productor adquiere slot;
2. marca WRITING;
3. escribe 40% del payload;
4. muere;
5. consumidor ve WRITING indefinidamente.
```

Sin timeout y lease, el sistema se bloquea. Con recuperación basada solo en tiempo, un productor lento puede ser declarado muerto erróneamente.

## Lease con epoch

```rust
#[repr(C)]
pub struct ProducerLease {
    pub producer_id: u64,
    pub lease_epoch: u64,
    pub heartbeat_ns: u64,
    pub deadline_ns: u64,
    pub state: u32,
}

pub const LEASE_ACTIVE: u32 = 1;
pub const LEASE_EXPIRED: u32 = 2;
pub const LEASE_REVOKED: u32 = 3;
```

Reglas:

```text
- el productor renueva el heartbeat;
- el reloj debe ser monotónico;
- un consumidor no reutiliza un slot solo por timeout;
- un supervisor valida que el proceso murió;
- la recuperación incrementa lease_epoch;
- una publicación antigua no puede volver a ser aceptada.
```

El `lease_epoch` evita aceptar un mensaje de un productor que reinició con el mismo `producer_id`.

**N81:** crítico, abierto.

# N82 — El proceso reiniciado puede heredar identidad vieja

Si el productor reinicia y reutiliza:

```text
producer_id = 7
generation = 42
```

un consumidor puede confundir el estado nuevo con el viejo. Eso habilita ABA lógico.

## Identidad de proceso

```rust
#[repr(C)]
pub struct ProcessIdentity {
    pub logical_agent_id: u64,
    pub boot_nonce: [u8; 16],
    pub process_start_ns: u64,
    pub protocol_epoch: u64,
}
```

El descriptor debe incluir:

```text
logical_agent_id
boot_nonce
protocol_epoch
generation
```

Un reinicio siempre crea una nueva identidad de sesión.

**N82:** crítico, abierto.

# N83 — No existe recuperación FFI de ownership

Supongamos:

```text
Python/Dart reserva input
Rust guarda puntero
Rust inicia worker
Python libera input
worker accede después
```

El resultado puede ser use-after-free.

O:

```text
Rust reserva output
Dart libera con allocator distinto
```

El resultado puede ser corrupción o crash.

## Regla de ownership

No guardar punteros extranjeros después del retorno salvo que exista un lease explícito. Preferir handles:

```rust
#[repr(C)]
pub struct BufferHandle {
    pub id: u64,
    pub generation: u64,
    pub bytes: u64,
}
```

La API debe tener pares claros:

```text
buffer_create -> handle
buffer_retain -> handle
buffer_release -> status
buffer_view -> temporal view
buffer_publish -> immutable generation
```

No deben cruzar la ABI:

```text
Vec<T>
String
&[T]
&mut [T]
Box<T>
trait objects
Rust enums sin repr
```

Para layout C compatible, Rust documenta el uso de `repr(C)`; aun así, la propiedad de memoria y el ciclo de vida deben definirse por separado.[^8_5][^8_6]

**N83:** crítico, abierto.

# N84 — UAF por ACK prematuro

Una secuencia peligrosa:

```text
1. consumidor lee metadata;
2. envía ACK;
3. productor libera/reutiliza slot;
4. consumidor todavía procesa payload.
```

El ACK debe significar exactamente una cosa:

```text
ACK_ACQUIRED:
  el consumidor tiene derecho a leer.

ACK_PROCESSED:
  terminó de procesar.

ACK_RELEASED:
  ya no usa memoria.
```

No usar un ACK ambiguo.

```rust
#[repr(u32)]
pub enum LeaseState {
    Acquired = 1,
    Processing = 2,
    Released = 3,
    Revoked = 4,
}
```

El productor solo puede reclamar después de `Released`, o tras una recuperación formal que pruebe que el consumidor murió.

**N84:** crítico, abierto.

# N85 — Deadlock entre leases, backpressure y recovery

Puede ocurrir:

```text
productor espera slot libre;
consumidor espera payload completo;
payload no se completa porque productor espera ACK;
ACK no llega porque consumidor espera el productor.
```

La arquitectura necesita un grafo de espera y límites de tiempo.

## Regla de no bloqueo indefinido

Toda operación de IPC debe aceptar:

```text
deadline
cancellation token
owner identity
```

```rust
#[repr(C)]
pub struct Deadline {
    pub monotonic_deadline_ns: u64,
    pub cancellation_epoch: u64,
}
```

Nunca hacer:

```text
while (!ready) {}
```

Preferir:

```text
while !ready {
    if now_monotonic() >= deadline {
        return Status::Timeout;
    }
    if cancelled() {
        return Status::Cancelled;
    }
    wait_with_backoff();
}
```

La espera activa sin límite puede ser un DoS incluso sin agente malicioso.

**N85:** alta, abierto.

# N86 — Aislamiento de procesos sin aislamiento de recursos

Una separación por procesos no evita que un agente consuma todos los recursos. Hay que imponer límites independientes:

```text
CPU
memoria
PIDs
file descriptors
mappings
disk
IOPS
network
cantidad de mensajes
bytes inflight
tiempo de lease
```

cgroups v2 dispone de mecanismos de límite de memoria y puede activar el OOM killer dentro del grupo cuando se alcanza el límite efectivo.[^8_2]

### Matriz operativa

| Recurso | Límite | Acción al superar | Evidencia |
| :-- | --: | :-- | :-- |
| Memoria | `memory.max` | matar agente o rechazar publicación | log + cgroup events |
| CPU | `cpu.max` | throttling | `cpu.stat` |
| Procesos | `pids.max` | rechazar fork/clone | evento kernel |
| FDs | `RLIMIT_NOFILE` | rechazar apertura | error contabilizado |
| Slabs | cuota por agente | `QuotaExceeded` | contador |
| Leases | máximo activo | rechazar adquisición | métrica |
| Mensajes | tasa máxima | backpressure | histograma |

**N86:** crítico, abierto.

# N87 — Denegación de servicio por consumidor que retiene leases

Un consumidor puede adquirir muchos slots y nunca liberarlos. Esto impide garbage collection y bloquea al productor.

### Solución

```text
máximo de leases por agente
deadline por lease
heartbeat
revocación supervisada
cuota de bytes retenidos
penalización progresiva
```

La revocación debe invalidar el lease mediante epoch:

```rust
fn lease_valid(
    issued_epoch: u64,
    current_epoch: u64,
    now_ns: u64,
    deadline_ns: u64,
) -> bool {
    issued_epoch == current_epoch && now_ns < deadline_ns
}
```

Un consumidor muerto no debe conservar memoria indefinidamente.

**N87:** crítico, abierto.

# N88 — Side channel por tamaño y tasa de mensajes

Aunque no se transmitan tokens ni JSON, el bus puede filtrar:

```text
dimensión
cantidad de agentes activos
frecuencia de publicación
tamaño de tensores
tiempo de cálculo
número de reintentos
```

Si esos datos dependen del contenido, otro agente puede inferir estados privados.

## Mitigaciones posibles

```text
- tamaños por clases/padding;
- ventanas de publicación;
- cuotas y tasas uniformes;
- respuestas indistinguibles;
- no compartir contadores globales;
- separar buses por nivel de confianza;
- evitar que el consumidor consulte ocupación ajena.
```

Ninguna garantiza “side-channel free”. La propiedad debe expresarse como límite de información observable.

**N88:** alta, abierto.

# N89 — Crash consistency del control y del payload

Un diseño sin persistencia debe decirlo claramente:

```text
solo crash safety del proceso;
se pierde estado en reboot;
no hay garantía ante power loss.
```

Si se promete persistencia, hay que separar:

```text
payload data
checksum
commit record
root/index
generation
```


### Shadow-copy recomendado

```text
old_root -> versión estable

1. escribir payload nuevo en región libre
2. escribir checksum
3. verificar checksum
4. flush del payload
5. escribir commit record
6. flush del commit
7. publicar root nuevo
8. flush del root
9. reclamar root viejo después de grace period
```

Para recuperación:

```text
si root nuevo válido y commit válido:
    usar root nuevo
si no:
    usar root anterior
```

Los sistemas de memoria persistente requieren mecanismos explícitos de crash consistency; escribir directamente en memoria no hace que una transacción sea atómica.[^8_7][^8_8]

**N89:** crítico, abierto.

# N90 — Reinicio simultáneo produce dos líderes

Si productor y supervisor reinician a la vez, ambos pueden creer que poseen el bus. Entonces aparecen dos escritores sobre el mismo slot.

## Elección de líder

```text
leader_epoch
fencing_token
owner_nonce
```

Cada operación de escritura debe incluir el token actual:

```rust
#[repr(C)]
pub struct FencingToken {
    pub owner_id: u64,
    pub epoch: u64,
    pub nonce: [u8; 16],
}
```

El slot rechaza cualquier escritura con token inferior o distinto del líder actual.

**N90:** crítico, abierto.

# N91 — Recuperación puede aceptar una generación parcialmente escrita

No basta con:

```text
generation != 0
```

La generación debe corresponder a:

```text
payload completo
checksum correcto
metadata válida
commit record válido
bounds válidos
protocol version compatible
```


### Validador

```rust
fn valid_commit(
    commit: &CommitRecord,
    segment_bytes: u64,
    actual_checksum: u64,
) -> bool {
    if commit.magic != COMMIT_MAGIC {
        return false;
    }

    let end = match commit.payload_offset.checked_add(commit.payload_bytes) {
        Some(end) => end,
        None => return false,
    };

    if end > segment_bytes {
        return false;
    }

    commit.payload_bytes != 0 &&
    commit.checksum == actual_checksum &&
    commit.state == COMMITTED
}
```

El código debe rechazar cualquier combinación ambigua y registrar la razón.

**N91:** crítico, abierto.

# N92 — No hay pruebas de recuperación diferencial

No probar solo:

```text
arranca limpio
publica
reinicia
lee
```

Probar todas las interrupciones:

```text
antes de payload
mitad de payload
después de payload
antes de checksum
después de checksum
antes de commit
después de commit
antes de root
después de root
durante garbage collection
durante ACK
```


### Modelo de inyección

```python
PHASES = [
    "before_payload",
    "mid_payload",
    "after_payload",
    "before_checksum",
    "after_checksum",
    "before_commit",
    "after_commit",
    "before_root",
    "after_root",
    "during_gc",
    "during_ack",
]


def expected_after_crash(phase):
    if phase in {"after_root"}:
        return "new_generation_or_previous_valid"
    if phase in {"after_commit", "before_root"}:
        return "new_generation_recoverable"
    return "previous_generation"
```

La tabla exacta debe definirse junto con el protocolo.

**N92:** crítico, abierto.

# N93 — No se prueba monotonicidad después de recovery

Después de reiniciar, debe cumplirse:

```text
accepted_generation_new >= accepted_generation_old
```

salvo que el contrato permita rollback explícito.

### Propiedad

```python
def assert_monotonic_generations(generations):
    for before, after in zip(generations, generations[1:]):
        if after < before:
            raise AssertionError(
                f"generation rollback: {before} -> {after}"
            )
```

Si hay rollback por corrupción, debe informarse como evento de seguridad, no ocultarse.

**N93:** alta, abierto.

# N94 — Logs de recovery pueden filtrar secretos

Los logs podrían registrar:

```text
offsets
tamaños
generaciones
hashes
fallos de checksum
identidades de agentes
latencias
```

Incluso si no contienen payload, pueden revelar actividad o estructura del sistema.

Debe existir una política:

```text
log público
log operador
log forense
log confidencial
```

Y el contenido debe minimizarse.

**N94:** media/alta, abierto.

# Modelo de amenaza mínimo exigible

```text
Activos:
  A1 payload
  A2 metadata
  A3 identidad
  A4 disponibilidad
  A5 claves/capabilities
  A6 historial de generaciones

Actores:
  T1 agente buggy
  T2 agente malicioso
  T3 productor muerto
  T4 consumidor lento
  T5 proceso reiniciado
  T6 usuario local no autorizado
  T7 fallo de energía
  T8 truncamiento/corrupción del medio

Propiedades:
  P1 no leer sin capability
  P2 no escribir sin capability
  P3 no aceptar payload incompleto
  P4 no bloquear indefinidamente
  P5 recovery idempotente
  P6 generaciones monotónicas
  P7 versiones antiguas reclamadas solo con seguridad
  P8 errores observables sin filtrar secretos
```

Cada par actor/activo debe producir una prueba o una justificación de exclusión.

# Matriz de aislamiento propuesta

| Capa | Protege contra | Mecanismo | No resuelve |
| :-- | :-- | :-- | :-- |
| Proceso separado | corrupción directa de heap | PID distinto | acceso a shared memory |
| User namespace | privilegios | UID/GID aislados | side channels |
| Mount namespace | archivos visibles | filesystem aislado | kernel bugs |
| Network namespace | red | interfaz separada | CPU/memoria |
| Seccomp | syscalls peligrosas | allowlist | abuso de syscalls permitidas |
| cgroups | DoS de recursos | cuotas | lectura de datos autorizados |
| Capabilities | acceso por objeto | offsets/permisos | fuga por timing |
| MAC/LSM | política de acceso | AppArmor/SELinux | errores de protocolo |
| Criptografía | confidencialidad | encryption/MAC | disponibilidad |
| Supervisor | crash/restart | health + fencing | bug lógico del protocolo |

La conclusión importante es que **ninguna capa sustituye a las demás**.

# Hallazgos del ciclo 7

| ID | Hallazgo | Severidad | Estado |
| :-- | :-- | --: | :-- |
| N80 | Crash durante llamada FFI | Crítica | Abierto |
| N81 | Slot huérfano tras muerte del productor | Crítica | Abierto |
| N82 | Identidad vieja después de reinicio | Crítica | Abierto |
| N83 | Ownership FFI no formalizado | Crítica | Abierto |
| N84 | ACK prematuro y UAF | Crítica | Abierto |
| N85 | Deadlock entre leases/backpressure/recovery | Alta | Abierto |
| N86 | Aislamiento sin cuotas de recursos | Crítica | Abierto |
| N87 | DoS reteniendo leases | Crítica | Abierto |
| N88 | Side channels por tamaño/tasa | Alta | Abierto |
| N89 | Crash consistency payload/control | Crítica | Abierto |
| N90 | Dos líderes después de reinicio | Crítica | Abierto |
| N91 | Recovery acepta generación parcial | Crítica | Abierto |
| N92 | Sin inyección diferencial de crashes | Crítica | Abierto |
| N93 | Rollback de generaciones no definido | Alta | Abierto |
| N94 | Logs pueden filtrar información | Media/alta | Abierto |

# Veredicto final del ciclo

La afirmación correcta hoy es:

```text
El dossier no demuestra que POLYDIM V762 sobreviva:
  - crash dentro de FFI;
  - muerte del productor;
  - reinicio con identidad reutilizada;
  - consumidor que retiene leases;
  - dos líderes simultáneos;
  - power loss;
  - recuperación repetida;
  - presión de memoria;
  - side channels de disponibilidad.
```

Eso **no prueba que el código falle**. Prueba que la certificación es prematura.

Para pasar de papel SOTA a industria, el cierre debe exigir:

```text
1. Threat model firmado.
2. Capability matrix por agente.
3. Lease/fencing protocol.
4. Crash state machine.
5. Shadow-copy o WAL.
6. Recovery idempotente.
7. Fault injection por fase.
8. cgroup/seccomp/LSM matrix.
9. Side-channel budget.
10. Logs y artefactos reproducibles.
```

Y una corrección de proceso: no voy a seguir produciendo “soluciones finales” específicas de Rust/C++ como si ya conociera el monolito. Esos fragmentos son diseños de referencia, no parches validados. El siguiente salto real requiere que adjuntes el código fuente, porque sin él solo podemos seguir descubriendo vacíos del dossier, no cerrar defectos de implementación.

<span style="display:none">[^8_10][^8_11][^8_12][^8_13][^8_14][^8_15][^8_16][^8_17][^8_18][^8_19][^8_20][^8_9]</span>

<div align="center">⁂</div>

[^8_1]: 03_MULTI_AI_TRIBUNAL_VERDICTS-2.md

[^8_2]: https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html

[^8_3]: https://csrc.nist.gov/pubs/sp/800/61/r3/final

[^8_4]: https://rust-lang.github.io/rfcs/2945-c-unwind-abi.html

[^8_5]: https://doc.rust-lang.org/nomicon/other-reprs.html

[^8_6]: https://doc.rust-lang.org/reference/type-layout.html

[^8_7]: https://www.microsoft.com/en-us/research/publication/crash-consistency-encrypted-non-volatile-main-memory-systems/

[^8_8]: https://www.microsoft.com/en-us/research/wp-content/uploads/2017/02/dudetm_asplos17.pdf

[^8_9]: https://www.nist.gov/news-events/news/2025/04/nist-revises-sp-800-61-incident-response-recommendations-and-considerations

[^8_10]: https://csrc.nist.gov/pubs/sp/800/61/r2/final

[^8_11]: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf

[^8_12]: https://csrc.nist.gov/pubs/sp/800/61/r1/final

[^8_13]: https://man7.org/conf/lceu2016/cgroups-LinuxCon.eu_2016-Kerrisk.pdf

[^8_14]: https://doc.rust-lang.org/nomicon/ffi.html

[^8_15]: https://doc.rust-lang.org/beta/nomicon/ffi.html

[^8_16]: https://doc.rust-lang.org/stable/nomicon/ffi.html

[^8_17]: https://internals.rust-lang.org/t/unhandled-panics-in-rust-vs-in-ffi/17981

[^8_18]: https://deepwiki.com/rust-lang/nomicon/11.1-calling-foreign-functions

[^8_19]: https://deepwiki.com/rust-lang/nomicon/11-foreign-function-interface-(ffi)

[^8_20]: https://deepwiki.com/rust-lang/nomicon/12.2-panic-handling

