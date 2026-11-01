"""Tests de la carga: conversión de números, descartes y filtros."""

import pandas as pd
import pytest

from src import config as cfg
from src.ingest import a_numero, cargar_ventas, verificar_columnas


# ── Conversión de números en formato argentino ────────────────────────

@pytest.mark.parametrize("texto, esperado", [
    (" $399.999,00", 399999.00),   # con símbolo, miles y decimales
    ("48.400,00",     48400.00),   # sin símbolo
    ("$0,00",             0.00),   # cero explícito
    ("2,66%",             2.66),   # porcentaje: se saca el signo
    ("10,5",             10.50),   # alícuota de IVA
    (" $-1.234,56",   -1234.56),   # negativo con guion
    ("($9.876,54)",   -9876.54),   # negativo en formato contable
])
def test_convierte_formato_argentino(texto, esperado):
    """El punto separa miles y la coma decimales, al revés que en Python."""
    assert a_numero(pd.Series([texto])).iloc[0] == pytest.approx(esperado)


@pytest.mark.parametrize("texto", ["", None, "Canal Verde", "   "])
def test_lo_no_numerico_queda_nulo_no_cero(texto):
    """Un cero se sumaría; un nulo se puede contar aparte. La diferencia importa."""
    assert pd.isna(a_numero(pd.Series([texto])).iloc[0])


# ── Verificación de columnas ──────────────────────────────────────────

def test_falla_si_falta_una_columna_obligatoria(ventas_mixtas):
    """Mejor un error ruidoso que un resultado incompleto en silencio."""
    sin_canal = ventas_mixtas.drop(columns=[cfg.CANAL])
    with pytest.raises(ValueError, match="Faltan columnas"):
        verificar_columnas(sin_canal)


def test_el_error_nombra_la_columna_que_falta(ventas_mixtas):
    """Un mensaje útil dice qué arreglar, no solo que algo falló."""
    sin_canal = ventas_mixtas.drop(columns=[cfg.CANAL])
    with pytest.raises(ValueError) as e:
        verificar_columnas(sin_canal)
    assert cfg.CANAL in str(e.value)


# ── Carga completa ────────────────────────────────────────────────────

def test_descarta_las_filas_de_plantilla(planilla_xlsx):
    """La fila sin mes y con monto cero no es una venta."""
    df = cargar_ventas(planilla_xlsx)
    assert len(df) == 4          # de las 5 originales
    assert (df[cfg.MONTO] > 0).all()


def test_filtro_de_canal(planilla_xlsx):
    """'ambos' es el default y es la cifra histórica del canal."""
    assert len(cargar_ventas(planilla_xlsx)) == 4
    assert len(cargar_ventas(planilla_xlsx, canal="canal_verde")) == 3
    assert len(cargar_ventas(planilla_xlsx, canal="stock_verde")) == 1


def test_canal_invalido_falla_con_las_opciones(planilla_xlsx):
    with pytest.raises(ValueError, match="canal_verde"):
        cargar_ventas(planilla_xlsx, canal="verde")


def test_las_columnas_quedan_numericas(planilla_xlsx):
    """Si quedaran como texto, cualquier suma concatenaría en vez de sumar."""
    df = cargar_ventas(planilla_xlsx)
    for col in (cfg.MONTO, cfg.GANANCIA_NETA, cfg.DIFERENCIA_ENVIO):
        assert pd.api.types.is_numeric_dtype(df[col]), col