"""Tests de las reglas de calidad de datos."""

from src import config as cfg
from src import metrics as m
from src import validate as v


def test_no_marca_una_venta_sana(venta_blanca):
    """Una fila correcta no debe disparar ninguna regla de severidad alta."""
    hallazgos = v.validar(venta_blanca)
    assert not any(h.severidad == v.ALTA for h in hallazgos)


def test_detecta_el_margen_absurdo(ventas_mixtas):
    """R01: la regla que existe por el caso de la heladera."""
    ids = [h.id for h in v.validar(ventas_mixtas)]
    assert "R01" in ids


def test_detecta_la_fila_sin_canal(ventas_mixtas):
    """R14: nació de perfilar los datos, no estaba en el diccionario."""
    ids = [h.id for h in v.validar(ventas_mixtas)]
    assert "R14" in ids


def test_cada_hallazgo_trae_las_filas_culpables(ventas_mixtas):
    """Marcar sin mostrar dónde obliga a buscar a mano. No sirve."""
    for h in v.validar(ventas_mixtas):
        assert h.cantidad == len(h.filas)
        assert h.cantidad > 0


def test_el_informe_ordena_por_severidad(ventas_mixtas):
    t = v.informe(ventas_mixtas)
    if len(t) > 1:
        orden = {v.ALTA: 0, v.MEDIA: 1, v.BAJA: 2}
        valores = [orden[s] for s in t["severidad"]]
        assert valores == sorted(valores)


def test_hay_bloqueantes_detecta_severidad_alta(ventas_mixtas, venta_blanca):
    """Sirve para que el generador se detenga antes de informar sobre datos malos."""
    assert v.hay_bloqueantes(ventas_mixtas)
    assert not v.hay_bloqueantes(venta_blanca)