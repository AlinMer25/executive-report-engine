"""Tests del congelado: que una foto se pueda releer y comparar."""

import pytest

from src import config as cfg
from src import snapshot as snap


@pytest.fixture(autouse=True)
def snapshots_en_carpeta_temporal(tmp_path, monkeypatch):
    """Redirige los snapshots a una carpeta temporal.

    monkeypatch cambia un valor solo durante el test y lo restaura al
    terminar. Sin esto, cada corrida de los tests dejaría archivos en
    data/snapshots/ del proyecto real.
    """
    monkeypatch.setattr(snap, "DIR_SNAPSHOTS", tmp_path / "snapshots")


def test_congelar_crea_datos_y_ficha(venta_blanca):
    ruta = snap.congelar(venta_blanca, "2026-07", etiqueta="prueba")
    assert ruta.exists()
    assert ruta.with_suffix(".json").exists()


def test_la_huella_cambia_si_cambian_los_datos(tmp_path, venta_blanca):
    """Dos archivos con distinto contenido no pueden compartir huella."""
    a = tmp_path / "a.csv"; b = tmp_path / "b.csv"
    venta_blanca.to_csv(a, index=False)
    otro = venta_blanca.copy(); otro[cfg.MONTO] = 999.0
    otro.to_csv(b, index=False)
    assert snap.huella(a) != snap.huella(b)


def test_la_huella_es_igual_con_el_mismo_contenido(tmp_path, venta_blanca):
    a = tmp_path / "a.csv"; b = tmp_path / "b.csv"
    venta_blanca.to_csv(a, index=False)
    venta_blanca.to_csv(b, index=False)
    assert snap.huella(a) == snap.huella(b)


def test_cargar_devuelve_lo_congelado(venta_blanca):
    snap.congelar(venta_blanca, "2026-07")
    recuperado = snap.cargar("2026-07")
    assert len(recuperado) == len(venta_blanca)
    assert recuperado[cfg.MONTO].iloc[0] == venta_blanca[cfg.MONTO].iloc[0]


def test_cargar_un_periodo_inexistente_falla_claro():
    with pytest.raises(FileNotFoundError, match="2099-01"):
        snap.cargar("2099-01")


def test_comparar_detecta_el_cambio(venta_blanca):
    """Es la función que convierte una sorpresa en una explicación."""
    snap.congelar(venta_blanca, "2026-07", etiqueta="cierre")
    crecido = venta_blanca.copy()
    crecido.loc[1] = crecido.loc[0]           # llega una venta rezagada
    snap.congelar(crecido, "2026-07", etiqueta="recalculo")

    # Se extrae primero la columna y después se busca la fila. Acceder con
    # .loc[fila, columna] en dos ejes a la vez devuelve un valor sin tipo
    # definido, y además se lee peor.
    diferencias = snap.comparar("2026-07").set_index("metrica")["diferencia"]
    assert diferencias["operaciones"] == 1
    assert diferencias["facturacion"] > 0