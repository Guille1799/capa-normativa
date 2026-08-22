"""Tests del registro, con fixtures SINTÉTICOS.

A propósito no hay ningún dominio real aquí: si estos tests necesitaran hablar de
un dominio concreto, el registro habría dejado de ser infraestructura.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from capa_normativa import (
    BlockedNormError,
    NormError,
    NormRegistry,
    RetiredNormError,
)

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


# ── R12: el solapamiento entre RANGOS (v0.3.0) ──────────────────────────
# R10 comparaba CONJUNTOS de pares, así que solo veía igualdad y subsunción. Dos rangos
# son literales distintos y convivían tan tranquilos. Encontrado tendiendo la trampa a
# propósito sobre un eje de bandas: con ">=40" y ">=60" declaradas, un sujeto de 70 se
# llevaba el valor de la PRIMERA rama del fichero. No un aviso ausente: la respuesta mal.


def dos_ramas(tmp_path, when_a, when_b):
    norms = [{"slug": "intento", "title": "t", "status": "vigente",
              "strength": "condicional", "certainty": "moderada", "unit": "u",
              "semantics": "s",
              "branches": [{"when": when_a, "value": 1, "evidence": ["EV-001"]},
                           {"when": when_b, "value": 2, "evidence": ["EV-001"]},
                           {"when": {k: "any" for k in {**when_a, **when_b}},
                            "value": 0, "evidence": ["EV-001"]}]}]
    p = tmp_path / "n.yaml"
    p.write_text(yaml.safe_dump(norms, allow_unicode=True), "utf-8")
    return NormRegistry.load(norms_path=p, evidence_path=FIX / "evidence.yaml",
                             schema_path=FIX / "schema.yaml", today=HOY)


@pytest.mark.parametrize("a, b, motivo", [
    (">=40", ">=60", "bandas abiertas: todo lo de b esta tambien en a"),
    ("[10,20]", "[20,30)", "comparten exactamente el extremo cerrado"),
    ("<=50", ">=50", "se tocan en 50 y ambos lo incluyen"),
    (">=18", "20", "un literal numerico que cae DENTRO del rango"),
])
def test_ilegal_dos_rangos_que_solapan(tmp_path, a, b, motivo):
    with pytest.raises(NormError, match="mismo sujeto"):
        dos_ramas(tmp_path, {"size": a}, {"size": b})


@pytest.mark.parametrize("a, b, motivo", [
    (">=100", "[10,100)", "el 100 queda fuera del intervalo abierto"),
    ("[10,20)", "[20,30)", "adyacentes pero disjuntos"),
    ("<50", ">=50", "se tocan sin compartir ningun punto"),
    (">=18", "10", "el literal cae fuera"),
    (">=18", "alpha", "un literal no numerico no puede cumplir un rango"),
])
def test_rangos_disjuntos_no_dan_falso_positivo(tmp_path, a, b, motivo):
    """La mitad que importa: un gate que rechaza de más se acaba desactivando."""
    assert dos_ramas(tmp_path, {"size": a}, {"size": b}).resolve("intento", size="0") is not None


def test_no_solapan_si_discriminan_por_OTRA_dimension(tmp_path):
    """Dos rangos idénticos en `size` conviven si `mode` los separa: el sujeto tendría
    que cumplir las dos a la vez, y no puede."""
    r = dos_ramas(tmp_path, {"size": ">=10", "mode": "fast"}, {"size": ">=10", "mode": "slow"})
    assert r.resolve("intento", size="50", mode="fast").value == 1
    assert r.resolve("intento", size="50", mode="slow").value == 2


def test_ilegal_un_rango_vacio_es_una_rama_muerta(tmp_path):
    """`[5,3]` no matchea nunca: cae al comodín y devuelve un valor plausible que no es
    el suyo. Es el modo de fallo que más cuesta ver, porque nada falla."""
    with pytest.raises(NormError, match="VACÍO"):
        colar(tmp_path, {"size": "[5,3]"})
    with pytest.raises(NormError, match="VACÍO"):
        colar(tmp_path, {"size": "(4,4)"})


def test_un_rango_de_un_solo_punto_sigue_siendo_valido(tmp_path):
    """`[4,4]` es raro pero legítimo: matchea exactamente el 4."""
    assert colar(tmp_path, {"size": "[4,4]"}).resolve("intento", size="4").value == 1


# ── R13: las claves desconocidas dejan de tragarse (v0.4.0) ─────────────
# El parser aceptaba cualquier clave que no entendiera y la DESCARTABA en silencio, así
# que lo escrito y lo que hacía el registro podían no coincidir sin que nada fallara.
# Encontrado intentando poner `certainty` en una RAMA: se aceptaba, se tiraba, y resolve()
# seguía devolviendo la certeza de la norma. El que la escribió creía haber ramificado la
# confianza y no había hecho nada.


def test_la_certeza_por_rama_YA_NO_se_ignora_pero_TAMPOCO_es_libre(tmp_path):
    """LA sonda que destapó R13, reescrita al contrato de la v0.14.0.

    Decía: *«la certeza por rama es una limitación ABIERTA del molde; lo que no puede pasar
    es que se acepte y se ignore»*. Eso último sigue siendo el punto — pero la limitación se
    cerró, así que `certainty` en una rama ya no es una clave desconocida: es la forma
    correcta. Lo que la sonda vigila ahora es que **se lea y se compruebe**, que es lo mismo
    que vigilaba antes por el otro lado: la certeza sube a `alta` en una rama cuya evidencia
    es `moderada`, y R15b la para. Si algún día se volviera a ignorar, esto pasaría a verde
    solo — por eso el mensaje se comprueba, y no solo que falle.
    """
    def meter(n):
        by_slug(n, "threshold_by_kind")["branches"][0]["certainty"] = "alta"
    with pytest.raises(NormError, match="rama #0 viaja con certainty='alta'"):
        mutando(tmp_path, meter)


def test_una_certeza_de_rama_fuera_de_la_escala_no_se_construye(tmp_path):
    """La escala la declara el consumidor, así que un valor que no está en ella no es una
    certeza distinta: es una errata que apagaría R15b y R19 en esa rama."""
    def meter(n):
        by_slug(n, "threshold_by_kind")["branches"][0]["certainty"] = "altísima"
    with pytest.raises(NormError, match="no está en la escala declarada"):
        mutando(tmp_path, meter)


def test_ilegal_errata_en_value(tmp_path):
    """El peor de todos: `valeu: 55.0` hacía que la norma CARGARA y emitiera None con
    `is_fallback=False` — indistinguible de un "aquí no gobierno" deliberado."""
    def meter(n):
        b = by_slug(n, "threshold_by_kind")["branches"][0]
        b["valeu"] = b.pop("value")
    with pytest.raises(NormError, match="valeu"):
        mutando(tmp_path, meter)


def test_la_errata_sugiere_la_clave_correcta(tmp_path):
    """Un mensaje que solo dice "clave desconocida" obliga a ir a leer el código."""
    def meter(n):
        by_slug(n, "threshold_by_kind")["certainy"] = "alta"
    with pytest.raises(NormError, match=r"¿querías decir 'certainty'\?"):
        mutando(tmp_path, meter)


@pytest.mark.parametrize("clave", ["applies_only_if", "expires", "unit"])
def test_ilegal_clave_inventada_en_una_rama(tmp_path, clave):
    """`expires` y `unit` son válidas en la NORMA y no en la rama: escribirlas ahí es creer
    que caducas o etiquetas una rama sola, y no hacer nada."""
    def meter(n):
        by_slug(n, "threshold_by_kind")["branches"][0][clave] = "x"
    with pytest.raises(NormError, match="claves desconocidas"):
        mutando(tmp_path, meter)


def test_las_claves_conocidas_siguen_pasando():
    """Sin falsos positivos. Los fixtures ejercen entre todos las 13 claves de norma y las 4
    de rama; si R13 se pasara de estricto, el registro entero dejaría de cargar."""
    from capa_normativa.registry import _BRANCH_KEYS, _NORM_KEYS

    usadas_norma, usadas_rama = set(), set()
    for raw in yaml.safe_load((FIX / "norms.yaml").read_text("utf-8")):
        usadas_norma |= set(raw)
        for b in raw.get("branches") or []:
            usadas_rama |= set(b)

    assert usadas_norma <= _NORM_KEYS and usadas_rama <= _BRANCH_KEYS
    assert usadas_norma >= {"slug", "status", "branches", "certainty", "strength"}
    assert reg().resolve("threshold_by_kind", kind="alpha").value == 10.0


# ── R14: los estados y los punteros son reales (v0.5.0) ────────────────


def test_ilegal_status_desconocido(tmp_path):
    """R14a. Y el motivo por el que importa NO es la pulcritud: la caducidad solo se
    comprobaba `if status == "vigente"`, así que una errata la DESACTIVABA — una norma
    caducada cargaba y seguía emitiendo."""
    def meter(n):
        by_slug(n, "threshold_by_kind")["status"] = "vigent"
    with pytest.raises(NormError, match=r"desconocido.*¿querías decir 'vigente'\?"):
        mutando(tmp_path, meter)


def test_la_errata_en_status_ya_no_desactiva_la_caducidad(tmp_path):
    """La demostración del daño: `vigent` + fecha pasada. Antes cargaba tan tranquila."""
    def meter(n):
        x = by_slug(n, "threshold_by_kind")
        x["status"], x["expires"] = "vigent", "2020-01-01"
    with pytest.raises(NormError, match="desconocido"):
        mutando(tmp_path, meter)


def test_ilegal_replaced_by_que_apunta_a_la_nada(tmp_path):
    """R14b. El puntero colgante que este registro existe para impedir, cometido dentro
    del propio registro — y peor que pasivo: `RetiredNormError` compone su mensaje con él
    y se lo enseña al lector como si fuera ayuda."""
    def meter(n):
        by_slug(n, "legacy_cap")["retirement"]["replaced_by"] = ["norma_que_no_existe"]
    with pytest.raises(NormError, match="apunta a normas que no existen"):
        mutando(tmp_path, meter)


def test_replaced_by_vacio_SI_es_valido(tmp_path):
    """"No hay sustituto" es una respuesta legítima, y el mensaje de error ya la sugería…
    mientras la rechazaba: `not []` es cierto, así que seguir la instrucción no funcionaba.
    Ahora lo que se exige es que la clave esté ESCRITA, no que tenga contenido."""
    def meter(n):
        by_slug(n, "legacy_cap")["retirement"]["replaced_by"] = []
    assert mutando(tmp_path, meter) is not None


def test_una_norma_bloqueada_NO_emite_valor(tmp_path):
    """R14c — la propiedad que §5.1 prometía y no existía.

    Emitir aquí sería resolver el conflicto a escondidas, eligiendo por orden de fichero.
    El registro prefiere no responder: una norma tiene valor o está explícitamente
    bloqueada, nunca ambigua."""
    def bloquear(n):
        x = by_slug(n, "threshold_by_kind")
        x["status"] = "bloqueada"
        x["blocking"] = {"date": "2026-01-01",
                         "reason": "dos fuentes dan cortes distintos y nadie ha adjudicado",
                         "conflicting_evidence": ["EV-001", "EV-002"]}
    r = mutando(tmp_path, bloquear)
    with pytest.raises(BlockedNormError, match="BLOQUEADA"):
        r.resolve("threshold_by_kind", kind="alpha")
    # …y el motivo viaja en el error, que es lo que la hace accionable.
    try:
        r.resolve("threshold_by_kind", kind="alpha")
    except BlockedNormError as e:
        assert "nadie ha adjudicado" in str(e)


def test_bloquear_es_un_ACTO_y_lleva_motivo(tmp_path):
    """Igual que retirar. Sin motivo, "bloqueada" sería una etiqueta que nadie sabe deshacer."""
    def meter(n):
        by_slug(n, "threshold_by_kind")["status"] = "bloqueada"
    with pytest.raises(NormError, match="blocking.reason"):
        mutando(tmp_path, meter)


def test_una_norma_bloqueada_SI_puede_tener_ramas_que_solapan(tmp_path):
    """Es la semántica, no una excepción: sus ramas SON las candidatas en conflicto, así
    que solapan por definición. Exigirle ramas disjuntas sería pedirle que estuviera
    adjudicada — justo lo que declara no estar. Y no hay riesgo de que el orden decida
    nada, porque no emite."""
    def bloquear(n):
        x = by_slug(n, "threshold_by_kind")
        x["status"] = "bloqueada"
        x["blocking"] = {"reason": "conflicto abierto"}
        x["branches"].insert(0, {"when": {"kind": "alpha"}, "value": 999,
                                 "evidence": ["EV-002"]})
    r = mutando(tmp_path, bloquear)          # con R10 activo esto sería "mismo sujeto"
    with pytest.raises(BlockedNormError):
        r.resolve("threshold_by_kind", kind="alpha")


def test_ilegal_blocking_sin_estar_bloqueada(tmp_path):
    """Simetría con `retirement`: el campo y el estado no pueden ir por separado."""
    def meter(n):
        by_slug(n, "threshold_by_kind")["blocking"] = {"reason": "x"}
    with pytest.raises(NormError, match="no es bloqueada"):
        mutando(tmp_path, meter)


def test_a_una_norma_que_no_emite_no_se_le_exige_caducidad(tmp_path):
    """Roce anotado desde el caso 3 y arreglado aquí: las reglas de vigencia se aplicaban
    también a normas retiradas o bloqueadas, donde caducar no significa nada."""
    def meter(n):
        x = by_slug(n, "threshold_by_kind")
        x["status"], x["blocking"] = "bloqueada", {"reason": "conflicto abierto"}
        x.pop("expires")                      # certeza baja y SIN caducidad
    assert mutando(tmp_path, meter) is not None


# ── R15: la capa ① EVIDENCIA deja de entrar sin mirar (v0.6.0) ─────────
# Ocho rondas de uso y nadie la había sondeado: el parser solo comprobaba los IDs. Todo
# lo demás —qué dice la fuente, de qué año es, cuánto de fiable— entraba sin verse.


def con_evidencia(tmp_path, mutate):
    """Carga los fixtures con `evidence.yaml` mutado."""
    ev = yaml.safe_load((FIX / "evidence.yaml").read_text("utf-8"))
    mutate(ev)
    p = tmp_path / "evidence.yaml"
    p.write_text(yaml.safe_dump(ev, allow_unicode=True), "utf-8")
    return NormRegistry.load(norms_path=FIX / "norms.yaml", evidence_path=p,
                             schema_path=FIX / "schema.yaml", today=HOY)


def test_ilegal_declarar_mas_certeza_de_la_que_sostiene_la_evidencia(tmp_path):
    """R15b — EL agujero de la ronda 8, y el que hacía decorativa toda la escala.

    R1 impide que algo `vinculante` tenga certeza débil, pero la certeza era
    AUTODECLARADA y no estaba anclada a nada: bastaba escribir `alta` a mano. O sea que
    la regla que impide tratar como dogma lo que la evidencia no sostiene se saltaba
    con una palabra.
    """
    def inflar(n):
        x = by_slug(n, "threshold_by_kind")
        x["certainty"] = "alta"                     # su evidencia es moderada/alta…
        for b in x["branches"]:
            b["evidence"] = ["EV-001"]              # …y aquí solo queda la moderada
    with pytest.raises(NormError, match="MEJOR evidencia que ELLA cita es"):
        mutando(tmp_path, inflar)


def test_declarar_MENOS_certeza_de_la_que_hay_es_legitimo(tmp_path):
    """Nadie obliga a apurar. Rebajar la certeza es una postura conservadora válida —
    lo que no se puede es inflarla."""
    def rebajar(n):
        x = by_slug(n, "threshold_by_kind")
        x["certainty"] = "muy_baja"
        x["expires"] = "2099-01-01"
    assert mutando(tmp_path, rebajar) is not None


def test_una_norma_SIN_RESPALDO_no_se_compara_con_nada(tmp_path):
    """No cita evidencia por definición, así que R15b no le aplica. Sus guardas son
    otras: `provenance_note` obligatoria, jamás vinculante y caducidad forzosa."""
    assert reg().resolve("unsupported_number", kind="alpha").value == 3.3


def test_ilegal_ids_de_evidencia_repetidos(tmp_path):
    """R15a. Dos entradas DISTINTAS con el mismo id colapsaban en silencio y nadie podía
    saber cuál estaba citando una norma. Es la colisión de identificadores que este
    registro persigue, en la capa append-only — donde además nunca se borra, así que el
    choque es para siempre."""
    def duplicar(ev):
        impostora = dict(ev[0])
        impostora["claim"] = "lo contrario de lo que dice la de verdad"
        ev.append(impostora)
    with pytest.raises(NormError, match="ids de evidencia repetidos"):
        con_evidencia(tmp_path, duplicar)


def test_ilegal_marcar_como_reciente_un_clasico(tmp_path):
    """R15c. Citar un clásico está permitido; citarlo SIN marcarlo, no. Es el fallo real
    de un cluster entero de la referencia: cinco citas pre-2018 y ninguna señalada."""
    def mentir(ev):
        ev[0]["anio"] = 1994          # clásico…
        ev[0]["reciente"] = True      # …marcado como reciente
    with pytest.raises(NormError, match="recencia incoherente"):
        con_evidencia(tmp_path, mentir)


def test_un_clasico_BIEN_marcado_pasa(tmp_path):
    """No se prohíbe lo viejo: se prohíbe disfrazarlo."""
    def marcar(ev):
        ev[0]["anio"], ev[0]["reciente"] = 1994, False
    assert con_evidencia(tmp_path, marcar) is not None


def test_sin_declarar_los_campos_R15_no_comprueba_nada(tmp_path):
    """Opt-in de verdad: el registro no sabe cómo se llaman los campos de TU evidencia.
    Sin declararlos, el comportamiento es exactamente el de la v0.5.0 — que es lo que
    hace que esta versión no sea breaking."""
    raw = yaml.safe_load((FIX / "schema.yaml").read_text("utf-8"))
    for k in ("evidence_certainty_field", "evidence_year_field",
              "evidence_recent_field", "recency_horizon"):
        raw.pop(k)
    s = tmp_path / "schema.yaml"
    s.write_text(yaml.safe_dump(raw, allow_unicode=True), "utf-8")

    norms = yaml.safe_load((FIX / "norms.yaml").read_text("utf-8"))
    x = by_slug(norms, "threshold_by_kind")
    x["certainty"] = "alta"                          # inflada a propósito
    for b in x["branches"]:
        b["evidence"] = ["EV-001"]
    n = tmp_path / "norms.yaml"
    n.write_text(yaml.safe_dump(norms, allow_unicode=True), "utf-8")

    assert NormRegistry.load(norms_path=n, evidence_path=FIX / "evidence.yaml",
                             schema_path=s, today=HOY) is not None


# ── R16: el contrato de `resolve()`, no solo el de carga (v0.7.0) ──────
# Nueve rondas protegiendo lo que se ESCRIBE en el YAML. La otra mitad —qué pasa cuando
# el motor PREGUNTA— estaba entera sin cubrir.


def test_ilegal_preguntar_por_una_dimension_inventada():
    """R16a, el simétrico de R11. Una errata en la LLAMADA se ignoraba en silencio y la
    respuesta caía al comodín — un valor plausible que no es el que pediste.

    Y es peor que en el fichero: allí lo escribes una vez, mientras que una llamada mal
    escrita puede estar en cualquiera de los treinta sitios que consultan el registro. En
    una norma de bandas el comodín significa "no hay dato", así que la errata convierte una
    señal real en silencio.
    """
    with pytest.raises(NormError, match=r"no declaradas.*¿querías decir 'kind'\?"):
        reg().resolve("threshold_by_kind", kynd="alpha")


def test_preguntar_bien_sigue_funcionando():
    """Sin falsos positivos: pasar de menos está permitido (cae al comodín, que para eso
    está), y pasar dimensiones declaradas que esa norma no usa también."""
    assert reg().resolve("threshold_by_kind", kind="alpha").value == 10.0
    assert reg().resolve("threshold_by_kind").is_fallback is True
    assert reg().resolve("threshold_by_kind", kind="alpha", mode="fast").value == 10.0


def test_un_CERO_no_es_un_dato_ausente(tmp_path):
    """R16b. `missing` se calculaba con `not subject.get(r)`, así que 0, False y "" contaban
    como "no me lo has dado". Un cero es un valor: cero sesiones, cero dolor."""
    r = reg().resolve("coefficient_by_range", size=0, mode="fast")
    assert r.missing == (), "un 0 explícito no puede contar como dato ausente"
    assert reg().resolve("coefficient_by_range", mode="fast").missing == ("size",)
    assert reg().resolve("coefficient_by_range", size=None, mode="fast").missing == ("size",)


def test_el_registro_entrega_COPIAS_no_sus_tripas(tmp_path):
    """R16c. `value` y `matched` eran referencias a lo que vive dentro del registro, así que
    quien preguntaba podía cambiar la norma para todos. Era la negación literal de "solo hay
    una copia", que es la tesis entera de esta capa."""
    def con_lista(n):
        by_slug(n, "threshold_by_kind")["branches"][0]["value"] = [1, 2, 3]
    r = mutando(tmp_path, con_lista)

    primera = r.resolve("threshold_by_kind", kind="alpha")
    primera.value.append(999)
    primera.matched["kind"] = "MANIPULADO"

    segunda = r.resolve("threshold_by_kind", kind="alpha")
    assert segunda.value == [1, 2, 3], "el registro se dejó modificar desde fuera"
    assert segunda.matched == {"kind": "alpha"}


