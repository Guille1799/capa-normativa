"""MENTIROSOS de `tableros-corren-solos`: once rondas de pega, cada una falsa por un sitio.

## Qué es un mentiroso

Una implementación **completa** de la cosa que el comprobador juzga —aquí, el par (informe de la
ronda, hora del último arranque)— rota por **UNA sola razón**, con el test exigiendo que caiga
**en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

Todos son honestos en todo lo demás a propósito. Uno roto por dos razones sobreviviría a que le
quitaran una exigencia al comprobador, que es justo cómo un test pasa por la razón equivocada.

## Qué protege

`ronda_de_tableros.veredicto()` es una función PURA —se le da el mundo, no lo mira— y es el juez
de la promesa «los tableros corren solos». Su valor está en que pregunta ocho cosas que se parecen
sólo de lejos:

  · ¿ha arrancado la tarea alguna vez? · ¿arrancó hace poco? · ¿dejó evidencia? · ¿esa evidencia
  dice cuándo terminó? · ¿es reciente? · ¿la lanzó una tarea o una persona? · ¿cubrió todos los
  tableros? · ¿corrió `--verifica`, que es quien vigila a los vigilantes?

Y cada una tiene su arreglo: reponer la tarea, encender el portátil, mirar por qué la ronda no
escribe, añadir el tablero que falta. Un rojo que no diga cuál de las ocho es no acciona nada — y
un verde que se gane saltándose una es peor, porque se lee como que todo lo demás está vigilado.
"""
from __future__ import annotations

import datetime
import importlib.util
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parent.parent / "scripts" / "ronda_de_tableros.py"

#: Reloj FIJO e inyectado: `veredicto` recibe el «ahora», así que aquí no hay bomba de relojería.
AHORA = datetime.datetime(2026, 9, 14, 12, 0, 0)


