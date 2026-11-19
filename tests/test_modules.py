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
    assert ids[-2:] == ["mod.graduacion", "core.atencion"]