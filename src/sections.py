"""
sections.py — Decide qué secciones lleva el informe y calcula su contenido.

Es el puente entre el spec y el documento. Toma la planilla ya cargada y
devuelve una lista de secciones, cada una con sus frases y sus tablas. No
dibuja gráficos ni escribe archivos: de eso se ocupan charts.py y report.py.

La separación tiene un motivo práctico: este archivo se puede testear sin
abrir ningún .docx. Si una cifra del informe sale mal, el error está acá;
si sale bien pero se ve mal, está en report.py.

Las frases son plantillas con los números del período (decisión D11 del
spec): el analista las edita y enriquece. El motor dice qué pasó; la
interpretación sigue siendo del analista.

Referencia: docs/02-spec-del-modelo.md, secciones 5 y 6.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field

import pandas as pd

from . import config as cfg
from .ingest import a_fecha
from . import metrics as m

# Participación mínima (% de facturación) para que algo cuente como relevante
# en rankings y gráficos. Confirmado en 5%.
UMBRAL_RELEVANCIA = 5.0

MESES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo",
         6: "junio", 7: "julio", 8: "agosto", 9: "septiembre",
         10: "octubre", 11: "noviembre", 12: "diciembre"}


# ──────────────────────────────────────────────────────────────────────
# La unidad del informe
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Seccion:
    """Una sección del informe, lista para que report.py la escriba.

    id      : identificador estable del spec ('core.kpis'). Nunca un número:
              la numeración depende de qué módulos se activen.
    titulo  : lo que se lee en el documento.
    frases  : párrafos plantilla con los números ya puestos.
    tablas  : tablas para mostrar, con un nombre cada una.
    alertas : callouts destacados (los "puntos de atención").
    graficos: imágenes PNG (bytes) que report.py inserta después de las tablas.
    """
    id: str
    titulo: str
    frases: list[str] = field(default_factory=list)
    tablas: dict[str, pd.DataFrame] = field(default_factory=dict)
    alertas: list[str] = field(default_factory=list)
    graficos: dict[str, bytes] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# Formato argentino para las frases
# ──────────────────────────────────────────────────────────────────────

# Modo público (spec §3, modo_publicacion): cuando _UNIDAD tiene un valor,
# pesos() deja de escribir pesos y escribe "unidades base": 1 u. = 1% de la
# facturación del mes base. Las proporciones se conservan; la magnitud no.
_UNIDAD: float | None = None


@contextmanager
def publicacion(facturacion_base: float):
    """Activa el modo público mientras dura el bloque `with`.

    Un context manager garantiza que el modo se apague al salir, incluso si
    algo falla adentro. Sin él, un error a mitad de camino dejaría el modo
    público prendido para lo que se genere después.
    """
    global _UNIDAD
    if facturacion_base <= 0:
        raise ValueError("La facturación del mes base tiene que ser positiva.")
    _UNIDAD = facturacion_base / 100
    try:
        yield
    finally:
        _UNIDAD = None


def unidades(x: float) -> str:
    """Un monto expresado en unidades base: 143,2 u. · 0,32 u."""
    assert _UNIDAD is not None
    u = x / _UNIDAD
    decimales = 1 if abs(u) >= 100 else 2 if abs(u) >= 1 else 3
    numero = f"{u:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{numero} u."      # la unidad va después: el replace no la toca


def pesos(x: float) -> str:
    """$317,5 M para millones; $424.437 para el resto.

    En modo público devuelve unidades base (ver publicacion()).
    """
    if _UNIDAD is not None:
        return unidades(x)
    if x < 0:                               # -$147,0 M, no $-147,0 M
        return "-" + pesos(-x)
    if abs(x) >= 1_000_000:
        return f"${x / 1_000_000:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"${x:,.0f}".replace(",", ".")


def pct(x: float, decimales: int = 1) -> str:
    """+34,1% con signo, para variaciones."""
    return f"{x:+.{decimales}f}%".replace(".", ",")


def pp(x: float) -> str:
    """+1,64 pp: variación de un margen, que nunca se expresa en %."""
    return f"{x:+.2f} pp".replace(".", ",")


def porcentaje(x: float, decimales: int = 2) -> str:
    """23,04%: un nivel, sin signo."""
    return f"{x:.{decimales}f}%".replace(".", ",")


# ──────────────────────────────────────────────────────────────────────
# Períodos
# ──────────────────────────────────────────────────────────────────────

def filtrar_periodo(df: pd.DataFrame, periodo: str) -> pd.DataFrame:
    """Filas cuya fecha cae en el mes 'AAAA-MM'.

    Se filtra por la fecha y no por la columna 'Mes', porque 'Mes' no tiene
    año: 'Octubre' de 2026 y de 2027 serían lo mismo.
    """
    fechas = a_fecha(df[cfg.FECHA])        # un solo criterio de fechas en todo el motor
    return df[fechas.dt.strftime("%Y-%m") == periodo].copy()


def periodo_anterior(periodo: str, meses: int = 1) -> str:
    """'2026-10' con meses=1 → '2026-09'."""
    return (pd.Period(periodo, freq="M") - meses).strftime("%Y-%m")


def nombre_periodo(periodo: str) -> str:
    p = pd.Period(periodo, freq="M")
    return f"{MESES[p.month]} {p.year}"


def fila(tabla: pd.DataFrame, clave) -> dict:
    """Una fila de la tabla como diccionario: {'facturacion': 1.2e8, ...}.

    Se usa en lugar de tabla.loc[clave, columna], que pandas tipa como
    "cualquier cosa" y obliga a convertir cada valor a mano. El diccionario
    se lee mejor y el verificador de tipos no se queja.
    """
    return tabla.to_dict("index")[clave]


def variacion(actual: float, anterior: float) -> float:
    """Variación % con el signo de la DIRECCIÓN, no del número.

    Se divide por el valor absoluto del anterior: si la ganancia pasa de
    -72 a -147, empeoró, y la variación tiene que salir negativa. Dividiendo
    por -72 salía +104%, y el resumen lo ponía en "lo que funcionó".
    """
    return (actual - anterior) / abs(anterior) * 100 if anterior else 0.0


# ──────────────────────────────────────────────────────────────────────
# Secciones del núcleo
# ──────────────────────────────────────────────────────────────────────

def seccion_kpis(r: dict, r_ant: dict) -> Seccion:
    """core.kpis — Los indicadores del período contra el anterior."""
    filas = [
        ("Ventas", r["operaciones"], r_ant["operaciones"], "n"),
        ("Unidades", r["unidades"], r_ant["unidades"], "n"),
        ("Facturación", r["facturacion"], r_ant["facturacion"], "$"),
        ("Ticket promedio", r["ticket_promedio"], r_ant["ticket_promedio"], "$"),
        ("Ganancia neta", r["ganancia_neta"], r_ant["ganancia_neta"], "$"),
        ("Margen neto", r["margen_neto"], r_ant["margen_neto"], "%"),
    ]
    tabla = pd.DataFrame([{
        "Indicador": nombre,
        "Período": (porcentaje(a) if t == "%" else pesos(a) if t == "$" else f"{a:,.0f}".replace(",", ".")),
        "Anterior": (porcentaje(b) if t == "%" else pesos(b) if t == "$" else f"{b:,.0f}".replace(",", ".")),
        # El margen varía en puntos porcentuales, nunca en %: "cayó 1,64 pp",
        # no "cayó 6,6%". Es el invariante I6 del spec.
        "Variación": pp(a - b) if t == "%" else pct(variacion(a, b)),
    } for nombre, a, b, t in filas])
    return Seccion("core.kpis", "Indicadores clave", tablas={"kpis": tabla})


def seccion_resumen(r: dict, r_ant: dict, nombre: str, nombre_ant: str) -> Seccion:
    """core.resumen — Los cuatro párrafos del spec: resultado, causa,
    motor de rentabilidad y contracara. Acá van las dos primeras como
    plantilla; causa y contracara las completa el analista."""
    v_fact = variacion(r["facturacion"], r_ant["facturacion"])
    v_gan = variacion(r["ganancia_neta"], r_ant["ganancia_neta"])
    d_margen = r["margen_neto"] - r_ant["margen_neto"]

    frases = [
        f"{nombre.capitalize()} cerró con {r['operaciones']} ventas y "
        f"{pesos(r['facturacion'])} de facturación, {pct(v_fact)} respecto de "
        f"{nombre_ant}. La ganancia neta fue de {pesos(r['ganancia_neta'])} "
        f"({pct(v_gan)}) y el margen neto se ubicó en "
        f"{porcentaje(r['margen_neto'])} ({pp(d_margen)}).",
    ]
    # La frase de lectura cambia según la combinación de señales: es la
    # misma lógica que usaron los informes de junio y julio a mano.
    if v_fact > 0 and d_margen < 0:
        frases.append("El período facturó más pero rindió menos por cada peso "
                      "facturado: el crecimiento vino acompañado de compresión "
                      "de margen. [Completar: causa principal.]")
    elif v_fact > 0 and d_margen >= 0:
        frases.append("El período creció en facturación sosteniendo o mejorando "
                      "el margen. [Completar: qué lo explica.]")
    elif v_fact <= 0 and d_margen >= 0:
        frases.append("La facturación retrocedió, pero el margen se sostuvo o "
                      "mejoró. [Completar: causa de la caída de volumen.]")
    else:
        frases.append("Cayeron a la vez la facturación y el margen. "
                      "[Completar: causa principal.]")
    return Seccion("core.resumen", "Resumen ejecutivo", frases=frases)


def seccion_dimension(df: pd.DataFrame, columna: str, id_: str, titulo: str,
                      etiqueta: str) -> Seccion:
    """core.plataformas / core.categorias / core.proveedores.

    Siempre facturación Y margen juntos: un ranking solo por volumen
    esconde que facturar más no es ganar más.
    """
    t = m.por_dimension(df, columna)
    margen_canal = df[m.C_GANANCIA_NETA].sum() / df[m.C_BASE].sum() * 100

    tabla = pd.DataFrame({
        etiqueta: t.index.astype(str),
        "Ventas": t["operaciones"].astype(int).to_numpy(),
        "Facturación": [pesos(x) for x in t["facturacion"]],
        "Participación": [porcentaje(x, 1) for x in t["participacion"]],
        "Margen neto": [porcentaje(x) for x in t["margen_neto"]],
    })

    lider = t.index[0]
    relevantes = t[t["participacion"] >= UMBRAL_RELEVANCIA]   # se ignora lo marginal
    mejor = relevantes["margen_neto"].idxmax()
    peor = relevantes["margen_neto"].idxmin()
    L, M, P = fila(t, lider), fila(t, mejor), fila(t, peor)

    frases = [
        f"{lider} lidera con {pesos(L['facturacion'])} "
        f"({porcentaje(L['participacion'], 1)} del total) y margen de "
        f"{porcentaje(L['margen_neto'])}.",
        f"Entre los de participación relevante, el de mejor margen es {mejor} "
        f"({porcentaje(M['margen_neto'])}) y el más bajo es "
        f"{peor} ({porcentaje(P['margen_neto'])}), contra un "
        f"promedio del canal de {porcentaje(margen_canal)}.",
    ]
    return Seccion(id_, titulo, frases=frases, tablas={id_: tabla})


def seccion_productos(df: pd.DataFrame, n: int = 10) -> Seccion:
    """core.productos — Top por ganancia neta.

    En modo público el producto se muestra pero el costo de compra jamás:
    por eso la tabla no tiene ninguna columna de costo.
    """
    g = df.groupby(cfg.PRODUCTO)
    t = pd.DataFrame({
        "unidades": g[cfg.CANTIDAD].sum(),
        "facturacion": g[m.C_BASE].sum(),
        "ganancia": g[m.C_GANANCIA_NETA].sum(),
    })
    t["margen"] = t["ganancia"] / t["facturacion"] * 100
    t = t.sort_values("ganancia", ascending=False).head(n)

    tabla = pd.DataFrame({
        "Producto": t.index.astype(str),
        "Unidades": t["unidades"].astype(int).to_numpy(),
        "Ganancia neta": [pesos(x) for x in t["ganancia"]],
        "Margen": [porcentaje(x) for x in t["margen"]],
    })
    top = t.index[0]
    T = fila(t, top)
    frases = [f"{top} encabeza con {pesos(T['ganancia'])} de ganancia "
              f"neta en {int(T['unidades'])} unidades "
              f"({porcentaje(T['margen'])} de margen)."]
    return Seccion("core.productos", "Productos destacados", frases=frases,
                   tablas={"productos": tabla})


def seccion_atencion(r: dict, r_ant: dict, margenes_previos: list[float]
                     ) -> Seccion:
    """core.atencion — Los callouts obligatorios por margen (spec §6).

    Toda alerta de margen se expresa en pesos, no solo en puntos: un punto
    sobre una facturación cuatro veces mayor cuesta cuatro veces más.
    """
    s = Seccion("core.atencion", "Puntos de atención")
    margen = r["margen_neto"]
    costo = (r_ant["margen_neto"] - margen) / 100 * r["facturacion"]

    if margen < cfg.PISO_MARGEN_ALARMA_2:
        s.alertas.append(
            f"ALERTA SEVERA — El margen neto ({porcentaje(margen)}) está por debajo "
            f"del piso de {porcentaje(cfg.PISO_MARGEN_ALARMA_2, 1)}. "
            f"Frente al margen del período anterior, la diferencia equivale a "
            f"{pesos(costo)} de ganancia no obtenida.")
    elif margen < cfg.PISO_MARGEN_ALARMA_1:
        s.alertas.append(
            f"El margen neto ({porcentaje(margen)}) quedó por debajo del piso de "
            f"alarma de {porcentaje(cfg.PISO_MARGEN_ALARMA_1, 1)}. Frente al período "
            f"anterior equivale a {pesos(costo)} de ganancia no obtenida.")

    # Alarma por tendencia: N caídas seguidas, sin importar el nivel.
    serie = margenes_previos + [margen]
    n = cfg.MESES_TENDENCIA_ALARMA
    if len(serie) > n and all(serie[-i] < serie[-i - 1] for i in range(1, n + 1)):
        recorrido = " → ".join(porcentaje(x) for x in serie[-(n + 1):])
        s.alertas.append(
            f"Tendencia: el margen neto bajó {n} períodos consecutivos "
            f"({recorrido}), aunque ningún piso se haya cruzado.")

    if not s.alertas:
        s.frases.append("Sin alertas de margen en el período. "
                        "[Completar: otros puntos de atención.]")
    return s


# ──────────────────────────────────────────────────────────────────────
# Armado
# ──────────────────────────────────────────────────────────────────────

def serie_mensual(df: pd.DataFrame, periodo: str, meses: int = 6) -> pd.DataFrame:
    """Facturación y margen de los últimos `meses` meses hasta `periodo` inclusive.

    Los meses sin ventas se saltean (no se dibuja un cero falso).
    """
    filas = {}
    for k in range(meses - 1, -1, -1):
        p = periodo_anterior(periodo, k)
        datos = filtrar_periodo(df, p)
        if not datos.empty:
            r = m.resumen(datos)
            filas[p] = {"facturacion": r["facturacion"], "margen_neto": r["margen_neto"]}
    return pd.DataFrame.from_dict(filas, orient="index")


def _agregar_graficos(secciones: list[Seccion], df: pd.DataFrame,
                      actual: pd.DataFrame, periodo: str, margen: float) -> None:
    """Cuelga cada gráfico de la sección a la que pertenece."""
    from . import charts                    # import local: solo si hay gráficos

    por_id = {s.id: s for s in secciones}
    por_id["core.kpis"].graficos["evolucion"] = charts.evolucion(
        serie_mensual(df, periodo))

    plat = m.por_dimension(actual, cfg.PLATAFORMA)
    plat = plat[plat["participacion"] >= UMBRAL_RELEVANCIA]
    por_id["core.plataformas"].graficos["margen"] = charts.margen_por_dimension(
        plat, margen, "Margen neto por plataforma (participación ≥ 5%)")

    por_id["core.categorias"].graficos["fact_gan"] = charts.facturacion_y_ganancia(
        m.por_dimension(actual, cfg.CATEGORIA), "Facturación y ganancia neta por categoría")


def construir(df: pd.DataFrame, periodo: str, meses_tendencia: int = 4,
              graficos: bool = True, params=None) -> list[Seccion]:
    """Arma las secciones del núcleo para un período.

    df: planilla completa ya cargada (ingest.cargar_ventas). Se filtra acá
    para poder comparar contra períodos anteriores con la misma tabla.
    """
    df = m.calcular(df) if m.C_GANANCIA_NETA not in df.columns else df

    actual = filtrar_periodo(df, periodo)
    ant_periodo = periodo_anterior(periodo)
    anterior = filtrar_periodo(df, ant_periodo)

    if actual.empty:
        raise ValueError(f"No hay ventas en el período {periodo}.")
    if anterior.empty:
        raise ValueError(f"No hay ventas en el período anterior ({ant_periodo}) "
                         f"para comparar.")

    r, r_ant = m.resumen(actual), m.resumen(anterior)

    margenes_previos = []
    for k in range(meses_tendencia, 0, -1):
        previo = filtrar_periodo(df, periodo_anterior(periodo, k))
        if not previo.empty:
            margenes_previos.append(m.resumen(previo)["margen_neto"])

    nombre, nombre_ant = nombre_periodo(periodo), nombre_periodo(ant_periodo)
    secciones = [
        seccion_resumen(r, r_ant, nombre, nombre_ant),
        seccion_kpis(r, r_ant),
        seccion_dimension(actual, cfg.PLATAFORMA, "core.plataformas",
                          "Rendimiento por plataforma", "Plataforma"),
        seccion_dimension(actual, cfg.CATEGORIA, "core.categorias",
                          "Rendimiento por categoría", "Categoría"),
        seccion_dimension(actual, cfg.PROVEEDOR, "core.proveedores",
                          "Rendimiento por proveedor", "Proveedor"),
        seccion_productos(actual),
    ]
    from . import seguimiento as sg         # import local: evita import circular
    secciones.append(sg.seccion_seguimiento(df, periodo))
    # Módulos opcionales: entran solo si se cumple su condición (spec §6).
    from . import modules                   # import local: evita import circular
    secciones += modules.activos(df, periodo, params or modules.Parametros())
    secciones.append(seccion_atencion(r, r_ant, margenes_previos))
    secciones.append(sg.seccion_recomendaciones(periodo))
    if graficos:
        _agregar_graficos(secciones, df, actual, periodo, r["margen_neto"])
    return secciones