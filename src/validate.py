"""
validate.py — Las reglas de calidad de datos del diccionario, en código.

El diccionario de métricas define doce reglas que marcan una fila como
"revisar". Hasta ahora se aplicaban a ojo. Acá corren solas sobre cada carga.

El origen de todas ellas es un caso real: en el informe de mayo, una heladera
figuró con 74% de margen por un costo mal cargado. Se detectó a mano, de
casualidad. La regla 1 existe para que eso no dependa de la suerte.

Cada regla devuelve las filas que la incumplen, con su severidad. Ninguna
corrige nada por su cuenta: marcar es automático, decidir es de la persona.

Referencia: docs/03-diccionario-de-metricas.md, hoja "Validaciones"
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config as cfg
from . import metrics as m

ALTA, MEDIA, BAJA = "alta", "media", "baja"


@dataclass
class Hallazgo:
    """Resultado de una regla sobre un conjunto de datos."""
    id: str
    nombre: str
    severidad: str
    accion: str
    filas: pd.DataFrame = field(repr=False)

    @property
    def cantidad(self) -> int:
        return len(self.filas)


# ──────────────────────────────────────────────────────────────────────
# Las reglas
# ──────────────────────────────────────────────────────────────────────
# Cada una recibe el DataFrame ya calculado y devuelve una máscara booleana:
# una serie de Verdadero/Falso del mismo largo, con Verdadero en las filas
# que incumplen. Es la forma de pandas de decir "estas filas".

def _r01_margen_neto_fuera_de_rango(d):
    return (d[m.C_MARGEN_NETO] < cfg.MARGEN_NETO_MIN) | (d[m.C_MARGEN_NETO] > cfg.MARGEN_NETO_MAX)

def _r02_margen_bruto_implausible(d):
    return d[m.C_MARGEN_BRUTO] > cfg.MARGEN_BRUTO_MAX

def _r03_ganancia_sin_margen(d):
    return (d[m.C_GANANCIA_NETA] > 0) & (d[m.C_MARGEN_NETO] == 0)

def _r04_monto_vacio(d):
    return d[cfg.MONTO].isna() | (d[cfg.MONTO] <= 0)

def _r05_costo_mayor_que_ingreso(d):
    return d[m.C_COSTO_SIN_IVA] > (d[m.C_BASE] - d[m.C_COMISION])

def _r06_mes_no_coincide_con_fecha(d):
    fecha = pd.to_datetime(d[cfg.FECHA], dayfirst=True, errors="coerce")
    meses = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",7:"Julio",
             8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
    real = fecha.dt.month.map(meses)
    return real.notna() & (real != d[cfg.MES])

def _r07_fuga_de_flete_alta(d):
    return d[m.C_DIF_ENVIO] < cfg.FUGA_ENVIO_ALERTA

def _r08_cliente_sin_id(d):
    if cfg.CLIENTE_ID not in d.columns:
        return pd.Series(False, index=d.index)
    c = d[cfg.CLIENTE_ID].astype("string").str.strip()
    return c.isna() | (c == "")

def _r09_producto_sin_categoria(d):
    c = d[cfg.CATEGORIA].astype("string").str.strip()
    return c.isna() | (c == "")

def _r10_venta_cancelada(d):
    # El diccionario pide excluir Devoluciones y Notas de Crédito, pero la
    # planilla no tiene una columna de tipo de comprobante: las canceladas se
    # depuran a mano antes de analizar. La regla queda declarada y sin
    # implementar, que es más honesto que fingir que se verifica.
    return pd.Series(False, index=d.index)

def _r11_duplicado_exacto(d):
    claves = [c for c in (cfg.FECHA, cfg.CLIENTE_ID, cfg.SKU, cfg.MONTO) if c in d.columns]
    return d.duplicated(subset=claves, keep=False) & d[cfg.MONTO].notna()

def _r12_comision_fuera_de_rango(d):
    return (d[cfg.COMISION_PCT] < 0) | (d[cfg.COMISION_PCT] > cfg.COMISION_PCT_MAX)

# Reglas 13 y 14: no están en el diccionario original. Nacen de problemas
# detectados al perfilar los datos el 31/10/2026.

def _r13_envio_no_derivable(d):
    """La diferencia de envío no se deriva de sus propios insumos.

    Marca las filas donde 'Pago x Envío' se completó copiando el costo. El
    valor de 'Diferencia Envío' es el correcto; el insumo es el contaminado.
    """
    if m.C_DIF_ENVIO_RECALC not in d.columns:
        return pd.Series(False, index=d.index)
    return (d[m.C_DIF_ENVIO_RECALC] - d[cfg.DIFERENCIA_ENVIO]).abs() > 1

def _r14_sin_canal(d):
    c = d[cfg.CANAL].astype("string").str.strip()
    return c.isna() | (c == "")


REGLAS = [
    ("R01", "Margen neto fuera de rango", ALTA,
     "Revisar la carga de costo o precio. Es el caso de la heladera.",
     _r01_margen_neto_fuera_de_rango),
    ("R02", "Margen bruto implausible", MEDIA,
     "Verificar el costo unitario cargado.", _r02_margen_bruto_implausible),
    ("R03", "Ganancia positiva con margen cero", MEDIA,
     "Posible división por cero o monto vacío.", _r03_ganancia_sin_margen),
    ("R04", "Monto vacío o cero", ALTA,
     "Venta sin ingreso: excluir o corregir.", _r04_monto_vacio),
    ("R05", "Costo mayor que el ingreso neto de comisión", MEDIA,
     "Venta a pérdida: confirmar si es real o un error de carga.",
     _r05_costo_mayor_que_ingreso),
    ("R06", "Mes declarado distinto del mes de la fecha", MEDIA,
     "Corregir la etiqueta de mes.", _r06_mes_no_coincide_con_fecha),
    ("R07", "Pérdida de flete elevada", BAJA,
     "Normal pero conviene monitorear.", _r07_fuga_de_flete_alta),
    ("R08", "Cliente sin identificador", BAJA,
     "Completar por cruce. Tarea de mantenimiento.", _r08_cliente_sin_id),
    ("R09", "Producto sin categoría", MEDIA,
     "Asignar categoría para no perder la fila en los agrupamientos.",
     _r09_producto_sin_categoria),
    ("R10", "Venta cancelada mezclada", ALTA,
     "SIN IMPLEMENTAR: la planilla no registra el tipo de comprobante.",
     _r10_venta_cancelada),
    ("R11", "Duplicado exacto", MEDIA,
     "Verificar doble carga de la misma venta.", _r11_duplicado_exacto),
    ("R12", "Comisión fuera de rango", MEDIA,
     "Verificar; las comisiones típicas van de 5% a 20%, más con cuotas.",
     _r12_comision_fuera_de_rango),
    ("R13", "Diferencia de envío no derivable de sus insumos", MEDIA,
     "'Pago x Envío' se completó copiando el costo. Ver el instructivo de reparación.",
     _r13_envio_no_derivable),
    ("R14", "Operación sin canal asignado", MEDIA,
     "Completar con Canal Verde o Stock Verde.", _r14_sin_canal),
]


# ──────────────────────────────────────────────────────────────────────
# Ejecución
# ──────────────────────────────────────────────────────────────────────

def validar(df: pd.DataFrame, columnas_muestra: list[str] | None = None
            ) -> list[Hallazgo]:
    """Corre todas las reglas y devuelve solo las que encontraron algo."""
    if m.C_MARGEN_NETO not in df.columns:
        df = m.calcular(df)

    if columnas_muestra is None:
        columnas_muestra = [c for c in (cfg.MES, cfg.FECHA, cfg.PLATAFORMA,
                                        cfg.PRODUCTO, cfg.MONTO, m.C_MARGEN_NETO)
                            if c in df.columns]

    hallazgos = []
    for id_, nombre, sev, accion, regla in REGLAS:
        try:
            mascara = regla(df).fillna(False)
        except KeyError:
            continue  # la columna no está en este dataset: la regla no aplica
        if mascara.any():
            hallazgos.append(Hallazgo(id_, nombre, sev, accion,
                                      df.loc[mascara, columnas_muestra]))
    return hallazgos


def informe(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla resumen de la validación, ordenada por severidad."""
    orden = {ALTA: 0, MEDIA: 1, BAJA: 2}
    filas = [{
        "regla": h.id, "severidad": h.severidad, "filas": h.cantidad,
        "%": round(h.cantidad / len(df) * 100, 2),
        "descripcion": h.nombre, "accion": h.accion,
    } for h in validar(df)]

    if not filas:
        return pd.DataFrame(columns=["regla","severidad","filas","%",
                                     "descripcion","accion"])
    t = pd.DataFrame(filas)
    return t.sort_values(["severidad", "filas"],
                         key=lambda s: s.map(orden) if s.name == "severidad" else -s,
                         ).reset_index(drop=True)


def hay_bloqueantes(df: pd.DataFrame) -> bool:
    """Verdadero si hay hallazgos de severidad alta.

    Pensado para que el generador de informes se detenga antes de producir
    un documento sobre datos que ya se sabe que están mal.
    """
    return any(h.severidad == ALTA for h in validar(df))