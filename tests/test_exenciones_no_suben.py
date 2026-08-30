"""El trinquete de las exenciones cambia de color, y por los cinco motivos que promete.

Se le montan líneas base de pega en un temporal en vez de tocar la de verdad: así se puede exigir
el VERDE, que es la mitad que casi nunca se prueba. Un guardián que sólo se ha visto en rojo podría
estar rojo por estar roto.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "scripts" / "aceptaciones" / "exenciones_no_suben.py"

#: Tres exenciones de mentira, con la forma que el trinquete espera.
_BASE = {
    "uno":  {"value": "tests/test_uno.py", "clase": "test-nombrado", "reason": "porque si"},
    "dos":  {"value": "tests/test_dos.py", "clase": "test-nombrado", "reason": "porque tambien"},
    "tres": {"value": "autoprueba", "clase": "autoprueba", "reason": "se prueba sola"},
}


def _modulo():
    if not GUION.is_file():
        pytest.skip("no existe exenciones_no_suben.py")
    spec = importlib.util.spec_from_file_location("trinquete_bajo_prueba", str(GUION))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _montar(mod, tmp_path, actual, baseline=None, tope=None):
    """Le pone al comprobador una línea base de pega y un estado actual de pega."""
    f = tmp_path / "baseline.json"
    f.write_text(json.dumps(baseline if baseline is not None else _BASE), encoding="utf-8")
    mod.BASELINE = f
    mod.TOPE = tope if tope is not None else len(baseline or _BASE)
    mod.estado_actual = lambda: actual
    return mod


def test_verde_cuando_nada_sube(tmp_path):
    """La mitad que se olvida: si no puede cerrarse, su rojo no significa nada."""
    mod = _modulo()
    _montar(mod, tmp_path, dict(_BASE))
    ok, msg = mod.exenciones_no_suben()
    assert ok, f"nada ha cambiado y ha salido ROJO: {msg}"


def test_rojo_con_una_exencion_NUEVA(tmp_path):
    """El caso que motivó todo: un comprobador nuevo que nace exento sin que nadie lo impida.

    Así se vació la lista hasta 31 de 31 — cada detector mejor que el simulacro se declaraba
    exento, y ninguna guarda contaba.
    """
    mod = _modulo()
    actual = dict(_BASE)
    actual["cuatro"] = {"value": "tests/test_cuatro.py", "clase": "test-nombrado",
                        "reason": "el numero 32"}
    _montar(mod, tmp_path, actual)
    ok, msg = mod.exenciones_no_suben()
    assert not ok, "una exencion nueva ha salido VERDE"
    assert "cuatro" in msg, f"no dice CUAL es la nueva, asi que no hay nada que mirar: {msg}"


def test_rojo_cuando_una_coartada_apunta_a_OTRO_test(tmp_path):
    """El caso que un contador NO ve: el numero no sube, pero la prueba que respalda la exencion
    ha cambiado. Vigilar solo la cuenta dejaria pasar un cambio de coartada en silencio."""
    mod = _modulo()
    actual = dict(_BASE)
    actual["uno"] = dict(_BASE["uno"], value="tests/test_otro_distinto.py")
    _montar(mod, tmp_path, actual)
    ok, msg = mod.exenciones_no_suben()
    assert not ok, "la coartada apunta a otro test y ha salido VERDE"
    assert "uno" in msg


def test_rojo_con_el_tope_FLOJO(tmp_path):
    """Una holgura permite empeorar sin que nadie lo note, asi que la holgura es el hallazgo.

    Esta comprobacion la trae el trinquete del paquete de fabrica, y corrigio el diseno de este
    comprobador el dia que se escribio: el tope se habia puesto en 32 anticipando una exencion que
    todavia no existia, y el trinquete lo canto.
    """
    mod = _modulo()
    _montar(mod, tmp_path, dict(_BASE), tope=len(_BASE) + 5)
    ok, msg = mod.exenciones_no_suben()
    assert not ok, "un tope con holgura ha salido VERDE"
    assert "flojo" in msg.lower() or "tope" in msg.lower()


def test_rojo_si_no_se_puede_leer_el_tablero(tmp_path):
    """No haber podido mirar NUNCA es «no hay exenciones». Un tablero que no carga daria cero, y
    cero pareceria el estado perfecto."""
    mod = _modulo()

    def explota():
        raise mod.NoSePudoMirar("el tablero no expone SIN_MUTACION")

    _montar(mod, tmp_path, dict(_BASE))
    mod.estado_actual = explota
    ok, msg = mod.exenciones_no_suben()
    assert not ok
    assert "no se pudo mirar" in msg


def test_rojo_si_falta_la_linea_base(tmp_path):
    """Sin linea base no hay con que comparar, y sin comparar no vigila nada."""
    mod = _modulo()
    _montar(mod, tmp_path, dict(_BASE))
    mod.BASELINE = tmp_path / "no_existe.json"
    ok, msg = mod.exenciones_no_suben()
    assert not ok
    assert "linea base" in msg or "falta" in msg


def test_el_tope_de_verdad_no_tiene_holgura():
    """Contra el estado REAL: el tope declarado tiene que ser exactamente el numero de exenciones.

    Si sobra holgura, el trinquete permite crecer hasta llenarla sin decir nada — y esa es
    justamente la forma en que un trinquete deja de serlo.
    """
    mod = _modulo()
    try:
        actual = mod.estado_actual()
    except mod.NoSePudoMirar as e:
        pytest.skip(f"no se pudo leer el tablero: {e}")
    assert mod.TOPE == len(actual), (
        f"tope {mod.TOPE} para {len(actual)} exenciones: la holgura permite empeorar en silencio")
