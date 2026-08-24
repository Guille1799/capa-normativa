"""Un guardián que figura en el censo pero está apagado sigue figurando. Esto pregunta si vive.

## Por qué existe (medido el 2026-08-24)

El censo (`censo_de_guardianes.py`) enumera lo que arranca solo y exige que cada uno esté descrito.
No pregunta si **funciona**. Y esa diferencia costó 73 días sin que nadie lo viera:

    ClaudeWarmup   Disabled   ultima corrida: 12-jun-2026   51 corridas perdidas

`ClaudeWarmup` existe para llamar a `claude -p` a diario, que es lo que **renueva el token de
refresco**. O sea: el guardián que mantiene viva la autonomía llevaba apagado desde junio. Lo tapaba
Ralph, que hace esa misma llamada cada noche — pero la cola segura de `capa-normativa` está hoy a
cero tareas, así que esa tapadera es más fina de lo que parece.

Es el mismo fallo de `AUTONOMIA_MUERTA_41_DIAS`, otra vez y más largo. Un inventario que dice
«existe» y no dice «funciona» es un inventario que tranquiliza.

## Qué se mira, y qué NO

Tres señales, y las tres son inequívocas:

  · **Desactivada** — no hay interpretación posible: no va a correr.
  · **Sin correr en más de `_DIAS_SIN_CORRER` días** — existe, está activa, y aun así no pasa nada.
  · **El último intento falló** — corrió y murió; el siguiente probablemente también.

Y una que se descarta a propósito: **`NumberOfMissedRuns` NO es señal**. Un portátil apagado a las
3:00 acumula corridas perdidas sin que nada esté roto — hoy `ralph-cn` lleva 3, `ralph-diario-mcp`
2 y `ralph-eu` 1, y las tres funcionan. Un comprobador que se pusiera rojo por eso enseñaría a
ignorarlo, que es la forma en que mueren los guardianes buenos.

## La trampa prohibida, otra vez

Si el Programador no contesta, esto es ROJO por «no pude mirar» — nunca «no hay guardianes muertos».
La enumeración se le pide al censo para no tener dos algoritmos que puedan divergir.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CENSO = Path(__file__).resolve().parent / "censo_de_guardianes.py"
_spec = importlib.util.spec_from_file_location("censo_para_vivos", str(_CENSO))
_censo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_censo)

FuenteRota = _censo.FuenteRota

#: Días sin correr a partir de los cuales una tarea activa se considera parada. Siete cubre el
#: caso real de un portátil que pasa un fin de semana apagado sin dar un falso rojo el lunes.
_DIAS_SIN_CORRER = 7

#: Códigos de salida que NO son muerte, cada uno con su motivo escrito. Una lista de tolerancias
#: sin motivos es el sitio donde un fallo real se esconde de por vida.
_RESULTADOS_TOLERADOS = {
    0: "exito",
    267009: "SCHED_S_TASK_RUNNING: la tarea esta corriendo AHORA MISMO, asi que aun no hay "
            "resultado. Sin esto, una ronda se ponia roja a si misma al medirse mientras corria.",
    267011: "SCHED_S_TASK_HAS_NOT_RUN: nunca ha corrido todavia. Lo canta la señal de «sin correr "
            "en N dias», que dice mas y con fecha.",
}


def _es_tuya(tarea: dict) -> bool:
    """El mismo criterio que el censo: es tuya si ejecuta un script que escribiste.

    Sin esto, la primera version juzgaba a Adobe, Edge, NVIDIA y OneDrive y sacaba 12 «guardianes
    muertos» de 24, la mitad de ellos actualizadores de terceros. Un comprobador con esa proporcion
    de ruido no se lee — y uno que no se lee no protege de nada. El criterio se importa del censo
    en vez de copiarse, para que no puedan separarse.
    """
    return any(ext in tarea.get("accion", "").lower() for ext in _censo._SCRIPTS)


def _dias_desde(marca: str, hoy=None) -> float | None:
    """Días desde una fecha del Programador. `None` si no se pudo interpretar — y eso NO es cero."""
    import datetime
    texto = (marca or "").strip()
    if not texto or texto.startswith(("12/30/1899", "1/1/0001", "30/12/1899")):
        return None
    for formato in ("%m/%d/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
                    "%Y-%m-%d %H:%M:%S"):
        try:
            cuando = datetime.datetime.strptime(texto, formato)
        except ValueError:
            continue
        ahora = hoy or datetime.datetime.now()
        return (ahora - cuando).total_seconds() / 86400
    return None


def muertos(tareas=None, hoy=None) -> list[tuple[str, str]]:
    """(nombre, por que se le da por muerto), para cada guardian que no vive."""
    filas = _censo.tareas_detalladas() if tareas is None else tareas
    filas = [t for t in filas if _es_tuya(t)]
    fuera = []
    for t in filas:
        nombre = t["nombre"]
        if (t.get("estado") or "").strip().lower() == "disabled":
            fuera.append((nombre, f"DESACTIVADA — no va a correr. Ultima corrida: "
                                  f"{t.get('ultima') or 'nunca'}"))
            continue
        dias = _dias_desde(t.get("ultima"), hoy)
        if dias is None:
            fuera.append((nombre, "no ha corrido nunca, o su fecha no se pudo leer — que no es "
                                  "lo mismo que haber corrido bien"))
            continue
        if dias > _DIAS_SIN_CORRER:
            fuera.append((nombre, f"activa pero sin correr desde hace {dias:.0f} dias"))
            continue
        try:
            res = int(t.get("resultado") or 0)
        except (TypeError, ValueError):
            fuera.append((nombre, f"su ultimo resultado no es un numero: {t.get('resultado')!r}"))
            continue
        if res not in _RESULTADOS_TOLERADOS:
            fuera.append((nombre, f"su ultimo intento fallo con {res} (0x{res & 0xFFFFFFFF:08X})"))
    return fuera


def guardianes_vivos() -> tuple[bool, str]:
    try:
        filas = _censo.tareas_detalladas()
    except FuenteRota as e:
        return False, (f"no se pudo preguntar al Programador ({e}). Eso es NO HABER MIRADO, "
                       "no «ningun guardian muerto».")
    if not filas:
        return False, "el Programador no devolvio ninguna tarea: eso es no haber podido mirar"

    vivos_totales = [t for t in filas if _es_tuya(t)]
    caidos = muertos(filas)
    if caidos:
        detalle = "; ".join(f"{n} ({p})" for n, p in caidos[:3])
        mas = f" (+{len(caidos) - 3} mas)" if len(caidos) > 3 else ""
        return False, (f"{len(caidos)} de {len(vivos_totales)} guardianes programados TUYOS NO viven: "
                       f"{detalle}{mas}")
    return True, (f"los {len(vivos_totales)} guardianes tuyos estan activos, han corrido en los "
                  f"ultimos {_DIAS_SIN_CORRER} dias y su ultimo intento no fallo")


if __name__ == "__main__":
    ok, msg = guardianes_vivos()
    print(("VERDE: " if ok else "ROJO: ") + msg)
    sys.exit(0 if ok else 1)
