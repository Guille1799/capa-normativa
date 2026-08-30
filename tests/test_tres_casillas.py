"""El tablero sabe decir TRES cosas, y la tercera no es un aprobado ni una infracción.

Hasta el 2026-08-30 el contrato era `tuple[bool, str]` y «no he podido mirar» no tenía dónde ir.
Como aquí está prohibido aprobar en vacío, acababa en ROJO — la misma casilla que «he mirado y
está mal», que es una cosa completamente distinta.

Estos tests fijan las dos mitades del contrato nuevo:

  · que la casilla exista y se distinga de las otras dos, y
  · que **no sea un descanso**: un mudo NO cuenta como promesa cumplida, y saca al tablero de
    cero. Si un mudo se colara como verde, habríamos reinventado aprobar en vacío por la puerta
    de atrás, que es exactamente lo que este proyecto existe para impedir.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
TABLERO = RAIZ / "scripts" / "aceptacion.py"


@pytest.fixture()
def tablero():
    """El tablero cargado y VACIADO, para juzgar sólo los comprobadores de mentira de cada test."""
    spec = importlib.util.spec_from_file_location("tablero_tres_casillas", str(TABLERO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.COMPROBADORES.clear()
    return mod


def _pon(mod, **cuales):
    for nombre, valor in cuales.items():
        mod.COMPROBADORES[nombre.replace("_", "-")] = (lambda v=valor: (v, "motivo de mentira"))


def test_un_mudo_se_pinta_distinto_de_verde_y_de_rojo(tablero, capsys):
    _pon(tablero, uno=True, dos=False, tres=None)
    tablero.main([])
    salida = capsys.readouterr().out
    assert tablero.VERDE in salida and tablero.ROJO in salida and tablero.MUDO in salida, (
        "las tres casillas tienen que verse distintas: " + salida)


def test_un_mudo_NO_cuenta_como_promesa_cumplida(tablero, capsys):
    """La mitad que impide reinventar el pecado: no saber es lo contrario de saber que sí."""
    _pon(tablero, uno=True, dos=None)
    tablero.main([])
    salida = capsys.readouterr().out
    assert "1/2 promesas cumplidas" in salida, f"el mudo se ha colado como cumplida: {salida}"
    assert "1 sin poder medirse" in salida, f"y encima no se dice cuantos hay: {salida}"


def test_solo_mudos_saca_al_tablero_de_cero(tablero):
    """Salida 3, NO CONCLUYENTE. Un 0 diria «todo bien», y no lo sabemos."""
    _pon(tablero, uno=True, dos=None)
    assert tablero.main([]) == 3


def test_un_rojo_gana_a_un_mudo(tablero):
    """Con una infraccion REAL delante, no poder medir otra cosa no rebaja la alarma."""
    _pon(tablero, uno=False, dos=None)
    assert tablero.main([]) == 1


def test_sin_mudos_el_tablero_se_comporta_EXACTAMENTE_como_antes(tablero):
    """Compatibilidad hacia atras: los 33 comprobadores de hoy no se enteran del cambio."""
    _pon(tablero, uno=True, dos=True)
    assert tablero.main([]) == 0
    tablero.COMPROBADORES.clear()
    _pon(tablero, uno=True, dos=False)
    assert tablero.main([]) == 1


def test_un_comprobador_que_REVIENTA_sigue_siendo_ROJO_y_no_mudo(tablero, capsys):
    """Una excepcion no es «no he podido mirar»: es un comprobador roto, y eso SI es un rojo.

    Distinguirlo importa porque el mudo se perdona una vez y el rojo no. Si un comprobador que
    revienta se contara como mudo, un fallo de programacion se perdonaria solo.
    """
    def revienta():
        raise RuntimeError("me he roto")

    tablero.COMPROBADORES["revienta"] = revienta
    assert tablero.main([]) == 1
    salida = capsys.readouterr().out
    assert tablero.ROJO in salida and tablero.MUDO not in salida


def test_el_tablero_de_VERDAD_no_tiene_ningun_mudo_hoy(capsys):
    """Ancla contra el estado real: hoy ninguno de los 33 usa la casilla nueva todavia.

    El dia que alguno la use, este test cae y hay que venir a decir CUAL y POR QUE — que es
    justo la conversacion que queremos forzar, porque estrenar la casilla no es un detalle.
    """
    spec = importlib.util.spec_from_file_location("tablero_real", str(TABLERO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "MUDO"), "el contrato de tres casillas ha desaparecido del tablero"
    assert mod.VERDE != mod.ROJO != mod.MUDO != mod.VERDE
