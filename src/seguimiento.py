"""
seguimiento.py — Recomendaciones con ID y su seguimiento con dato.

Cada mes escribís tus recomendaciones en un archivo JSON:

    data/recomendaciones/2026-09.json

El informe de ese mes las publica (core.recomendaciones) y el informe del mes
siguiente las retoma una por una (core.seguimiento). Si la recomendación
declara qué medir, el motor busca el dato y propone el estado solo.

La carpeta está en .gitignore: las recomendaciones nombran plataformas y
proveedores reales.

Formato de cada recomendación (solo "id" y "texto" son obligatorios):

    {
      "id": "2026-09-01",
      "texto": "Revisar el precio de Bigote para que cubra el envío",
      "medir": {
        "dimension": "Plataforma",          # columna de la planilla, o null = total
        "valor": "Bigote",                  # uno o una lista: ["Zero", "Visuar"]
        "metrica": "margen_neto",           # margen_neto, facturacion, ganancia_neta u operaciones
        "objetivo": 23.0                    # opcional
      },
      "estado": "superada por los hechos",  # opcional: pisa el estado automático
      "nota": "Se dio de baja la cuenta"    # opcional
    }
"""

from __future__ import annotations

import json

import pandas as pd

from . import config as cfg
from . import metrics as m
from .sections import (Seccion, filtrar_periodo, nombre_periodo, periodo_anterior,
                       pesos, porcentaje, pp)

ESTADOS = ("cumplida", "en curso", "no abordada", "superada por los hechos")
METRICAS = ("margen_neto", "facturacion", "ganancia_neta", "operaciones")


# ──────────────────────────────────────────────────────────────────────
# Leer y validar el archivo
# ──────────────────────────────────────────────────────────────────────

def cargar(periodo: str) -> list[dict] | None:
    """Recomendaciones de un período, o None si no hay archivo."""
    ruta = cfg.DIR_RECOMENDACIONES / f"{periodo}.json"
    if not ruta.exists():
        return None
    recos = json.loads(ruta.read_text(encoding="utf-8"))
    validar(recos, ruta.name)
    return recos


def validar(recos: list[dict], origen: str) -> None:
    """Un error de tipeo en el JSON tiene que frenar acá, con un mensaje claro,
    y no aparecer como un número raro en el informe."""
    ids = set()
    for r in recos:
        if "id" not in r or "texto" not in r:
            raise ValueError(f"{origen}: cada recomendación necesita 'id' y 'texto'.")
        if r["id"] in ids:
            raise ValueError(f"{origen}: el ID '{r['id']}' está repetido.")
        ids.add(r["id"])
        if r.get("estado") and r["estado"] not in ESTADOS:
            raise ValueError(f"{origen} [{r['id']}]: estado '{r['estado']}' inválido. "
                             f"Opciones: {', '.join(ESTADOS)}")
        medir = r.get("medir")
        if medir and medir.get("metrica") not in METRICAS:
            raise ValueError(f"{origen} [{r['id']}]: métrica inválida. "
                             f"Opciones: {', '.join(METRICAS)}")


# ──────────────────────────────────────────────────────────────────────
# Medir
# ──────────────────────────────────────────────────────────────────────

def _valor(df: pd.DataFrame, medir: dict) -> float | None:
    """El valor de la métrica sobre las filas que pide la recomendación."""
    dimension, valor = medir.get("dimension"), medir.get("valor")
    if dimension:
        valores = valor if isinstance(valor, list) else [valor]
        df = df[df[dimension].isin(valores)]
    if df.empty:
        return None
    return float(m.resumen(df)[medir["metrica"]])


def _formato(metrica: str, x: float) -> str:
    if metrica == "margen_neto":
        return porcentaje(x)
    if metrica == "operaciones":
        return f"{x:,.0f}".replace(",", ".")
    return pesos(x)


def _diferencia(metrica: str, antes: float, ahora: float) -> str:
    if metrica == "margen_neto":
        return pp(ahora - antes)
    var = (ahora / antes - 1) * 100 if antes else 0.0
    return f"{var:+.1f}%".replace(".", ",")


