"""Tests del Resumen y QA (A2)."""

import re

import pytest
from docx import Document

from src import modules as md
from src import qa
from src import report
from src import sample_data


@pytest.fixture(scope="module")
def planilla(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("datos") / "ventas.xlsx"
    sample_data.escribir(ruta)
    return ruta


@pytest.fixture
def a1_y_a2(planilla, tmp_path):
    """Genera A1 y A2 con capacidad activa (para tener todas las secciones)."""
    p = md.Parametros(dotacion={"2026-08": 2, "2026-09": 3})
    a1 = report.generar(planilla, "2026-09", salida=tmp_path / "A1.docx", params=p)
    a2 = tmp_path / "Resumen_QA_2026-09_trimestral_ambos.docx"
    return a1, a2


def texto(ruta):
    """Todo el texto de un .docx: párrafos y celdas de tablas."""
    doc = Document(str(ruta))
    partes = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        partes += [c.text for fila in t.rows for c in fila.cells]
    return "\n".join(partes)


# Cifras con unidad: $458,4 M · $584.650 · 23,34% · +50,8% · -0,99 pp
CIFRA = re.compile(r"[+-]?\$[\d.,]+(?: M)?|[+-]?\d+,\d+(?:%| pp)")


def test_se_genera_el_a2_junto_al_a1(a1_y_a2):
    a1, a2 = a1_y_a2
    assert a1.exists() and a2.exists()


def test_invariante_I2_todo_dato_del_a2_existe_en_el_a1(a1_y_a2):
    """El corazón del A2: no inventa números. Cada cifra con unidad que
    aparece en el resumen tiene que estar en el informe completo."""
    a1, a2 = a1_y_a2
    en_a1 = texto(a1)
    faltan = [c for c in CIFRA.findall(texto(a2)) if c not in en_a1]
    assert faltan == []


def test_exactamente_tres_prioridades(a1_y_a2):
    _, a2 = a1_y_a2
    doc = Document(str(a2))
    prioridades = next(t for t in doc.tables
                       if len(t.columns) == 2 and t.rows[0].cells[1].text == "Prioridad")
    assert len(prioridades.rows) == 1 + 3          # encabezado + 3


def test_capacidad_declara_primero_lo_no_atribuible(a1_y_a2):
    _, a2 = a1_y_a2
    t = texto(a2)
    assert "Primero lo que no es del equipo" in t
    assert t.index("Primero lo que no es del equipo") < t.index("Después lo que sí")


@pytest.mark.parametrize("respuesta, esperado", [
    ("Facturación $458,4 M", True),
    ("Tres frentes: [Completar]", False),
])
def test_tiene_cifra(respuesta, esperado):
    assert qa.tiene_cifra(respuesta) is esperado


def test_rellena_hasta_n():
    assert qa._completar(["a"], 3) == ["a", qa.COMPLETAR, qa.COMPLETAR]
    assert qa._completar(["a", "b", "c", "d"], 3) == ["a", "b", "c"]