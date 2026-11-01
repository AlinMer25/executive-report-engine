"""Tests del cálculo: la bifurcación fiscal y la agregación ponderada."""

import pandas as pd
import pytest

from src import config as cfg
from src import metrics as m


# ── Venta en Blanco ───────────────────────────────────────────────────

def test_blanco_usa_base_sin_iva(venta_blanca):
    """En Blanco el IVA no es ingreso: se descuenta de la base."""
    d = m.calcular(venta_blanca)
    assert d[m.C_BASE].iloc[0] == pytest.approx(100_000)


def test_blanco_paga_iibb(venta_blanca):
    """4% de la base, solo en ventas declaradas."""
    d = m.calcular(venta_blanca)
    assert d[m.C_IIBB].iloc[0] == pytest.approx(4_000)


def test_blanco_ganancia_bruta(venta_blanca):
    """100.000 − 4.000 − 50.000 − 12.100 = 33.900"""
    d = m.calcular(venta_blanca)
    assert d[m.C_GANANCIA_BRUTA].iloc[0] == pytest.approx(33_900)


def test_blanco_suma_el_envio_con_iva(venta_blanca):
    """33.900 + 2.000 = 35.900. En Blanco el envío entra con IVA."""
    d = m.calcular(venta_blanca)
    assert d[m.C_GANANCIA_NETA].iloc[0] == pytest.approx(35_900)
    assert d[m.C_MARGEN_NETO].iloc[0] == pytest.approx(0.359)


# ── Venta en Negro ────────────────────────────────────────────────────

def test_negro_usa_base_con_iva(venta_negra):
    """En Negro el IVA no se declara, así que queda dentro del ingreso."""
    d = m.calcular(venta_negra)
    assert d[m.C_BASE].iloc[0] == pytest.approx(121_000)


def test_negro_no_paga_iibb(venta_negra):
    """Es la diferencia central entre los dos regímenes."""
    d = m.calcular(venta_negra)
    assert d[m.C_IIBB].iloc[0] == 0


def test_negro_ganancia_bruta(venta_negra):
    """121.000 − 0 − 50.000 − 12.100 = 58.900"""
    d = m.calcular(venta_negra)
    assert d[m.C_GANANCIA_BRUTA].iloc[0] == pytest.approx(58_900)


def test_negro_netea_el_iva_del_envio(venta_negra):
    """58.900 + 2.000/1,21 = 60.552,89. Es la asimetría del sistema."""
    d = m.calcular(venta_negra)
    assert d[m.C_GANANCIA_NETA].iloc[0] == pytest.approx(60_552.89, abs=0.01)


def test_la_comision_se_calcula_sobre_el_monto_con_iva(venta_blanca):
    """Aun en Blanco: es lo que la plataforma efectivamente retiene."""
    d = m.calcular(venta_blanca)
    assert d[m.C_COMISION].iloc[0] == pytest.approx(12_100)


# ── Agregación ────────────────────────────────────────────────────────

def test_el_margen_del_periodo_es_ponderado():
    """Dos ventas de tamaño muy distinto NO promedian sus márgenes.

    Una de 1.000.000 al 5% y otra de 10.000 al 50%:
      promedio simple    → 27,5%   (incorrecto, sobrepondera la chica)
      ponderado por monto → 5,4%   (correcto)

    Confundirlos puede invertir la conclusión de un informe.
    """
    df = pd.DataFrame({
        m.C_BASE:          [1_000_000.0, 10_000.0],
        m.C_GANANCIA_NETA: [   50_000.0,  5_000.0],
        m.C_GANANCIA_BRUTA:[   50_000.0,  5_000.0],
        m.C_DIF_ENVIO:     [        0.0,      0.0],
        m.C_MARGEN_NETO:   [       0.05,      0.5],
        cfg.CANTIDAD:      [          1,        1],
    })
    r = m.resumen(df)
    assert r["margen_neto"] == pytest.approx(5.4455, abs=0.001)
    assert r["margen_neto"] != pytest.approx(27.5, abs=1.0)


def test_por_dimension_devuelve_margen_junto_a_facturacion(ventas_mixtas):
    """Un ranking solo por volumen esconde el fenómeno que hay que medir."""
    d = m.calcular(ventas_mixtas)
    t = m.por_dimension(d, cfg.CANAL)
    assert "facturacion" in t.columns and "margen_neto" in t.columns


# ── Contraste contra la planilla ──────────────────────────────────────

def test_el_contraste_no_marca_nada_si_la_planilla_esta_bien(venta_blanca):
    """Tabla vacía significa que la carga está sana."""
    assert len(m.contraste(venta_blanca)) == 0


def test_el_contraste_detecta_una_ganancia_mal_cargada(venta_blanca):
    """Es el caso de la heladera: el motor recalcula y no coincide."""
    roto = venta_blanca.copy()
    roto[cfg.GANANCIA_BRUTA] = 99_999.0
    hallazgos = m.contraste(roto)
    assert len(hallazgos) >= 1
    assert "ganancia_bruta" in hallazgos["metrica"].values


# ── Fuga logística ────────────────────────────────────────────────────

def test_balance_negativo_con_buen_margen_no_es_fuga():
    """El hallazgo central: perder en flete no implica perder margen.

    Si el costo del envío está incorporado al precio, el ingreso lo
    compensa. Marcar esto como fuga fue el error de tres informes.
    """
    df = pd.DataFrame({
        cfg.METODO_ENVIO:  ["FvG Envios", "Mercadoenvios"],
        m.C_BASE:          [100_000_000.0, 10_000_000.0],
        m.C_GANANCIA_NETA: [ 26_000_000.0,  1_800_000.0],   # 26% y 18%
        m.C_DIF_ENVIO:     [ -2_000_000.0,   -500_000.0],   # ambos negativos
        cfg.CANTIDAD:      [            1,             1],
    })
    t = m.fuga_logistica(df, margen_referencia=24.0, participacion_minima=1.0)
    assert not t.loc["FvG Envios", "fuga_real"]      # pierde flete, buen margen
    assert t.loc["Mercadoenvios", "fuga_real"]        # pierde flete Y margen