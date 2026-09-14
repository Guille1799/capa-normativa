"""MENTIROSOS de `_delega`: seis comprobadores delegados de pega, cada uno roto por un sitio.

## Qué es un mentiroso

Una implementación **completa** de la cosa que se juzga —aquí, un guion de
`scripts/aceptaciones/`, que es de donde cuelgan SIETE comprobadores del tablero— rota por **UNA
sola razón**, con el test exigiendo que caiga **en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

## Qué protege, y por qué esta pieza en concreto

`_delega` nace de juntar SIETE copias del mismo bloque, idénticas salvo el nombre del guion.
Cien líneas repetidas — y cada una habría necesitado por separado el mismo cambio para entender la
tercera casilla. Eso significa que **un fallo aquí sale multiplicado por siete**.

Su trabajo entero es traducir un proceso a un color, y lo caro es que traduzca de más:

  · el guion **NO EXISTE** -> ROJO, y éste sí: no es que no se haya podido mirar, es que falta el
    que tenía que mirar.
  · **se cuelga** -> MUDO. Colgarse no es un veredicto: es no haber podido medir. Como ROJO era
    una falsa alarma con la forma exacta de las que este arnés persigue.
  · **sale 3** -> MUDO, porque el guion mismo dice que no pudo.
  · **sale != 0** -> ROJO.
  · **sale 0** -> VERDE.

Y la distinción ROJO/MUDO no es filosofía: el 2026-08-30 diez comprobadores salían rojos durante la
ronda y verdes al repreguntarles a solas. No mentían sobre su promesa — mentían sobre haber podido
medirla.

⚠️ Un MUDO **también suspende** aquí, y por eso vale como mentiroso: `None` no es aprobar. Lo que
se prueba es que el motivo diga cuál de los dos es, porque un mudo que insiste acaba en rojo y uno
que se confunde con un rojo no se arregla nunca.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

TABLERO = Path(__file__).resolve().parent.parent / "scripts" / "aceptacion.py"

#: Segundos que se le dan a un guion antes de darlo por colgado. Corto a propósito: el mentiroso
#: `se_cuelga` tiene que poder probarse sin que la suite tarde quince minutos.
TIMEOUT = 5


def _cargar():
    spec = importlib.util.spec_from_file_location("tablero_para_delegacion", str(TABLERO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _cargar()

#: Un árbol de pega con su `scripts/aceptaciones/`. El tablero real no se toca: apuntar `RAIZ` a
#: otro sitio es la costura que permite probar esto sin romper nada de la máquina.
_RAIZ = Path(tempfile.mkdtemp(prefix="mentirosos-delega-"))
_CARPETA = _RAIZ / "scripts" / "aceptaciones"
_CARPETA.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="module", autouse=True)
def _limpiar():
    yield
    shutil.rmtree(_RAIZ, ignore_errors=True)


def _fabrica(nombre, *, dice=None, sale=0, duerme=0, escribe=True):
    """Un comprobador delegado de pega. Por defecto el HONESTO; cada argumento mete UNA mentira.

    Honesto significa: existe, termina deprisa, imprime su veredicto y sale 0.
    """
    if not escribe:
        return nombre + ".py"          # el guion que nunca se escribió
    cuerpo = ["import sys, time"]
    if duerme:
        cuerpo.append("time.sleep(" + str(duerme) + ")")
    if dice is not None:
        cuerpo.append("print(" + repr(dice) + ")")
    cuerpo.append("sys.exit(" + str(sale) + ")")
    (_CARPETA / (nombre + ".py")).write_text("\n".join(cuerpo) + "\n", encoding="utf-8")
    return nombre + ".py"


HONESTO = _fabrica("honesto", dice="VERDE: los cuatro repos publicos tienen su guarda")


def _sonda(guion):
    """`_delega` de verdad, apuntado al árbol de pega. `(aprueba, por qué no)`."""
    original = T.RAIZ
    T.RAIZ = _RAIZ
    try:
        return T._delega(guion, "verde por defecto", timeout=TIMEOUT, corte=200)
    finally:
        T.RAIZ = original


MENTIROSOS = {
    # Falta el guion. No es «no se ha podido mirar»: es que falta el que tenía que mirar, y un mudo
    # lo perdonaría dos días enteros.
    "el_guion_no_existe": (_fabrica("ausente", escribe=False), "no existe"),
    # Mide, encuentra el problema y lo cuenta. Es el rojo BUENO: el único accionable.
    "falla_y_lo_explica": (_fabrica("explica", dice="ROJO: 3 repos publicos sin guarda: uno, dos, tres",
                                    sale=1),
                           "3 repos publicos sin guarda"),
    # Sale 1 y no imprime nada. El color es correcto y el rojo es inútil: nadie sabe qué arreglar.
    "falla_y_se_calla": (_fabrica("callado", sale=1), "falla sin mensaje"),
    # No pudo medir Y LO DICE. Ésta es la casilla que faltaba hasta el 2026-08-30, y su ausencia
    # obligaba a mentir: «he mirado y está mal» y «no he podido mirar» iban al mismo sitio.
    "no_pudo_medir_y_lo_dice": (_fabrica("mudo", dice="MUDO: el Programador no contesto", sale=3),
                                "el Programador no contesto"),
    # Sale 3 sin decir por qué. Sigue siendo mudo, y el motivo por defecto tiene que decirlo.
    "no_pudo_medir_y_se_calla": (_fabrica("mudo_callado", sale=3), "no se pudo medir"),
    # Se cuelga. Traducirlo a ROJO acusa al guion de un fallo que puede ser de la máquina — y esta
    # máquina, bajo carga, falla al lanzar procesos.
    "se_cuelga": (_fabrica("colgado", duerme=TIMEOUT * 6), "se cuelga"),
}


def test_el_delegado_honesto_APRUEBA():
    """Sin esto los mentirosos no prueban nada: una sonda que suspende siempre los caza todos."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    guion, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(guion)
    assert not ok, nombre + " aprobo, y su guion no habia dado ningun verde"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_un_MUDO_no_se_confunde_con_un_ROJO():
    """La distinción que costó diez falsos rojos en una ronda, comprobada en el tipo y no en el texto.

    `False` y `None` se parecen mucho en un `if`, y ahí está el peligro: quien lea el veredicto con
    un `not` los trata igual. El tablero los pinta distinto y la ronda los escala distinto — un
    mudo que insiste sube a rojo; un rojo no baja a mudo nunca.
    """
    rojo, _ = _sonda(MENTIROSOS["falla_y_se_calla"][0])
    mudo, _ = _sonda(MENTIROSOS["no_pudo_medir_y_se_calla"][0])
    assert rojo is False, "un fallo medido tiene que ser ROJO, no mudo"
    assert mudo is None, "no haber podido medir NO es haber medido mal"


def test_el_color_NO_se_dice_dos_veces():
    """El tablero ya pinta el emoji: un motivo que empieza por «ROJO:» lo dice dos veces.

    Es cosmético hasta que no lo es — las líneas quedaban como «🔴 nombre ROJO: ...», y un tablero
    que se lee mal es un tablero que no se lee.
    """
    _, motivo = _sonda(MENTIROSOS["falla_y_lo_explica"][0])
    assert not motivo.startswith("ROJO"), motivo
    _, mudo = _sonda(MENTIROSOS["no_pudo_medir_y_lo_dice"][0])
    assert not mudo.startswith("MUDO"), mudo
