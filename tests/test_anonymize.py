"""Tests de la anonimización y del invariante monetario.
 
Estos son los tests que decidén si el repositorio puede ser público. Si
alguno falla, hay un valor confidencial a punto de publicarse.
"""
 
import pandas as pd
import pytest
 
from src import anonymize as an
from src import config as cfg
from src import metrics as m
 
 
# ── Índice base 100 ───────────────────────────────────────────────────
 
def test_el_indice_arranca_en_cien():
    serie = pd.Series([21_928_190.0, 70_493_510.0, 328_610_100.0])
    assert an.indexar(serie).iloc[0] == 100.0
 
 
def test_el_indice_conserva_las_proporciones():
    """Es lo que hace que el análisis siga siendo verdadero sin los montos.
 
    Si la facturación se multiplicó por 15, el índice va de 100 a 1500.
    Se publica la trayectoria real; se oculta la magnitud.
    """
    serie = pd.Series([100_000.0, 300_000.0, 1_500_000.0])
    idx = an.indexar(serie)
    assert idx.tolist() == [100.0, 300.0, 1500.0]
 
 
def test_la_base_del_indice_puede_fijarse():
    serie = pd.Series([200.0, 400.0])
    assert an.indexar(serie, valor_base=400.0).tolist() == [50.0, 100.0]
 
 
def test_base_cero_falla_en_vez_de_dar_infinito():
    with pytest.raises(ValueError, match="no puede ser cero"):
        an.indexar(pd.Series([0.0, 10.0]))
 
 
# ── Pseudónimos ───────────────────────────────────────────────────────
 
def test_el_pseudonimo_es_estable_entre_corridas(tmp_path):
    """El Proveedor A de abril tiene que seguir siendo el A en septiembre.
 
    Sin esto, comparar dos informes deja de significar algo.
    """
    ruta = tmp_path / "mapa.json"
    primero = an.asignar_pseudonimos(["Zeta", "Alfa"], ruta=ruta)
    segundo = an.asignar_pseudonimos(["Alfa", "Zeta", "Beta"], ruta=ruta)
    assert segundo["Alfa"] == primero["Alfa"]
    assert segundo["Zeta"] == primero["Zeta"]
 
 
def test_un_proveedor_nuevo_recibe_la_letra_siguiente(tmp_path):
    ruta = tmp_path / "mapa.json"
    an.asignar_pseudonimos(["Alfa", "Zeta"], ruta=ruta)
    mapa = an.asignar_pseudonimos(["Alfa", "Zeta", "Beta"], ruta=ruta)
    assert mapa["Beta"] == "Proveedor C"
 
 
def test_el_pseudonimo_conserva_el_rubro(tmp_path):
    """Un proveedor sin rubro es una letra sin información."""
    mapa = an.asignar_pseudonimos(
        ["Alfa"], rubros={"Alfa": "línea blanca"}, ruta=tmp_path / "m.json")
    assert mapa["Alfa"] == "Proveedor A (línea blanca)"
 
 
def test_el_mapa_queda_guardado(tmp_path):
    """Es la única pieza que permitiría revertir la anonimización.
 
    Por eso vive en config/pseudonyms_private.json y está en .gitignore.
    """
    ruta = tmp_path / "mapa.json"
    an.asignar_pseudonimos(["Alfa"], ruta=ruta)
    assert ruta.exists()
    assert an.cargar_mapa(ruta)["Alfa"] == "Proveedor A"
 
 
# ── El invariante monetario ───────────────────────────────────────────
 
@pytest.mark.parametrize("texto", [
    "La facturación fue de $317.480.000",
    "ganancia neta $73.160.000 en el mes",
    "el costo de estructura es 2.570.000 por mes",
])
def test_detecta_montos_absolutos(texto):
    assert an.buscar_montos(texto)
 
 
@pytest.mark.parametrize("texto", [
    "el margen neto fue de 23,04%",
    "la facturación llegó a 1.443,7 puntos de índice",
    "en septiembre de 2026 hubo 748 operaciones",
    "la brecha fue de 1,64 pp",
])
def test_no_marca_indices_porcentajes_ni_anios(texto):
    """Un invariante que marca lo que está bien se desactiva al segundo mes."""
    assert not an.buscar_montos(texto)
 
 
def test_falla_si_sobrevive_una_columna_en_pesos():
    tabla = pd.DataFrame({"operaciones": [100], "facturacion": [50_000_000.0]})
    with pytest.raises(ValueError, match="facturacion"):
        an.verificar_publicable(tabla, "una tabla")
 
 
def test_falla_con_una_columna_prohibida():
    """El costo de compra por SKU no se publica ni siquiera indexado."""
    tabla = pd.DataFrame({"operaciones": [100], cfg.COSTO_UNITARIO: [1234.0]})
    with pytest.raises(ValueError, match="prohibidas"):
        an.verificar_publicable(tabla, "una tabla")
 
 
def test_la_serie_anonimizada_pasa_el_invariante():
    serie = pd.DataFrame({
        "operaciones": [104, 784],
        "facturacion": [21_928_190.0, 328_610_100.0],
        "ganancia_neta": [6_119_404.0, 80_833_005.0],
        "margen_neto": [27.91, 24.60],
    }, index=["Abril", "Septiembre"])
    publicable = an.anonimizar_serie_mensual(serie)
    an.verificar_publicable(publicable, "la serie")   # no debe levantar
 
 
def test_la_anonimizacion_no_toca_lo_que_es_real():
    """Operaciones y márgenes se publican tal cual: no son confidenciales."""
    serie = pd.DataFrame({
        "operaciones": [104, 784],
        "facturacion": [21_928_190.0, 328_610_100.0],
        "margen_neto": [27.91, 24.60],
    }, index=["Abril", "Septiembre"])
    pub = an.anonimizar_serie_mensual(serie)
    assert pub["operaciones"].tolist() == [104, 784]
    assert pub["margen_neto"].tolist() == [27.91, 24.60]
