# Inventario de secciones — informes de Canal Verde

Fase F1 · Base empírica del modelo de informe
Relevamiento: 27 de octubre de 2026
Fuente: 7 informes mensuales y 5 resúmenes QA, junio – septiembre 2026

---

## 1. Alcance y método

Este documento no propone una estructura: la **releva**. Cada sección listada
abajo existe porque apareció en al menos un informe real, y su clasificación
como núcleo o módulo surge de su frecuencia de aparición, no de un criterio
de diseño.

**Corpus relevado (7 informes):**

| # | Documento | Mes | Corte comparativo | Secciones |
|---|---|---|---|---|
| 1 | Informe_Ventas_Junio_CanalVerde | Junio | Solo MoM | 8 |
| 2 | Informe_Ventas_Junio_Trimestral | Junio | MoM + trimestre abr-jun | 12 |
| 3 | Informe_Ventas_Julio_Trimestral | Julio | MoM + trimestre may-jul | 12 |
| 4 | Informe_Ventas_Agosto_Trimestral | Agosto | MoM + trimestre jun-ago | 12 |
| 5 | Informe_Ventas_Septiembre_Trimestral | Septiembre | MoM + trimestre jul-sep | 12 |
| 6 | Informe_Ventas_Septiembre_Trimestral_v2 | Septiembre | MoM + trimestre jul-sep | 13 |
| 7 | Informe_Ventas_Septiembre_Bimestral | Septiembre | Bimestre ago-sep | 12 |

**Fuera de corpus:** abril y mayo 2026 no existen como informe. La serie de
datos los incluye (reconstruidos desde el informe de junio trimestral), pero
no hay documento del que relevar secciones. El inventario arranca en junio.

Los resúmenes QA para José son un **artefacto distinto**, con estructura
propia, y se relevan por separado en la sección 5.

---

## 2. La matriz

`●` presente como sección propia · `◐` presente pero fusionada o embebida en
otra · `○` ausente

| Sección | Jun | Jun·T | Jul | Ago | Sep·T | Sep·v2 | Sep·B | Frec. |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Encabezado y metadata de período | ● | ● | ● | ● | ● | ● | ● | 7/7 |
| Callout "El mes en una frase" | ○ | ○ | ● | ● | ● | ● | ● | 5/7 |
| Nota de integridad de datos | ○ | ● | ○ | ○ | ○ | ○ | ○ | 1/7 |
| **Resumen ejecutivo** | ● | ● | ● | ● | ● | ● | ● | **7/7** |
| **Indicadores clave (KPIs)** | ● | ● | ● | ● | ● | ● | ● | **7/7** |
| Factor del mes (evento exógeno) | ○ | ○ | ○ | ○ | ● | ● | ● | 3/7 |
| **Rendimiento por plataforma** | ● | ● | ● | ● | ● | ● | ● | **7/7** |
| Rendimiento por categoría | ◐ | ● | ● | ● | ● | ● | ● | 6/7 |
| Rendimiento por proveedor | ◐ | ● | ● | ● | ● | ● | ● | 6/7 |
| **Productos destacados** | ● | ● | ● | ● | ● | ● | ● | **7/7** |
| Análisis de logística de envíos | ◐ | ● | ● | ● | ○ | ○ | ○ | 4/7 |
| Evolución dentro del mes | ● | ● | ● | ● | ○ | ○ | ○ | 4/7 |
| Capacidad / productividad operativa | ○ | ○ | ○ | ○ | ● | ● | ● | 3/7 |
| Comparativa con período anterior | ◐ | ● | ● | ● | ● | ● | ● | 6/7 |
| Analítica trimestral | ○ | ● | ● | ● | ● | ● | ○ | 5/7 |
| **Puntos de atención** | ● | ● | ● | ● | ● | ● | ● | **7/7** |
| **Recomendaciones accionables** | ● | ● | ● | ● | ● | ● | ● | **7/7** |
| Carga de trabajo del mes siguiente | ○ | ○ | ○ | ○ | ○ | ● | ● | 2/7 |
| **Nota metodológica** | ● | ● | ● | ● | ● | ● | ● | **7/7** |

