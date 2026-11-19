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
# Registro: el orden de esta lista es el orden en el informe
# ──────────────────────────────────────────────────────────────────────

MODULOS = [mod_graduacion]


def activos(df: pd.DataFrame, periodo: str) -> list[Seccion]:
    """Corre todos los módulos y devuelve solo los que cumplieron su condición."""
    resultado = []
    for modulo in MODULOS:
        s = modulo(df, periodo)
        if s is not None:
            resultado.append(s)
    return resultado