def estado_automatico(antes: float | None, ahora: float | None,
                      objetivo: float | None) -> str | None:
    """Propone un estado. Supone que más es mejor (margen, facturación, ganancia).

    cumplida   : llegó al objetivo
    en curso   : mejoró pero no llegó (o mejoró y no había objetivo)
    no abordada: no mejoró
    """
    if ahora is None:
        return None
    if objetivo is not None and ahora >= objetivo:
        return "cumplida"
    if antes is None:                  # no existía y ahora sí: arrancó (ej. Midea)
        return "en curso"
    if antes is not None and ahora > antes:
        return "en curso"
    return "no abordada"


def contraejemplos(df_antes: pd.DataFrame, df_ahora: pd.DataFrame,
                   medir: dict) -> list[str]:
    """Matiz obligatorio del spec: si la recomendación es sobre un grupo,
    ¿algún miembro va en contra del agregado? (el caso Mosconi)."""
    valor = medir.get("valor")
    if not isinstance(valor, list) or len(valor) < 2:
        return []
    metrica = medir["metrica"]
    total_antes = _valor(df_antes, medir)
    total_ahora = _valor(df_ahora, medir)
    if total_antes is None or total_ahora is None:
        return []
    mejora_grupo = total_ahora > total_antes

    contra = []
    for v in valor:
        uno = {**medir, "valor": v}          # copia del dict con un solo valor
        a, b = _valor(df_antes, uno), _valor(df_ahora, uno)
        if a is None or b is None:
            continue
        if (b > a) != mejora_grupo:           # va en la dirección opuesta
            contra.append(f"{v} ({_diferencia(metrica, a, b)})")
    return contra


# ──────────────────────────────────────────────────────────────────────
# Secciones
# ──────────────────────────────────────────────────────────────────────

def seccion_seguimiento(df: pd.DataFrame, periodo: str) -> Seccion:
    """core.seguimiento: TODAS las recomendaciones del período anterior,
    incluidas las no abordadas. Omitir una es abandonarla en silencio."""
    previo = periodo_anterior(periodo)
    recos = cargar(previo)
    titulo = "Seguimiento de recomendaciones"
    if recos is None:
        return Seccion("core.seguimiento", titulo, frases=[
            f"[Completar: no hay recomendaciones registradas para "
            f"{nombre_periodo(previo)}. Crear data/recomendaciones/{previo}.json.]"])

    df_antes, df_ahora = filtrar_periodo(df, previo), filtrar_periodo(df, periodo)
    filas, frases = [], []
    for r in recos:
        medir = r.get("medir")
        antes = ahora = None
        dato = "[Completar]"
        if medir:
            antes, ahora = _valor(df_antes, medir), _valor(df_ahora, medir)
            mt = medir["metrica"]
            if antes is not None and ahora is not None:
                dato = (f"{_formato(mt, antes)} → {_formato(mt, ahora)} "
                        f"({_diferencia(mt, antes, ahora)})")
            elif ahora is not None:
                dato = f"sin ventas → {_formato(mt, ahora)}"
            contra = contraejemplos(df_antes, df_ahora, medir)
            if contra:
                frases.append(f"Atención [{r['id']}]: el agregado esconde "
                              f"miembros que van en contra: {', '.join(contra)}.")

        estado = (r.get("estado")
                  or estado_automatico(antes, ahora, (medir or {}).get("objetivo"))
                  or "[Completar]")
        filas.append({"ID": r["id"], "Recomendación": r["texto"],
                      "Dato": dato, "Estado": estado})

    tabla = pd.DataFrame(filas)
    conteo = tabla["Estado"].value_counts()
    resumen = ", ".join(f"{n} {e}" for e, n in conteo.items())
    frases.insert(0, f"De las {len(recos)} recomendaciones de "
                     f"{nombre_periodo(previo)}: {resumen}.")
    return Seccion("core.seguimiento", titulo, frases=frases,
                   tablas={"seguimiento": tabla})


def seccion_recomendaciones(periodo: str) -> Seccion:
    """core.recomendaciones: las de este período, con su ID."""
    recos = cargar(periodo)
    titulo = "Recomendaciones"
    if recos is None:
        return Seccion("core.recomendaciones", titulo, frases=[
            f"[Completar: 5 a 8 recomendaciones en imperativo, con justificación "
            f"numérica. Registrarlas en data/recomendaciones/{periodo}.json para "
            f"que el informe siguiente las retome.]"])
    return Seccion("core.recomendaciones", titulo,
                   frases=[f"[{r['id']}] {r['texto']}" for r in recos])