def test_ilegal_dos_ramas_del_sujeto_desconocido(tmp_path):
    """R16d — el punto ciego que creó la propia R10: excluye las ramas todo-comodín "porque
    solapan por definición", lo cual es correcto para UNA y deja pasar DOS. Con dos, el
    motor sobrescribe el fallback y gana la ÚLTIMA del fichero: el orden decide el valor,
    justo donde la regla que lo impide decidió no mirar."""
    def duplicar_comodin(n):
        x = by_slug(n, "threshold_by_kind")
        x["branches"].append({"when": {"kind": "any"}, "value": 999, "evidence": ["EV-002"]})
    with pytest.raises(NormError, match="ramas del sujeto desconocido"):
        mutando(tmp_path, duplicar_comodin)


def test_una_norma_BLOQUEADA_si_puede_tener_dos_comodines(tmp_path):
    """La excepción es la misma que en R10, y por el mismo motivo: sus ramas son las
    candidatas en conflicto y no emite ninguna."""
    def bloquear(n):
        x = by_slug(n, "threshold_by_kind")
        x["status"], x["blocking"] = "bloqueada", {"reason": "conflicto abierto"}
        x["branches"] = [{"when": {"kind": "any"}, "value": 10, "evidence": ["EV-001"]},
                         {"when": {"kind": "any"}, "value": 20, "evidence": ["EV-002"]}]
    r = mutando(tmp_path, bloquear)
    with pytest.raises(BlockedNormError):
        r.resolve("threshold_by_kind", kind="alpha")


