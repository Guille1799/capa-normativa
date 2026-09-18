# -*- coding: utf-8 -*-
"""La coartada de `nada-vive-solo-fuera-de-main`: aqui se le ve cambiar de color.

## Por que hace falta este fichero

El comprobador nacio el 2026-09-17 (commit `c898bbd`) y entro en `SIN_MUTACION` el mismo dia,
porque su artefacto es una AUSENCIA --que nada viva fuera de `main`-- y una ausencia no se
fabrica plantando un fichero. La exencion es legitima; lo que no lo es, es quedarse ahi. Un
comprobador SIN ESTRENAR y uno ROTO emiten exactamente la misma senal: siempre el mismo color.

Y no es una hipotesis: ese commit metio los 67 renglones del comprobador en `scripts/aceptacion.py`
y **no metio nada mas**. Sin coartada, la exencion se quedo sin respaldo y el tope de
`exenciones_no_suben.py` se quedo en 34 para 35 exentos.

## Que se prueba, y por que no se ejecuta la pieza de verdad

El comprobador NO implementa la busqueda: le PREGUNTA a
`agent-gates/bin/nada_vive_solo_fuera_de_main.py`, una pieza compartida que vive fuera de este
repo. Asi que lo que aqui se interroga es **el consumidor**: como traduce cada respuesta de la
pieza, y que le pregunta exactamente. La pieza se falsifica; si se corriera la de verdad, el
color de estos tests dependeria del estado del disco y volverian a medir otra cosa.

Los dos casos que mas importan son los de abajo del todo, y son la misma trampa dos veces: que la
pieza **no este** y que la pieza **no se pueda ejecutar** tienen que salir ROJO, nunca verde. Un
comprobador que aprueba porque su herramienta no aparecio es el peor modo de fallo posible: el
hueco se tapa solo y nadie se entera.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TABLERO = RAIZ / "scripts" / "aceptacion.py"


def _tablero():
    spec = importlib.util.spec_from_file_location("tablero_nada_vive", str(TABLERO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TB = _tablero()


class _Respuesta:
    """Lo minimo de `CompletedProcess` que el comprobador mira."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _contesta(monkeypatch, tmp_path, respuesta=None, revienta=None):
    """Monta una pieza compartida de pega que contesta lo que se le diga.

    Devuelve la lista donde quedan grabados los `argv` con que se la llamo: la pregunta que se le
    hace es tan parte del contrato como la respuesta que se traduce.
    """
    pieza = tmp_path / "agent-gates" / "bin" / "nada_vive_solo_fuera_de_main.py"
    pieza.parent.mkdir(parents=True, exist_ok=True)
    pieza.write_text("# pieza de pega\n", encoding="utf-8")
    monkeypatch.setattr(TB, "RAIZ_PROYECTOS", tmp_path)

    llamadas = []

    def _falso_run(argv, **kw):
        llamadas.append((list(argv), kw))
        if revienta is not None:
            raise revienta
        return respuesta

    monkeypatch.setattr(subprocess, "run", _falso_run)
    return llamadas


# --- las dos respuestas normales de la pieza --------------------------------


def test_verde_cuando_la_pieza_dice_que_no_hay_nada_escondido(monkeypatch, tmp_path):
    _contesta(monkeypatch, tmp_path, _Respuesta(0, "nada vive solo fuera de main\n"))
    ok, msg = TB.nada_vive_solo_fuera_de_main()
    assert ok is True
    assert "nada vive solo fuera de main" in msg


def test_rojo_cuando_la_pieza_encuentra_algo_escondido(monkeypatch, tmp_path):
    """Y el mensaje tiene que traer lo que la pieza dijo: un rojo sin el QUE no se puede atender."""
    _contesta(monkeypatch, tmp_path,
              _Respuesta(1, "stash@{0}: datos_de_prueba.json vive SOLO ahi\nmas detalle\n"))
    ok, msg = TB.nada_vive_solo_fuera_de_main()
    assert ok is False
    assert "datos_de_prueba.json" in msg


# --- la pregunta, que es la mitad del contrato ------------------------------


def test_le_pregunta_por_ESTE_repo_y_le_pasa_los_ACEPTADOS(monkeypatch, tmp_path):
    """La pieza es generica: si no se le dice DONDE mirar, mira otra cosa y contesta que todo bien.

    Y los ACEPTADOS viajan en la llamada a proposito. Estan escritos en el cuerpo del comprobador,
    en el diff, para que alguien pueda discutir esa exencion -- no en un fichero de configuracion
    que nadie vuelve a abrir.
    """
    llamadas = _contesta(monkeypatch, tmp_path, _Respuesta(0, "limpio\n"))
    TB.nada_vive_solo_fuera_de_main()
    argv, kw = llamadas[0]
    assert "--repo" in argv and str(TB.RAIZ) in argv
    assert "--acepta" in argv and ".prueba_hook.txt" in argv
    assert kw.get("timeout"), "sin timeout, una pieza colgada cuelga el tablero entero"
    assert kw.get("stdin") is subprocess.DEVNULL, (
        "sin stdin cerrado, una pieza que pregunte algo se queda esperando para siempre")


