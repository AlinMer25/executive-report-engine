"""
config.py — El contrato del motor con sus datos de entrada.

Todo nombre de columna, valor esperado y umbral del sistema vive acá y en
ningún otro lado. Si la planilla cambia un encabezado o el spec cambia un
umbral, se toca este archivo y nada más.

Referencias:
    docs/02-spec-del-modelo.md        parámetros y umbrales
    docs/03-diccionario-de-metricas.md   definición de cada métrica
"""

from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# Rutas del proyecto
# ──────────────────────────────────────────────────────────────────────

# __file__ es la ruta de este archivo. .parent sube un nivel (src/),
# .parent otra vez llega a la raíz del repo. Así las rutas funcionan
# sin importar desde qué carpeta se ejecute el programa.
RAIZ = Path(__file__).parent.parent

DIR_CRUDO = RAIZ / "data" / "raw"       # datos reales — nunca se commitean
DIR_MUESTRA = RAIZ / "data" / "sample"  # dataset sintético — sí se commitea
DIR_SALIDA = RAIZ / "output"            # informes generados — no se commitean

HOJA_VENTAS = "Ventas26"
HOJA_COSTOS = "Costos"
HOJA_FINANCIACION = "Financiacion"


# ──────────────────────────────────────────────────────────────────────
# Nombres de columna de la hoja de ventas
# ──────────────────────────────────────────────────────────────────────
# Se leen POR NOMBRE, nunca por letra ni por posición.
#
# Motivo: el diccionario de métricas documentaba las columnas por letra y,
# al insertarse columnas nuevas en la planilla, las letras se corrieron
# entre 2 y 5 posiciones según el caso. Un programa atado a letras habría
# seguido corriendo y devolviendo números equivocados, que es el peor modo
# de fallar. Atado a nombres, si una columna falta el programa se detiene
# y lo dice.

MES = "Mes"
FECHA = "Fecha"
CANTIDAD = "Cantidad"
CLIENTE_ID = "Nro de Cliente"

EMPRESA = "Empresa"
REGIMEN = "Facturación"          # "Blanco" o "Negro"
PLATAFORMA = "Plataforma"
METODO_ENVIO = "Metodo de Envio"
FINANCIACION = "Financiacion"
CANAL = "Canal"                  # "Canal Verde" o "Stock Verde"

SKU = "SKU"
PRODUCTO = "Producto"
SUBCATEGORIA_1 = "Sub-Categoria1"
SUBCATEGORIA = "SubCategoria"
CATEGORIA = "Categoria"
PROVEEDOR = "Proveedor"

IVA = "IVA"                      # 10.5 o 21
CALCULO_IVA = "Calculo IVA"      # 1.105 o 1.21

PRECIO_UNITARIO = "Precio Unitario"
MONTO = "Monto por Venta"             # con IVA — base de cálculo en Negro
MONTO_SIN_IVA = "Monto por Venta Sin Iva"   # base de cálculo en Blanco

COMISION_PCT = "Comision % x Venta"
COMISION_PESOS = "Comision alicuota"

COSTO_UNITARIO = "Costo Unitario"
COSTO_TOTAL = "Costo Total de producto x cant vendida"
COSTO_SIN_IVA = "Costo sin iva"

IIBB = "IIBB"
GANANCIA_BRUTA = "Ganancia de Venta Bruta"
MARGEN_BRUTO = "Margen Bruto"

PAGO_ENVIO = "Pago x Envio "      # ojo: el encabezado real termina en espacio
COSTO_ENVIO = "Costo de Envio Real"
DIFERENCIA_ENVIO = "Diferencia Envio"
DIFERENCIA_ENVIO_SIN_IVA = "Diferencia de envio sin IVA"

GANANCIA_NETA = "Ganancia Neta post costo de envio"
MARGEN_NETO = "Margen Neto de Venta"


# Columnas sin las cuales el motor no puede calcular nada.
# Si alguna falta, la carga falla de entrada con un mensaje claro
# en vez de producir resultados incompletos en silencio.
COLUMNAS_REQUERIDAS = [
    MES, FECHA, CANTIDAD, REGIMEN, PLATAFORMA, CANAL,
    PRODUCTO, CATEGORIA, PROVEEDOR,
    MONTO, MONTO_SIN_IVA, GANANCIA_NETA, DIFERENCIA_ENVIO,
]


# ──────────────────────────────────────────────────────────────────────
# Valores admitidos
# ──────────────────────────────────────────────────────────────────────

REGIMEN_BLANCO = "Blanco"
REGIMEN_NEGRO = "Negro"

CANAL_VERDE = "Canal Verde"
STOCK_VERDE = "Stock Verde"

# Códigos de empresa que determinan el régimen fiscal.
# Es la bifurcación que gobierna TODO el cálculo: en Blanco se descuenta
# IVA e IIBB, en Negro no.
EMPRESAS_BLANCO = {0, 500}
EMPRESAS_NEGRO = {10, 510}

TASA_IIBB = 0.04      # 4%, solo en ventas Blanco
IVA_ENVIO = 1.21      # el flete siempre tributa 21%, sea cual sea el producto


# ──────────────────────────────────────────────────────────────────────
# Umbrales del spec
# ──────────────────────────────────────────────────────────────────────
# Cambiar un número acá cambia cuándo suena una alarma en todo el sistema.
# Cada valor está justificado en docs/02-spec-del-modelo.md.

PISO_MARGEN_ALARMA_1 = 23.0   # callout obligatorio
PISO_MARGEN_ALARMA_2 = 20.0   # alerta severa
PISO_MARGEN_OBJETIVO = 26.0   # nivel de recuperación declarado
MESES_TENDENCIA_ALARMA = 3    # caídas consecutivas que disparan alerta

UMBRAL_LOGISTICA = 0.0025     # 0,25% de la facturación
UMBRAL_DISPERSION_SEMANAL = 1.5   # semana pico / semana valle

MES_BASE_INDICE = "2026-04"   # abril 2026 = 100


# ──────────────────────────────────────────────────────────────────────
# Reglas de validación — docs/03, hoja "Validaciones"
# ──────────────────────────────────────────────────────────────────────

MARGEN_NETO_MIN = -0.20   # −20%
MARGEN_NETO_MAX = 0.45    # +45%
MARGEN_BRUTO_MAX = 0.45
COMISION_PCT_MAX = 45.0
FUGA_ENVIO_ALERTA = -50_000   # en pesos, por operación
