# Apuntes de método

Criterios de trabajo que fui adoptando al construir este proyecto.
No son notas sobre *este* repo: son reglas que se aplican a cualquier proyecto
de software o de datos. Cada entrada dice **qué se hace**, **por qué**, y
**cómo se traslada** a otro contexto.

Documento vivo. Se agrega al final a medida que aparecen prácticas nuevas.

---

## 1. Antes de escribir código

### 1.1 El spec va primero, y no tiene una línea de código

**Qué.** Antes de programar se escribe un documento que define qué debe hacer
el sistema, con qué entradas, bajo qué condiciones y con qué salidas.

**Por qué.** Las decisiones difíciles de un sistema casi nunca son técnicas.
"¿Cuándo se emite esta sección?" no se resuelve programando: se resuelve
decidiendo. Si se empieza por el código, esas decisiones se terminan tomando
por accidente, escondidas adentro de un `if`, y nadie —ni uno mismo tres meses
después— puede auditarlas.

**Cómo se traslada.** En cualquier proyecto: antes de la primera línea, escribir
qué entra, qué sale, y qué reglas gobiernan el medio. Si no se puede escribir,
tampoco se puede programar.

### 1.2 Relevar antes de diseñar

**Qué.** Cuando ya existe una práctica manual que el sistema va a reemplazar,
primero se la inventaria: qué se hizo realmente, cuántas veces, con qué
variantes.

**Por qué.** Un diseño sacado de la cabeza refleja lo que uno cree que hace. Un
inventario refleja lo que hizo. En este proyecto, poner siete informes en una
tabla reveló que una sección marcada como "prioridad máxima" durante tres meses
había desaparecido sin que nadie lo notara. Ese hallazgo no salía de ningún
diseño previo: salía de contar.

**Cómo se traslada.** Antes de automatizar un proceso, documentar el proceso tal
como es. La frecuencia de cada paso te dice qué es núcleo y qué es excepción.

### 1.3 La gobernanza de datos va antes que el primer commit

**Qué.** Si el proyecto toca datos sensibles, la política de qué se publica y
qué no se escribe **antes** de que entre el primer dato.

**Por qué.** Un commit es inmutable. Un dato que entra al historial sigue ahí
aunque se borre el archivo después; sacarlo requiere reescribir el historial.
La única protección barata es que nunca entre.

**Cómo se traslada.** Primer commit de cualquier repo con datos: el
`.gitignore` y la política. Después, todo lo demás.

---

## 2. Git

### 2.1 Lo que no está commiteado no existe

**Qué.** Un `git init` sin commits es una carpeta vacía con una subcarpeta
oculta adentro. Trabajo sin artefacto verificable es trabajo que no pasó.

**Por qué.** Es fácil confundir "empecé" con "avancé". El historial de git es
el único registro que no miente.

**Cómo se traslada.** Para medir progreso real, mirar el log, no la intención.
Aplica fuera de la programación: un informe que no se entregó no existe.

### 2.2 El `.gitignore` se escribe por extensión, no por carpeta

**Qué.** En vez de ignorar `data/raw/*.xlsx`, se ignora **todo** `*.xlsx` en
cualquier lugar, y después se habilita la excepción con `!data/sample/*.csv`.

**Por qué.** Una regla que depende de que uno guarde el archivo en la carpeta
correcta no es una política: es una esperanza. La red se teje para el día en que
uno está distraído, no para cuando está atento.

**Revisarla cada vez que aparece un formato nuevo.** En este proyecto el
`.gitignore` bloqueaba planillas en cinco extensiones, y apareció una exportación
en `.txt` con datos de clientes que pasaba por el agujero. Una política de
bloqueo no es permanente: envejece con cada formato nuevo que entra al proyecto.

**Cómo se traslada.** Bloquear por defecto, habilitar lo seguro. Es el mismo
principio que en seguridad informática: *deny by default*.

### 2.3 El orden del historial es un argumento

**Qué.** El primer commit de este repo es la política de anonimización, no el
código.

