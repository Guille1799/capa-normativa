"""Un guardián que figura en el censo pero está apagado sigue figurando. Aquí se prueba lo contrario.

El test que más importa es el último: **una fuente que no contesta es ROJO**, nunca «ningún guardián
muerto». Es la misma trampa que persigue todo el arnés, aplicada al guardián de los guardianes — y
el sitio donde más barata sale, porque un verde por no haber mirado no se distingue de un verde de
verdad.
"""
from __future__ import annotations

import datetime
import importlib.util
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parent.parent / "scripts" / "aceptaciones" / "guardianes_vivos.py"
HOY = datetime.datetime(2026, 8, 24, 12, 0, 0)


def _cargar():
    spec = importlib.util.spec_from_file_location("vivos_bajo_prueba", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tarea(nombre="ralph-cn", estado="Ready", ultima=None, resultado="0",
           accion=r"C:\proyectos\ralph_cn.cmd"):
    """Una tarea del Programador, RECIÉN corrida salvo que se diga otra cosa.

    ⚠️ La fecha por defecto **se deriva del reloj y no se escribe**. Estaba escrita —`8/24/2026`—
    y el 2026-08-31 este fichero se puso rojo solo, a media sesión y sin que nadie lo tocara:
    `test_verde_solo_cuando_todas_las_tuyas_viven` llama a `guardianes_vivos()` SIN inyectarle
    `hoy`, así que compara contra el reloj de verdad. Siete días después de esa fecha, la tarea de
    mentira cruzó `_DIAS_SIN_CORRER` y el test empezó a fallar.

    Era una bomba de relojería con fecha de detonación conocida. Y el arreglo sólido no es mover
    el número —eso sólo la reprograma para dentro de una semana— sino que **no haya número que
    mover**. Los tests que sí necesitan una fecha concreta la siguen pasando a mano.
    """
    if ultima is None:
        ultima = datetime.datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
    return {"nombre": nombre, "accion": accion, "estado": estado,
            "ultima": ultima, "resultado": resultado}


# --- las tres señales de muerte ---------------------------------------------


def test_una_tarea_DESACTIVADA_esta_muerta():
    m = _cargar()
    caidos = m.muertos([_tarea(estado="Disabled")], hoy=HOY)
    assert len(caidos) == 1
    assert "DESACTIVADA" in caidos[0][1]


def test_una_tarea_activa_que_no_corre_desde_hace_meses_esta_muerta():
    """El caso real: `ClaudeWarmup`, activa en el papel y sin correr desde el 12 de junio."""
    m = _cargar()
    caidos = m.muertos([_tarea(ultima="6/12/2026 8:36:35 AM")], hoy=HOY)
    assert len(caidos) == 1
    assert "sin correr" in caidos[0][1]


def test_un_codigo_de_WINDOWS_es_muerte():
    """0x800705AF — «el fichero de paginacion es demasiado pequeño». Lo puso el sistema porque el
    programa no llego a terminar."""
    m = _cargar()
    caidos = m.muertos([_tarea(resultado="2147943855")], hoy=HOY)
    assert len(caidos) == 1
    assert "NO llego a terminar" in caidos[0][1]


def test_un_guardian_que_GRITA_no_esta_muerto():
    """La correccion del 2026-08-24, y el test que impide que vuelva.

    Tres guardianes salen != 0 POR DISEÑO cuando encuentran algo: `healthcheck.py` sale 1 con
    resultado DEGRADED, `test-regresion-diaria.ps1` sale 1 cuando la regresion falla, y
    `ralph_diario.sh` usa 2 para «atascado». La primera version de este comprobador los llamaba
    muertos a los tres — llenaba el rojo de ruido, y un comprobador ruidoso se deja de leer.

    Un codigo pequeño lo eligio el programa: es un HALLAZGO suyo. Reportarlo es trabajo de cada
    guardian, no de este.
    """
    m = _cargar()
    for codigo in ("1", "2", "3"):
        assert m.muertos([_tarea(resultado=codigo)], hoy=HOY) == [], f"exit {codigo} no es muerte"


def test_la_frontera_esta_donde_la_pone_Windows():
    """Justo por debajo del umbral es hallazgo; justo por encima, muerte. Sin esta pareja, mover
    el umbral no rompe nada y deja de significar lo que dice."""
    m = _cargar()
    assert m.muertos([_tarea(resultado=str(0x7FFFFFFF))], hoy=HOY) == []
    assert len(m.muertos([_tarea(resultado=str(0x80000000))], hoy=HOY)) == 1


# --- lo que NO es muerte ------------------------------------------------------


def test_una_tarea_sana_no_sale():
    m = _cargar()
    assert m.muertos([_tarea()], hoy=HOY) == []


def test_la_que_esta_CORRIENDO_ahora_mismo_no_esta_muerta():
    """267009 no es un fallo: es «aun no ha terminado». Sin esto, una ronda se pone roja al
    medirse a sí misma mientras corre — pasó de verdad el 2026-08-23."""
    m = _cargar()
    assert m.muertos([_tarea(resultado="267009")], hoy=HOY) == []


def test_un_actualizador_de_terceros_NO_se_juzga():
    """Adobe, Edge, NVIDIA y OneDrive no son guardianes tuyos. La primera versión los juzgaba y
    sacaba 12 muertos de 24, la mitad ruido — y un comprobador ruidoso no se lee."""
    m = _cargar()
    ajena = _tarea(nombre="Launch Adobe CCXProcess", resultado="2147942402",
                   accion=r"C:\Program Files\Adobe\CCXProcess.exe")
    assert m.muertos([ajena], hoy=HOY) == []


def test_las_corridas_perdidas_NO_cuentan_como_muerte():
    """Un portátil apagado a las 3:00 acumula perdidas sin que nada esté roto."""
    m = _cargar()
    t = _tarea()
    t["perdidas"] = "3"
    assert m.muertos([t], hoy=HOY) == []


# --- no aprobar por no haber podido mirar ------------------------------------


def test_una_fecha_ilegible_es_muerte_y_no_cero_dias():
    """Si la fecha no se puede leer, lo cómodo es tratarla como «hoy» y dar por viva la tarea.
    Eso es aprobar en vacío con otro disfraz."""
    m = _cargar()
    caidos = m.muertos([_tarea(ultima="no-es-una-fecha")], hoy=HOY)
    assert len(caidos) == 1
    assert "no ha corrido nunca" in caidos[0][1] or "no se pudo leer" in caidos[0][1]


def test_si_el_Programador_no_contesta_es_ROJO(monkeypatch):
    m = _cargar()

    def revienta():
        raise m.FuenteRota("A general error occurred")

    monkeypatch.setattr(m._censo, "tareas_detalladas", revienta)
    ok, msg = m.guardianes_vivos()
    assert ok is False
    assert "NO HABER MIRADO" in msg


def test_cero_tareas_es_ROJO_y_no_maquina_limpia(monkeypatch):
    m = _cargar()
    monkeypatch.setattr(m._censo, "tareas_detalladas", lambda: [])
    ok, msg = m.guardianes_vivos()
    assert ok is False
    assert "no haber podido mirar" in msg


def test_verde_solo_cuando_todas_las_tuyas_viven(monkeypatch):
    m = _cargar()
    sanas = [_tarea(nombre="ralph-cn"), _tarea(nombre="ronda-de-tableros")]
    monkeypatch.setattr(m._censo, "tareas_detalladas", lambda: sanas)
    ok, msg = m.guardianes_vivos()
    assert ok is True, msg
    assert "2" in msg


# --- la máquina de verdad ----------------------------------------------------


@pytest.mark.maquina
def test_contra_la_maquina_real_la_pregunta_se_puede_hacer():
    """Sin fixtures. No exige que estén vivos —hoy 8 no lo están— sino que la pregunta se pueda
    hacer: si esto revienta, el comprobador no protege de nada."""
    m = _cargar()
    filas = m._censo.tareas_detalladas()
    assert filas, "el Programador no devolvio tareas"
    mias = [t for t in filas if m._es_tuya(t)]
    assert len(mias) >= 10, f"solo {len(mias)} tareas propias: el filtro se ha vuelto loco"


# --- no arrancar tampoco es gritar ------------------------------------------

def test_un_127_es_NO_HABER_ARRANCADO_y_no_un_hallazgo():
    """El caso real del 2026-08-31, con `ralph-eu` muerto dentro durante dias.

    Al sacar el arnes del repo PUBLICO eu-political-observatory para dejarlo presentable, eso
    llego a `main`; el worktree del robot se sincronizo y la sincronizacion BORRO
    `scripts/ralph.sh`, que es lo que su lanzador ejecuta. Desde entonces la tarea arranca, no
    encuentra nada y termina en 127 todos los dias — y este comprobador la daba por VIVA, porque
    127 es un numero pequeño y los pequeños «los elige el programa».

    No este. 127 es lo que devuelve un shell cuando NO ENCUENTRA que ejecutar, y por convencion
    ningun programa lo usa como veredicto propio.
    """
    m = _cargar()
    caidos = m.muertos([_tarea(nombre="ralph-eu", resultado="127")], hoy=HOY)
    assert len(caidos) == 1, "un 127 se ha dado por vivo: la tarea corre y no hace nada"
    assert "ARRANCAR" in caidos[0][1], caidos[0][1]
    assert "no existe" in caidos[0][1], (
        "el motivo tiene que decir QUE mirar, o el rojo no se puede cerrar: " + caidos[0][1])


def test_un_126_tambien(_=None):
    """Existe pero no es ejecutable: en Linux, un .sh sin el bit +x. Misma clase de muerte."""
    m = _cargar()
    caidos = m.muertos([_tarea(resultado="126")], hoy=HOY)
    assert len(caidos) == 1 and "ARRANCAR" in caidos[0][1]


def test_el_arreglo_NO_resucita_el_ruido_que_se_quito_ayer():
    """La otra direccion, y es la que protege el trabajo del 2026-08-30.

    `healthcheck.py` sale 1 cuando ENCUENTRA algo, `test-regresion-diaria.ps1` sale 1 cuando la
    regresion falla, y `ralph_diario.sh` usa 2 para «atascado». Los tres estan gritando, no
    muriendo. Si esta rama nueva se los tragara, volveriamos a llamar muertos a tres que trabajan
    — que es exactamente el ruido que se quito ayer.
    """
    m = _cargar()
    for codigo in ("1", "2", "3"):
        assert m.muertos([_tarea(resultado=codigo)], hoy=HOY) == [], (
            "el codigo " + codigo + " lo eligio el programa: es un hallazgo suyo, no su muerte")
