"""MENTIROSOS de `sabotaje-del-cableado`: cinco mundos de pega, cada uno roto por un sitio.

## Qué es un mentiroso

Una implementación **completa** de la cosa que el comprobador juzga —aquí, el mundo entero que
necesita para medir: un tablero versionado, sus piezas de cableado y la suite que hace de juez—
rota por **UNA sola razón**, con el test exigiendo que caiga **en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

## Qué protege

Este comprobador voltea el `return False` de cada pieza del tablero y exige que la suite proteste.
Es la negación exacta de lo único que se le pide a un guardián: **poder decir que no**. Una pieza
que se vuelve incapaz de dar un rojo y no rompe ninguna prueba deja decorativo a todo comprobador
que cuelgue de ella — y no se nota, porque el tablero sigue saliendo verde.

Sus cinco desenlaces piden cosas distintas, y tres de ellos son MUDOS a propósito:

  · el tablero tiene **cambios sin guardar** -> no se muta sobre trabajo sin commitear;
  · el tablero **no se puede leer** (no expone `COMPROBADORES`, no parsea) -> no se ha mutado nada;
  · **la suite ya falla** antes de mutar -> no puede hacer de juez, porque protestaría igual con
    cualquier sabotaje y esto saldría VERDE sin haber medido nada;
  · **cero piezas** detectadas -> eso sí es ROJO: sospechoso, no limpio;
  · una **pieza ciega** -> ROJO, y nombrándola.

⚠️ Que los tres primeros sean MUDO y no ROJO es el aprendizaje caro de este repo: «no he podido
medir» y «he medido y está mal» no son el mismo color. Aquí un MUDO **también suspende** —`None` no
es aprobar— pero el motivo tiene que decir cuál de los dos es.

## Por qué el juez se inyecta

`_corre_la_suite()` corre la suite entera, así que probar esto de verdad costaría minutos por
mentiroso. El juez de pega hace lo mismo que el de verdad —protesta cuando una pieza vigilada
pierde su `return False`— leyendo el tablero mutado que el comprobador acaba de escribir. Lo que se
prueba es el EXPERIMENTO, no pytest.
"""
from __future__ import annotations

import ast
import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parent.parent / "scripts" / "aceptaciones" / "sabotaje_del_cableado.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("sabotaje_para_mentirosos", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = _cargar()

_RAIZ = Path(tempfile.mkdtemp(prefix="mentirosos-sabotaje-"))

#: Un tablero de pega con DOS piezas, cada una capaz de decir que no. Es el mínimo que hace falta
#: para que «una pieza ciega» sea distinguible de «el tablero entero está ciego».
_PIEZA = ('def {n}():\n'
          '    if _mundo_roto():\n'
          '        return False, "{n} dice que no"\n'
          '    return True, "{n} ok"\n')


def _tablero(*, piezas=("alfa", "beta"), con_cable=True, con_comprobadores=True):
    cuerpo = ['"""Tablero de pega."""', "", "", "def _mundo_roto():", "    return False", "", ""]
    for n in piezas:
        cuerpo.append(_PIEZA.format(n=n) if con_cable
                      else 'def ' + n + '():\n    return True, "' + n + ' ok"\n')
        cuerpo.append("")
    if con_comprobadores:
        cuerpo.append("COMPROBADORES = {")
        cuerpo += ['    "' + n + '": ' + n + ',' for n in piezas]
        cuerpo.append("}")
    return "\n".join(cuerpo) + "\n"


def _git(repo, *a):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # `stdin=DEVNULL` explicito: estas llamadas corren al IMPORTAR el modulo, o sea antes de que
    # el fixture de sesion de `conftest.py` este activo, y sin el Windows revienta con
    # `WinError 6` al duplicar un descriptor heredado. Medido aqui mismo.
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True,
                          timeout=120, env=env, stdin=subprocess.DEVNULL)


