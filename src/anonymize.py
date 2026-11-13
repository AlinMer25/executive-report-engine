"""
anonymize.py — Convierte resultados reales en resultados publicables.

El repositorio es público y los datos son de una empresa real. La política
está en docs/04-politica-de-anonimizacion.md y se resume así:

    Márgenes, variaciones y participaciones      → reales, sin tocar
    Operaciones y unidades                       → reales
    Facturación, ganancia, ticket                → índice base 100
    Costo de estructura                          → solo como ratio
    Proveedores                                  → pseudónimo con rubro
    Plataformas                                  → reales, son públicas
    Costo de compra por SKU                      → NUNCA se publica

El invariante que lo vuelve verificable: **ni un solo valor monetario
absoluto en ningún archivo publicado**. No es una intención, es una función
que falla el build.

Por qué indexar y no inventar: indexado, el crecimiento del canal es real y
comprobable; inventado, el análisis pierde todo su valor. Se publica la
trayectoria verdadera sin publicar la magnitud.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from . import config as cfg
from . import metrics as m

RUTA_PSEUDONIMOS = cfg.RAIZ / "config" / "pseudonyms_private.json"

# Columnas en pesos que no pueden sobrevivir a la anonimización.
COLUMNAS_MONETARIAS = [
    cfg.PRECIO_UNITARIO, cfg.MONTO, cfg.MONTO_SIN_IVA,
    cfg.COMISION_PESOS, cfg.COSTO_UNITARIO, cfg.COSTO_TOTAL,
    cfg.COSTO_SIN_IVA, cfg.IIBB, cfg.GANANCIA_BRUTA,
    cfg.PAGO_ENVIO, cfg.COSTO_ENVIO,
    cfg.DIFERENCIA_ENVIO, cfg.DIFERENCIA_ENVIO_SIN_IVA, cfg.GANANCIA_NETA,
    m.C_BASE, m.C_COMISION, m.C_COSTO_SIN_IVA, m.C_IIBB,
    m.C_GANANCIA_BRUTA, m.C_DIF_ENVIO, m.C_DIF_ENVIO_RECALC, m.C_GANANCIA_NETA,
    "facturacion", "ganancia_neta", "ganancia_bruta", "ticket_promedio",
    "balance_envios", "costo_en_margen",
]

# Datos que no se publican de ninguna forma, ni indexados.
COLUMNAS_PROHIBIDAS = [cfg.CLIENTE_ID, cfg.COSTO_UNITARIO, cfg.COSTO_TOTAL]


# ──────────────────────────────────────────────────────────────────────
# Índice base 100
# ──────────────────────────────────────────────────────────────────────

def indexar(serie: pd.Series, valor_base: float | None = None) -> pd.Series:
    """Convierte una serie de pesos en un índice con base 100.

    Si no se indica el valor base, se usa el primer elemento de la serie.
    El índice conserva exactamente las proporciones: si la facturación se
    triplicó, el índice va de 100 a 300. Lo que se pierde es la magnitud,
    que es justamente lo confidencial.
    """
    if valor_base is None:
        valor_base = float(serie.iloc[0])
    if not valor_base:
        raise ValueError("El valor base del índice no puede ser cero.")
    return (serie / valor_base * 100).round(1)


def indexar_tabla(tabla: pd.DataFrame, fila_base: str | int | None = None
                  ) -> pd.DataFrame:
    """Indexa todas las columnas monetarias de una tabla de serie temporal.

    fila_base : etiqueta de la fila que vale 100. Por defecto, la primera.
    Cada columna se indexa contra su propio valor en esa fila, de modo que
    todas arrancan en 100 y después divergen según su trayectoria real.
    """
    t = tabla.copy()
    for col in t.columns:
        if col in COLUMNAS_MONETARIAS and pd.api.types.is_numeric_dtype(t[col]):
            # .to_numpy(dtype=float) convierte la columna en un arreglo de
            # decimales. Así el tipo queda definido y el verificador sabe
            # que la base es un número, no "cualquier cosa".
            valores = t[col].to_numpy(dtype=float)
            posicion = 0 if fila_base is None else t.index.get_loc(fila_base)
            t[col] = indexar(t[col], float(valores[posicion]))
            t = t.rename(columns={col: f"{col}_idx"})
    return t


# ──────────────────────────────────────────────────────────────────────
# Pseudónimos
# ──────────────────────────────────────────────────────────────────────

def cargar_mapa(ruta: Path = RUTA_PSEUDONIMOS) -> dict:
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {}


def guardar_mapa(mapa: dict, ruta: Path = RUTA_PSEUDONIMOS) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(mapa, indent=2, ensure_ascii=False),
                    encoding="utf-8")


def asignar_pseudonimos(nombres, rubros: dict | None = None,
                        ruta: Path = RUTA_PSEUDONIMOS) -> dict:
    """Asigna una letra estable a cada proveedor y la deja guardada.

    La estabilidad es el punto: el Proveedor A de abril tiene que seguir
    siendo el Proveedor A en septiembre, o las comparaciones entre informes
    dejan de significar algo. Por eso el mapa se persiste y solo se le
    agregan nombres nuevos, nunca se reasigna.

    El rubro se conserva —"Proveedor A (línea blanca)"— porque es lo que le
    da sentido analítico a la comparación. Un proveedor sin rubro es una
    letra sin información.

    El archivo vive en config/pseudonyms_private.json y está en .gitignore:
    es la única pieza que permitiría revertir la anonimización.
    """
    mapa = cargar_mapa(ruta)
    rubros = rubros or {}

    # El orden alfabético hace la asignación reproducible: dos corridas
    # sobre los mismos datos dan el mismo mapa.
    for nombre in sorted(set(str(n) for n in nombres if pd.notna(n))):
        if nombre in mapa:
            continue
        letra = _siguiente_letra(len(mapa))
        rubro = rubros.get(nombre)
        mapa[nombre] = f"Proveedor {letra} ({rubro})" if rubro else f"Proveedor {letra}"

    guardar_mapa(mapa, ruta)
    return mapa


def _siguiente_letra(n: int) -> str:
    """A, B, ... Z, AA, AB, ... Igual que las columnas de una planilla."""
    letras = ""
    n += 1
    while n:
        n, resto = divmod(n - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def pseudonimizar(serie: pd.Series, mapa: dict) -> pd.Series:
    """Reemplaza nombres por sus pseudónimos. Lo no mapeado queda 'Otros'."""
    return serie.map(lambda x: mapa.get(str(x), "Otros"))


# ──────────────────────────────────────────────────────────────────────
# El invariante
# ──────────────────────────────────────────────────────────────────────

# Un símbolo de peso seguido de dígitos, con o sin separadores.
PATRON_MONTO = re.compile(r"\$\s?-?\d[\d.,]*")

# Un número grande suelto, sin símbolo. El umbral deja pasar años (2026),
# índices (1.443,7) y porcentajes, y atrapa cifras de facturación.
PATRON_NUMERO_GRANDE = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d{3}){2,}(?![\d])")


def buscar_montos(texto: str) -> list[str]:
    """Devuelve los valores monetarios absolutos encontrados en un texto.

    Lista vacía significa que el texto cumple el invariante. Se usa sobre
    cualquier archivo que vaya a publicarse: documentos, markdown, CSV.
    """
    return PATRON_MONTO.findall(texto) + PATRON_NUMERO_GRANDE.findall(texto)


def columnas_monetarias_en(tabla: pd.DataFrame) -> list[str]:
    """Columnas en pesos que sobrevivieron a la anonimización.

    Comprobación estructural, complementaria a la de texto: una columna
    llamada 'facturacion' no debería existir en un dataset publicable,
    aunque ninguno de sus valores lleve símbolo de peso.
    """
    return [c for c in tabla.columns if c in COLUMNAS_MONETARIAS]


def verificar_publicable(objeto, nombre: str = "el objeto") -> None:
    """Falla si lo que se le pasa no cumple el invariante monetario.

    Pensada para correr sobre cada archivo antes de publicarlo. Levanta
    una excepción en vez de advertir: el invariante no admite excepciones,
    y una advertencia que se puede ignorar no es una garantía.
    """
    problemas = []

    if isinstance(objeto, pd.DataFrame):
        monetarias = columnas_monetarias_en(objeto)
        if monetarias:
            problemas.append(f"columnas en pesos: {', '.join(monetarias)}")
        prohibidas = [c for c in objeto.columns if c in COLUMNAS_PROHIBIDAS]
        if prohibidas:
            problemas.append(f"columnas prohibidas: {', '.join(prohibidas)}")
        texto = objeto.to_csv(index=False)
    else:
        texto = str(objeto)

    montos = buscar_montos(texto)
    if montos:
        muestra = ", ".join(montos[:5])
        problemas.append(f"{len(montos)} valores monetarios, p. ej.: {muestra}")

    if problemas:
        raise ValueError(
            f"{nombre} no cumple el invariante monetario:\n  - "
            + "\n  - ".join(problemas)
        )


def verificar_archivo(ruta: Path) -> None:
    """Aplica el invariante a un archivo de texto ya escrito."""
    verificar_publicable(Path(ruta).read_text(encoding="utf-8"), str(ruta))


# ──────────────────────────────────────────────────────────────────────
# Transformación completa
# ──────────────────────────────────────────────────────────────────────

def anonimizar_serie_mensual(serie: pd.DataFrame, mes_base: str | None = None
                             ) -> pd.DataFrame:
    """Prepara la serie mensual del canal para publicación.

    Indexa las columnas en pesos y deja intactas las reales: operaciones,
    unidades, márgenes y variaciones.
    """
    t = indexar_tabla(serie, fila_base=mes_base)
    verificar_publicable(t, "la serie mensual")
    return t


def anonimizar_por_proveedor(tabla: pd.DataFrame, rubros: dict | None = None
                             ) -> pd.DataFrame:
    """Prepara una tabla por proveedor para publicación.

    Pseudonimiza los nombres, indexa la facturación contra el total de la
    tabla —de modo que el proveedor más grande sea legible en proporción—
    y conserva el margen y la participación, que son reales.
    """
    t = tabla.copy()
    mapa = asignar_pseudonimos(t.index, rubros)
    t.index = pd.Index([mapa.get(str(i), "Otros") for i in t.index],
                       name=t.index.name)

    if "facturacion" in t.columns:
        total = t["facturacion"].sum()
        t["facturacion_idx"] = (t["facturacion"] / total * 100).round(1)
        t = t.drop(columns=["facturacion"])
    for col in ("ganancia_neta", "balance_envios", "costo_en_margen"):
        if col in t.columns:
            t = t.drop(columns=[col])

    verificar_publicable(t, "la tabla por proveedor")
    return t