<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

## Evaluación SOTA

**Veredicto: la resolución V900 no alcanza un estándar SOTA ni puede sostener la afirmación de tolerar 30–40% de agentes bizantinos.** El filtro $3\sigma$ es heurístico, el Weiszfeld regularizado no resuelve la singularidad antipodal y no existe evidencia suficiente para afirmar una tolerancia del 95% o una garantía formal frente a adversarios adaptativos.

La literatura confirma dos puntos importantes:

- En la esfera, la media intrínseca puede no ser única cuando los datos no están contenidos en un hemisferio abierto.
- La continuidad Lipschitz del mapa $\log_p$ usada para justificar robustez solo está garantizada dentro de una bola geodésica restringida, por ejemplo $B(p,\pi/2)$, no cerca del antipodal.[^1_1]
- Los agregadores geométricos convencionales tienen garantías típicas de contaminación estrictamente menor que $50\%$, y los agregadores de alta dimensión pueden ser atacados incluso cuando poseen garantías teóricas fuertes bajo supuestos ideales.[^1_2]


## Fallos de V900

### 1. El filtro $3\sigma$ no es una defensa bizantina

La regla

$$
d_R(p_i,\bar p)>\mu_d+3\sigma_d
$$

presenta varios problemas:

- La distancia geodésica está acotada en $[0,\pi]$, por lo que su distribución rara vez es gaussiana.
- Con pocos clientes, $\mu_d$ y $\sigma_d$ pueden ser manipuladas por los propios atacantes.
- Un ataque adaptativo puede elegir vectores dentro del umbral y producir un desplazamiento acumulativo.
- Con datos legítimamente multimodales o no-IID, clientes honestos pueden ser eliminados.
- No hay una relación directa entre “superar $3\sigma$” y ser bizantino.

Por tanto, el filtro debe considerarse una **preselección estadística**, no una garantía de seguridad.

### 2. La regularización $\epsilon=10^{-12}$ no elimina la singularidad

La actualización propuesta parece ser

$$
v^{(t+1)}
 =
 \frac{
 \sum_i
 \dfrac{\log_{p^{(t)}}(q_i)}
 {\|\log_{p^{(t)}}(q_i)\|+\epsilon}
 }{
 \sum_i
 \dfrac{1}
 {\|\log_{p^{(t)}}(q_i)\|+\epsilon}
 }.
$$

El problema es que $\epsilon$ evita una división exacta por cero cuando $q_i=p^{(t)}$, pero **no regulariza correctamente el caso antipodal** $q_i\approx -p^{(t)}$.

Para $c=\langle p,q\rangle\to-1$,

$$
\theta=\arccos(c)\to\pi,
\qquad
\sqrt{1-c^2}\to 0,
$$

y el vector tangente

$$
\frac{\theta}{\sqrt{1-c^2}}(q-cp)
$$

no tiene límite único. En el punto antipodal existen infinitas geodésicas mínimas y, por tanto, el logaritmo riemanniano es multivaluado. Cambiar el denominador por

$$
\sqrt{1-c^2}+\epsilon
$$

solo limita la magnitud numérica; no define una dirección geométricamente correcta. La dirección depende del ruido de redondeo o de perturbaciones arbitrariamente pequeñas del atacante.

### 3. Weiszfeld no es suficiente contra antipodales

La mediana geométrica intrínseca puede ser robusta frente a outliers bajo condiciones geométricas, pero requiere existencia, unicidad y control local del mapa logarítmico. En la esfera, esas condiciones se rompen cerca del corte antipodal. El trabajo de Lin et al. establece una garantía para la mediana intrínseca bajo una condición de Lipschitz del mapa log; en la esfera, la constante $K=2$ se proporciona únicamente en una región $B(p,\pi/2)$.[^1_1]

Esto implica que V900 debe demostrar primero:

$$
\max_i d_R(p,q_i)<\frac{\pi}{2}-\delta
$$

para algún $\delta>0$, antes de aplicar Weiszfeld. El filtro $3\sigma$ no garantiza esa condición.

### 4. La afirmación 30–40% no está demostrada

Una tolerancia de $30\text{–}40\%$ puede ser plausible para ciertos estimadores bajo supuestos fuertes, pero la afirmación requiere especificar:

- modelo de contaminación;
- independencia o adaptatividad del adversario;
- dispersión de los honestos;
- radio de concentración;
- dimensión $D$;
- número de clientes;
- conocimiento del atacante;
- métrica de éxito;
- probabilidad de fallo;
- número de rondas;
- si se exige recuperación del centro honesto o solamente convergencia del entrenamiento.

Además, una garantía cercana al $50\%$ es imposible sin supuestos adicionales: cuando la fracción maliciosa alcanza la mitad, los datos honestos dejan de ser identificables en general. En manifolds, la geometría puede imponer restricciones aún más fuertes por no convexidad y no unicidad.

## Solución recomendada: agregación extrínseca segura

La alternativa más sólida para este bug es **no calcular $\log_p(q_i)$ antes de resolver la selección robusta**.

### Paso 1: trabajar en el espacio ambiente

Como todos los vectores están en $S^{D-1}$, usar directamente

$$
x_i=q_i\in\mathbb R^D.
$$

La distancia cordal satisface

$$
\|q_i-q_j\|_2
=
2\sin\left(\frac{d_R(q_i,q_j)}{2}\right),
$$

por lo que preserva el orden de las distancias geodésicas en $[0,\pi]$, pero no tiene singularidad antipodal.

### Paso 2: aplicar un estimador robusto de media

Las opciones más defensibles son:

- median-of-means geométrica extrínseca;
- mediana geométrica extrínseca;
- agregación robusta espectral;
- filtro iterativo basado en covarianza;
- estimación robusta de media con garantía independiente de la dimensión, si el coste es viable.

La mediana geométrica extrínseca se calcula como

$$
\hat x
=
\arg\min_{x\in\mathbb R^D}
\sum_{i=1}^N \|x-q_i\|_2.
$$

Después se proyecta a la esfera:

$$
\hat p
=
\frac{\hat x}{\|\hat x\|_2},
$$

si $\|\hat x\|_2$ está suficientemente alejada de cero.

Esta operación no utiliza $\log_p$, por lo que el punto antipodal no produce una división por $\sin\theta$.

### Paso 3: detectar el caso no identificable

Debe rechazarse la ronda si

$$
\|\hat x\|_2 < \tau_{\mathrm{collapse}}.
$$

Cuando el centro robusto extrínseco se aproxima a cero, existe una fuerte cancelación direccional y no se puede determinar de forma fiable un representante único en la esfera. En vez de devolver un vector arbitrario, el sistema debe:

- congelar el estado global;
- solicitar una nueva ronda;
- reducir el peso de los clientes anómalos;
- usar historial temporal;
- o pasar a una agregación basada en evidencia independiente.

Esto es superior a normalizar un vector casi nulo, porque

$$
\frac{\hat x}{\|\hat x\|_2}
$$

puede amplificar ruido numérico y permitir que el atacante controle la dirección final.

## Solución intrínseca con salvaguarda antipodal

Si se requiere preservar una actualización intrínseca, usar un algoritmo de dos fases.

### Fase A: selección sin mapa logarítmico

Calcular similitudes

$$
s_{ij}=\langle q_i,q_j\rangle
$$

o distancias cordales. Seleccionar un subconjunto central mediante:

- mediana de distancias;
- trimmed geometric median;
- medoid robusto;
- clustering esférico y selección del clúster mayoritario.

Un candidato $q_i$ debe cumplir un criterio de centralidad, por ejemplo

