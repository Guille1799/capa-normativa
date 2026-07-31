"""Tests del registro, con fixtures SINTÉTICOS.

A propósito no hay ningún dominio real aquí: si estos tests necesitaran hablar de
un dominio concreto, el registro habría dejado de ser infraestructura.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from capa_normativa import NormError, NormRegistry, RetiredNormError

FIX = Path(__file__).parent / "fixtures"
HOY = date(2026, 1, 1)


def reg(today=HOY):
    return NormRegistry.load(FIX, today=today)


def mutando(tmp_path, mutate):
    """Carga los fixtures con una mutación aplicada, para probar los rechazos."""
    norms = yaml.safe_load((FIX / "norms.yaml").read_text("utf-8"))
    mutate(norms)
    p = tmp_path / "norms.yaml"
    p.write_text(yaml.safe_dump(norms, allow_unicode=True), "utf-8")
    return NormRegistry.load(norms_path=p, evidence_path=FIX / "evidence.yaml",
                             schema_path=FIX / "schema.yaml", today=HOY)


def by_slug(norms, slug):
    return next(n for n in norms if n["slug"] == slug)


# ── resolución ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind, esperado", [("alpha", 10.0), ("beta", 20.0)])
def test_resuelve_la_rama_del_sujeto(kind, esperado):
    assert reg().resolve("threshold_by_kind", kind=kind).value == esperado


def test_sujeto_desconocido_usa_la_rama_por_defecto_Y_LO_DECLARA():
    r = reg().resolve("threshold_by_kind", kind="gamma")
    assert r.value == 20.0 and r.is_fallback is True


def test_el_valor_viaja_con_su_procedencia_nunca_pelado():
    r = reg().resolve("threshold_by_kind", kind="alpha")
    assert r.evidence == ("EV-001",) and r.certainty == "baja" and r.unit


def test_rangos_numericos_y_rama_mixta():
    """Rama específica en una dimensión y comodín en otra: debe matchear."""
    assert reg().resolve("coefficient_by_range", size="150", mode="fast").value == 1.5
    assert reg().resolve("coefficient_by_range", size="50", mode="slow").value == 1.0


def test_dato_requerido_ausente_no_se_adivina():
    r = reg().resolve("coefficient_by_range", mode="fast")
    assert r.value is None and r.missing == ("size",)


# ── estados ilegales: no se construyen ──────────────────────────────────

def test_ilegal_vinculante_con_certeza_debil(tmp_path):
    with pytest.raises(NormError, match="escala declarada"):
        mutando(tmp_path, lambda n: by_slug(n, "threshold_by_kind").update(strength="vinculante"))


def test_ilegal_certeza_debil_sin_caducidad(tmp_path):
    with pytest.raises(NormError, match="expiración"):
        mutando(tmp_path, lambda n: by_slug(n, "threshold_by_kind").pop("expires"))


def test_ilegal_norma_vigente_caducada():
    with pytest.raises(NormError, match="CADUCADA"):
        reg(today=date(2100, 1, 1))


def test_ilegal_rama_sin_evidencia(tmp_path):
    with pytest.raises(NormError, match="sin evidencia"):
        mutando(tmp_path, lambda n: by_slug(n, "threshold_by_kind")["branches"][0].pop("evidence"))


def test_ilegal_evidencia_inexistente(tmp_path):
    with pytest.raises(NormError, match="inexistente"):
        mutando(tmp_path, lambda n: by_slug(n, "threshold_by_kind")["branches"][0]
                .update(evidence=["EV-999"]))


def test_ilegal_no_declarar_el_sujeto_desconocido(tmp_path):
    """El anti-sesgo: si no dices qué pasa con quien no conoces, no arranca."""
    def quitar(n):
        x = by_slug(n, "threshold_by_kind")
        x["branches"] = [b for b in x["branches"] if b["when"].get("kind") != "unknown"]
    with pytest.raises(NormError, match="caso desconocido"):
        mutando(tmp_path, quitar)


def test_ilegal_slug_duplicado(tmp_path):
    with pytest.raises(NormError, match="duplicado"):
        mutando(tmp_path, lambda n: n.append(dict(n[0])))


# ── el límite de expresividad, mecanizado ───────────────────────────────

def colar(tmp_path, when):
    norms = [{"slug": "intento", "title": "t", "status": "vigente",
              "strength": "condicional", "certainty": "moderada", "unit": "u",
              "semantics": "s",
              "branches": [{"when": when, "value": 1, "evidence": ["EV-001"]},
                           {"when": {k: "any" for k in when}, "value": 0,
                            "evidence": ["EV-001"]}]}]
    p = tmp_path / "n.yaml"
    p.write_text(yaml.safe_dump(norms, allow_unicode=True), "utf-8")
    return NormRegistry.load(norms_path=p, evidence_path=FIX / "evidence.yaml",
                             schema_path=FIX / "schema.yaml", today=HOY)


def test_limite_rechaza_disyuncion(tmp_path):
    with pytest.raises(NormError, match="disyunción"):
        colar(tmp_path, {"mode": ["fast", "slow"]})


def test_limite_rechaza_condicion_compuesta(tmp_path):
    with pytest.raises(NormError, match="compuesta"):
        colar(tmp_path, {"mode": {"op": "or", "vals": ["a", "b"]}})


def test_limite_rechaza_operadores_inventados(tmp_path):
    with pytest.raises(NormError, match="operador inventado"):
        colar(tmp_path, {"prefix": "algo*"})


def test_limite_permite_lo_declarado(tmp_path):
    assert colar(tmp_path, {"kind": "alpha"}).resolve("intento", kind="alpha").value == 1
    assert colar(tmp_path, {"n": ">=18"}).resolve("intento", n="30").value == 1
    assert colar(tmp_path, {"n": "[10,20)"}).resolve("intento", n="15").value == 1


# ── retirada y ausencia de respaldo ─────────────────────────────────────

def test_una_norma_retirada_no_se_puede_leer():
    with pytest.raises(RetiredNormError, match="RETIRADA"):
        reg().resolve("legacy_cap", kind="alpha")


def test_la_retirada_dice_por_que_y_con_que_se_sustituye():
    try:
        reg().resolve("legacy_cap", kind="alpha")
    except RetiredNormError as e:
        assert "threshold_by_kind" in str(e) and "heurísticas" in str(e)


def test_ilegal_retirar_sin_motivo(tmp_path):
    with pytest.raises(NormError, match="retirement.reason"):
        mutando(tmp_path, lambda n: by_slug(n, "legacy_cap")["retirement"].pop("reason"))


def test_una_norma_sin_respaldo_existe_pero_grita():
    r = reg().resolve("unsupported_number", kind="alpha")
    assert r.value == 3.3 and r.certainty == "sin_respaldo" and r.evidence == ()


def test_sin_respaldo_exige_decir_de_donde_salio(tmp_path):
    with pytest.raises(NormError, match="provenance_note"):
        mutando(tmp_path, lambda n: by_slug(n, "unsupported_number").pop("provenance_note"))


def test_no_se_puede_fingir_ausencia_de_respaldo_teniendo_evidencia(tmp_path):
    with pytest.raises(NormError, match="no puede ser"):
        mutando(tmp_path, lambda n: by_slug(n, "unsupported_number")["branches"][0]
                .update(evidence=["EV-001"]))


# ── genericidad ─────────────────────────────────────────────────────────

def test_el_registro_no_conoce_ningun_dominio():
    """Si el motor llega a mencionar un dominio concreto, ha dejado de ser
    infraestructura. El dominio vive en los YAML del consumidor."""
    import re
    src = (Path(__file__).parent.parent / "src" / "capa_normativa" / "registry.py").read_text("utf-8")
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    src = re.sub(r"#.*", "", src)
    prohibidos = ["kcal", "ffm", "salud", "paciente", "atleta", "nutri", "entren",
                  "dosis", "sexo", "edad"]
    assert not [t for t in prohibidos if t in src.lower()]


# ── R10: el orden del fichero no puede decidir el valor ─────────────────

def test_ilegal_dos_ramas_que_matchean_al_mismo_sujeto(tmp_path):
    """Encontrado revisando antes de publicar: dos ramas solapadas se aceptaban y
    ganaba la primera del fichero — o sea, el ORDEN decidía el valor, que es
    exactamente lo que el límite de expresividad prohíbe."""
    def duplicar(n):
        x = by_slug(n, "threshold_by_kind")
        x["branches"].insert(1, {"when": {"kind": "alpha"}, "value": 999,
                                 "evidence": ["EV-002"]})
    with pytest.raises(NormError, match="mismo sujeto"):
        mutando(tmp_path, duplicar)


def test_ilegal_una_rama_subsume_a_otra(tmp_path):
    """`{kind: alpha}` y `{kind: alpha, mode: fast}`: un sujeto alpha+fast matchea
    las dos. Subsunción = solapamiento garantizado."""
    def subsumir(n):
        x = by_slug(n, "threshold_by_kind")
        x["branches"].insert(1, {"when": {"kind": "alpha", "mode": "fast"}, "value": 999,
                                 "evidence": ["EV-002"]})
    with pytest.raises(NormError, match="mismo sujeto"):
        mutando(tmp_path, subsumir)


def test_ramas_disjuntas_siguen_siendo_validas():
    """No debe haber falsos positivos: alpha y beta no solapan, y la rama del
    sujeto desconocido solapa por definición pero el motor la prueba la última."""
    r = reg()
    assert r.resolve("threshold_by_kind", kind="alpha").value == 10.0
    assert r.resolve("threshold_by_kind", kind="beta").value == 20.0


# ── R11: una norma no puede ramificar por otra norma ────────────────────
# El agujero que motivó la v0.2.0. R9 mecaniza la FORMA de la condición (comodín,
# igualdad, rango) pero no su SEMÁNTICA: para el registro, "atributo del sujeto" y
# "valor de otra norma" eran el mismo string. Encontrado usando el registro en
# producción, buscándolo a propósito: se colaba al primer intento.


def esquema(tmp_path, **cambios):
    """Fixtures con un schema.yaml mutado."""
    raw = yaml.safe_load((FIX / "schema.yaml").read_text("utf-8"))
    raw.update(cambios)
    for k, v in list(cambios.items()):
        if v is None:
            raw.pop(k, None)
    p = tmp_path / "schema.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), "utf-8")
    return NormRegistry.load(norms_path=FIX / "norms.yaml", evidence_path=FIX / "evidence.yaml",
                             schema_path=p, today=HOY)


def test_ilegal_ramificar_por_el_nombre_de_otra_norma(tmp_path):
    """LA razón de ser de R11. `{threshold_by_kind: ">=10"}` es un rango bien formado,
    así que R9 lo daba por bueno: una norma referenciaba a otra y el encadenamiento
    quedaba en manos de la disciplina en vez de la construcción."""
    with pytest.raises(NormError, match="no es una dimensión declarada"):
        colar(tmp_path, {"threshold_by_kind": ">=10"})


def test_ilegal_ramificar_por_una_dimension_inventada(tmp_path):
    with pytest.raises(NormError, match="no es una dimensión declarada"):
        colar(tmp_path, {"dimension_que_nadie_declaro": "x"})


def test_r11_caza_las_erratas_de_dimension(tmp_path):
    """Regalo de R11, y no menor: una dimensión mal escrita no matchea NUNCA y cae al
    fallback en silencio. Antes eso era un bug indetectable; ahora no arranca."""
    with pytest.raises(NormError, match="no es una dimensión declarada"):
        colar(tmp_path, {"kimd": "alpha"})


def test_ilegal_declarar_una_norma_como_dimension_del_sujeto(tmp_path):
    """La puerta de atrás de R11: declarar el slug de una norma como si fuera un
    atributo del sujeto y encadenar igual. Un nombre es una cosa o la otra."""
    dims = yaml.safe_load((FIX / "schema.yaml").read_text("utf-8"))["subject_dimensions"]
    with pytest.raises(NormError, match="dimensión del sujeto Y son slugs"):
        esquema(tmp_path, subject_dimensions=dims + ["threshold_by_kind"])


def test_un_schema_sin_subject_dimensions_no_arranca(tmp_path):
    """BREAKING v0.2.0, y a propósito: opcional habría dejado el agujero abierto por
    defecto, que es la forma de tener un límite que no impide nada."""
    with pytest.raises(NormError, match="falta `subject_dimensions`"):
        esquema(tmp_path, subject_dimensions=None)


def test_las_dimensiones_declaradas_siguen_funcionando(tmp_path):
    """Sin falsos positivos: lo declarado se resuelve igual que antes."""
    assert colar(tmp_path, {"kind": "alpha"}).resolve("intento", kind="alpha").value == 1
    assert reg().resolve("coefficient_by_range", size="150", mode="fast").value == 1.5
