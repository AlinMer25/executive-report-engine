"""
modules.py — Módulos opcionales del informe.

Una sección del núcleo sale siempre. Un módulo sale solo si se cumple su
condición de entrada (spec §6): si no hay nada que decir, no ocupa lugar.
Por eso cada función devuelve una Seccion o None.
"""

from __future__ import annotations

import pandas as pd

from . import config as cfg
from . import metrics as m
from .sections import Seccion, fila, filtrar_periodo, pesos, porcentaje, pp


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


def mod_graduacion(df: pd.DataFrame, periodo: str) -> Seccion | None:
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

def mod_logistica(df: pd.DataFrame, periodo: str) -> Seccion | None:
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
    return Seccion("mod.logistica", "Fuga logística", frases=frases, tablas=tablas)


# ──────────────────────────────────────────────────────────────────────
# Registro: el orden de esta lista es el orden en el informe
# ──────────────────────────────────────────────────────────────────────

MODULOS = [mod_graduacion, mod_logistica]


def activos(df: pd.DataFrame, periodo: str) -> list[Seccion]:
    """Corre todos los módulos y devuelve solo los que cumplieron su condición."""
    resultado = []
    for modulo in MODULOS:
        s = modulo(df, periodo)
        if s is not None:
            resultado.append(s)
    return resultado