def test_adjudicacion_y_retirada_siguen_siendo_libres(tmp_path):
    """LIMITACIÓN DECLARADA: dentro de `adjudication`/`retirement` no se comprueban claves.
    Son metadatos de prosa —quién adjudicó, con qué conflicto, por qué— y no gobiernan lo
    que el registro emite, así que una errata ahí es cosmética. Endurecerlo también haría el
    gate insufrible para el sitio donde más se escribe a mano."""
    def meter(n):
        by_slug(n, "legacy_cap")["retirement"]["nota_libre"] = "lo que sea"
    assert mutando(tmp_path, meter) is not None


# ── R17 · una afirmación que no respalda nada no es evidencia ────────────

def _con_evidencia(tmp_path, mutate):
    """Como `mutando`, pero la mutación es sobre `evidence.yaml`."""
    ev = yaml.safe_load((FIX / "evidence.yaml").read_text("utf-8"))
    mutate(ev)
    p = tmp_path / "evidence.yaml"
    p.write_text(yaml.safe_dump(ev, allow_unicode=True), "utf-8")
    return NormRegistry.load(norms_path=FIX / "norms.yaml", evidence_path=p,
                             schema_path=FIX / "schema.yaml", today=HOY)


def test_R17_una_evidencia_sin_respaldo_se_rechaza_DONDE_ESTA(tmp_path):
    """Encontrado escribiendo siete de ellas y chocando con el muro (§5.34).

    Hasta la v0.8.0 el registro aceptaba una entrada de evidencia con la certeza más baja
    de la escala y reventaba después, en la NORMA que la citara, con un mensaje que
    culpaba a la norma. Y no había salida: si la cita, no puede declararse `sin_respaldo`
    (R4); si declara más, se salta R15b. La entrada era **inutilizable por construcción**
    y nada lo decía — el que la escribía descubría el problema en otro fichero.
    """
    with pytest.raises(NormError, match="no es evidencia"):
        _con_evidencia(tmp_path, lambda ev: ev[0].update(certeza="sin_respaldo"))


