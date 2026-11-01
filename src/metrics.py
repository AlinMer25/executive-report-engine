"""
metrics.py — Las métricas del canal, recalculadas desde sus insumos.

Decisión central: el motor NO lee las columnas ya calculadas de la planilla.
Las vuelve a calcular desde precio, costo, comisión e IVA, siguiendo las
fórmulas del diccionario de métricas.

Parece trabajo duplicado y no lo es. Recalcular permite **contrastar**: si el
número del motor y el de la planilla difieren en una fila, hay un error de
carga en esa fila. Es la caza del caso de la heladera —aquel margen de 74% que
era un costo mal cargado— convertida en una función que corre sola.

Leer la columna ya hecha sería confiar. Recalcular es verificar.

Referencia: docs/03-diccionario-de-metricas.md
"""

from __future__ import annotations

import pandas as pd

from . import config as cfg

# Nombres de las columnas que este módulo agrega.
# Llevan prefijo para no pisar nunca las de la planilla: así las dos
# versiones conviven y se pueden comparar.
C_BASE = "calc_base_imponible"
C_COMISION = "calc_comision"
C_COSTO_SIN_IVA = "calc_costo_sin_iva"
C_IIBB = "calc_iibb"
C_GANANCIA_BRUTA = "calc_ganancia_bruta"
C_MARGEN_BRUTO = "calc_margen_bruto"
C_DIF_ENVIO = "calc_diferencia_envio"
C_DIF_ENVIO_RECALC = "calc_diferencia_envio_recalculada"
C_GANANCIA_NETA = "calc_ganancia_neta"
C_MARGEN_NETO = "calc_margen_neto"


# ──────────────────────────────────────────────────────────────────────
# Cálculo fila por fila
# ──────────────────────────────────────────────────────────────────────

def calcular(df: pd.DataFrame, origen_envio: str = "planilla") -> pd.DataFrame:
    """Agrega las columnas recalculadas, sin tocar las originales.

    Todo el cálculo se bifurca según el régimen fiscal. En Blanco se
    descuenta IVA e IIBB; en Negro no. No es un detalle contable: cambia
    la base de cálculo del margen, y comparar un margen Blanco con uno
    Negro sin segmentar lleva a conclusiones falsas.

    origen_envio : 'planilla' (default) o 'recalculado'
        De dónde sale la diferencia de envío. El default NO es recalcular,
        y es la única excepción de este módulo. Motivo: la columna
        'Pago x Envio' está contaminada en 44 filas, donde se completó
        copiando el costo en envíos que en realidad el marketplace no paga.
        Recalcular desde un insumo contaminado da cero donde hubo un costo
        real. La columna 'Diferencia Envio' de la planilla es un hecho
        registrado, no un derivado, y es la fuente confiable.
        'recalculado' existe para auditar: ver contraste().
    """
    if origen_envio not in ("planilla", "recalculado"):
        raise ValueError("origen_envio debe ser 'planilla' o 'recalculado'")
    d = df.copy()
    es_blanco = d[cfg.REGIMEN] == cfg.REGIMEN_BLANCO

    # Base imponible: sobre qué monto se mide la rentabilidad.
    # Blanco: monto sin IVA. Negro: monto con IVA.
    d[C_BASE] = d[cfg.MONTO_SIN_IVA].where(es_blanco, d[cfg.MONTO])

    # La comisión de plataforma se calcula SIEMPRE sobre el monto con IVA,
    # sea cual sea el régimen. Es lo que la plataforma efectivamente retiene.
    d[C_COMISION] = d[cfg.MONTO] * d[cfg.COMISION_PCT] / 100

    # El costo de compra se netea de IVA con el mismo factor del producto
    # (1,105 o 1,21 según la alícuota).
    d[C_COSTO_SIN_IVA] = d[cfg.COSTO_TOTAL] / d[cfg.CALCULO_IVA]

    # Ingresos Brutos: 4% de la base, SOLO en ventas Blanco.
    d[C_IIBB] = (d[C_BASE] * cfg.TASA_IIBB).where(es_blanco, 0.0)

    d[C_GANANCIA_BRUTA] = (
        d[C_BASE] - d[C_IIBB] - d[C_COSTO_SIN_IVA] - d[C_COMISION]
    )
    d[C_MARGEN_BRUTO] = d[C_GANANCIA_BRUTA] / d[C_BASE]

    # Resultado logístico de la venta.
    # Atención a la interpretación: un valor negativo NO implica una fuga.
    # Cuando el costo del flete ya está incorporado al precio de venta, ese
    # costo se recupera por el lado del ingreso y el margen no se resiente.
    # Para saber si hay fuga real hay que mirar el margen del método de
    # envío, no el signo de esta columna. Ver fuga_logistica().
    d[C_DIF_ENVIO_RECALC] = d[cfg.PAGO_ENVIO] - d[cfg.COSTO_ENVIO]
    d[C_DIF_ENVIO] = (d[cfg.DIFERENCIA_ENVIO] if origen_envio == "planilla"
                      else d[C_DIF_ENVIO_RECALC])

    # Asimetría real del sistema, no un error: en Blanco el envío entra con
    # IVA; en Negro, neteado. Así está definido y así lo calcula la planilla.
    envio_aplicado = d[C_DIF_ENVIO].where(es_blanco, d[C_DIF_ENVIO] / cfg.IVA_ENVIO)

    d[C_GANANCIA_NETA] = d[C_GANANCIA_BRUTA] + envio_aplicado
    d[C_MARGEN_NETO] = d[C_GANANCIA_NETA] / d[C_BASE]

    return d


