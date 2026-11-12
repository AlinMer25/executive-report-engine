"""
sample_data.py — Genera el dataset sintético que se publica en el repositorio.

Sin esto, el repositorio sería código que nadie puede ejecutar: los datos
reales no se publican y el motor sin datos no demuestra nada.

El dataset reproduce la **estructura** y los **órdenes de magnitud relativos**
del caso real —mezcla de regímenes fiscales, crecimiento mensual, efecto del
envío gratis, dispersión de márgenes por categoría— pero ninguno de sus
valores. Es un caso verosímil, no un caso real disfrazado.

Está generado con semilla fija, así que dos corridas producen exactamente el
mismo archivo. Eso lo vuelve parte reproducible del repositorio y no un
artefacto que cambia cada vez que alguien lo regenera.

Uso:
    python -m src.sample_data
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg

SEMILLA = 2026

# Proporciones tomadas del caso real. Son las que hacen que el dataset
# ejercite los mismos caminos del código: la bifurcación fiscal, el filtro
# de canal, el efecto del envío gratis.
PROPORCION_NEGRO = 0.91
PROPORCION_STOCK_VERDE = 0.31
PROPORCION_ENVIO_GRATIS = 0.23

# Operaciones por mes: la trayectoria de crecimiento del caso real.
OPERACIONES_POR_MES = {
    "Abril": 104, "Mayo": 256, "Junio": 249,
    "Julio": 347, "Agosto": 555, "Septiembre": 784,
}

PLATAFORMAS = [
    ("Fravega", 0.20, False), ("BNA", 0.14, False), ("ICBC", 0.11, False),
    ("Provincia Compras", 0.10, False), ("Carrefour", 0.06, False),
    ("Macro", 0.05, False), ("Bigote", 0.11, True), ("Demelf", 0.07, True),
    ("Macro Env. Gratis", 0.06, True), ("Provincia Env. Gratis", 0.05, True),
    ("BNA Env. Gratis", 0.05, True),
]

# (categoría, ticket típico, margen típico, desvío del margen)
CATEGORIAS = [
    ("Cocción",                     420_000, 0.238, 0.05),
    ("Tecnologia",                1_600_000, 0.252, 0.06),
    ("Electrodomésticos",           560_000, 0.186, 0.06),
    ("Pequeños Electro",             70_000, 0.205, 0.09),
    ("Muebles",                     310_000, 0.262, 0.07),
    ("Herramientas y Construcción", 160_000, 0.318, 0.06),
    ("Climatización",               480_000, 0.272, 0.06),
    ("Aire Libre",                  240_000, 0.281, 0.08),
]

PROVEEDORES = {
    "Cocción": "Proveedor A (línea blanca)",
    "Tecnologia": "Proveedor B (tecnología)",
    "Electrodomésticos": "Proveedor C (electro)",
    "Pequeños Electro": "Proveedor D (pequeños electro)",
    "Muebles": "Proveedor E (muebles)",
    "Herramientas y Construcción": "Proveedor F (pinturería)",
    "Climatización": "Proveedor G (climatización)",
    "Aire Libre": "Proveedor H (aire libre)",
}

METODOS_ENVIO = ["Flex", "FvG Envios", "Mercadoenvios", "Transporte", "Correo PickIt"]


def generar(semilla: int = SEMILLA) -> pd.DataFrame:
    """Construye el dataset sintético completo."""
    rng = np.random.default_rng(semilla)
    filas = []
    numero_mes = {"Abril": 4, "Mayo": 5, "Junio": 6,
                  "Julio": 7, "Agosto": 8, "Septiembre": 9}

    pesos_plataforma = np.array([p[1] for p in PLATAFORMAS])
    pesos_plataforma = pesos_plataforma / pesos_plataforma.sum()

    for mes, cantidad in OPERACIONES_POR_MES.items():
        for _ in range(cantidad):
            cat, ticket_tipico, margen_tipico, desvio = CATEGORIAS[
                rng.integers(len(CATEGORIAS))]
            i_plat = rng.choice(len(PLATAFORMAS), p=pesos_plataforma)
            plataforma, _, es_envio_gratis = PLATAFORMAS[i_plat]

            es_negro = rng.random() < PROPORCION_NEGRO
            regimen = cfg.REGIMEN_NEGRO if es_negro else cfg.REGIMEN_BLANCO
            alicuota = 10.5 if cat == "Cocción" else 21.0
            factor_iva = 1 + alicuota / 100

            cantidad_vendida = 1 if rng.random() < 0.93 else 2
            monto = float(np.round(
                rng.lognormal(np.log(ticket_tipico), 0.45) * cantidad_vendida, 2))
            monto_sin_iva = round(monto / factor_iva, 2)
            base = monto if es_negro else monto_sin_iva

            # El envío gratis deprime el margen: el flete está en el precio
            # pero no siempre alcanza a cubrirlo. Es el fenómeno que el
            # motor tiene que poder detectar sobre este dataset.
            margen_objetivo = margen_tipico + rng.normal(0, desvio)
            if es_envio_gratis:
                margen_objetivo -= 0.045

            comision_pct = float(np.round(rng.uniform(8, 22), 2))
            comision = round(monto * comision_pct / 100, 2)
            iibb = round(base * cfg.TASA_IIBB, 2) if not es_negro else 0.0

            costo_envio = float(np.round(
                rng.uniform(0.02, 0.06) * min(monto, 900_000), 2))
            pago_envio = 0.0 if es_envio_gratis else round(
                costo_envio * rng.uniform(0.6, 1.3), 2)
            dif_envio = round(pago_envio - costo_envio, 2)
            envio_aplicado = dif_envio if not es_negro else dif_envio / cfg.IVA_ENVIO

            # Se despeja el costo para que la fila alcance el margen buscado.
            ganancia_neta = round(base * margen_objetivo, 2)
            ganancia_bruta = round(ganancia_neta - envio_aplicado, 2)
            costo_sin_iva = round(base - iibb - comision - ganancia_bruta, 2)
            costo_total = round(costo_sin_iva * factor_iva, 2)

            dia = int(rng.integers(1, 29))
            filas.append({
                cfg.MES: mes,
                cfg.FECHA: f"{dia:02d}/{numero_mes[mes]:02d}/2026",
                cfg.CANTIDAD: cantidad_vendida,
                cfg.CLIENTE_ID: f"{rng.integers(100000, 999999)}",
                cfg.SKU: f"SKU{rng.integers(1000, 9999)}",
                cfg.PRODUCTO: f"{cat} modelo {rng.integers(100, 999)}",
                cfg.REGIMEN: regimen,
                cfg.PLATAFORMA: plataforma,
                cfg.METODO_ENVIO: METODOS_ENVIO[rng.integers(len(METODOS_ENVIO))],
                cfg.CANAL: (cfg.STOCK_VERDE if rng.random() < PROPORCION_STOCK_VERDE
                            else cfg.CANAL_VERDE),
                cfg.CATEGORIA: cat,
                cfg.SUBCATEGORIA: cat,
                cfg.SUBCATEGORIA_1: cat,
                cfg.PROVEEDOR: PROVEEDORES[cat],
                cfg.FINANCIACION: "Sin Financiación",
                cfg.IVA: alicuota,
                cfg.CALCULO_IVA: factor_iva,
                cfg.PRECIO_UNITARIO: round(monto / cantidad_vendida, 2),
                cfg.MONTO: monto,
                cfg.MONTO_SIN_IVA: monto_sin_iva,
                cfg.COMISION_PCT: comision_pct,
                cfg.COMISION_PESOS: comision,
                cfg.COSTO_UNITARIO: round(costo_total / cantidad_vendida, 2),
                cfg.COSTO_TOTAL: costo_total,
                cfg.COSTO_SIN_IVA: costo_sin_iva,
                cfg.IIBB: iibb,
                cfg.GANANCIA_BRUTA: ganancia_bruta,
                cfg.MARGEN_BRUTO: round(ganancia_bruta / base, 4),
                cfg.PAGO_ENVIO: pago_envio,
                cfg.COSTO_ENVIO: costo_envio,
                cfg.DIFERENCIA_ENVIO: dif_envio,
                cfg.DIFERENCIA_ENVIO_SIN_IVA: round(dif_envio / cfg.IVA_ENVIO, 2),
                cfg.GANANCIA_NETA: ganancia_neta,
                cfg.MARGEN_NETO: round(ganancia_neta / base, 4),
            })

    return pd.DataFrame(filas)


def escribir(ruta=None, semilla: int = SEMILLA):
    """Genera el dataset y lo escribe como .xlsx en data/sample/."""
    ruta = ruta or (cfg.DIR_MUESTRA / "ventas_sinteticas.xlsx")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df = generar(semilla)
    df.to_excel(ruta, sheet_name=cfg.HOJA_VENTAS, index=False)
    return ruta, df


if __name__ == "__main__":
    ruta, df = escribir()
    print(f"{len(df)} operaciones escritas en {ruta}")