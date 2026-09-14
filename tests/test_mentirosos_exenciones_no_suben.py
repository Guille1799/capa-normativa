"""MENTIROSOS de `exenciones-no-suben`: seis regímenes de exenciones, cada uno falso por un sitio.

## Qué es un mentiroso

Una implementación **completa** de la cosa que el comprobador juzga —aquí, el par (línea base de
exenciones, estado de hoy)— rota por **UNA sola razón**, y el test exige que caiga **en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

## Qué protege

`SIN_MUTACION` es la lista de comprobadores a los que se les perdona la prueba por mutación. Cada
entrada es un comprobador **que nadie ha visto ponerse rojo**, así que la lista es deuda: si puede
crecer en silencio, el trinquete es decoración y el tablero entero se puede vaciar de significado
una entrada cada vez.

`Trinquete.revisar()` hace seis preguntas que se parecen sólo de lejos, y cada una nombra una
manera distinta de que la deuda crezca sin que nadie lo decida:

  · **TRI001** una exención NUEVA · **TRI002** una que cambió de coartada · **TRI003** una del
  baseline que ya no existe —que no es basura, es un PERMISO DE REENTRADA— · **TRI004** el tope
  superado · **TRI005** una sin `reason`, o sea gratis · **TRI007** una con la clase fuera del
  vocabulario, o sea sin clasificar.

Cada una pide un arreglo distinto, y todas se ven igual desde fuera: «el trinquete dice rojo».
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from capa_normativa.vigilante.trinquete import Trinquete  # noqa: E402

#: El vocabulario y la forma de una entrada se copian de `scripts/aceptaciones/exenciones_no_suben.py`,
#: que es quien monta el trinquete de verdad en este repo.
VOCABULARIO = ("test-nombrado", "autoprueba")


def _entrada(tests="tests/test_canario.py", razon="lo ve cambiar de color", clase="test-nombrado"):
    return {"value": tests, "reason": razon, "clase": clase}


#: Tres exenciones declaradas, cada una con su coartada. El tope vale EXACTAMENTE tres: con un tope
#: más alto saltaría TRI006 («el tope está flojo») y el honesto no aprobaría — o sea que el tope
#: flojo también es una mentira, sólo que informativa.
BASE = {
    "guardia-de-commit": _entrada("tests/test_guardia_de_commit.py"),
    "canario-de-los-hooks": _entrada("tests/test_canario_de_los_hooks.py"),
    "sabotaje-del-cableado": _entrada(None, "se autoprueba con --sin-cache", "autoprueba"),
}
TOPE = len(BASE)


def _fabrica(*, base=None, actual=None):
    """Un régimen de exenciones de pega. Por defecto el HONESTO: el estado de hoy es el declarado."""
    b = dict(BASE if base is None else base)
    a = dict(b if actual is None else actual)
    return b, a


HONESTO = _fabrica()


def _sonda(caso):
    """El trinquete de verdad. `(aprueba, por qué no)` — como lo lee `exenciones_no_suben()`."""
    base, actual = caso
    tri = Trinquete(base, tope=TOPE, vocabulario=VOCABULARIO, que_migrar_a="ARTEFACTOS")
    hallazgos = tri.revisar(actual)
    return not hallazgos, " · ".join(str(h.codigo) + " " + h.mensaje for h in hallazgos)


def _con(**cambios):
    """El estado de hoy, igual que el declarado salvo lo que se diga."""
    a = {k: dict(v) for k, v in BASE.items()}
    a.update(cambios)
    return a


def _base_con(**cambios):
    b = {k: dict(v) for k, v in BASE.items()}
    b.update(cambios)
    return b


MENTIROSOS = {
    # Un comprobador nuevo que nace EXENTO. Es la forma normal de que esta lista crezca: nadie
    # decide nada, simplemente aparece una línea más.
    "una_exencion_nueva": ((BASE, _con(**{"escaparate-con-guarda": _entrada()})),
                           "entrada(s) nueva(s) sin declarar"),
    # La exención sigue ahí y su coartada ha cambiado: ahora dice que la prueba otro test. Puede
    # ser legítimo, pero es una DECISIÓN, y sin pasar por el diff nadie puede discutirla.
    "coartada_cambiada": ((BASE, _con(**{"guardia-de-commit": _entrada("tests/test_otro.py")})),
                          "valor(es) cambiado(s) sin procedencia"),
    # Una entrada del baseline que ya no existe en el tablero. No es residuo inofensivo: mientras
    # siga ahí, volver a escribir esa exención a mano no dispara absolutamente nada.
    "permiso_de_reentrada": ((BASE, {k: v for k, v in _con().items() if k != "canario-de-los-hooks"}),
                             "ya no existen"),
    # El tope por debajo de lo que el baseline ya tiene. El trinquete sólo gira en un sentido, y
    # subir el tope tiene que costar un commit y un porqué.
    "el_tope_se_queda_corto": ((_base_con(**{"extra": _entrada()}), _con(**{"extra": _entrada()})),
                               "y el tope es"),
    # Una exención sin `reason`. Salir de la lista de pendientes es una decisión; sin motivo
    # escrito es gratis, y gratis significa que nadie podrá discutirlo después.
    "exencion_gratis": ((_base_con(**{"guardia-de-commit": _entrada(razon="  ")}), _con()),
                        "sin `reason`"),
    # Una exención con la clase fuera del vocabulario: nadie ha decidido QUÉ ES. Clasificar antes
    # de entrar obliga a decidirlo entonces, no después — que es cuando ya no se hace.
    "exencion_sin_clasificar": ((_base_con(**{"guardia-de-commit": _entrada(clase="varios")}), _con()),
                                "fuera del vocabulario"),
}


def test_el_regimen_honesto_APRUEBA():
    """Si el honesto no aprobara, los seis mentirosos caerían gratis y no probarían nada."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    caso, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(caso)
    assert not ok, nombre + " aprobo, y su lista de exenciones habia crecido en silencio"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_un_tope_FLOJO_tambien_se_denuncia():
    """La séptima, y va aparte porque no es una mentira sobre las exenciones: es sobre el guardián.

    Un tope por encima de lo que hay no rompe nada hoy — y deja hueco para meter deuda sin que
    nada se queje. Eso convierte el trinquete en decoración, que es peor que no tenerlo porque
    parece que vigila.
    """
    tri = Trinquete(BASE, tope=TOPE + 5, vocabulario=VOCABULARIO)
    hallazgos = tri.revisar(dict(BASE))
    assert hallazgos, "un tope flojo salio limpio: el trinquete no se vigila a si mismo"
    assert "el tope esta flojo" in " · ".join(h.mensaje for h in hallazgos).replace("á", "a")
