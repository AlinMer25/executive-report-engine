# Especificación del modelo de informe

Fase F1 · Contrato funcional del motor
Versión 1.1 — 31 de octubre de 2026
Base empírica: `docs/01-inventario-de-secciones.md`

---

## 1. Propósito

Este documento define **qué produce el motor de informes y bajo qué
condiciones**. No describe implementación. Es el contrato que el código de F2
a F4 debe cumplir, y el documento contra el cual se verifica si lo cumple.

Toda regla acá declarada se deriva del inventario de siete informes reales. Las
decisiones que el inventario no podía resolver —umbrales, pisos, ventanas de
comparación— están marcadas como **[DECISIÓN]** con su justificación, para que
se puedan discutir y cambiar sin leer el código.

### El problema que resuelve

Seis meses de informes produjeron tres patologías medibles:

1. Secciones que aparecían y desaparecían sin criterio declarado. Un problema
   escalado durante tres informes (fuga de envíos) dejó de reportarse sin que
   nadie lo decidiera.
2. Reexpresión silenciosa de meses cerrados. Junio se publicó con 235, 240 y
   249 ventas en tres documentos distintos, sin nota.
3. El mismo mes con tres cortes comparativos distintos y tres titulares
   distintos, todos correctos.

Ninguna es un error de análisis. Las tres son consecuencia de que el formato
nunca fue un contrato, sino una costumbre.

---

## 2. Artefactos de salida

El motor produce **dos documentos** por ejecución.

| ID | Documento | Destinatario | Relación |
|---|---|---|---|
| `A1` | Informe ejecutivo de ventas | Archivo del canal, consulta | Fuente |
| `A2` | Resumen y QA | Jefe de área, reunión mensual | **Derivado de A1** |

**Formato de salida: `.docx` para ambos.** Es el formato en el que los seis
meses de informes ya circularon, el que José abre sin fricción y el que admite
edición manual de último momento antes de una reunión. El motor genera el
`.docx` directamente con `python-docx`; no hay paso intermedio de conversión.

**Regla de derivación.** `A2` no se escribe: se compone a partir de `A1`.
Todo dato que aparece en `A2` debe existir en `A1`. Si una cifra aparece solo
en el resumen, es un defecto — fue la causa de la contradicción detectada en
septiembre (250→341 en la tabla del resumen contra 347→278→374 en la serie).

**Verificación asociada:** test que confirma que todo valor numérico de `A2`
tiene origen en `A1`. Se implementa en F3.

---

## 3. Parámetros de ejecución

Lo que hoy se decide informe por informe, pasa a ser parámetro declarado.

| Parámetro | Valores | Default | Qué controla |
|---|---|---|---|
| `mes_objetivo` | AAAA-MM | — | Período principal del informe |
| `corte_comparativo` | `mensual` · `bimestral` · `trimestral` · `cuatrimestral` · `semestral` · `anual` | `trimestral` | Qué sección de evolución se emite |
| `ventana_capacidad` | par de meses | últimos 2 | Base de la comparación de productividad |
| `piso_margen_alarma_1` | % | `23,0` | Primer umbral: callout de atención |
| `piso_margen_alarma_2` | % | `20,0` | Segundo umbral: alerta severa |
| `piso_margen_objetivo` | % | `26,0` | Nivel de recuperación declarado |
| `alarma_por_tendencia` | n.º de meses | `3` | Dispara por caída sostenida, sin importar el nivel |
| `modo_publicacion` | `interno` · `publico` | `interno` | Activa la anonimización |

**Por qué `corte_comparativo` es parámetro.** Septiembre produjo tres informes
con tres cortes. Ninguno está mal; el problema es que la elección era
invisible. Declarada como parámetro, aparece en el encabezado y en la nota
metodológica, y queda claro por qué dos informes del mismo mes difieren.

Los cortes `cuatrimestral`, `semestral` y `anual` todavía no tienen precedente
en el corpus — la serie arranca en abril de 2026 y el primer cierre anual
completo será el de diciembre. Se declaran ahora porque el cierre de año ya
está a la vista y agregar un valor al parámetro después obliga a tocar el
motor. El balance del Q4 y el cierre 2026 son los primeros usos previstos.

**Por qué `ventana_capacidad` es parámetro.** El inventario mostró que el mismo
módulo, con el mismo dato, produce conclusiones distintas según el par de meses
comparado: julio vs. septiembre concluye "la capacidad escala linealmente";
agosto vs. septiembre concluye "la productividad subió 36,4%". Las dos son
verdad. La ventana decide el titular, así que la ventana se declara.

