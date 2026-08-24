"""`escaparate-sin-rutas-de-casa` cambia de color de verdad, en las dos direcciones.

Un comprobador que sólo se ha visto en rojo no está comprobado: podría estar rojo por estar roto.
Y uno que sólo se ha visto en verde es peor, porque el verde es la respuesta que nadie mira.

Aquí se fuerzan las dos sobre repos de mentira montados en un temporal, sin tocar los de verdad.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "scripts" / "aceptaciones" / "escaparate_sin_rutas_de_casa.py"


def _modulo():
    if not GUION.is_file():
        pytest.skip("no existe escaparate_sin_rutas_de_casa.py")
    spec = importlib.util.spec_from_file_location("esc_rutas_bajo_prueba", str(GUION))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _repo_falso(base: Path, contenido: str) -> Path:
    """Un repo git de verdad —hace falta, porque el comprobador usa `git ls-files`— con un fichero."""
    d = base / "repo_de_mentira"
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(d), capture_output=True, timeout=120)
    (d / "codigo.py").write_text(contenido, encoding="utf-8")
    subprocess.run(["git", "add", "codigo.py"], cwd=str(d), capture_output=True, timeout=120)
    return d


@pytest.fixture()
def mod_y_repo(tmp_path, monkeypatch):
    mod = _modulo()
    return mod, tmp_path


def test_rojo_cuando_un_repo_publico_lleva_la_ruta(mod_y_repo, monkeypatch):
    """La dirección que importa: si hay una ruta de casa publicada, NO puede salir verde."""
    mod, tmp = mod_y_repo
    usuario = Path.home().name
    repo = _repo_falso(tmp, f'RUTA = r"C:/Users/{usuario}/proyectos/algo"\n')
    monkeypatch.setattr(mod, "publicos", lambda: [repo])

    ok, msg = mod.escaparate_sin_rutas_de_casa()
    assert not ok, "hay una ruta de casa en un repo publico y ha salido VERDE"
    # El motivo tiene que decir de QUE LADO esta, porque de eso depende el precio del arreglo:
    # antes de empujar es una reescritura local, despues es un force-push sobre historia publica.
    assert "EMPUJADO" in msg.upper(), f"el motivo no dice de que lado esta: {msg}"


def test_verde_cuando_no_la_lleva(mod_y_repo, monkeypatch):
    """La otra dirección: sin rutas, tiene que poder cerrarse. Si no, el rojo no significa nada."""
    mod, tmp = mod_y_repo
    repo = _repo_falso(tmp, 'RUTA = Path.home() / "proyectos" / "algo"\n')
    monkeypatch.setattr(mod, "publicos", lambda: [repo])

    ok, msg = mod.escaparate_sin_rutas_de_casa()
    assert ok, f"no hay ninguna ruta de casa y ha salido ROJO: {msg}"


def test_cero_repos_publicos_es_rojo(mod_y_repo, monkeypatch):
    """No haber podido mirar NUNCA es «esta limpio». Una lista vacia es sospechosa, no limpia."""
    mod, _ = mod_y_repo
    monkeypatch.setattr(mod, "publicos", lambda: [])
    ok, msg = mod.escaparate_sin_rutas_de_casa()
    assert not ok and "cero repos" in msg


def test_si_no_se_puede_preguntar_es_rojo(mod_y_repo, monkeypatch):
    """Si `gh` no contesta, tampoco. Es la misma trampa con otra cara."""
    mod, _ = mod_y_repo

    def explota():
        raise mod.NoSePudoMirar("gh no contesta")

    monkeypatch.setattr(mod, "publicos", explota)
    ok, msg = mod.escaparate_sin_rutas_de_casa()
    assert not ok and "no se pudo mirar" in msg


def test_el_usuario_se_deriva_y_no_esta_escrito():
    """Una constante con el nombre de G seria falsa en cualquier otra maquina, y el comprobador
    pasaria a ser decoracion sin que nadie lo notara."""
    fuente = GUION.read_text(encoding="utf-8")
    cuerpo = fuente.split('"""', 2)[-1]  # sin el docstring, que SI cita el caso medido
    assert "Path.home().name" in cuerpo, "el usuario tiene que derivarse de Path.home()"
