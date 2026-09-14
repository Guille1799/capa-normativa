"""MENTIROSOS de `_fabrica_bug`: tres tests de pega, y la distinción que el tablero se juega ahí.

## Qué es un mentiroso

Una implementación **completa** de la cosa que se juzga —aquí, el test que cierra un defecto: los
DOCE comprobadores `bug-*` del tablero salen de esta fábrica— rota por **UNA sola razón**, con el
test exigiendo que caiga **en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

## Qué protege

La fábrica no opina sobre el contenido de nada: pregunta por un EXIT CODE, que es la regla entera
de este tablero. Lo que sí hace, y es lo único que hace falta probar, es **separar dos rojos que
se ven idénticos en la pantalla**:

  · pytest sale **4** cuando no encuentra el nodo -> el test no está escrito;
  · pytest sale **1** cuando el test existe y falla -> alguien lo escribió y el defecto sigue.

Los dos son rojo. Sólo el segundo significa que hay trabajo hecho. Si el tablero no los separa, un
test **mal nombrado** se lee como trabajo pendiente para siempre — y nadie va a mirar el nombre,
porque el tablero ya está diciendo que falta el trabajo.
"""
from __future__ import annotations

import importlib.util
import shutil
import tempfile
from pathlib import Path

import pytest

TABLERO = Path(__file__).resolve().parent.parent / "scripts" / "aceptacion.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("tablero_para_fabrica", str(TABLERO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _cargar()

#: Un árbol de pega con sus tests. El de verdad no se toca: la fábrica corre pytest con
#: `cwd=RAIZ`, así que apuntar `RAIZ` a otro sitio es toda la costura que hace falta.
_RAIZ = Path(tempfile.mkdtemp(prefix="mentirosos-bugs-"))
(_RAIZ / "tests").mkdir(parents=True, exist_ok=True)

_RESUMEN = "arreglar: el barrido dice 4 cuando ha mirado 0 ficheros"


@pytest.fixture(scope="module", autouse=True)
def _limpiar():
    yield
    shutil.rmtree(_RAIZ, ignore_errors=True)


def _fabrica(nombre, *, cuerpo="assert True", escribe=True, funcion="test_el_defecto_esta_cerrado"):
    """El test que cierra el defecto, de pega. Por defecto el HONESTO: existe, corre y pasa."""
    nodo = "tests/test_" + nombre + ".py::" + funcion
    if escribe:
        (_RAIZ / "tests" / ("test_" + nombre + ".py")).write_text(
            "def " + funcion + "():\n    " + cuerpo + "\n", encoding="utf-8")
    return nodo


HONESTO = _fabrica("cerrado")


def _sonda(nodo):
    """El comprobador que fabricaría el tablero, apuntado al árbol de pega."""
    original = T.RAIZ
    T.RAIZ = _RAIZ
    try:
        return T._fabrica_bug("bug-de-pega", nodo, _RESUMEN)()
    finally:
        T.RAIZ = original


MENTIROSOS = {
    # El test no existe. Es la promesa sin empezar, y su mensaje tiene que decir eso mismo.
    "sin_escribir": (_fabrica("ausente", escribe=False), "sin escribir"),
    # El test está escrito y el defecto sigue vivo. Mismo color, trabajo completamente distinto: no
    # hay que escribir nada, hay que arreglar el bug.
    "existe_y_el_defecto_sigue": (_fabrica("vivo", cuerpo="assert False, 'el barrido sigue diciendo 4'"),
                                  "el test existe y FALLA"),
    # El fichero está y el NODO no: el test se renombró. Cuenta como no escrito, y ésa es
    # justamente la trampa — el tablero pedirá para siempre un trabajo que ya está hecho, y la
    # pista que lo desharía (el nombre) no está en ningún sitio salvo aquí.
    "el_test_se_renombro": (_fabrica("renombrado", funcion="test_con_otro_nombre").replace(
        "test_con_otro_nombre", "test_el_defecto_esta_cerrado"), "sin escribir"),
}


def test_el_test_honesto_APRUEBA():
    """Y su motivo dice qué se cerró: un verde sin nombre no se puede auditar después."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo
    assert "cerrado" in motivo and _RESUMEN[:20] in motivo, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    nodo, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(nodo)
    assert not ok, nombre + " aprobo, y su defecto seguia abierto"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_los_DOS_rojos_no_dicen_lo_mismo():
    """La comprobación directa de lo único que esta fábrica añade sobre «corre y mira el exit».

    Se hace aparte y comparando los dos motivos entre sí: que cada uno contenga su pista no impide
    que ambos digan además lo mismo, y entonces quien lea el tablero seguiría sin poder
    distinguirlos.
    """
    _, ausente = _sonda(MENTIROSOS["sin_escribir"][0])
    _, roto = _sonda(MENTIROSOS["existe_y_el_defecto_sigue"][0])
    assert ausente != roto, "el rojo por AUSENCIA y el rojo por FALLO salen con el mismo texto"
