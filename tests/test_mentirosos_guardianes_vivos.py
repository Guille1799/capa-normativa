"""MENTIROSOS de `guardianes-vivos`: ocho guardianes de pega, cada uno muerto de una manera.

## Qué es un mentiroso, y por qué no basta con un test que pase

Un MENTIROSO es una implementación **completa** de la cosa que el comprobador juzga —aquí, una
tarea del Programador de Windows— rota por **UNA sola razón**, y el test exige que caiga **en SU
caso**. Estructuralmente son dos exigencias:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

Sin la segunda no se distingue «cae» de «cae por la razón equivocada», que es exactamente contra
lo que existen. Un solo mentiroso roto por dos razones a la vez sobreviviría a que le quitaran una
exigencia al comprobador: por eso todos son honestos en todo lo demás a propósito.

## Qué protege este comprobador

`guardianes_vivos.muertos()` es quien separa «el guardián existe» de «el guardián FUNCIONA», y esa
diferencia costó 73 días sin que nadie la viera: `ClaudeWarmup` llevaba desactivada desde el 12 de
junio, con 51 corridas perdidas, y figuraba en el censo tan tranquila.

Sus ramas son ocho y no se parecen: desactivada, nunca corrida, sin correr desde hace días,
resultado ilegible, no llegó a arrancar (127 y 126), y muerta por Windows. Cada una pide un arreglo
distinto —activar la tarea, reponer el guion, cambiar la batería— así que un rojo que no diga cuál
es no acciona nada.
"""
from __future__ import annotations

import datetime
import importlib.util
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parent.parent / "scripts" / "aceptaciones" / "guardianes_vivos.py"

#: Un reloj FIJO, inyectado. La fecha de la tarea honesta se deriva de él y no se escribe: escrita,
#: el fichero se ponía rojo solo al cruzar `_DIAS_SIN_CORRER` días después (pasó el 2026-08-31 en
#: `test_guardianes_vivos.py`, y el arreglo sólido es que no haya número que mover).
HOY = datetime.datetime(2026, 9, 14, 12, 0, 0)


def _cargar():
    spec = importlib.util.spec_from_file_location("vivos_para_mentirosos", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GV = _cargar()


def _reloj(dias_atras: float) -> str:
    """Una marca del Programador, en su formato de siempre, derivada de `HOY`."""
    return (HOY - datetime.timedelta(days=dias_atras)).strftime("%m/%d/%Y %I:%M:%S %p")


def _fabrica(*, estado="Ready", ultima=None, resultado="0",
             accion=r"C:\Users\x\proyectos\ralph_cn.cmd"):
    """Una tarea programada de pega. Por defecto es la HONESTA; cada argumento mete UNA mentira.

    Honesta significa las cuatro cosas a la vez: es TUYA (su acción ejecuta un guion tuyo, que es
    el filtro que impide juzgar a los actualizadores de Adobe), está activa, corrió ayer, y su
    último intento salió 0.
    """
    return {"nombre": "guardian-de-pega", "estado": estado,
            "ultima": _reloj(1) if ultima is None else ultima,
            "resultado": resultado, "accion": accion}


HONESTO = _fabrica()


def _sonda(tarea):
    """El comprobador de verdad, con UNA tarea delante. `(aprueba, por qué no)`."""
    caidos = GV.muertos([tarea], hoy=HOY)
    return not caidos, "; ".join(porque for _, porque in caidos)


MENTIROSOS = {
    # Figura en el censo y nadie la va a lanzar nunca. Es `ClaudeWarmup` tal cual: 51 corridas
    # perdidas y un inventario que seguía diciendo que estaba.
    "desactivada": (_fabrica(estado="Disabled"), "DESACTIVADA"),
    # El Programador pone `12/30/1899` cuando una tarea nunca ha corrido. Leerlo como «hace mucho»
    # o como «cero» son dos formas de inventarse una medida que no se tiene.
    "nunca_ha_corrido": (_fabrica(ultima="12/30/1899 12:00:00 AM"),
                         "no ha corrido nunca, o su fecha no se pudo leer"),
    # Activa, con fecha legible, y esa fecha es de hace un mes. No está apagada: está abandonada,
    # y el arreglo no es el mismo.
    "activa_pero_sin_correr": (_fabrica(ultima=_reloj(30)), "activa pero sin correr desde hace"),
    # Su `LastTaskResult` no es un número. No se puede juzgar, y eso NO es aprobar.
    "resultado_ilegible": (_fabrica(resultado="ERROR"), "su ultimo resultado no es un numero"),
    # 127 es el shell diciendo que NO ENCONTRÓ qué ejecutar. Cae del lado de los códigos pequeños
    # —donde vive «el programa eligió esto»— diciendo justo lo contrario. Caso real: sincronizar el
    # worktree del robot borró `scripts/ralph.sh`, y el guardián de los guardianes lo daba por vivo.
    "no_encuentra_su_guion": (_fabrica(resultado="127"), "NO LLEGO A ARRANCAR: salio 127"),
    # 126 es el hermano del anterior y pide otro arreglo: el fichero está, pero no es ejecutable.
    "su_guion_no_es_ejecutable": (_fabrica(resultado="126"), "NO LLEGO A ARRANCAR: salio 126"),
    # Por encima de 0x80000000 el código lo puso Windows, no el programa: la tarea no llegó a
    # terminar. Gritar no es morir; esto sí es morir.
    "la_mato_windows": (_fabrica(resultado=str(0x8007000E)), "NO llego a terminar"),
    # Y el caso de Windows que ya se midió aquí: no falló el programa, Windows SE NEGÓ a lanzarla
    # por estar a batería. El mensaje tiene que decir eso, o se buscan bugs donde no los hay.
    "no_la_lanzo_por_la_bateria": (_fabrica(resultado=str(0x800710E0)),
                                   "DisallowStartIfOnBatteries"),
}


def test_el_guardian_honesto_APRUEBA():
    """Si el honesto no aprobara, los mentirosos no probarían nada: todos caerían gratis."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    tarea, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(tarea)
    assert not ok, nombre + " aprobo, y es un guardian muerto"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_un_guardian_que_NO_ES_TUYO_no_se_juzga():
    """El filtro que evita el ruido: sin él salían 12 «muertos» de 24, la mitad actualizadores.

    Se prueba con el caso más feo — una tarea de tercero DESACTIVADA y sin correr en un mes, o sea
    dos mentiras a la vez— porque el filtro tiene que ganarle a las dos.
    """
    ajeno = _fabrica(estado="Disabled", ultima=_reloj(90),
                     accion=r"C:\Program Files\Adobe\AdobeGCClient\AGCInvokerUtility.exe")
    ok, motivo = _sonda(ajeno)
    assert ok, "juzgar a terceros es el ruido que hace que nadie lea este comprobador: " + motivo
