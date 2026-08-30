"""Una sonda tiene que dar el MISMO veredicto se corra desde el checkout principal o desde un worktree.

Dos formas distintas del mismo fallo, cada una en su bloque:

  1. **`RAIZ.parent`** (2026-08-23, abajo del todo esta la segunda) — las dos sondas que miran
     FUERA del repo buscaban su fichero en la carpeta equivocada. Es lo que documenta el resto
     de esta cabecera.
  2. **`core.hooksPath`** — configuracion COMPARTIDA por todos los worktrees, con la ruta
     absoluta a UNO de ellos dentro. Ver el bloque de comentarios de mitad de fichero.

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


# --- La segunda forma: la CONFIG del repo nombra UN arbol, y los worktrees son N --------------
#
# Medido el 2026-08-23, misma familia y distinto disfraz. `core.hooksPath` no vive en el
# worktree: vive en el `.git` COMUN, asi que los N arboles leen el mismo valor. Y ese valor es
# hoy la ruta absoluta al checkout principal, o sea que una sonda que lo use tal cual no falla a
# veces — solo puede acertar en 1 arbol de N, por construccion.
#
# Ademas ni siquiera daba un rojo: `RAIZ / <absoluta>` se traga el prefijo (regla de `pathlib`),
# y el `hook.relative_to(RAIZ)` de la sonda LANZABA `ValueError`. Comprobado con los valores
# reales de hoy: desde un worktree `guardia_de_commit()` no medía nada, reventaba.


def _hook(arbol: Path, cuerpo: str) -> None:
    """Un `hooks/pre-commit` versionado en ese arbol, con el cuerpo que se le diga.

    `--no-verify` porque el `core.hooksPath` del mundo ya apunta a esta misma carpeta: sin el, un
    hook que grita bloquea el commit que lo versiona. Aqui solo se esta poniendo el fichero en el
    arbol; quien tiene que ejecutarlo es la sonda, y lo hace contra su propio repo de pega.
    """
    carpeta = arbol / "hooks"
    carpeta.mkdir(parents=True, exist_ok=True)
    f = carpeta / "pre-commit"
    f.write_text("#!/bin/sh" + chr(10) + cuerpo + chr(10), encoding="utf-8")
    # ⚠️ EL PERMISO DE EJECUCION NO ES ADORNO, y en Windows no se nota.
    #
    # En Windows da igual: git lanza el hook a traves del shell y ese bit ni existe. En Linux git
    # NO EJECUTA un hook sin el — y no avisa: simplemente no corre, el commit pasa, y la sonda
    # concluye que la guarda «dejo pasar un caso rojo conocido».
    #
    # MEDIDO el 2026-08-30 al añadir Linux a la CI: estos dos tests llevaban SEIS DIAS rojos por
    # esto, desde el 24-ago. En Windows pasaban, y nadie lo vio porque nadie miraba la CI.
    f.chmod(f.stat().st_mode | 0o111)
    _git("-C", str(arbol), "add", "-A")
    _git("-C", str(arbol), "-c", "user.email=t@local", "-c", "user.name=t",
         "commit", "-qm", "hook", "--no-verify")


@pytest.fixture
def mundo_con_hooks(mundo):
    """`mundo`, y ademas `core.hooksPath` apuntando en ABSOLUTO al checkout principal.

    No es un caso rebuscado: es literalmente lo que contesta `git config --get core.hooksPath`
    en capa-normativa hoy. Una config compartida por todos los worktrees no tiene otra forma de
    nombrar una carpeta concreta que una ruta absoluta, y esa ruta es de UN arbol.
    """
    proyectos, arbol = mundo
    repo = proyectos / "repo-de-pega"
    _git("-C", str(repo), "config", "core.hooksPath", str(repo / "hooks"))
    return repo, arbol


def test_una_ruta_del_checkout_principal_se_reancla_al_arbol_propio(mundo_con_hooks, monkeypatch):
    """El reanclaje, y al lado lo que hacia el codigo anterior con el mismo dato."""
    repo, arbol = mundo_con_hooks
    m = _tablero()
    monkeypatch.setattr(m, "RAIZ", arbol)
    assert m._en_el_arbol_propio(str(repo / "hooks")) == arbol / "hooks"
    # Lo de antes, en una linea: `pathlib` deja que la absoluta se coma el prefijo entero, asi
    # que `RAIZ /` no aislaba nada. No es un descuido de quien lo escribio, es la regla.
    assert arbol / str(repo / "hooks") == repo / "hooks"
    # Y una relativa cuelga del arbol propio, que es lo que ya se esperaba de ella.
    assert m._en_el_arbol_propio("hooks") == arbol / "hooks"


def test_una_carpeta_de_hooks_de_VERDAD_fuera_del_repo_se_respeta(mundo, tmp_path, monkeypatch):
    """El reanclaje no puede pasarse de listo: fuera del repo, la ruta es una decision, no un fallo.

    Sin esta mitad, «arreglar la punteria» degeneraria en «traerse todo a casa», y una carpeta de
    hooks compartida por varios repos —que es una configuracion legitima— se resolveria a un
    sitio inventado dentro del arbol.
    """
    _, arbol = mundo
    m = _tablero()
    monkeypatch.setattr(m, "RAIZ", arbol)
    fuera = tmp_path / "hooks-de-la-empresa"
    assert m._en_el_arbol_propio(str(fuera)) == fuera


def test_la_guardia_de_commit_juzga_el_pre_commit_de_SU_arbol(mundo_con_hooks, monkeypatch):
    """Las tres condiciones, sobre el arbol propio, con un hook DISTINTO en cada arbol.

    El del checkout principal deja pasar cualquier commit y el del worktree grita. Asi el
    veredicto distingue cual de los dos se examino, en vez de depender de leer una ruta en un
    mensaje — que es lo que un arreglo cosmetico dejaria pasar.
    """
    repo, arbol = mundo_con_hooks
    _hook(repo, "exit 0")           # el del vecino: permisivo
    _hook(arbol, "exit 1")          # el propio: grita
    m = _tablero()
    monkeypatch.setattr(m, "RAIZ", arbol)
    ok, motivo = m.guardia_de_commit()
    assert ok, motivo


def test_el_rojo_de_la_guardia_dice_DONDE_ha_buscado(mundo_con_hooks, monkeypatch):
    """Con el hook solo en el vecino, la sonda tiene que salir ROJA y decir en que arbol miro.

    Es la mitad legible del arreglo. El mensaje anterior repetia el valor de `core.hooksPath` y
    sonaba a «falta el hook» cuando lo que pasaba era «estas mirando otro sitio»; son dos rojos
    con arreglos opuestos, y sin la ruta entera no se distinguen leyendolos.
    """
    repo, arbol = mundo_con_hooks
    _hook(repo, "exit 1")
    m = _tablero()
    monkeypatch.setattr(m, "RAIZ", arbol)
    ok, motivo = m.guardia_de_commit()
    assert not ok, motivo
    assert str(arbol / "hooks") in motivo, motivo


def test_la_guardia_de_commit_desde_el_checkout_PRINCIPAL_sigue_igual(mundo_con_hooks, monkeypatch):
    """El control. Un arreglo que rompiera el caso que HOY funciona no seria un arreglo.

    Aqui `RAIZ` es el checkout principal, o sea el unico arbol donde `core.hooksPath` ya acertaba
    por casualidad. El reanclaje tiene que ser la identidad en ese caso.
    """
    repo, _ = mundo_con_hooks
    _hook(repo, "exit 1")
    m = _tablero()
    monkeypatch.setattr(m, "RAIZ", repo)
    assert m._en_el_arbol_propio(str(repo / "hooks")) == repo / "hooks"
    ok, motivo = m.guardia_de_commit()
    assert ok, motivo