def test_R17_el_mensaje_dice_cual_es_la_salida(tmp_path):
    """Un rechazo sin salida convierte el gate en un obstáculo, y los obstáculos se rodean."""
    with pytest.raises(NormError) as e:
        _con_evidencia(tmp_path, lambda ev: ev[0].update(certeza="sin_respaldo"))
    assert "provenance_note" in str(e.value) and "SIN entrada de evidencia" in str(e.value)


# ── R18 · con cuánta fuerza obliga, y en qué se apoya ────────────────────

def test_R18_strength_desconocido_no_se_construye(tmp_path):
    """El mismo agujero que R14a cerró para `status`, abierto en `strength` hasta hoy.

    Solo se comparaba contra el literal "vinculante", así que `vinculnte` no era un error:
    era una norma OBLIGATORIA degradada a sugerencia, en silencio y sin que nada lo notara.
    """
    with pytest.raises(NormError, match="desconocido"):
        mutando(tmp_path, lambda n: by_slug(n, "threshold_by_kind").update(strength="vinculnte"))


def test_R18_la_errata_sugiere_el_valor_correcto(tmp_path):
    with pytest.raises(NormError, match="precautorio"):
        mutando(tmp_path, lambda n: by_slug(n, "threshold_by_kind").update(strength="precautrio"))


