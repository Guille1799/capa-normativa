"""Tests del trinquete, con la disciplina F14: cada comprobación se rompe a propósito, con
`assert` de que la mutación ENTRÓ, y comprobando comportamiento en vez de presencia de cadenas.

Los casos rojos vienen del historial REAL del trinquete de origen (277 → 206 en 14 pasos),
no de la imaginación: la entrada obsoleta como permiso de reentrada, el valor que cambia sin
que el nombre cambie, y la tupla que JSON convierte en lista.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from capa_normativa.vigilante.trinquete import Entrada, Trinquete

VIGILANTE_DIR = Path(__file__).resolve().parent.parent / "src" / "capa_normativa" / "vigilante"


def _baseline(tmp_path: Path, entradas: dict) -> Path:
    p = tmp_path / "baseline.json"
    p.write_text(json.dumps(entradas, ensure_ascii=False), encoding="utf-8")
    return p


def _codigos(hallazgos) -> set[str]:
    return {h.codigo for h in hallazgos}


BASE_SANA = {
    "_UMBRAL": {"value": 30, "reason": "hecho del mundo: distancia de maraton", "clase": "mundo"},
    "_FACTOR": {"value": 1.55, "reason": "convencion tecnica del pipeline", "clase": "tecnica"},
}


def test_un_baseline_al_ras_y_coherente_no_da_hallazgos(tmp_path: Path):
    t = Trinquete(_baseline(tmp_path, BASE_SANA), tope=2, vocabulario={"mundo", "tecnica"})
    assert t.revisar({k: v for k, v in BASE_SANA.items()}) == []


# ── TRI001 · entradas nuevas ──

def test_TRI001_SALTA_con_una_constante_nueva(tmp_path: Path):
    t = Trinquete(_baseline(tmp_path, BASE_SANA), tope=2)
    actual = dict(BASE_SANA) | {"_NUEVO": {"value": 7, "reason": ""}}

    assert "_NUEVO" not in t.baseline, "la mutación no se aplicó: ya estaba en el baseline"
    assert "_NUEVO" in actual, "la mutación no se aplicó: no está en el estado actual"

    assert "TRI001" in _codigos(t.revisar(actual))


# ── TRI002 · valores cambiados (un baseline de solo nombres no lo vería) ──

def test_TRI002_SALTA_cuando_cambia_un_VALOR_sin_cambiar_el_nombre(tmp_path: Path):
    t = Trinquete(_baseline(tmp_path, BASE_SANA), tope=2)
    actual = {"_UMBRAL": {"value": 41, "reason": "x"}, "_FACTOR": {"value": 1.55, "reason": "x"}}

    # (b) la mutación entró: mismo conjunto de claves, valor distinto.
    assert set(actual) == set(t.baseline), "el caso no es válido: cambiaron las claves"
    assert actual["_UMBRAL"]["value"] != t.baseline["_UMBRAL"].valor, "la mutación no se aplicó"

    codigos = _codigos(t.revisar(actual))
    assert "TRI002" in codigos
    assert "TRI001" not in codigos, "no hay entradas nuevas: solo cambió un valor"


def test_una_lista_y_una_tupla_con_el_mismo_contenido_NO_son_un_cambio(tmp_path: Path):
    """CASO ROJO del original: JSON no distingue tupla de lista, así que un baseline releído
    del disco reportaría cambiadas todas las secuencias."""
    p = _baseline(tmp_path, {"_BANDAS": {"value": [18, 40, 60], "reason": "clasificador"}})
    t = Trinquete(p, tope=1)

    # (b) la mutación entró: en disco es lista, en memoria vamos a pasar tupla.
    assert isinstance(json.loads(p.read_text(encoding="utf-8"))["_BANDAS"]["value"], list)

    hallazgos = t.revisar({"_BANDAS": Entrada(valor=(18, 40, 60), razon="clasificador")})
    assert "TRI002" not in _codigos(hallazgos), "falso positivo: lista y tupla son el mismo valor"


# ── TRI003 · la entrada obsoleta como permiso de reentrada ──

def test_TRI003_SALTA_con_una_entrada_que_ya_no_existe(tmp_path: Path):
    """La comprobación no obvia, y la que se descubrió tarde: sin ella, algo migrado seguía
    en el baseline para siempre y volver a escribirlo a mano no disparaba nada."""
    t = Trinquete(_baseline(tmp_path, BASE_SANA), tope=2)
    actual = {"_UMBRAL": BASE_SANA["_UMBRAL"]}  # _FACTOR migrado y ya no está en el código

    assert "_FACTOR" in t.baseline, "el caso no es válido: no estaba en el baseline"
    assert "_FACTOR" not in actual, "la mutación no se aplicó: sigue en el estado actual"

    assert "TRI003" in _codigos(t.revisar(actual))


def test_el_permiso_de_reentrada_se_cierra_al_borrar_la_entrada(tmp_path: Path):
    """Comportamiento, no cadena: tras borrar la entrada obsoleta, re-escribir a mano esa
    constante SÍ dispara TRI001. Antes de borrarla, no dispararía nada."""
    t_con = Trinquete(_baseline(tmp_path, BASE_SANA), tope=2)
    reentrada = dict(BASE_SANA)  # alguien vuelve a escribir _FACTOR a mano
    assert "TRI001" not in _codigos(t_con.revisar(reentrada)), (
        "con la entrada obsoleta dentro, la reentrada pasa desapercibida — eso es el fallo")

    sin_obsoleta = {"_UMBRAL": BASE_SANA["_UMBRAL"]}
    t_sin = Trinquete(_baseline(tmp_path / "b2", {}) if False else
                      _baseline(tmp_path, sin_obsoleta), tope=1)
    assert "TRI001" in _codigos(t_sin.revisar(reentrada)), (
        "borrada la entrada obsoleta, la reentrada YA dispara")


# ── TRI004 / TRI006 · el tope ──

def test_TRI004_SALTA_cuando_el_baseline_supera_el_tope(tmp_path: Path):
    grande = dict(BASE_SANA) | {"_TERCERO": {"value": 1, "reason": "x", "clase": "tecnica"}}
    t = Trinquete(_baseline(tmp_path, grande), tope=2)
    assert t.cuenta() == 3 > t.tope, "la mutación no se aplicó: el baseline no supera el tope"
    assert "TRI004" in _codigos(t.revisar(grande))


def test_TRI006_avisa_de_que_el_tope_esta_FLOJO(tmp_path: Path):
    """«Si baja, BAJA EL TOPE. Dejarlo alto convierte el trinquete en decoración.»"""
    t = Trinquete(_baseline(tmp_path, BASE_SANA), tope=99)
    hallazgos = t.revisar(BASE_SANA)
    assert "TRI006" in _codigos(hallazgos)
    assert "TRI004" not in _codigos(hallazgos), "no ha crecido: solo el tope está flojo"


def test_el_tope_al_ras_no_avisa_de_nada(tmp_path: Path):
    t = Trinquete(_baseline(tmp_path, BASE_SANA), tope=2)
    assert _codigos(t.revisar(BASE_SANA)) & {"TRI004", "TRI006"} == set()


def test_TRI004_obliga_a_declarar_cual_de_las_DOS_cosas_paso(tmp_path: Path):
    """El caso 277→279 del historial real: el contador subió porque el extractor dejó de
    estar ciego, y 279 era el primer número que no mentía. La intención no es computable
    (ley 1), así que lo único que cabe es que el mensaje OBLIGUE a declararla."""
    grande = dict(BASE_SANA) | {"_X": {"value": 1, "reason": "x"}}
    t = Trinquete(_baseline(tmp_path, grande), tope=2)
    tri004 = next(h for h in t.revisar(grande) if h.codigo == "TRI004")
    assert "CRECIDO" in tri004.arreglo and "CIEGO" in tri004.arreglo, (
        "el mensaje debe forzar la distinción: es lo único que el mecanismo puede hacer aquí")


# ── TRI005 / TRI007 · declaración ──

def test_TRI005_SALTA_con_una_entrada_sin_razon(tmp_path: Path):
    sin = {"_UMBRAL": {"value": 30, "reason": "", "clase": "mundo"}}
    t = Trinquete(_baseline(tmp_path, sin), tope=1)
    assert not t.baseline["_UMBRAL"].razon, "la mutación no se aplicó: tiene razón"
    assert "TRI005" in _codigos(t.revisar(sin))


def test_TRI007_SALTA_con_una_clase_fuera_del_vocabulario(tmp_path: Path):
    mala = {"_U": {"value": 1, "reason": "x", "clase": "inventada"}}
    t = Trinquete(_baseline(tmp_path, mala), tope=1, vocabulario={"mundo", "tecnica"})
    assert t.baseline["_U"].clase not in t.vocabulario, "la mutación no se aplicó"
    assert "TRI007" in _codigos(t.revisar(mala))


def test_sin_vocabulario_no_se_exige_clase(tmp_path: Path):
    """El vocabulario es del inquilino: un proyecto sin clases no debe pagar por ellas."""
    sin_clase = {"_U": {"value": 1, "reason": "x"}}
    t = Trinquete(_baseline(tmp_path, sin_clase), tope=1)
    assert "TRI007" not in _codigos(t.revisar(sin_clase))


# ── contrato y frontera ──

def test_revisar_ENUMERA_en_vez_de_parar_en_el_primero(tmp_path: Path):
    """El registro es fail-fast a propósito; el vigilante tiene que dar la lista entera."""
    t = Trinquete(_baseline(tmp_path, {"_VIEJO": {"value": 1, "reason": ""}}), tope=0)
    codigos = _codigos(t.revisar({"_NUEVO": {"value": 2}}))
    assert len(codigos) >= 4, f"solo enumeró {codigos}"
    assert {"TRI001", "TRI003", "TRI004", "TRI005"} <= codigos


def test_todo_hallazgo_del_trinquete_dice_que_hacer(tmp_path: Path):
    t = Trinquete(_baseline(tmp_path, {"_VIEJO": {"value": 1, "reason": ""}}), tope=0,
                  vocabulario={"mundo"})
    for h in t.revisar({"_NUEVO": {"value": 2}}):
        assert h.detector == "trinquete"
        assert len(h.arreglo) > 30, f"{h.codigo}: el arreglo es demasiado vago"


def test_el_baseline_puede_venir_en_memoria(tmp_path: Path):
    t = Trinquete({"_U": Entrada(valor=1, razon="x")}, tope=1)
    assert t.cuenta() == 1
    assert t.revisar({"_U": Entrada(valor=1, razon="x")}) == []


def test_el_trinquete_no_importa_el_registro():
    """La frontera de los dos módulos, mecanizada también aquí."""
    arbol = ast.parse((VIGILANTE_DIR / "trinquete.py").read_text(encoding="utf-8-sig"))
    for n in ast.walk(arbol):
        nombres = []
        if isinstance(n, ast.Import):
            nombres = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module:
            nombres = [n.module]
        for nombre in nombres:
            assert "registry" not in nombre, f"trinquete importa {nombre!r}"


def test_un_baseline_que_no_es_json_valido_revienta_claro(tmp_path: Path):
    p = tmp_path / "roto.json"
    p.write_text("{esto no es json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        Trinquete(p, tope=1)