---

## 4. Modelo de composición

### 4.1 Identificadores estables

Las secciones se referencian por **ID**, nunca por número. El número de sección
se asigna al componer el documento, según qué módulos se activaron. Una
recomendación que dice "ver sección 7" se rompe en cuanto cambia la
composición; `mod.logistica` no.

### 4.2 Tipos de sección

| Tipo | Comportamiento |
|---|---|
| **Núcleo** | Se emite siempre. Sin condición |
| **Módulo** | Se emite si cumple su condición de entrada |

### 4.3 La regla de salida

> **Todo módulo que se emitió en el período anterior y no entra en el actual
> emite una línea de cierre declarando el motivo.**

Motivos admitidos: `resuelto` · `bajo umbral` · `se dejó de medir` ·
`absorbido por <id>`.

Esta regla es el requisito central del spec. Sin ella, el formato permite que
un problema desaparezca del reporting sin haberse resuelto — que es exactamente
lo que pasó con la fuga de envíos entre agosto y septiembre, después de tres
meses consecutivos declarada "prioridad máxima".

Una línea de cierre no ocupa espacio y cierra el ciclo:

> *Logística de envíos: no se emite este período. Motivo: absorbido por
> mod.factor_del_mes. Balance del período: −$X (0,18% de facturación).*

---

## 5. Catálogo de secciones — Informe ejecutivo (A1)

### 5.1 Núcleo

---

**`core.encabezado`**
Mes, rango de fechas, `corte_comparativo` declarado, destinatario, autoría.
*Invariante:* el corte comparativo aparece siempre, explícito.

---

**`core.titular`**
Callout de apertura. El mes en 2-3 frases: resultado, contexto que lo explica,
alerta principal.
*Origen:* adoptado en julio, presente en los cinco informes siguientes.
*Invariante:* contiene al menos una cifra y al menos una alerta. Un titular
que solo celebra es un defecto.

---

**`core.resumen`**
3-4 párrafos. Estructura relevada, constante en los siete informes:
1. Resultado del período con variación
2. Causa principal del resultado
3. Motor de rentabilidad (qué sostuvo el mes)
4. Contracara (qué se deterioró)

*Invariante:* el párrafo 4 es obligatorio. Si el motor no encuentra deterioro,
lo declara explícitamente; no lo omite.

---

**`core.kpis`**
Grid de 6 a 9 indicadores con variación vs. período anterior.
*Mínimo obligatorio:* ventas, unidades, facturación, ganancia neta, margen
neto, ticket promedio.
*Invariante:* margen en puntos porcentuales (pp), nunca en %, para no
confundir "cayó 1,64 pp" con "cayó 1,64%".

---

**`core.plataformas`** · **`core.categorias`** · **`core.proveedores`**
Tres secciones separadas. Cada una: ranking por facturación, lectura de margen,
identificación de los extremos (mejor y peor rendimiento relativo).
*Origen:* fusionadas solo en junio v1; separadas en los seis informes
siguientes.
*Invariante:* cada sección reporta facturación **y** margen. Un ranking solo
por volumen oculta exactamente el fenómeno que el análisis de progreso
identificó como central.

---

**`core.productos`**
Top por ganancia neta + el producto de mejor margen del top.
*Invariante en `modo_publicacion = publico`:* nombre de producto sí, costo de
compra nunca.

---

**`core.comparativa`**
Tabla de 8-10 métricas contra el período anterior, con variación.
El período de comparación lo define `corte_comparativo`.
*Invariante:* incluye siempre ticket promedio junto a margen. Es el par que
distingue "vendimos más barato" de "vendimos con peor rentabilidad" — la
distinción que respondió la pregunta P4 de José en septiembre.

---

**`core.seguimiento`** — **sección nueva, no existía en el corpus**
Retoma las recomendaciones del período anterior y cierra cada una con dato.

Estados: `cumplida` · `en curso` · `no abordada` · `superada por los hechos`.

*Origen de la decisión:* el resumen de septiembre incorporó esta sección una
sola vez, para el compromiso de agosto sobre mantener vivos a los proveedores.
Produjo el hallazgo más fuerte de los seis meses — los proveedores que
recibieron mantenimiento mejoraron margen (+1,3 pp Bien Copiado, +0,9 pp Zero)
y los que no lo recibieron se desplomaron (−5,2 pp Visuar, −10,3 pp Alpaca).
Un grupo de control involuntario.

