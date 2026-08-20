"""`GIT_DIR` no puede secuestrar a los detectores. EL CASO REAL, no uno inventado.

## Qué pasó (2026-08-20)

Git **exporta `GIT_DIR` a sus hooks**, y en un worktree ese valor es una ruta ABSOLUTA al gitdir
del repo principal. Los detectores enumeraban así:

    subprocess.run(["git", "ls-files"], cwd=repo)

Con `GIT_DIR` en el entorno, `cwd=` deja de decidir: git contesta sobre el repo del `GIT_DIR`.
Los nombres devueltos se unían a `repo`, daban rutas inexistentes, y el detector recorría una
lista de fantasmas.

**Medido:** el vigilante como hook pre-commit dentro de un worktree escaneaba CERO ficheros y
respondía «limpio». No fallaba: mentía. Y se cazó de rebote, porque el canario del hook bloqueó
un commit diciendo que el detector no detectaba nada.

Por eso estos tests ponen `GIT_DIR` A PROPÓSITO: sin esa variable el bug es invisible, y un test
que no la pone habría pasado en verde sobre el código roto.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from capa_normativa.vigilante.secretos import revisar_secretos
from capa_normativa.vigilante.sintaxis import revisar_sintaxis
from capa_normativa.vigilante.versionados import versionados


@pytest.fixture
def git_dir_ajeno(tmp_path, monkeypatch):
    """Un repo git REAL, distinto del que se va a escanear, exportado como `GIT_DIR`."""
    otro = tmp_path / "otro_repo"
    otro.mkdir()
    for orden in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(otro), *orden], capture_output=True)
    (otro / "sano.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(otro), "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", str(otro), "commit", "-qm", "base"], capture_output=True)
    monkeypatch.setenv("GIT_DIR", str((otro / ".git").resolve()))
    return otro


def test_SINTAXIS_no_se_deja_secuestrar_por_GIT_DIR(tmp_path, git_dir_ajeno):
    """Sin el arreglo esto devolvía 0 hallazgos: escaneaba el repo del GIT_DIR, no el de al lado."""
    objetivo = tmp_path / "objetivo"
    objetivo.mkdir()
    (objetivo / "roto.py").write_text("def f(:\n", encoding="utf-8")

    hallazgos = revisar_sintaxis(objetivo)

    assert hallazgos, ("el detector no vio el fichero roto: `GIT_DIR` lo mandó a otro repo y "
                       "habría respondido «limpio» sin mirar nada")


def test_SECRETOS_no_se_deja_secuestrar_por_GIT_DIR(tmp_path, git_dir_ajeno):
    """El más grave de los dos: decir «limpio» sin escanear es cómo se publica una credencial."""
    objetivo = tmp_path / "objetivo"
    objetivo.mkdir()
    (objetivo / "config.md").write_text("clave = " + "gsk" + "_" + "A" * 32 + "\n",
                                        encoding="utf-8")

    hallazgos = revisar_secretos(objetivo)

    assert hallazgos, "el escáner de secretos respondió «limpio» sobre un fichero con credencial"


def test_las_rutas_que_NO_existen_se_descartan(tmp_path, git_dir_ajeno):
    """Cinturón tras los tirantes: si algo volviera a envenenar la lista, se nota — en vez de
    recorrer fantasmas y llamarlo «limpio»."""
    vacio = tmp_path / "vacio"
    vacio.mkdir()

    assert versionados(vacio) is None, (
        "sobre un directorio que no es repo tiene que devolver None (no una lista de fantasmas "
        "heredada del GIT_DIR ajeno)")


def test_un_repo_de_verdad_SI_se_enumera(tmp_path, monkeypatch):
    """La otra mitad: al blindarlo no se puede haber roto el camino normal."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for orden in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(repo), *orden], capture_output=True)
    (repo / "a.py").write_text("y = 2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "x"], capture_output=True)

    lista = versionados(repo, "*.py")

    assert lista and [p.name for p in lista] == ["a.py"]


def test_NO_hay_dos_enumeraciones(tmp_path):
    """El bug estaba DUPLICADO en los dos detectores, idéntico. Dos copias de lo mismo divergen
    —o, como aquí, se equivocan a la vez y hay que arreglarlo dos veces."""
    import inspect

    from capa_normativa.vigilante import secretos, sintaxis

    for mod in (secretos, sintaxis):
        fuente = inspect.getsource(mod)
        assert "ls-files" not in fuente, (
            f"{mod.__name__} volvió a enumerar por su cuenta: la enumeración vive en "
            f"`versionados.py` y solo ahí")
