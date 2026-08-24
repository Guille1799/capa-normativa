"""El despachador de hooks: un hook por evento que decide qué corre en cada proyecto.

Existe para poder activar `allowManagedHooksOnly` (CVE-2025-59536) sin perder los hooks de
proyecto. Los tests que más importan son dos, y los dos son de **no fallar en silencio**:

  · una tabla ilegible NO puede leerse como «este repo no tiene hooks», porque eso apagaría todos
    los guardianes de proyecto sin que nada lo dijera;
  · el código de salida que se propaga es el PEOR, no el último: un hook que bloquea no puede
    quedar tapado por otro que pasa después.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks" / "despachador.py"
pytestmark = pytest.mark.skipif(not MODULO.is_file(),
                                reason="el despachador no esta instalado en proyectos/.claude/hooks")


def _cargar(tmp_path=None):
    spec = importlib.util.spec_from_file_location("despachador_bajo_prueba", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- a quien delega ----------------------------------------------------------


def test_un_repo_SIN_entrada_no_ejecuta_nada():
    """El caso de un repositorio recién clonado: sin entrada en la tabla, sin hooks de proyecto.
    Que es exactamente lo que se quiere."""
    m = _cargar()
    assert m.hooks_de("Stop", "repo-que-nadie-conoce", tabla={}) == []


def test_un_repo_CON_entrada_recibe_los_suyos():
    m = _cargar()
    tabla = {"mi-repo": {"Stop": [["python", "guardia.py"]]}}
    assert m.hooks_de("Stop", "mi-repo", tabla=tabla) == [["python", "guardia.py"]]


def test_los_hooks_de_OTRO_repo_no_se_cuelan():
    """El fallo que este despachador existe para impedir: con las rutas absolutas de mcp en un
    fichero global, su gate de MRR correría dentro de ponerse_wenorro."""
    m = _cargar()
    tabla = {"mcp_smart_context": {"Stop": [["python", "stop_gate_mcp.py"]]}}
    assert m.hooks_de("Stop", "ponerse_wenorro", tabla=tabla) == []


def test_cada_evento_recibe_solo_lo_suyo():
    m = _cargar()
    tabla = {"r": {"Stop": [["a"]], "PreToolUse": [["b"]]}}
    assert m.hooks_de("Stop", "r", tabla=tabla) == [["a"]]
    assert m.hooks_de("PreToolUse", "r", tabla=tabla) == [["b"]]


def test_sin_repo_conocido_no_hay_hooks():
    m = _cargar()
    assert m.hooks_de("Stop", None, tabla={"r": {"Stop": [["a"]]}}) == []


# --- de dónde deduce el repo -------------------------------------------------


def test_el_repo_se_deduce_TAMBIEN_desde_un_worktree(monkeypatch, tmp_path):
    """Un worktree vive en `<repo>/.claude/worktrees/<x>`. Sin subir hasta el hijo directo de la
    carpeta de proyectos, un agente encerrado en un worktree se quedaría sin los hooks de su repo."""
    m = _cargar()
    raiz = tmp_path / "proyectos"
    hondo = raiz / "mi-repo" / ".claude" / "worktrees" / "xyz"
    hondo.mkdir(parents=True)
    monkeypatch.setattr(m, "RAIZ_PROYECTOS", raiz)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(hondo))
    assert m._repo_abierto() == "mi-repo"


def test_un_directorio_de_FUERA_no_es_ningun_repo(monkeypatch, tmp_path):
    m = _cargar()
    raiz = tmp_path / "proyectos"
    raiz.mkdir()
    fuera = tmp_path / "otra-parte"
    fuera.mkdir()
    monkeypatch.setattr(m, "RAIZ_PROYECTOS", raiz)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(fuera))
    assert m._repo_abierto() is None


# --- no fallar en silencio ---------------------------------------------------


def test_una_tabla_ILEGIBLE_no_se_lee_como_sin_hooks(monkeypatch, tmp_path):
    """La trampa cara: si un JSON roto devolviera `{}`, todos los guardianes de proyecto quedarían
    apagados y desde fuera se vería igual que «este repo no tiene»."""
    m = _cargar()
    rota = tmp_path / "hooks_por_repo.json"
    rota.write_text("{ esto no es json", encoding="utf-8")
    monkeypatch.setattr(m, "TABLA", rota)
    with pytest.raises(Exception):
        m._tabla()


def test_una_tabla_que_NO_existe_si_es_vacia(monkeypatch, tmp_path):
    """Distinto del anterior a propósito: «no hay tabla» es un estado legítimo (máquina nueva);
    «hay tabla y no se puede leer» es una avería."""
    m = _cargar()
    monkeypatch.setattr(m, "TABLA", tmp_path / "no_existe.json")
    assert m._tabla() == {}


def test_se_propaga_el_PEOR_codigo_no_el_ultimo(monkeypatch, tmp_path):
    """Un hook que bloquea no puede quedar tapado por otro que pasa después."""
    m = _cargar()
    bloquea = tmp_path / "bloquea.py"
    bloquea.write_text("import sys; sys.exit(2)\n", encoding="utf-8")
    pasa = tmp_path / "pasa.py"
    pasa.write_text("import sys; sys.exit(0)\n", encoding="utf-8")
    tabla = {"r": {"Stop": [[sys.executable, str(bloquea)], [sys.executable, str(pasa)]]}}
    monkeypatch.setattr(m, "_tabla", lambda: tabla)
    monkeypatch.setattr(m, "_repo_abierto", lambda: "r")
    monkeypatch.setattr(m.sys, "stdin", type("F", (), {"read": staticmethod(lambda: "")})())
    assert m.main(["--evento", "Stop"]) == 2


def test_sin_evento_no_adivina():
    m = _cargar()
    assert m.main([]) == 2


def test_la_tabla_real_cubre_los_repos_con_hooks():
    """Sin fixtures: la tabla generada tiene que conocer a los cuatro repos que hoy declaran hooks.
    Si alguien añade hooks a un repo y no regenera la tabla, este test lo canta."""
    m = _cargar()
    if not m.TABLA.is_file():
        pytest.skip("la tabla aun no se ha generado en esta maquina")
    t = m._tabla()
    repos = {k for k in t if not k.startswith("_")}
    raiz = m.RAIZ_PROYECTOS
    con_hooks = set()
    for s in raiz.glob("*/.claude/settings.json"):
        try:
            d = json.loads(s.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if d.get("hooks"):
            con_hooks.add(s.parent.parent.name)
    faltan = con_hooks - repos
    assert not faltan, f"repos con hooks que la tabla no conoce: {sorted(faltan)}"
