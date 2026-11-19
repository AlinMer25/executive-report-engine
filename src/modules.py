"""
modules.py — Módulos opcionales del informe.

Una sección del núcleo sale siempre. Un módulo sale solo si se cumple su
condición de entrada (spec §6): si no hay nada que decir, no ocupa lugar.
Por eso cada función devuelve una Seccion o None.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import config as cfg
from . import metrics as m
from . import snapshot as snap
from .sections import (Seccion, fila, filtrar_periodo, periodo_anterior, pesos,
                       porcentaje, pp)


# ──────────────────────────────────────────────────────────────────────
# Parámetros de ejecución que leen los módulos
# ──────────────────────────────────────────────────────────────────────

# Cuántos meses abarca cada corte (spec §3).
CORTES = {"mensual": 1, "bimestral": 2, "trimestral": 3,
          "cuatrimestral": 4, "semestral": 6, "anual": 12}


@dataclass
class Parametros:
    """Lo que el analista declara al generar el informe (spec §3).

    Se pasa entero a cada módulo: cada uno lee solo lo que le importa. Así,
    sumar un parámetro nuevo no obliga a cambiar la firma de todos los
    módulos.
    """
    corte: str = "trimestral"

    def __post_init__(self):
        # __post_init__ corre justo después de crear el objeto: es el lugar
        # para rechazar un valor inválido antes de que llegue a un cálculo.
        if self.corte not in CORTES:
            raise ValueError(f"corte_comparativo inválido: '{self.corte}'. "
                             f"Opciones: {', '.join(CORTES)}")


# ──────────────────────────────────────────────────────────────────────
# mod.graduacion — Canal Verde y Stock Verde
# ──────────────────────────────────────────────────────────────────────

def productos_graduados(df: pd.DataFrame, periodo: str) -> list[str]:
    """Productos que se vendieron por primera vez como Stock Verde en `periodo`
    y que antes ya se habían vendido como Canal Verde.

    Es la graduación medida, no declarada: el rastro queda en la planilla.
    """
    fechas = pd.to_datetime(df[cfg.FECHA], errors="coerce", dayfirst=True)
    mes = fechas.dt.strftime("%Y-%m")
    antes = df[mes < periodo]
    ahora = df[mes == periodo]

    stock_ahora = set(ahora.loc[ahora[cfg.CANAL] == cfg.STOCK_VERDE, cfg.PRODUCTO])
    stock_antes = set(antes.loc[antes[cfg.CANAL] == cfg.STOCK_VERDE, cfg.PRODUCTO])
    verde_antes = set(antes.loc[antes[cfg.CANAL] == cfg.CANAL_VERDE, cfg.PRODUCTO])

    return sorted(str(p) for p in (stock_ahora & verde_antes) - stock_antes)


def mod_graduacion(df: pd.DataFrame, periodo: str,
             params: Parametros | None = None) -> Seccion | None:
    """Condición de entrada: hay ventas de los dos sub-canales en el período."""
    actual = filtrar_periodo(df, periodo)
    canales = set(actual[cfg.CANAL].dropna())
    if not {cfg.CANAL_VERDE, cfg.STOCK_VERDE} <= canales:      # <= : "está contenido en"
        return None

    t = m.por_dimension(actual, cfg.CANAL)
    # fila() devuelve un dict con números simples: Pylance sabe qué tipo son.
    verde, stock = fila(t, cfg.CANAL_VERDE), fila(t, cfg.STOCK_VERDE)
    brecha = float(verde["margen_neto"] - stock["margen_neto"])

    tabla = pd.DataFrame({
        "Sub-canal": [cfg.CANAL_VERDE, cfg.STOCK_VERDE],
        "Ventas": [int(verde["operaciones"]), int(stock["operaciones"])],
        "Facturación": [pesos(verde["facturacion"]), pesos(stock["facturacion"])],
        "Participación": [porcentaje(verde["participacion"], 1),
                          porcentaje(stock["participacion"], 1)],
        "Margen neto": [porcentaje(verde["margen_neto"]),
                        porcentaje(stock["margen_neto"])],
    })

    frases = [
        f"El {porcentaje(verde['participacion'], 1)} de la facturación se generó "
        f"sin inmovilizar capital (Canal Verde). Stock Verde aportó "
        f"{pesos(stock['facturacion'])} con margen de "
        f"{porcentaje(stock['margen_neto'])}, {pp(-brecha)} respecto de Canal Verde.",
    ]

    graduados = productos_graduados(df, periodo)
    if graduados:
        frases.append(f"Productos graduados a Stock Verde en el período: "
                      f"{len(graduados)} ({', '.join(graduados[:5])}"
                      f"{'…' if len(graduados) > 5 else ''}).")
    else:
        frases.append("No hubo productos graduados a Stock Verde en el período.")
    frases.append("[Completar: lectura del mecanismo de graduación.]")

    return Seccion("mod.graduacion", "Canal Verde y Stock Verde",
                   frases=frases, tablas={"graduacion": tabla})


# ──────────────────────────────────────────────────────────────────────
# mod.logistica — fuga logística real
# ──────────────────────────────────────────────────────────────────────

def mod_logistica(df: pd.DataFrame, periodo: str,
             params: Parametros | None = None) -> Seccion | None:
    """Condición de entrada: al menos una plataforma o método de envío con
    fuga real (balance de envíos < 0, margen ≥ 1 pp debajo del canal y
    participación ≥ 1%). Ordenado por costo en pesos, no por balance.
    """
    actual = filtrar_periodo(df, periodo)
    if actual.empty:
        return None

    frases, tablas, costo_total = [], {}, 0.0
    for columna, etiqueta in ((cfg.PLATAFORMA, "Plataforma"),
                              (cfg.METODO_ENVIO, "Método de envío")):
        if columna not in actual.columns:
            continue
        t = m.fuga_logistica(actual, columna,
                             brecha_minima_pp=cfg.FUGA_BRECHA_MINIMA_PP,
                             participacion_minima=cfg.FUGA_PARTICIPACION_MINIMA)
        fugas = t[t["fuga_real"]]
        if fugas.empty:
            continue

        tablas[columna] = pd.DataFrame({
            etiqueta: fugas.index.astype(str),
            "Participación": [porcentaje(x, 1) for x in fugas["participacion"]],
            "Margen neto": [porcentaje(x) for x in fugas["margen_neto"]],
            "Brecha": [pp(x) for x in fugas["brecha_margen_pp"]],
            "Ganancia no obtenida": [pesos(-x) for x in fugas["costo_en_margen"]],
        })
        peor = fila(fugas, fugas.index[0])            # ya viene ordenado por costo
        frases.append(
            f"Por {etiqueta.lower()}: {len(fugas)} con fuga real. La de mayor costo es "
            f"{fugas.index[0]}, con margen de {porcentaje(peor['margen_neto'])} "
            f"({pp(peor['brecha_margen_pp'])} contra el canal): "
            f"{pesos(-peor['costo_en_margen'])} de ganancia no obtenida.")
        if columna == cfg.PLATAFORMA:                 # no sumar dos veces lo mismo
            costo_total = float(-fugas["costo_en_margen"].sum())

    if not tablas:
        return None

    if costo_total:
        frases.insert(0, f"Operando al margen del canal, las plataformas con fuga "
                         f"habrían generado {pesos(costo_total)} más de ganancia neta.")
    frases.append("[Completar: ¿el precio cubre el flete en estas plataformas?]")
    return Seccion("mod.logistica", "Dónde se pierde margen", frases=frases, tablas=tablas)


# ──────────────────────────────────────────────────────────────────────
# mod.evolucion — evolución dentro del período
# ──────────────────────────────────────────────────────────────────────

# Semanas fijas del mes: 1-7, 8-14, 15-21 y 22 a fin de mes. La última tiene
# entre 7 y 10 días, por eso se compara la facturación POR DÍA y no el total:
# si no, la semana 4 "ganaría" siempre por tener más días.
CORTES_SEMANA = [(1, 7), (8, 14), (15, 21), (22, 31)]


def semanas(df: pd.DataFrame, periodo: str) -> pd.DataFrame:
    """Resumen por semana del mes, con facturación diaria promedio."""
    actual = filtrar_periodo(df, periodo)
    if m.C_GANANCIA_NETA not in actual.columns:
        actual = m.calcular(actual)
    dia = pd.to_datetime(actual[cfg.FECHA], errors="coerce", dayfirst=True).dt.day
    dias_del_mes = pd.Period(periodo, freq="M").days_in_month

    filas = []
    for n, (desde, hasta) in enumerate(CORTES_SEMANA, start=1):
        hasta = min(hasta, dias_del_mes)
        tramo = actual[(dia >= desde) & (dia <= hasta)]
        dias = hasta - desde + 1
        base = float(tramo[m.C_BASE].sum())
        neta = float(tramo[m.C_GANANCIA_NETA].sum())
        filas.append({
            "semana": f"S{n} ({desde}-{hasta})",
            "dias": dias,
            "operaciones": len(tramo),
            "facturacion": base,
            "facturacion_diaria": base / dias,
            "margen_neto": neta / base * 100 if base else 0.0,
        })
    return pd.DataFrame(filas)


def mod_evolucion(df: pd.DataFrame, periodo: str,
             params: Parametros | None = None) -> Seccion | None:
    """Condición de entrada: la semana pico factura por día al menos 1,5 veces
    lo que factura la semana valle (cfg.UMBRAL_DISPERSION_SEMANAL)."""
    t = semanas(df, periodo)
    diaria = t["facturacion_diaria"]
    if t["operaciones"].sum() == 0 or diaria.min() <= 0:
        return None
    dispersion = float(diaria.max() / diaria.min())
    if dispersion < cfg.UMBRAL_DISPERSION_SEMANAL:
        return None

    # argmax/argmin devuelven la POSICIÓN (un int), no la etiqueta del índice.
    pico = fila(t, t.index[int(diaria.to_numpy().argmax())])
    valle = fila(t, t.index[int(diaria.to_numpy().argmin())])
    tabla = pd.DataFrame({
        "Semana": t["semana"],
        "Ventas": t["operaciones"],
        "Facturación": [pesos(x) for x in t["facturacion"]],
        "Facturación por día": [pesos(x) for x in t["facturacion_diaria"]],
        "Margen neto": [porcentaje(x) for x in t["margen_neto"]],
    })
    veces = f"{dispersion:.1f}".replace(".", ",")
    frases = [
        f"La facturación no fue pareja en el mes: la semana {pico['semana']} "
        f"facturó {pesos(pico['facturacion_diaria'])} por día, "
        f"{veces} veces la semana {valle['semana']} "
        f"({pesos(valle['facturacion_diaria'])} por día).",
        "[Completar: qué pasó en la semana pico (evento, promoción, plataforma).]",
    ]
    return Seccion("mod.evolucion", "Evolución dentro del período",
                   frases=frases, tablas={"semanas": tabla})


# ──────────────────────────────────────────────────────────────────────
# mod.integridad — reexpresión de meses ya publicados (spec §7)
# ──────────────────────────────────────────────────────────────────────

METRICAS_CABECERA = {
    "operaciones": "Ventas",
    "unidades": "Unidades",
    "facturacion": "Facturación",
    "ganancia_neta": "Ganancia neta",
    "margen_neto": "Margen neto",
}
UMBRAL_REEXPRESION = 5.0      # % de cambio que obliga a una sección propia


def reexpresiones(df: pd.DataFrame, periodo: str, meses: int = 6) -> pd.DataFrame:
    """Compara cada mes anterior a `periodo` contra su versión PUBLICADA.

    La versión publicada es el primer snapshot de ese mes (el que se congeló
    al entregar el informe). La actual es lo que dice hoy la planilla.
    Devuelve una fila por cada métrica que cambió, aunque sea un poco:
    core.metodologia las declara todas, mod.integridad solo las grandes.
    """
    filas = []
    for k in range(meses - 1, 0, -1):
        mes = periodo_anterior(periodo, k)
        versiones = snap.listar(mes)
        datos = filtrar_periodo(df, mes)
        if versiones.empty or datos.empty:
            continue
        publicado = fila(versiones, versiones.index[-1])   # la más vieja va última
        hoy = snap.totales(datos)
        for clave, nombre in METRICAS_CABECERA.items():
            antes, ahora = float(publicado[clave]), float(hoy[clave])
            if abs(ahora - antes) < 1e-6:                  # no cambió
                continue
            filas.append({
                "periodo": mes,
                "metrica": nombre,
                "publicado": antes,
                "actual": ahora,
                "variacion_pct": (ahora - antes) / antes * 100 if antes else 100.0,
            })
    return pd.DataFrame(filas, columns=["periodo", "metrica", "publicado",
                                        "actual", "variacion_pct"])


def valor_cabecera(metrica: str, x: float) -> str:
    """Formatea un valor según la métrica: pesos, porcentaje o cantidad."""
    if metrica == "Margen neto":
        return porcentaje(x)
    if metrica in ("Facturación", "Ganancia neta"):
        return pesos(x)
    return f"{x:,.0f}".replace(",", ".")


def mod_integridad(df: pd.DataFrame, periodo: str,
             params: Parametros | None = None) -> Seccion | None:
    """Condición de entrada: algún mes publicado cambió ≥ 5% en una métrica
    de cabecera. Los cambios menores van solo a la nota metodológica."""
    r = reexpresiones(df, periodo)
    grandes = r[r["variacion_pct"].abs() >= UMBRAL_REEXPRESION]
    if grandes.empty:
        return None

    tabla = pd.DataFrame({
        "Período": grandes["periodo"],
        "Métrica": grandes["metrica"],
        "Publicado": [valor_cabecera(mt, x) for mt, x in zip(grandes["metrica"], grandes["publicado"])],
        "Actual": [valor_cabecera(mt, x) for mt, x in zip(grandes["metrica"], grandes["actual"])],
        "Variación": [f"{x:+.1f}%".replace(".", ",") for x in grandes["variacion_pct"]],
    })
    meses = ", ".join(sorted(grandes["periodo"].unique()))
    frases = [
        f"Las cifras de {meses} difieren en más de un "
        f"{UMBRAL_REEXPRESION:.0f}% de las publicadas. Este informe usa los "
        f"valores actuales; los publicados se conservan en el registro de "
        f"versiones.",
        "[Completar: motivo de la reexpresión (carga tardía de costos, "
        "cancelaciones, depuración).]",
    ]
    return Seccion("mod.integridad", "Nota de integridad de datos",
                   frases=frases, tablas={"reexpresiones": tabla})


# ──────────────────────────────────────────────────────────────────────
# mod.evolucion_larga — analítica del corte largo
# ──────────────────────────────────────────────────────────────────────

ABREV = ["", "ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]


def ventana(periodo: str, meses: int) -> list[str]:
    """Los `meses` meses que terminan en `periodo`, del más viejo al más nuevo."""
    return [periodo_anterior(periodo, k) for k in range(meses - 1, -1, -1)]


def nombre_ventana(meses: list[str]) -> str:
    """['2026-07', '2026-08', '2026-09'] → 'jul–sep 2026'."""
    a, b = pd.Period(meses[0], freq="M"), pd.Period(meses[-1], freq="M")
    if a.year == b.year:
        return f"{ABREV[a.month]}–{ABREV[b.month]} {b.year}"
    return f"{ABREV[a.month]} {a.year}–{ABREV[b.month]} {b.year}"


def _resumen_meses(df: pd.DataFrame, meses: list[str]) -> dict | None:
    """Resumen de varios meses juntos; None si falta alguno (comparar una
    ventana incompleta contra una completa sería engañoso)."""
    partes = [filtrar_periodo(df, mes) for mes in meses]
    if any(p.empty for p in partes):
        return None
    return m.resumen(pd.concat(partes))


def mod_evolucion_larga(df: pd.DataFrame, periodo: str,
                        params: Parametros | None = None) -> Seccion | None:
    """Condición de entrada: corte_comparativo distinto de 'mensual'."""
    params = params or Parametros()
    n = CORTES[params.corte]
    if n == 1:
        return None

    meses = ventana(periodo, n)
    actual = _resumen_meses(df, meses)
    if actual is None:
        return None                     # no hay datos para la ventana completa

    filas = []
    for mes in meses:
        r = m.resumen(filtrar_periodo(df, mes))
        filas.append({"Mes": mes, **r})
    filas.append({"Mes": f"Total {nombre_ventana(meses)}", **actual})
    t = pd.DataFrame(filas)

    tabla = pd.DataFrame({
        "Mes": t["Mes"],
        "Ventas": t["operaciones"].astype(int),
        "Facturación": [pesos(x) for x in t["facturacion"]],
        "Ticket promedio": [pesos(x) for x in t["ticket_promedio"]],
        "Ganancia neta": [pesos(x) for x in t["ganancia_neta"]],
        "Margen neto": [porcentaje(x) for x in t["margen_neto"]],
    })

    nombre = nombre_ventana(meses)
    previos = ventana(periodo_anterior(periodo, n), n)
    anterior = _resumen_meses(df, previos)

    if anterior is None:
        frases = [
            f"El período {nombre} ({params.corte}) facturó "
            f"{pesos(actual['facturacion'])} con margen neto de "
            f"{porcentaje(actual['margen_neto'])}. No hay datos completos de "
            f"{nombre_ventana(previos)} para comparar.",
        ]
    else:
        var = (actual["facturacion"] / anterior["facturacion"] - 1) * 100
        dif = actual["margen_neto"] - anterior["margen_neto"]
        frases = [
            f"El período {nombre} ({params.corte}) facturó "
            f"{pesos(actual['facturacion'])}, "
            f"{f'{var:+.1f}%'.replace('.', ',')} contra {nombre_ventana(previos)}. "
            f"El margen neto fue {porcentaje(actual['margen_neto'])} ({pp(dif)}) y "
            f"la ganancia neta, {pesos(actual['ganancia_neta'])}.",
        ]
    frases.append("[Completar: tendencia del período y qué la explica.]")

    return Seccion("mod.evolucion_larga", f"Analítica {params.corte} ({nombre})",
                   frases=frases, tablas={"evolucion_larga": tabla})


# ──────────────────────────────────────────────────────────────────────
# Registro: el orden de esta lista es el orden en el informe
# ──────────────────────────────────────────────────────────────────────

MODULOS = [mod_integridad, mod_logistica, mod_evolucion, mod_evolucion_larga,
           mod_graduacion]


def activos(df: pd.DataFrame, periodo: str,
            params: Parametros | None = None) -> list[Seccion]:
    """Corre todos los módulos y devuelve solo los que cumplieron su condición."""
    resultado = []
    for modulo in MODULOS:
        s = modulo(df, periodo, params or Parametros())
        if s is not None:
            resultado.append(s)
    return resultado