---

## 3. Núcleo fijo

Siete secciones aparecen en los siete informes, sin excepción. Son el
esqueleto del modelo y ninguna necesita disparador: se emiten siempre.

| Orden | Sección | Contenido invariante |
|---|---|---|
| 00 | Encabezado | Mes, rango de fechas, corte comparativo, destinatario, autoría |
| 01 | Resumen ejecutivo | 3-4 párrafos: resultado, causa, motor de rentabilidad, contracara |
| 02 | Indicadores clave | Grid de 6-9 KPIs con variación vs. período anterior |
| 03 | Rendimiento por plataforma | Ranking por facturación + lectura de margen |
| 04 | Productos destacados | Top por ganancia neta + el de mejor margen |
| 05 | Comparativa con período anterior | Tabla de 8-10 métricas con variación |
| 06 | Puntos de atención | 3-4 callouts, cada uno con dato, causa y consecuencia |
| 07 | Recomendaciones accionables | 6-7 ítems en imperativo, con justificación numérica |
| 08 | Nota metodológica | Volumen de datos, definición de márgenes, redondeo |

**Nota sobre el orden.** El núcleo no se emite en bloque: los módulos se
intercalan. La numeración definitiva del modelo debe ser por **identificador
estable** (`core.resumen`, `core.kpis`) y no por número correlativo, porque el
número de sección cambia según cuántos módulos se activen. Esta es la primera
decisión de diseño que el inventario obliga a tomar.

**Casi-núcleo (6/7).** *Rendimiento por categoría* y *Rendimiento por
proveedor* solo faltan como sección propia en el informe de junio v1, donde
estaban fusionadas en una sola ("Categorías y proveedores"). La separación en
junio trimestral fue una mejora que nunca se revirtió: desde entonces son dos
secciones en los seis informes siguientes. Van al núcleo.

---

## 4. Módulos opcionales y sus disparadores

Cada módulo aparece cuando algo lo justifica. El disparador se infiere de las
condiciones presentes en los meses donde aparece y ausentes donde no.

| Módulo | Meses | Disparador inferido |
|---|---|---|
| Analítica trimestral | Jun·T – Sep·T | Corte trimestral elegido para el informe |
| Logística de envíos | Jun·T – Ago | Balance de envíos materialmente negativo |
| Evolución dentro del mes | Jun – Ago | Hay dato semanal y una distribución con forma |
| Factor del mes | Sep (×3) | Evento exógeno que explica el resultado más que las métricas |
| Capacidad operativa | Sep (×3) | Cambio de dotación o medición de productividad disponible |
| Carga del mes siguiente | Sep·v2, Sep·B | Carga entrante excede lo medido como capacidad |
| Nota de integridad | Jun·T | Depuración de datos que altera cifras ya reportadas |
| Callout "mes en una frase" | Jul – Sep | Ninguno: se adoptó y se quedó |

### 4.1 El hallazgo del inventario: los módulos que se apagaron sin cerrar

Dos módulos desaparecen en septiembre sin una línea que lo explique.

**Logística de envíos** corrió tres meses consecutivos con el mismo
diagnóstico. Junio: −$317K, prioridad máxima. Julio: −$982K, "prioridad
máxima para agosto", responsable identificado (FvG Envios, −$792K). Agosto:
−$726K, "tercer mes consecutivo en rojo", "es el mismo diagnóstico hace tres
meses y sigue sin resolverse". Y en septiembre la sección **no existe**. No
hay cifra de cierre, no hay nota de que se resolvió, no hay nota de que se
dejó de medir. Un problema que se escaló durante tres informes simplemente
deja de aparecer.

