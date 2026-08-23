"""Los tableros y `--verifica` se ejecutan SOLOS, no cuando alguien se acuerda.

## Qué se exige

Tres cosas, y hacen falta las tres:

1. **Algo lo dispara.** Existe al menos una tarea programada de Windows que ejecuta los tableros
   —su acción nombra `aceptacion.py` o `ronda_de_tableros`— y su última ejecución terminó bien y
   fue hace menos de 48 h.
2. **Y dejó evidencia de haber corrido de verdad.** Hay un informe de ronda fresco, escrito por la
   tarea (no por una persona), que cubre los siete tableros, con todos legibles y sin ninguno
   huérfano ni desaparecido.
3. **`--verifica` también corre.** Porque es quien vigila a los vigilantes: comprueba que cada
   comprobador sabe ponerse rojo. Un tablero que corre solo pero cuyos comprobadores han dejado de
   saber fallar es peor que ninguno — da verdes que no significan nada.

Y si no se puede leer ninguna tarea, es ROJO. Aprobar en vacío se lee como «todo al día», que es
peor que no tener la promesa.

## Por qué existe esta promesa

Medido el 2026-08-23: corren automáticamente el pre-commit (en cada commit de los cinco repos), los
tres Ralph de madrugada y el healthcheck cada 30 min. **Los siete tableros completos y `--verifica`
no los ejecutaba nadie.** Se corrían a mano, y por tanto sólo cuando alguien se acordaba.

Un guarda que nadie ejecuta es decoración: puede llevar semanas en rojo sin que nadie lo vea.

Y nace por un motivo concreto: al encolar el trabajo, dije *«me aseguro de que `--verifica` entre
también»* — una promesa mía, en prosa, sin nada que la hiciera cumplirse. G lo cazó en el mensaje
siguiente. Esto es esa frase convertida en algo que no depende de mi memoria.

## ⚠️ Qué cambió el 2026-08-23 por la tarde, y por qué

La primera versión preguntaba **sólo** al Programador de tareas, y lo decía con su motivo: *«no se
puede dictar el formato del informe de un trabajo que aún no está hecho; quien lo haga elegirá otro
nombre y esto se quedaría rojo por una tontería»*. Era la decisión correcta entonces.

Ese trabajo ya está hecho (`scripts/ronda_de_tableros.py`), así que el motivo caducó — y con él
caducó también la debilidad que tenía: **una tarea puede arrancar, salir 0 y no haber corrido ni un
tablero.** Buscar `aceptacion.py` dentro de la cadena de la acción es buscar una subcadena, y una
subcadena no prueba nada sobre lo que pasó.

Así que ahora se le exigen las dos mitades. Es **más** estricto, no menos: lo que antes era rojo
sigue siendo rojo, y además deja de poder aprobarse con una tarea que no hace nada. La condición
del `--verifica` conserva las dos puertas —que lo nombre una tarea, **o** que el informe demuestre
que corrió en todos los tableros— para no estrechar el contrato original a una sola implementación.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_PS = r"""
$out = @()
Get-ScheduledTask -TaskPath '\' | ForEach-Object {
  $t = $_
  $args = ($t.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' '
  $i = $t | Get-ScheduledTaskInfo
  $out += [pscustomobject]@{
    nombre = $t.TaskName
    accion = $args
    ultimo = if ($i.LastRunTime) { $i.LastRunTime.ToString('s') } else { '' }
    resultado = $i.LastTaskResult
  }
}
$out | ConvertTo-Json -Compress
"""

#: Cómo se reconoce una tarea que dispara los tableros. Dos nombres, no uno: el directo (alguien
#: encadena `aceptacion.py` en la propia tarea) y el de la ronda (una tarea que los corre todos).
#: Se aceptan los dos a propósito, para no atar la promesa a una implementación concreta.
_FIRMAS_DE_TAREA = ("aceptacion.py", "ronda_de_tableros")


def _ronda():
    """El módulo de la ronda, del árbol propio. `None` si todavía no existe."""
    guion = Path(__file__).resolve().parent.parent / "ronda_de_tableros.py"
    if not guion.is_file():
        return None
    spec = importlib.util.spec_from_file_location("ronda_para_la_promesa", str(guion))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tareas() -> list:
    """Las tareas programadas de hoy, con su accion y su ultima ejecucion. Se le pregunta al
    Programador de tareas, que es quien dispara las cosas en esta maquina."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", _PS],
                       capture_output=True, timeout=180)
    salida = r.stdout.decode("utf-8", "replace").strip()
    if not salida:
        return []
    datos = json.loads(salida)
    return datos if isinstance(datos, list) else [datos]


