"""Tests del modo público: unidades base, pseudónimos y verificación final."""

import pytest

from src import config as cfg
from src import publico as pub
from src import report
from src import sample_data as sd
from src import sections as sc

# Nombres "reales" de mentira, para comprobar que no se filtran.
REALES = ["Acme Hogar", "Globex", "Initech Tecno", "Umbrella", "Hooli",
          "Stark Electro", "Wayne Aire", "Wonka", "Cyberdyne", "Soylent"]


@pytest.fixture(scope="module")
def planilla_con_nombres(tmp_path_factory):
    """Sintéticos con nombres de proveedor que NO parecen pseudónimos."""
    df = sd.generar()
    originales = sorted(df[cfg.PROVEEDOR].dropna().unique())
    df[cfg.PROVEEDOR] = df[cfg.PROVEEDOR].map(dict(zip(originales, REALES)))
    ruta = tmp_path_factory.mktemp("datos") / "ventas.xlsx"
    df.to_excel(ruta, sheet_name=cfg.HOJA_VENTAS, index=False)
    return ruta


# ── Unidades base ───────────────────────────────────────────────────────

def test_unidades_conservan_la_proporcion():
    with sc.publicacion(200_000_000):            # 1 u. = $2 M
        assert sc.pesos(286_400_000) == "143,2 u."
        assert sc.pesos(600_000) == "0,300 u."
    assert sc.pesos(286_400_000) == "$286,4 M"   # afuera del with, vuelve a pesos


def test_el_modo_se_apaga_aunque_haya_un_error():
    with pytest.raises(RuntimeError):
        with sc.publicacion(100):
            raise RuntimeError("algo falló a mitad de camino")
    assert sc._UNIDAD is None


# ── Nombres ─────────────────────────────────────────────────────────────

def test_limpiar_reemplaza_palabras_enteras_y_el_mas_largo_primero():
    mapa = {"Zero": "Proveedor A", "Zero Pinturería": "Proveedor B"}
    assert pub.limpiar("Escalar Zero Pinturería", mapa) == "Escalar Proveedor B"
    assert pub.limpiar("Hablar con zero", mapa) == "Hablar con Proveedor A"
    assert pub.limpiar("Zeroland no es Zero", mapa) == "Zeroland no es Proveedor A"


# ── De punta a punta ────────────────────────────────────────────────────

def test_informe_publico_sin_pesos_ni_nombres(planilla_con_nombres, tmp_path):
    ruta = report.generar(planilla_con_nombres, "2026-09", modo="publico",
                          salida=tmp_path / "pub.docx")
    a2 = tmp_path / "Resumen_QA_2026-09_trimestral_ambos_publico.docx"
    for archivo in (ruta, a2):
        texto = pub.texto_docx(archivo)
        assert "$" not in texto
        assert not any(n in texto for n in REALES)
        assert " u." in texto                      # los montos están, en unidades


def test_los_margenes_son_los_mismos_en_las_dos_versiones(planilla_con_nombres, tmp_path):
    interno = report.generar(planilla_con_nombres, "2026-09", salida=tmp_path / "int.docx")
    publico = report.generar(planilla_con_nombres, "2026-09", modo="publico",
                             salida=tmp_path / "pub.docx")
    import re
    margenes = re.compile(r"\d+,\d{2}%")
    assert margenes.findall(pub.texto_docx(interno)) == \
        margenes.findall(pub.texto_docx(publico))


def test_un_nombre_que_se_escapa_borra_el_archivo(tmp_path):
    from docx import Document
    ruta = tmp_path / "filtrado.docx"
    doc = Document()
    doc.add_paragraph("La recomendación nombra a Globex.")
    doc.save(str(ruta))
    with pytest.raises(ValueError, match="Globex"):
        pub.verificar_docx(ruta, {"Globex": "Proveedor A"})
    assert not ruta.exists()


def test_publico_y_publicar_no_se_combinan(planilla_con_nombres, tmp_path):
    with pytest.raises(SystemExit):
        report.generar(planilla_con_nombres, "2026-09", modo="publico",
                       publicar=True, salida=tmp_path / "x.docx")