"""
ingest.py — Carga la planilla de ventas y la deja lista para calcular.

Responsabilidad única: leer el archivo, verificar que tenga lo necesario,
convertir los textos a números y descartar lo que no es una venta.
No calcula ninguna métrica: de eso se ocupa metrics.py.

La frontera importa. Si la carga también calculara, un error de lectura y un
error de fórmula se confundirían, y el descuadre sería imposible de ubicar.
"""

import pandas as pd

from . import config as cfg


# ──────────────────────────────────────────────────────────────────────
# Conversión de números
# ──────────────────────────────────────────────────────────────────────

def a_numero(serie: pd.Series) -> pd.Series:
    """Convierte texto en formato argentino a número.

    La planilla guarda ' $399.999,00': el punto separa miles y la coma
    los decimales, al revés que en Python. Sin convertir, cualquier suma
    daría error o, peor, concatenaría textos.

    Lo que no se puede convertir queda como nulo (NA), nunca como cero:
    un cero es un dato y se sumaría; un nulo es la ausencia de dato y se
    puede contar aparte.
    """
    s = serie.astype("string")
    s = s.str.replace(r"[^\d,.\-()]", "", regex=True)      # quita $, espacios, %
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)   # (1.234) → -1.234
    s = s.str.replace(".", "", regex=False)                # punto = miles
    s = s.str.replace(",", ".", regex=False)               # coma = decimal
    return pd.to_numeric(s, errors="coerce")


# Columnas que deben quedar numéricas después de cargar.
COLUMNAS_NUMERICAS = [
    cfg.CANTIDAD, cfg.IVA, cfg.CALCULO_IVA,
    cfg.PRECIO_UNITARIO, cfg.MONTO, cfg.MONTO_SIN_IVA,
    cfg.COMISION_PCT, cfg.COMISION_PESOS,
    cfg.COSTO_UNITARIO, cfg.COSTO_TOTAL, cfg.COSTO_SIN_IVA,
    cfg.IIBB, cfg.GANANCIA_BRUTA,
    cfg.PAGO_ENVIO, cfg.COSTO_ENVIO,
    cfg.DIFERENCIA_ENVIO, cfg.DIFERENCIA_ENVIO_SIN_IVA,
    cfg.GANANCIA_NETA,
]


# ──────────────────────────────────────────────────────────────────────
# Pasos de la carga
# ──────────────────────────────────────────────────────────────────────

def verificar_columnas(df: pd.DataFrame) -> None:
    """Falla de entrada si falta una columna imprescindible.

    Preferimos un error ruidoso ahora a un resultado incorrecto después.
    Es la lección del diccionario desactualizado: las columnas se buscan
    por nombre, y si el nombre no está, el motor se detiene y lo dice.
    """
    faltantes = [c for c in cfg.COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltantes:
        raise ValueError(
            "Faltan columnas obligatorias en la planilla:\n  - "
            + "\n  - ".join(faltantes)
            + "\n\nColumnas encontradas:\n  "
            + ", ".join(map(str, df.columns))
        )


def descartar_filas_vacias(df: pd.DataFrame) -> pd.DataFrame:
    """Saca las filas que no representan una venta.

    La planilla arrastra filas de plantilla al final: sin mes, sin
    plataforma y con monto en cero. Si se cuentan, inflan el
    denominador de cualquier promedio sin aportar al numerador.
    """
    tiene_mes = df[cfg.MES].notna() & (df[cfg.MES].astype("string").str.strip() != "")
    tiene_monto = df[cfg.MONTO].notna() & (df[cfg.MONTO] > 0)
    return df[tiene_mes & tiene_monto].copy()


def normalizar_texto(df: pd.DataFrame) -> pd.DataFrame:
    """Unifica los valores de texto que vienen cargados de varias formas.

    Cada corrección de acá nace de un problema real detectado al perfilar
    los datos. No se inventan: se documentan.
    """
    columnas_texto = [
        cfg.MES, cfg.REGIMEN, cfg.PLATAFORMA, cfg.METODO_ENVIO,
        cfg.CANAL, cfg.CATEGORIA, cfg.PROVEEDOR, cfg.PRODUCTO,
        cfg.SUBCATEGORIA, cfg.SUBCATEGORIA_1, cfg.FINANCIACION,
    ]
    for col in columnas_texto:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    # 'Tecnologia' / 'Tecnología' convivieron y partían la categoría en dos
    # al agregar. Hoy la planilla usa una sola grafía, pero la corrección
    # queda puesta para que un retroceso no vuelva a partir el número.
    df[cfg.CATEGORIA] = df[cfg.CATEGORIA].replace({"Tecnología": "Tecnologia"})

    return df


def convertir_numeros(df: pd.DataFrame) -> pd.DataFrame:
    """Pasa a número todas las columnas numéricas presentes."""
    for col in COLUMNAS_NUMERICAS:
        if col in df.columns:
            df[col] = a_numero(df[col])
    return df


def filtrar_canal(df: pd.DataFrame, canal: str = "ambos") -> pd.DataFrame:
    """Aplica el parámetro `canal` del spec.

    'ambos' es el default y es la cifra histórica: los dos sub-canales son
    del mismo sector. Los otros dos valores existen para aislarlos, que es
    lo que necesita mod.graduacion.
    """
    opciones = {
        "ambos": None,
        "canal_verde": cfg.CANAL_VERDE,
        "stock_verde": cfg.STOCK_VERDE,
    }
    if canal not in opciones:
        raise ValueError(
            f"canal='{canal}' no es válido. Opciones: {', '.join(opciones)}"
        )
    if opciones[canal] is None:
        return df
    return df[df[cfg.CANAL] == opciones[canal]].copy()


# ──────────────────────────────────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────────────────────────────────

def cargar_ventas(ruta, canal: str = "ambos", hoja: str = cfg.HOJA_VENTAS) -> pd.DataFrame:
    """Carga la hoja de ventas y devuelve una tabla lista para calcular.

    Parámetros
    ----------
    ruta : str o Path
        Archivo .xlsx de la planilla.
    canal : 'ambos' | 'canal_verde' | 'stock_verde'
        Sub-canal a incluir. Ver docs/02-spec-del-modelo.md.
    hoja : str
        Nombre de la hoja dentro del archivo.
    """
    # dtype=str obliga a leer TODO como texto. Sin eso, pandas adivina el
    # tipo de cada columna y con el formato argentino adivina mal: una
    # columna con '1.234,00' y '999,00' mezcladas termina medio numérica
    # y medio texto. Mejor leer todo como texto y convertir nosotros,
    # con reglas que podemos leer y testear.
    df = pd.read_excel(ruta, sheet_name=hoja, dtype=str)

    verificar_columnas(df)
    df = convertir_numeros(df)
    df = descartar_filas_vacias(df)
    df = normalizar_texto(df)
    df = filtrar_canal(df, canal)

    return df.reset_index(drop=True)