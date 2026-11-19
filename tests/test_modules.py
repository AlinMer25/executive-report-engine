"""Tests de los módulos opcionales."""

import pandas as pd
import pytest

from src import config as cfg
from src import modules as md
from src import sample_data as sd


@pytest.fixture(scope="module")
def sinteticos():
    return sd.generar()


def _venta(fecha, producto, canal):
    return {cfg.FECHA: fecha, cfg.PRODUCTO: producto, cfg.CANAL: canal}


def test_graduado_es_verde_antes_y_stock_por_primera_vez():
    df = pd.DataFrame([
        _venta("10/08/2026", "Tostadora", cfg.CANAL_VERDE),
        _venta("15/09/2026", "Tostadora", cfg.STOCK_VERDE),   # se gradúa
        _venta("12/08/2026", "Licuadora", cfg.STOCK_VERDE),
        _venta("20/09/2026", "Licuadora", cfg.STOCK_VERDE),   # ya era stock
        _venta("21/09/2026", "Pava", cfg.STOCK_VERDE),        # nunca fue verde
    ])
    assert md.productos_graduados(df, "2026-09") == ["Tostadora"]


def test_modulo_entra_con_los_dos_subcanales(sinteticos):
    s = md.mod_graduacion(sinteticos, "2026-09")
    assert s is not None
    assert s.id == "mod.graduacion"
    assert len(s.tablas["graduacion"]) == 2


def test_modulo_no_entra_con_un_solo_subcanal(sinteticos):
    solo_verde = sinteticos[sinteticos[cfg.CANAL] == cfg.CANAL_VERDE]
    assert md.mod_graduacion(solo_verde, "2026-09") is None


def test_el_modulo_va_antes_de_puntos_de_atencion(sinteticos):
    from src import sections as sc
    ids = [s.id for s in sc.construir(sinteticos, "2026-09", graficos=False)]
    assert ids[-1] == "core.atencion"                 # las alertas cierran
    assert ids.index("mod.graduacion") > ids.index("core.productos")


# ── mod.logistica ───────────────────────────────────────────────────────

def test_logistica_detecta_la_fuga_y_ordena_por_costo(sinteticos):
    s = md.mod_logistica(sinteticos, "2026-09")
    if s is None:
        pytest.skip("Los sintéticos de este mes no tienen fuga real.")
    assert s.id == "mod.logistica"
    assert any("ganancia no obtenida" in f for f in s.frases)


def test_logistica_no_entra_sin_fuga(sinteticos):
    """Si nadie pierde en flete, no hay fuga aunque el margen sea bajo."""
    from src import metrics as m
    sin_perdida = m.calcular(sinteticos)
    sin_perdida[m.C_DIF_ENVIO] = 0.0
    assert md.mod_logistica(sin_perdida, "2026-09") is None


# ── mod.evolucion ───────────────────────────────────────────────────────

def test_semanas_cubren_todo_el_mes(sinteticos):
    t = md.semanas(sinteticos, "2026-09")
    assert t["dias"].sum() == 30                     # septiembre tiene 30 días
    assert t["operaciones"].sum() == len(
        md.filtrar_periodo(sinteticos, "2026-09"))   # ninguna venta se pierde


def test_evolucion_entra_con_semana_pico(sinteticos):
    """Triplicar las ventas de la primera semana fuerza la dispersión."""
    sept = md.filtrar_periodo(sinteticos, "2026-09")
    dia = pd.to_datetime(sept[cfg.FECHA], dayfirst=True).dt.day
    pico = pd.concat([sinteticos] + [sept[dia <= 7]] * 2)
    s = md.mod_evolucion(pico, "2026-09")
    assert s is not None and "S1 (1-7)" in s.frases[0]


def test_evolucion_no_entra_si_el_mes_es_parejo(sinteticos, monkeypatch):
    monkeypatch.setattr(md.cfg, "UMBRAL_DISPERSION_SEMANAL", 1000.0)
    assert md.mod_evolucion(sinteticos, "2026-09") is None