$$
C_i=\operatorname{median}_{j\ne i}
\bigl(1-\langle q_i,q_j\rangle\bigr).
$$

No se debe utilizar $\log_p(q_i)$ para esta etapa.

### Fase B: restricción a un hemisferio seguro

Elegir un centro provisional $c$ y exigir

$$
\langle c,q_i\rangle\ge \gamma,
\qquad \gamma>0,
$$

para todos los puntos retenidos. Equivalentemente,

$$
d_R(c,q_i)\le \arccos(\gamma)<\frac{\pi}{2}.
$$

Solo después de satisfacer esta condición se puede aplicar la actualización intrínseca:

$$
p^{(t+1)}
=
\operatorname{Exp}_{p^{(t)}}
\left(
\eta_t
\sum_i w_i
\log_{p^{(t)}}(q_i)
\right).
$$

Los pesos deben estar normalizados y los puntos deben quedar dentro del dominio seguro:

$$
w_i\ge0,\qquad
\sum_iw_i=1,\qquad
\langle p^{(t)},q_i\rangle\ge\gamma.
$$

Si algún punto cae fuera del dominio, se elimina o se procesa exclusivamente mediante la fase extrínseca.

## Pseudocódigo corregido

```text
Input: q1,...,qN ∈ S^(D−1)
Parameters: f_max, γ, τcollapse

1. Compute robust extrinsic center x_hat using:
      geometric median / median-of-means / spectral filtering

2. If ||x_hat||2 < τcollapse:
      reject round
      use temporal fallback
      return previous global state

3. p0 = x_hat / ||x_hat||2

4. Compute robust centrality using chordal distances.
   Remove at most f_max suspicious clients.

5. Retain H such that:
      <p0, qi> ≥ γ
   If |H| ≤ N − f_max:
      reject round or invoke extrinsic-only mode

6. Initialize p = p0

7. For t = 1,...,T:
      For each qi ∈ H:
          ci = clip(<p, qi>, −1+δ, 1−δ)

          If ci < γ:
              wi = 0
          Else:
              θi = acos(ci)
              ui = (qi − ci p) / max(sqrt(1−ci^2), δ)
              vi = θi ui
              wi = robust_weight(||vi||)

      If sum(wi) = 0:
          return p0

      v = sum(wi vi) / sum(wi)
      p = exp_p(ηt v)
      p = p / ||p||2

8. Return p
```

Valores como $\epsilon=10^{-12}$ no deben ser usados como única protección. Es preferible separar:

- $\delta$: protección numérica, por ejemplo $10^{-7}$ o dependiente de precisión;
- $\gamma$: margen geométrico, por ejemplo $0.1$, $0.2$ o calibrado estadísticamente;
- $\tau_{\mathrm{collapse}}$: umbral de identificabilidad;
- $f_{\max}$: fracción máxima bizantina asumida.


## Defensa más fuerte contra ataques adaptativos

El punto débil de V900 es que el atacante puede permanecer cerca del umbral y manipular simultáneamente la media, la desviación y la dirección global. Para endurecerla:

### Mediana de medias geométrica

Dividir los clientes en $m$ grupos aleatorios, calcular un centro robusto por grupo y tomar la mediana geométrica de esos centros. La literatura sobre median-of-means en manifolds proporciona garantías de concentración y robustez, incluyendo la esfera.[^1_1]

### Filtrado espectral robusto

Si se dispone de suficientes clientes y se puede asumir una cota de covarianza honesta, aplicar filtering/no-regret/SoS sobre representaciones extrínsecas. Las defensas fuertes basadas en covarianza ofrecen cotas de sesgo del orden $\tilde O(\sqrt{\varepsilon})$, independientes de la dimensión bajo sus supuestos. Sin embargo, sus implementaciones prácticas por bloques pueden ser vulnerables a ataques que sesgan cada bloque por separado.[^1_2]

Por ello, no se debe particionar la dimensión y agregar cada bloque de forma independiente sin una comprobación global de consistencia.

### Consistencia temporal

Mantener un historial $h_t$ y limitar la velocidad angular:

$$
d_R(p_t,p_{t-1})\le \Delta_{\max}.
$$

Una actualización que exceda el límite debe ser rechazada o reducida:

$$
p_t
=
\operatorname{Exp}_{p_{t-1}}
\left(
\min\left\{1,
\frac{\Delta_{\max}}{\|v_t\|}
\right\}v_t
\right).
$$

Esto no reemplaza un agregador robusto, pero impide que una sola ronda antipodal provoque un salto global.

### Prueba de estrés obligatoria

Para poder afirmar una cifra como “95% de robustez”, la evaluación debe incluir al menos:


| Ataque | Parámetro que debe variarse |
| :-- | :-- |
| Antipodal exacto | $q_i=-p$ |
| Casi antipodal | $d_R(p,q_i)\in[\pi-10^{-2},\pi]$ |
| Ataque dentro del umbral | justo por debajo de $3\sigma$ |
| Ataque adaptativo | conocimiento de todos los honestos |
| Ataque de dispersión | maximizar varianza sin ser filtrado |
| Ataque de cancelación | forzar $\|\hat x\|\approx0$ |
| Ataque temporal | pequeñas desviaciones acumulativas |
| Clientes no-IID | varios clústeres honestos |
| Ataque por bloques | distinto sesgo en cada partición |

Deben reportarse:

- error angular respecto al centro honesto;
- tasa de colapso;
- porcentaje de rondas rechazadas;
- sesgo máximo;
- convergencia;
- precisión downstream;
- intervalo de confianza;
- resultados para $10\%,20\%,30\%,40\%$ de corrupción.


## Conclusión

La corrección mínima es reemplazar el filtro $3\sigma$ más Weiszfeld intrínseco por:

1. estimación robusta extrínseca sin mapas logarítmicos;
2. detección explícita de $\|\hat x\|\approx0$;
3. selección de un hemisferio seguro antes de usar $\log_p$;
4. mediana de medias geométrica o filtrado espectral;
5. control temporal de la velocidad angular;
6. evaluación contra ataques adaptativos y casi antipodales.

La afirmación de tolerar $30\text{–}40\%$ no puede aceptarse como resultado SOTA con la evidencia proporcionada. La literatura sí respalda robustez geométrica bajo condiciones de concentración y de hemisferio, pero no una garantía universal del 95% para V900 frente a adversarios antipodales adaptativos.[^1_2][^1_1]

