"""`revista-de-runtimes` traduce el resultado de su guion a un color, y eso no lo probaba nadie.

MEDIDO el 2026-09-01 con `sabotaje-del-cableado`: volteándole los `return False` —dejándola
**incapaz de dar un rojo jamás**— las 694 pruebas seguían pasando. Ni una.

Es el segundo de los dos agujeros que encontró, y el más solitario: `revista_de_runtimes` es el
único comprobador que se quedó con su propio cable cuando los otros siete se juntaron en
`_delega`, porque su guion vive fuera de `scripts/aceptaciones/` y lleva argumento propio.

Se aprovecha para traerla al contrato de tres casillas, que aún no tenía: colgarse era ROJO, y
colgarse no es un veredicto.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
TABLERO = RAIZ / "scripts" / "aceptacion.py"


@pytest.fixture(scope="module")
def tb():
    spec = importlib.util.spec_from_file_location("tablero_revista", str(TABLERO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Resultado:
    def __init__(self, returncode, salida=b""):
        self.returncode = returncode
        self.stdout = salida
        self.stderr = b""


@pytest.fixture()
def con_guion(tb, monkeypatch, tmp_path):
    """Hace creer al comprobador que su guion existe, sin tocar `~/proyectos`.

    La guarda del guion ausente se prueba aparte; aquí estorbaría, porque en una máquina donde no
    exista el fichero todos los demás casos saldrían por esa rama y no probarían la traducción.
    """
    monkeypatch.setattr(Path, "exists", lambda self: True)


def _contesta(monkeypatch, resultado):
    def falso(*a, **k):
        if isinstance(resultado, BaseException):
            raise resultado
        return resultado
    monkeypatch.setattr(subprocess, "run", falso)


def test_salida_0_es_VERDE(tb, con_guion, monkeypatch):
    _contesta(monkeypatch, _Resultado(0, b"todo cuadra\n"))
    ok, msg = tb.revista_de_runtimes()
    assert ok is True and "cuadran" in msg


def test_salida_distinta_de_cero_es_ROJO(tb, con_guion, monkeypatch):
    """La fila que el sabotaje volteaba, y la que nadie probaba."""
    _contesta(monkeypatch, _Resultado(1, b"ROJO: el interprete no cuadra con el manifiesto\n"))
    ok, msg = tb.revista_de_runtimes()
    assert ok is not True, "una revista que falla NO puede leerse como exito"
    assert ok is False, f"deberia ser ROJO: {msg}"
    assert "manifiesto" in msg


def test_un_fallo_SIN_MENSAJE_sigue_siendo_rojo(tb, con_guion, monkeypatch):
    _contesta(monkeypatch, _Resultado(1, b""))
    ok, msg = tb.revista_de_runtimes()
    assert ok is False and "sin mensaje" in msg


def test_COLGARSE_es_MUDO_y_ya_no_rojo(tb, con_guion, monkeypatch):
    """Contrato de tres casillas. Colgarse no es un veredicto: es no haber podido medir."""
    _contesta(monkeypatch, subprocess.TimeoutExpired(cmd="x", timeout=600))
    ok, msg = tb.revista_de_runtimes()
    assert ok is None, f"colgarse tiene que ser MUDO y no {ok!r}: {msg}"
    assert "no haber medido" in msg


def test_no_llegar_a_ARRANCAR_es_MUDO(tb, con_guion, monkeypatch):
    """Bajo carga esta maquina falla al lanzar procesos. Antes subia como excepcion y el tablero
    lo pintaba de ROJO: una falsa alarma con la forma exacta de las que perseguimos."""
    _contesta(monkeypatch, OSError(6, "The handle is invalid"))
    ok, msg = tb.revista_de_runtimes()
    assert ok is None and "no se pudo lanzar" in msg


def test_salida_3_es_MUDO(tb, con_guion, monkeypatch):
    _contesta(monkeypatch, _Resultado(3, b"MUDO: no se pudo leer el manifiesto\n"))
    ok, msg = tb.revista_de_runtimes()
    assert ok is None and msg == "no se pudo leer el manifiesto"


def test_un_guion_que_NO_EXISTE_es_ROJO_y_dice_la_ruta_ENTERA(tb, monkeypatch):
    """No es mudo: falta el que tenia que mirar. Y la ruta va completa por un motivo medido —
    cuando esta sonda salio roja desde un worktree, el trozo relativo sonaba a que faltaba el
    guion, y lo que fallaba era la carpeta desde la que se miraba."""
    monkeypatch.setattr(Path, "exists", lambda self: False)
    ok, msg = tb.revista_de_runtimes()
    assert ok is False, f"un guion ausente no puede ser mudo: {msg}"
    assert "no existe" in msg and "revista_runtimes.py" in msg
    assert msg.count("/") + msg.count("\\") >= 2, f"la ruta no va entera: {msg}"
