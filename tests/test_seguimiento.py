"""Tests de seguimiento.py: recomendaciones con ID y su seguimiento."""

import json

import pytest

from src import config as cfg
from src import sample_data as sd
from src import seguimiento as sg


@pytest.fixture(scope="module")
def sinteticos():
    return sd.generar()


def escribir(periodo, recos):
    """Guarda un archivo de recomendaciones en la carpeta (temporal) de tests."""
    cfg.DIR_RECOMENDACIONES.mkdir(parents=True, exist_ok=True)
    ruta = cfg.DIR_RECOMENDACIONES / f"{periodo}.json"
    ruta.write_text(json.dumps(recos, ensure_ascii=False), encoding="utf-8")


# ── Validación del archivo ──────────────────────────────────────────────

@pytest.mark.parametrize("recos, mensaje", [
    ([{"texto": "sin id"}], "'id' y 'texto'"),
    ([{"id": "1", "texto": "a"}, {"id": "1", "texto": "b"}], "repetido"),
    ([{"id": "1", "texto": "a", "estado": "hecha"}], "estado"),
    ([{"id": "1", "texto": "a", "medir": {"metrica": "ventas"}}], "métrica"),
])
def test_errores_del_archivo_se_frenan_con_mensaje(recos, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        sg.validar(recos, "prueba.json")


# ── Estado automático ───────────────────────────────────────────────────

@pytest.mark.parametrize("antes, ahora, objetivo, esperado", [
    (20.0, 24.0, 23.0, "cumplida"),
    (20.0, 22.0, 23.0, "en curso"),
    (20.0, 19.0, 23.0, "no abordada"),
    (20.0, 21.0, None, "en curso"),
    (None, None, 23.0, None),
])
def test_estado_automatico(antes, ahora, objetivo, esperado):
    assert sg.estado_automatico(antes, ahora, objetivo) == esperado


# ── Secciones ───────────────────────────────────────────────────────────

def test_sin_archivo_pide_completar(sinteticos):
    s = sg.seccion_seguimiento(sinteticos, "2026-09")
    assert "data/recomendaciones/2026-08.json" in s.frases[0]


def test_se_emiten_todas_incluso_las_no_medibles(sinteticos):
    escribir("2026-08", [
        {"id": "2026-08-01", "texto": "Subir margen de Bigote",
         "medir": {"dimension": cfg.PLATAFORMA, "valor": "Bigote",
                   "metrica": "margen_neto", "objetivo": 99.0}},
        {"id": "2026-08-02", "texto": "Hablar con el proveedor X"},
        {"id": "2026-08-03", "texto": "Cerrar cuenta vieja",
         "estado": "superada por los hechos"},
    ])
    s = sg.seccion_seguimiento(sinteticos, "2026-09")
    t = s.tablas["seguimiento"]
    assert list(t["ID"]) == ["2026-08-01", "2026-08-02", "2026-08-03"]
    assert "→" in t.iloc[0]["Dato"]                     # se midió
    assert t.iloc[1]["Estado"] == "[Completar]"          # no medible, sin estado
    assert t.iloc[2]["Estado"] == "superada por los hechos"   # declarado pisa


def test_el_agregado_no_esconde_contraejemplos(sinteticos):
    """El caso Mosconi: grupo con miembros que van en direcciones opuestas."""
    plataformas = list(sinteticos[cfg.PLATAFORMA].dropna().unique())
    escribir("2026-08", [{"id": "g", "texto": "Mantener todas las plataformas",
                          "medir": {"dimension": cfg.PLATAFORMA,
                                    "valor": plataformas,
                                    "metrica": "margen_neto"}}])
    s = sg.seccion_seguimiento(sinteticos, "2026-09")
    # Con todas las plataformas del canal, alguna va contra el agregado.
    assert any("van en contra" in f for f in s.frases)


def test_recomendaciones_del_mes_con_id():
    escribir("2026-09", [{"id": "2026-09-01", "texto": "Revisar precios"}])
    s = sg.seccion_recomendaciones("2026-09")
    assert s.frases == ["[2026-09-01] Revisar precios"]


def test_lo_que_no_existia_y_arranco_esta_en_curso():
    """El caso Midea: sin ventas en septiembre, primeras ventas en octubre."""
    assert sg.estado_automatico(None, 4_500_000.0, None) == "en curso"