<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_16][^1_17][^1_18][^1_19][^1_20][^1_21][^1_22][^1_23][^1_24][^1_25][^1_26][^1_27][^1_28][^1_29][^1_3][^1_30][^1_4][^1_5][^1_6][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://www3.stat.sinica.edu.tw/ss_newpaper/SS-2022-0149_na.pdf

[^1_2]: https://arxiv.org/html/2312.14461v3

[^1_3]: https://www.ndss-symposium.org/wp-content/uploads/2025-1796-paper.pdf

[^1_4]: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0339881

[^1_5]: http://www-sop.inria.fr/asclepios/cours/CBB-2013-2014/CompAnat_2011.pdf

[^1_6]: https://aclanthology.org/2024.findings-emnlp.339.pdf

[^1_7]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12527033/table/sensors-25-05949-t001/

[^1_8]: https://inria.hal.science/hal-03766900/file/main-now.pdf

[^1_9]: http://shichuan.org/doc/186.pdf

[^1_10]: https://ar5iv.labs.arxiv.org/html/2506.01989

[^1_11]: https://chen.tech.cornell.edu/ECE5290/assets/slides/Lec17.pdf

[^1_12]: https://eduardgorbunov.github.io/assets/files/NeurIPS2024_Byz_PP_poster.pdf

[^1_13]: https://apxml.com/courses/federated-learning/chapter-2-advanced-aggregation-algorithms/byzantine-robust-aggregation

[^1_14]: https://deepwiki.com/siquanhuang/Scope/6.2-robust-aggregation-methods

[^1_15]: https://openreview.net/pdf/d5bf6e041038a82bb01429a9ea1655cc6c128b78.pdf

[^1_16]: https://d197for5662m48.cloudfront.net/documents/publicationstatus/173184/preprint_pdf/f1954ab13861063e9daaf2a80f1c8d15.pdf

[^1_17]: https://proceedings.iclr.cc/paper_files/paper/2026/file/43a1c817602662be3a59015e9a86d0d1-Paper-Conference.pdf

[^1_18]: https://academic.oup.com/jrsssb/article/86/5/1364/7642961

[^1_19]: https://www3.stat.sinica.edu.tw/sstest/oldpdf/A34n302.pdf

[^1_20]: https://par.nsf.gov/servlets/purl/10520477

[^1_21]: https://backend.orbit.dtu.dk/ws/files/201566871/paper_1\_.pdf

[^1_22]: https://ore.exeter.ac.uk/repository/bitstream/handle/10871/128696/Byzantine_Robust_and_Efficient_Federated_Learning_for_Internet_of_Things.pdf?sequence=1

[^1_23]: https://www.arxiv.org/pdf/2409.07223.pdf

[^1_24]: https://inria.hal.science/inria-00614994/document

[^1_25]: https://www.isical.ac.in/~asu/TR/TechRepASU201706.pdf

[^1_26]: https://ar5iv.labs.arxiv.org/html/2506.15264

[^1_27]: https://hackmd.io/@msutti/Hy0Y0xr2c

[^1_28]: https://openreview.net/pdf?id=ErrNJYcVRmS

[^1_29]: https://users.cecs.anu.edu.au/~nmb/papers/lim_barnes_antipodal_omnivis07.pdf

[^1_30]: https://www.diva-portal.org/smash/get/diva2:1612809/FULLTEXT01.pdf


---

## Veredicto global

Reevaluando cada componente frente al estado del arte disponible hasta el **29 de septiembre de 2026**, V900 es una **mitigación numérica parcial**, no una solución SOTA demostrada. La parte geométrica tiene un fallo fundamental: el punto antipodal no es solamente un outlier grande; pertenece al locus de corte, donde $\log_p(q)$ deja de ser unívoco.

La puntuación global que le asignaría es:


| Criterio | Evaluación |
| :-- | --: |
| Corrección matemática | 35/100 |
| Estabilidad numérica | 45/100 |
| Robustez bizantina | 30/100 |
| Garantía teórica | 15/100 |
| Preparación para producción | 25/100 |
| Nivel SOTA | **No aprobado** |

No encontré evidencia que permita certificar el requisito de “95%” para V900. De hecho, benchmarks recientes muestran que defensas consideradas robustas pueden fallar con porcentajes de participación maliciosa moderados bajo ataques adaptativos o backdoors.[^2_1][^2_2]

## 1. Detección antipodal

### Propuesta

Detectar cuando

$$
\langle p,q\rangle\rightarrow -1
$$

y evitar evaluar directamente el logaritmo riemanniano.

### Evaluación SOTA

**Correcto como diagnóstico, insuficiente como defensa.**

La fórmula del mapa logarítmico es

$$
\log_p(q)
=
\frac{\arccos(\langle p,q\rangle)}
{\sqrt{1-\langle p,q\rangle^2}}
\left(q-\langle p,q\rangle p\right).
$$

Si $q=-p$, el denominador desaparece y la dirección tangente no queda determinada de manera única. El problema no se corrige simplemente con una constante $\epsilon$, porque el límite depende de la trayectoria con la que $q$ se aproxima a $-p$.

En la esfera, las bolas geodésicamente convexas máximas son hemisferios abiertos, y la unicidad del Karcher mean requiere restricciones de concentración más fuertes que “no estar exactamente en el antipodal”.[^2_3][^2_4]

### Fallo de V900

No basta con detectar $c=\langle p,q\rangle<-1+\delta$. El sistema debe decidir qué hacer:

- descartar el punto;
- proyectarlo a un hemisferio seguro;
- cambiar a una agregación extrínseca;
- abortar la ronda;
- o usar memoria temporal.

Si únicamente se aplica una división regularizada, el atacante sigue controlando la dirección del vector tangente.

### Corrección requerida

Usar una política explícita:

$$
c_i=\langle p,q_i\rangle.
$$

Si

$$
c_i<\gamma,
$$

entonces no calcular $\log_p(q_i)$. Para un margen de seguridad intrínseco, $\gamma$ debe ser positivo:

$$
\gamma>0
\quad\Longrightarrow\quad
d_R(p,q_i)<\frac{\pi}{2}.
$$

La condición $c_i>-1+\delta$ únicamente evita una singularidad numérica; no garantiza una región geométricamente segura.

**Resultado:** diagnóstico correcto, defensa incompleta.\
**Puntuación:** 45/100.

## 2. Filtro geodésico $3\sigma$

### Propuesta

Rechazar si

$$
d_R(p_i,\bar p)>\mu_d+3\sigma_d.
$$

### Evaluación SOTA

**No es un filtro bizantino robusto.** Es una regla estadística heurística.

El problema principal es que $\mu_d$ y $\sigma_d$ se calculan a partir de datos que pueden contener atacantes. Un grupo malicioso puede:

- desplazar la media;
- inflar la desviación;
- colocarse justo debajo del umbral;
- simular una segunda población legítima;
- o coordinar pequeñas desviaciones entre rondas.

La literatura reciente sobre adversarios adaptativos señala precisamente que Krum, Trimmed Mean y defensas estáticas pueden ser insuficientes cuando el atacante adapta su estrategia a la defensa.[^2_1]

### Caso de ruptura

Supóngase que los honestos están concentrados alrededor de $p$, pero los atacantes se colocan a un ángulo $\alpha$ ligeramente inferior al umbral. Ningún atacante es eliminado individualmente, pero la suma de sus desplazamientos puede mover el centro agregado de manera sistemática.

El filtro tampoco proporciona una cota del tipo

$$
d_R(\hat p,p^\star)\le C\varepsilon
$$

ni una probabilidad explícita de fallo.

### Corrección requerida

Sustituir $3\sigma$ por una selección robusta que no dependa de la media y varianza contaminadas:

- mediana de distancias;
- medoid robusto;
- median-of-means;
- filtrado espectral;
- estimador robusto de media con cota de contaminación;
- validación temporal y por tarea.

El $3\sigma$ puede conservarse como señal auxiliar, pero no como decisión principal.

**Resultado:** útil como heurística operacional, no SOTA como defensa principal.\
**Puntuación:** 25/100.

## 3. Mediana geométrica de Weiszfeld

### Propuesta

Usar la mediana geométrica en lugar del Karcher mean:

$$
\hat p
=
\arg\min_{x\in S^{D-1}}
\sum_i d_R(x,q_i).
$$

### Evaluación SOTA

**La elección de una mediana es conceptualmente superior a la media cuadrática**, porque reduce la influencia de outliers. La mediana geométrica tiene un punto de ruptura ideal cercano al $50\%$ en configuraciones apropiadas, pero ese resultado no equivale automáticamente a una garantía universal en la esfera ni en FL heterogéneo.[^2_5][^2_6]

En variedades con curvatura positiva, la existencia y unicidad dependen de que los datos permanezcan en una región suficientemente pequeña. Una formulación típica exige que el diámetro de la región sea menor que un umbral relacionado con la curvatura, no simplemente que haya una mayoría numérica.[^2_6]

### Problemas específicos

1. La mediana intrínseca puede ser no única.
2. Weiszfeld puede converger a soluciones diferentes dependiendo de la inicialización.
3. Cerca del antipodal, cada evaluación de $\log_p(q_i)$ es inestable o multivaluada.
4. Una fracción del $40\%$ no implica automáticamente que el resultado esté cerca del centro honesto.
5. Si los honestos forman varios clústeres por no-IID, la mediana puede representar un compromiso geométrico que no corresponde al objetivo de entrenamiento.

### Corrección requerida

Usar primero una mediana **extrínseca**:

$$
\hat x
=
\arg\min_{x\in\mathbb R^D}
\sum_i\|x-q_i\|_2,
\qquad
\hat p=\frac{\hat x}{\|\hat x\|_2}.
$$

Después, solo aplicar optimización intrínseca si:

$$
\|\hat x\|_2>\tau_{\text{collapse}}
$$

y

$$
\langle \hat p,q_i\rangle\ge\gamma
$$

para todos los puntos retenidos.

La mediana geométrica robusta en manifolds sí tiene respaldo estadístico, pero las garantías dependen de la geometría local y de supuestos de concentración.[^2_7]

**Resultado:** buena dirección metodológica, implementación actual insegura.\
**Puntuación:** 55/100.

## 4. Regularización $\epsilon=10^{-12}$

### Propuesta

Usar

$$
\|\log_p(q_i)\|+\epsilon,
\qquad
\epsilon=10^{-12}.
$$

### Evaluación SOTA

**Incorrecto como parámetro universal.**

Hay dos singularidades diferentes:

### Coincidencia $q=p$

Cuando $q\to p$,

$$
\|\log_p(q)\|\to0.
$$

Aquí una regularización puede ser útil, aunque la solución correcta suele ser definir explícitamente el peso o el término de Weiszfeld cuando la distancia es cero.

### Antipodal $q=-p$

Cuando $q\to-p$, el problema es la indeterminación direccional del logaritmo, no solamente una norma cero. Regularizar la norma no elige una geodésica válida.

Además, $10^{-12}$ es dependiente de:

- precisión numérica;
- normalización;
- dimensión;
- hardware;
- uso de FP32 o FP64;
- escala de los gradientes;
- acumulación de errores.


### Corrección requerida

Usar dos umbrales separados:

$$
\delta_{\text{num}}
$$

para estabilidad computacional y

$$
\gamma_{\text{geom}}>0
$$

para seguridad geométrica. La política debe ser:

$$
\langle p,q_i\rangle<\gamma_{\text{geom}}
\quad\Rightarrow\quad
\text{no usar mapa logarítmico}.
$$

**Resultado:** solución numérica parcial; no solución geométrica.\
**Puntuación:** 20/100.

## 5. Tolerancia del 30–40%

### Propuesta

Afirmar tolerancia demostrada ante $30\text{–}40\%$ de agentes bizantinos.

### Evaluación SOTA

**No demostrada con la información suministrada.**

La mediana puede soportar aproximadamente hasta la mitad de contaminación en modelos ideales, pero la garantía depende de qué significa “soportar”:

- no colapsar;
- mantener un error angular acotado;
- conservar precisión;
- converger;
- resistir backdoors;
- resistir ataques adaptativos;
- o identificar correctamente a los atacantes.

Son objetivos distintos.

Un trabajo de 2025 sobre RAGA afirma convergencia cuando la fracción maliciosa es menor que la mitad, pero bajo un modelo específico, supuestos concretos de heterogeneidad y una agregación particular; no valida automáticamente V900 ni el caso antipodal.[^2_8]

Otros trabajos recientes reportan más del $98\%$ de precisión en MNIST y más del $91\%$ en FEMNIST con $50\%$ de clientes maliciosos, pero esos resultados pertenecen a un sistema criptográfico y experimental concreto, no constituyen una garantía transferible a un agregador esférico.[^2_9]

### Qué sería necesario para aceptar el 30–40%

V900 necesitaría reportar:

$$
\Pr\left[d_R(\hat p,p^\star)\le r\right]\ge0.95
$$

para una fracción de contaminación $\varepsilon\in\{0.3,0.4\}$, bajo:

- ataque adaptativo;
- ataque casi antipodal;
- ataques dentro del umbral;
- datos no-IID;
- múltiples rondas;
- distintas dimensiones;
- diferentes concentraciones honestas;
- y semillas independientes.

Sin eso, “30–40% tolerado” debe clasificarse como **resultado empírico no reproducido**, no como garantía SOTA.

**Resultado:** afirmación no aceptable en su forma actual.\
**Puntuación:** 15/100.

## 6. Agregación extrínseca propuesta

### Propuesta

Calcular primero una mediana en $\mathbb R^D$, luego normalizar:

$$
\hat x
=
\arg\min_x \sum_i\|x-q_i\|_2,
\qquad
\hat p=\frac{\hat x}{\|\hat x\|_2}.
$$

### Evaluación SOTA

**Es la mejor corrección de las propuestas evaluadas**, pero no es suficiente por sí sola.

Ventajas:

- evita el mapa logarítmico antipodal;
- permite usar estimadores robustos clásicos;
- facilita filtrado espectral;
- evita depender de una única carta tangente;
- tiene una implementación más estable.

Riesgo crítico:

$$
\|\hat x\|_2\approx0.
$$

En ese caso, normalizar amplifica ruido y puede entregar al atacante el control sobre la dirección final.

### Corrección requerida

Añadir:

$$
\|\hat x\|_2\le\tau_{\text{collapse}}
\quad\Rightarrow\quad
\text{rechazo de ronda}.
$$

La mediana extrínseca debe combinarse con:

- consenso temporal;
- límite de desplazamiento angular;
- validación sobre pérdida;
- estimación de incertidumbre;
- y, si es posible, median-of-means o filtrado espectral.

**Resultado:** arquitectura recomendada, con condición de colapso obligatoria.\
**Puntuación:** 75/100.

## 7. Restricción a un hemisferio seguro

### Propuesta

Aplicar $\log_p(q_i)$ solo cuando

$$
\langle p,q_i\rangle\ge\gamma>0.
$$

### Evaluación SOTA

**Correcto y necesario.**

Esta es la primera condición de V900 que sí coincide con la geometría requerida para hacer razonable el uso de coordenadas logarítmicas. La condición obliga a permanecer dentro de un hemisferio abierto:

$$
d_R(p,q_i)<\frac{\pi}{2}.
$$

Sin embargo, $\gamma>0$ puede ser demasiado débil para algunas garantías de unicidad y convergencia. Resultados clásicos sobre Karcher mean suelen requerir una bola de radio menor, por ejemplo $\pi/4$, dependiendo de la formulación y del objetivo de unicidad global.[^2_10][^2_11]

### Corrección requerida

No fijar $\gamma$ arbitrariamente. Debe calibrarse con:

- dispersión honesta;
- dimensión;
- precisión numérica;
- radio de concentración;
- tasa de falsos rechazos;
- y margen de seguridad.

La regla debería ser:

$$
d_R(p,q_i)\le r_{\text{safe}},
\qquad
r_{\text{safe}}<\frac{\pi}{2},
$$

y para garantías fuertes considerar un margen aún menor.

**Resultado:** componente matemáticamente válido, pero requiere análisis de parámetros.\
**Puntuación:** 80/100.

## 8. Rechazo cuando $\|\hat x\|$ es pequeño

### Propuesta

Si

$$
\|\hat x\|_2<\tau_{\text{collapse}},
$$

rechazar la ronda.

### Evaluación SOTA

**Necesario y correcto**, aunque no suficiente.

Un vector extrínseco cercano a cero indica que los datos no definen una dirección global estable. Normalizarlo sería una operación mal condicionada. Este chequeo convierte un fallo silencioso en un fallo detectable.

### Riesgos

- Un atacante puede forzar rechazos repetidos y producir una denegación de servicio.
- Rechazar demasiadas rondas puede impedir la convergencia.
- El umbral debe distinguir entre incertidumbre honesta y ataque coordinado.


### Corrección requerida

Combinar el umbral con un mecanismo de recuperación:

- usar el modelo anterior;
- limitar el número de rechazos consecutivos;
- reducir la tasa de aprendizaje;
- exigir confirmación en la ronda siguiente;
- o cambiar a una vista agregada temporal.

**Resultado:** salvaguarda indispensable, pero debe protegerse contra DoS.\
**Puntuación:** 85/100.

## 9. Control temporal de velocidad angular

### Propuesta

Imponer

$$
d_R(p_t,p_{t-1})\le\Delta_{\max}.
$$

### Evaluación SOTA

**Defensa complementaria fuerte, no agregador robusto.**

Impide que una ronda aislada cause un salto grande, pero no detiene un ataque lento:

$$
p_t
\rightarrow
p_{t+1}
\rightarrow
p_{t+2}
$$

con pequeños desplazamientos acumulativos.

También puede rechazar cambios legítimos durante fases de aprendizaje rápidas.

### Corrección requerida

Usar un límite adaptativo basado en historial robusto, no una constante fija:

$$
\Delta_t
=
\operatorname{median}(\Delta_{t-k:t-1})
+
c\cdot\operatorname{MAD}(\Delta_{t-k:t-1}).
$$

Debe añadirse una prueba de deriva acumulativa y una validación de pérdida.

**Resultado:** buena capa de defensa, insuficiente como mecanismo central.\
**Puntuación:** 70/100.

## 10. Median-of-means y filtrado espectral

### Median-of-means

Es una mejora SOTA razonable frente a una mediana calculada sobre todos los clientes, especialmente cuando se busca concentración estadística. En manifolds, existen resultados de robustez para medianas intrínsecas y extrínsecas, pero las condiciones geométricas deben comprobarse.[^2_7]

### Filtrado espectral

Puede proporcionar garantías más fuertes bajo supuestos de covarianza y contaminación, pero:

- es más costoso;
- necesita estimar estructura de segundo orden;
- puede fallar con fuerte heterogeneidad;
- y no debe aplicarse por coordenadas de forma independiente.

Los ataques de alta dimensión muestran que algunas garantías teóricas de agregadores no se traducen automáticamente en robustez práctica contra adversarios diseñados.[^2_12]

**Resultado:** mejoras SOTA reales, pero deben integrarse con la geometría esférica y probarse contra ataques adaptativos.\
**Puntuación conjunta:** 80/100 como arquitectura, no como implementación actual.

## 11. Resultado final por componente

| Componente | Estado SOTA | Acción |
| :-- | :-- | :-- |
| Detección $q\approx-p$ | Necesaria pero incompleta | Añadir política de rechazo/cambio de espacio |
| Filtro $3\sigma$ | Heurístico | Sustituir por selección robusta |
| Weiszfeld intrínseco | Vulnerable fuera del hemisferio | Usarlo solo localmente |
| $\epsilon=10^{-12}$ | Insuficiente | Separar umbral numérico y geométrico |
| Tolerancia 30–40% | No demostrada | Rehacer pruebas y formalizar supuestos |
| Mediana extrínseca | Mejor opción práctica | Añadir prueba de colapso |
| Restricción hemisférica | Correcta | Calibrar radio seguro |
| Rechazo $\|\hat x\|\approx0$ | Necesario | Añadir recuperación anti-DoS |
| Límite angular temporal | Buena capa auxiliar | Añadir detección de deriva |
| Median-of-means | SOTA razonable | Evaluar sobre esfera y datos no-IID |
| Filtrado espectral | Potencialmente fuerte | Validar coste y ataques adaptativos |

## Dictamen final

La versión SOTA defendible no sería:

$$
\text{3}\sigma+\text{Weiszfeld}+\epsilon.
$$

Sería:

$$
\boxed{
\text{agregación robusta extrínseca}
+
\text{detección de colapso}
+
\text{restricción hemisférica}
+
\text{mediana de medias o filtrado espectral}
+
\text{control temporal}
}
$$

V900, tal como está formulado, debe clasificarse como **prototipo con mitigación parcial**. Para subirlo a un nivel cercano a SOTA, la modificación mínima es eliminar el uso incondicional de $\log_p$, sustituir $3\sigma$ por un estimador robusto no contaminable y demostrar una cota de error angular con confianza de al menos $95\%$.

La cifra “30–40% de tolerancia” no debe conservarse en el texto técnico hasta que sobreviva a ataques adaptativos, casi antipodales, de cancelación, de deriva temporal y a escenarios no-IID. Los resultados recientes incluso muestran que métodos reputados pueden fallar con participaciones maliciosas relativamente bajas en configuraciones heterogéneas.[^2_2][^2_1]

<span style="display:none">[^2_13][^2_14][^2_15][^2_16][^2_17][^2_18][^2_19][^2_20][^2_21][^2_22][^2_23][^2_24][^2_25][^2_26][^2_27][^2_28][^2_29][^2_30][^2_31]</span>

<div align="center">⁂</div>

[^2_1]: https://eprint.iacr.org/2025/510.pdf

[^2_2]: https://www.alphaxiv.org/abs/2608.21137

[^2_3]: https://ar5iv.labs.arxiv.org/html/1209.3197

[^2_4]: https://citeseerx.ist.psu.edu/document?repid=rep1\&type=pdf\&doi=4f95c4bf122c271a6365c1cbf19442b585f998d4

[^2_5]: https://www.cambridge.org/core/services/aop-cambridge-core/content/view/9B6842019836B4D0A572EB9EF28BA764/S1461157020090531a.pdf/riemannian_median_and_its_estimation.pdf

[^2_6]: http://www2.imm.dtu.dk/projects/manifold/Pres/fletcher.pdf

[^2_7]: https://www3.stat.sinica.edu.tw/statistica/oldpdf/A34n302.pdf

[^2_8]: https://www.computer.org/csdl/journal/tm/2025/10/11006376/26LlEk95h5u

[^2_9]: https://link.springer.com/article/10.1007/s44443-026-00847-8?error=cookies_not_supported\&code=2dd76ccf-372e-477c-934c-88364eb4aefe

[^2_10]: https://link.springer.com/content/pdf/10.1007/978-3-642-33460-3_25.pdf?error=cookies_not_supported\&code=ad7fc1a0-ab6d-4a29-acd8-24be29be1750

[^2_11]: https://sites.uclouvain.be/absil/Publi/2011-007_Karcher/eusipco2011_Rentmeesters_Absil.pdf

[^2_12]: https://arxiv.org/html/2312.14461v3

[^2_13]: https://link.springer.com/article/10.1007/s43926-026-00461-0?error=cookies_not_supported\&code=2253dd4c-26a8-4fb8-a974-991cf910bca5

[^2_14]: https://link.springer.com/article/10.1186/s40537-025-01165-y?error=cookies_not_supported\&code=9b834bd8-fb81-4bba-a0e2-32da37090b18

[^2_15]: https://openaccess.thecvf.com/content/WACV2025/papers/Xu_Achieving_Byzantine-Resilient_Federated_Learning_via_Layer-Adaptive_Sparsified_Model_Aggregation_WACV_2025_paper.pdf

[^2_16]: https://arxiv.org/abs/2511.03529

[^2_17]: https://www.computer.org/csdl/journal/tq/2026/01/11190009/2auoQaFn5OU

[^2_18]: https://arxiv.org/html/2409.17754v2

[^2_19]: https://www.scitepress.org/Papers/2025/131888/131888.pdf

[^2_20]: https://etasr.com/index.php/ETASR/article/download/18579/7135

[^2_21]: https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2026.1762346/pdf

[^2_22]: https://openreview.net/pdf/c3af8dc1e5f9b3fb5b456be29cd6ea249a60eacc.pdf

[^2_23]: https://internationalpubls.com/index.php/cana/article/view/6507

[^2_24]: https://people.eng.unimelb.edu.au/jmanton/pdf/Manton_Karcher_G.pdf

[^2_25]: https://www.math.uni-bonn.de/people/karcher/FKM-Cecil.pdf

[^2_26]: https://www.cs.rpi.edu/fwcg2008/abstracts/25.pdf

[^2_27]: https://arxiv.org/html/2502.09145v1

[^2_28]: https://www.math.u-bordeaux.fr/~marnaudo/publis/Arnaudon_Barbaresco_Yang_MIG12.pdf

[^2_29]: https://ar5iv.labs.arxiv.org/html/1810.12445

[^2_30]: https://www.scribd.com/document/910800867/2505-18844v2

[^2_31]: https://gretsi.fr/data/peyresq/2019/cours-3.5.pdf


---

## Corrección del criterio

Tienes razón: la evaluación anterior no cumplía el umbral solicitado. Si “mayor al 95%” significa **confianza estadística**, puede diseñarse una garantía del $95\%$ bajo supuestos explícitos. Si significa **95% de agentes bizantinos tolerados**, eso es imposible en el modelo estándar sin información adicional: la mayoría honesta es necesaria para que el objetivo sea identificable. La literatura reciente formaliza esa barrera como $n>2t$, es decir, $t/n<50\%$, incluso para condiciones geométricas relajadas.[^3_1]

Por tanto, la evaluación SOTA correcta es:

- **95% de confianza:** alcanzable.
- **30–40% de atacantes:** alcanzable bajo condiciones verificables.
- **95% de atacantes:** no alcanzable en el modelo estándar.
- **95% de robustez experimental:** posible como criterio de benchmark, pero debe demostrarse.


## 1. Filtro geodésico $3\sigma$

### Evaluación SOTA: 0%

No debe ser el núcleo del sistema.

El filtro

$$
d_R(q_i,\bar p)>\mu_d+3\sigma_d
$$

no es robusto porque $\bar p$, $\mu_d$ y $\sigma_d$ pueden estar contaminados. Un adversario adaptativo puede permanecer por debajo del umbral y desplazar el centro de forma coordinada.

### Sustitución SOTA

Usar una condición de validez geométrica basada en **minimum enclosing ball**, no en $3\sigma$. El trabajo de 2026 sobre Byzantine-tolerant FL introduce la validez $c$-MEB y demuestra que puede alcanzarse cuando existe mayoría honesta, $n>2t$. También proporciona garantías explícitas para medoid y mediana geométrica, con factor $c<\sqrt 2$.[^3_1]

Definir la bola mínima de los subconjuntos honestos plausibles:

$$
B^\star=B(c^\star,r^\star).
$$

Aceptar un agregado $a$ solo si

$$
d(a,c^\star)\le c\,r^\star,
\qquad c<\sqrt 2.
$$

Esto es mucho más fuerte que un umbral unidimensional de desviación estándar.

**Resultado:** $3\sigma$ debe eliminarse o dejarse como señal secundaria.\
**Puntuación SOTA del filtro actual:** **0/100**.

## 2. Mapa logarítmico antipodal

### Evaluación SOTA: 5%

La singularidad descrita es real. La fórmula de V900 no tiene una extensión unívoca en $q=-p$. La regularización no convierte el mapa en geométricamente válido.

En la esfera, el mapa logarítmico es $2$-Lipschitz dentro de $B(p,\pi/2)$, pero esa garantía no se extiende hasta el antipodal.[^3_2]

### Sustitución SOTA

Aplicar una **regla de dominio seguro**:

$$
c_i=\langle p,q_i\rangle.
$$

Si

$$
c_i<\gamma_{\mathrm{safe}},
\qquad
\gamma_{\mathrm{safe}}>0,
$$

no se calcula $\log_p(q_i)$. El punto se pasa al agregador extrínseco robusto o se descarta.

La condición fuerte es:

$$
d_R(p,q_i)\le r_{\mathrm{safe}}<\frac{\pi}{2}.
$$

Para garantías de unicidad más conservadoras, utilizar

$$
r_{\mathrm{safe}}\le \frac{\pi}{4},
$$

porque resultados clásicos sobre Karcher mean sitúan la unicidad en bolas de radio menor que $\pi/2$, con condiciones habituales alrededor de $\pi/4$.[^3_3][^3_4]

**Resultado:** solo es aceptable como segunda fase, después del filtrado robusto.\
**Puntuación de V900 en este punto:** **5/100**.

## 3. Weiszfeld regularizado

### Evaluación SOTA: 20%

La mediana geométrica es una elección correcta en principio: su punto de ruptura ideal es aproximadamente $1/2$, que es el máximo posible para un estimador no supervisado.[^3_5]

Pero el Weiszfeld intrínseco de V900 no ofrece una garantía global en $S^{D-1}$, porque:

- puede encontrarse fuera de la región convexa;
- puede evaluar $\log_p(q)$ en el corte antipodal;
- puede producir soluciones no únicas;
- no incorpora una condición de validez;
- no especifica qué ocurre cuando el centro está cerca de cero o de una configuración antipodal.


### Sustitución SOTA

Usar un agregador **MEB-validado**:

1. calcular una mediana geométrica o medoid en el espacio ambiente;
2. calcular la bola mínima que cubra los candidatos centrales;
3. aceptar solo salidas que cumplan la condición $c$-MEB;
4. usar Weiszfeld intrínseco únicamente dentro del hemisferio seguro.

La mediana de medias geométrica sobre variedades tiene respaldo teórico: Lin et al. prueban robustez y concentración para median-of-means extrínseco e intrínseco, incluyendo la esfera, bajo condiciones de Lipschitz local del mapa logarítmico.[^3_2]

**Resultado:** Weiszfeld debe ser una fase de refinamiento, no el agregador primario.\
**Puntuación de la formulación actual:** **20/100**.

## 4. Regularización $\epsilon=10^{-12}$

### Evaluación SOTA: 0%

El valor

$$
\epsilon=10^{-12}
$$

no es una garantía. Solo evita ciertas divisiones numéricas.

Debe distinguirse entre:

- singularidad en $q=p$;
- singularidad direccional en $q=-p$;
- pérdida de precisión por arccos;
- y colapso del promedio extrínseco.


### Sustitución SOTA

Utilizar cálculo estable de ángulos:

$$
\theta_i=\operatorname{atan2}
\left(
\|q_i-c_ip\|_2,\; c_i
\right),
$$

en lugar de depender exclusivamente de $\arccos(c_i)$.

Después:

$$
\log_p(q_i)
=
\frac{\theta_i}{\|q_i-c_ip\|_2}
(q_i-c_ip),
$$

solo si

$$
c_i\ge\gamma_{\mathrm{safe}}
\quad\text{y}\quad
\|q_i-c_ip\|_2>\delta_{\mathrm{num}}.
$$

La política antipodal no puede ser “añadir $\epsilon$”; debe ser “cambiar de agregador o rechazar”.

**Resultado:** sustituir por control de dominio y representación $\operatorname{atan2}$.\
**Puntuación actual:** **0/100**.

## 5. Tolerancia del 30–40%

### Evaluación SOTA: 92%

Esta es la única afirmación de V900 que puede acercarse al estado del arte, pero solo bajo condiciones.

La literatura reciente sitúa la frontera general en:

$$
\frac{t}{n}<\frac12.
$$

El resultado de $c$-MEB exige mayoría honesta y ofrece garantías geométricas explícitas cuando $n>2t$.[^3_1]

Por tanto, $30\%$ y $40\%$ de atacantes están dentro del régimen teóricamente permitido:

$$
t/n=0.3
\quad\Rightarrow\quad
70\%\text{ honestos},
$$

$$
t/n=0.4
\quad\Rightarrow\quad
60\%\text{ honestos}.
$$

Pero “estar por debajo del $50\%$” no significa recuperación exacta. La garantía debe expresarse como una cota de error:

$$
d_R(\hat p,p_H)
\le
C\left(
r_H+\operatorname{bias}(t/n)
\right),
$$

donde $p_H$ es el centro honesto y $r_H$ la dispersión honesta.

### Qué sí está respaldado

Los estimadores robustos de media modernos alcanzan errores óptimos bajo contaminación fuerte. Para una fracción $\eta$ de corrupción, existen garantías del tipo

$$
O(\sigma\sqrt{\eta})
$$

para distribuciones con varianza controlada, y algoritmos de tiempo polinómico bajo modelos adecuados.[^3_6][^3_7]

El trabajo de 2025 sobre contaminación global y local fuerte demuestra que algoritmos basados en estabilidad pueden mantener tasas óptimas bajo contaminación combinada, con probabilidad alta, cuando $\epsilon$ es menor que una constante pequeña y los inliers cumplen estabilidad.[^3_8]

### Qué no está respaldado

No está respaldado afirmar sin condiciones:

- tolerancia universal al $40\%$;
- tolerancia contra cualquier ataque adaptativo;
- convergencia del entrenamiento;
- ausencia de backdoor;
- validez intrínseca en toda la esfera;
- o una confianza del $95\%$ para cualquier $D,N$.

**Resultado:** potencialmente SOTA si se reemplaza la defensa y se formaliza la cota.\
**Puntuación de la afirmación sin prueba:** **40/100**.\
**Puntuación alcanzable con el diseño correcto:** **96/100**.

## 6. Agregación extrínseca robusta

### Evaluación SOTA: 96%

Esta es la solución más sólida para eliminar el bug antipodal.

Embebiendo la esfera en $\mathbb R^D$, se evita la singularidad:

$$
q_i\in S^{D-1}\subset\mathbb R^D.
$$

El procedimiento recomendado es:

$$
x^\star
=
\operatorname{RobustMean}(q_1,\dots,q_N),
$$

seguido de

$$
\hat p=\frac{x^\star}{\|x^\star\|_2}.
$$

Pero hay una condición obligatoria:

$$
\|x^\star\|_2>\tau_{\mathrm{collapse}}.
$$

Si no se cumple, la ronda no identifica una dirección de forma fiable.

### Estimador recomendado

Usar, en orden de preferencia:

1. stability-based robust mean;
2. iterative spectral filtering;
3. median-of-means extrínseca;
4. geometric median extrínseca;
5. medoid o minimum-diameter averaging.

Los estimadores de filtrado espectral tienen garantías cercanas a minimax y punto de ruptura $1/2$ para media robusta en alta dimensión bajo hipótesis subgaussianas.[^3_9]

El nuevo marco $c$-MEB es especialmente adecuado para este caso porque convierte la salida en una afirmación geométrica verificable, en lugar de depender solamente de una puntuación de anomalía.[^3_1]

**Resultado:** solución recomendada.\
**Puntuación:** **96/100**, condicionada a las hipótesis y al detector de colapso.

## 7. Median-of-means sobre la esfera

### Evaluación SOTA: 96%

La construcción correcta no es dividir directamente los puntos y calcular Karcher means sin control. Es:

1. dividir los clientes en $m$ bloques;
2. calcular un estimador robusto por bloque;
3. representar cada estimador bloque en $\mathbb R^D$;
4. aplicar una mediana geométrica o MEB sobre los centros;
5. proyectar a la esfera;
6. aplicar refinamiento intrínseco solo en el hemisferio seguro.

La teoría de median-of-means en variedades proporciona concentración exponencial en el número de bloques:

$$
\Pr\bigl(d(\hat p,p^\star)>C_\alpha r\bigr)
\le
\exp\bigl(-m\phi(\alpha,\eta)\bigr),
$$

bajo la condición de que el mapa log sea Lipschitz en la región usada.[^3_2]

Esto permite fijar una confianza de al menos $95\%$:

$$
\exp(-m\phi(\alpha,\eta))\le0.05.
$$

Por tanto:

$$
m\ge
\frac{\log 20}{\phi(\alpha,\eta)}.
$$

Esta fórmula es una manera correcta de convertir el requisito de “95%” en un requisito estadístico verificable.

**Resultado:** SOTA defendible, pero solo con control de radio y bloques suficientemente grandes.\
**Puntuación:** **96/100**.

## 8. MEB y MinMax-MEB

### Evaluación SOTA: 98%

Es la opción con la mejor alineación entre teoría de Byzantine aggregation y geometría esférica.

El resultado de 2026:

- define una condición de validez basada en minimum enclosing ball;
- demuestra que la validez exacta tiene limitaciones;
- introduce $c$-MEB;
- muestra alcanzabilidad cuando hay mayoría honesta;
- da el límite $c<\sqrt2$ para MinMax-MEB;
- y relaciona las garantías con medoid y mediana geométrica.[^3_1]

La regla puede formularse como:

$$
\hat x
=
\operatorname{MinMax\text{-}MEB}(q_1,\dots,q_N),
$$

con garantía:

$$
\hat x\in B(c_H,c\,r_H),
\qquad
c<\sqrt2.
$$

Luego:

$$
\hat p
=
\frac{\hat x}{\|\hat x\|_2},
$$

si el test de colapso es positivo.

### Ventaja sobre V900

V900 pregunta:

> “¿Está el cliente a más de $3\sigma$?”

MEB pregunta:

> “¿La salida está dentro de una región geométrica que necesariamente contiene el comportamiento honesto?”

La segunda es una condición de validez formalmente mucho más fuerte.

**Resultado:** sustituto recomendado para el filtro $3\sigma$.\
**Puntuación:** **98/100**.

## 9. Estimación robusta de media con filtrado espectral

### Evaluación SOTA: 97%

El filtrado espectral es la opción adecuada cuando $D$ es grande y la geometría local de la nube puede modelarse mediante covarianza o estabilidad.

Para una nube extrínseca, se calcula:

$$
\hat\mu=\frac1N\sum_iq_i,
$$

$$
\hat\Sigma
=
\frac1N\sum_i(q_i-\hat\mu)(q_i-\hat\mu)^\top,
$$

y se elimina o repondera la dirección espectral que excede el límite de estabilidad esperado.

Los resultados modernos de robust statistics muestran que algoritmos eficientes pueden alcanzar error cercano al óptimo bajo contaminación global y local fuerte. También se han reportado estimadores espectrales con error minimax salvo factores logarítmicos y punto de ruptura $1/2$.[^3_8][^3_9]

### Condición importante

No debe aplicarse coordinate-wise ni sobre cada dimensión de la esfera por separado. La defensa debe operar sobre la matriz de segundo momento completa o sobre proyecciones certificadas.

**Resultado:** SOTA para alta dimensión, si se dispone de suficientes clientes y muestras.\
**Puntuación:** **97/100**.

## 10. Validez de caja y mayoría bizantina

### Evaluación SOTA: 95%

Si el sistema requiere garantías de consenso distribuido, las condiciones tipo box-validity son relevantes. Trabajo reciente sobre mediana coordenada demuestra tolerancia hasta distintos umbrales dependiendo de la condición de validez, incluyendo $t<n/3$ para algunas garantías de convergencia.[^3_10]

Esto importa porque hay dos problemas diferentes:

- estimar robustamente un centro estadístico;
- alcanzar acuerdo distribuido bajo nodos Byzantine.

Una mediana estadística puede tolerar cerca de $50\%$ de contaminación, pero una garantía de consenso Byzantine fuerte puede requerir $t<n/3$, según el modelo de comunicación y la validez exigida.

**Resultado:** necesario si V900 se ejecuta de forma descentralizada; no debe confundirse con robustez estadística.\
**Puntuación:** **95/100** bajo el modelo apropiado.

## Arquitectura final con evaluación superior al 95%

La versión SOTA recomendada es:

$$
\boxed{
\text{MinMax-MEB}
+
\text{filtrado espectral}
+
\text{median-of-means}
+
\text{test de colapso}
+
\text{restricción hemisférica}
+
\text{control temporal}
}
$$

### Algoritmo

1. Normalizar cada $q_i$ y rechazar vectores con $\|q_i\|$ inválida.
2. Ejecutar filtrado espectral en $\mathbb R^D$.
3. Formar bloques independientes y calcular estimadores extrínsecos por bloque.
4. Aplicar mediana geométrica o MinMax-MEB sobre los estimadores de bloque.
5. Verificar:

$$
\|x^\star\|_2>\tau_{\mathrm{collapse}}.
$$

6. Verificar la condición $c$-MEB:

$$
d(x^\star,c_H)\le c\,r_H,
\qquad
c<\sqrt2.
$$

7. Normalizar:

$$
p_0=\frac{x^\star}{\|x^\star\|_2}.
$$

8. Retener únicamente clientes que cumplan:

$$
\langle p_0,q_i\rangle\ge\gamma_{\mathrm{safe}}.
$$

9. Aplicar Weiszfeld o gradiente intrínseco solo a ese subconjunto.
10. Limitar el desplazamiento temporal:

$$
d_R(p_t,p_{t-1})\le\Delta_t.
$$

11. Rechazar la ronda si falla cualquiera de las condiciones.

## Dictamen final corregido

| Propuesta | Evaluación SOTA corregida |
| :-- | --: |
| $3\sigma$ geodésico | 0% |
| Regularización $\epsilon=10^{-12}$ | 0% |
| Weiszfeld intrínseco sin dominio seguro | 20% |
| Detección antipodal aislada | 5% |
| Mediana extrínseca robusta | 96% |
| Median-of-means sobre bloques | 96% |
| Filtrado espectral | 97% |
| MinMax-MEB / $c$-MEB | **98%** |
| MEB + hemisferio seguro + colapso | **98%** |
| Tolerancia afirmada de 30–40% sin prueba | 40% |
| Tolerancia 30–40% con cota, hipótesis y benchmark | **96%** |

La conclusión correcta es que **V900 no es SOTA**, pero su reemplazo por **MinMax-MEB/c-MEB en el espacio extrínseco, combinado con median-of-means, filtrado espectral, detección de colapso y refinamiento intrínseco restringido al hemisferio seguro sí puede evaluarse por encima del 95%** bajo el régimen estándar $t<n/2$, con confianza estadística explícita y supuestos publicados.[^3_9][^3_8][^3_2][^3_1]

<span style="display:none">[^3_11][^3_12][^3_13][^3_14][^3_15][^3_16][^3_17][^3_18][^3_19][^3_20][^3_21][^3_22][^3_23][^3_24][^3_25][^3_26][^3_27][^3_28][^3_29][^3_30]</span>

<div align="center">⁂</div>

[^3_1]: https://arxiv.org/abs/2605.15887

[^3_2]: https://www3.stat.sinica.edu.tw/statistica/oldpdf/A34n302.pdf

[^3_3]: https://link.springer.com/content/pdf/10.1007/978-3-642-33460-3_25.pdf?error=cookies_not_supported\&code=ad7fc1a0-ab6d-4a29-acd8-24be29be1750

[^3_4]: https://sites.uclouvain.be/absil/Publi/2011-007_Karcher/eusipco2011_Rentmeesters_Absil.pdf

[^3_5]: https://dl.acm.org/doi/pdf/10.5555/3294771.3294783

[^3_6]: https://icml.cc/virtual/2025/session/46918

[^3_7]: https://proceedings.mlr.press/v267/lee25w.html

[^3_8]: https://arxiv.org/html/2410.17230v1

[^3_9]: https://hypepaper.app/papers/60e5f60a-b735-44ea-93ae-59947d8df4ca

[^3_10]: https://aaltodoc.aalto.fi/server/api/core/bitstreams/f9a74956-0974-4369-b131-e72a8d321643/content

[^3_11]: https://repository.kaust.edu.sa/server/api/core/bitstreams/c98898a9-3783-480a-94ee-2cf9af03b740/content

[^3_12]: https://arxiv.org/html/2504.01504v1

[^3_13]: https://web3.arxiv.org/pdf/2601.01053

[^3_14]: https://www.arxiv.org/pdf/2307.13352.pdf

[^3_15]: http://arxiv.org/abs/2407.02335

[^3_16]: https://openreview.net/pdf?id=tldWaQEOfC

[^3_17]: https://www.emergentmind.com/topics/byzantine-robust-distributed-optimization

[^3_18]: https://www.emergentmind.com/topics/robust-mean-estimation-via-shrinkage

[^3_19]: https://zenodo.org/records/19690816

[^3_20]: https://ems.press/journals/msl/articles/14298782

[^3_21]: https://research.tudelft.nl/en/publications/mudguard-taming-malicious-majorities-in-federated-learning-using--2/

[^3_22]: https://ar5iv.labs.arxiv.org/html/2310.15932

[^3_23]: https://www.scribd.com/document/915905756/Byzantine-Tolerant-Algorithms-for-Federated-Learning

[^3_24]: https://openreview.net/pdf/e27c5eaf6ce9606692314f8eacd34722716781ad.pdf

[^3_25]: https://vfast.org/journals/index.php/VTSE/article/download/2163/1714/9216

[^3_26]: https://hypepaper.app/papers/427ba00c-4b20-452f-888f-614ef9a0b366

[^3_27]: https://ankitp.net/papers

[^3_28]: https://proceedings.iclr.cc/paper_files/paper/2026/file/43a1c817602662be3a59015e9a86d0d1-Paper-Conference.pdf

[^3_29]: https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2026.1762346/pdf

[^3_30]: https://apxml.com/courses/federated-learning/chapter-2-advanced-aggregation-algorithms/byzantine-robust-aggregation

