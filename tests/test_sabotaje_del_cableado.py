"""El saboteador cambia de color, restaura siempre, y se niega a juzgar con un juez roto.

Este comprobador es el único que **escribe en `scripts/aceptacion.py`**, así que sus tests miran
dos cosas distintas: que su veredicto sea correcto, y que el fichero vuelva intacto pase lo que
pase. Lo segundo importa más — si se quedara a medias, el repo tendría todos los guardianes
incapaces de decir que no, que es el peor estado posible.

El oráculo (correr la suite entera) se falsifica en todos los tests menos en el último: correrla
de verdad son ~65 s por pieza, y una coartada que tarda diez minutos no la ejecuta nadie.
"""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "scripts" / "aceptaciones" / "sabotaje_del_cableado.py"
TABLERO = RAIZ / "scripts" / "aceptacion.py"


@pytest.fixture()
def sab(tmp_path):
    """El módulo, con su memoria APUNTADA A UN TEMPORAL.

    Sin esta redirección los tests eran inútiles y además dañinos: la memoria de verdad
    cortocircuitaba el módulo antes de llegar a nada de lo falsificado, y al terminar la
    sobreescribían con veredictos de mentira. O sea que envenenaban al comprobador real.
    """
    if not GUION.is_file():
        pytest.skip("no existe sabotaje_del_cableado.py")
    spec = importlib.util.spec_from_file_location("sabotaje_bajo_prueba", str(GUION))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.CACHE = tmp_path / "sabotaje_de_mentira.json"
    return mod


@pytest.fixture()
def tablero_intacto():
    """Guarda la huella del tablero y exige que vuelva idéntico. La red bajo la red."""
    antes = TABLERO.read_bytes()
    yield hashlib.sha256(antes).hexdigest()
    if hashlib.sha256(TABLERO.read_bytes()).hexdigest() != hashlib.sha256(antes).hexdigest():
        TABLERO.write_bytes(antes)
        pytest.fail("el test dejo scripts/aceptacion.py modificado; se ha restaurado a mano")


def _limpio(mod, monkeypatch):
    """Que git diga que el arbol esta limpio, sin preguntarle."""
    class R:
        returncode = 0
        stdout = ""
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: R())


def _suite(mod, monkeypatch, referencia: bool, luego):
    """Falsifica el oraculo distinguiendo la corrida DE REFERENCIA de las de mutacion.

    ⚠️ El mismo valor significa cosas opuestas en las dos: en la de referencia, «la suite protesta»
    quiere decir que el JUEZ esta roto; en las de mutacion, que la PIEZA esta vigilada. La primera
    version de estos tests devolvia una constante para todas y por eso fallaron tres — el fallo
    era del test, y encontrarlo es justo para lo que estan.
    """
    estado = {"primera": True}

    def falso():
        if estado["primera"]:
            estado["primera"] = False
            return referencia
        return luego() if callable(luego) else luego

    monkeypatch.setattr(mod, "_corre_la_suite", falso)


# ── el veredicto ─────────────────────────────────────────────────────────────────────────────

def test_ROJO_si_una_pieza_puede_quedarse_sin_poder_decir_que_no(sab, monkeypatch,
                                                                 tablero_intacto):
    """El caso que lo justifica todo: la suite no protesta ante la pieza saboteada."""
    _limpio(sab, monkeypatch)
    monkeypatch.setattr(sab, "piezas_de_cableado", lambda _f: ["_delega"])
    _suite(sab, monkeypatch, referencia=False, luego=False)   # juez sano, y nadie protesta

    ok, msg = sab.sabotaje_del_cableado()
    assert ok is False, f"una pieza ciega ha salido VERDE: {msg}"
    assert "_delega" in msg, f"no dice CUAL esta ciega, asi que no hay nada que arreglar: {msg}"
    assert "decorativo" in msg


def test_VERDE_si_la_suite_protesta_por_cada_pieza(sab, monkeypatch, tablero_intacto):
    """La mitad que se olvida: si no puede cerrarse, su rojo no significa nada."""
    _limpio(sab, monkeypatch)
    monkeypatch.setattr(sab, "piezas_de_cableado", lambda _f: ["_delega", "_fabrica_bug"])
    llamadas = []
    _suite(sab, monkeypatch, referencia=False, luego=lambda: llamadas.append(1) or True)

    ok, msg = sab.sabotaje_del_cableado()
    assert ok is True, msg
    assert len(llamadas) == 2, (
        "esperaba una corrida por cada una de las 2 piezas, y hubo " + str(len(llamadas)))


def test_MUDO_si_la_SUITE_YA_FALLA_antes_de_mutar(sab, monkeypatch, tablero_intacto):
    """El agujero que casi se cuela, y era de los grandes.

    Si la suite ya esta roja por su cuenta, protesta igual ante CUALQUIER sabotaje — y entonces
    todas las piezas parecerian vigiladas y esto saldria VERDE sin haber medido nada. Es la misma
    mentira que mato a la maquina anterior con su `0/0`, sólo que con otro disfraz.
    """
    _limpio(sab, monkeypatch)
    monkeypatch.setattr(sab, "piezas_de_cableado", lambda _f: ["_delega"])
    _suite(sab, monkeypatch, referencia=True, luego=True)    # protesta ya SIN mutar nada

    ok, msg = sab.sabotaje_del_cableado()
    assert ok is None, f"con el juez ya roto NO se puede dar un veredicto: {msg}"
    assert "ANTES de mutar" in msg


