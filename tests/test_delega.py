"""`_delega` traduce el resultado de un guion a un color, y esa traducción no la probaba nadie.

## Por qué existe este fichero

`_delega` es la pieza de la que cuelgan **siete** comprobadores: es la que corre el guion de cada
uno y decide si su salida significa verde, rojo o mudo. Un error ahí no rompe nada visible — deja
al comprobador perfecto y al tablero ciego.

MEDIDO el 2026-09-01 con `sabotaje-del-cableado`: volteándole los `return False` —o sea dejándola
**incapaz de dar un rojo jamás**— las 694 pruebas seguían pasando. Ni una se enteraba. Y el efecto
real es éste, observado ese día con el sabotaje puesto:

    🟢 escaparate-sin-rutas-de-casa  YA PUBLICADO ... eu-political-observatory 2

El mensaje acusa y el color absuelve. El comprobador está diciendo que hay una ruta de casa
publicada en GitHub, y el tablero lo pinta de verde.

## Qué se prueba, y por qué cada caso

La tabla entera de traducción, porque cada fila corresponde a una decisión distinta y las tres
casillas tienen que poder distinguirse. Lo único prohibido de verdad es que algo que no es un
éxito acabe en VERDE.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
TABLERO = RAIZ / "scripts" / "aceptacion.py"

#: Un guion que EXISTE de verdad, para pasar la primera guarda sin falsificar el sistema de
#: ficheros. Lo que se falsifica es sólo lo que devuelve al ejecutarlo.
GUION_REAL = "ci_de_los_publicos_en_verde.py"


@pytest.fixture(scope="module")
def tb():
    spec = importlib.util.spec_from_file_location("tablero_delega", str(TABLERO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "_delega"):
        pytest.skip("el tablero ya no delega por `_delega`")
    return mod


class _Resultado:
    def __init__(self, returncode, salida=b""):
        self.returncode = returncode
        self.stdout = salida
        self.stderr = b""


def _contesta(monkeypatch, resultado):
    """Falsifica lo que devuelve el guion, sin tocar el disco.

    Va por `monkeypatch` y no por asignación: `_delega` importa `subprocess` dentro, así que una
    asignación caería sobre el módulo GLOBAL y se quedaría puesta el resto de la sesión. Eso ya
    tumbó 68 tests ajenos el 2026-08-30.
    """
    def falso(*a, **k):
        if isinstance(resultado, BaseException):
            raise resultado
        return resultado
    monkeypatch.setattr(subprocess, "run", falso)


def test_salida_0_es_VERDE(tb, monkeypatch):
    _contesta(monkeypatch, _Resultado(0, b"VERDE: todo en orden\n"))
    ok, msg = tb._delega(GUION_REAL, "por defecto")
    assert ok is True
    assert msg == "todo en orden", f"el prefijo del color se queda en el mensaje: {msg!r}"


def test_salida_1_es_ROJO(tb, monkeypatch):
    """La fila que el sabotaje volteaba, y la que nadie probaba."""
    _contesta(monkeypatch, _Resultado(1, b"ROJO: hay dos ficheros con la ruta de casa\n"))
    ok, msg = tb._delega(GUION_REAL, "por defecto")
    assert ok is not True, "un guion que falla NO puede leerse como exito"
    assert ok is False, f"deberia ser ROJO: {msg}"
    assert msg == "hay dos ficheros con la ruta de casa"


def test_salida_3_es_MUDO(tb, monkeypatch):
    """3 = NO CONCLUYENTE. Ni aprobado ni infraccion: no se ha podido medir."""
    _contesta(monkeypatch, _Resultado(3, b"MUDO: gh no contesta\n"))
    ok, msg = tb._delega(GUION_REAL, "por defecto")
    assert ok is None, f"un 3 tiene que ser MUDO y no {ok!r}: {msg}"
    assert msg == "gh no contesta"


def test_un_guion_que_se_CUELGA_es_MUDO(tb, monkeypatch):
    """Colgarse no es un veredicto: es no haber podido medir. Si se cuelga siempre, insistira y
    la ronda lo sube a ROJO sola a los dos dias CON ronda."""
    _contesta(monkeypatch, subprocess.TimeoutExpired(cmd="x", timeout=900))
    ok, msg = tb._delega(GUION_REAL, "por defecto")
    assert ok is None and "cuelga" in msg


def test_un_guion_que_NO_LLEGA_A_ARRANCAR_es_MUDO(tb, monkeypatch):
    """Bajo carga, esta maquina falla al lanzar procesos (OSError 6). Eso no dice nada sobre la
    promesa vigilada — es la causa que sospechamos detras de los comprobadores que parpadean."""
    _contesta(monkeypatch, OSError(6, "The handle is invalid"))
    ok, msg = tb._delega(GUION_REAL, "por defecto")
    assert ok is None and "no se pudo lanzar" in msg


def test_un_guion_que_NO_EXISTE_es_ROJO_y_no_mudo(tb, monkeypatch):
    """Y este SI es rojo, a proposito: no es que no se haya podido mirar, es que FALTA el que
    tenia que mirar. Un mudo lo perdonaria dos dias."""
    ok, msg = tb._delega("no_existe_este_guion.py", "por defecto")
    assert ok is False, f"un guion ausente no puede ser mudo: {msg}"
    assert "no existe" in msg


def test_un_fallo_SIN_MENSAJE_sigue_siendo_rojo(tb, monkeypatch):
    """Un guion que muere callado no puede colarse por la rendija de «no dijo nada»."""
    _contesta(monkeypatch, _Resultado(1, b""))
    ok, msg = tb._delega(GUION_REAL, "por defecto")
    assert ok is False and msg == "falla sin mensaje"


def test_usa_salida_False_ignora_lo_que_diga_el_guion(tb, monkeypatch):
    """Tres comprobadores prefieren su frase fija a la ultima linea del guion. Aunque el mensaje
    venga de otro sitio, el COLOR sigue saliendo del codigo de salida."""
    _contesta(monkeypatch, _Resultado(0, b"cualquier cosa\n"))
    ok, msg = tb._delega(GUION_REAL, "la frase fija", usa_salida=False)
    assert ok is True and msg == "la frase fija"

    _contesta(monkeypatch, _Resultado(1, b"ROJO: algo va mal\n"))
    ok, msg = tb._delega(GUION_REAL, "la frase fija", usa_salida=False)
    assert ok is False, "con usa_salida=False el color tiene que seguir viniendo del exit code"


def test_el_mensaje_se_CORTA_pero_el_color_no_cambia(tb, monkeypatch):
    """Un guion charlatan no puede tumbar el tablero ni cambiar su veredicto."""
    _contesta(monkeypatch, _Resultado(1, b"ROJO: " + b"x" * 5000 + b"\n"))
    ok, msg = tb._delega(GUION_REAL, "por defecto", corte=50)
    assert ok is False and len(msg) <= 50
