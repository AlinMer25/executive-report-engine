"""
qa.py — Resumen y QA (artefacto A2 del spec, §8).

El A2 es la versión de una página que José lee antes de la reunión, más las
preguntas que probablemente haga y cómo responderlas.

Regla central (invariante I2): todo dato del A2 existe en el A1. Por eso este
archivo NO calcula métricas nuevas: toma las secciones que ya armó
sections.py y los mismos resúmenes de metrics.py, y los reorganiza.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import cast

import pandas as pd
from docx import Document
from docx.shared import Pt
from docx.styles.style import ParagraphStyle

from . import config as cfg
from . import metrics as m
from . import modules as md
from . import report as rp
from . import seguimiento as sg
from .sections import (Seccion, filtrar_periodo, nombre_periodo,
                       periodo_anterior, pct, pesos, porcentaje, pp, variacion)

COMPLETAR = "[Completar]"
UMBRAL_DEPENDENCIA = 40.0      # % de facturación de un solo proveedor
UMBRAL_CRECIMIENTO = 30.0      # % de crecimiento que pide "¿se sostiene?"
UMBRAL_TICKET_ESTABLE = 5.0    # % de variación del ticket considerada estable


@dataclass
class Pregunta:
    pregunta: str
    respuesta: str


@dataclass
class ResumenQA:
    periodo: str
    titular: str
    kpis: list[tuple[str, str, str]]          # (valor, nombre, variación)
    funciono: list[str]
    corregir: list[str]
    en_una_linea: str
    prioridades: list[str]
    seguimiento: pd.DataFrame | None
    productividad: pd.DataFrame | None
    preguntas: list[Pregunta]
    cierre: str
    corte: str = "trimestral"
    avisos: list[str] = field(default_factory=list)
    publico: bool = False


# ──────────────────────────────────────────────────────────────────────
# Piezas
# ──────────────────────────────────────────────────────────────────────

def _completar(lista: list[str], n: int) -> list[str]:
    """Exactamente n ítems: recorta o rellena con marcas para completar."""
    return (lista + [COMPLETAR] * n)[:n]


def tiene_cifra(texto: str) -> bool:
    """Invariante de §8.1: una respuesta sin dato es una opinión."""
    return bool(re.search(r"\d", texto))


def _primera_oracion(texto: str) -> str:
    return texto.split(". ")[0].rstrip(".") + "."


def proveedor_principal(actual: pd.DataFrame) -> tuple[str, float]:
    t = m.por_dimension(actual, cfg.PROVEEDOR)
    return str(t.index[0]), float(t["participacion"].iloc[0])


# ──────────────────────────────────────────────────────────────────────
# Preguntas (spec §8.1): cada una nace de un hecho del A1
# ──────────────────────────────────────────────────────────────────────

def generar_preguntas(r: dict, r_ant: dict, periodo: str, secciones: dict[str, Seccion],
                      prov: tuple[str, float], cerrados: list[str],
                      prioridades: list[str]) -> list[Pregunta]:
    mes, mes_ant = nombre_periodo(periodo), nombre_periodo(periodo_anterior(periodo))
    v_fact = variacion(r["facturacion"], r_ant["facturacion"])
    v_gan = variacion(r["ganancia_neta"], r_ant["ganancia_neta"])
    v_ventas = variacion(r["operaciones"], r_ant["operaciones"])
    v_ticket = variacion(r["ticket_promedio"], r_ant["ticket_promedio"])
    d_margen = r["margen_neto"] - r_ant["margen_neto"]

    P = [Pregunta(
        f"¿Cómo nos fue en {mes}?",
        f"Facturación {pesos(r['facturacion'])} ({pct(v_fact)}), ganancia neta "
        f"{pesos(r['ganancia_neta'])} ({pct(v_gan)}) y margen "
        f"{porcentaje(r['margen_neto'])} ({pp(d_margen)}). {COMPLETAR}: la razón "
        f"en una frase.")]

    if "mod.integridad" in secciones:
        s = secciones["mod.integridad"]
        P.append(Pregunta(
            "¿Por qué cambiaron las cifras del mes pasado?",
            f"Adelantate y explicalo vos: {s.frases[0]} {COMPLETAR}: el motivo."))

    if r["margen_neto"] < cfg.PISO_MARGEN_ALARMA_1:
        P.append(Pregunta(
            "¿Por qué bajó el margen?",
            f"Margen {porcentaje(r['margen_neto'])} ({pp(d_margen)}), debajo del "
            f"piso de {porcentaje(cfg.PISO_MARGEN_ALARMA_1)}. {COMPLETAR}: la causa."))

    if abs(v_ticket) < UMBRAL_TICKET_ESTABLE and d_margen < 0:
        P.append(Pregunta(
            "¿Vendimos más barato?",
            f"El ticket promedio casi no cambió ({pesos(r['ticket_promedio'])}, "
            f"{pct(v_ticket)}) pero el margen cayó {pp(d_margen)}: no fue precio "
            f"de venta, fue rentabilidad. {COMPLETAR}: dónde."))
    elif v_ventas < 0 < v_fact:
        P.append(Pregunta(
            "¿Vendimos menos?",
            f"En cantidad sí ({r['operaciones']} ventas, {pct(v_ventas)}); en valor "
            f"no: el ticket promedio subió a {pesos(r['ticket_promedio'])} "
            f"({pct(v_ticket)})."))

    if v_fact > UMBRAL_CRECIMIENTO:
        P.append(Pregunta(
            "¿Esto se sostiene o fue puntual?",
            f"La facturación creció {pct(v_fact)}. {COMPLETAR}: qué parte es "
            f"estructural y qué parte es del período."))

    nombre, part = prov
    if part > UMBRAL_DEPENDENCIA:
        P.append(Pregunta(
            f"¿No dependemos demasiado de {nombre}?",
            f"Sí, y decilo con el número: {nombre} es el "
            f"{porcentaje(part, 1)} de la facturación. {COMPLETAR}: el plan para "
            f"diversificar."))

    if "mod.logistica" in secciones:
        P.append(Pregunta("¿Dónde estamos perdiendo margen?",
                          secciones["mod.logistica"].frases[0]))

    if "mod.evolucion" in secciones:
        P.append(Pregunta("¿Por qué el mes no fue parejo?",
                          secciones["mod.evolucion"].frases[0]))

    if "mod.capacidad" in secciones:
        s = secciones["mod.capacidad"]
        # Invariante de atribución: primero lo que NO es del equipo.
        P.append(Pregunta(
            "¿El equipo rinde o se está estirando?",
            f"Primero lo que no es del equipo: {COMPLETAR} (precio, catálogo, "
            f"promociones, disponibilidad de compra). Después lo que sí: "
            f"{s.frases[1]}"))

    seg = secciones.get("core.seguimiento")
    if seg is not None and "seguimiento" in seg.tablas:
        P.append(Pregunta(f"¿Qué pasó con lo que comprometimos en {mes_ant}?",
                          seg.frases[0]))

    for titulo in cerrados:                    # invariante I3
        P.append(Pregunta(f"¿Qué pasó con «{titulo}»?",
                          f"Salió del informe porque dejó de cumplir su condición "
                          f"de entrada en {mes}. {COMPLETAR}: si se resolvió o "
                          f"solo cambió de lugar."))

    P.append(Pregunta(
        f"¿Qué viene en {nombre_periodo(periodo_anterior(periodo, -1))}?",
        "Tres frentes: " + "; ".join(prioridades) + "."))

    return P[:12]


def modulos_cerrados(df: pd.DataFrame, periodo: str, params: md.Parametros,
                     actuales: set[str]) -> list[str]:
    """Módulos numéricos que estaban el período anterior y ya no (I3).

    Los cualitativos dependen de lo que declaraste ese mes, que el motor no
    guarda, así que solo se comparan los que se activan por dato.
    """
    numericos = {md.mod_integridad, md.mod_logistica, md.mod_evolucion,
                 md.mod_graduacion}
    anterior = periodo_anterior(periodo)
    if filtrar_periodo(df, anterior).empty:
        return []
    cerrados = []
    for modulo in md.MODULOS:
        if modulo not in numericos:
            continue
        s = modulo(df, anterior, params)
        if s is not None and s.id not in actuales:
            cerrados.append(s.titulo)
    return cerrados


# ──────────────────────────────────────────────────────────────────────
# Armado
# ──────────────────────────────────────────────────────────────────────

def construir(df: pd.DataFrame, periodo: str, secciones: list[Seccion],
              params: md.Parametros | None = None) -> ResumenQA:
    params = params or md.Parametros()
    por_id = {s.id: s for s in secciones}
    actual = m.calcular(filtrar_periodo(df, periodo))
    anterior = m.calcular(filtrar_periodo(df, periodo_anterior(periodo)))
    r, r_ant = m.resumen(actual), m.resumen(anterior)

    v_fact = variacion(r["facturacion"], r_ant["facturacion"])
    v_gan = variacion(r["ganancia_neta"], r_ant["ganancia_neta"])
    v_ventas = variacion(r["operaciones"], r_ant["operaciones"])
    v_ticket = variacion(r["ticket_promedio"], r_ant["ticket_promedio"])
    d_margen = r["margen_neto"] - r_ant["margen_neto"]
    mes, mes_ant = nombre_periodo(periodo), nombre_periodo(periodo_anterior(periodo))
    prov = proveedor_principal(actual)

    # ── qa.titular / qa.kpis
    titular = (f"Facturación {pesos(r['facturacion'])} ({pct(v_fact)}), ganancia "
               f"neta {pesos(r['ganancia_neta'])} ({pct(v_gan)}) y margen "
               f"{porcentaje(r['margen_neto'])} ({pp(d_margen)}). {COMPLETAR}: qué "
               f"lo explica y cuál es la alerta del mes.")
    kpis = [
        (pesos(r["facturacion"]), "Facturación", pct(v_fact)),
        (pesos(r["ganancia_neta"]), "Ganancia neta", pct(v_gan)),
        (porcentaje(r["margen_neto"]), "Margen neto", pp(d_margen)),
        (f"{r['operaciones']:,}".replace(",", "."), "Cantidad de ventas", pct(v_ventas)),
        (pesos(r["ticket_promedio"]), "Ticket promedio", pct(v_ticket)),
        (porcentaje(prov[1], 1), f"Participación de {prov[0]}", "proveedor principal"),
    ]

    # ── qa.balance: cada bullet sale de un dato que ya está en el A1
    hechos = [
        (v_fact, f"Facturación {pesos(r['facturacion'])} ({pct(v_fact)})"),
        (v_gan, f"Ganancia neta {pesos(r['ganancia_neta'])} ({pct(v_gan)})"),
        (d_margen, f"Margen {porcentaje(r['margen_neto'])} ({pp(d_margen)})"),
        (v_ticket, f"Ticket promedio {pesos(r['ticket_promedio'])} ({pct(v_ticket)})"),
        (v_ventas, f"{r['operaciones']} ventas ({pct(v_ventas)})"),
    ]
    funciono = [t for v, t in hechos if v > 0]
    corregir = [t for v, t in hechos if v < 0]
    for s in secciones:
        corregir += [_primera_oracion(a) for a in s.alertas]
    if "mod.logistica" in por_id:
        corregir.append(_primera_oracion(por_id["mod.logistica"].frases[0]))
    if prov[1] > UMBRAL_DEPENDENCIA:
        corregir.append(f"{prov[0]}: {porcentaje(prov[1], 1)} de la facturación")
    if "mod.integridad" in por_id:
        corregir.append(f"{mes_ant.capitalize()} reexpresado (ver nota de integridad)")

    # ── qa.periodo
    en_una_linea = (f"{mes_ant.capitalize()} ({pesos(r_ant['facturacion'])}; "
                    f"{porcentaje(r_ant['margen_neto'])}) → {mes} "
                    f"({pesos(r['facturacion'])}; {porcentaje(r['margen_neto'])}). "
                    f"{COMPLETAR}: la lectura en una frase.")

    # ── qa.prioridades: exactamente 3, desde core.recomendaciones
    recos = sg.cargar(periodo) or []
    prioridades = _completar([f"[{x['id']}] {x['texto']}" for x in recos], 3)

    # ── qa.seguimiento / qa.productividad: se reutilizan las tablas del A1
    seg = por_id.get("core.seguimiento")
    seguimiento = seg.tablas.get("seguimiento") if seg else None
    cap = por_id.get("mod.capacidad")
    productividad = cap.tablas.get("capacidad") if cap else None

    cerrados = modulos_cerrados(df, periodo, params, set(por_id))
    preguntas = generar_preguntas(r, r_ant, periodo, por_id, prov, cerrados, prioridades)

    avisos = []
    for i, p in enumerate(preguntas, start=1):
        if not tiene_cifra(p.respuesta):
            avisos.append(f"P{i} no tiene cifra en la respuesta: completala con un dato.")
    if len(preguntas) < 8:
        avisos.append(f"Hay {len(preguntas)} preguntas derivadas del informe (el spec "
                      f"pide 8 a 12): agregá las que falten a mano.")

    return ResumenQA(
        periodo=periodo, titular=titular, kpis=kpis,
        funciono=_completar(funciono, 5), corregir=_completar(corregir, 5),
        en_una_linea=en_una_linea, prioridades=prioridades,
        seguimiento=seguimiento, productividad=productividad,
        preguntas=preguntas,
        cierre=f"{COMPLETAR}: la historia de {mes} en una línea, y con qué abrir.",
        corte=params.corte, avisos=avisos,
    )


# ──────────────────────────────────────────────────────────────────────
# Escritura del .docx
# ──────────────────────────────────────────────────────────────────────

def escribir(qa: ResumenQA, ruta: Path) -> Path:
    doc = Document()
    estilo = cast(ParagraphStyle, doc.styles["Normal"])
    estilo.font.name, estilo.font.size = "Calibri", Pt(10)

    t = doc.add_paragraph().add_run(
        f"RESUMEN EJECUTIVO — VENTAS {nombre_periodo(qa.periodo).upper()}")
    t.font.size, t.font.bold, t.font.color.rgb = Pt(18), True, rp.VERDE
    version = " · versión pública: montos en unidades base" if qa.publico else ""
    meta = doc.add_paragraph().add_run(
        f"Canal Verde · corte {qa.corte} · generado el {date.today():%d/%m/%Y}{version}")
    meta.font.size, meta.font.italic = Pt(9), True

    rp._alerta(doc, f"El titular del mes. {qa.titular}")

    # Grid de 6 KPIs: 2 filas × 3 columnas
    grid = doc.add_table(rows=2, cols=3)
    grid.style = "Table Grid"
    for i, (valor, nombre, var) in enumerate(qa.kpis):
        celda = grid.rows[i // 3].cells[i % 3]
        rp._sombrear(celda, "F2F5F3")
        celda.text = ""
        p = celda.paragraphs[0]
        v = p.add_run(f"{valor}\n")
        v.font.size, v.font.bold, v.font.color.rgb = Pt(14), True, rp.VERDE
        p.add_run(f"{nombre} ({var})").font.size = Pt(8.5)
    doc.add_paragraph()

    rp._tabla(doc, pd.DataFrame({"✓ Lo que funcionó": qa.funciono,
                                 "⚠ Lo que hay que corregir": qa.corregir}))
    rp._alerta(doc, f"El período en una línea. {qa.en_una_linea}")

    doc.add_heading("Las 3 prioridades", level=2)
    rp._tabla(doc, pd.DataFrame({"#": ["1", "2", "3"], "Prioridad": qa.prioridades}))

    if qa.seguimiento is not None:
        doc.add_heading("Cierre de los compromisos anteriores", level=2)
        rp._tabla(doc, qa.seguimiento)
    if qa.productividad is not None:
        doc.add_heading("Dato de productividad del área", level=2)
        rp._tabla(doc, qa.productividad)

    doc.add_heading("Preguntas clave", level=2)
    for i, p in enumerate(qa.preguntas, start=1):
        rp._alerta(doc, f"P{i}. {p.pregunta}\nCómo responder: {p.respuesta}")

    rp._alerta(doc, f"Antes de entrar a la reunión. {qa.cierre}")

    if qa.avisos:
        doc.add_heading("Para revisar antes de enviar", level=2)
        for a in qa.avisos:
            doc.add_paragraph(a, style="List Bullet")

    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(ruta))
    return ruta