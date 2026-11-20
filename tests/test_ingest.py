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


def test_decide_el_formato_por_columna_no_por_valor():
    """El caso que rompió al parser anterior: el factor de IVA 1.105.

    Mirando ese valor solo, '1.105' puede ser mil ciento cinco (formato
    argentino) o uno coma ciento cinco (estándar), y las dos lecturas son
    defendibles. Mirando la columna entera no hay ambigüedad.
    """
    estandar = a_numero(pd.Series(["1.105", "1.21", "1.105"]))
    assert estandar.tolist() == [1.105, 1.21, 1.105]

    argentina = a_numero(pd.Series([" $399.999,00", "48.400,00", "1.105"]))
    assert argentina.tolist() == [399999.0, 48400.0, 1105.0]


def test_las_columnas_numericas_son_decimales():
    """Aunque todos los valores sean enteros.

    Si pandas elige tipo entero, después falla al guardar un decimal ahí
    —dividir el envío por 1,21 levanta un error— y el motor anda con un
    dataset y no con otro.
    """
    enteros = a_numero(pd.Series(["100", "200", "300"]))
    assert pd.api.types.is_float_dtype(enteros)


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


def test_encabezados_con_espacios_se_limpian(tmp_path, ventas_mixtas):
    """'Pago x Envio ' (con espacio al final) se lee como 'Pago x Envio'."""
    from src.ingest import cargar_ventas
    sucio = ventas_mixtas.rename(columns=lambda c: f"{c} ")
    ruta = tmp_path / "sucio.xlsx"
    sucio.to_excel(ruta, sheet_name=cfg.HOJA_VENTAS, index=False)
    df = cargar_ventas(ruta)
    assert all(c == c.strip() for c in df.columns)


# ── La prueba de octubre: planilla descargada directo de Google Sheets ─────

def test_fechas_en_las_tres_formas_dan_el_mismo_mes():
    """dayfirst=True leía '2026-10-03' como 10 de marzo y '2026-10-25' como nada."""
    from src.ingest import a_fecha
    textos = pd.Series(["03/10/2026", "2026-10-03 00:00:00", "2026-10-25"], dtype=object)
    assert list(a_fecha(textos).dt.strftime("%Y-%m-%d")) == \
        ["2026-10-03", "2026-10-03", "2026-10-25"]
    nativas = pd.Series(pd.to_datetime(["2026-10-03"]))
    assert a_fecha(nativas).iloc[0].day == 3          # una fecha de verdad pasa intacta


def test_numeros_nativos_mezclados_con_texto():
    """Un solo '1,21' tipeado a mano volvía 1105 a todo el resto de la columna."""
    from src.ingest import a_numero
    mezcla = pd.Series([1.105, 1.21, "1,21", 310800.0, " $399.999,00"], dtype=object)
    assert list(a_numero(mezcla)) == [1.105, 1.21, 1.21, 310800.0, 399999.0]


def test_planilla_nativa_da_lo_mismo_que_la_de_texto(tmp_path):
    """La misma planilla, guardada como texto o con celdas nativas, tiene
    que dar exactamente las mismas ventas y la misma ganancia."""
    from src import metrics as m
    from src import sample_data as sd
    from src.ingest import cargar_ventas
    from src.sections import filtrar_periodo

    texto = sd.generar()
    nativa = texto.copy()
    nativa[cfg.FECHA] = pd.to_datetime(nativa[cfg.FECHA], format="%d/%m/%Y")
    nativa[cfg.CALCULO_IVA] = nativa[cfg.CALCULO_IVA].astype(object)
    nativa.loc[nativa.index[0], cfg.CALCULO_IVA] = "1,21" if \
        nativa[cfg.CALCULO_IVA].iloc[0] == 1.21 else "1,105"   # una celda tipeada a mano

    for nombre, df in (("texto", texto), ("nativa", nativa)):
        df.to_excel(tmp_path / f"{nombre}.xlsx", sheet_name=cfg.HOJA_VENTAS, index=False)
    a = filtrar_periodo(cargar_ventas(tmp_path / "texto.xlsx"), "2026-09")
    b = filtrar_periodo(cargar_ventas(tmp_path / "nativa.xlsx"), "2026-09")
    assert len(a) == len(b)
    assert m.resumen(a)["ganancia_neta"] == pytest.approx(m.resumen(b)["ganancia_neta"])