Si esta sección hubiera sido núcleo desde junio, la fuga de envíos no habría
podido desaparecer en silencio.

*Invariante:* se emiten **todas** las recomendaciones del período anterior,
incluidas las no abordadas. Una recomendación omitida equivale a una
recomendación silenciosamente abandonada.

*Matiz obligatorio:* cuando el seguimiento se reporta en agregado, el motor
debe verificar si algún componente del agregado contradice la conclusión. En
septiembre, Mosconi estaba en el grupo de proveedores mantenidos y perdió 5,8
pp — tanto como los que quedaron afuera — pero el agregado (25,0% → 25,5%) lo
tapaba. El spec exige señalarlo. Un argumento que esconde su propio
contraejemplo se cae en la primera repregunta.

---

**`core.atencion`**
3 a 5 callouts. Cada uno: dato, causa identificada, consecuencia si no se
corrige.
*Invariante:* si se cruza cualquiera de los dos pisos de margen, o si se
cumple la condición de tendencia (§6), se emite obligatoriamente un callout de
margen, con la pérdida **expresada en pesos**.

---

**`core.recomendaciones`**
5 a 8 ítems en imperativo, cada uno con justificación numérica.
*Invariante:* cada recomendación recibe un ID persistente, para que
`core.seguimiento` pueda retomarla el período siguiente. Sin ID, el
seguimiento no es verificable.

---

**`core.metodologia`**
Volumen de datos, definición de márgenes, redondeo, y **toda reexpresión
aplicada** (ver §7).

---

### 5.2 Módulos

| ID | Título | Entrada | Tipo de umbral |
|---|---|---|---|
| `mod.integridad` | Nota de integridad de datos | Hubo depuración que altera cifras ya publicadas | Binario |
| `mod.factor_del_mes` | Factor del mes | Evento exógeno explica más que las métricas | **Cualitativo** |
| `mod.logistica` | Análisis de logística de envíos | \|balance\| ≥ 0,25% de facturación | **Numérico** |
| `mod.evolucion` | Evolución dentro del período | Dato semanal disponible y dispersión ≥ 1,5× entre semana pico y valle | **Numérico** |
| `mod.capacidad` | Capacidad y productividad operativa | Cambió la dotación, o se pidió la medición | Binario |
| `mod.evolucion_larga` | Analítica del corte largo | `corte_comparativo ≠ mensual` | Paramétrico |
| `mod.carga_siguiente` | Carga de trabajo del período siguiente | Carga entrante > capacidad medida | **Cualitativo** |

**[DECISIÓN] Umbral de `mod.logistica` = 0,25% de facturación.**
Calibrado contra la serie real: junio 0,40%, julio 0,46%, agosto 0,32%. Con
este umbral, los tres meses que efectivamente emitieron la sección la habrían
emitido igual. Si septiembre hubiera quedado por debajo, el módulo habría
emitido su **línea de cierre** en lugar de desaparecer.

**[DECISIÓN] Umbral de `mod.evolucion` = dispersión ≥ 1,5×.**
En junio y julio la semana pico concentraba notoriamente más que el resto. En
agosto la distribución se emparejó y la sección perdió sentido analítico — pero
se emitió igual. El umbral evita emitir una sección que solo dice "estuvo
parejo".

**Nota sobre los umbrales cualitativos.** `mod.factor_del_mes` y
`mod.carga_siguiente` no admiten umbral numérico: dependen de información que
no está en la planilla (una decisión de la empresa, una carga de trabajo
prevista). Se declaran como **entrada manual del analista**, y el spec exige
que, cuando se activan, el informe diga quién las activó y con qué
justificación. Un módulo cualitativo sin justificación declarada es
indistinguible de un módulo arbitrario.

---

## 6. El piso de margen

**[DECISIÓN 31/10/2026] Dos niveles de alarma, un objetivo, y una condición de
tendencia. La alerta siempre en pesos.**

| Nivel | Valor | Función |
|---|---|---|
| `piso_margen_alarma_1` | **23,0%** | Callout obligatorio en `core.atencion` |
| `piso_margen_alarma_2` | **20,0%** | Alerta severa: encabeza `core.atencion` y entra en las 3 prioridades de A2 |
| `piso_margen_objetivo` | **26,0%** | Nivel de recuperación declarado |
| `alarma_por_tendencia` | **3 meses** | Dispara con tres caídas consecutivas, cualquiera sea el nivel |

