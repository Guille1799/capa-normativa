"""El censo de guardianes: que enumere de verdad, y que NO apruebe por no haber podido mirar.

Los dos tests que importan de verdad son los de contar de MENOS, porque ése es el fallo que este
comprobador tiene prohibido: un censo que cuadra mientras un guardián está muerto es peor que no
tener censo, porque además tranquiliza.

Los dos salieron de fallos reales cometidos escribiéndolo el 2026-08-24:

  · `command: "python"` con el guion en `args`: cinco guardianes distintos de G
    (`prompt_router`, `doc_decision_gate`, `promesa_gate`, `vigilante_pre_commit`,
    `autohealth_monitor`) se colapsaban en un único `hook:usuario:python`.
  · PowerShell devolviendo cero tareas se leía como «no hay tareas» en vez de «no pude preguntar».
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parent.parent / "scripts" / "aceptaciones" / "censo_de_guardianes.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("censo_bajo_prueba", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _settings(tmp_path: Path, hooks: dict) -> Path:
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    return f


# --- contar de MENOS: los dos fallos reales ---------------------------------


def test_dos_hooks_con_el_guion_en_args_son_dos_guardianes(tmp_path):
    """El fallo original: mirar sólo `command` los hacía uno solo, y uno podía morirse en silencio."""
    m = _cargar()
    f = _settings(tmp_path, {"Stop": [{"hooks": [
        {"command": "python", "args": ["C:/x/.claude/hooks/doc_decision_gate.py"]},
        {"command": "python", "args": ["C:/x/.claude/hooks/promesa_gate.py"]},
    ]}]})
    ids = m._hooks_de(f, "usuario")
    assert len(set(ids)) == 2, f"se colapsaron en {set(ids)}"
    assert "hook:usuario:doc_decision_gate.py" in ids
    assert "hook:usuario:promesa_gate.py" in ids


def test_el_guion_dentro_de_command_tambien_se_ve(tmp_path):
    m = _cargar()
    f = _settings(tmp_path, {"SessionStart": [{"hooks": [
        {"command": "python C:/x/.claude/hooks/inject_context.py"},
    ]}]})
    assert m._hooks_de(f, "usuario") == ["hook:usuario:inject_context.py"]


def test_una_fuente_que_no_contesta_es_ROJO_y_no_menos_guardianes(monkeypatch):
    """«No pude preguntar» no es «no hay». Es la trampa que el arnés existe para prohibir."""
    m = _cargar()

    def revienta():
        raise m.FuenteRota("el Programador no contesta")

    monkeypatch.setattr(m, "_tareas_programadas", revienta)
    ok, msg = m.censo_de_guardianes()
    assert ok is False
    assert "no se pudo enumerar" in msg
    assert "Programador" in msg


def test_cero_guardianes_es_ROJO_aunque_el_censo_este_impecable(monkeypatch):
    m = _cargar()
    monkeypatch.setattr(m, "guardianes", lambda: ([], []))
    ok, msg = m.censo_de_guardianes()
    assert ok is False
    assert "0 guardianes" in msg


# --- la ficha: qué cuenta como descrito -------------------------------------


def _con_censo(m, tmp_path: Path, texto: str, vivos: list[str], monkeypatch):
    censo = tmp_path / "GUARDIANES.md"
    censo.write_text(texto, encoding="utf-8")
    monkeypatch.setattr(m, "CENSO", censo)
    monkeypatch.setattr(m, "guardianes", lambda: (vivos, []))
    return m.censo_de_guardianes()


FICHA_BUENA = """# Censo

## `tarea:ralph-cn`
**Tipo:** ejecuta
**Si muere:** capa-normativa se queda sin tandas nocturnas y el tablero no avanza solo.
"""


def test_verde_cuando_cada_vivo_tiene_su_ficha(tmp_path, monkeypatch):
    m = _cargar()
    ok, msg = _con_censo(m, tmp_path, FICHA_BUENA, ["tarea:ralph-cn"], monkeypatch)
    assert ok is True, msg


def test_una_cabecera_sin_si_muere_no_cuenta(tmp_path, monkeypatch):
    """Aprobar en vacío, en su forma documental: la cabecera está, el contenido no."""
    m = _cargar()
    texto = "# Censo\n\n## `tarea:ralph-cn`\n**Tipo:** ejecuta\n"
    ok, msg = _con_censo(m, tmp_path, texto, ["tarea:ralph-cn"], monkeypatch)
    assert ok is False
    assert "Si muere" in msg


def test_un_si_muere_demasiado_corto_no_cuenta(tmp_path, monkeypatch):
    m = _cargar()
    texto = "# Censo\n\n## `tarea:ralph-cn`\n**Tipo:** ejecuta\n**Si muere:** nada.\n"
    ok, msg = _con_censo(m, tmp_path, texto, ["tarea:ralph-cn"], monkeypatch)
    assert ok is False
    assert "consecuencia" in msg


def test_sin_tipo_no_cuenta(tmp_path, monkeypatch):
    m = _cargar()
    texto = ("# Censo\n\n## `tarea:ralph-cn`\n"
             "**Si muere:** capa-normativa se queda sin tandas nocturnas y nadie lo nota.\n")
    ok, msg = _con_censo(m, tmp_path, texto, ["tarea:ralph-cn"], monkeypatch)
    assert ok is False
    assert "Tipo" in msg


def test_un_guardian_nuevo_pone_el_censo_ROJO_solo(tmp_path, monkeypatch):
    """Lo que hace que el censo no envejezca: la lista sale de las fuentes, no del documento."""
    m = _cargar()
    ok, _ = _con_censo(m, tmp_path, FICHA_BUENA, ["tarea:ralph-cn"], monkeypatch)
    assert ok is True
    ok, msg = _con_censo(m, tmp_path, FICHA_BUENA,
                         ["tarea:ralph-cn", "tarea:recien-instalada"], monkeypatch)
    assert ok is False
    assert "tarea:recien-instalada" in msg


def test_el_censo_puede_tener_de_mas(tmp_path, monkeypatch):
    """`OllamaServe` no lo enumera el criterio, pero describirlo no puede poner nada rojo."""
    m = _cargar()
    texto = FICHA_BUENA + "\n## `tarea:OllamaServe`\n**Tipo:** sirve\n**Si muere:** la cadena de validacion con Ollama deja de responder.\n"
    ok, msg = _con_censo(m, tmp_path, texto, ["tarea:ralph-cn"], monkeypatch)
    assert ok is True, msg


# --- la máquina de verdad ----------------------------------------------------


@pytest.mark.maquina
def test_contra_la_maquina_real_enumera_las_cuatro_familias():
    """Sin fixtures: si aquí sale una familia a cero, la fuente se rompió."""
    m = _cargar()
    vivos, rotas = m.guardianes()
    assert not rotas, f"fuentes que no se pudieron enumerar: {rotas}"
    familias = {g.split(":")[0] for g in vivos}
    assert familias == {"hook", "tarea", "pre-commit", "tablero"}, familias
    for familia in familias:
        assert sum(1 for g in vivos if g.startswith(familia + ":")) >= 5, f"{familia} sospechosamente vacia"
