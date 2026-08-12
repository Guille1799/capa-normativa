"""Procedencia POR RAMA — tests que están ROJOS sin el cambio (v0.13.0).

Fixtures SINTÉTICOS, como el resto de la suite: si estos tests necesitaran hablar de un
dominio concreto, el registro habría dejado de ser infraestructura.

⚠️ CUIDADO CON EL FALSO VERDE. Hoy R13 rechaza `certainty`/`provenance_note` en una rama
por CLAVE DESCONOCIDA, así que un `pytest.raises(NormError)` a secas pasaría por el motivo
equivocado — el peligro que `conftest.py` ya nombra. Por eso cada rechazo comprueba además
que el mensaje NO es el de R13: `_rechaza_pero_no_por_clave_desconocida`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from capa_normativa import NormError, NormRegistry

HOY = __import__("datetime").date(2026, 1, 1)

SCHEMA = {
    "certainty_scale": ["alta", "moderada", "baja", "muy_baja", "sin_respaldo"],
    "weak_from": "baja",
    "unsupported_level": "sin_respaldo",
    "wildcards": ["unknown", "any"],
    "subject_dimensions": ["mode"],
    "evidence_certainty_field": "certeza",
}

EVIDENCIA = [
    {"id": "EV-A", "cita": "Autor A 2021", "claim": "vale 3 en modo alfa", "certeza": "moderada"},
    {"id": "EV-B", "cita": "Autor B 2019", "claim": "vale 2 en modo beta", "certeza": "baja"},
    {"id": "EV-C", "cita": "Doc interno", "claim": "vale 9 y es del propio proyecto", "certeza": "muy_baja"},
]


def cargar(tmp_path: Path, norms: list[dict], nombre: str = "r"):
    d = tmp_path / nombre
    d.mkdir()
    (d / "schema.yaml").write_text(yaml.safe_dump(SCHEMA, allow_unicode=True), "utf-8")
    (d / "evidence.yaml").write_text(yaml.safe_dump(EVIDENCIA, allow_unicode=True), "utf-8")
    (d / "norms.yaml").write_text(yaml.safe_dump(norms, allow_unicode=True), "utf-8")
    return NormRegistry.load(d, today=HOY)


def _rechaza_pero_no_por_clave_desconocida(tmp_path, norms, nombre):
    """Que falle no basta: tiene que fallar por LA REGLA, no porque el parser no conozca
    la clave. Sin esta comprobación estos tests pasarían hoy en verde sin el cambio."""
    with pytest.raises(NormError) as exc:
        cargar(tmp_path, norms, nombre)
    assert "claves desconocidas" not in str(exc.value), (
        f"rechazado por R13 (clave desconocida), no por la regla que se está probando: "
        f"{exc.value}")
    return str(exc.value)


def _control_positivo(tmp_path, nombre):
    """Un rechazo NO se puede probar solo sobre una forma que el parser aún no admite:
    hoy la MIXTA bien escrita también falla, así que `raises` pasaría en verde sin el
    cambio (medido: dos de estos tests lo hacían). El par bueno/malo lo cierra."""
    cargar(tmp_path, MIXTA(), nombre + "_ok")


# ── la norma MIXTA, que es el caso que hoy no se puede escribir ──────────────

def MIXTA(**norma):
    """Una rama respaldada y otra que es convención del motor. Es la forma que el molde
    de v0.12.0 rechaza en los dos sentidos (registry.py:524 y :527)."""
    base = {
        "slug": "mixta",
        "title": "una rama respaldada, otra convención",
        "status": "vigente",
        "strength": "condicional",
        "certainty": "sin_respaldo",
        "expires": "2030-01-01",
        "branches": [
            {"when": {"mode": "alfa"}, "value": 3, "evidence": ["EV-A"], "certainty": "moderada"},
            {"when": {"mode": "any"}, "value": 9, "certainty": "sin_respaldo",
             "provenance_note": "convención del motor: es lo que hacía el código, sin fuente"},
        ],
    }
    base.update(norma)
    return [base]


def test_una_rama_puede_declarar_su_propia_certeza(tmp_path):
    """EL CASO. Hoy no es representable: R4 es todo-o-nada A NIVEL DE NORMA, así que una
    norma mixta tiene que mentir en un sentido u otro — inflar la certeza de la rama sin
    respaldo, o borrar el respaldo real de la otra."""
    reg = cargar(tmp_path, MIXTA())
    n = reg.norma("mixta")
    assert n.branches[0].certainty == "moderada"
    assert n.branches[1].certainty == "sin_respaldo"


def test_la_rama_sin_respaldo_dice_de_donde_sale_SU_numero(tmp_path):
    """`provenance_note` es el PRECIO de declararse sin respaldo ('decir de dónde salió el
    número'). Si la ausencia de respaldo es por rama, el precio también: una nota de norma
    que describe dos orígenes distintos en un solo bloque de prosa es exactamente la prosa
    que no parsea nadie."""
    reg = cargar(tmp_path, MIXTA())
    assert "convención del motor" in reg.norma("mixta").branches[1].provenance_note
    assert reg.norma("mixta").branches[0].provenance_note is None


def test_una_rama_sin_respaldo_SIN_nota_no_se_construye(tmp_path):
    """Sin esto, la procedencia por rama sería la puerta de atrás de R4: declararse
    `sin_respaldo` en la rama y no pagar nada."""
    _control_positivo(tmp_path, "sin_nota")
    norms = MIXTA()
    del norms[0]["branches"][1]["provenance_note"]
    msg = _rechaza_pero_no_por_clave_desconocida(tmp_path, norms, "sin_nota")
    assert "provenance_note" in msg


def test_una_rama_con_evidencia_no_puede_llevar_provenance_note(tmp_path):
    """El espejo por rama de registry.py:490. El matiz de una cita va PEGADO a la cita
    (`note`), no en el campo de los números sin respaldo."""
    _control_positivo(tmp_path, "nota_con_ev")
    norms = MIXTA()
    norms[0]["branches"][0]["provenance_note"] = "esto es un matiz de la cita, no una procedencia"
    msg = _rechaza_pero_no_por_clave_desconocida(tmp_path, norms, "nota_con_ev")
    assert "provenance_note" in msg


# ── lo que el consumidor RECIBE, que es el único sitio donde esto se paga ────

def test_resolve_devuelve_la_certeza_de_LA_RAMA_no_la_de_la_norma(tmp_path):
    """El pago. Sin esto el cambio es decorativo: `Resolution.certainty` sale de la norma
    (registry.py:883), así que el motor recibe la MISMA certeza tanto si le contestó la
    rama respaldada como si le contestó la convención."""
    reg = cargar(tmp_path, MIXTA())
    assert reg.resolve("mixta", mode="alfa").certainty == "moderada"
    assert reg.resolve("mixta", mode="omega").certainty == "sin_respaldo"


def test_resolve_entrega_la_procedencia_de_la_rama_que_contesto(tmp_path):
    reg = cargar(tmp_path, MIXTA())
    assert reg.resolve("mixta", mode="alfa").provenance_note is None
    assert "convención del motor" in reg.resolve("mixta", mode="omega").provenance_note


# ── cómo se acopla con las reglas que ya existen ─────────────────────────────

def test_la_certeza_de_la_norma_es_la_de_su_rama_MAS_DEBIL(tmp_path):
    """La etiqueta de la norma no puede afirmar más de lo que sostiene su PEOR rama: es
    lo que leen R1 (nada vinculante con certeza débil) y R2 (lo débil caduca solo). Si
    pudiera declararse por encima, la procedencia por rama sería la forma nueva de la
    certeza autodeclarada que la v0.6.0 cerró."""
    norms = MIXTA(certainty="moderada")     # la rama peor es `sin_respaldo`
    msg = _rechaza_pero_no_por_clave_desconocida(tmp_path, norms, "inflada")
    assert "moderada" in msg and "sin_respaldo" in msg


def test_R15b_mira_la_evidencia_DE_CADA_RAMA_no_la_union(tmp_path):
    """El agujero que la propia R15b deja abierto hoy, y que NO necesita ramas mixtas para
    aparecer: `mejor = min(certezas)` (registry.py:557) toma la mejor evidencia de TODAS
    las ramas juntas, así que una rama que solo cita una fuente floja viaja con la certeza
    que sostiene la fuente de su hermana. Medido en el primer inquilino el 2026-08-12:
    pasa en `working_sets_by_mode`, que es `vigente` y resuelve en producción.
    """
    norms = [{
        "slug": "por_union",
        "title": "una rama floja viajando con la certeza de su hermana",
        "status": "vigente",
        "strength": "condicional",
        "certainty": "baja",           # la sostiene EV-B (baja) — pero solo en la rama beta
        "expires": "2030-01-01",
        "branches": [
            {"when": {"mode": "beta"}, "value": 2, "evidence": ["EV-B"]},
            {"when": {"mode": "any"}, "value": 9, "evidence": ["EV-C"]},   # muy_baja
        ],
    }]
    with pytest.raises(NormError) as exc:
        cargar(tmp_path, norms, "union")
    assert "muy_baja" in str(exc.value)


def test_una_norma_con_una_rama_debil_no_puede_ser_VINCULANTE(tmp_path):
    """R1, y el motivo por el que `strength` NO se parte por rama: el consumidor lee
    `norm.is_binding` sin saber qué rama le contestó, así que una norma vinculante con una
    rama sin respaldo obliga a obedecer un número que no sostiene nadie. Quien necesite
    'vinculante aquí, condicional allá' escribe DOS normas con `when` disjuntos."""
    norms = MIXTA(strength="vinculante", certainty="moderada")
    msg = _rechaza_pero_no_por_clave_desconocida(tmp_path, norms, "vinculante")
    assert "vinculante" in msg


# ── y lo que NO puede cambiar ────────────────────────────────────────────────

def test_lo_escrito_hoy_sigue_significando_exactamente_lo_mismo(tmp_path):
    """Una norma sin campos por rama se comporta igual que en v0.12.0: cada rama hereda la
    certeza de la norma. Es la condición para que esto sea aditivo."""
    norms = [{
        "slug": "de_siempre",
        "title": "sin nada por rama",
        "status": "vigente",
        "strength": "condicional",
        "certainty": "baja",
        "expires": "2030-01-01",
        "branches": [
            {"when": {"mode": "beta"}, "value": 2, "evidence": ["EV-B"]},
            {"when": {"mode": "any"}, "value": 2, "evidence": ["EV-B"]},
        ],
    }]
    reg = cargar(tmp_path, norms, "vieja")
    assert reg.resolve("de_siempre", mode="beta").certainty == "baja"
    assert reg.resolve("de_siempre", mode="omega").certainty == "baja"
    assert reg.norma("de_siempre").certainty == "baja"


def test_la_norma_ENTERA_sin_respaldo_sigue_pagando_con_UNA_nota(tmp_path):
    """Las 22 normas que el primer inquilino tiene así no se tocan: si NINGUNA rama declara
    nada, la nota de la norma cubre a todas."""
    norms = [{
        "slug": "convencion_entera",
        "title": "todo el número es convención",
        "status": "vigente",
        "strength": "condicional",
        "certainty": "sin_respaldo",
        "provenance_note": "estaba en el código sin cita ni comentario",
        "expires": "2030-01-01",
        "branches": [
            {"when": {"mode": "beta"}, "value": 2},
            {"when": {"mode": "any"}, "value": 9},
        ],
    }]
    reg = cargar(tmp_path, norms, "entera")
    r = reg.resolve("convencion_entera", mode="omega")
    assert r.certainty == "sin_respaldo"
    assert "sin cita ni comentario" in r.provenance_note
