"""
publico.py — Modo de publicación público (spec §3, política en docs/04).

Convierte un informe interno en uno que se puede mostrar en el repo o en una
entrevista sin exponer a la empresa:

    Montos en pesos   → unidades base (1 u. = 1% de la facturación del mes base)
    Proveedores       → "Proveedor A (rubro)", estable entre informes
    Márgenes, %, pp   → reales: son el análisis, y solos no revelan tamaño

Y lo verifica DESPUÉS de escribir el .docx: si queda un solo monto o un solo
nombre real de proveedor, el archivo se borra y la generación falla. Es el
invariante I1 aplicado al producto final, no a la intención.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from docx import Document

from . import anonymize as an
from . import config as cfg
from . import metrics as m
from .sections import Seccion, filtrar_periodo


def rubros_por_proveedor(df: pd.DataFrame) -> dict[str, str]:
    """Rubro = la categoría que más factura cada proveedor.

    El pseudónimo conserva el rubro porque es lo que le da sentido a la
    comparación: "Proveedor A (tecnología)" dice algo; "Proveedor A", no.
    """
    d = m.calcular(df)
    t = d.groupby([cfg.PROVEEDOR, cfg.CATEGORIA])[m.C_BASE].sum().reset_index()
    t = t.sort_values(m.C_BASE, ascending=False).drop_duplicates(cfg.PROVEEDOR)
    return {str(p): str(c).lower() for p, c in zip(t[cfg.PROVEEDOR], t[cfg.CATEGORIA])}


def preparar(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Reemplaza los proveedores por su pseudónimo. Devuelve la tabla nueva
    y el mapa real → pseudónimo (que se usa después para verificar)."""
    mapa = an.asignar_pseudonimos(df[cfg.PROVEEDOR].dropna().unique(),
                                  rubros_por_proveedor(df), ruta=an.RUTA_PSEUDONIMOS)
    d = df.copy()
    d[cfg.PROVEEDOR] = an.pseudonimizar(d[cfg.PROVEEDOR], mapa)
    # Solo los nombres reales que aparecen en ESTA planilla.
    presentes = {str(p) for p in df[cfg.PROVEEDOR].dropna().unique()}
    return d, {k: v for k, v in mapa.items() if k in presentes}


def facturacion_base(df: pd.DataFrame) -> float:
    """Facturación del mes base: la vara contra la que se miden los montos."""
    base = filtrar_periodo(df, cfg.MES_BASE_INDICE)
    if base.empty:
        raise ValueError(f"Modo público: no hay ventas del mes base "
                         f"({cfg.MES_BASE_INDICE}) para construir las unidades.")
    return float(m.resumen(base)["facturacion"])


# ──────────────────────────────────────────────────────────────────────
# Reemplazo de nombres en textos que no salen de la planilla
# ──────────────────────────────────────────────────────────────────────

def _patron(mapa: dict[str, str]) -> re.Pattern | None:
    """Una sola expresión con todos los nombres, del más largo al más corto
    (así "Zero Pinturería" se reemplaza entero antes que "Zero")."""
    # Un nombre real que coincide con algún pseudónimo (pasa con los datos
    # sintéticos, que ya vienen con nombres tipo "Proveedor B") no se busca:
    # reemplazarlo rompería los pseudónimos que ya están en el texto.
    seudonimos = set(mapa.values())
    nombres = sorted((n for n in mapa if n not in seudonimos), key=len, reverse=True)
    if not nombres:
        return None
    # (?<!\w) y (?!\w): "que no haya una letra pegada antes ni después".
    # Así "Zero" no se reemplaza adentro de "Zeroland".
    return re.compile("|".join(rf"(?<!\w){re.escape(n)}(?!\w)" for n in nombres),
                      re.IGNORECASE)


def limpiar(texto: str, mapa: dict[str, str]) -> str:
    """Reemplaza nombres reales por pseudónimos en un texto libre
    (tus recomendaciones, por ejemplo, que escribís con nombres reales)."""
    patron = _patron(mapa)
    if patron is None:
        return texto
    minusculas = {k.lower(): v for k, v in mapa.items()}   # para ignorar mayúsculas
    return patron.sub(lambda x: minusculas[x.group(0).lower()], texto)


def limpiar_secciones(secciones: list[Seccion], mapa: dict[str, str]) -> None:
    """Aplica limpiar() a frases, alertas y celdas de tablas, en el lugar."""
    for s in secciones:
        s.frases = [limpiar(f, mapa) for f in s.frases]
        s.alertas = [limpiar(a, mapa) for a in s.alertas]
        for clave, tabla in s.tablas.items():
            s.tablas[clave] = tabla.map(
                lambda x: limpiar(x, mapa) if isinstance(x, str) else x)


# ──────────────────────────────────────────────────────────────────────
# Verificación del archivo final
# ──────────────────────────────────────────────────────────────────────

def texto_docx(ruta: Path) -> str:
    doc = Document(str(ruta))
    partes = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        partes += [c.text for fila in t.rows for c in fila.cells]
    return "\n".join(partes)


def verificar_docx(ruta: Path, mapa: dict[str, str]) -> None:
    """Falla si el .docx tiene un monto en pesos o un nombre real.

    Si falla, BORRA el archivo: un documento que no pasó la verificación no
    tiene que quedar dando vueltas en output/ con apariencia de publicable.
    """
    texto = texto_docx(ruta)
    problemas = []
    montos = an.buscar_montos(texto)
    if montos:
        problemas.append(f"montos en pesos: {', '.join(montos[:5])}")
    patron = _patron(mapa)
    if patron is not None:
        nombres = sorted({x.group(0) for x in patron.finditer(texto)})
        if nombres:
            problemas.append(f"nombres reales de proveedores: {', '.join(nombres)}")
    if problemas:
        ruta.unlink()
        raise ValueError(f"{ruta.name} no es publicable y se borró:\n  - "
                         + "\n  - ".join(problemas))


def limpiar_qa(resumen, mapa: dict[str, str]) -> None:
    """Lo mismo para el A2: prioridades y preguntas pueden traer nombres
    reales desde tu archivo de recomendaciones."""
    resumen.publico = True
    resumen.prioridades = [limpiar(t, mapa) for t in resumen.prioridades]
    resumen.funciono = [limpiar(t, mapa) for t in resumen.funciono]
    resumen.corregir = [limpiar(t, mapa) for t in resumen.corregir]
    for p in resumen.preguntas:
        p.pregunta, p.respuesta = limpiar(p.pregunta, mapa), limpiar(p.respuesta, mapa)