# ──────────────────────────────────────────────────────────────────────
# Agregación de un período
# ──────────────────────────────────────────────────────────────────────

def resumen(df: pd.DataFrame) -> dict:
    """Totales del período, con el margen ponderado.

    El margen del período es Σ ganancia / Σ base, NUNCA el promedio de los
    márgenes de cada venta. Una venta de $1M al 5% y otra de $10K al 50% no
    promedian 27,5%: el ponderado da 5,4%. El promedio simple sobrepondera
    las ventas chicas y puede invertir la conclusión del informe.
    """
    if C_GANANCIA_NETA not in df.columns:
        df = calcular(df)

    base = df[C_BASE].sum()
    bruta = df[C_GANANCIA_BRUTA].sum()
    neta = df[C_GANANCIA_NETA].sum()

    return {
        "operaciones": int(len(df)),
        "unidades": float(df[cfg.CANTIDAD].sum()),
        "facturacion": float(base),
        "ticket_promedio": float(base / len(df)) if len(df) else 0.0,
        "ganancia_bruta": float(bruta),
        "ganancia_neta": float(neta),
        "margen_bruto": float(bruta / base * 100) if base else 0.0,
        "margen_neto": float(neta / base * 100) if base else 0.0,
        "balance_envios": float(df[C_DIF_ENVIO].sum()),
        "ventas_con_flete_negativo": int((df[C_DIF_ENVIO] < 0).sum()),
        "ventas_a_perdida": int((df[C_GANANCIA_NETA] < 0).sum()),
    }


def por_dimension(df: pd.DataFrame, dimension: str,
                  minimo_operaciones: int = 1) -> pd.DataFrame:
    """Resumen agrupado por plataforma, categoría, proveedor o canal.

    Devuelve siempre facturación Y margen juntos. Un ranking solo por
    volumen esconde exactamente el fenómeno que este proyecto vino a medir:
    facturar más no es ganar más.
    """
    if C_GANANCIA_NETA not in df.columns:
        df = calcular(df)

    g = df.groupby(dimension, dropna=False)
    tabla = pd.DataFrame({
        "operaciones": g.size(),
        "unidades": g[cfg.CANTIDAD].sum(),
        "facturacion": g[C_BASE].sum(),
        "ganancia_neta": g[C_GANANCIA_NETA].sum(),
        "balance_envios": g[C_DIF_ENVIO].sum(),
    })
    tabla["margen_neto"] = tabla["ganancia_neta"] / tabla["facturacion"] * 100
    tabla["participacion"] = tabla["facturacion"] / tabla["facturacion"].sum() * 100

    tabla = tabla[tabla["operaciones"] >= minimo_operaciones]
    return tabla.sort_values("facturacion", ascending=False)


# ──────────────────────────────────────────────────────────────────────
# Contraste contra la planilla
# ──────────────────────────────────────────────────────────────────────

# Qué columna recalculada se compara contra cuál de la planilla.
PARES_DE_CONTRASTE = [
    (C_COMISION, cfg.COMISION_PESOS),
    (C_COSTO_SIN_IVA, cfg.COSTO_SIN_IVA),
    (C_IIBB, cfg.IIBB),
    (C_GANANCIA_BRUTA, cfg.GANANCIA_BRUTA),
    (C_DIF_ENVIO_RECALC, cfg.DIFERENCIA_ENVIO),
    (C_GANANCIA_NETA, cfg.GANANCIA_NETA),
]


