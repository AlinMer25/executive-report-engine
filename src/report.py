"""
report.py — Escribe el informe ejecutivo en .docx.

Recibe las secciones ya armadas por sections.py y las vuelca a un documento
de Word. No calcula nada: si un número está mal, el error está en otro lado.

Uso desde la terminal:

    python -m src.report --archivo data/raw/ventas.xlsx --mes 2026-10

El informe queda en output/, que está en .gitignore porque tiene datos reales.
"""

from __future__ import annotations

import argparse
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import cast

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.styles.style import ParagraphStyle

from . import config as cfg
from . import modules as md
from . import sections as sc
from . import snapshot as snap
from . import validate as val
from .ingest import cargar_ventas

VERDE = RGBColor(0x1B, 0x5E, 0x3F)
GRIS = RGBColor(0x4A, 0x4A, 0x4A)


# ──────────────────────────────────────────────────────────────────────
# Piezas de formato
# ──────────────────────────────────────────────────────────────────────

def _sombrear(celda, color_hex: str) -> None:
    """Pinta el fondo de una celda.

    python-docx no tiene una función directa para esto, así que se escribe
    el XML de Word a mano: un elemento <w:shd> con el color de relleno.
    Es el tipo de cosa que se busca una vez, se encapsula en una función
    y no se vuelve a pensar.
    """
    sombra = OxmlElement("w:shd")
    sombra.set(qn("w:val"), "clear")
    sombra.set(qn("w:fill"), color_hex)
    celda._tc.get_or_add_tcPr().append(sombra)


def _tabla(doc, df: pd.DataFrame) -> None:
    """Escribe un DataFrame como tabla de Word, con encabezado verde."""
    t = doc.add_table(rows=1, cols=len(df.columns))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, nombre in enumerate(df.columns):
        celda = t.rows[0].cells[i]
        celda.text = str(nombre)
        _sombrear(celda, "1B5E3F")
        run = celda.paragraphs[0].runs[0]
        run.font.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for n, fila in enumerate(df.itertuples(index=False)):
        celdas = t.add_row().cells
        for i, valor in enumerate(fila):
            celdas[i].text = str(valor)
            celdas[i].paragraphs[0].runs[0].font.size = Pt(9)
            if n % 2:                       # filas alternadas, para leer mejor
                _sombrear(celdas[i], "F2F5F3")
    doc.add_paragraph()


def _alerta(doc, texto: str) -> None:
    """Un callout: tabla de una sola celda, con fondo y texto en negrita."""
    t = doc.add_table(rows=1, cols=1)
    celda = t.rows[0].cells[0]
    severa = texto.startswith("ALERTA SEVERA")
    _sombrear(celda, "F8E1DC" if severa else "FFF4D6")
    celda.text = texto
    run = celda.paragraphs[0].runs[0]
    run.font.size = Pt(9.5)
    run.font.bold = severa
    doc.add_paragraph()


# ──────────────────────────────────────────────────────────────────────
# El documento
# ──────────────────────────────────────────────────────────────────────

def escribir(secciones: list[sc.Seccion], periodo: str, ruta: Path,
             filas_analizadas: int, hallazgos: list,
             reexp: pd.DataFrame | None = None,
             corte: str = "trimestral") -> Path:
    """Arma el .docx a partir de las secciones."""
    doc = Document()
    estilo = cast(ParagraphStyle, doc.styles["Normal"])   # le aclara el tipo a Pylance
    estilo.font.name = "Calibri"
    estilo.font.size = Pt(10)

    # ── Encabezado
    titulo = doc.add_paragraph()
    r = titulo.add_run("INFORME EJECUTIVO DE VENTAS")
    r.font.size, r.font.bold, r.font.color.rgb = Pt(20), True, VERDE

    sub = doc.add_paragraph()
    r = sub.add_run(f"Canal Verde — {sc.nombre_periodo(periodo).capitalize()}")
    r.font.size, r.font.color.rgb = Pt(13), GRIS

    meta = doc.add_paragraph()
    r = meta.add_run(
        f"Período {periodo} · comparado contra {sc.periodo_anterior(periodo)} · "
        f"corte {corte} · "
        f"generado el {date.today():%d/%m/%Y}")
    r.font.size, r.font.italic = Pt(9), True

    # ── Secciones, numeradas en el momento de escribir
    # El número no viene de sections.py: depende de cuántas secciones
    # hayan entrado. Por eso el spec usa identificadores estables.
    for n, s in enumerate(secciones, start=1):
        doc.add_heading(f"{n}. {s.titulo}", level=1)
        for a in s.alertas:
            _alerta(doc, a)
        for f in s.frases:
            doc.add_paragraph(f)
        for df in s.tablas.values():
            _tabla(doc, df)
        for png in s.graficos.values():
            doc.add_picture(BytesIO(png), width=Cm(16))   # bytes → imagen, sin archivo

    # ── Nota metodológica (core.metodologia)
    doc.add_heading(f"{len(secciones) + 1}. Nota metodológica", level=1)
    nota = (f"Análisis sobre {filas_analizadas} operaciones del período. "
            "Márgenes netos calculados post-comisión, post-IIBB y post-envío, "
            "recalculados por el motor desde sus insumos. El margen del período "
            "es ponderado por facturación. Los márgenes varían en puntos "
            f"porcentuales (pp). Corte comparativo declarado: {corte}.")
    doc.add_paragraph(nota)

    # Spec §7, regla 2: toda reexpresión se declara, aunque sea chica.
    if reexp is not None and not reexp.empty:
        doc.add_paragraph(
            "Cifras de meses ya publicados que cambiaron:").runs[0].bold = True
        # to_dict("records"): una lista de diccionarios, uno por fila.
        for r in reexp.to_dict("records"):
            metrica = str(r["metrica"])
            antes = md.valor_cabecera(metrica, float(r["publicado"]))
            ahora = md.valor_cabecera(metrica, float(r["actual"]))
            var = f"{float(r['variacion_pct']):+.1f}%".replace(".", ",")
            doc.add_paragraph(f"{r['periodo']} · {metrica}: {antes} → {ahora} ({var})",
                              style="List Bullet")

    if hallazgos:
        doc.add_paragraph(
            "Calidad de datos al momento de generar el informe:").runs[0].bold = True
        for h in hallazgos:
            doc.add_paragraph(f"{h.id} · {h.nombre}: {h.cantidad} filas "
                              f"(severidad {h.severidad}).", style="List Bullet")

    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta))
    return ruta


