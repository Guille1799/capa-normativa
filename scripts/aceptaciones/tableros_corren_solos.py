"""Los tableros y `--verifica` se ejecutan SOLOS, no cuando alguien se acuerda.

## Qué se exige

Dos cosas, y hacen falta las dos:

1. **Los siete tableros corren solos.** Existe al menos una tarea programada de Windows cuya acción
   ejecuta `aceptacion.py`, y su última ejecución terminó bien y fue hace menos de 48 h.
2. **`--verifica` también.** Alguna tarea (la misma u otra) lo incluye. Porque `--verifica` es quien
   vigila a los vigilantes: comprueba que cada comprobador sabe ponerse rojo. Un tablero que corre
   solo pero cuyos comprobadores han dejado de saber fallar es peor que ninguno — da verdes que no
   significan nada.

## Por qué existe esta promesa

Medido el 2026-08-23: corren automáticamente el pre-commit (en cada commit de los cinco repos), los
tres Ralph de madrugada y el healthcheck cada 30 min. **Los siete tableros completos y `--verifica`
no los ejecuta nadie.** Se corren a mano, y por tanto sólo cuando alguien se acuerda.

Un guarda que nadie ejecuta es decoración: puede llevar semanas en rojo sin que nadie lo vea.

Y esta promesa nace por un motivo concreto: al encolar el trabajo, dije *«me aseguro de que
`--verifica` entre también»* — una promesa mía, en prosa, sin nada que la hiciera cumplirse. G lo
cazó en el mensaje siguiente. Esto es esa frase convertida en algo que no depende de mi memoria.

## Por qué pregunta al PROGRAMADOR y no por un fichero

Porque no se puede dictar el formato del informe de un trabajo que aún no está hecho: quien lo haga
elegirá otro nombre y esto se quedaría rojo por una tontería. Lo que sí es verdad de cualquier
implementación es que **algo tiene que dispararlo**, y en esta máquina eso es el Programador de
tareas de Windows. Se le pregunta a él, que es la fuente.

⚠️ Nace ROJA: hoy no existe ninguna tarea así.
"""
from __future__ import annotations

import json
import subprocess
import sys

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


def _reciente(iso: str, horas: int = 48) -> bool:
    import datetime as dt
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

    corre_tableros = [t for t in todas if "aceptacion.py" in (t.get("accion") or "")]
    corre_verifica = [t for t in corre_tableros if "--verifica" in (t.get("accion") or "")]

    problemas = []
    if not corre_tableros:
        problemas.append("ninguna tarea programada ejecuta `aceptacion.py`: los siete tableros solo"
                         " corren cuando alguien se acuerda")
    else:
        vivas = [t for t in corre_tableros
                 if t.get("resultado") == 0 and _reciente(t.get("ultimo", ""))]
        if not vivas:
            problemas.append("hay tarea para los tableros (" + ", ".join(
                t["nombre"] for t in corre_tableros) + ") pero NINGUNA ha terminado bien en las"
                " ultimas 48 h: registrada no es lo mismo que arrancando")
    if not corre_verifica:
        problemas.append("ninguna tarea incluye `--verifica`: nadie comprueba que los"
                         " comprobadores sigan sabiendo ponerse rojos")

    if problemas:
        print("ROJO: " + "; ".join(problemas))
        return 1
    print("VERDE: " + str(len(corre_tableros)) + " tarea(s) ejecutan los tableros y "
          + str(len(corre_verifica)) + " incluyen --verifica, con ejecucion buena y reciente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