**Por qué.** Cuando alguien audita el historial, lo primero que ve es que la
gobernanza vino antes que la primera línea. Eso no se puede fingir después: el
historial es inmutable y está fechado.

**Cómo se traslada.** El orden en que se hacen las cosas queda registrado.
Conviene que ese registro cuente la historia correcta.

### 2.4 Normalizar los fines de línea

**Qué.** `git config --global core.autocrlf true` en Windows.

**Por qué.** Windows termina las líneas con dos caracteres invisibles y
Linux/Mac con uno. Sin normalizar, git marca archivos como modificados cuando
nadie los tocó, y los diffs se llenan de ruido.

**Cómo se traslada.** Una vez por máquina, en cualquier repo que vaya a tocar
más de un sistema operativo.

---

### 2.5 Un commit, una historia

**Qué.** Antes de `git commit`, mirar `git status` y separar lo que no pertenece
al mismo cambio. `git restore --staged <archivo>` lo saca de la tanda sin
borrar nada.

**Por qué.** Si el spec y el código viajan juntos, después no se puede volver
atrás uno sin el otro, y el historial deja de contar qué pasó.

**Cómo se traslada.** Documentación por un lado, código por otro; un fix no
viaja con una funcionalidad nueva.

### 2.6 Excepciones al `.gitignore`: declararlas, no forzarlas

**Qué.** Para subir un archivo que el `.gitignore` bloquea (los datos
sintéticos de muestra), se agrega una excepción con `!`:
`!data/sample/*.xlsx`. No se usa `git add -f`.

**Por qué.** `-f` fuerza ese archivo una vez y no deja rastro de la decisión.
La excepción queda escrita, se lee y vale para todos.

**Cómo se traslada.** Toda decisión que se repite tiene que vivir en un archivo,
no en la memoria de quien tipeó el comando.

### 2.7 La terminal no perdona un carácter

**Qué.** `&&` encadena comandos ("si el anterior salió bien, seguí").
`$$` es otra cosa: Bash lo reemplaza por el número de proceso (de ahí el
misterioso `1394`). Un typo como `psuh` simplemente falla.

**Por qué.** La terminal ejecuta exactamente lo que se escribe, no lo que se
quiso escribir.

**Cómo se traslada.** Ante un resultado raro, releer el comando carácter por
carácter antes de buscar el error en otro lado.

## 3. Entorno de trabajo

### 3.1 Entorno virtual por proyecto

**Qué.** `python -m venv .venv` y activarlo antes de trabajar. La carpeta
`.venv` va al `.gitignore`.

**Por qué.** Sin aislamiento, todas las librerías se instalan en el Python del
sistema, y dos proyectos que necesitan versiones distintas de la misma librería
se pisan. El venv le da a cada proyecto las suyas.

**Cómo se traslada.** Todo lenguaje tiene su equivalente. La idea es la misma:
las dependencias pertenecen al proyecto, no a la máquina.

### 3.2 `requirements.txt`: la receta exacta

**Qué.** `pip freeze > requirements.txt` deja escritas las versiones exactas
instaladas.

**Por qué.** Es lo que permite que otra persona clone el repo y reproduzca el
entorno con un comando. Sin eso, el proyecto funciona en una sola computadora
del mundo: la propia.

**Cómo se traslada.** Reproducible significa que otro lo corre sin vos. Si para
correrlo hace falta preguntarte algo, no es reproducible.

---

## 4. Diseño del sistema

### 4.1 Identificadores estables, no números de orden

**Qué.** Las secciones se referencian por ID (`mod.logistica`), nunca por
posición (`sección 7`).

**Por qué.** El número cambia en cuanto cambia la composición, y todas las
referencias quedan rotas y apuntando a otra cosa. El ID no se mueve.

**Cómo se traslada.** Vale para secciones, para filas de una base y para
cualquier cosa referenciada desde otro lado. La posición es un accidente; la
identidad no.

### 4.2 Leer por nombre, no por posición

