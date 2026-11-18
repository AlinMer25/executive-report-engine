"""
ingest.py — Carga la planilla de ventas y la deja lista para calcular.

Responsabilidad única: leer el archivo, verificar que tenga lo necesario,
convertir los textos a números y descartar lo que no es una venta.
No calcula ninguna métrica: de eso se ocupa metrics.py.

La frontera importa. Si la carga también calculara, un error de lectura y un
error de fórmula se confundirían, y el descuadre sería imposible de ubicar.
"""

import openpyxl
import pandas as pd

from . import config as cfg


# ──────────────────────────────────────────────────────────────────────
# Conversión de números
# ──────────────────────────────────────────────────────────────────────

def a_numero(serie: pd.Series) -> pd.Series:
    """Convierte texto a número decidiendo el formato por columna.

    La planilla exporta en formato argentino —' $399.999,00', punto para
    miles y coma para decimales— pero un archivo generado por otro programa
    escribe '399999.0', con el punto como decimal. Las dos formas tienen que
    dar el mismo número.

    **La decisión se toma una vez por columna, no valor por valor**, y ese
    detalle es el que hace que funcione. Decidir por valor parece más fino y
    es peor: el factor de IVA '1.105' se lee como mil ciento cinco en formato
    argentino y como uno coma ciento cinco en el estándar, y las dos lecturas
    son defendibles mirando ese valor solo. Mirando la columna entera no hay
    ambigüedad, porque una columna viene de una sola fuente con un solo
    formato.

    El criterio: si **algún** valor de la columna tiene coma decimal, o
    alguno tiene dos o más grupos de miles ('1.234.567'), la columna está en
    formato argentino. Si no, el punto es decimal.

    Lo que no se puede convertir queda nulo (NA), nunca cero: un cero se
    sumaría; un nulo es la ausencia de dato y se puede contar aparte.
    """
    s = serie.astype("string")
    s = s.str.replace(r"[^\d,.\-()]", "", regex=True)      # quita $, espacios, %
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)   # (1.234) → -1.234

    hay_coma = bool(s.str.contains(",", na=False).any())
    hay_miles = bool(s.str.fullmatch(r"-?\d{1,3}(?:\.\d{3}){2,}", na=False).any())

    if hay_coma or hay_miles:
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)

    # Se fuerza a decimal aunque todos los valores sean enteros. Si no,
    # pandas elige tipo entero y después falla al guardar un decimal ahí:
    # dividir el envío por 1,21 sobre una columna entera levanta un error.
    # Que el tipo dependa de los datos que tocó cargar hace que el motor
    # ande con un dataset y no con otro, que es la peor clase de defecto.
    return pd.to_numeric(s, errors="coerce").astype("Float64")


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

def detectar_errores_formula(ruta, hoja: str) -> list[str]:
    """Lista, fila por fila, los errores de fórmula de la planilla.

    Tiene que correr ANTES de que pandas lea el archivo. pandas convierte
    #¡REF!, #¡VALOR!, #¡DIV/0! y el resto en celdas vacías sin avisar: el
    error se pierde y el total baja en silencio. openpyxl, en cambio, los
    conserva y los marca con el tipo 'e' (error).

    Devuelve una lista con un texto por fila de datos, en el mismo orden que
    las filas del DataFrame: vacío si la fila está sana, o algo como
    "Monto por Venta: #REF!; IIBB: #DIV/0!" si no.
    """
    # read_only=True: lee sin cargar todo el libro en memoria a la vez.
    # data_only=True: trae el resultado de cada fórmula, no la fórmula.
    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    filas = libro[hoja].iter_rows(values_only=False)
    encabezados = [c.value for c in next(filas)]

    resultado = []
    for fila in filas:
        errores = [f"{encabezados[i]}: {celda.value}"
                   for i, celda in enumerate(fila)
                   if celda.data_type == "e" and i < len(encabezados)]
        resultado.append("; ".join(errores))
    libro.close()
    return resultado


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

    # Una fila con error de fórmula NO es una fila vacía, aunque su monto
    # haya llegado vacío. Si se descartara, la venta desaparecería sin
    # rastro. Se conserva para que la validación (R16) la señale.
    tiene_error = pd.Series(False, index=df.index)
    if cfg.ERRORES_FORMULA in df.columns:
        tiene_error = df[cfg.ERRORES_FORMULA].astype("string").str.len().fillna(0) > 0

    return df[tiene_mes & (tiene_monto | tiene_error)].copy()


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
    # Encabezados sin espacios sobrantes: "Pago x Envio " y "Pago x Envio"
    # pasan a ser la misma columna. Un espacio invisible no rompe el motor.
    df.columns = [str(c).strip() for c in df.columns]

    # Los errores se buscan antes de convertir, porque la conversión los
    # borra. Se guardan en una columna propia que viaja con cada fila.
    errores = detectar_errores_formula(ruta, hoja)
    df[cfg.ERRORES_FORMULA] = (errores + [""] * len(df))[:len(df)]

    verificar_columnas(df)
    df = convertir_numeros(df)
    df = descartar_filas_vacias(df)
    df = normalizar_texto(df)
    df = filtrar_canal(df, canal)

    return df.reset_index(drop=True)