def test_R18_precautorio_OBLIGA_pese_a_la_certeza_debil(tmp_path):
    """El caso que faltaba, y es real: un veto de seguridad.

    R1 dice "nada vinculante con certeza débil", y en general acierta. Pero un veto
    PRECAUTORIO obliga *precisamente porque* la evidencia es débil: no obliga porque
    sepamos que hace daño, sino porque **no sabemos que sea seguro**. Con solo dos
    valores, esas reglas tenían que escribirse `condicional` mientras el código las
    aplicaba a rajatabla — el registro describiendo mal lo que el motor hace, y en
    seguridad, que es donde menos se puede permitir.
    """
    r = mutando(tmp_path, lambda n: by_slug(n, "threshold_by_kind").update(
        strength="precautorio", precaution="alto impacto excéntrico sobre un tendón ya cargado"))
    assert r._norms["threshold_by_kind"].is_binding


def test_R18_precautorio_sin_decir_de_que_protege_no_se_construye(tmp_path):
    """La puerta de atrás obvia: vincular lo que sea con evidencia floja cambiando una palabra.

    El daño evitado es texto libre y nadie puede verificarlo, igual que `provenance_note`.
    Lo que sí consigue es obligar a NOMBRARLO, y que la afirmación quede en el diff donde
    alguien puede discutirla.
    """
    with pytest.raises(NormError, match="de qué daño protege"):
        mutando(tmp_path, lambda n: by_slug(n, "threshold_by_kind").update(strength="precautorio"))


def test_R18_precautorio_con_certeza_FUERTE_tampoco(tmp_path):
    """Si la evidencia sostiene la regla, es `vinculante` — y decirlo así informa más.

    Sin este rechazo `precautorio` se convertiría en el valor cómodo por defecto: obliga
    siempre y no exige nada. Queriendo decir exactamente "obliga porque NO sabemos que sea
    seguro", con certeza fuerte deja de ser cierto.
    """
    def mut(n):
        by_slug(n, "binding_high")["strength"] = "precautorio"
        by_slug(n, "binding_high")["precaution"] = "da igual lo que ponga aquí"
    with pytest.raises(NormError, match="es `vinculante`"):
        mutando(tmp_path, mut)


def test_R18_precaution_en_una_norma_que_no_es_precautoria_no_se_construye(tmp_path):
    """Simétrico a `provenance_note`: un campo que no aplica es una afirmación que engaña."""
    with pytest.raises(NormError, match="no es precautorio"):
        mutando(tmp_path, lambda n: by_slug(n, "threshold_by_kind").update(precaution="algo"))


def test_R18_is_binding_evita_que_el_consumidor_conozca_el_vocabulario():
    """El día que apareció `precautorio`, todo `if strength == "vinculante"` que hubiera por
    ahí dejó de ser correcto **y falló hacia el lado malo**: tratando un veto de seguridad
    como una sugerencia. `is_binding` existe para que ese `if` no haya que escribirlo.
    """
    norms = reg()._norms
    assert not norms["threshold_by_kind"].is_binding
    assert norms["binding_high"].is_binding


