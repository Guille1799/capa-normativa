"""El canario tiene que ser DETERMINISTA. El caso real, no uno inventado.

## Qué pasó (2026-08-20)

El canario del hook `vigilante_pre_commit.py` bloqueó un `git commit` hecho desde un *worktree*
diciendo «el canario de `sintaxis` no saltó: el detector no detecta nada». A mano no se
reproducía **nunca**, ni desde el worktree ni desde el checkout principal.

La causa: git exporta `GIT_DIR` a sus hooks —y solo desde un worktree, con ruta absoluta al
gitdir del repo principal—. El canario montaba su caso rojo en un `TemporaryDirectory` que NO
era un repo, así que `git ls-files` contestaba sobre el repo del `GIT_DIR`, devolvía nombres de
otro árbol, y el detector recorría rutas inexistentes: 0 hallazgos. Una shell normal no tiene
`GIT_DIR`, y por eso el fallo solo existía dentro del hook.

## Por qué estos tests son así

Un canario cuya fiabilidad depende de dónde se ejecute no sirve de canario. Así que aquí se
mueven **las tres cosas de las que no puede depender**, a propósito y por separado:

* el **CWD** — dentro de un repo, dentro de un worktree, y fuera de todo;
* el **entorno** — con un `GIT_DIR` ajeno exportado, como hace git;
* dónde cae `%TEMP%` — incluido el caso feo de que caiga DENTRO de un repo.

Y la otra mitad, que es la que se olvida: **que el canario pueda fallar**. Los tests en rojo de
abajo son los que impiden relajarlo hasta convertirlo en un no-op, que es exactamente el fallo
que existe para cazar.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from capa_normativa.vigilante import canario as mod
from capa_normativa.vigilante.canario import CASOS, canario, repo_de_pega
from capa_normativa.vigilante.secretos import revisar_secretos
from capa_normativa.vigilante.sintaxis import revisar_sintaxis

#: Los detectores REALES. Se comprueban los de verdad: un canario validado solo contra dobles
#: verifica el canario, no el sistema.
REVISORES = {"secretos": revisar_secretos, "sintaxis": revisar_sintaxis}


def _git(donde: Path, *args: str) -> None:
    """`git` sobre `donde`, con el entorno limpio.

    Lo de `entorno_limpio()` aquí no es copiar al código bajo prueba por inercia: sin él, el
    andamio de estos tests se deja secuestrar por el `GIT_DIR` que ellos mismos exportan y
    revienta al montar el segundo repo. Pasó al escribirlos — la misma trampa, un piso arriba.
    """
    subprocess.run(["git", "-C", str(donde), *args], capture_output=True, check=True,
                   env=mod.entorno_limpio())


def _repo(donde: Path) -> Path:
    """Un repo git real con un commit, sin depender de la config global del usuario."""
    donde.mkdir(parents=True, exist_ok=True)
    for orden in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        _git(donde, *orden)
    (donde / "sano.py").write_text("x = 1\n", encoding="utf-8")
    _git(donde, "add", "-A")
    _git(donde, "commit", "-qm", "base")
    return donde


# ─────────────────────────────────────────────────────────────────────────────
# LA PRUEBA DE ACEPTACIÓN: pasa con el CWD dentro de un repo Y fuera de él.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dentro_de_repo", [True, False], ids=["cwd_en_repo", "cwd_fuera"])
def test_el_canario_pasa_dentro_y_fuera_de_un_repo_git(tmp_path, monkeypatch, dentro_de_repo):
    """El canario no puede depender de desde dónde se le llame.

    Los dos casos importan: dentro de un repo es como corre de verdad (un hook pre-commit),
    y fuera es como se le llama a mano al depurarlo. Si solo pasara en uno, «no se reproduce»
    volvería a ser un diagnóstico posible — y es el que costó esta sesión.
    """
    cwd = _repo(tmp_path / "repo") if dentro_de_repo else (tmp_path / "fuera")
    cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(cwd)
    assert _es_repo(cwd) is dentro_de_repo, "el escenario no es el que dice ser"

    canario(REVISORES)  # no lanza == pasa


def _es_repo(ruta: Path) -> bool:
    r = subprocess.run(["git", "-C", str(ruta), "rev-parse", "--is-inside-work-tree"],
                       capture_output=True, text=True, env=mod.entorno_limpio())
    return r.returncode == 0 and r.stdout.strip() == "true"


# ─────────────────────────────────────────────────────────────────────────────
# Las otras dos dependencias que tampoco puede tener: el entorno y dónde cae %TEMP%.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dentro_de_repo", [True, False], ids=["cwd_en_repo", "cwd_fuera"])
def test_un_GIT_DIR_AJENO_no_secuestra_al_canario(tmp_path, monkeypatch, dentro_de_repo):
    """EL CASO REAL. Sin `GIT_DIR` el bug es invisible, así que se pone a propósito: un test
    que no la exporte habría pasado en verde sobre el código roto."""
    ajeno = _repo(tmp_path / "ajeno")
    monkeypatch.setenv("GIT_DIR", str((ajeno / ".git").resolve()))
    cwd = _repo(tmp_path / "repo") if dentro_de_repo else (tmp_path / "fuera")
    cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(cwd)

    canario(REVISORES)


def test_el_canario_pasa_dentro_de_un_WORKTREE_con_el_entorno_que_git_da_a_sus_hooks(tmp_path,
                                                                                     monkeypatch):
    """La reconstrucción exacta del fallo: git solo exporta `GIT_DIR` a los hooks, y solo desde
    un worktree su valor apunta a otro sitio. Medido con un hook de pega el 2026-08-20."""
    principal = _repo(tmp_path / "principal")
    wt = tmp_path / "wt"
    _git(principal, "worktree", "add", "-q", str(wt), "-b", "rama")
    gitdir = principal / ".git" / "worktrees" / "wt"
    monkeypatch.setenv("GIT_DIR", str(gitdir.resolve()))
    monkeypatch.setenv("GIT_INDEX_FILE", str((gitdir / "index").resolve()))
    monkeypatch.setenv("GIT_PREFIX", "")
    monkeypatch.chdir(wt)

    canario(REVISORES)


def test_el_canario_pasa_aunque_TEMP_caiga_DENTRO_de_un_repo(tmp_path, monkeypatch):
    """El caso feo, no el ejemplar. Si `%TEMP%` estuviera dentro de un repo, un directorio
    temporal sin `git init` propio heredaría la enumeración de ESE repo — y el canario volvería
    a mirar una lista de ficheros que no están donde dice."""
    envolvente = _repo(tmp_path / "envolvente")
    monkeypatch.setattr(tempfile, "tempdir", str(envolvente))

    canario(REVISORES)

    with repo_de_pega() as repo:
        assert repo.is_relative_to(envolvente), "el escenario no es el que dice ser"


# ─────────────────────────────────────────────────────────────────────────────
# ROJOS: que el canario PUEDA fallar. Sin esto, «pasa siempre» y «funciona» son lo mismo.
# ─────────────────────────────────────────────────────────────────────────────

def test_ROJO_un_detector_SORDO_hace_saltar_al_canario():
    """Lo mínimo que se le pide: un detector que no detecta nada tiene que bloquearlo."""
    with pytest.raises(RuntimeError, match="no saltó"):
        canario({"sintaxis": lambda _ruta: []})


def test_ROJO_un_detector_SIN_caso_rojo_es_un_error_y_no_un_salto_silencioso():
    """Añadir un detector al hook sin añadirle su caso rojo dejaría un detector que nadie
    comprueba, y en silencio. El silencio es el modo de fallo de toda esta familia."""
    with pytest.raises(RuntimeError, match="no hay caso rojo"):
        canario({"inventado": lambda _ruta: [object()]})


def test_ROJO_sin_detectores_no_es_un_pase_limpio():
    with pytest.raises(RuntimeError, match="ningún detector"):
        canario({})


def test_ROJO_si_la_enumeracion_por_GIT_muere_el_canario_TIENE_que_saltar(monkeypatch):
    """LA MUTACIÓN QUE ANTES NO ENTRABA, y es la razón de este fichero.

    Medido el 2026-08-20 sobre el canario anterior: anulando `versionados()` por completo
    —o sea, con la enumeración por git MUERTA— seguía devolviendo 1 hallazgo y dando verde,
    porque su directorio no era un repo y el detector caía al `rglob` de reserva. Daba por
    buena una comprobación del camino que en producción no se usa.
    """
    monkeypatch.setattr(mod, "versionados", lambda repo, patron=None: None)

    with pytest.raises(RuntimeError, match="no enumeró por git"):
        canario(REVISORES)


def test_ROJO_el_canario_se_comprueba_a_si_mismo(monkeypatch):
    """Si `_correr` se relajara hasta no poder fallar, el canario entero sería un no-op — y su
    verde no significaría nada. El pase con detectores sordos es lo que lo impide."""
    monkeypatch.setattr(mod, "_correr", lambda revisores, repo: None)  # un canario que nunca falla

    with pytest.raises(RuntimeError, match="no-op"):
        canario(REVISORES)


# ─────────────────────────────────────────────────────────────────────────────
# El repo de pega, que es lo que hace determinista a todo lo anterior.
# ─────────────────────────────────────────────────────────────────────────────

def test_el_repo_de_pega_es_un_repo_DE_VERDAD_con_los_casos_versionados():
    """Todo el arreglo cuelga de esto: si el repo de pega no fuera repo, git volvería a
    contestar sobre el que encontrase por ahí."""
    with repo_de_pega() as repo:
        assert (repo / ".git").exists(), "sin `.git` propio, git busca hacia arriba"
        from capa_normativa.vigilante.versionados import versionados
        lista = versionados(repo)
        assert lista is not None
        assert sorted(p.name for p in lista) == sorted(f for f, _ in CASOS.values())


def test_hay_un_caso_rojo_por_cada_detector_que_corre_el_hook():
    """El hook corre `secretos` y `sintaxis`. Que el canario los cubra a los dos no puede
    depender de que alguien se acuerde."""
    assert set(CASOS) >= {"secretos", "sintaxis"}


def test_el_fichero_del_canario_no_dispara_al_detector_que_comprueba(tmp_path):
    """La credencial de muestra va partida en el código a propósito. Escrita de una pieza, el
    vigilante corriendo sobre su propio repo —lo hace, es un trabajo del CI— marcaría este
    módulo como fuga, y la salida sería excluirlo: así se apagan los detectores."""
    from capa_normativa.vigilante import canario as este

    repo = _repo(tmp_path / "repo")
    destino = repo / "canario_copiado.py"
    destino.write_text(Path(este.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    _git(repo, "add", "-A")

    assert not revisar_secretos(repo), "el propio canario dispara el detector de secretos"
