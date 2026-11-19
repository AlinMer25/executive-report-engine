"""Tests de sections.py: qué secciones van, qué números llevan, qué dicen."""

import pandas as pd
import pytest

from src import config as cfg
from src import sections as sc
from src import sample_data as sd


@pytest.fixture(scope="module")
def sinteticos():
    return sd.generar()


# ── Formato argentino ─────────────────────────────────────────────────

@pytest.mark.parametrize("valor, esperado", [
    (317_480_000, "$317,5 M"),
    (424_437, "$424.437"),
    (-5_200_000, "$-5,2 M"),
])
def test_formato_de_pesos(valor, esperado):
    assert sc.pesos(valor) == esperado


def test_el_margen_varia_en_puntos_no_en_porcentaje():
    """Invariante I6: 'cayó 1,64 pp', nunca 'cayó 6,6%'."""
    assert sc.pp(-1.64) == "-1,64 pp"


# ── Períodos ──────────────────────────────────────────────────────────

def test_periodo_anterior_cruza_el_anio():
    assert sc.periodo_anterior("2026-01") == "2025-12"


def test_filtra_por_fecha_y_no_por_la_columna_mes():
    """'Mes' no tiene año: octubre de 2026 y de 2027 serían lo mismo."""
    df = pd.DataFrame({cfg.FECHA: ["15/10/2026", "15/10/2027"],
                       cfg.MES: ["Octubre", "Octubre"]})
    assert len(sc.filtrar_periodo(df, "2026-10")) == 1


# ── Armado ────────────────────────────────────────────────────────────

def test_arma_las_secciones_del_nucleo_en_orden(sinteticos):
    # Solo el núcleo: los módulos opcionales (mod.*) tienen sus propios tests.
    ids = [s.id for s in sc.construir(sinteticos, "2026-09", graficos=False)
           if s.id.startswith("core.")]
    assert ids == ["core.resumen", "core.kpis", "core.plataformas",
                   "core.categorias", "core.proveedores", "core.productos",
                   "core.seguimiento", "core.atencion", "core.recomendaciones"]


def test_el_resumen_usa_los_numeros_del_periodo(sinteticos):
    secciones = sc.construir(sinteticos, "2026-09")
    resumen = secciones[0].frases[0]
    ventas = len(sc.filtrar_periodo(sinteticos, "2026-09"))
    assert f"{ventas} ventas" in resumen


def test_productos_no_muestra_costos(sinteticos):
    """El costo de compra por SKU no se publica nunca."""
    productos = [s for s in sc.construir(sinteticos, "2026-09")
                 if s.id == "core.productos"][0]
    columnas = " ".join(productos.tablas["productos"].columns).lower()
    assert "costo" not in columnas


def test_falla_claro_si_no_hay_periodo_anterior(sinteticos):
    with pytest.raises(ValueError, match="período anterior"):
        sc.construir(sinteticos, "2026-04")   # abril es el primer mes


# ── Alertas de margen ─────────────────────────────────────────────────

def _r(margen, facturacion=100_000_000):
    return {"margen_neto": margen, "facturacion": facturacion}


def test_sin_alerta_si_el_margen_esta_sano():
    s = sc.seccion_atencion(_r(25.0), _r(24.0), [])
    assert not s.alertas


def test_alerta_bajo_el_primer_piso():
    s = sc.seccion_atencion(_r(22.0), _r(24.0), [])
    assert len(s.alertas) == 1 and "piso de alarma" in s.alertas[0]


def test_alerta_severa_bajo_el_segundo_piso():
    s = sc.seccion_atencion(_r(19.0), _r(24.0), [])
    assert s.alertas[0].startswith("ALERTA SEVERA")


def test_la_alerta_de_margen_va_en_pesos():
    """2 puntos sobre $100 M son $2 M: la alerta tiene que decirlo."""
    s = sc.seccion_atencion(_r(22.0), _r(24.0), [])
    assert "$2,0 M" in s.alertas[0]


def test_alerta_por_tendencia_aunque_no_cruce_ningun_piso():
    """El problema de julio a septiembre no fue el nivel sino la deriva."""
    s = sc.seccion_atencion(_r(24.0), _r(24.5), [26.0, 25.5, 24.5])
    assert any("Tendencia" in a for a in s.alertas)


def test_sin_tendencia_si_hubo_un_rebote():
    s = sc.seccion_atencion(_r(24.0), _r(24.5), [26.0, 24.0, 24.5])
    assert not any("Tendencia" in a for a in s.alertas)


# ── Gráficos ────────────────────────────────────────────────────────────

def test_serie_mensual_hasta_el_periodo(sinteticos):
    serie = sc.serie_mensual(sinteticos, "2026-09", meses=6)
    assert list(serie.index) == ["2026-04", "2026-05", "2026-06",
                                 "2026-07", "2026-08", "2026-09"]


def test_graficos_se_cuelgan_de_su_seccion(sinteticos):
    secciones = {s.id: s for s in sc.construir(sinteticos, "2026-09")}
    assert "evolucion" in secciones["core.kpis"].graficos
    assert "margen" in secciones["core.plataformas"].graficos
    png = secciones["core.kpis"].graficos["evolucion"]
    assert png[:8] == b"\x89PNG\r\n\x1a\n"      # firma de todo archivo PNG


def test_sin_graficos(sinteticos):
    secciones = sc.construir(sinteticos, "2026-09", graficos=False)
    assert all(not s.graficos for s in secciones)