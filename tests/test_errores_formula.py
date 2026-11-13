"""Tests de la detección de errores de fórmula (regla R16).

Escribir un error real de Excel en un archivo de prueba requiere openpyxl:
pandas no sabe escribirlos, solo sabe borrarlos al leer.
"""

import openpyxl
import pytest

from src import config as cfg
from src import validate as v
from src.ingest import cargar_ventas


def _con_errores(ruta_origen, ruta_destino, errores_por_fila):
    """Copia un .xlsx y escribe errores de fórmula en celdas elegidas.

    errores_por_fila: {fila_de_datos: (columna, error)}, fila 0 = primera venta.
    """
    libro = openpyxl.load_workbook(ruta_origen)
    hoja = libro[cfg.HOJA_VENTAS]
    columnas = {c.value: c.column for c in hoja[1]}
    for fila, (columna, error) in errores_por_fila.items():
        celda = hoja.cell(row=fila + 2, column=columnas[columna])
        celda.value = error
        celda.data_type = "e"          # "e" = error: así lo guarda Excel
    libro.save(ruta_destino)
    return ruta_destino


@pytest.fixture
def planilla_con_errores(tmp_path, planilla_xlsx):
    return _con_errores(planilla_xlsx, tmp_path / "con_errores.xlsx", {
        0: (cfg.GANANCIA_NETA, "#REF!"),
        1: (cfg.MONTO, "#DIV/0!"),
    })


def test_detecta_el_error_y_dice_donde_esta(planilla_con_errores):
    df = cargar_ventas(planilla_con_errores)
    errores = df[cfg.ERRORES_FORMULA].tolist()
    assert any("#REF!" in e and cfg.GANANCIA_NETA in e for e in errores)


def test_un_error_en_el_monto_no_hace_desaparecer_la_venta(planilla_con_errores):
    """El caso grave: con el monto en error, la fila parecía vacía y se
    descartaba. La venta desaparecía del total sin dejar rastro."""
    df = cargar_ventas(planilla_con_errores)
    assert any("#DIV/0!" in e for e in df[cfg.ERRORES_FORMULA])


def test_la_regla_r16_marca_las_filas_con_error(planilla_con_errores):
    df = cargar_ventas(planilla_con_errores)
    r16 = [h for h in v.validar(df) if h.id == "R16"]
    assert r16 and r16[0].cantidad == 2
    assert r16[0].severidad == v.ALTA


def test_una_planilla_sana_no_dispara_r16(planilla_xlsx):
    df = cargar_ventas(planilla_xlsx)
    assert "R16" not in [h.id for h in v.validar(df)]


@pytest.mark.parametrize("error", ["#VALUE!", "#REF!", "#NAME?", "#DIV/0!",
                                   "#N/A", "#NULL!", "#NUM!"])
def test_detecta_los_siete_tipos_de_error(tmp_path, planilla_xlsx, error):
    ruta = _con_errores(planilla_xlsx, tmp_path / "e.xlsx", {0: (cfg.IIBB, error)})
    assert error in cargar_ventas(ruta)[cfg.ERRORES_FORMULA].iloc[0]