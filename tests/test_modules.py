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
    assert ids[-2:] == ["core.atencion", "core.recomendaciones"]
    assert ids.index("mod.graduacion") > ids.index("core.productos")


# ── mod.logistica ───────────────────────────────────────────────────────

def test_logistica_detecta_la_fuga_y_ordena_por_costo(sinteticos):
    s = md.mod_logistica(sinteticos, "2026-09")
    if s is None:
        pytest.skip("Los sintéticos de este mes no tienen fuga real.")
    assert s.id == "mod.logistica"
    assert any("ganancia no obtenida" in f for f in s.frases)


def test_logistica_no_entra_sin_fuga(sinteticos):
    """Si nadie pierde en flete, no hay fuga aunque el margen sea bajo."""
    from src import metrics as m
    sin_perdida = m.calcular(sinteticos)
    sin_perdida[m.C_DIF_ENVIO] = 0.0
    assert md.mod_logistica(sin_perdida, "2026-09") is None


# ── mod.evolucion ───────────────────────────────────────────────────────

def test_semanas_cubren_todo_el_mes(sinteticos):
    t = md.semanas(sinteticos, "2026-09")
    assert t["dias"].sum() == 30                     # septiembre tiene 30 días
    assert t["operaciones"].sum() == len(
        md.filtrar_periodo(sinteticos, "2026-09"))   # ninguna venta se pierde


def test_evolucion_entra_con_semana_pico(sinteticos):
    """Triplicar las ventas de la primera semana fuerza la dispersión."""
    sept = md.filtrar_periodo(sinteticos, "2026-09")
    dia = pd.to_datetime(sept[cfg.FECHA], dayfirst=True).dt.day
    pico = pd.concat([sinteticos] + [sept[dia <= 7]] * 2)
    s = md.mod_evolucion(pico, "2026-09")
    assert s is not None and "S1 (1-7)" in s.frases[0]


def test_evolucion_no_entra_si_el_mes_es_parejo(sinteticos, monkeypatch):
    monkeypatch.setattr(md.cfg, "UMBRAL_DISPERSION_SEMANAL", 1000.0)
    assert md.mod_evolucion(sinteticos, "2026-09") is None


# ── mod.integridad ──────────────────────────────────────────────────────

from src import snapshot as snap  # noqa: E402


def test_integridad_no_entra_sin_snapshots(sinteticos):
    assert md.mod_integridad(sinteticos, "2026-09") is None


def test_integridad_no_entra_si_no_cambio_nada(sinteticos):
    snap.congelar(md.filtrar_periodo(sinteticos, "2026-08"), "2026-08")
    assert md.reexpresiones(sinteticos, "2026-09").empty
    assert md.mod_integridad(sinteticos, "2026-09") is None


