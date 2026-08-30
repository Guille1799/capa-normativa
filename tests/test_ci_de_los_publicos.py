"""El guardián de la CI cambia de color, y distingue las tres cosas que no son lo mismo.

Un repo con la CI roja, un repo sin CI, y un repo al que no se le puede preguntar son tres estados
distintos. Confundirlos es lo que convierte un guardián en ruido: acusar a un repo de tener la CI
rota cuando no la tiene es la misma mentira que aprobarlo sin mirar, sólo que al revés.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "scripts" / "aceptaciones" / "ci_de_los_publicos_en_verde.py"


def _modulo():
    if not GUION.is_file():
        pytest.skip("no existe ci_de_los_publicos_en_verde.py")
    spec = importlib.util.spec_from_file_location("ci_bajo_prueba", str(GUION))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Respuesta:
    """Lo que devolvería `gh run list --json`, sin llamar a GitHub."""

    def __init__(self, filas, returncode=0, stderr=""):
        self.stdout = json.dumps(filas)
        self.returncode = returncode
        self.stderr = stderr


def _con_gh(mp, mod, respuesta, repos=("uno", "dos")):
    """Le falsifica a `mod` la lista de repos y la respuesta de `gh`, y lo DESHACE al salir.

    Va por `monkeypatch` y no por asignacion directa por un motivo medido el 2026-08-30: escrita
    como asignacion, la sustitucion no cae sobre el modulo bajo prueba sino sobre el `subprocess`
    GLOBAL, que es el mismo objeto para todo el proceso. Se quedaba puesta el resto de la sesion y
    tumbo 68 tests ajenos con el OSError falso de aqui abajo — el test del guardian de la CI
    rompiendo a los demas. `monkeypatch` restaura al terminar cada test.
    """
    mp.setattr(mod, "publicos", lambda: [Path(r) for r in repos])
    mp.setattr(mod.subprocess, "run", lambda *a, **k: respuesta)
    return mod


def test_verde_cuando_la_ultima_esta_en_verde(monkeypatch):
    """La mitad que se olvida: si no puede cerrarse, su rojo no significa nada."""
    mod = _modulo()
    _con_gh(monkeypatch, mod, _Respuesta([{"conclusion": "success", "status": "completed",
                              "headBranch": "main", "createdAt": "2026-08-30T10:00:00Z",
                              "workflowName": "CI"}]))
    ok, msg = mod.ci_de_los_publicos_en_verde()
    assert ok, f"la ultima corrida esta en verde y ha salido ROJO: {msg}"


def test_rojo_cuando_la_ultima_fallo(monkeypatch):
    """El caso real: capa-normativa estuvo asi SEIS DIAS y nadie lo supo."""
    mod = _modulo()
    _con_gh(monkeypatch, mod, _Respuesta([{"conclusion": "failure", "status": "completed",
                              "headBranch": "main", "createdAt": "2026-08-24T10:00:00Z",
                              "workflowName": "CI"}]))
    ok, msg = mod.ci_de_los_publicos_en_verde()
    assert not ok, "la ultima corrida fallo y ha salido VERDE"
    assert "uno" in msg, f"no dice EN QUE repo, asi que no hay nada que mirar: {msg}"
    assert "2026-08-24" in msg, "no dice CUANDO fue, que es lo que mide la gravedad"


def test_un_repo_SIN_CI_no_cuenta_como_rota(monkeypatch):
    """No tener CI y tenerla rota son cosas distintas, y confundirlas es acusar en falso.

    `eu-political-observatory` se quedo sin workflows el 2026-08-29 al sacarle el arnes del repo
    publico. Pintarlo de rojo por eso seria pedirle que arregle algo que no existe.
    """
    mod = _modulo()
    _con_gh(monkeypatch, mod, _Respuesta([]))
    ok, msg = mod.ci_de_los_publicos_en_verde()
    assert ok, f"un repo sin CI ha puesto ROJO: {msg}"
    assert "sin ninguna corrida" in msg, f"tampoco lo informa, o sea que se pierde: {msg}"


def test_una_corrida_EN_CURSO_no_es_un_fallo(monkeypatch):
    """Todavia no ha dicho nada. Darla por rota seria inventarse un veredicto."""
    mod = _modulo()
    _con_gh(monkeypatch, mod, _Respuesta([{"conclusion": None, "status": "in_progress",
                              "headBranch": "main", "createdAt": "2026-08-30T10:00:00Z",
                              "workflowName": "CI"}]))
    ok, msg = mod.ci_de_los_publicos_en_verde()
    assert ok, f"una corrida en curso ha puesto ROJO: {msg}"
    assert "en curso" in msg


def test_MUDO_si_gh_no_contesta(monkeypatch):
    """No haber podido preguntar NUNCA es «estan verdes» — pero tampoco es una CI rota.

    Es el primer comprobador que estrena la tercera casilla, y aqui esta el porque: desde dentro
    NO hay forma de distinguir un tropiezo de red de que `gh` no este instalado. Diciendo MUDO no
    hace falta distinguirlos: si el impedimento es permanente insistira, y la ronda lo sube a ROJO
    a los dos dias CON ronda. Lo unico prohibido, y lo que protege el primer assert, es el verde.
    """
    mod = _modulo()
    _con_gh(monkeypatch, mod, _Respuesta([], returncode=1, stderr="no auth"))
    ok, msg = mod.ci_de_los_publicos_en_verde()
    assert ok is not True, "no haber podido preguntar se ha leido como «estan verdes»"
    assert ok is None, f"deberia ser MUDO y no ROJO: no es una CI rota, es no haber mirado. {msg}"
    assert "no se pudo" in msg


def test_rojo_y_NO_mudo_si_no_hay_repos_publicos(monkeypatch):
    """Cero repos publicos es un resultado sospechoso, no una maquina limpia.

    Y este SI es rojo: `gh` ha contestado, y ha contestado algo imposible. Eso es haber mirado y
    ver algo que no cuadra, que es lo contrario de no haber podido mirar. La linea entre las dos
    casillas pasa exactamente por aqui.
    """
    mod = _modulo()
    monkeypatch.setattr(mod, "publicos", lambda: [])
    ok, msg = mod.ci_de_los_publicos_en_verde()
    assert ok is False, f"contestar algo imposible es ROJO, no MUDO: {msg}"
    assert "cero repos" in msg


def test_MUDO_si_no_se_puede_lanzar_gh(monkeypatch):
    """Bajo carga esta maquina falla al ARRANCAR procesos, y eso no dice nada sobre la CI.

    Es la causa que sospechamos detras de los 10 comprobadores de la familia mcp que salian rojos
    durante la ronda y verdes al repreguntarles a solas. Con la casilla nueva, este caso deja de
    producir una falsa alarma sin dejar de contarse.
    """
    mod = _modulo()

    def revienta(*a, **k):
        raise OSError(6, "The handle is invalid")

    monkeypatch.setattr(mod, "publicos", lambda: [Path("uno")])
    monkeypatch.setattr(mod.subprocess, "run", revienta)
    ok, msg = mod.ci_de_los_publicos_en_verde()
    assert ok is None, f"un proceso que no arranca es MUDO, no ROJO: {msg}"
    assert "no se pudo" in msg
