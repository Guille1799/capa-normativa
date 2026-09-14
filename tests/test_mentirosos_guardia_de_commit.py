"""MENTIROSOS de `guardia-de-commit`: cuatro pre-commit de pega, cada uno inútil por un sitio.

## Qué es un mentiroso

Una implementación **completa** de la cosa que el comprobador juzga —aquí, el `pre-commit` del
repo, con su configuración y su versionado— rota por **UNA sola razón**, con el test exigiendo que
caiga **en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

## Qué protege

Tres condiciones, y la última es la única que prueba algo:

  1. `core.hooksPath` apunta a una carpeta del repo. Un hook que sólo vive en `.git/hooks` no
     viaja en un clon, no se revisa en un diff y puede desaparecer sin que nadie se entere.
  2. Ahí hay un `pre-commit` y **git lo sigue**. Que exista el fichero no basta: sin versionar no
     hay red de revert.
  3. Ese hook, corrido contra un repo de pega con un caso rojo conocido, **sale con exit != 0**.

⚠️ Las dos primeras las aprueba un `touch`. Y ése es justo el fallo que se persigue: el 2026-08-20
el escáner recorría CERO ficheros y contestaba «limpio» por un `GIT_DIR` heredado. **Existir no es
funcionar**, y un hook que existe y no protege es peor que ninguno, porque parece que sí.

## Por qué hay cuatro repos de pega y no uno

Cada mentiroso necesita su propio repo porque la mentira vive en la CONFIGURACIÓN, no en el texto
del hook: dónde apunta `core.hooksPath`, si el fichero está ahí, si git lo sigue. Montarlos de
verdad es lo único que prueba que el comprobador mira el repo y no una idea del repo — la
costura `_hook_efectivo()` existe precisamente para no tener que romper el hook real de la máquina,
que es un guardián que entonces no se probaría nunca.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

TABLERO = Path(__file__).resolve().parent.parent / "scripts" / "aceptacion.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("tablero_para_guardia", str(TABLERO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _cargar()

_RAIZ = Path(tempfile.mkdtemp(prefix="mentirosos-guardia-"))

#: El hook HONESTO: mira lo que hay en cola y grita si hay algo. No es decorativo que MIRE — un
#: `exit 1` a secas pasaría las tres condiciones sin haber abierto nada, que es la versión de
#: juguete del fallo que este comprobador persigue.
_HONESTO_SH = (
    "#!/bin/sh\n"
    "if git diff --cached --name-only | grep -q . ; then\n"
    "  echo 'caso rojo conocido entre los ficheros en cola' >&2\n"
    "  exit 1\n"
    "fi\n"
    "exit 0\n"
)

#: El mismo hook, con el `exit 1` vuelto `exit 0`. Sigue mirando, sigue imprimiendo: lo único que
#: ha perdido es la capacidad de decir que no.
_DEJA_PASAR_SH = _HONESTO_SH.replace("exit 1", "exit 0")


def _git(repo, *a):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # `stdin=DEVNULL` explicito: estas llamadas corren al IMPORTAR el modulo, o sea antes de que
    # el fixture de sesion de `conftest.py` este activo, y sin el Windows revienta con
    # `WinError 6` al duplicar un descriptor heredado. Medido aqui mismo.
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True,
                          timeout=120, env=env, stdin=subprocess.DEVNULL)


def _fabrica(nombre, *, declara_hookspath=True, escribe_hook=True, versiona=True,
             guion=_HONESTO_SH):
    """Un repo con su pre-commit, de pega. Por defecto el HONESTO; cada argumento mete UNA mentira."""
    repo = _RAIZ / nombre
    (repo / "hooks").mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "pega@local")
    _git(repo, "config", "user.name", "pega")
    (repo / "LEEME.md").write_text("repo de pega\n", encoding="utf-8")
    _git(repo, "add", "--", "LEEME.md")
    if escribe_hook:
        hook = repo / "hooks" / "pre-commit"
        hook.write_text(guion, encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        if versiona:
            _git(repo, "add", "-f", "--", "hooks/pre-commit")
    if declara_hookspath:
        _git(repo, "config", "core.hooksPath", "hooks")
    return repo


HONESTO = _fabrica("honesto")


def _sonda(repo):
    """`guardia_de_commit()` de verdad, juzgando el repo de pega en vez del árbol real."""
    original = T.RAIZ
    T.RAIZ = repo
    try:
        return T.guardia_de_commit()
    finally:
        T.RAIZ = original


MENTIROSOS = {
    # Sin `core.hooksPath` el hook sólo puede vivir en `.git/hooks`: no viaja en un clon, no se
    # revisa en ningún diff, y desaparece sin señal.
    "sin_hookspath": (_fabrica("sin_hookspath", declara_hookspath=False),
                      "core.hooksPath sin definir"),
    # La config apunta a una carpeta del repo y ahí no hay pre-commit. El mensaje tiene que decir
    # las DOS rutas —la declarada y la mirada—, o el rojo se lee como «falta el hook» cuando lo que
    # pasa es que se está mirando en otro sitio.
    "carpeta_declarada_y_vacia": (_fabrica("carpeta_vacia", escribe_hook=False),
                                  "no hay pre-commit"),
    # El hook existe, funciona, y git no lo sigue. Sin red de revert y sin revisarse en ningún
    # diff: mañana no está y nadie se entera.
    "hook_sin_versionar": (_fabrica("sin_versionar", versiona=False), "NO esta versionado"),
    # Y el caro: está configurado, está versionado, arranca, imprime — y deja pasar la carga
    # envenenada. Las tres primeras condiciones lo aprueban; sólo la tercera lo caza.
    "deja_pasar_la_carga_envenenada": (_fabrica("deja_pasar", guion=_DEJA_PASAR_SH),
                                       "DEJO PASAR"),
}


@pytest.fixture(scope="module", autouse=True)
def _limpiar():
    yield
    shutil.rmtree(_RAIZ, ignore_errors=True)


def test_el_pre_commit_honesto_APRUEBA():
    """Configurado, versionado y gritando. Sin esto los cuatro mentirosos caerían gratis."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    repo, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(repo)
    assert not ok, nombre + " aprobo, y ese repo no esta protegido"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_el_rojo_de_la_carpeta_vacia_dice_DONDE_ha_mirado():
    """Desde un worktree la ruta declarada y la mirada NUNCA coinciden, y sin las dos el rojo miente.

    `core.hooksPath` es configuración COMPARTIDA: vive en el `.git` común, así que los N worktrees
    leen el mismo valor — hoy, la ruta absoluta al checkout principal. Una sonda que la use tal cual
    no es que se equivoque a veces: sólo puede acertar en 1 de los N árboles, por construcción.
    """
    repo, _ = MENTIROSOS["carpeta_declarada_y_vacia"]
    _, motivo = _sonda(repo)
    assert str(repo / "hooks").replace(chr(92), "/") in motivo.replace(chr(92), "/"), motivo
