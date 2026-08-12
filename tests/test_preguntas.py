"""Tests de PRG — el detector de F13, con la disciplina F14.

Los casos rojos vienen del caso real (el TDEE con dos productores) y de las reglas que se
midieron esta sesión, no de la imaginación.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from capa_normativa.vigilante.preguntas import CLASES, revisar_preguntas


def _repo(tmp_path: Path, ficheros: dict[str, str]) -> Path:
    for nombre, contenido in ficheros.items():
        p = tmp_path / nombre
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenido, encoding="utf-8")
    return tmp_path


def _cods(hs) -> set[str]:
    return {h.codigo for h in hs}


# El caso real, reducido: la autoridad y un bypass que la esquiva.
CATALOGO = {
    "tdee": {
        "autoridad": "daily_plan.tdee_kcal",
        "tope": 2,
        "productores": [
            {"sitio": "sync/garmin.py:10", "ancla": "compute_tdee(", "clase": "fuente",
             "nota": "escribe la autoridad"},
            {"sitio": "api/chat.py:20", "ancla": "total_kcal_day", "clase": "productor",
             "nota": "BYPASS: Garmin crudo rotulado TDEE"},
        ],
    }
}
CODIGO = {
    "sync/garmin.py": "def sync():\n    x = compute_tdee(a, b)\n",
    "api/chat.py": "def prompt(stats):\n    return stats['total_kcal_day']\n",
}


def test_un_catalogo_coherente_solo_avisa_del_tope_flojo(tmp_path: Path):
    """1 productor declarado contra un tope de 2: el tope está flojo y hay que bajarlo."""
    hs = revisar_preguntas(_repo(tmp_path, CODIGO), CATALOGO)
    assert _cods(hs) == {"PRG005"}, [str(h) for h in hs]


def test_al_ras_no_hay_ningun_hallazgo(tmp_path: Path):
    cat = {**CATALOGO, "tdee": {**CATALOGO["tdee"], "tope": 1}}
    assert revisar_preguntas(_repo(tmp_path, CODIGO), cat) == []


# ── PRG001 · el ancla que ya no está: la clase de fallo nº1 ──

def test_PRG001_SALTA_si_el_ancla_desaparece(tmp_path: Path):
    """Un catálogo de productores envejece como cualquier documento. Sin esta comprobación,
    afirma algo que su fuente ya no sostiene."""
    codigo = dict(CODIGO)
    codigo["api/chat.py"] = "def prompt(plan):\n    return plan['tdee_kcal']\n"   # ya no lee Garmin
    assert "total_kcal_day" not in codigo["api/chat.py"], "la mutación NO entró"

    hs = revisar_preguntas(_repo(tmp_path, codigo), {**CATALOGO, "tdee": {**CATALOGO["tdee"], "tope": 1}})
    assert "PRG001" in _cods(hs)
    assert any("BAJA el tope" in h.arreglo for h in hs if h.codigo == "PRG001")


def test_PRG001_SALTA_si_el_fichero_ya_no_existe(tmp_path: Path):
    codigo = {k: v for k, v in CODIGO.items() if k != "api/chat.py"}
    assert "api/chat.py" not in codigo, "la mutación NO entró"
    hs = revisar_preguntas(_repo(tmp_path, codigo), {**CATALOGO, "tdee": {**CATALOGO["tdee"], "tope": 1}})
    assert "PRG001" in _cods(hs)


# ── PRG002 · el trinquete de productores ──

def test_PRG002_SALTA_si_los_productores_SUPERAN_el_tope(tmp_path: Path):
    """El criterio de legitimidad acordado: una capa nueva vale solo si ABSORBE productores."""
    cat = {"tdee": {**CATALOGO["tdee"], "tope": 1}}
    cat["tdee"]["productores"] = CATALOGO["tdee"]["productores"] + [
        {"sitio": "api/otro.py:5", "ancla": "tdee_a_mano", "clase": "productor"}]
    codigo = {**CODIGO, "api/otro.py": "v = tdee_a_mano()\n"}

    hs = revisar_preguntas(_repo(tmp_path, codigo), cat)
    assert "PRG002" in _cods(hs)
    tri = next(h for h in hs if h.codigo == "PRG002")
    assert "no subas el tope" in tri.arreglo and "VISIBLE" in tri.arreglo, (
        "debe forzar a distinguir «crecio la deuda» de «dejo de estar ciego»")


def test_una_FUENTE_no_cuenta_para_el_tope(tmp_path: Path):
    """Varias fuentes que escriben la autoridad son SANAS —es una cascada con su etiqueta—.
    Solo los bypass cuentan. Confundirlo haría el tope imposible de cumplir."""
    cat = {"tdee": {"autoridad": "daily_plan.tdee_kcal", "tope": 0, "productores": [
        {"sitio": "sync/garmin.py:10", "ancla": "compute_tdee(", "clase": "fuente"},
        {"sitio": "sync/garmin.py:11", "ancla": "compute_tdee(", "clase": "mutador"},
        {"sitio": "sync/garmin.py:12", "ancla": "compute_tdee(", "clase": "latente"},
    ]}}
    assert revisar_preguntas(_repo(tmp_path, CODIGO), cat) == [], (
        "fuente/mutador/latente no son bypass: no pueden hacer fallar el tope")


# ── PRG004 · sin autoridad: el patrón B ──

def test_PRG004_SALTA_si_la_pregunta_no_tiene_AUTORIDAD(tmp_path: Path):
    """3 de las 9 preguntas del primer inquilino están así. No es un error, pero no puede
    quedar implícito: sin autoridad, el tope no tiene contra qué medir."""
    cat = {"tendencia_peso": {"tope": 6, "productores": []}}
    hs = revisar_preguntas(_repo(tmp_path, CODIGO), cat)
    assert "PRG004" in _cods(hs)
    assert any("patrón B" in h.arreglo or "autoridad" in h.arreglo for h in hs)


# ── PRG003 · candidatos, informativo a propósito ──

def test_PRG003_propone_candidatos_sin_declarar(tmp_path: Path):
    codigo = {**CODIGO, "engine/otro_tdee.py": "def compute_tdee_v2():\n    return 1\n"}
    cat = {"tdee": {**CATALOGO["tdee"], "tope": 1, "senales": ["compute_tdee"]}}

    hs = revisar_preguntas(_repo(tmp_path, codigo), cat)
    prg3 = [h for h in hs if h.codigo == "PRG003"]
    assert prg3, "no propuso el candidato"
    assert "otro_tdee.py" in prg3[0].mensaje
    assert "INFORMATIVO" in prg3[0].arreglo, "debe declararse informativo, no acusatorio"


def test_PRG003_no_propone_lo_YA_declarado(tmp_path: Path):
    cat = {"tdee": {**CATALOGO["tdee"], "tope": 1, "senales": ["compute_tdee", "total_kcal_day"]}}
    hs = revisar_preguntas(_repo(tmp_path, CODIGO), cat)
    assert "PRG003" not in _cods(hs), "los declarados no son candidatos"


def test_PRG003_no_mira_dentro_de_venv_ni_node_modules(tmp_path: Path):
    codigo = {**CODIGO,
              "venv/lib/x.py": "compute_tdee()\n",
              "node_modules/p/y.ts": "compute_tdee()\n"}
    cat = {"tdee": {**CATALOGO["tdee"], "tope": 1, "senales": ["compute_tdee"]}}
    assert "PRG003" not in _cods(revisar_preguntas(_repo(tmp_path, codigo), cat))


def test_sin_senales_no_propone_nada(tmp_path: Path):
    """Las señales son opcionales: sin ellas el detector sigue valiendo para lo declarado."""
    codigo = {**CODIGO, "engine/otro.py": "compute_tdee()\n"}
    cat = {"tdee": {**CATALOGO["tdee"], "tope": 1}}
    assert "PRG003" not in _cods(revisar_preguntas(_repo(tmp_path, codigo), cat))


# ── contrato ──

def test_una_clase_desconocida_revienta_y_DICE_las_validas(tmp_path: Path):
    cat = {"tdee": {"autoridad": "x", "tope": 1,
                    "productores": [{"sitio": "a.py:1", "ancla": "x", "clase": "inventada"}]}}
    with pytest.raises(ValueError, match="clase `inventada`"):
        revisar_preguntas(_repo(tmp_path, CODIGO), cat)


def test_las_clases_son_las_del_paso_0():
    assert set(CLASES) == {"productor", "fuente", "mutador", "latente"}


def test_el_catalogo_puede_venir_de_un_YAML(tmp_path: Path):
    repo = _repo(tmp_path, CODIGO)
    y = tmp_path / "preguntas.yaml"
    y.write_text(
        "tdee:\n"
        "  autoridad: daily_plan.tdee_kcal\n"
        "  tope: 1\n"
        "  productores:\n"
        "    - sitio: api/chat.py:20\n"
        "      ancla: total_kcal_day\n"
        "      clase: productor\n", encoding="utf-8")
    assert revisar_preguntas(repo, y) == []


def test_todo_hallazgo_dice_que_hacer(tmp_path: Path):
    cat = {"q": {"tope": 0, "productores": [
        {"sitio": "no_existe.py:1", "ancla": "x", "clase": "productor"}]}}
    hs = revisar_preguntas(_repo(tmp_path, CODIGO), cat)
    assert hs
    for h in hs:
        assert h.detector == "preguntas"
        assert len(h.arreglo) > 30, f"{h.codigo}: el arreglo es demasiado vago"


def test_ROJO_PRG003_no_mira_dentro_de_worktrees_ni_arboles_paralelos(tmp_path: Path):
    """CASO ROJO MEDIDO (2026-08-11): en la primera corrida sobre el repo real, el detector
    propuso 50 candidatos y los primeros eran COPIAS del propio repo dentro de
    `.claude/worktrees/`. Un candidato que es una copia de un fichero ya declarado no es señal,
    es ruido — y el ruido apaga detectores."""
    codigo = {**CODIGO,
              ".claude/worktrees/copia/api/chat.py": "compute_tdee()\n",
              "_archivo_viejo/x.py": "compute_tdee()\n",
              "obs-fix/y.py": "compute_tdee()\n"}
    cat = {"tdee": {**CATALOGO["tdee"], "tope": 1, "senales": ["compute_tdee"]}}
    hs = revisar_preguntas(_repo(tmp_path, codigo), cat)
    assert "PRG003" not in _cods(hs), f"propuso ruido de árboles paralelos: {[h.mensaje for h in hs]}"