def contraste(df: pd.DataFrame, tolerancia: float = 1.0) -> pd.DataFrame:
    """Compara lo recalculado contra lo que dice la planilla.

    Devuelve una fila por cada discrepancia mayor a `tolerancia` pesos.
    Una tabla vacía significa que la planilla y el motor coinciden: la
    carga está sana.

    La tolerancia por defecto es de un peso, para no marcar diferencias de
    redondeo. Subirla esconde errores; bajarla llena la salida de ruido.
    """
    if C_GANANCIA_NETA not in df.columns:
        df = calcular(df)

    hallazgos = []
    for calculada, de_planilla in PARES_DE_CONTRASTE:
        if de_planilla not in df.columns:
            continue
        diferencia = df[calculada] - df[de_planilla]
        marcadas = df[diferencia.abs() > tolerancia]

        # Se arma la tabla por columnas en vez de fila por fila. Es más
        # rápido, y además evita el acceso df.at[fila, columna], que
        # devuelve un valor de tipo indefinido para el verificador de tipos.
        if len(marcadas):
            hallazgos.append(pd.DataFrame({
                "fila": marcadas.index,
                "fecha": marcadas[cfg.FECHA].to_numpy(),
                "producto": marcadas[cfg.PRODUCTO].to_numpy(),
                "metrica": calculada.replace("calc_", ""),
                "motor": marcadas[calculada].round(2).to_numpy(),
                "planilla": marcadas[de_planilla].round(2).to_numpy(),
                "diferencia": diferencia[marcadas.index].round(2).to_numpy(),
            }))

    if not hallazgos:
        return pd.DataFrame(columns=["fila", "fecha", "producto", "metrica",
                                     "motor", "planilla", "diferencia"])
    return pd.concat(hallazgos, ignore_index=True).sort_values(
        "diferencia", key=lambda s: s.abs(), ascending=False
    )


# ──────────────────────────────────────────────────────────────────────
# Fuga logística real
# ──────────────────────────────────────────────────────────────────────

def fuga_logistica(df: pd.DataFrame, dimension: str = cfg.METODO_ENVIO,
                   margen_referencia: float | None = None,
                   brecha_minima_pp: float = 1.0,
                   participacion_minima: float = 1.0) -> pd.DataFrame:
    """Identifica dónde se pierde margen de verdad, y cuánto cuesta en pesos.

    Un balance de envíos negativo NO es, por sí solo, una fuga. Cuando el
    costo del flete está incorporado al precio de venta, el ingreso lo
    compensa y el margen queda intacto. Ordenar por monto absoluto de envío
    ordena por tamaño de plataforma, no por gravedad del problema.

    Pero lo inverso también es cierto, y es lo que vuelve indispensable esta
    función: **que el costo esté incorporado al precio es una política, no un
    resultado.** Si el precio no alcanza a cubrirlo, el margen cae igual. La
    única evidencia de que la política funcionó es el margen.

    Por eso el criterio combina las dos señales: hay fuga cuando el balance
    de envíos es negativo Y el margen queda por debajo de la referencia.
    'costo_en_margen' cuantifica en pesos la ganancia no obtenida.

    dimension : columna por la que agrupar — método de envío o plataforma.
    brecha_minima_pp : puntos por debajo de la referencia para marcar fuga.
    participacion_minima : % de facturación mínimo para entrar en el análisis.
        Evita que una plataforma de tres operaciones encabece el ranking por
        un margen extremo sobre una base irrelevante.
    """
    if C_GANANCIA_NETA not in df.columns:
        df = calcular(df)

    if margen_referencia is None:
        margen_referencia = df[C_GANANCIA_NETA].sum() / df[C_BASE].sum() * 100

    g = df.groupby(dimension, dropna=False)
    t = pd.DataFrame({
        "operaciones": g.size(),
        "facturacion": g[C_BASE].sum(),
        "balance_envios": g[C_DIF_ENVIO].sum(),
        "ganancia_neta": g[C_GANANCIA_NETA].sum(),
    })
    t["margen_neto"] = t["ganancia_neta"] / t["facturacion"] * 100
    t["participacion"] = t["facturacion"] / t["facturacion"].sum() * 100
    t["envio_sobre_facturacion"] = t["balance_envios"] / t["facturacion"] * 100
    t["brecha_margen_pp"] = t["margen_neto"] - margen_referencia
    t["costo_en_margen"] = t["brecha_margen_pp"] / 100 * t["facturacion"]

    # Fuga real: pierde en flete, rinde por debajo del canal, y pesa lo
    # suficiente como para que corregirlo cambie el resultado.
    t["fuga_real"] = (
        (t["balance_envios"] < 0)
        & (t["brecha_margen_pp"] <= -brecha_minima_pp)
        & (t["participacion"] >= participacion_minima)
    )

    return t.sort_values("costo_en_margen")