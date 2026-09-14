"""MENTIROSOS del censo de guardianes: seis censos de pega, cada uno incompleto por un sitio.

## Qué es un mentiroso

Una implementación **completa** de la cosa que el comprobador juzga —aquí, el censo entero: quién
está vivo y qué ficha tiene cada uno— rota por **UNA sola razón**, con el test exigiendo que caiga
**en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

## Qué protege

`censo_de_guardianes.py` cierra la aceptación de `inv-registro-md-session-start-sh`, y su trabajo
no es contar guardianes: es que **ninguno pueda aparecer sin que alguien escriba qué se rompe si
muere**. Enumera de cuatro fuentes vivas —hooks de usuario, hooks de cada repo, tareas del
Programador y los tableros de la ronda— así que instalar una tarea nueva lo pone rojo solo.

Las seis ramas piden arreglos distintos, y las dos primeras son las que hacen que esto valga algo:

  · una **fuente que no contesta** NO es una fuente sin guardianes · **cero guardianes** no es una
  máquina limpia, es no haber podido mirar · un guardián **sin ficha** · una ficha **sin `Tipo`** ·
  una **sin `Si muere`** · y una cuyo `Si muere` es tan corto que no dice ninguna consecuencia.

La última es la que impide aprobar en vacío: sin el umbral, una cabecera sola cumpliría la letra
del contrato sin decir nada.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parent.parent / "scripts" / "aceptaciones" / "censo_de_guardianes.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("censo_para_mentirosos", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = _cargar()

#: El umbral sale del MÓDULO, no se escribe aquí: escrito, este fichero se pondría rojo el día que
#: alguien lo suba, por un motivo que no tiene nada que ver con lo que prueba.
MINIMO = C._MINIMO_SI_MUERE

_CONSECUENCIA = ("si muere, nadie vuelve a comprobar los hooks y un guardian roto pasa "
                 "desapercibido durante semanas")
assert len(_CONSECUENCIA) >= MINIMO, "la ficha honesta tiene que cumplir el umbral de verdad"


def _ficha(tipo="hook de UserPromptSubmit", si_muere=_CONSECUENCIA):
    partes = []
    if tipo is not None:
        partes.append("**Tipo:** " + tipo)
    if si_muere is not None:
        partes.append("**Si muere:** " + si_muere)
    return "\n\n".join(partes) + "\n"


#: Dos guardianes vivos, los dos descritos. Es el censo HONESTO.
VIVOS = ["prompt_router.py", "pre-commit:capa-normativa"]


def _fabrica(*, vivos=None, rotas=(), fichas=None):
    """Un censo de pega. Por defecto el HONESTO; cada argumento mete UNA mentira."""
    v = list(VIVOS if vivos is None else vivos)
    return {"vivos": v, "rotas": list(rotas),
            "fichas": {g: _ficha() for g in v} if fichas is None else fichas}


HONESTO = _fabrica()


def _sonda(censo):
    """El comprobador de verdad, con un censo inyectado. `(aprueba, por qué no)`.

    Se le cambian sus dos puertas de entrada —`guardianes()` y `_fichas()`— y se restauran en
    `finally`: un test que se deja los parches puestos contamina todo lo que corra después, y el
    daño aparecería lejos de aquí.
    """
    orig_g, orig_f = C.guardianes, C._fichas
    C.guardianes = lambda: (censo["vivos"], censo["rotas"])
    C._fichas = lambda: censo["fichas"]
    try:
        return C.censo_de_guardianes()
    finally:
        C.guardianes, C._fichas = orig_g, orig_f


MENTIROSOS = {
    # El Programador contestó «A general error occurred» y el censo salió con los que pudo leer.
    # Una fuente que no contesta no es una fuente sin guardianes: es no haber mirado ahí.
    "una_fuente_no_contesta": (_fabrica(rotas=["tareas programadas: Get-ScheduledTask fallo"]),
                               "NO es una fuente sin guardianes"),
    # Cero guardianes en esta máquina es imposible. Un censo vacío que sale verde es la forma más
    # barata de aprobar en vacío, y su silencio se lee como buenas noticias.
    "censo_vacio": (_fabrica(vivos=[], fichas={}), "eso es no haber podido mirar"),
    # Un guardián vivo del que nadie ha escrito nada. Es el caso normal: se instala una tarea y
    # nadie se acuerda de describirla.
    "guardian_sin_ficha": (_fabrica(fichas={VIVOS[0]: _ficha()}), "sin ficha"),
    # Tiene ficha y no dice QUÉ ES. Sin tipo no se puede saber ni dónde buscarlo cuando falle.
    "ficha_sin_tipo": (_fabrica(fichas={VIVOS[0]: _ficha(tipo=None), VIVOS[1]: _ficha()}),
                       "sin `**Tipo:**`"),
    # Dice qué es y no dice qué se rompe si muere, que es la única mitad accionable de una ficha.
    "ficha_sin_consecuencia": (_fabrica(fichas={VIVOS[0]: _ficha(si_muere=None), VIVOS[1]: _ficha()}),
                               "sin `**Si muere:**`"),
    # Y el que cumple la letra sin decir nada: un `Si muere` de tres palabras. Sin umbral, una
    # cabecera sola aprobaría — y entonces el censo mide que alguien tecleó, no que alguien pensó.
    "consecuencia_de_adorno": (_fabrica(fichas={VIVOS[0]: _ficha(si_muere="se rompe"),
                                                VIVOS[1]: _ficha()}),
                               "no dice una consecuencia"),
}


def test_el_censo_honesto_APRUEBA():
    """Sin esto los seis mentirosos caerían gratis: una sonda que suspende siempre los caza todos."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    censo, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(censo)
    assert not ok, nombre + " aprobo, y su censo no describia a todos"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_el_umbral_del_si_muere_se_mide_EN_CARACTERES_UTILES():
    """El caso feo: un `Si muere` largo de espacios. Se recorta antes de medir, o el umbral es papel."""
    pega = C._ficha_completa(_ficha(si_muere="   se rompe   " + " " * MINIMO))
    assert pega, "un Si muere de relleno aprobo el umbral"
    assert "no dice una consecuencia" in pega