def generar(archivo, periodo: str, canal: str = "ambos",
            salida: Path | None = None, estricto: bool = False,
            publicar: bool = False,
            params: md.Parametros | None = None) -> Path:
    """De la planilla al .docx, en un solo paso.

    publicar=True congela los datos del mes en un snapshot: esa foto pasa a
    ser "lo publicado" contra lo que mod.integridad compara en los meses
    siguientes. Se usa una sola vez, con la versión que se entrega.
    """
    df = cargar_ventas(archivo, canal=canal)
    del_periodo = sc.filtrar_periodo(df, periodo)

    hallazgos = val.validar(del_periodo)
    if estricto and any(h.severidad == val.ALTA for h in hallazgos):
        altas = ", ".join(h.id for h in hallazgos if h.severidad == val.ALTA)
        raise SystemExit(f"Modo estricto: hay hallazgos de severidad alta ({altas}). "
                         "Corregí la planilla o generá sin --estricto.")

    params = params or md.Parametros()
    corte = params.corte
    secciones = sc.construir(df, periodo, params=params)
    reexp = None
    if canal == "ambos":
        reexp = md.reexpresiones(df, periodo)
    else:
        # Los snapshots publicados son del total: comparar contra un solo
        # sub-canal daría diferencias falsas.
        secciones = [s for s in secciones if s.id != "mod.integridad"]

    salida = salida or cfg.DIR_SALIDA / f"Informe_Ventas_{periodo}_{corte}_{canal}.docx"
    ruta = escribir(secciones, periodo, salida, len(del_periodo), hallazgos, reexp,
                    corte)

    # A2: el Resumen y QA sale de las MISMAS secciones (invariante I2).
    from . import qa                        # import local: qa importa report
    resumen_qa = qa.construir(df, periodo, secciones, params)
    qa.escribir(resumen_qa, salida.parent / f"Resumen_QA_{periodo}_{corte}_{canal}.docx")

    if publicar:
        if canal != "ambos":
            raise SystemExit("--publicar solo vale para el total (--canal ambos).")
        snap.congelar(del_periodo, periodo, etiqueta="informe publicado")
    return ruta


# ──────────────────────────────────────────────────────────────────────
# Línea de comandos
# ──────────────────────────────────────────────────────────────────────

def leer_dotacion(texto: str | None) -> dict[str, float]:
    """'2026-08=2,2026-09=3' → {'2026-08': 2.0, '2026-09': 3.0}"""
    if not texto:
        return {}
    dotacion = {}
    for par in texto.split(","):
        mes, n = par.split("=")
        dotacion[mes.strip()] = float(n)
    return dotacion


def leer_ventana(texto: str | None) -> tuple[str, str] | None:
    """'2026-07,2026-09' → ('2026-07', '2026-09')"""
    if not texto:
        return None
    desde, hasta = (x.strip() for x in texto.split(","))
    return desde, hasta


def main() -> None:
    p = argparse.ArgumentParser(description="Genera el informe ejecutivo de ventas.")
    p.add_argument("--archivo", required=True, help="Planilla .xlsx de ventas")
    p.add_argument("--mes", required=True, help="Período a informar, AAAA-MM")
    p.add_argument("--canal", default="ambos",
                   choices=["ambos", "canal_verde", "stock_verde"])
    p.add_argument("--estricto", action="store_true",
                   help="No generar si hay hallazgos de severidad alta")
    p.add_argument("--corte", default="trimestral", choices=list(md.CORTES),
                   help="Corte comparativo de la analítica larga (spec §3)")
    p.add_argument("--autor", default="el analista",
                   help="Quién activa los módulos cualitativos")
    p.add_argument("--factor", help="Factor del mes (evento exógeno)")
    p.add_argument("--factor-justificacion")
    p.add_argument("--carga", help="Carga de trabajo prevista para el período siguiente")
    p.add_argument("--carga-justificacion")
    p.add_argument("--dotacion", help='Operadores por mes: "2026-08=2,2026-09=3"')
    p.add_argument("--ventana-capacidad", help='Par de meses: "2026-07,2026-09"')
    p.add_argument("--publicar", action="store_true",
                   help="Congelar los datos del mes como versión publicada")
    a = p.parse_args()

    params = md.Parametros(
        corte=a.corte, autor=a.autor,
        factor=a.factor, factor_justificacion=a.factor_justificacion,
        carga=a.carga, carga_justificacion=a.carga_justificacion,
        dotacion=leer_dotacion(a.dotacion),
        ventana_capacidad=leer_ventana(a.ventana_capacidad),
    )
    ruta = generar(a.archivo, a.mes, a.canal, estricto=a.estricto,
                   publicar=a.publicar, params=params)
    print(f"Informe generado: {ruta}")


if __name__ == "__main__":
    main()