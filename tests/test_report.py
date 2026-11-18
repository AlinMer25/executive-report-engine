"""Tests de report.py: que el .docx exista, tenga la estructura esperada
y que el modo estricto frene cuando corresponde."""

import pandas as pd
import pytest
from docx import Document

from src import report
from src import sample_data


def _titulos(doc):
    """Textos de los títulos de sección (estilo Heading 1)."""
    return [p.text for p in doc.paragraphs
            if p.style is not None and p.style.name == "Heading 1"]


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