**Qué.** El código busca la columna `"Proveedor"`, no la columna `R`.

**Por qué.** En este proyecto el diccionario de métricas documentaba columnas
por letra, y cuando se insertaron columnas en la planilla las letras se
corrieron —algunas 2 posiciones, otras 5— sin avisar. Un código atado a letras
habría devuelto números equivocados **sin fallar**, que es el peor modo de
fallar.

**Cómo se traslada.** Donde haya un contrato entre dos sistemas, atarlo a
nombres. Un error ruidoso es mejor que un resultado silenciosamente incorrecto.

### 4.3 Las decisiones implícitas se vuelven parámetros declarados

**Qué.** Lo que antes se decidía informe por informe —si comparar contra el mes,
el bimestre o el trimestre— pasa a ser un parámetro con nombre, valor por
defecto y registro en la salida.

**Por qué.** Una decisión invisible no se puede discutir ni auditar. Tres
informes del mismo mes con tres conclusiones distintas no son un error: son el
resultado de una elección que nadie declaró.

**Cómo se traslada.** Cuando dos corridas del mismo proceso dan resultados
distintos, hay un parámetro oculto. Sacarlo a la superficie y ponerle nombre.

### 4.4 Los umbrales se calibran contra datos reales

**Qué.** El umbral que decide cuándo se emite una alerta se prueba contra la
serie histórica antes de fijarlo.

**Por qué.** Un umbral inventado falla de dos maneras: si es muy bajo suena
siempre y se ignora a los dos meses; si es muy alto no suena nunca. El 26% de
margen que se recomendó dos veces se habría roto tres meses seguidos: habría
sido ruido, no alarma.

**Cómo se traslada.** Antes de fijar cualquier umbral, correrlo mentalmente
contra los últimos períodos. Si hubiera disparado siempre o nunca, está mal.

### 4.5 Toda condición de entrada necesita su condición de salida

**Qué.** Si una sección aparece cuando se cumple algo, tiene que declarar algo
cuando deja de aparecer.

**Por qué.** Sin eso, un problema puede desaparecer del reporte sin haberse
resuelto. Pasó: una fuga escalada durante tres informes dejó de reportarse en el
cuarto, sin cifra de cierre y sin que nadie lo decidiera.

**Cómo se traslada.** Vale para alertas, monitoreo, tableros y actas de reunión.
Que algo deje de mostrarse es información, y hay que emitirla.

---

## 5. Trabajo con datos

### 5.1 Perfilar antes de calcular

**Qué.** Antes de escribir una sola métrica: contar filas, listar los valores
distintos de cada columna categórica, buscar vacíos y duplicados.

**Por qué.** En este proyecto, perfilar cinco columnas reveló que la planilla
contenía **dos canales de negocio distintos** mezclados, y que seis meses de
informes los venían sumando sin declararlo. Ninguna fórmula lo habría detectado:
las fórmulas estaban bien, el universo era otro.

**Cómo se traslada.** Primera media hora de cualquier dataset nuevo: `value_counts`
de cada columna categórica. Los errores de universo son más caros que los
errores de cálculo y mucho más difíciles de ver.

### 5.2 Un diccionario de métricas es un contrato

**Qué.** Un documento que define cada métrica con su fórmula exacta, su columna
de origen, su rango esperado y sus reglas de validación. Con una regla de oro:
*ninguna métrica se reporta si no está definida ahí primero*.

**Por qué.** Sin eso, "margen" significa cosas distintas según quién lo calcule,
y dos informes del mismo mes no coinciden. Con eso, la discusión se da una vez
y queda escrita.

**Cómo se traslada.** Cualquier equipo que reporte números necesita uno. Es la
pieza más barata de construir y la que más discusiones evita.

### 5.3 Separar el error de cálculo del error de universo

**Qué.** Cuando dos números no coinciden, preguntarse primero *"¿estamos
contando las mismas filas?"* antes de revisar la fórmula.

