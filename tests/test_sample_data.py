"""Tests del dataset sintético que se publica en el repositorio."""
 
import pytest
 
from src import config as cfg
from src import metrics as m
from src import sample_data as sd
from src.ingest import cargar_ventas
 
 
@pytest.fixture(scope="module")
def sintetico():
    return sd.generar()
 
 
def test_es_reproducible(sintetico):
    """Dos corridas dan el mismo archivo.
 
    Es lo que lo convierte en parte del repositorio y no en un artefacto
    que cambia cada vez que alguien lo regenera.
    """
    assert sd.generar().equals(sintetico)
 
 
def test_otra_semilla_da_otro_dataset(sintetico):
    assert not sd.generar(semilla=1).equals(sintetico)
 
 
def test_tiene_todas_las_columnas_obligatorias(sintetico):
    faltantes = [c for c in cfg.COLUMNAS_REQUERIDAS if c not in sintetico.columns]
    assert not faltantes, faltantes
 
 
def test_es_internamente_consistente(tmp_path):
    """El contraste sobre el dataset sintético tiene que dar cero.
 
    Si diera algo, el motor estaría en desacuerdo con los datos que él
    mismo genera, y no se sabría cuál de los dos está mal.
    """
    ruta, _ = sd.escribir(tmp_path / "s.xlsx")
    df = m.calcular(cargar_ventas(ruta))
    assert len(m.contraste(df)) == 0
 
 
def test_reproduce_los_dos_regimenes_fiscales(sintetico):
    """Sin las dos ramas, el dataset no ejercita el cálculo principal."""
    regimenes = set(sintetico[cfg.REGIMEN])
    assert regimenes == {cfg.REGIMEN_BLANCO, cfg.REGIMEN_NEGRO}
 
 
def test_reproduce_los_dos_subcanales(sintetico):
    assert set(sintetico[cfg.CANAL]) == {cfg.CANAL_VERDE, cfg.STOCK_VERDE}
 
 
def test_reproduce_el_efecto_del_envio_gratis(tmp_path):
    """El fenómeno tiene que estar en los datos, o el demo no demuestra nada.
 
    En el caso real el envío gratis rinde unos 4 puntos menos. El dataset
    sintético tiene que mostrar una brecha del mismo signo y orden.
    """
    ruta, _ = sd.escribir(tmp_path / "s.xlsx")
    df = m.calcular(cargar_ventas(ruta))
    gratis = [p for p, _, eg in sd.PLATAFORMAS if eg]
    con = df[df[cfg.PLATAFORMA].isin(gratis)]
    sin = df[~df[cfg.PLATAFORMA].isin(gratis)]
    margen = lambda d: d[m.C_GANANCIA_NETA].sum() / d[m.C_BASE].sum() * 100
    assert margen(con) < margen(sin) - 2.0
 
 
def test_ningun_proveedor_lleva_nombre_real(sintetico):
    """El dataset se publica: los proveedores ya nacen pseudonimizados."""
    assert all(str(p).startswith("Proveedor ")
               for p in sintetico[cfg.PROVEEDOR].unique())