def test_MUDO_si_el_arbol_tiene_cambios_sin_guardar(sab, monkeypatch, tablero_intacto):
    """Mutar sobre trabajo sin commitear arriesga perderlo al restaurar. Y no poder medir
    NUNCA es «todas las piezas estan vigiladas»."""
    class R:
        returncode = 0
        stdout = " M scripts/aceptacion.py\n"
    monkeypatch.setattr(sab.subprocess, "run", lambda *a, **k: R())

    ok, msg = sab.sabotaje_del_cableado()
    assert ok is None and "sin guardar" in msg


def test_ROJO_si_no_se_detecta_ninguna_pieza(sab, monkeypatch, tablero_intacto):
    """Cero piezas de cableado es un resultado imposible, no una casa limpia."""
    _limpio(sab, monkeypatch)
    monkeypatch.setattr(sab, "piezas_de_cableado", lambda _f: [])
    ok, msg = sab.sabotaje_del_cableado()
    assert ok is False and "cero piezas" in msg


# ── la red bajo la red: el tablero vuelve intacto ────────────────────────────────────────────

def test_el_tablero_vuelve_INTACTO_aunque_la_suite_reviente(sab, monkeypatch, tablero_intacto):
    """Lo que de verdad no puede fallar. Si se quedara a medias, el repo tendria TODOS los
    guardianes incapaces de decir que no — el peor estado posible, y ademas silencioso."""
    _limpio(sab, monkeypatch)
    monkeypatch.setattr(sab, "piezas_de_cableado", lambda _f: ["_delega"])

    def revienta():
        raise OSError("el proceso no arranca")

    # juez sano en la de referencia, y la mutacion revienta a mitad
    _suite(sab, monkeypatch, referencia=False, luego=revienta)
    ok, msg = sab.sabotaje_del_cableado()
    assert ok is None, msg
    # el fixture `tablero_intacto` comprueba la huella al salir; esto lo dice tambien aqui
    assert "no se pudo lanzar" in msg or "no se ha medido" in msg


def test_voltear_niega_EXACTAMENTE_la_capacidad_de_decir_que_no(sab):
    """La mutacion tiene que ser esa y no otra: `return False` -> `return True`, y nada mas."""
    fuente = ("def f():\n"
              "    if x:\n"
              "        return False, 'mal'\n"
              "    return True, 'bien'\n")
    mutada, cuantos = sab.voltear(fuente, "f")
    assert cuantos == 1
    assert "return True, 'mal'" in mutada
    assert mutada.count("return True") == 2 and "return False" not in mutada


def test_las_piezas_se_DERIVAN_del_tablero_de_verdad(sab):
    """Una lista escrita a mano envejeceria igual que el problema: el dia que naciera una pieza
    nueva, nadie la anadiria y su punto ciego no saldria en ningun sitio."""
    piezas = sab.piezas_de_cableado(TABLERO.read_text(encoding="utf-8"))
    assert "_delega" in piezas, "falta la pieza de la que cuelgan mas comprobadores"
    assert len(piezas) >= 5, f"solo {len(piezas)} piezas: la derivacion se ha quedado corta"
    # los envoltorios de una linea NO entran: su cable es `_delega`, y mutarlos gastaria una
    # corrida entera de la suite para no medir nada nuevo
    assert "ci_de_los_publicos_en_verde" not in piezas


# ── la memoria: barata, y honesta sobre que es memoria ───────────────────────────────────────

def test_la_SEGUNDA_vez_no_vuelve_a_medir_si_nada_ha_cambiado(sab, monkeypatch, tablero_intacto):
    """Diez minutos al dia matan a un guardian: se desactiva «un momento» y no vuelve.

    La memoria es segura porque su llave es exactamente lo que puede cambiar la respuesta —el
    tablero y la suite—. Si ninguno se ha tocado, volver a medir daria lo mismo CON CERTEZA.
    """
    _limpio(sab, monkeypatch)
    monkeypatch.setattr(sab, "piezas_de_cableado", lambda _f: ["_delega"])
    corridas = []
    _suite(sab, monkeypatch, referencia=False, luego=lambda: corridas.append(1) or True)

    ok1, _ = sab.sabotaje_del_cableado()
    assert ok1 is True and len(corridas) == 1

    ok2, msg2 = sab.sabotaje_del_cableado()
    assert ok2 is True
    assert len(corridas) == 1, "ha vuelto a medir aunque no habia cambiado nada"
    assert "medido el" in msg2, (
        "un verde que viene de la memoria TIENE que distinguirse de uno medido hoy: " + msg2)


def test_un_MUDO_no_se_recuerda(sab, monkeypatch, tablero_intacto):
    """No es una medicion: es no haber podido medir. Recordarlo seria dar por bueno un hueco."""
    class R:
        returncode = 0
        stdout = " M scripts/aceptacion.py\n"
    monkeypatch.setattr(sab.subprocess, "run", lambda *a, **k: R())

    ok, _ = sab.sabotaje_del_cableado()
    assert ok is None
    assert not sab.CACHE.exists(), "se ha guardado un MUDO como si fuera un veredicto"


def test_si_el_TABLERO_cambia_la_memoria_deja_de_valer(sab, monkeypatch, tablero_intacto, tmp_path):
    """La llave tiene que morder. Si no, la memoria se convierte en un verde eterno."""
    _limpio(sab, monkeypatch)
    monkeypatch.setattr(sab, "piezas_de_cableado", lambda _f: ["_delega"])
    corridas = []
    _suite(sab, monkeypatch, referencia=False, luego=lambda: corridas.append(1) or True)
    sab.sabotaje_del_cableado()
    assert len(corridas) == 1

    monkeypatch.setattr(sab, "_llave", lambda: "otra-huella-porque-el-tablero-cambio")
    _suite(sab, monkeypatch, referencia=False, luego=lambda: corridas.append(1) or True)
    sab.sabotaje_del_cableado()
    assert len(corridas) == 2, "la memoria ha seguido valiendo con el tablero cambiado"
