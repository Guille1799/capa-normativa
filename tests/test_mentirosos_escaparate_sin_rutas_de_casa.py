"""MENTIROSOS de `escaparate-sin-rutas-de-casa`: cinco escaparates de pega, cada uno sucio por un sitio.

## Qué es un mentiroso

Una implementación **completa** de la cosa que el comprobador juzga —aquí, los repos públicos con
sus ficheros versionados y su upstream— rota por **UNA sola razón**, con el test exigiendo que
caiga **en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

## Qué protege

Una ruta `C:/Users/<usuario>` dentro de un repo público no es sólo un dato personal: es **código
que sólo funciona en una máquina**. Y la diferencia entre las dos formas de tenerla decide un
trabajo completamente distinto:

  · **aún no empujada** -> limpiar es gratis hoy, con un commit;
  · **ya publicada** -> limpiarla exige reescribir la historia y un force-push, y eso lo decide G.

Un rojo que no diga cuál de las dos es no acciona nada.

## Y la tercera lista, que es la que faltaba

MEDIDO el 2026-08-30: un fichero que no se podía leer se saltaba con un `continue` **en silencio**.
Un fichero saltado no aporta hallazgos, o sea que aportaba VERDE — el veredicto decía «ninguno de
los N repos lleva la ruta de casa» sin mencionar que a M ficheros ni se les había mirado. Eso es
**aprobar en vacío, fichero a fichero**, escondido dentro de un `continue`.

Por eso `un_fichero_sin_mirar` sale **MUDO** y no rojo, y por eso hay un test aparte para el ORDEN:
un hallazgo real manda sobre la duda, pero la duda manda sobre el verde. Al revés sería tapar una
infracción confirmada con un «no estoy seguro».
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

MODULO = (Path(__file__).resolve().parent.parent / "scripts" / "aceptaciones"
          / "escaparate_sin_rutas_de_casa.py")


def _cargar():
    spec = importlib.util.spec_from_file_location("rutas_para_mentirosos", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


E = _cargar()

_RAIZ = Path(tempfile.mkdtemp(prefix="mentirosos-rutas-"))

#: La ruta de casa se DERIVA, no se escribe: escrita, este fichero sólo probaría algo en una
#: máquina, que es exactamente el defecto que el comprobador persigue.
_CASA = str(Path.home()).replace(chr(92), "/")
_SUCIO = "CARPETA = r'" + _CASA + "/proyectos/capa-normativa'\n"
_LIMPIO = "CARPETA = Path.home() / 'proyectos' / 'capa-normativa'\n"


def _git(repo, *a):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # `stdin=DEVNULL` explicito: esto corre al IMPORTAR, antes de que el fixture de sesion de
    # `conftest.py` este activo, y sin el Windows revienta con `WinError 6`.
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True,
                          timeout=180, env=env, stdin=subprocess.DEVNULL)


def _repo(nombre, *, publicado=_LIMPIO, despues_de_empujar=None, enorme=False):
    """Un repo público de pega, con su remoto y su upstream de verdad.

    El upstream no se finge: `_publicado_hasta()` se lo pregunta a git, y sin él todo hallazgo
    caería en «aún no empujado» y las dos ramas caras dejarían de ser distinguibles.
    """
    remoto = _RAIZ / (nombre + ".git")
    repo = _RAIZ / nombre
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare", "-q", str(remoto)], capture_output=True,
                   timeout=180, stdin=subprocess.DEVNULL)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "pega@local")
    _git(repo, "config", "user.name", "pega")
    (repo / "codigo.py").write_text(publicado, encoding="utf-8")
    _git(repo, "add", "--", "codigo.py")
    _git(repo, "commit", "-qm", "lo que ya salio a github")
    _git(repo, "branch", "-M", "main")
    _git(repo, "remote", "add", "origin", str(remoto))
    _git(repo, "push", "-q", "-u", "origin", "main")
    if despues_de_empujar is not None:
        (repo / "nuevo.py").write_text(despues_de_empujar, encoding="utf-8")
        _git(repo, "add", "--", "nuevo.py")
        _git(repo, "commit", "-qm", "todavia no empujado")
    if enorme:
        # Por encima del tope de tamaño del comprobador. Rastrear un binario grande buscando texto
        # no tiene sentido — pero saltárselo tiene que DECIRSE, que es todo lo que se prueba aquí.
        (repo / "gordo.csv").write_text("x" * (E._TOPE_BYTES + 1024), encoding="utf-8")
        _git(repo, "add", "--", "gordo.csv")
        _git(repo, "commit", "-qm", "un fichero por encima del tope")
    return repo


def _fabrica(*, publicos=None):
    """Un escaparate de pega. Por defecto el HONESTO: un repo público, limpio y legible entero."""
    return {"publicos": (lambda: [_repo("limpio")]) if publicos is None else publicos}


HONESTO = _fabrica()


def _sonda(escaparate):
    """`escaparate_sin_rutas_de_casa()` de verdad, con la lista de repos inyectada.

    `publicos()` pregunta a `gh` una vez por repo; lo que se juzga aquí es el rastreo, no la
    enumeración. `_con_ruta` y `_publicado_hasta` son los de verdad, sobre repos git de verdad.
    """
    original = E.publicos
    E.publicos = escaparate["publicos"]
    try:
        return E.escaparate_sin_rutas_de_casa()
    finally:
        E.publicos = original


def _revienta(excepcion):
    def publicos():
        raise excepcion
    return publicos


MENTIROSOS = {
    # `gh` no contestó. Eso NO es «no hay rutas de casa»: es no haber podido mirar, y es MUDO.
    "no_se_pudo_enumerar": (_fabrica(publicos=_revienta(E.NoSePudoMirar("gh no contesto"))),
                            "no se pudo mirar"),
    # `gh` contestó, y contestó algo imposible. Eso SÍ es haber mirado — por eso es ROJO y no mudo.
    "cero_repos_publicos": (_fabrica(publicos=lambda: []), "sospechoso, no limpio"),
    # Todo lo que se leyó está limpio, y hay un fichero que no se pudo leer. El verde de antes se
    # ganaba saltándoselo en silencio: aprobar en vacío, fichero a fichero.
    "un_fichero_sin_mirar": (_fabrica(publicos=lambda: [_repo("con_gordo", enorme=True)]),
                             "no se pudo leer"),
    # La ruta está en un commit que aún no ha salido. Limpiar es gratis hoy.
    "ruta_de_casa_sin_empujar": (_fabrica(publicos=lambda: [_repo("sin_empujar",
                                                                  despues_de_empujar=_SUCIO)]),
                                 "AUN NO EMPUJADO"),
    # La ruta ya está en GitHub. Mismo texto, trabajo completamente distinto: force-push, y lo
    # decide G.
    "ruta_de_casa_ya_publicada": (_fabrica(publicos=lambda: [_repo("publicada", publicado=_SUCIO)]),
                                  "YA PUBLICADO"),
}


@pytest.fixture(scope="module", autouse=True)
def _limpiar():
    yield
    shutil.rmtree(_RAIZ, ignore_errors=True)


def test_el_escaparate_honesto_APRUEBA():
    """Un repo público, limpio, y todos sus ficheros leídos. Sin esto nada de abajo prueba nada."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo
    assert "se pudieron leer todos" in motivo, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    escaparate, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(escaparate)
    assert not ok, nombre + " aprobo, y ese escaparate no esta limpio"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_un_hallazgo_REAL_manda_sobre_la_duda():
    """El orden de las dos ramas es la decisión entera, y sólo se ve con las dos a la vez.

    Si ya hay una ruta de casa publicada, que además queden ficheros sin mirar no rebaja nada — así
    que el veredicto tiene que ser ROJO y nombrar la infracción. Al revés se taparía una infracción
    confirmada con un «no estoy seguro», que es el peor cambio posible entre dos colores.
    """
    sucio_y_ciego = _fabrica(publicos=lambda: [_repo("sucio_y_gordo", publicado=_SUCIO,
                                                     enorme=True)])
    ok, motivo = _sonda(sucio_y_ciego)
    assert ok is False, "una infraccion confirmada se degrado a «no se pudo medir»: " + str(motivo)
    assert "YA PUBLICADO" in motivo, motivo