### 6.1 Por qué no 26% como alarma

Se recomendó 26% en junio y en julio y nunca se fijó. Hoy se rompería tres
meses seguidos (25,53 → 24,68 → 23,04). Una alarma que suena siempre deja de
ser alarma: a los dos meses se ignora. El 26% queda como **objetivo de
recuperación**, que es el rol que de verdad cumple.

### 6.2 Por qué dos niveles y no uno

Un solo umbral trata igual una desviación de medio punto que un derrumbe. Con
dos, el informe distingue *"esto hay que mirarlo"* de *"esto hay que frenarlo
ahora"*, y el segundo nivel escala solo: pasa al tope de los puntos de atención
y entra obligatoriamente en las tres prioridades del resumen para José.

### 6.3 La alarma arranca en octubre — decisión consciente

Con el primer piso en 23,0%, septiembre (23,04%) **no habría disparado**, por
cuatro centésimas de punto. Y septiembre fue el mes que más caro costó de toda
la serie: $5,2 millones de ganancia cedida por margen.

Queda registrado porque la decisión fue deliberada: el sistema empieza a medir
desde octubre en adelante y no se usa para reabrir meses ya cerrados y
discutidos. Lo que cubre ese hueco es la condición de tendencia.

### 6.4 La condición de tendencia

> Si el margen neto baja **tres meses consecutivos**, se emite el callout aunque
> ningún piso se haya cruzado.

Es la regla que captura el fenómeno real. El problema de julio a septiembre no
fue el nivel —todos los meses estuvieron en un rango defendible— sino la
**deriva sostenida**: 25,53 → 24,68 → 23,04, sin un solo rebote, 2,5 puntos
acumulados. Cada caída tuvo su justificación razonable por separado, y
justamente por eso una tendencia estructural terminó leyéndose como tres
accidentes independientes.

Un piso detecta niveles. Esta condición detecta direcciones. Hacen falta las
dos.

### 6.5 Por qué en pesos y no en puntos

Este es el hallazgo del análisis de progreso y el spec lo convierte en regla.
La caída de junio fue de 5,7 pp y costó $4,5M. La de septiembre fue de 1,64 pp
y costó $5,2M — **más cara, en un tercio de los puntos**. La razón es escala:
un punto de margen sobre $81M son $810 mil; sobre $317M son $3,2 millones.

Mientras la alarma se mida en puntos, el umbral se queda quieto mientras el
canal crece, y una compresión cada vez más cara se lee cada vez más chica.

> **Regla.** Todo callout de margen reporta: variación en pp, **costo en pesos
> del período**, y ganancia contrafáctica al margen del período anterior.

*En `modo_publicacion = publico`, el costo en pesos se expresa como índice o
como % de la ganancia neta. El invariante monetario no admite excepción.*

---

## 7. Reexpresión de períodos cerrados

El motor **puede** reexpresar meses ya publicados —depuración, cancelaciones,
carga tardía son motivos legítimos— pero no en silencio.

**Reglas:**

1. Toda serie histórica lleva versión. Un mes reexpresado conserva su valor
   anterior en el registro.
2. `core.metodologia` declara cada reexpresión aplicada en ese informe: métrica,
   valor anterior, valor nuevo, motivo.
3. Si la reexpresión supera el 5% en cualquier métrica de cabecera, se emite
   `mod.integridad` como sección propia.

**Lo que esto habría evitado:** junio publicado con 235, 240 y 249 ventas en
tres documentos. Julio con 432 y 359 unidades —17% de diferencia— sin una nota.
ICBC agosto con $11,4M y $14,0M. Ninguna cambia las conclusiones; todas
erosionan la confianza en el analista por un motivo ajeno a la calidad del
análisis.

---

## 8. Catálogo de secciones — Resumen y QA (A2)

