"""La lista de comprobadores exentos del pase de mutación sólo puede DECRECER.

## El agujero que tapa, medido el 2026-08-30

`--verifica` imprimía esto, y pasaba:

    0/0 verificados por mutación (31 declarados no mutables)

**Cero de cero.** El pase adversarial que existe para atacar a los comprobadores y exigir que se
pongan rojos no atacaba a ninguno: los 31 estaban exentos. Y un 0 de 0 es un 100 % — el informe
sale limpio.

La única guarda que había sobre ese número era que no fuera negativo (`31 - 31 = 0`, pasa), así
que nada impedía que las exenciones lo cubrieran todo.

## Por qué se vació, que no fue por dejadez

Los comprobadores se hicieron **mejores que el simulacro**.

La mutación sabe un solo truco: **crear un fichero** y ver si el comprobador cambia de opinión.
Eso funciona contra un detector que pregunta «¿existe este artefacto?». Pero los de aquí fueron
evolucionando a interrogar el mundo real — el Programador de tareas, GitHub, los hooks de verdad,
los cinco repos — y contra eso, plantar un fichero no hace nada. Treinta de las treinta y una
exenciones empiezan literalmente por *«no se muta creando un fichero»*.

O sea que cada comprobador nuevo y mejor nacía, por construcción, fuera del alcance del simulacro.
Uno a uno, hasta 31 de 31. **Nadie lo impedía, y nada lo decía.**

## Por qué un trinquete y no un gate

Se reutiliza `capa_normativa.vigilante.trinquete`, el mecanismo del propio paquete, y su docstring
ya defiende el porqué mejor que esto: *«un gate absoluto sale rojo el día 1 y se desactiva; el
trinquete se calibra sobre el estado actual y sólo prohíbe empeorar»*. Exigir hoy 0 exenciones
pondría el tablero rojo sin nada que hacer, y un rojo así se aprende a ignorar.

Y empieza a servir **de inmediato**, antes de convertir ni un comprobador: con el tope puesto, el
siguiente no puede nacer exento sin que alguien baje el número a mano y explique por qué.

## La regla se corrigió el mismo día, y merece leerse

Esto nació diciendo «el tope sólo se baja». Horas después bloqueó al comprobador de la CI, se
midió por qué no se podía bajar, y salió que `ARTEFACTOS` está VACÍO: el pase de mutación exige
que el comprobador esté ROJO de partida, o sea que sólo sabe atacar a los que aún no funcionan.
Contra uno verde no tiene ataque, y todos los de aquí miran el mundo por `git ls-files` o por el
sistema operativo — no por si existe un fichero suelto.

Así que la regla vieja pedía algo imposible. La nueva conserva lo único que valía: que una
exención no pueda aparecer sin que alguien la nombre. Se deja escrito en vez de reescribir el
docstring como si nunca hubiera dicho otra cosa.

## Qué vigila de cada entrada, y qué NO

El valor vigilado es **el test que nombra su coartada**, no la prosa del motivo. Las prosas se
reescriben a menudo y hacerlo no debería disparar nada; que la coartada apunte a OTRO test sí,
porque significa que la prueba que respalda esa exención ha cambiado.

## La trampa prohibida

Si no se puede leer el tablero, esto es **ROJO por no haber podido mirar**. Un tablero que no carga
daría cero exenciones, y cero exenciones parecería el estado perfecto.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
TABLERO = RAIZ / "scripts" / "aceptacion.py"
BASELINE = Path(__file__).resolve().parent / "exenciones_baseline.json"

#: El tope de HOY. Sólo se mueve A MANO, con `--calibrar` y un commit: ese acto es lo único que
#: convierte un cambio en la deuda en algo que el tablero defiende a partir de ahora.
#:
#: Empieza en 32 y no en 31 porque este comprobador se cuenta a sí mismo: su veredicto sale de leer
#: `SIN_MUTACION` en memoria, así que tampoco se le puede mutar creando un fichero. Decirlo en vez
#: de disimularlo es la mitad del trabajo — el primer paso para bajar el tope es admitir dónde está.
#:
#: 2026-08-30, 32 -> 33, y la primera subida. Entra `ci-de-los-publicos-en-verde`, que pregunta a
#: GitHub por la última corrida de CI de cada repo público: no hay fichero que se pueda plantar para
#: que GitHub conteste otra cosa. Su exención es ESTRUCTURAL, no dejadez.
#:
#: Y la subida obligó a corregir la regla que este mismo fichero escribió por la mañana —«sólo se
#: baja»—, porque medir enseñó que HOY NO SE PUEDE BAJAR: `_verifica` sólo sabe mutar en la
#: dirección rojo -> verde (plantar el artefacto que FALTA), así que no tiene ningún ataque contra
#: un comprobador que ya funciona. `ARTEFACTOS` tiene CERO entradas. Un número que sólo puede subir
#: y nunca bajar no es un trinquete: es el gate que el docstring de arriba dice que no hay que
#: construir. La regla nueva conserva lo que de verdad valía —que ninguna exención pueda aparecer
#: EN SILENCIO— y admite que subir es legítimo cuando se nombra al comprobador y su motivo.
#:
#: El arreglo de fondo está encolado en PENDIENTES: enseñar a `_verifica` la dirección
#: verde -> rojo -> verde. Mientras no exista, este tope sube y no baja, y eso hay que verlo.
TOPE = int(os.environ.get("CN_TOPE_EXENCIONES") or 33)

#: Las dos formas que puede tener una coartada hoy. El vocabulario obliga a clasificar: una entrada
#: sin clase reconocida es una exención que nadie ha mirado.
VOCABULARIO = ("test-nombrado", "autoprueba")


class NoSePudoMirar(Exception):
    """No se pudo leer el tablero. Nunca se traduce a «no hay exenciones»."""


def _tablero():
    if not TABLERO.is_file():
        raise NoSePudoMirar(f"no existe {TABLERO}")
    spec = importlib.util.spec_from_file_location("tablero_para_trinquete", str(TABLERO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def estado_actual() -> dict[str, dict]:
    """{exención: {value, reason, clase}} tal y como está el tablero AHORA."""
    m = _tablero()
    sm = getattr(m, "SIN_MUTACION", None)
    if not sm:
        raise NoSePudoMirar("el tablero no expone SIN_MUTACION, o esta vacio: sospechoso, no limpio")

    fuera = {}
    for nombre, motivo in sm.items():
        tests = sorted(set(re.findall(r"tests/[\w/]+\.py", str(motivo))))
        fuera[nombre] = {
            "value": ", ".join(tests) if tests else "autoprueba",
            "clase": "test-nombrado" if tests else "autoprueba",
            "reason": str(motivo)[:200],
        }
    return fuera


def exenciones_no_suben() -> tuple[bool, str]:
    try:
        actual = estado_actual()
    except NoSePudoMirar as e:
        return False, f"no se pudo mirar ({e}). Eso NO es «no hay exenciones»."

    if not BASELINE.is_file():
        return False, (f"falta {BASELINE.name}: sin linea base el trinquete no puede comparar, y "
                       "sin comparar no vigila nada. Se crea con --calibrar.")

    sys.path.insert(0, str(RAIZ / "src"))
    from capa_normativa.vigilante.trinquete import Trinquete

    tri = Trinquete(
        BASELINE,
        tope=TOPE,
        vocabulario=VOCABULARIO,
        que_migrar_a=("ARTEFACTOS, escribiendo la MENTIRA que le hace cambiar de color "
                      "(un Programador de tareas falso, un GitHub falso: lo que ese comprobador "
                      "pregunte). La mentira de casi todos ya esta escrita en su propio test"),
    )
    hallazgos = tri.revisar(actual)
    if hallazgos:
        return False, " · ".join(str(getattr(h, "mensaje", h))[:150] for h in hallazgos[:3])

    return True, (f"{len(actual)} exenciones, tope {TOPE}: ninguna nueva, ninguna cambiada de "
                  f"coartada. El siguiente comprobador no puede nacer exento en silencio — mover "
                  f"el tope exige --calibrar, un commit y nombrar por que")


def _calibrar() -> int:
    """Congela el estado de hoy como linea base. Se corre A MANO y se commitea."""
    actual = estado_actual()
    BASELINE.write_text(json.dumps(actual, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"linea base escrita: {len(actual)} exenciones en {BASELINE.name}")
    return 0


if __name__ == "__main__":
    if "--calibrar" in sys.argv:
        raise SystemExit(_calibrar())
    ok, msg = exenciones_no_suben()
    print(("VERDE: " if ok else "ROJO: ") + msg)
    sys.exit(0 if ok else 1)
