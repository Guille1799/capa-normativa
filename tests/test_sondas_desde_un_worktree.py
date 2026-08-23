"""Las dos sondas que miran FUERA del repo tienen que encontrar su fichero desde un worktree.

`registro_sin_caducados()` abre `REGISTRO.md` y `revista_de_runtimes()` ejecuta
`.claude/hooks/revista_runtimes.py`. Los dos ficheros viven en la carpeta que CONTIENE los
repos, y los dos se resolvian con `RAIZ.parent`. Eso es verdad desde el checkout principal
—`proyectos/capa-normativa` -> `proyectos`— y MENTIRA desde un worktree, donde `RAIZ` es
`capa-normativa/.claude/worktrees/<x>` y `RAIZ.parent` es `.../worktrees`, una carpeta donde no
hay ni registro ni hooks.

Medido el 2026-08-23 antes de tocar nada: la MISMA sonda, el MISMO commit, VERDE desde el
checkout principal y ROJA desde el worktree de al lado con «no existe REGISTRO.md». Ese rojo no
habla de la promesa, habla de DONDE SE CORRIO — el instrumento tumbando la medida, la misma
familia que el `GIT_DIR` que secuestro a los detectores.

⚠️ El mundo de estos tests es un worktree DE VERDAD (`git worktree add`), no un `tmp_path` con
la forma parecida. El arreglo consiste en preguntarle a git donde esta el checkout principal, asi
que un decorado sin git no probaria nada: pasaria por el camino de emergencia y no por el que se
usa. Y por eso tampoco se toca el `RAIZ` real — se le inyecta uno de pega.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
GUION = RAIZ / "scripts" / "aceptacion.py"

#: Lo que crea `_mundo`. La marca no es adorno: es como el guion de pega comprueba su `cwd` sin
#: comparar cadenas de ruta, que en Windows se escriben de varias formas para el mismo sitio
#: (mayusculas, nombres 8.3, enlaces de %TEMP%) y darian falsos rojos.
MARCA = ".es-la-carpeta-de-proyectos"


def _tablero():
    """El tablero cargado como modulo suelto, para poder inyectarle un `RAIZ` de pega."""
    spec = importlib.util.spec_from_file_location("tablero_bajo_prueba", str(GUION))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _git(*a, **k):
    import subprocess
    r = subprocess.run(["git", *a], capture_output=True, text=True, timeout=120, **k)
    if r.returncode != 0:
        raise RuntimeError("git " + " ".join(a) + " -> " + r.stderr.strip())
    return r


@pytest.fixture
def mundo(tmp_path):
    """`<tmp>/proyectos/` con un repo dentro y un worktree ANIDADO, como el de verdad.

    La anidacion importa: el worktree cuelga de `<repo>/.claude/worktrees/<x>`, que es la
    disposicion real de estos repos y la que hace que `RAIZ.parent` se salga por arriba a una
    carpeta intermedia en vez de a la carpeta de proyectos.
    """
    proyectos = tmp_path / "proyectos"
    repo = proyectos / "repo-de-pega"
    repo.mkdir(parents=True)
    (proyectos / MARCA).write_text("", encoding="utf-8")
    _git("init", "-q", str(repo))
    (repo / "algo.txt").write_text("x", encoding="utf-8")
    _git("-C", str(repo), "add", "-A")
    _git("-C", str(repo), "-c", "user.email=t@local", "-c", "user.name=t",
         "commit", "-qm", "raiz")
    arbol = repo / ".claude" / "worktrees" / "simulado"
    _git("-C", str(repo), "worktree", "add", "-q", "--detach", str(arbol))
    return proyectos, arbol


def test_el_registro_se_encuentra_TAMBIEN_desde_un_worktree(mundo, monkeypatch):
    """Con `RAIZ.parent` esta sonda contesta «no existe REGISTRO.md» y el rojo es del sitio.

    Se comprueban las dos mitades: que NO sale la rama de «no existe» —el sintoma exacto que se
    midio— y que ademas el veredicto es el del registro bueno. La segunda hace falta porque un
    arreglo que se limitara a callar el mensaje pasaria la primera.
    """
    proyectos, arbol = mundo
    (proyectos / "REGISTRO.md").write_text(
        "# REGISTRO" + chr(10)
        + "llegada la fecha de CADUCA, o hay SENAL DE USO, o la cosa se quita" + chr(10) * 2
        + "## una entrada viva" + chr(10)
        + "CADUCA: 2099-12-31" + chr(10)
        + "ESTADO: en uso" + chr(10),
        encoding="utf-8")
    m = _tablero()
    monkeypatch.setattr(m, "RAIZ", arbol)
    ok, motivo = m.registro_sin_caducados()
    assert "no existe" not in motivo, motivo
    assert ok, motivo


def test_la_revista_se_encuentra_Y_CORRE_desde_un_worktree(mundo, monkeypatch):
    """Cubre los dos usos de la sonda: donde busca el guion y desde donde lo ejecuta.

    El guion de pega solo sale con 0 si su `cwd` es la carpeta de proyectos, asi que el verde no
    se puede conseguir arreglando solo la ruta del fichero: `cwd=` tenia el mismo defecto y se
    habria quedado atras sin que nadie se enterara.
    """
    proyectos, arbol = mundo
    hooks = proyectos / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "revista_runtimes.py").write_text(
        "import os, sys" + chr(10)
        + "if os.path.exists(" + repr(MARCA) + "):" + chr(10)
        + "    print('la revista corrio desde la carpeta de proyectos')" + chr(10)
        + "    sys.exit(0)" + chr(10)
        + "print('cwd equivocado: ' + os.getcwd())" + chr(10)
        + "sys.exit(1)" + chr(10),
        encoding="utf-8")
    m = _tablero()
    monkeypatch.setattr(m, "RAIZ", arbol)
    ok, motivo = m.revista_de_runtimes()
    assert "no existe" not in motivo, motivo
    assert ok, motivo


def test_desde_el_checkout_PRINCIPAL_sigue_saliendo_lo_mismo(mundo, monkeypatch):
    """El control. Un arreglo que rompiera el caso que HOY funciona no seria un arreglo.

    Aqui `RAIZ` es el repo principal, donde `RAIZ.parent` ya era correcto: la carpeta que se
    resuelva tiene que seguir siendo esa misma.
    """
    proyectos, arbol = mundo
    repo = proyectos / "repo-de-pega"
    (proyectos / "REGISTRO.md").write_text("# REGISTRO" + chr(10), encoding="utf-8")
    m = _tablero()
    monkeypatch.setattr(m, "RAIZ", repo)
    ok, motivo = m.registro_sin_caducados()
    assert "no existe" not in motivo, motivo
    assert ok, motivo