| ID | Sección | Tipo | Nota |
|---|---|---|---|
| `qa.titular` | El titular del período | Núcleo | Deriva de `core.titular` |
| `qa.kpis` | Grid de 6 KPIs | Núcleo | Subconjunto de `core.kpis` |
| `qa.balance` | Lo que funcionó / Lo que hay que corregir | Núcleo | 5 bullets por columna |
| `qa.periodo` | El período en una línea | Núcleo | — |
| `qa.prioridades` | Las 3 prioridades | Núcleo | **Exactamente 3**, derivadas de `core.recomendaciones` |
| `qa.seguimiento` | Cierre del compromiso anterior | Núcleo | Deriva de `core.seguimiento` |
| `qa.productividad` | Dato de productividad del área | Módulo | Activo si `mod.capacidad` activo |
| `qa.preguntas` | Preguntas clave | Núcleo | 8 a 12, ver abajo |
| `qa.cierre` | Antes de entrar a la reunión | Núcleo | La historia en una línea |

### 8.1 Generación de `qa.preguntas`

Cada pregunta se deriva de un hecho del informe, no se inventa. Reglas de
generación relevadas del corpus:

| Condición en A1 | Pregunta obligatoria |
|---|---|
| Margen por debajo del piso | "¿Por qué bajó el margen?" |
| Ticket estable + margen en baja | "¿Vendimos más barato?" |
| Un proveedor > 40% de facturación | "¿No dependemos demasiado de X?" |
| Módulo cerrado este período | "¿Qué pasó con <tema del período anterior>?" |
| Crecimiento > 30% | "¿Esto se sostiene o fue puntual?" |
| Cambio de dotación | "¿El equipo rinde o se está estirando?" |

*Invariante:* toda respuesta propuesta contiene una cifra del informe. Una
respuesta sin dato es una opinión, y en una reunión se cae.

*Invariante de atribución:* cuando la respuesta atribuye un resultado al
trabajo del área, debe declarar primero lo que **no** es atribuible. El modelo
está en la P7 de septiembre: reconocer el aporte del precio, el catálogo y
Tecnología antes de aislar lo que solo explica la capacidad operativa. La
precisión en la atribución es lo que da autoridad; la sobreatribución es lo que
la destruye en la primera repregunta.

---

## 9. Invariantes globales

Se verifican por código en F3. Fallan el build, no advierten.

| # | Invariante | Alcance |
|---|---|---|
| I1 | Ningún valor monetario absoluto | `modo_publicacion = publico` |
| I2 | Todo dato de A2 existe en A1 | Siempre |
| I3 | Todo módulo emitido el período anterior y ausente ahora tiene línea de cierre | Siempre |
| I4 | Toda recomendación tiene ID persistente | Siempre |
| I5 | Toda reexpresión está declarada en `core.metodologia` | Siempre |
| I6 | Margen siempre en pp; variaciones monetarias siempre con su % sobre facturación | Siempre |
| I7 | Toda métrica usada existe en el `Diccionario_Metricas_CanalVerde` | Siempre |

**Sobre I7.** El diccionario ya define 16 métricas con fórmula exacta y 12
reglas de validación, y establece su propia regla de oro: *ninguna métrica se
reporta si no está definida ahí primero*. El spec la adopta y la hace
verificable. F2 construye la capa de métricas sobre ese diccionario, no desde
cero.

---

## 10. Fuera de alcance

Declarado para que no se discuta después:

- **Generación de prosa narrativa.** El motor produce estructura, datos y
  alertas. La redacción de los párrafos de análisis queda en manos del
  analista. Automatizar el texto convertiría el proyecto en otra cosa.
- **Predicción o proyección.** El motor reporta lo que pasó.
- **Carga y limpieza del dato origen.** El motor consume una planilla ya
  depurada. Las reglas de validación del diccionario corren aguas arriba.
- **Distribución.** El motor produce archivos. Cómo llegan a destino no es su
  problema.

---

## 11. Registro de decisiones

| # | Decisión | Estado |
|---|---|---|
| D1 | Pisos de margen: 23,0% / 20,0% + tendencia de 3 meses | **Cerrada 31/10.** Conversar el valor con José cuando haya un mes medido con el sistema |
| D2 | Umbral de `mod.logistica`: 0,25% de facturación | **Cerrada 31/10.** Calibrada contra jun 0,40% · jul 0,46% · ago 0,32% |
| D3 | Formato de salida de A1 y A2: `.docx` | **Cerrada 31/10.** Generado con `python-docx` |
| D4 | Mes base del índice de anonimización: abril 2026 = 100 | **Cerrada.** Decidida 23/10, confirmada 31/10 |
| D5 | Cortes `cuatrimestral`, `semestral` y `anual`: sin precedente en el corpus | Declarados; se validan con el primer cierre que los use |

---

*Marcos Olmedo Wasmuth — executive-report-engine · F1 · spec v1.1*
