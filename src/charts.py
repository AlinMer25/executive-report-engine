"""
charts.py — Gráficos del informe.

Cada función recibe datos ya calculados y devuelve la imagen como bytes PNG.
No escribe archivos: report.py mete los bytes directo en el .docx. Así no
quedan imágenes sueltas en disco (que tendrían datos reales).

Regla del proyecto: el gráfico no calcula. Si un número está mal, el error
está en metrics.py o sections.py, igual que con las tablas.
"""

from __future__ import annotations

from io import BytesIO

import matplotlib

matplotlib.use("Agg")           # dibuja en memoria, sin abrir ventanas
import matplotlib.pyplot as plt  # noqa: E402  (tiene que ir después de use)
import pandas as pd  # noqa: E402

from . import config as cfg  # noqa: E402

# Paleta del informe: el verde del encabezado de tablas + neutros.
VERDE = "#1B5E3F"
VERDE_CLARO = "#8DB8A0"
GRIS = "#4A4A4A"
AMARILLO = "#D9A21B"
ROJO = "#B3402F"


def _estilo(ax) -> None:
    """Saca el 'ruido' de matplotlib: bordes de arriba y derecha, grilla fuerte."""
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(colors=GRIS, labelsize=8)
    ax.grid(axis="x", color="#E5E5E5", linewidth=0.6)
    ax.set_axisbelow(True)


def _a_png(fig) -> bytes:
    """Convierte la figura en bytes PNG y la cierra (si no, se acumulan en memoria)."""
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def _millones(x: float, _pos=None) -> str:
    """Etiqueta de eje: $300 M, o unidades base en modo público."""
    from . import sections as sc            # lee el modo vigente
    if sc._UNIDAD is not None:
        return f"{x / sc._UNIDAD:,.0f} u.".replace(",", ".")
    return f"${x / 1e6:,.0f} M".replace(",", ".")


# ──────────────────────────────────────────────────────────────────────
# 1. Evolución mensual: facturación (barras) + margen neto (línea)
# ──────────────────────────────────────────────────────────────────────

def evolucion(serie: pd.DataFrame) -> bytes:
    """serie: índice = 'AAAA-MM', columnas 'facturacion' y 'margen_neto'.

    Dos ejes porque son dos unidades distintas (pesos y %). Los pisos de
    margen se dibujan como líneas punteadas: el lector ve de un vistazo
    si algún mes los perforó.
    """
    fig, ax = plt.subplots(figsize=(7, 3.2))
    x = range(len(serie))
    ax.bar(x, serie["facturacion"], color=VERDE_CLARO, width=0.6)
    ax.yaxis.set_major_formatter(_millones)
    ax.set_xticks(list(x), list(serie.index))
    _estilo(ax)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color="#E5E5E5", linewidth=0.6)

    ax2 = ax.twinx()                       # segundo eje, a la derecha
    ax2.plot(x, serie["margen_neto"], color=VERDE, marker="o", linewidth=2)
    for i, v in enumerate(serie["margen_neto"]):
        ax2.annotate(f"{v:.1f}%".replace(".", ","), (i, v),
                     textcoords="offset points", xytext=(0, 7),
                     ha="center", fontsize=7, color=VERDE)
    ax2.axhline(cfg.PISO_MARGEN_ALARMA_1, color=AMARILLO, linestyle="--", linewidth=1)
    ax2.axhline(cfg.PISO_MARGEN_ALARMA_2, color=ROJO, linestyle="--", linewidth=1)
    ax2.set_ylim(min(15, serie["margen_neto"].min() - 2),
                 max(32, serie["margen_neto"].max() + 3))
    ax2.tick_params(colors=GRIS, labelsize=8)
    ax2.spines["top"].set_visible(False)

    ax.set_title("Facturación y margen neto por mes", fontsize=10,
                 color=GRIS, loc="left")
    return _a_png(fig)


# ──────────────────────────────────────────────────────────────────────
# 2. Margen neto por dimensión, con línea del promedio ponderado
# ──────────────────────────────────────────────────────────────────────

def margen_por_dimension(tabla: pd.DataFrame, margen_total: float,
                         titulo: str, maximo: int = 12) -> bytes:
    """tabla: salida de metrics.por_dimension (índice = nombre).

    Barras horizontales porque los nombres de plataforma son largos.
    El color avisa contra los pisos; la línea punteada es el margen
    ponderado del período, que es contra lo que hay que leer cada barra.
    """
    t = tabla.head(maximo).sort_values("margen_neto")
    colores = [ROJO if m < cfg.PISO_MARGEN_ALARMA_2
               else AMARILLO if m < cfg.PISO_MARGEN_ALARMA_1
               else VERDE for m in t["margen_neto"]]

    fig, ax = plt.subplots(figsize=(7, 0.32 * len(t) + 1))
    ax.barh([str(i) for i in t.index], t["margen_neto"], color=colores, height=0.6)
    ax.axvline(margen_total, color=GRIS, linestyle=":", linewidth=1.2)
    ax.text(margen_total, len(t) - 0.4,
            f" promedio {margen_total:.1f}%".replace(".", ","),
            fontsize=7, color=GRIS, va="bottom")
    for i, m in enumerate(t["margen_neto"]):
        ax.text(m + 0.3, i, f"{m:.1f}%".replace(".", ","),
                va="center", fontsize=7, color=GRIS)
    _estilo(ax)
    ax.set_title(titulo, fontsize=10, color=GRIS, loc="left")
    return _a_png(fig)


# ──────────────────────────────────────────────────────────────────────
# 3. Facturación vs ganancia neta, barras acostadas
# ──────────────────────────────────────────────────────────────────────

def facturacion_y_ganancia(tabla: pd.DataFrame, titulo: str,
                           maximo: int = 8) -> bytes:
    """Muestra lo que el proyecto vino a medir: facturar más no es ganar más."""
    t = tabla.head(maximo).iloc[::-1]       # el más grande arriba
    y = range(len(t))
    alto = 0.38

    fig, ax = plt.subplots(figsize=(7, 0.45 * len(t) + 1))
    ax.barh([i + alto / 2 for i in y], t["facturacion"], height=alto,
            color=VERDE_CLARO, label="Facturación")
    ax.barh([i - alto / 2 for i in y], t["ganancia_neta"], height=alto,
            color=VERDE, label="Ganancia neta")
    ax.set_yticks(list(y), [str(i) for i in t.index])
    ax.xaxis.set_major_formatter(_millones)
    _estilo(ax)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.set_title(titulo, fontsize=10, color=GRIS, loc="left")
    return _a_png(fig)