**Evolución dentro del mes** corre cuatro informes y desaparece en el
mismo corte, pese a que septiembre es precisamente el mes donde el dato
semanal era más revelador — la curva de apagado de Tecnología ($56,7M → $3,5M)
es exactamente una evolución intramensual, y aparece reubicada dentro de
"Factor del mes" en lugar de en su sección.

**Lo que esto le exige al modelo.** Un módulo no puede tener solo condición
de entrada: necesita **condición de salida declarada**. Si la logística de
envíos deja de reportarse, el informe debe decir por qué — se resolvió, bajó
del umbral, o se dejó de medir. Sin eso, el formato permite que un problema
desaparezca del reporting sin haberse resuelto, y esa es una falla del
sistema, no del analista.

Esta regla —*todo módulo declara entrada y salida*— es el primer requisito
funcional que el inventario produce.

### 4.2 El mismo módulo con tres nombres

La sección de capacidad aparece en los tres informes de septiembre bajo tres
títulos y tres enfoques distintos:

| Versión | Título | Comparación | Hallazgo |
|---|---|---|---|
| Sep·T | "Capacidad operativa y productividad" | jul → ago → sep | Ganancia por operador: $29,7M → $29,2M → $36,6M |
| Sep·v2 | "Capacidad operativa: la métrica de escalamiento" | jul vs. sep | 338 vs. 341 operaciones por operador: escala lineal |
| Sep·B | "Productividad operativa del equipo" | ago vs. sep | 250 → 341 por operador: +36,4% |

Los tres son correctos y los tres miden cosas distintas sobre los mismos
datos. La elección del par de meses a comparar **cambia la conclusión**: v2
concluye "la capacidad escala de forma lineal", el bimestral concluye "la
productividad subió 36%". Ambas son verdad y se excluyen mutuamente como
titular.

Para el modelo: cuando un módulo admite más de una ventana de comparación, la
ventana es **parámetro declarado**, no decisión implícita del redactor.

---

## 5. El artefacto secundario: Resumen y QA para José

Es un documento aparte, derivado del informe, con destinatario y función
propios. Estructura relevada sobre 5 ejemplares (jun, jul, ago, sep, sep·B):

| Sección | Frecuencia | Nota |
|---|---|---|
| Titular del mes | 5/5 | Núcleo |
| Grid de 6 KPIs | 5/5 | Núcleo. Subconjunto del grid del informe |
| Tabla "Lo que funcionó / Lo que hay que corregir" | 5/5 | Núcleo. 5 bullets por columna |
| El trimestre/bimestre en una línea | 5/5 | Núcleo |
| Las 3 prioridades | 5/5 | Núcleo. Siempre exactamente 3 |
| Dato de productividad del área | 1/5 | Módulo, espejo de la sección de capacidad |
| Seguimiento del compromiso anterior | 1/5 | Módulo. **Ver abajo** |
| Preguntas clave (P1…Pn) | 5/5 | Núcleo. 8 preguntas en jun-ago, 11 en sep |
| Antes de entrar a la reunión | 5/5 | Núcleo |

**El módulo que debería ser núcleo.** El resumen de septiembre bimestral
incorpora una sección que ninguno de los anteriores tiene: *"Mantener vivos
los demás proveedores"*, que retoma textualmente el compromiso asumido en el
informe de agosto y lo cierra con números (+41,3% operaciones, +61,8%
ganancia, margen conjunto de 25,0% a 25,5%).

Es la única vez en todo el corpus que un informe **cierra el ciclo de una
recomendación anterior**. Y produjo el hallazgo más fuerte de los seis meses:
los proveedores que recibieron trabajo de mantenimiento mejoraron margen, los
que no lo recibieron se desplomaron. Un grupo de control involuntario.

Si esa sección hubiera sido núcleo desde junio, la fuga de envíos no habría
podido desaparecer en silencio: el informe de septiembre habría estado
obligado a reportar qué pasó con la prioridad número uno de agosto.

