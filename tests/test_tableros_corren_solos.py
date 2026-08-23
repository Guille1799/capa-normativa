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
    comprobadores que quiza ya no saben fallar."""
    m = _chk()
    m.tareas = lambda: [_tarea("python scripts/aceptacion.py")]
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


def test_la_tarea_completa_y_reciente_es_verde():
    """El control. Sin este, un comprobador que siempre dice ROJO tambien pasaria los de arriba."""
    m = _chk()
    m.tareas = lambda: [_tarea("python scripts/aceptacion.py ; python scripts/aceptacion.py --verifica")]
    assert m.main() == 0


def test_sin_poder_leer_las_tareas_es_ROJO_y_no_verde():
    """Aprobar en vacio se lee como «todo al dia», que es peor que no tener la promesa."""
    m = _chk()
    m.tareas = lambda: []
    assert m.main() == 1