# ── v0.9.0 · el paquete deja de apagarse en silencio ────────────────────────────
#
# Los tres bugs que motivan esta versión eran EL MISMO: algo se desactiva y nada avisa.
# Y el más embarazoso es que R13 —"una clave desconocida no se construye"— llevaba desde
# la v0.4.0 protegiendo las normas y las ramas mientras el fichero que ENCIENDE Y APAGA
# reglas se tragaba cualquier cosa.

def test_una_ERRATA_en_schema_yaml_ya_no_apaga_reglas_en_silencio(tmp_path):
    """El caso real, medido en un consumidor: `evidence_certainty_field` escrito
    `evidence_certanty_field` hacía que el registro cargara igual, con R15b y R17
    **desactivadas**, sin un solo aviso. La regla que impide que una norma se declare más
    segura de lo que su fuente sostiene simplemente dejaba de existir.
    """
    import yaml as _yaml
    raw = _yaml.safe_load((FIX / "schema.yaml").read_text("utf-8"))
    raw["evidence_certanty_field"] = raw.pop("evidence_certainty_field")
    p = tmp_path / "schema.yaml"
    p.write_text(_yaml.safe_dump(raw, allow_unicode=True), "utf-8")
    with pytest.raises(NormError, match="claves desconocidas"):
        NormRegistry.load(norms_path=FIX / "norms.yaml", evidence_path=FIX / "evidence.yaml",
                          schema_path=p, today=HOY)


def test_el_mensaje_del_schema_SUGIERE_la_clave_correcta(tmp_path):
    """Un "clave desconocida" a secas obliga a ir a buscar la lista. La sugerencia es la
    diferencia entre arreglarlo en diez segundos y abrir el código del paquete."""
    import yaml as _yaml
    raw = _yaml.safe_load((FIX / "schema.yaml").read_text("utf-8"))
    raw["recency_horizonn"] = raw.pop("recency_horizon")
    p = tmp_path / "schema.yaml"
    p.write_text(_yaml.safe_dump(raw, allow_unicode=True), "utf-8")
    with pytest.raises(NormError, match=r"¿querías decir 'recency_horizon'\?"):
        NormRegistry.load(norms_path=FIX / "norms.yaml", evidence_path=FIX / "evidence.yaml",
                          schema_path=p, today=HOY)


def test_format_version_se_acepta_aunque_todavia_no_se_use(tmp_path):
    """Va declarada desde el día uno A PROPÓSITO: si se añadiera después, la comprobación
    de arriba la rechazaría — el gate nuevo mordiendo a la versión siguiente."""
    r = esquema(tmp_path, format_version=1)
    assert r._norms, "el registro tiene que cargar con `format_version` presente"


def test_una_ERRATA_en_un_campo_de_evidencia_no_pasa(tmp_path):
    """El cuarto sitio del mismo bug, y el peor de todos: `evidence.yaml` no validaba NADA.
    El día que exista un campo `verified`, un `verifed` haría que una entrada pareciera
    comprobada — en el único campo cuyo trabajo es decir que algo lo está.
    """
    import yaml as _yaml
    ev = _yaml.safe_load((FIX / "evidence.yaml").read_text("utf-8"))
    campo = _yaml.safe_load((FIX / "schema.yaml").read_text("utf-8"))["evidence_certainty_field"]
    ev[0][campo[:-1]] = ev[0].pop(campo)          # se come la última letra
    p = tmp_path / "evidence.yaml"
    p.write_text(_yaml.safe_dump(ev, allow_unicode=True), "utf-8")
    with pytest.raises(NormError, match="parecen una errata"):
        NormRegistry.load(norms_path=FIX / "norms.yaml", evidence_path=p,
                          schema_path=FIX / "schema.yaml", today=HOY)


def test_un_campo_de_evidencia_NUEVO_si_pasa(tmp_path):
    """La otra mitad, y es la que mantiene esto agnóstico: el vocabulario de la evidencia es
    del consumidor (§5.25). Un campo que NO se parece a ninguno declarado es vocabulario
    propio y tiene que entrar sin pedir permiso — si no, el paquete se estaría apropiando
    del esquema de datos de su inquilino."""
    import yaml as _yaml
    ev = _yaml.safe_load((FIX / "evidence.yaml").read_text("utf-8"))
    ev[0]["exact"] = "the quick brown fox"
    ev[0]["prefix"] = "…"
    ev[0]["revisado_por"] = "guille"
    p = tmp_path / "evidence.yaml"
    p.write_text(_yaml.safe_dump(ev, allow_unicode=True), "utf-8")
    r = NormRegistry.load(norms_path=FIX / "norms.yaml", evidence_path=p,
                          schema_path=FIX / "schema.yaml", today=HOY)
    assert r._norms, "un campo nuevo de evidencia no puede bloquear la carga"


def test_la_version_del_modulo_y_la_del_paquete_NO_pueden_divergir():
    """Estaban divergidas: `__version__` decía **0.7.0** con el wheel en **0.8.0**. Un
    consumidor que mire la versión para saber si puede usar una regla obtiene la respuesta
    equivocada — y el paquete lleva dos versiones mintiendo sobre sí mismo.

    ⚠️ La receta de PyPA es comparar contra `importlib.metadata`, y **aquí no vale**: el
    `conftest` inyecta `src/` a propósito (los tests miden ESTE repo), mientras
    `importlib.metadata` lee la copia INSTALADA. Comparar las dos cosas hace que el test
    falle siempre que el repo va por delante de la instalación, que es el estado normal
    mientras se desarrolla — un test que falla por el motivo equivocado se acaba borrando.
    La fuente de verdad del wheel es `pyproject.toml`, así que es contra eso.
    (La comprobación instalado-vs-declarado es del CONSUMIDOR, y allí ya existe.)
    """
    import re
    from pathlib import Path
    import capa_normativa

    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text("utf-8")
    declarada = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)
    assert capa_normativa.__version__ == declarada, (
        f"__init__.py dice {capa_normativa.__version__} y pyproject.toml dice {declarada}. "
        f"El wheel se construye con la de pyproject: el módulo mentiría a sus consumidores.")