**Decisión que esto sugiere para F1:** el seguimiento de recomendaciones del
período anterior pasa a núcleo, en ambos artefactos.

---

## 6. Inconsistencias detectadas

### 6.1 Reexpresión silenciosa de meses cerrados

Cada informe reexpresa los meses anteriores sin nota que lo declare:

| Mes | Primera publicación | Reexpresión posterior | Δ |
|---|---|---|---|
| Junio | 235 ventas · $77,90M | 240 → 249 ventas · $81,04M | +6,0% ventas |
| Julio | 340 ventas · $109,10M | 347 ventas · $116,50M | +6,8% facturación |
| Agosto | 530 ventas · $228,92M | 555 ventas · $236,80M | +3,4% facturación |

Las unidades de julio figuran como **432** en el informe de julio y **359** en
el de agosto. Es la discrepancia más grande de la serie (−17%) y no tiene nota.

A nivel plataforma ocurre lo mismo: ICBC agosto aparece con $11,4M en el
informe de agosto y $14,0M en la base depurada; Frávega con $93,3M y $96,9M.

Las causas son legítimas —depuración, ventas canceladas, carga tardía— pero
ninguna está declarada en el documento. **Dos informes abiertos lado a lado
muestran cifras distintas para el mismo mes sin explicación.**

### 6.2 Contradicción interna en el informe de septiembre

El resumen bimestral publica dos valores para la misma métrica: la tabla
comparativa indica 250 → 341 operaciones por operador; la serie reconstruida
desde ventas y dotación da 347 → 278 → 374. Las dos cifras están en el mismo
documento.

El origen es la diferencia de base —una mide solo la base manual sin
Tecnología, la otra el total— pero el documento no distingue las dos bases al
nombrar la métrica.

### 6.3 Categoría cargada con dos grafías

"Tecnologia" y "Tecnología" conviven en la planilla y parten la categoría en
dos al agregar. Se consolidó a mano en los informes de septiembre, lo cual
significa que **el número publicado no es reproducible desde el dato crudo**.
Está declarado en la nota metodológica, que es lo correcto, pero sigue siendo
una corrección manual sin registrar.

### 6.4 Tres cortes temporales para el mismo mes

Septiembre tiene informe trimestral, trimestral v2 y bimestral. Los tres son
del mismo mes con los mismos datos y llegan a titulares distintos. No es un
error: es la consecuencia de que el corte comparativo nunca fue un parámetro
declarado, sino una decisión tomada informe por informe.

---

## 7. Lo que el inventario le exige al modelo (entrada a F1)

1. **Identificadores estables de sección**, no numeración correlativa.
2. **Todo módulo declara condición de entrada y de salida.** Un módulo que
   deja de emitirse genera una línea que explica por qué.
3. **El corte comparativo es parámetro declarado** (mensual, bimestral,
   trimestral), no decisión implícita.
4. **La ventana de comparación de un módulo es parámetro**, no elección del
   redactor, cuando admite más de una.
5. **El seguimiento de recomendaciones del período anterior pasa a núcleo**,
   en el informe y en el resumen QA.
6. **Toda reexpresión de un mes cerrado se versiona y se declara** en el
   documento que la contiene.
7. **Una métrica, una definición, una base.** Si existen dos bases (total y
   base manual), son dos métricas con dos nombres.
8. **Ninguna corrección manual sin registro.** Lo que hoy se arregla a mano
   —la grafía de Tecnología— se corrige en el pipeline o se documenta como
   transformación.

Los puntos 7 y 8 conectan directamente con el
`Diccionario_Metricas_CanalVerde`, que ya define 16 métricas con fórmula
exacta y 12 reglas de validación. F2 construye la capa de métricas sobre ese
diccionario, no desde cero.

---

*Marcos Olmedo Wasmuth — executive-report-engine · F1*
