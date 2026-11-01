"""
conftest.py — Datos de prueba compartidos por todos los tests.

pytest busca este archivo automáticamente y pone sus "fixtures" a disposición
de cualquier test que las pida por nombre. No hay que importarlo.

Decisión importante: los tests NO usan datos reales. Usan un conjunto
sintético de pocas filas, con resultados calculados a mano. Hay tres motivos:

1. Un test tiene que poder afirmar "el resultado es exactamente 33.900". Con
   datos reales solo se puede afirmar "no explotó", que no prueba nada.
2. Los datos reales no entran al repositorio. Un test que los necesite es un
   test que nadie más puede correr.
3. Si mañana cambia la planilla, los tests siguen midiendo lo mismo.
"""

import pandas as pd
import pytest

from src import config as cfg


def _fila(**kw):
    """Arma una fila completa con valores por defecto sensatos."""
    base = {
        cfg.MES: "Julio", cfg.FECHA: "15/07/2026", cfg.CANTIDAD: 1,
        cfg.CLIENTE_ID: "900001", cfg.SKU: "111", cfg.PRODUCTO: "Producto de prueba",
        cfg.REGIMEN: cfg.REGIMEN_BLANCO, cfg.PLATAFORMA: "Fravega",
        cfg.METODO_ENVIO: "Flex", cfg.CANAL: cfg.CANAL_VERDE,
        cfg.CATEGORIA: "Cocción", cfg.SUBCATEGORIA: "Cocinas",
        cfg.SUBCATEGORIA_1: "Cocinas Morelli", cfg.PROVEEDOR: "Proveedor A",
        cfg.FINANCIACION: "Sin Financiación",
        cfg.IVA: 21.0, cfg.CALCULO_IVA: 1.21,
        cfg.PRECIO_UNITARIO: 121_000.0, cfg.MONTO: 121_000.0,
        cfg.MONTO_SIN_IVA: 100_000.0,
        cfg.COMISION_PCT: 10.0, cfg.COMISION_PESOS: 12_100.0,
        cfg.COSTO_UNITARIO: 60_500.0, cfg.COSTO_TOTAL: 60_500.0,
        cfg.COSTO_SIN_IVA: 50_000.0,
        cfg.IIBB: 4_000.0,
        cfg.GANANCIA_BRUTA: 33_900.0, cfg.MARGEN_BRUTO: 0.339,
        cfg.PAGO_ENVIO: 5_000.0, cfg.COSTO_ENVIO: 3_000.0,
        cfg.DIFERENCIA_ENVIO: 2_000.0, cfg.DIFERENCIA_ENVIO_SIN_IVA: 1_652.89,
        cfg.GANANCIA_NETA: 35_900.0, cfg.MARGEN_NETO: 0.359,
    }
    base.update(kw)
    return base


@pytest.fixture
def venta_blanca():
    """Una venta en Blanco con números redondos verificables a mano.

    Base 100.000 (sin IVA) − IIBB 4.000 − costo 50.000 − comisión 12.100
      = ganancia bruta 33.900        → margen bruto 33,9%
    + diferencia de envío 2.000 (con IVA, porque es Blanco)
      = ganancia neta 35.900         → margen neto 35,9%
    """
    return pd.DataFrame([_fila()])


@pytest.fixture
def venta_negra():
    """La misma venta pero en Negro, para contrastar la bifurcación fiscal.

    Base 121.000 (CON IVA) − IIBB 0 − costo 50.000 − comisión 12.100
      = ganancia bruta 58.900
    + diferencia de envío 2.000 / 1,21 = 1.652,89 (sin IVA, porque es Negro)
      = ganancia neta 60.552,89
    """
    return pd.DataFrame([_fila(
        **{cfg.REGIMEN: cfg.REGIMEN_NEGRO, cfg.IIBB: 0.0,
           cfg.GANANCIA_BRUTA: 58_900.0, cfg.GANANCIA_NETA: 60_552.89})])


@pytest.fixture
def ventas_mixtas():
    """Cinco filas que cubren los casos que el motor tiene que distinguir.

    0 — Blanco normal
    1 — Negro normal
    2 — Stock Verde (para el filtro de canal)
    3 — fila de plantilla vacía (para el descarte)
    4 — margen absurdo (para la regla de validación R01)
    """
    return pd.DataFrame([
        _fila(),
        _fila(**{cfg.REGIMEN: cfg.REGIMEN_NEGRO, cfg.IIBB: 0.0,
                 cfg.GANANCIA_BRUTA: 58_900.0, cfg.GANANCIA_NETA: 60_552.89}),
        _fila(**{cfg.CANAL: cfg.STOCK_VERDE, cfg.PRODUCTO: "Producto graduado"}),
        _fila(**{cfg.MES: "", cfg.MONTO: 0.0, cfg.MONTO_SIN_IVA: 0.0,
                 cfg.PLATAFORMA: "", cfg.CANAL: ""}),
        _fila(**{cfg.COSTO_TOTAL: 1_210.0, cfg.COSTO_SIN_IVA: 1_000.0,
                 cfg.PRODUCTO: "Heladera mal cargada",
                 cfg.GANANCIA_NETA: 84_900.0, cfg.MARGEN_NETO: 0.849}),
    ])


@pytest.fixture
def planilla_xlsx(tmp_path, ventas_mixtas):
    """Escribe las ventas mixtas a un .xlsx temporal.

    tmp_path es una fixture de pytest: una carpeta nueva y vacía para cada
    test, que se borra sola al terminar. Evita que un test ensucie el disco
    o dependa de archivos dejados por otro.
    """
    ruta = tmp_path / "planilla.xlsx"
    ventas_mixtas.to_excel(ruta, sheet_name=cfg.HOJA_VENTAS, index=False)
    return ruta