# ── v0.9.0 · la forma CONSTANTE ─────────────────────────────────────────────────
#
# Medido en el primer inquilino: el 54 % de las normas no ramifica por nada. Escribían
# `when: {sex: any}` como peaje, y la dimensión se elegía a capricho (`sex` ×18, `event`
# ×12, `modality` ×8) — si el eje llevara información, no se podría elegir así.

def _const(tmp_path, **campos):
    """Una norma constante mínima, escrita en el YAML como se escribiría de verdad."""
    import yaml as _yaml
    base = {"slug": "cte", "title": "constante", "status": "vigente",
            "strength": "condicional", "certainty": "baja", "unit": "u",
            "semantics": "umbral", "expires": "2027-12-31", "evidence": ["EV-001"]}
    base.update(campos)
    base = {k: v for k, v in base.items() if v is not None}
    p = tmp_path / "norms.yaml"
    p.write_text(_yaml.safe_dump([base], allow_unicode=True), "utf-8")
    return NormRegistry.load(norms_path=p, evidence_path=FIX / "evidence.yaml",
                             schema_path=FIX / "schema.yaml", today=HOY)


def test_una_norma_puede_ser_UN_VALOR_sin_ramas(tmp_path):
    """Lo que compra la v0.9.0: procedencia y caducidad sin pagar una ramificación falsa."""
    r = _const(tmp_path, value=55.0)
    res = r.resolve("cte")
    assert res.value == 55.0 and res.evidence == ("EV-001",)
    assert r._norms["cte"].constant is True


def test_una_constante_NO_se_marca_como_sujeto_desconocido(tmp_path):
    """El arreglo semántico, y no es cosmético: sin él, el 54 % del registro respondería
    `is_fallback=True` — «he aplicado la rama del sujeto desconocido»— y `__str__` diría
    "(rama por defecto)". No es lo mismo *no te conozco* que *aquí no hay a quién conocer*:
    lo primero es un aviso de que falta un dato, y un aviso que sale siempre no avisa."""
    res = _const(tmp_path, value=55.0).resolve("cte")
    assert res.is_fallback is False
    assert res.matched == {}
    assert "rama por defecto" not in str(res)


def test_una_constante_SIGUE_sujeta_a_todas_las_reglas(tmp_path):
    """La forma nueva no puede ser una puerta de atrás. Se implementa SINTETIZANDO la rama,
    no salteándola, así que R4 y R15b miran exactamente lo mismo que antes."""
    with pytest.raises(NormError, match="sin evidencia"):
        _const(tmp_path, value=55.0, evidence=None)          # R4
    with pytest.raises(NormError, match="evidencia inexistente"):
        _const(tmp_path, value=55.0, evidence=["EV-NO-EXISTE"])
    with pytest.raises(NormError, match="MEJOR evidencia"):
        _const(tmp_path, value=55.0, certainty="alta")        # R15b
    with pytest.raises(NormError, match="no puede ser"):
        _const(tmp_path, value=55.0, certainty="sin_respaldo",
               provenance_note="x")                           # R4: sin_respaldo con evidencia


def test_constante_y_ramas_a_la_vez_no_se_construye(tmp_path):
    """O es una constante o ramifica. Las dos cosas es un estado ambiguo, y el registro no
    tiene que adivinar cuál gana."""
    with pytest.raises(NormError, match="no las dos"):
        _const(tmp_path, value=55.0,
               branches=[{"when": {"sex": "any"}, "value": 1.0, "evidence": ["EV-001"]}])


def test_una_norma_sin_valor_y_sin_ramas_sigue_sin_existir(tmp_path):
    """El guard de siempre, con el mensaje ampliado para nombrar la salida nueva."""
    with pytest.raises(NormError, match="sin ramas y sin `value`"):
        _const(tmp_path, evidence=None, branches=[])


def test_dos_ramas_con_when_VACIO_ya_no_se_pisan_en_silencio(tmp_path):
    """🔴 Bug VIVO hasta la v0.9.0, verificado antes de cerrarlo: dos ramas `when: {}` con
    valores 55.0 y 99.0 **cargaban**, y `resolve()` devolvía 99.0 — ganaba la última del
    fichero. R16d no las veía porque filtra con `if b.when`, y una rama vacía no es ni
    comodín ni concreta para ese filtro.

    Es exactamente lo que R16d existe para impedir (que el ORDEN decida el valor), en la
    forma que esta misma versión convierte en canónica. Cerrarlo iba PRIMERO."""
    with pytest.raises(NormError, match="`when` vacío"):
        _const(tmp_path, evidence=None,
               branches=[{"when": {}, "value": 55.0, "evidence": ["EV-001"]},
                         {"when": {}, "value": 99.0, "evidence": ["EV-001"]}])


def test_rama_sin_when_se_rechaza_como_when_vacio(tmp_path):
    """🔴 Bug VIVO hasta hoy: una rama que OMITE la clave `when` (no `when: {}`, la clave
    AUSENTE) produce el mismo `Branch.when == {}`, pero esquivaba la guarda —que exigía la
    clave PRESENTE y vacía— y también R16d (`if b.when`) y `concretas`. Con DOS así,
    `resolve()` devolvía 99.0: ganaba la última del fichero, el ORDEN decidía el valor. Es
    exactamente lo que la guarda de `when: {}` existe para impedir, en la forma que no miraba.

    Ahora se comprueba el `when` EFECTIVO: ausente o vacío es lo mismo. La única rama sin
    `when` legítima es la SINTÉTICA de la forma constante, y esa está exenta por `constante`."""
    # DOS ramas sin la clave `when`: antes cargaban y ganaba 99.0; ahora se rechazan.
    with pytest.raises(NormError, match="`when` vacío"):
        _const(tmp_path, evidence=None,
               branches=[{"value": 55.0, "evidence": ["EV-001"]},
                         {"value": 99.0, "evidence": ["EV-001"]}])
    # UNA sola rama sin `when` tampoco: es una constante escrita como rama, y serviría
    # marcada is_fallback=True en una norma que no tiene ni una rama comodín.
    with pytest.raises(NormError, match="`when` vacío"):
        _const(tmp_path, evidence=None,
               branches=[{"value": 55.0, "evidence": ["EV-001"]}])
    # La forma constante legítima (rama sintética sin `when`) SIGUE cargando: no es un
    # falso positivo de la guarda nueva.
    assert _const(tmp_path, value=55.0).resolve("cte").value == 55.0