def _juez(vigiladas, *, siempre_protesta=False):
    """La suite de pega: protesta cuando una pieza VIGILADA ha perdido su `return False`.

    Es el contrato entero de un juez sano — y por eso el mentiroso `la_suite_ya_falla` se
    construye haciéndolo protestar siempre: entonces no distingue nada y su verde no vale.
    """
    def corre():
        if siempre_protesta:
            return True
        arbol = ast.parse(S.TABLERO.read_bytes().decode("utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.FunctionDef) and n.name in vigiladas:
                if not S._lineas_que_dicen_que_no(n):
                    return True
        return False
    return corre


def _fabrica(nombre, *, fuente=None, vigiladas=("alfa", "beta"), commitea=True,
             siempre_protesta=False):
    """Un mundo de pega: repo + tablero + juez. Por defecto el HONESTO; cada argumento, UNA mentira."""
    repo = _RAIZ / nombre
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "pega@local")
    _git(repo, "config", "user.name", "pega")
    tablero = repo / "scripts" / "aceptacion.py"
    tablero.write_text(_tablero() if fuente is None else fuente, encoding="utf-8", newline="\n")
    if commitea:
        _git(repo, "add", "-f", "--", "scripts/aceptacion.py")
        _git(repo, "commit", "-qm", "tablero de pega")
    return {"raiz": repo, "tablero": tablero,
            "juez": _juez(set(vigiladas), siempre_protesta=siempre_protesta)}


HONESTO = _fabrica("honesto")


def _sonda(mundo):
    """`_medir()` de verdad, sobre el tablero de pega y con el juez inyectado."""
    orig = (S.RAIZ, S.TABLERO, S._corre_la_suite)
    S.RAIZ, S.TABLERO, S._corre_la_suite = mundo["raiz"], mundo["tablero"], mundo["juez"]
    try:
        return S._medir()
    finally:
        S.RAIZ, S.TABLERO, S._corre_la_suite = orig


MENTIROSOS = {
    # Mutar sobre cambios sin commitear arriesga perderlos al restaurar. Y no poder hacer el
    # experimento NUNCA es «todo vigilado».
    "el_tablero_tiene_cambios_sin_guardar": (_fabrica("sin_commitear", commitea=False),
                                             "cambios sin guardar"),
    # Sin `COMPROBADORES` no hay de dónde derivar las piezas. Derivarlas es a propósito: una lista
    # a mano envejecería igual que el problema que intenta resolver.
    "el_tablero_no_expone_comprobadores": (_fabrica("sin_comprobadores",
                                                    fuente=_tablero(con_comprobadores=False)),
                                           "no se pudo leer el tablero"),
    # Ninguna pieza tiene un `return False` que negar. Un tablero así no se puede saboteaR, y eso
    # es sospechoso, no limpio: el experimento saldría verde sin haber hecho nada.
    "cero_piezas_de_cableado": (_fabrica("sin_cable", fuente=_tablero(con_cable=False)),
                                "cero piezas de cableado"),
    # El juez protesta pase lo que pase. Toda mutación parecería cazada y esto saldría VERDE
    # afirmando que las piezas están vigiladas cuando no ha medido absolutamente nada.
    "la_suite_ya_falla_antes_de_mutar": (_fabrica("juez_roto", siempre_protesta=True),
                                         "no puede hacer de juez"),
    # Y el hallazgo de verdad: `beta` puede volverse incapaz de dar un rojo y ninguna prueba se
    # entera. Todo comprobador que cuelgue de ella es decorativo desde ese momento.
    "una_pieza_ciega": (_fabrica("pieza_ciega", vigiladas=("alfa",)),
                        "INCAPACES DE PONERSE ROJAS"),
}


@pytest.fixture(scope="module", autouse=True)
def _limpiar():
    yield
    shutil.rmtree(_RAIZ, ignore_errors=True)


def test_el_mundo_honesto_APRUEBA():
    """Dos piezas, las dos vigiladas, y el juez sabe distinguir. Sin esto nada de abajo prueba nada."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    mundo, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(mundo)
    assert not ok, nombre + " aprobo, y su cableado no estaba vigilado"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_la_pieza_ciega_se_NOMBRA():
    """Un rojo que dice «hay una pieza ciega» y no cuál no acciona nada: hay nueve donde mirar."""
    mundo, _ = MENTIROSOS["una_pieza_ciega"]
    _, motivo = _sonda(mundo)
    assert "beta" in motivo, motivo
    assert "alfa" not in motivo, "acusa tambien a la pieza que SI esta vigilada: " + motivo


def test_el_tablero_se_RESTAURA_byte_a_byte():
    """Si la mutación se quedara puesta, el repo se queda con todos los guardianes incapaces de
    decir que no — y el siguiente que corra la suite verá verdes que no significan nada."""
    mundo = _fabrica("restaura")
    antes = mundo["tablero"].read_bytes()
    _sonda(mundo)
    assert mundo["tablero"].read_bytes() == antes


def test_un_return_False_que_vive_en_la_PROSA_no_cuenta_como_cable():
    """El fallo del 2026-09-01: el comprobador mutó su propio docstring y se acusó de estar ciego.

    Un comentario que habla de código no es código. Mirando el árbol sintáctico eso deja de poder
    confundirse — y la diferencia se paga entera, porque la acusación falsa señalaba a una pieza
    perfectamente sana.
    """
    fuente = ('def gamma():\n'
              '    """Explica que hace un `return False, motivo` sin tener ninguno."""\n'
              '    return _delega("x.py", "verde")\n'
              '\n\n'
              'COMPROBADORES = {"gamma": gamma}\n')
    assert S.piezas_de_cableado(fuente) == [], "conto la prosa como cable"
