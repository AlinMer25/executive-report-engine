"""
snapshot.py — Congela el dataset de un período y permite comparar versiones.

El problema que resuelve: la planilla es un documento vivo. Después de
cerrado un informe se siguen cargando costos, se completa el régimen fiscal,
llegan fletes y entran ventas rezagadas. Un mes recalculado dos semanas
después no da lo mismo, y sin registro esa diferencia aparece sola en una
reunión.

La solución no es impedir que el dato cambie —cambia por buenos motivos—
sino dejar constancia de contra qué datos se calculó cada informe.

Cada congelado produce dos archivos:

    data/snapshots/2026-09/20261005T093012.csv   los datos
    data/snapshots/2026-09/20261005T093012.json  la ficha de control

La ficha guarda fecha, huella digital, cantidad de filas y los totales del
período. Con eso, cualquier informe se puede regenerar idéntico dentro de un
año, y cualquier diferencia se puede explicar en vez de descubrir.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import config as cfg

DIR_SNAPSHOTS = cfg.RAIZ / "data" / "snapshots"


# ──────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────

def huella(ruta: Path) -> str:
    """Calcula la huella digital SHA-256 del archivo.

    Es un código de 64 caracteres derivado del contenido. Cambiar un solo
    dígito del archivo cambia la huella por completo. Sirve para responder
    '¿son los mismos datos?' sin tener que compararlos fila por fila.
    """
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        # Se lee de a bloques para no cargar el archivo entero en memoria.
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def base_imponible(df: pd.DataFrame) -> pd.Series:
    """Monto sobre el que se calcula el margen de cada venta.

    Depende del régimen: en Blanco se usa el monto sin IVA, en Negro el
    monto con IVA. No es una elección nuestra, es cómo está definido en el
    diccionario de métricas y cómo lo calcula la planilla.
    """
    return df[cfg.MONTO_SIN_IVA].where(df[cfg.REGIMEN] == cfg.REGIMEN_BLANCO,
                                       df[cfg.MONTO])


def totales(df: pd.DataFrame) -> dict:
    """Cifras de control del período. Es lo que se compara entre versiones."""
    base = base_imponible(df)
    ganancia = df[cfg.GANANCIA_NETA].sum()
    facturacion = base.sum()
    return {
        "operaciones": int(len(df)),
        "unidades": float(df[cfg.CANTIDAD].sum()),
        "facturacion": float(facturacion),
        "ganancia_neta": float(ganancia),
        "margen_neto": float(ganancia / facturacion * 100) if facturacion else 0.0,
        "balance_envios": float(df[cfg.DIFERENCIA_ENVIO].sum()),
    }


# ──────────────────────────────────────────────────────────────────────
# Congelar
# ──────────────────────────────────────────────────────────────────────

def congelar(df: pd.DataFrame, periodo: str, etiqueta: str = "") -> Path:
    """Guarda una copia inmutable del dataset de un período.

    Parámetros
    ----------
    df : DataFrame ya cargado con ingest.cargar_ventas()
    periodo : 'AAAA-MM', por ejemplo '2026-09'
    etiqueta : texto libre — 'cierre del informe', 'recálculo de noviembre'

    Devuelve la ruta del archivo de datos.
    """
    carpeta = DIR_SNAPSHOTS / periodo
    carpeta.mkdir(parents=True, exist_ok=True)

    # El nombre es la fecha y hora con segundos: ordena solo y es legible.
    # Si dos congelados caen en el mismo segundo, se agrega un sufijo: una
    # foto no puede pisar a otra en silencio, porque el objetivo mismo de
    # este módulo es que ninguna versión se pierda.
    sello = datetime.now().strftime("%Y%m%dT%H%M%S")
    # El sufijo es una letra, no un guion con número: así el orden
    # alfabético de los archivos sigue coincidiendo con el cronológico,
    # que es de lo que dependen 'primera' y 'ultima' al releer.
    if (carpeta / f"{sello}.csv").exists():
        from string import ascii_lowercase
        for letra in ascii_lowercase[1:]:
            if not (carpeta / f"{sello}{letra}.csv").exists():
                sello = f"{sello}{letra}"
                break
    ruta_datos = carpeta / f"{sello}.csv"
    ruta_ficha = carpeta / f"{sello}.json"

    # index=False: no guardamos el número de fila, que es un invento de
    # pandas y no un dato. Si se guardara, al releer aparecería como columna.
    df.to_csv(ruta_datos, index=False, encoding="utf-8")

    ficha = {
        "periodo": periodo,
        "etiqueta": etiqueta,
        "congelado": datetime.now().isoformat(timespec="seconds"),
        "filas": int(len(df)),
        "columnas": list(map(str, df.columns)),
        "huella_sha256": huella(ruta_datos),
        "totales": totales(df),
    }
    # ensure_ascii=False para que los acentos se guarden legibles.
    ruta_ficha.write_text(json.dumps(ficha, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    return ruta_datos


# ──────────────────────────────────────────────────────────────────────
# Consultar
# ──────────────────────────────────────────────────────────────────────

def listar(periodo: str | None = None) -> pd.DataFrame:
    """Devuelve las versiones congeladas, más recientes primero."""
    carpetas = [DIR_SNAPSHOTS / periodo] if periodo else sorted(
        p for p in DIR_SNAPSHOTS.glob("*") if p.is_dir()
    )
    filas = []
    for carpeta in carpetas:
        if not carpeta.exists():
            continue
        for ficha in sorted(carpeta.glob("*.json"), reverse=True):
            d = json.loads(ficha.read_text(encoding="utf-8"))
            filas.append({
                "periodo": d["periodo"],
                "version": ficha.stem,
                "congelado": d["congelado"],
                "etiqueta": d["etiqueta"],
                **d["totales"],
            })
    return pd.DataFrame(filas)


def cargar(periodo: str, version: str = "ultima") -> pd.DataFrame:
    """Relee un dataset congelado.

    version : 'ultima', 'primera', o el sello exacto ('20261005T093012').
    """
    carpeta = DIR_SNAPSHOTS / periodo
    disponibles = sorted(carpeta.glob("*.csv"))
    if not disponibles:
        raise FileNotFoundError(f"No hay snapshots para el período {periodo}")

    if version == "ultima":
        ruta = disponibles[-1]
    elif version == "primera":
        ruta = disponibles[0]
    else:
        ruta = carpeta / f"{version}.csv"
        if not ruta.exists():
            nombres = ", ".join(p.stem for p in disponibles)
            raise FileNotFoundError(
                f"No existe la versión '{version}' de {periodo}.\n"
                f"Disponibles: {nombres}"
            )
    return pd.read_csv(ruta, encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────
# Comparar
# ──────────────────────────────────────────────────────────────────────

def comparar(periodo: str, version_a: str = "primera",
             version_b: str = "ultima") -> pd.DataFrame:
    """Qué cambió entre dos fotos del mismo período.

    Es la función que convierte una sorpresa en una explicación: en vez de
    'los números no coinciden', produce 'la facturación subió 11,1M y el
    margen 1,43 pp entre el cierre y el recálculo'.
    """
    a, b = cargar(periodo, version_a), cargar(periodo, version_b)
    ta, tb = totales(a), totales(b)

    filas = []
    for clave in ta:
        va, vb = ta[clave], tb[clave]
        filas.append({
            "metrica": clave,
            version_a: va,
            version_b: vb,
            "diferencia": vb - va,
            "variacion_%": ((vb - va) / va * 100) if va else None,
        })
    return pd.DataFrame(filas)