def _dosis_por_edad(tmp_path, spec, con_comodin=True):
    """Registro autónomo con schema `[edad, sexo]` y una norma que ramifica por edad.

    El fixture del repo declara otras dimensiones (`kind`, `size`…), así que este bug
    —que vive en cómo se parsea la SPEC de un `when`— necesita su propio schema."""
    import yaml as _yaml
    schema = {
        "certainty_scale": ["alta", "moderada", "baja", "muy_baja", "sin_respaldo"],
        "weak_from": "baja",
        "unsupported_level": "sin_respaldo",
        "wildcards": ["unknown", "any"],
        "subject_dimensions": ["edad", "sexo"],
    }
    branches = [{"when": {"edad": spec}, "value": 10.0, "evidence": ["EV-001"]}]
    if con_comodin:
        branches.append({"when": {"edad": "any"}, "value": 40.0, "evidence": ["EV-001"]})
    norm = {"slug": "dosis", "title": "dosis por edad", "status": "vigente",
            "strength": "condicional", "certainty": "baja", "unit": "mg",
            "semantics": "umbral", "expires": "2027-12-31", "branches": branches}
    (tmp_path / "schema.yaml").write_text(_yaml.safe_dump(schema, allow_unicode=True), "utf-8")
    (tmp_path / "norms.yaml").write_text(_yaml.safe_dump([norm], allow_unicode=True), "utf-8")
    return NormRegistry.load(norms_path=tmp_path / "norms.yaml",
                             evidence_path=FIX / "evidence.yaml",
                             schema_path=tmp_path / "schema.yaml", today=HOY)


@pytest.mark.parametrize("spec", ["=>65", "> = 65", "≥65", ">=65kg", ">=1e3", "<>65"])
def test_operador_de_comparacion_mal_escrito_no_carga(tmp_path, spec):
    """🔴 Bug VIVO hasta hoy: un operador de comparación MAL escrito (`=>65`, una errata de
    un carácter) no cae en «operador inventado» —`_OPERATOR_CHARS` no incluía `<>=`— sino
    en «igualdad simple», y se guarda como el literal `"=>65"`. Esa rama no matchea NUNCA:
    `_range_match("70", "=>65")` es None, `"70" != "=>65"` y cae al comodín en silencio,
    devolviendo el valor del sujeto desconocido. Es el modo de fallo que R12 declara
    inaceptable, en la forma que no llegó a ser rango.

    Los signos unicode `≥65` no contienen ningún ASCII: añadir `<>=` no basta, por eso la
    guarda mira también `≥≤≠`."""
    with pytest.raises(NormError, match="comparación mal escrita"):
        _dosis_por_edad(tmp_path, spec)


@pytest.mark.parametrize("spec", [">=65", ">= 65"])
def test_comparacion_bien_escrita_discrimina(tmp_path, spec):
    """Control positivo: el arreglo no puede tragarse un rango legítimo. Con `>=65` la rama
    específica gana y NO es fallback — que es justo lo que el bug rompía silenciosamente."""
    res = _dosis_por_edad(tmp_path, spec).resolve("dosis", edad="70")
    assert res.value == 10.0 and res.is_fallback is False


@pytest.mark.parametrize("spec", ["<=100", "[10,100)", "65", "mujer", "(0,1]"])
def test_specs_validas_siguen_cargando(tmp_path, spec):
    """La guarda no puede volverse un falso positivo: rangos válidos, intervalos e
    igualdades literales (numéricas o de texto) siguen construyéndose sin queja."""
    assert _dosis_por_edad(tmp_path, spec) is not None


@pytest.mark.parametrize("spec", ["any", "unknown"])
def test_un_comodin_como_unica_rama_carga_y_es_fallback(tmp_path, spec):
    """El comodín como ÚNICA rama (sin una segunda rama comodín, que R16d rechazaría):
    carga y responde marcada `is_fallback=True`."""
    res = _dosis_por_edad(tmp_path, spec, con_comodin=False).resolve("dosis", edad="70")
    assert res.is_fallback is True


def test_requires_sigue_siendo_imposible_en_una_constante(tmp_path):
    """No hace falta tocar nada: R7 ya exige que lo declarado en `requires` sea una
    dimensión por la que alguna rama ramifique. Sin ramas, no hay ninguna. El caso feo
    se cae solo, y conviene que quede fijado."""
    with pytest.raises(NormError, match="ninguna rama ramifica"):
        _const(tmp_path, value=55.0, requires=["sex"])


def test_una_constante_puede_llevar_NOTE(tmp_path):
    """Lo cazó la migración real del primer inquilino, no la lectura: `note` estaba en
    `_BRANCH_KEYS` y no en `_NORM_KEYS`, así que al subir una constante a la forma nueva su
    nota —el porqué del número— era una clave desconocida y el registro no cargaba.

    Y la nota importa más aquí que en una rama: en una constante es lo ÚNICO que queda del
    razonamiento, porque ya no hay un `when` que explique a qué caso aplica."""
    r = _const(tmp_path, value=55.0, note="por esto y por lo otro")
    assert r._norms["cte"].branches[0].note == "por esto y por lo otro"
