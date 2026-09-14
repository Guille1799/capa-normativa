"""MENTIROSOS de `escaparate-con-guarda`: seis escaparates de pega, cada uno desprotegido por un sitio.

## Qué es un mentiroso

Una implementación **completa** de la cosa que el comprobador juzga —aquí, el escaparate entero:
el guion compartido, la lista de repos públicos y la guarda `pre-push` de cada uno— rota por **UNA
sola razón**, con el test exigiendo que caiga **en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

## Qué protege

La regla es de G, 2026-08-24: *«github es donde los reclutadores irán a mirar»*. Vivía escrita en
prosa en CINCO `CLAUDE.md` —«⚠️ El repo es público»— y no había impedido absolutamente nada: ni un
hook, ni un comprobador, ni un test. **Un mecanismo que sólo funciona si alguien lo lee no es un
mecanismo.**

Y una guarda es un fichero: se borra, se renombra, o nunca se instaló en el repo que creaste ayer.
Por eso el comprobador la EJECUTA — un `pre-push` que existe y revienta al arrancar protege igual
que ninguno, y desde fuera se ven idénticos.

Sus seis ramas piden arreglos distintos:

  · falta el **guion compartido** -> ningún repo tiene guarda, porque todos los shims apuntan ahí;
  · **no se pudo enumerar** los repos -> eso NO es «todos tienen guarda»;
  · **cero repos públicos** -> sospechoso, no limpio;
  · un repo **sin guarda**;
  · una guarda que **no llega a arrancar**;
  · una guarda que arranca y **no encuentra su guion**.

Las dos primeras son las caras: traducir «no he podido mirar» a verde es exactamente el fallo que
este arnés entero existe para impedir.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parent.parent / "scripts" / "aceptaciones" / "escaparate_con_guarda.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("escaparate_para_mentirosos", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


E = _cargar()

_RAIZ = Path(tempfile.mkdtemp(prefix="mentirosos-escaparate-"))
_GUION = _RAIZ / "escaparate_pre_push.py"
_GUION.write_text("# el guion compartido de pega\n", encoding="utf-8")

#: La guarda HONESTA: el shim que todos los repos instalan. Comprueba que el guion compartido
#: exista y deja pasar. Que MIRE no es adorno — el caso feo del comprobador es justo el shim que
#: arranca y no encuentra su guion.
_HONESTA_SH = ("#!/bin/sh\n"
               "if [ ! -f '" + _GUION.as_posix() + "' ]; then\n"
               "  echo 'falta el guion del escaparate' >&2\n"
               "  exit 1\n"
               "fi\n"
               "exit 0\n")

#: Arranca, mira, y su guion compartido no está. Dice exactamente eso, que es lo que la distingue
#: de una guarda que ni siquiera llega a ejecutarse.
_SIN_SU_GUION_SH = ("#!/bin/sh\n"
                    "echo 'falta el guion del escaparate' >&2\n"
                    "exit 1\n")

#: Ni siquiera arranca: 127 es el shell diciendo que no encontró qué ejecutar.
_NO_ARRANCA_SH = "#!/bin/sh\nexit 127\n"


def _git(repo, *a):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # `stdin=DEVNULL` explicito: esto corre al IMPORTAR, antes de que el fixture de sesion de
    # `conftest.py` este activo, y sin el Windows revienta con `WinError 6`.
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True,
                          timeout=120, env=env, stdin=subprocess.DEVNULL)


def _repo(nombre, *, guarda=_HONESTA_SH):
    repo = _RAIZ / nombre
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    if guarda is not None:
        hook = repo / ".git" / "hooks" / "pre-push"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(guarda, encoding="utf-8", newline="\n")
        hook.chmod(0o755)
    return repo


def _fabrica(*, guion=None, publicos=None):
    """Un escaparate de pega. Por defecto el HONESTO; cada argumento mete UNA mentira."""
    return {"guion": _GUION if guion is None else guion,
            "publicos": (lambda: [_repo("publico_sano")]) if publicos is None else publicos}


HONESTO = _fabrica()


def _sonda(escaparate):
    """`escaparate_con_guarda()` de verdad, con el guion y la lista de repos inyectados.

    `publicos()` pregunta a `gh` una vez por repo, así que se sustituye: lo que se prueba aquí es
    el juicio sobre las guardas, no la enumeración. `_guarda_de` y `_arranca` son los de verdad y
    ejecutan los `pre-push` de pega con el mismo `sh` que usaría git.
    """
    orig = (E.GUION, E.publicos)
    E.GUION, E.publicos = escaparate["guion"], escaparate["publicos"]
    try:
        return E.escaparate_con_guarda()
    finally:
        E.GUION, E.publicos = orig


def _revienta(excepcion):
    def publicos():
        raise excepcion
    return publicos


MENTIROSOS = {
    # Sin el guion compartido, ningún repo tiene guarda de verdad: todos los shims apuntan ahí. Es
    # un fallo de una sola causa y por eso se comprueba aparte, antes que nada.
    "falta_el_guion_compartido": (_fabrica(guion=_RAIZ / "no-existe.py"), "falta"),
    # `gh` no contestó. Eso NO es «todos tienen guarda»: es no haber podido mirar, y traducirlo a
    # verde es el fallo más caro que puede cometer un guarda.
    "no_se_pudo_enumerar": (_fabrica(publicos=_revienta(E.NoSePudoMirar("gh no contesto"))),
                            "no se pudo mirar"),
    # Ni siquiera se pudo lanzar el proceso que enumera. Bajo carga esta máquina falla al lanzar
    # procesos, y antes eso reventaba con una traza donde debería haber un veredicto.
    "no_se_pudo_ni_lanzar_la_enumeracion": (_fabrica(publicos=_revienta(OSError("WinError 6"))),
                                            "no se pudo ni enumerar"),
    # Cero repos públicos en esta máquina es imposible. Un cero de la propia búsqueda no es
    # ausencia: es sospechoso, y su verde se leería como limpio.
    "cero_repos_publicos": (_fabrica(publicos=lambda: []), "sospechoso, no limpio"),
    # El repo que creaste ayer: público, con remoto, y sin ninguna guarda. Empuja libre y sin señal.
    "un_repo_sin_guarda": (_fabrica(publicos=lambda: [_repo("sin_guarda", guarda=None)]),
                           "sin guarda"),
    # La guarda está y no llega a arrancar. Desde fuera se ve idéntica a una que funciona, y es
    # exactamente igual de inútil.
    "una_guarda_que_no_arranca": (_fabrica(publicos=lambda: [_repo("no_arranca",
                                                                   guarda=_NO_ARRANCA_SH)]),
                                  "no llega a arrancar"),
    # Arranca, mira, y le falta el guion compartido. Es un veredicto SOBRE la guarda —no sobre el
    # que mide— y pide otro arreglo: reponer el guion, no reinstalar el shim.
    "una_guarda_sin_su_guion": (_fabrica(publicos=lambda: [_repo("sin_su_guion",
                                                                 guarda=_SIN_SU_GUION_SH)]),
                                "no encuentra el guion compartido"),
}


@pytest.fixture(scope="module", autouse=True)
def _limpiar():
    yield
    shutil.rmtree(_RAIZ, ignore_errors=True)


def test_el_escaparate_honesto_APRUEBA():
    """Guion en su sitio, un repo público, y su guarda arranca. Sin esto nada de abajo prueba nada."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    escaparate, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(escaparate)
    assert not ok, nombre + " aprobo, y ese escaparate empuja libre"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_los_dos_NO_SE_PUDO_MIRAR_no_se_confunden_con_un_hallazgo():
    """Lo que separa una alarma de un instrumento roto, y sólo una de las dos pide trabajo.

    Se comprueba que el motivo lo DIGA, no sólo que el color sea rojo: un rojo que no distingue
    «no tienen guarda» de «no he podido preguntar» manda a alguien a instalar guardas que ya están.
    """
    for nombre in ("no_se_pudo_enumerar", "no_se_pudo_ni_lanzar_la_enumeracion"):
        _, motivo = _sonda(MENTIROSOS[nombre][0])
        assert "NO es" in motivo or "no se pudo" in motivo, nombre + " -> " + motivo
        assert "sin guarda" not in motivo, nombre + " acusa a los repos de un fallo suyo: " + motivo
