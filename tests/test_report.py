"""Tests de report.py: que el .docx exista, tenga la estructura esperada
y que el modo estricto frene cuando corresponde."""

import pandas as pd
import pytest
from docx import Document

from src import report
from src import sample_data


def _titulos(doc):
    """Textos de los títulos de sección numerados (estilo Heading 1).
    El anexo para el analista no lleva número: no es parte del informe."""
    return [p.text for p in doc.paragraphs
            if p.style is not None and p.style.name == "Heading 1"
            and not p.text.startswith("Anexo")]


@pytest.fixture(scope="module")
def planilla(tmp_path_factory):
    """Planilla sintética escrita a disco una sola vez para todo el archivo."""
    ruta = tmp_path_factory.mktemp("datos") / "ventas.xlsx"
    sample_data.escribir(ruta)
    return ruta


def test_genera_el_docx(planilla, tmp_path):
    salida = report.generar(planilla, "2026-09", salida=tmp_path / "i.docx")
    assert salida.exists()


def test_estructura(planilla, tmp_path):
    salida = report.generar(planilla, "2026-09", salida=tmp_path / "i.docx")
    doc = Document(str(salida))
    titulos = _titulos(doc)
    assert titulos[0] == "1. Resumen ejecutivo"
    assert titulos[-1].endswith("Nota metodológica")
    assert len(doc.tables) >= 4


def test_numeracion_correlativa(planilla, tmp_path):
    salida = report.generar(planilla, "2026-09", salida=tmp_path / "i.docx")
    doc = Document(str(salida))
    numeros = [int(t.split(".")[0]) for t in _titulos(doc)]
    assert numeros == list(range(1, len(numeros) + 1))


def test_estricto_frena_con_hallazgos_altos(planilla, tmp_path, monkeypatch):
    falso = report.val.Hallazgo("R99", "Prueba", report.val.ALTA, "Revisar",
                                 pd.DataFrame({"x": [1]}))
    monkeypatch.setattr(report.val, "validar", lambda df: [falso])
    with pytest.raises(SystemExit):
        report.generar(planilla, "2026-09", salida=tmp_path / "i.docx",
                       estricto=True)


def test_publicar_congela_el_mes(planilla, tmp_path):
    from src import snapshot as snap
    report.generar(planilla, "2026-09", salida=tmp_path / "i.docx", publicar=True)
    versiones = snap.listar("2026-09")
    assert len(versiones) == 1
    assert versiones.iloc[0]["etiqueta"] == "informe publicado"


def test_leer_parametros_de_la_terminal():
    assert report.leer_dotacion("2026-08=2, 2026-09=3") == {"2026-08": 2.0, "2026-09": 3.0}
    assert report.leer_dotacion(None) == {}
    assert report.leer_ventana("2026-07,2026-09") == ("2026-07", "2026-09")


# ── Anexo para el analista ──────────────────────────────────────────────

def _todo(doc):
    return "\n".join([p.text for p in doc.paragraphs] +
                     [c.text for t in doc.tables for f in t.rows for c in f.cells])


def test_anexo_lista_filas_buscables_con_su_problema(tmp_path):
    """Una fila sin categoría y otra con #REF! tienen que aparecer con su
    número de fila, su cliente y qué revisar."""
    from openpyxl import load_workbook
    from openpyxl.cell.cell import Cell
    from src import config as cfg
    df = sample_data.generar()
    sept = df.index[df[cfg.FECHA].astype(str).str.endswith("/09/2026")]
    df.loc[sept[0], cfg.CATEGORIA] = None
    df[cfg.CLIENTE_NOMBRE] = "Cliente de prueba"
    ruta = tmp_path / "ventas.xlsx"
    df.to_excel(ruta, sheet_name=cfg.HOJA_VENTAS, index=False)

    # Un #REF! de verdad en la celda del costo de otra venta de septiembre.
    libro = load_workbook(ruta)
    hoja = libro[cfg.HOJA_VENTAS]
    col = [c.value for c in hoja[1]].index(cfg.COSTO_TOTAL) + 1
    celda = hoja.cell(row=int(sept[1]) + 2, column=col)
    assert isinstance(celda, Cell)                 # no es una celda combinada
    celda.value, celda.data_type = "#REF!", "e"
    libro.save(ruta)

    salida = report.generar(ruta, "2026-09", salida=tmp_path / "i.docx")
    texto = _todo(Document(str(salida)))
    assert "Anexo para el analista" in texto
    assert "R09 producto sin categoría" in texto
    assert f"{cfg.COSTO_TOTAL}: #REF!" in texto
    assert str(int(sept[0]) + 2) in texto          # la fila, como en la planilla
    assert "Cliente de prueba" in texto


def test_el_anexo_nunca_va_al_modo_publico(planilla, tmp_path):
    salida = report.generar(planilla, "2026-09", modo="publico",
                            salida=tmp_path / "p.docx")
    assert "Anexo para el analista" not in _todo(Document(str(salida)))