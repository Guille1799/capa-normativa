"""El comprobador de «los tableros corren solos» tiene que saber decir que NO.

Nace ROJO contra el estado real, así que su verde no se puede observar sin inventar una tarea
programada. Se le inyecta el mundo: es la única forma de demostrar que distingue los cuatro casos
que le importan.

El caso que da sentido a todo esto es el segundo: **una tarea que corre los tableros pero no
`--verifica`**. Sin esa distinción, la promesa se cerraría a medias — y `--verifica` es quien
comprueba que cada comprobador siga sabiendo ponerse rojo. Tableros corriendo solos con
comprobadores que ya no saben fallar es peor que nada: son verdes que no significan nada.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GUION = RAIZ / "scripts" / "aceptaciones" / "tableros_corren_solos.py"


def _chk():
    spec = importlib.util.spec_from_file_location("chk_tableros", str(GUION))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _ahora() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _tarea(accion: str, resultado: int = 0, cuando: str | None = None) -> dict:
    return {"nombre": "T", "accion": accion,
            "ultimo": _ahora() if cuando is None else cuando, "resultado": resultado}


def test_sin_ninguna_tarea_es_rojo():
    """El estado de hoy: nadie ejecuta los tableros solo."""
    m = _chk()
    m.tareas = lambda: [_tarea("powershell -File otra_cosa.ps1")]
    assert m.main() == 1


def test_tableros_si_pero_verifica_NO_es_rojo():
    """El caso que motiva este test. Cerrar la promesa a medias dejaria corriendo los tableros con
    comprobadores que quiza ya no saben fallar.

    Se le inyecta un informe por lo demas PERFECTO —fresco, de la tarea, siete tableros legibles—
    al que solo le falta el `--verifica`. Sin esa inyeccion el test pasaria igual, pero por que el
    informe real esta lanzado a mano: verde por el motivo equivocado es como un test deja de
    probar lo que dice su nombre.
    """
    m = _chk()
    m.tareas = lambda: [_tarea("python scripts/aceptacion.py")]
    sin_verifica = _informe_sano()
    for t in sin_verifica["tableros"]:
        t["verifica"] = {"exit": None, "duracion_s": 0.0, "resumen": "no se llego a correr"}
    m.informe_de_la_ronda = lambda: sin_verifica
    assert m.main() == 1


def test_registrada_pero_que_nunca_termina_bien_es_rojo():
    """«Registrada» no es «arrancando». Ese error exacto ya se cometio con `ollama_chain`: el hook
    estaba en la configuracion y no habia arrancado nunca."""
    m = _chk()
    m.tareas = lambda: [_tarea("python scripts/aceptacion.py --verifica", resultado=1)]
    assert m.main() == 1


def test_registrada_pero_de_hace_un_mes_es_rojo():
    """Una tarea que existe y lleva un mes sin dispararse no vigila nada."""
    m = _chk()
    viejo = (dt.datetime.now() - dt.timedelta(days=30)).isoformat(timespec="seconds")
    m.tareas = lambda: [_tarea("python scripts/aceptacion.py --verifica", cuando=viejo)]
    assert m.main() == 1


def _informe_sano() -> dict:
    """Un informe de ronda recien escrito por la tarea, con los siete tableros legibles."""
    return {
        "terminado": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "lanzador": "tarea-programada",
        "declarados": 7, "corridos": 7,
        "tableros": [{"nombre": "t" + str(i), "estado": "ok", "verdes": 3, "rojos": [],
                      "verifica": {"exit": 0, "duracion_s": 1.0, "resumen": "ok"}}
                     for i in range(7)],
        "huerfanos": [], "ausentes": [],
    }


def test_la_tarea_completa_y_reciente_es_verde():
    """El control. Sin este, un comprobador que siempre dice ROJO tambien pasaria los de arriba.

    ⚠️ Este test cambio el 2026-08-23 por la tarde, y el motivo es que la promesa se hizo MAS
    estricta, no menos. La primera version se conformaba con que la ACCION de una tarea contuviera
    `aceptacion.py`; ahora ademas exige el informe, porque una subcadena no prueba que nada haya
    corrido — una tarea puede arrancar, salir 0 y no haber tocado un tablero. Se le inyecta el
    informe por el mismo sitio que las tareas.
    """
    m = _chk()
    m.tareas = lambda: [_tarea("python scripts/aceptacion.py ; python scripts/aceptacion.py --verifica")]
    m.informe_de_la_ronda = _informe_sano
    assert m.main() == 0


def test_la_tarea_arranca_pero_no_deja_informe_es_ROJO():
    """El agujero que tenia la primera version: `aceptacion.py` dentro de la cadena de la accion es
    una subcadena, y una subcadena no demuestra que se haya corrido ni un tablero."""
    m = _chk()
    m.tareas = lambda: [_tarea("python scripts/aceptacion.py --verifica")]
    m.informe_de_la_ronda = lambda: None
    assert m.main() == 1


def test_un_informe_lanzado_A_MANO_no_vale_como_evidencia():
    """Demuestra que el guion funciona, no que la ronda corra sola."""
    m = _chk()
    m.tareas = lambda: [_tarea("python scripts/aceptacion.py --verifica")]
    a_mano = _informe_sano()
    a_mano["lanzador"] = "a mano"
    m.informe_de_la_ronda = lambda: a_mano
    assert m.main() == 1


def test_un_informe_que_cubre_menos_de_siete_tableros_es_ROJO():
    """No aprueba en vacio, y tampoco a medias: los tableros que no se miraron no estan vigilados."""
    m = _chk()
    m.tareas = lambda: [_tarea("python scripts/aceptacion.py --verifica")]
    corto = _informe_sano()
    corto["corridos"] = 3
    corto["tableros"] = corto["tableros"][:3]
    m.informe_de_la_ronda = lambda: corto
    assert m.main() == 1


def test_la_tarea_de_la_RONDA_tambien_cuenta_como_disparador():
    """La promesa no ata a una implementacion: vale una tarea que encadene `aceptacion.py` y vale
    una que lance la ronda. Lo que no vale es que no haya ninguna."""
    m = _chk()
    m.tareas = lambda: [_tarea("C:\\Users\\Guille\\proyectos\\ronda_de_tableros.cmd")]
    m.informe_de_la_ronda = _informe_sano
    assert m.main() == 0


def test_sin_poder_leer_las_tareas_es_ROJO_y_no_verde():
    """Aprobar en vacio se lee como «todo al dia», que es peor que no tener la promesa."""
    m = _chk()
    m.tareas = lambda: []
    assert m.main() == 1
