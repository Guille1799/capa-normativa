"""Un mudo que insiste acaba en ROJO — y un finde sin trabajar no gasta paciencia.

La regla la fijó G el 2026-08-30, y su valor está en el denominador:

    «2 días, pero que esos días se haya trabajado — si no, en un finde que no curre va a saltar»

Mi primera versión contaba **tiempo transcurrido** desde la última medición buena. Con eso, un fin
de semana sin rondas hacía que el lunes, al primer tropiezo, el contador marcara tres días y
saltara la alarma: el vigilante no había fallado dos veces, le habían preguntado una. Estos tests
fijan la versión buena, y el primero de todos es el del finde.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
RONDA = RAIZ / "scripts" / "ronda_de_tableros.py"


@pytest.fixture(scope="module")
def ronda():
    spec = importlib.util.spec_from_file_location("ronda_bajo_prueba", str(RONDA))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_UN_finde_sin_rondas_no_gasta_paciencia(ronda):
    """EL test de esta regla. Sin él, el lunes salta una alarma que nadie ha merecido."""
    h, muertos = ronda.escalar_mudos({}, "tab", ["vigilante"], [], "2026-08-28")
    assert not muertos, "un primer mudo NO puede ser rojo"
    # viernes 28 mudo · sabado y domingo SIN ronda · lunes 31 vuelve a fallar
    h, muertos = ronda.escalar_mudos(h, "tab", ["vigilante"], [], "2026-08-31")
    assert muertos == ["vigilante"], (
        "dos dias CON ronda y mudo en los dos: eso si es un vigilante muerto")
    assert h["tab::vigilante"] == ["2026-08-28", "2026-08-31"], (
        "los dias del finde NO deben estar en la cuenta: " + str(h))


def test_un_mudo_suelto_se_perdona(ronda):
    """La maquina iba ahogada. Eso pasa y no es una averia."""
    _, muertos = ronda.escalar_mudos({}, "tab", ["uno"], [], "2026-08-30")
    assert muertos == []


def test_varias_rondas_del_MISMO_dia_cuentan_como_una(ronda):
    """Correr la ronda a mano tres veces no puede matar a un vigilante en diez minutos."""
    h = {}
    for _ in range(3):
        h, muertos = ronda.escalar_mudos(h, "tab", ["uno"], [], "2026-08-30")
        assert muertos == [], "tres corridas del mismo dia han matado al vigilante"
    assert h["tab::uno"] == ["2026-08-30"]


def test_una_medicion_conseguida_lo_resetea_TODO(ronda):
    h, _ = ronda.escalar_mudos({}, "tab", ["uno"], [], "2026-08-28")
    h, muertos = ronda.escalar_mudos(h, "tab", [], ["uno"], "2026-08-29")
    assert muertos == [] and "tab::uno" not in h, "midio: hay que perdonarle lo anterior"
    h, muertos = ronda.escalar_mudos(h, "tab", ["uno"], [], "2026-08-30")
    assert muertos == [], "tras medir, el contador empieza de cero otra vez"


def test_un_ROJO_tambien_lo_resetea(ronda):
    """Y esto es lo que separa las dos cosas que estaban mezcladas.

    Un ROJO significa que SI consiguio mirar. Si un rojo no reseteara, estariamos volviendo a
    confundir «mide y dice que mal» con «no consigue medir», que es el error que abrio todo esto.
    """
    h, _ = ronda.escalar_mudos({}, "tab", ["uno"], [], "2026-08-28")
    h, muertos = ronda.escalar_mudos(h, "tab", [], ["uno"], "2026-08-29")   # rojo = medido
    assert "tab::uno" not in h
    h, muertos = ronda.escalar_mudos(h, "tab", ["uno"], [], "2026-08-30")
    assert muertos == []


def test_cada_TABLERO_lleva_su_cuenta(ronda):
    """El mismo nombre en dos tableros son dos vigilantes distintos: capa-normativa y cn-ralph
    comparten nombres porque uno es worktree del otro, y sumarlos mataria a los dos a la vez."""
    h, _ = ronda.escalar_mudos({}, "tab-A", ["uno"], [], "2026-08-29")
    h, muertos = ronda.escalar_mudos(h, "tab-B", ["uno"], [], "2026-08-30")
    assert muertos == [], "el mudo de A no puede contarle al de B"


def test_el_tope_es_el_que_decidio_G(ronda):
    assert ronda.DIAS_MUDO_HASTA_ROJO == 2


# ── el enchufe: que la regla llegue de verdad a la ficha del tablero ─────────────────────────

def _ficha(nombre="tab", rojos=None, mudos=None, medidos=None):
    return {"nombre": nombre, "rojos": list(rojos or []), "mudos": list(mudos or []),
            "medidos": list(medidos or []), "verdes": 0}


def test_el_segundo_dia_mudo_ASCIENDE_a_rojo_en_la_ficha(ronda, tmp_path):
    """La prueba del enchufe. Sin esto, `escalar_mudos` seria una funcion que nadie llama."""
    f = tmp_path / "mudos.json"
    fichas = [_ficha(mudos=["vigilante"])]
    ronda.aplicar_mudos(fichas, f, "2026-08-28")
    assert fichas[0]["rojos"] == [], "el primer mudo no puede ensuciar la lista de rojos"

    fichas = [_ficha(mudos=["vigilante"])]
    ronda.aplicar_mudos(fichas, f, "2026-08-31")
    assert fichas[0]["rojos"] == ["vigilante"], "el segundo dia mudo tiene que salir como ROJO"
    assert fichas[0]["muertos"] == ["vigilante"], (
        "y hay que poder DECIR que es el vigilante quien esta muerto, no su promesa")
    assert fichas[0]["mudos"] == [], "ya no es un mudo: ha ascendido"


def test_un_rojo_de_VERDAD_no_se_pierde_al_ascender_un_mudo(ronda, tmp_path):
    f = tmp_path / "mudos.json"
    for dia in ("2026-08-28", "2026-08-29"):
        fichas = [_ficha(rojos=["infraccion-real"], mudos=["vigilante"])]
        ronda.aplicar_mudos(fichas, f, dia)
    assert fichas[0]["rojos"] == ["infraccion-real", "vigilante"]


def test_una_memoria_ILEGIBLE_no_tumba_la_ronda(ronda, tmp_path):
    """Empezar la cuenta de cero es aceptable. Reventar la ronda por esto, no."""
    f = tmp_path / "mudos.json"
    f.write_text("{esto no es json", encoding="utf-8")
    fichas = [_ficha(mudos=["vigilante"])]
    ronda.aplicar_mudos(fichas, f, "2026-08-30")
    assert fichas[0]["rojos"] == []


def test_un_tablero_SIN_mudos_no_toca_nada(ronda, tmp_path):
    """Los 33 comprobadores de hoy: ninguno devuelve la casilla nueva todavia."""
    f = tmp_path / "mudos.json"
    fichas = [_ficha(rojos=["algo"], medidos=["algo", "otro"])]
    ronda.aplicar_mudos(fichas, f, "2026-08-30")
    assert fichas[0]["rojos"] == ["algo"] and "muertos" not in fichas[0]