def informe_de_la_ronda():
    """El ultimo informe de la ronda, o `None`. Punto de inyeccion para los tests, igual que
    `tareas()`: el veredicto se comprueba dandole el mundo, no montando el mundo."""
    m = _ronda()
    return None if m is None else m.leer_ultimo()


#: `SCHED_S_TASK_RUNNING` (0x41301). Windows lo pone en `LastTaskResult` MIENTRAS la tarea corre.
#:
#: ⚠️ Sin esto la ronda se ponia ROJA A SI MISMA en cada informe que escribia, y es una trampa de
#: auto-referencia con nombre propio: el tablero de `capa-normativa` es UNO de los siete que corre
#: la ronda, asi que este comprobador se ejecuta SIEMPRE con su propia tarea en marcha. Preguntar
#: por el resultado de algo que aun no ha terminado es preguntar por algo que todavia no existe.
#:
#: Se descubrio ejecutandola de verdad desde el Programador: 21 verdes / 5 rojos donde la misma
#: pasada a mano daba 23 / 3. Leyendo el codigo no se ve; solo aparece cuando se muerde la cola.
#:
#: Un cuelgue no se cuela por aqui: si la tarea lleva tres dias «corriendo», su `LastRunTime` es de
#: hace tres dias, y de ahi sale el `arranque` que el veredicto exige fresco.
_EJECUTANDOSE = 267009


def _reciente(iso: str, horas: int = 48) -> bool:
    if not iso:
        return False
    try:
        return (dt.datetime.now() - dt.datetime.fromisoformat(iso)).total_seconds() < horas * 3600
    except Exception:
        return False


def main() -> int:
    todas = tareas()
    if not todas:
        print("ROJO: no se pudo leer ninguna tarea programada — sin eso esta comprobacion"
              " aprobaria en vacio, y aprobar en vacio se lee como «todo al dia»")
        return 1

    corre_tableros = [t for t in todas
                      if any(f in (t.get("accion") or "") for f in _FIRMAS_DE_TAREA)]
    corre_verifica = [t for t in corre_tableros if "--verifica" in (t.get("accion") or "")]

    if not corre_tableros:
        print("ROJO: ninguna tarea programada ejecuta los tableros: solo corren cuando alguien"
              " se acuerda")
        return 1
    vivas = [t for t in corre_tableros
             if t.get("resultado") == _EJECUTANDOSE
             or (t.get("resultado") == 0 and _reciente(t.get("ultimo", "")))]
    if not vivas:
        print("ROJO: hay tarea para los tableros (" + ", ".join(
            str(t.get("nombre")) for t in corre_tableros) + ") pero NINGUNA ha terminado bien en"
            " las ultimas 48 h: registrada no es lo mismo que arrancando")
        return 1

    ronda = _ronda()
    if ronda is None:
        print("ROJO: no existe scripts/ronda_de_tableros.py, asi que no hay quien deje evidencia"
              " de que los tableros han corrido — una tarea puede arrancar, salir 0 y no haber"
              " corrido ni uno")
        return 1

    # El arranque que se le entrega al veredicto es el de la tarea MAS reciente que haya terminado
    # bien. Asi las dos mitades se apoyan en la misma medida en vez de preguntar dos veces.
    arranque = max(dt.datetime.fromisoformat(t["ultimo"]) for t in vivas)
    ok, motivo = ronda.veredicto(informe_de_la_ronda(), dt.datetime.now(), arranque,
                                 verifica_por_tarea=bool(corre_verifica))
    if not ok:
        print("ROJO: " + motivo)
        return 1

    print("VERDE: " + str(len(corre_tableros)) + " tarea(s) ejecutan los tableros, con ejecucion"
          " buena y reciente, y el informe lo confirma — " + motivo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