def _cargar():
    spec = importlib.util.spec_from_file_location("ronda_para_mentirosos", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _cargar()

#: El suelo de tableros sale del MÓDULO, no se escribe aquí. Escrito, el día que la ronda cubra un
#: tablero más este fichero se pondría rojo por un motivo que no tiene nada que ver con él.
SUELO = R.SUELO_TABLEROS
VENTANA = R.VENTANA_H


def _tablero(nombre, *, estado="ok", verifica=0, rojos=()):
    return {"nombre": nombre, "estado": estado, "rojos": list(rojos),
            "verifica": {"exit": verifica}}


def _fabrica(*, terminado=None, lanzador="tarea-programada", corridos=None, tableros=None,
             huerfanos=(), ausentes=()):
    """Un informe de ronda de pega. Por defecto el HONESTO; cada argumento mete UNA mentira."""
    if tableros is None:
        tableros = [_tablero("tablero-" + str(i)) for i in range(SUELO)]
    return {
        "terminado": (AHORA - datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
                     if terminado is None else terminado,
        "lanzador": lanzador,
        "corridos": len(tableros) if corridos is None else corridos,
        "tableros": tableros,
        "huerfanos": list(huerfanos),
        "ausentes": list(ausentes),
    }


#: La tarea arrancó hace tres horas: dentro de la ventana, como el informe honesto.
ARRANQUE = AHORA - datetime.timedelta(hours=3)

HONESTO = (_fabrica(), ARRANQUE)


def _sonda(caso):
    informe, arranque = caso
    return R.veredicto(informe, AHORA, arranque)


MENTIROSOS = {
    # La tarea está REGISTRADA y nunca ha arrancado. Registrada no es lo mismo que arrancando, y
    # esa confusión es la que hace que un inventario tranquilice sin proteger.
    "la_tarea_nunca_arranco": ((_fabrica(), None), "NUNCA ha arrancado"),
    # Arrancó, pero hace más de la ventana: ha dejado de correr. Distinto del informe viejo, y el
    # arreglo también: aquí falla el Programador, allí falla la ronda.
    "la_tarea_dejo_de_arrancar": ((_fabrica(), AHORA - datetime.timedelta(hours=VENTANA + 5)),
                                  "su ultimo arranque fue hace"),
    # Arranca todos los días y no escribe nada. Una tarea que sale 0 sin haber hecho el trabajo es
    # indistinguible de una que lo hizo, salvo por la evidencia.
    "arranca_y_no_deja_evidencia": ((None, ARRANQUE), "no deja evidencia"),
    # Hay informe y no dice cuándo terminó: no sirve como evidencia, porque no se puede fechar.
    "el_informe_no_se_fecha": ((_fabrica(terminado=None) | {"terminado": "el martes"}, ARRANQUE),
                               "no dice cuando termino"),
    # El informe es de hace una semana. La tarea puede seguir arrancando: lo que ha muerto es la
    # ronda, y el mensaje tiene que señalar al informe, no al Programador.
    "el_informe_es_viejo": ((_fabrica(terminado=(AHORA - datetime.timedelta(hours=VENTANA + 5))
                                      .strftime("%Y-%m-%dT%H:%M:%S")), ARRANQUE),
                            "el ultimo informe es de hace"),
    # Informe fresco, completo y perfecto... lanzado a mano. Eso demuestra que el guion funciona,
    # que es exactamente lo que esta promesa NO pregunta.
    "lo_lanzo_una_persona": ((_fabrica(lanzador="a-mano"), ARRANQUE), "lo lanzo una persona a mano"),
    # Corrió, pero sólo la mitad de los tableros. Una ronda incompleta no vigila lo que falta, y su
    # verde se lee como si vigilara todo.
    "ronda_incompleta": ((_fabrica(tableros=[_tablero("t" + str(i)) for i in range(SUELO - 1)]),
                          ARRANQUE), "tiene que cubrir"),
    # Un tablero que la ronda no pudo leer. No es un rojo suyo: es un hueco en la vigilancia, y
    # contarlo como «ok» sería aprobar en vacío.
    "un_tablero_ilegible": ((_fabrica(tableros=[_tablero("t0", estado="error")]
                                      + [_tablero("t" + str(i)) for i in range(1, SUELO)]),
                             ARRANQUE), "no pudo leer"),
    # Todo verde y `--verifica` no llegó a correr. Tableros corriendo solos con comprobadores que
    # ya no saben ponerse rojos son verdes que no significan nada.
    "sin_verifica": ((_fabrica(tableros=[_tablero("t0", verifica=None)]
                               + [_tablero("t" + str(i)) for i in range(1, SUELO)]),
                      ARRANQUE), "no llego a correr `--verifica`"),
    # Hay un tablero en el disco que nadie vigila ni ha declarado. El peligro no es que esté rojo:
    # es que nadie lo mira y su silencio se lee como buenas noticias.
    "un_tablero_huerfano": ((_fabrica(huerfanos=["mcp_smart_context/scripts/aceptacion.py"]),
                             ARRANQUE), "que nadie vigila ni ha declarado"),
    # Y el simétrico: un tablero declarado que ya no está. La lista miente en la otra dirección.
    "un_tablero_declarado_que_falta": ((_fabrica(ausentes=["ponerse_wenorro"]), ARRANQUE),
                                       "declarados que ya no estan"),
}


def test_la_ronda_honesta_APRUEBA():
    """Sin esto los mentirosos no prueban nada: una sonda que suspende siempre los caza todos."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    caso, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(caso)
    assert not ok, nombre + " aprobo, y su ronda no corre sola"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_una_tarea_propia_de_verifica_ABRE_la_otra_puerta():
    """`sin_verifica` es un mentiroso sólo si nadie más corre `--verifica`.

    La condición no es «que lo haga la ronda»: es que se haga. Si hay una tarea programada que ya
    lo ejecuta por su cuenta, exigirlo otra vez estrecharía el contrato a UNA implementación — que
    es cómo un guardián acaba pidiendo trabajo que no protege nada.
    """
    informe, _ = MENTIROSOS["sin_verifica"][0]
    ok, motivo = R.veredicto(informe, AHORA, ARRANQUE, verifica_por_tarea=True)
    assert ok, motivo
