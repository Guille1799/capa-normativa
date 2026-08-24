"""La coartada de las DOS FÁBRICAS que producen 20 de los 26 comprobadores no mutables.

Veinte entradas de `SIN_MUTACION` no están escritas a mano: salen de dos funciones,
`_fabrica_bug` y `_fabrica_inv`, y lo único que cambia entre una y otra es una cadena — el nodo
de pytest o el comando. O sea que **la máquina que decide su color es la misma para las veinte**,
y verla cambiar de color una vez las cubre a las veinte.

Que sea así es lo que hace honesta la coartada, y también lo que marca su límite. Este fichero
demuestra:

  · que la fábrica de `bug-*` distingue los TRES desenlaces que dice distinguir —cerrado,
    sin escribir, y existe-pero-falla—, que es la distinción que impide leer un test mal
    nombrado como trabajo pendiente para siempre;
  · que la fábrica de `inv-*` traduce exit 0 a verde y exit != 0 a pendiente;
  · que el fichero que nombra cada `bug-*` EXISTE, para que su rojo signifique «falta el test»
    y no «la ruta está mal escrita».

Lo que NO demuestra, y conviene decirlo: que el nodo concreto de cada `bug-*` esté bien
nombrado dentro de su fichero. Eso sólo se sabrá el día que alguien escriba ese test. Para los
`inv-*` esa mitad sí está cubierta, y por otro sitio: `tests/test_inv_ejecutan_de_verdad.py`
comprueba que cada comando LLEGA A EJECUTARSE, que es el fallo por el que cuatro de ellos
llevaban meses diciendo «pendiente» sin haber arrancado nunca.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TABLERO = RAIZ / "scripts" / "aceptacion.py"


def _tablero():
    spec = importlib.util.spec_from_file_location("tablero_fabricas", str(TABLERO))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TB = _tablero()


def _fichero_de_test(tmp_path: Path, nombre: str, cuerpo: str) -> Path:
    """Un fichero de test de pega, con nombre propio para que pytest no confunda dos módulos."""
    f = tmp_path / nombre
    f.write_text(cuerpo, encoding="utf-8")
    return f


# ── la fábrica de los `bug-*`: tres desenlaces, y los tres significan cosas distintas ─────────

def test_bug_con_su_nodo_PASANDO_es_VERDE(tmp_path):
    """El desenlace «cerrado». Sin este, una fábrica que dijera ROJO SIEMPRE pasaría los dos
    tests de abajo y parecería sana."""
    f = _fichero_de_test(tmp_path, "test_pega_verde.py",
                         "def test_cerrado():" + chr(10) + "    assert True" + chr(10))
    chk = TB._fabrica_bug("bug-de-pega", str(f) + "::test_cerrado", "un defecto inventado")
    ok, motivo = chk()
    assert ok is True, motivo
    assert motivo.startswith("cerrado:")


def test_bug_con_su_nodo_INEXISTENTE_dice_SIN_ESCRIBIR(tmp_path):
    """El desenlace que da sentido a la fábrica.

    pytest sale 4 cuando no encuentra el nodo y 1 cuando el test existe y falla. Los dos son
    «rojo», pero sólo el segundo significa que alguien escribió el test. Si la fábrica no los
    separara, un test mal nombrado se leería como trabajo pendiente para siempre — y eso no se
    distingue mirando el tablero.
    """
    chk = TB._fabrica_bug("bug-de-pega", str(tmp_path / "no_existe.py") + "::test_x",
                          "un defecto inventado")
    ok, motivo = chk()
    assert ok is False
    assert motivo.startswith("sin escribir:"), motivo


def test_bug_con_su_nodo_FALLANDO_dice_que_EXISTE_Y_FALLA(tmp_path):
    """El otro rojo: el test está escrito, el defecto sigue vivo. Trabajo empezado, no trabajo
    por empezar."""
    f = _fichero_de_test(tmp_path, "test_pega_roja.py",
                         "def test_el_defecto_sigue():" + chr(10)
                         + "    assert False, 'el defecto sigue ahi'" + chr(10))
    chk = TB._fabrica_bug("bug-de-pega", str(f) + "::test_el_defecto_sigue",
                          "un defecto inventado")
    ok, motivo = chk()
    assert ok is False
    assert motivo.startswith("el test existe y FALLA"), motivo


def test_los_tres_desenlaces_de_bug_dan_MENSAJES_distintos(tmp_path):
    """Tres estados con el mismo texto son un estado. La distinción sólo vale si se ve."""
    f_ok = _fichero_de_test(tmp_path, "test_pega_tres_ok.py",
                            "def test_a():" + chr(10) + "    assert True" + chr(10))
    f_mal = _fichero_de_test(tmp_path, "test_pega_tres_mal.py",
                             "def test_b():" + chr(10) + "    assert False" + chr(10))
    motivos = {
        TB._fabrica_bug("b", str(f_ok) + "::test_a", "r")()[1],
        TB._fabrica_bug("b", str(f_mal) + "::test_b", "r")()[1],
        TB._fabrica_bug("b", str(tmp_path / "nada.py") + "::test_c", "r")()[1],
    }
    assert len(motivos) == 3, motivos


# ── la fábrica de los `inv-*`: un exit code y nada más ────────────────────────────────────────

def _inv(comando: str):
    return TB._fabrica_inv("inv-de-pega", comando, "un hallazgo inventado del inventario")


def test_inv_con_exit_0_es_VERDE():
    chk = _inv(sys.executable + ' -c "import sys; sys.exit(0)"')
    ok, motivo = chk()
    assert ok is True, motivo
    assert motivo.startswith("hecho:")


def test_inv_con_exit_distinto_de_0_es_PENDIENTE():
    chk = _inv(sys.executable + ' -c "import sys; sys.exit(1)"')
    ok, motivo = chk()
    assert ok is False
    assert motivo.startswith("pendiente:"), motivo


def test_inv_no_opina_sobre_la_SALIDA_solo_sobre_el_exit_code():
    """La regla del tablero entero: se pregunta por un exit code, nunca por el significado de un
    texto. Un comando que grita por stderr y sale 0 está VERDE, y tiene que estarlo."""
    chk = _inv(sys.executable + ' -c "import sys; print(\'ROJO ROJO ROJO\'); sys.exit(0)"')
    ok, _motivo = chk()
    assert ok is True


def test_inv_desnuda_el_comando_y_deja_fuera_la_prosa():
    """Nueve aceptaciones metían la explicación en el mismo campo que el comando y el shell la
    recibía entera. Con `powershell -Command` eso se concatena al código y lo revienta: el
    comprobador quedaba incerrable dijera nadie lo que dijera.

    Aquí la prosa lleva un `exit 1` dentro a propósito: si se colara al shell, el verde se
    convertiría en rojo y este test lo cantaría.
    """
    bruto = ("`" + sys.executable + ' -c "import sys; sys.exit(0)"` ' + chr(8212)
             + " y esta explicacion NO debe ejecutarse: exit 1")
    ok, _motivo = _inv(bruto)()
    assert ok is True


# ── que el rojo de cada `bug-*` signifique «falta el test» y no «la ruta está mal» ────────────

@pytest.mark.parametrize("nombre", sorted(getattr(TB, "_BUGS", {})))
def test_el_fichero_que_nombra_cada_bug_existe(nombre):
    """Un nodo cuyo FICHERO no existe sale 4 igual que uno sin escribir: rojo permanente y
    tarea incerrable, con el mismo texto que un rojo legítimo."""
    nodo = str(TB._BUGS[nombre][0])
    fichero = nodo.split("::", 1)[0]
    assert (RAIZ / fichero).is_file(), (
        nombre + ": nombra " + fichero + ", que no existe. Su ROJO diria «sin escribir» para "
        "siempre, y quien escribiera el test no lo bajaria del tablero.")


def test_hay_fabricas_que_comprobar():
    """Un parametrize sobre una lista vacía son cero tests, y cero tests en verde parecen éxito."""
    assert getattr(TB, "_BUGS", None), "no se leyo _BUGS: los tests de arriba pasarian en vacio"
    assert callable(getattr(TB, "_fabrica_bug", None))
    assert callable(getattr(TB, "_fabrica_inv", None))