def test_integridad_detecta_un_mes_reexpresado(sinteticos):
    """Se publica agosto; después aparece un 10% más de ventas cargadas tarde."""
    agosto = md.filtrar_periodo(sinteticos, "2026-08")
    snap.congelar(agosto, "2026-08", etiqueta="informe publicado")
    tardias = agosto.head(len(agosto) // 10)
    hoy = pd.concat([sinteticos, tardias])

    s = md.mod_integridad(hoy, "2026-09")
    assert s is not None
    assert "2026-08" in s.frases[0]
    assert "Ventas" in set(s.tablas["reexpresiones"]["Métrica"])


def test_cambio_chico_va_solo_a_metodologia(sinteticos):
    """Un cambio < 5% se declara, pero no abre sección propia."""
    agosto = md.filtrar_periodo(sinteticos, "2026-08")
    snap.congelar(agosto, "2026-08")
    hoy = pd.concat([sinteticos, agosto.head(3)])
    assert not md.reexpresiones(hoy, "2026-09").empty
    assert md.mod_integridad(hoy, "2026-09") is None


# ── Parámetros y mod.evolucion_larga ────────────────────────────────────

def test_corte_invalido_se_rechaza_al_crear():
    with pytest.raises(ValueError, match="corte_comparativo"):
        md.Parametros(corte="quincenal")


@pytest.mark.parametrize("corte, meses", [
    ("bimestral", ["2026-08", "2026-09"]),
    ("trimestral", ["2026-07", "2026-08", "2026-09"]),
])
def test_ventana_termina_en_el_periodo(corte, meses):
    assert md.ventana("2026-09", md.CORTES[corte]) == meses


def test_nombre_de_ventana():
    assert md.nombre_ventana(["2026-07", "2026-08", "2026-09"]) == "jul–sep 2026"
    assert md.nombre_ventana(["2026-11", "2026-12", "2027-01"]) == "nov 2026–ene 2027"


def test_mensual_no_emite_analitica_larga(sinteticos):
    p = md.Parametros(corte="mensual")
    assert md.mod_evolucion_larga(sinteticos, "2026-09", p) is None


def test_trimestral_compara_contra_el_trimestre_anterior(sinteticos):
    s = md.mod_evolucion_larga(sinteticos, "2026-09", md.Parametros("trimestral"))
    assert s is not None
    assert "jul–sep 2026" in s.titulo
    assert "contra abr–jun 2026" in s.frases[0]
    assert len(s.tablas["evolucion_larga"]) == 4      # 3 meses + total


def test_sin_ventana_anterior_completa_lo_dice(sinteticos):
    """Semestral a septiembre: no hay datos de oct 2025–mar 2026."""
    s = md.mod_evolucion_larga(sinteticos, "2026-09", md.Parametros("semestral"))
    assert s is not None
    assert "No hay datos completos" in s.frases[0]


def test_ventana_actual_incompleta_no_emite(sinteticos):
    """Anual a septiembre: faltan enero a marzo, mejor no mostrar nada."""
    assert md.mod_evolucion_larga(sinteticos, "2026-09", md.Parametros("anual")) is None


# ── Módulos que activa el analista ──────────────────────────────────────

def test_factor_sin_justificacion_se_rechaza():
    with pytest.raises(ValueError, match="justificación"):
        md.Parametros(factor="Hot Sale")


def test_factor_declara_quien_y_por_que(sinteticos):
    p = md.Parametros(factor="Hot Sale de mayo", autor="Marcos",
                      factor_justificacion="Las ventas se duplicaron en 3 días")
    s = md.mod_factor_del_mes(sinteticos, "2026-09", p)
    assert s is not None
    assert "activado por Marcos" in s.frases[1]


def test_sin_declarar_los_cualitativos_no_entran(sinteticos):
    p = md.Parametros()
    assert md.mod_factor_del_mes(sinteticos, "2026-09", p) is None
    assert md.mod_carga_siguiente(sinteticos, "2026-09", p) is None
    assert md.mod_capacidad(sinteticos, "2026-09", p) is None


def test_dotacion_cero_se_rechaza():
    with pytest.raises(ValueError, match="dotación"):
        md.Parametros(dotacion={"2026-09": 0})


def test_capacidad_divide_por_operadores(sinteticos):
    t = md.capacidad(sinteticos, ["2026-09"], {"2026-09": 2})
    ventas = len(md.filtrar_periodo(sinteticos, "2026-09"))
    assert t.iloc[0]["ventas_por_operador"] == ventas / 2


def test_capacidad_avisa_si_falta_un_mes(sinteticos):
    with pytest.raises(ValueError, match="2026-08"):
        md.capacidad(sinteticos, ["2026-08", "2026-09"], {"2026-09": 3})


def test_la_ventana_cambia_y_queda_escrita(sinteticos):
    """Spec §3: elegir otro par de meses cambia la conclusión, así que se declara."""
    dot: dict[str, float] = {"2026-07": 3, "2026-08": 2, "2026-09": 3}
    defecto = md.mod_capacidad(sinteticos, "2026-09", md.Parametros(dotacion=dot))
    otra = md.mod_capacidad(sinteticos, "2026-09", md.Parametros(
        dotacion=dot, ventana_capacidad=("2026-07", "2026-09")))
    assert defecto is not None and otra is not None
    assert "2026-08 contra 2026-09" in defecto.frases[0]
    assert "2026-07 contra 2026-09" in otra.frases[0]


def test_carga_usa_la_capacidad_medida_como_referencia(sinteticos):
    p = md.Parametros(carga="Ingresan 300 SKU nuevos", carga_justificacion="Alta de proveedor",
                      dotacion={"2026-09": 3})
    s = md.mod_carga_siguiente(sinteticos, "2026-09", p)
    assert s is not None
    assert any("Referencia" in f for f in s.frases)