**Por qué.** Las fórmulas de este proyecto estaban verificadas al centavo contra
los datos reales. La discrepancia entre informes no venía de ahí: venía de que
cada corrida incluía un conjunto distinto de filas.

**Cómo se traslada.** Ante cualquier descuadre: filas primero, fórmula después.

### 5.4 El formato de un número se decide por columna, no por celda

**Qué.** Para saber si "1.105" es mil ciento cinco o uno coma ciento cinco
(el factor de IVA 10,5%), el parser mira la columna entera: si *alguna* celda
usa coma decimal (`.any()`), toda la columna se lee en formato argentino.

**Por qué.** Mirando celda por celda, el mismo texto se interpretaba distinto
según la fila. Una columna tiene un solo formato.

**Cómo se traslada.** Las decisiones de formato se toman sobre el conjunto,
nunca sobre el valor aislado.

### 5.5 Los caracteres invisibles rompen sistemas

**Qué.** Un espacio al final de un encabezado (`"Pago x Envio "`) o un signo
menos tipográfico (`−`, U+2212) en lugar del guion (`-`) se ven iguales y no lo
son. Al leer la planilla, el motor limpia los encabezados con `.strip()`.

**Por qué.** Ayer el informe se cayó por un espacio que no se veía, y la suite
de tests no corría por un `−` copiado.

**Cómo se traslada.** Normalizar en la puerta de entrada (`strip`, minúsculas
cuando corresponda) y escribir el código solo con caracteres del teclado.

## 6. Tests y calidad

### 6.1 Todo bug se convierte en test

**Qué.** Cuando aparece un error con datos reales, primero se escribe el test
que lo reproduce y después se corrige. Ejemplos: el "1.105", los errores
`#REF!` (R16) y el encabezado con espacio.

**Por qué.** Un bug corregido sin test puede volver sin que nadie lo note.
Con test, vuelve y la suite lo grita.

**Cómo se traslada.** La suite de tests es la memoria del proyecto: cada fila
rara que te enseñó algo queda ahí para siempre.

### 6.2 Datos sintéticos con semilla fija

**Qué.** `sample_data.py` genera ventas al azar pero con `SEMILLA = 2026`:
cada corrida produce exactamente las mismas filas.

**Por qué.** Si los datos cambian en cada corrida, un test que falla no se puede
repetir ni investigar. Con semilla fija, el azar se vuelve reproducible.

**Cómo se traslada.** Todo lo aleatorio que se use para probar lleva semilla.

### 6.3 Las quejas del verificador de tipos se resuelven, no se silencian

**Qué.** Cuando Pylance marca algo, se reescribe el código para que el tipo
quede claro: `to_dict("index")` en lugar de `.loc[r, c]`, `to_numpy(dtype=float)`,
`cast(ParagraphStyle, ...)`, o chequear `is not None` antes de usar algo.

**Por qué.** Cada advertencia es una pregunta del tipo "¿y si esto viene vacío?".
Contestarla en el código evita el error en producción.

**Cómo se traslada.** "0 errores" es una condición de commit, igual que los
tests en verde.

## 7. Diseño del motor

### 7.1 Calcular y escribir son trabajos separados

**Qué.** `metrics.py` y `sections.py` calculan; `report.py` y `charts.py` solo
dibujan lo que reciben.

**Por qué.** Si un número sale mal, se sabe dónde buscar. Y el mismo cálculo
puede alimentar un .docx, un gráfico o, mañana, una web.

**Cómo se traslada.** Separar "qué digo" de "cómo lo muestro" en cualquier
informe, planilla o sistema.

### 7.2 Lo que tiene datos reales no toca el disco si no hace falta

**Qué.** Los gráficos se generan en memoria (`BytesIO`) y entran directo al
Word; no quedan PNG sueltos.

**Por qué.** Cada archivo intermedio es una copia más de información
confidencial que puede filtrarse o subirse por error.

**Cómo se traslada.** Minimizar las copias de datos sensibles es parte del
diseño, no un detalle.

---

*Marcos Olmedo Wasmuth — executive-report-engine*