# --- las tres formas de NO HABER PODIDO MIRAR, que nunca son un aprobado ----


def test_rojo_cuando_la_pieza_NO_esta_y_la_NOMBRA(monkeypatch, tmp_path):
    """La ausencia cae del lado que DICE ALGO, y ademas dice que falta."""
    monkeypatch.setattr(TB, "RAIZ_PROYECTOS", tmp_path)  # sin agent-gates dentro
    ok, msg = TB.nada_vive_solo_fuera_de_main()
    assert ok is False
    assert "nada_vive_solo_fuera_de_main.py" in msg
    assert "no es un aprobado" in msg


def test_rojo_cuando_la_pieza_no_se_puede_EJECUTAR(monkeypatch, tmp_path):
    """Existir no es contestar: un timeout o un interprete roto tampoco son un verde."""
    _contesta(monkeypatch, tmp_path, revienta=subprocess.TimeoutExpired("py", 300))
    ok, msg = TB.nada_vive_solo_fuera_de_main()
    assert ok is False
    assert "TimeoutExpired" in msg
    assert "no se pudo medir" in msg


def test_el_exit_2_se_declara_NO_SE_PUDO_MEDIR_y_no_rojo_a_secas(monkeypatch, tmp_path):
    """La tercera casilla. Un rojo se atiende arreglando el repo; un `no se pudo medir`, arreglando
    la pieza. Confundirlos manda a quien lo lee al sitio equivocado."""
    _contesta(monkeypatch, tmp_path, _Respuesta(2, "no pude leer el reflog\n"))
    ok, msg = TB.nada_vive_solo_fuera_de_main()
    assert ok is False
    assert "no se pudo medir" in msg


# --- y que esta coartada siga apuntando aqui --------------------------------


def test_la_exencion_de_SIN_MUTACION_apunta_a_ESTE_fichero():
    """Si alguien reescribe el motivo y se lleva por delante la cita, la exencion vuelve a quedarse
    sin quien la respalde -- y eso es exactamente lo que este fichero existe para impedir."""
    motivo = str(TB.SIN_MUTACION["nada-vive-solo-fuera-de-main"])
    assert Path(__file__).name in motivo


# --- y una vez sin doble: que la pieza se EJECUTE de verdad --------------------------------------
# Rescatado el 2026-09-18 de un test GEMELO que otra sesion escribio en paralelo y dejo suelto,
# sin trackear, en el worktree cn-ralph. Aquel fichero repetia seis de estas siete pruebas --y
# fallaba su propia auto-referencia, porque la exencion ya apuntaba a ESTE fichero-- pero traia una
# que aqui faltaba y que no es un duplicado: todas las de arriba sustituyen `subprocess.run`, asi
# que comprueban la FORMA de la llamada y nunca llegan a lanzar nada. Si el tablero dejara de
# invocar a la pieza, seguirian verdes. Esta planta un script de verdad y exige su huella.

_PIEZA_DE_VERDAD = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "Path(r{huella!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
    "print('la pieza ha contestado')\n"
    "sys.exit({codigo})\n"
)


def _pieza_que_deja_huella(monkeypatch, tmp_path, codigo=0):
    """Planta una pieza EJECUTABLE y devuelve el fichero donde apuntara sus argv."""
    huella = tmp_path / "argv.json"
    pieza = tmp_path / "agent-gates" / "bin" / "nada_vive_solo_fuera_de_main.py"
    pieza.parent.mkdir(parents=True, exist_ok=True)
    pieza.write_text(_PIEZA_DE_VERDAD.format(huella=str(huella), codigo=codigo), encoding="utf-8")
    monkeypatch.setattr(TB, "RAIZ_PROYECTOS", tmp_path)
    return huella


def test_el_verde_NO_es_por_no_haber_corrido(monkeypatch, tmp_path):
    """Un verde tiene que traer la huella de la ejecucion, o es el aprobado en vacio.

    Aqui NO se sustituye `subprocess.run`: la pieza de pega es un script de verdad que se lanza de
    verdad. Es la unica de este fichero que se enteraria si el tablero dejara de invocarla.
    """
    huella = _pieza_que_deja_huella(monkeypatch, tmp_path, codigo=0)
    ok, motivo = TB.nada_vive_solo_fuera_de_main()
    assert ok, motivo
    assert huella.is_file(), "la pieza no llego a ejecutarse y el comprobador dijo VERDE"
    argv = json.loads(huella.read_text(encoding="utf-8"))
    assert "--repo" in argv and str(TB.RAIZ) in argv, "no le paso el repo a mirar: " + str(argv)


def test_el_rojo_tampoco_es_por_no_haber_corrido(monkeypatch, tmp_path):
    """El gemelo del de arriba, en la otra direccion: un rojo tambien tiene que venir de haber
    preguntado. Un comprobador que se pone rojo sin lanzar nada es igual de mudo que uno verde."""
    huella = _pieza_que_deja_huella(monkeypatch, tmp_path, codigo=1)
    ok, _ = TB.nada_vive_solo_fuera_de_main()
    assert ok is False
    assert huella.is_file(), "dijo ROJO sin haber llegado a ejecutar la pieza"
