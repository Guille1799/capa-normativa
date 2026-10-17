"""Todo lo que arranca solo en esta máquina está descrito, y se dice qué se rompe si muere.

## Por qué existe

`AUTONOMIA_MUERTA_41_DIAS` documenta el fallo que este censo previene: algo que corría solo dejó de
correr y **nadie se enteró en 41 días**. El silencio de un guardián muerto y el silencio de un
guardián que no encuentra nada se ven exactamente igual.

Un inventario a mano no sirve, porque el que se olvida de mirar es el mismo que se olvidó de
apuntar. Así que aquí la lista **se enumera de las fuentes vivas** y lo único que se escribe a mano
es lo que ninguna máquina puede saber: qué se rompe cuando eso falta.

## Qué cuenta como guardián (decisión de G, 2026-08-24)

**Todo lo que arranca solo**, no sólo lo que vigila. La pregunta no era «¿cuáles son importantes?»
sino «¿para qué es el censo?»: si es para enterarte de una muerte, entonces `ContextWatcher-Reindex`
cuenta — cuando muere, el RAG se queda viejo y sigues preguntándole como si nada. Que no «vigile»
lo hace más peligroso, no menos, porque nadie lo echa de menos.

## Cómo se separan tus tareas del ruido, sin una lista a mano

Una lista de exclusiones se queda vieja el día que instalas otro programa. El criterio es medido:
**una tarea es tuya si ejecuta un script que escribiste** (`.ps1`, `.py`, `.cmd`, `.bat`, `.sh`).
Adobe, Edge, NVIDIA, OneDrive y Opera ejecutan un `.exe` de fábrica y se caen solos de la lista;
una tarea nueva tuya entra sola. Lo que el criterio deja fuera —`OllamaServe`, que es un binario—
puede describirse igual en el censo: **el censo puede tener de más, nunca de menos**.

## La trampa que este comprobador tiene prohibida

Aprobar en vacío. Si PowerShell falla, las tareas salen 0 y el censo cuadraría con menos guardianes
de los que hay: un verde por no haber podido mirar. Por eso **cada fuente falla en ROJO por
separado**, y una enumeración total vacía es ROJO aunque el censo esté impecable.
"""
from __future__ import annotations

import functools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ_PROYECTOS = Path(os.environ.get("PROYECTOS_RAIZ") or Path.home() / "proyectos")
CENSO = RAIZ_PROYECTOS / "GUARDIANES.md"
SETTINGS_USUARIO = Path(os.environ.get("CLAUDE_SETTINGS") or Path.home() / ".claude" / "settings.json")
#: Las rutinas de Claude Desktop: una carpeta con su `SKILL.md` por rutina. Su estado (activa o no)
#: vive en la app, no aquí, así que sólo sirven para la vuelta: «¿existe lo que esta ficha nombra?».
RUTINAS = Path(os.environ.get("CLAUDE_RUTINAS") or Path.home() / ".claude" / "scheduled-tasks")

#: Extensiones que delatan «esto lo escribió una persona», frente al `.exe` de un instalador.
_SCRIPTS = (".ps1", ".py", ".cmd", ".bat", ".sh")

#: Una ficha es EXACTAMENTE «## `id`». Un encabezado de sección con comillas invertidas en medio
#: («## Hooks de `eu` (y su gemelo `eu-ralph`)») no es una ficha: antes salía como la ficha `eu`.
_CABECERA = re.compile(r"^## `([^`]+)`\s*$")

#: Mínimo de texto útil en el «Si muere». Un guion suelto no explica nada; 40 caracteres obligan a
#: una frase. No es una cifra sagrada: es el umbral por debajo del cual no cabe una consecuencia.
_MINIMO_SI_MUERE = 40


class FuenteRota(Exception):
    """Una fuente no se pudo enumerar. Nunca se traduce a «hay menos guardianes»."""


def _hooks_de(settings: Path, etiqueta: str) -> list[str]:
    if not settings.exists():
        return []
    try:
        d = json.loads(settings.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise FuenteRota(f"{settings} no se pudo leer: {e}") from e
    fuera = []
    for entradas in (d.get("hooks") or {}).values():
        for entrada in entradas:
            for h in entrada.get("hooks", []):
                # El guion puede venir en `command` ("python x.py") o en `args` aparte
                # ("command": "python", "args": ["...x.py"]). Mirar solo `command` colapsaba
                # CINCO guardianes distintos de G en un unico `hook:usuario:python` — y un censo
                # que cuenta de menos es peor que no tenerlo: cuadra mientras uno esta muerto.
                partes = [h.get("command", "")] + [str(a) for a in (h.get("args") or [])]
                trozos = [t.strip('"\'') for t in " ".join(partes).split()]
                guion = next((t for t in trozos if t.lower().endswith(_SCRIPTS)), None)
                nombre = Path(guion).name if guion else (trozos[0] if trozos else "?")
                fuera.append(f"hook:{etiqueta}:{nombre}")
    return fuera


@functools.lru_cache(maxsize=1)
def tareas_detalladas() -> list[dict]:
    """Las tareas de la raíz del Programador, con su estado y su último resultado.

    Una sola consulta para las dos preguntas que se le hacen al Programador —«¿quién arranca solo?»
    (este censo) y «¿siguen vivos?» (`guardianes_vivos.py`)—, porque dos consultas para una misma
    fuente es la forma de que empiecen a discrepar sin que nadie lo note.

    Se cuenta DOS veces —el total por un lado, el detalle por otro— y se exige que cuadre. El
    motivo es medido: `Get-ScheduledTask` devuelve a veces *«A general error occurred»* sin más, y
    las dos salidas obvias son malas. Con `-ErrorAction Stop`, ese fallo transitorio pinta el censo
    de rojo y un rojo intermitente enseña a ignorarlo. Con `SilentlyContinue`, la tarea ilegible
    **desaparece de la cuenta** y el censo cuadra con un guardián de menos, que es exactamente lo
    que no puede pasar. Cuadrando total contra detalle, una tarea que no se deja leer se ve; y el
    reintento absorbe el fallo pasajero sin tapar el permanente.
    """
    ps = (
        "$t = @(Get-ScheduledTask -TaskPath '\\' -ErrorAction SilentlyContinue); "
        "'TOTAL|' + $t.Count; "
        "foreach ($x in $t) { $a = ($x.Actions | Select-Object -First 1); "
        "$i = $x | Get-ScheduledTaskInfo; "
        "'{0}|{1} {2}|{3}|{4}|{5}' -f $x.TaskName, $a.Execute, $a.Arguments, $x.State, "
        "$i.LastRunTime, $i.LastTaskResult }"
    )
    ultimo = ""
    for intento in (1, 2):
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=180)
        except Exception as e:  # noqa: BLE001
            ultimo = f"no se pudo preguntar al Programador: {e}"
            continue

        salida = (r.stdout or "").splitlines()
        cabecera = next((l for l in salida if l.startswith("TOTAL|")), None)
        if cabecera is None:
            ultimo = (f"el Programador no dijo cuantas tareas hay (intento {intento}): "
                      + ((r.stderr or "").strip().replace(chr(10), " ")[:110] or "sin stderr"))
            continue

        total = int(cabecera.split("|", 1)[1] or 0)
        filas = [l for l in salida if l.count("|") >= 4 and not l.startswith("TOTAL|")]
        if total == 0:
            ultimo = "el Programador dice que hay 0 tareas: eso es no haber podido mirar"
            continue
        if len(filas) != total:
            ultimo = (f"el Programador declara {total} tareas y solo se pudieron leer "
                      f"{len(filas)}: falta alguna por leer, no es que no existan")
            continue

        fuera = []
        for l in filas:
            nombre, accion, estado, ultima, resultado = l.split("|", 4)
            fuera.append({"nombre": nombre.strip(), "accion": accion.strip(),
                          "estado": estado.strip(), "ultima": ultima.strip(),
                          "resultado": resultado.strip()})
        return fuera

    raise FuenteRota(ultimo)


def _tareas_programadas() -> list[str]:
    """Las de la raíz cuya acción nombra un script. Falla en ROJO, nunca en «hay menos»."""
    return [f"tarea:{t['nombre']}" for t in tareas_detalladas()
            if any(ext in t["accion"].lower() for ext in _SCRIPTS)]


def _servicios() -> list[str]:
    """Los servicios de Windows que son tuyos: los que lanza Servy o corren desde `proyectos/`.

    El mismo criterio medido que las tareas —«lo escribiste tú»—, aplicado a servicios: los de
    Windows, NVIDIA o Adobe no corren con Servy ni desde tu carpeta. Y el mismo cuadre total contra
    detalle: un servicio que no se deja leer no puede desaparecer de la cuenta.
    """
    ps = ("$s = @(Get-CimInstance Win32_Service -ErrorAction Stop); 'TOTAL|' + $s.Count; "
          "foreach ($x in $s) { '{0}|{1}' -f $x.Name, $x.PathName }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=180)
    except Exception as e:  # noqa: BLE001
        raise FuenteRota(f"no se pudo preguntar a Windows por los servicios: {e}") from e
    salida = (r.stdout or "").splitlines()
    cabecera = next((l for l in salida if l.startswith("TOTAL|")), None)
    if cabecera is None:
        raise FuenteRota("Windows no dijo cuantos servicios hay: "
                         + ((r.stderr or "").strip().replace(chr(10), " ")[:110] or "sin stderr"))
    total = int(cabecera.split("|", 1)[1] or 0)
    filas = [l.split("|", 1) for l in salida if "|" in l and not l.startswith("TOTAL|")]
    if total == 0 or len(filas) != total:
        raise FuenteRota(f"Windows declara {total} servicios y se leyeron {len(filas)}")
    raiz = str(RAIZ_PROYECTOS).lower()
    return [f"servicio:{nombre.strip()}" for nombre, ruta in filas
            if "servy" in ruta.lower() or raiz in ruta.lower()]


def _repos() -> list[Path]:
    if not RAIZ_PROYECTOS.exists():
        raise FuenteRota(f"no existe {RAIZ_PROYECTOS}")
    return sorted(d for d in RAIZ_PROYECTOS.iterdir() if d.is_dir() and (d / ".git").exists())


def _tableros_de_la_ronda() -> list[str]:
    """Los tableros que la ronda EJECUTA, preguntandoselo a ella.

    Descubrirlos por mi cuenta daba dos algoritmos para una sola pregunta, y ya divergian: el mio
    se dejaba los de `ponerse_wenorro` y `pw-ralph` (viven en `backend/scripts/`) y metia cinco
    copias de JobHunter que la ronda excluye a proposito. Un tablero que nadie ejecuta solo no es
    un guardian: lo que arranca solo es la tarea `ronda-de-tableros`, y estos son su contenido —
    pero cada uno puede pudrirse por separado, asi que cada uno tiene ficha.
    """
    import importlib.util
    guion = Path(__file__).resolve().parent.parent / "ronda_de_tableros.py"
    if not guion.exists():
        raise FuenteRota(f"no existe {guion}")
    try:
        spec = importlib.util.spec_from_file_location("ronda_para_el_censo", str(guion))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        tableros = mod._TABLEROS
    except Exception as e:  # noqa: BLE001
        raise FuenteRota(f"no se pudo leer la lista de la ronda: {e}") from e
    if not tableros:
        raise FuenteRota("la ronda no declara ningun tablero")
    return [f"tablero:{nombre}" for nombre, _sub, _py in tableros]


def guardianes() -> tuple[list[str], list[str]]:
    """Todos los guardianes vivos, y las fuentes que no se pudieron enumerar."""
    ids: list[str] = []
    rotas: list[str] = []

    for fuente, fn in (
        ("settings de usuario", lambda: _hooks_de(SETTINGS_USUARIO, "usuario")),
        ("tareas programadas", _tareas_programadas),
        ("servicios", _servicios),
    ):
        try:
            ids += fn()
        except FuenteRota as e:
            rotas.append(f"{fuente}: {e}")

    try:
        for repo in _repos():
            ids += _hooks_de(repo / ".claude" / "settings.json", repo.name)
            if (repo / "hooks" / "pre-commit").exists() or (repo / ".git" / "hooks" / "pre-commit").exists():
                ids.append(f"pre-commit:{repo.name}")

    except FuenteRota as e:
        rotas.append(f"repos: {e}")

    try:
        ids += _tableros_de_la_ronda()
    except FuenteRota as e:
        rotas.append(f"tableros: {e}")

    return sorted(set(ids)), rotas


def existentes() -> tuple[set[str], list[str]]:
    """Lo que una ficha puede nombrar con derecho aunque el criterio no lo enumere.

    La IDA («¿todo lo vivo tiene ficha?») no basta: el 2026-10-16 el censo describía `eu-ralph` un
    mes después de su baja y dos tareas de JOB Assist tres días después de quitarlas, y nada se
    ponía rojo. Esta es la VUELTA: cada ficha tiene que nombrar algo que EXISTE hoy. «De más» sigue
    permitido —una tarea que ejecuta un binario (`OllamaServe`), una rutina de la app—, pero sólo
    si está; una ficha de algo que ya no existe es un guardián muerto con buena prensa.
    """
    ids: set[str] = set()
    rotas: list[str] = []
    try:
        ids |= {f"tarea:{t['nombre']}" for t in tareas_detalladas()}
    except FuenteRota as e:
        rotas.append(f"tareas programadas: {e}")
    if RUTINAS.is_dir():
        ids |= {f"rutina:{d.name}" for d in RUTINAS.iterdir() if (d / "SKILL.md").is_file()}
    return ids, rotas


def _fichas() -> dict[str, str]:
    """Identificador -> cuerpo de su ficha, del fichero del censo.

    Dos cosas que NO son fichas, y lo eran: lo que va entre vallas de código (el ejemplo del
    formato pasaba por la ficha real de `tarea:ralph-cn`, y borrar la de verdad no ponía nada
    rojo) y un encabezado de sección con comillas invertidas en medio.
    """
    if not CENSO.exists():
        return {}
    texto = CENSO.read_text(encoding="utf-8", errors="replace")
    fichas: dict[str, str] = {}
    actual = None
    cuerpo: list[str] = []
    en_valla = False
    for linea in texto.splitlines():
        if linea.lstrip().startswith("```"):
            en_valla = not en_valla
            continue
        if en_valla:
            continue
        if linea.startswith("## "):
            if actual:
                fichas[actual] = "\n".join(cuerpo)
            m = _CABECERA.match(linea)
            actual = m.group(1).strip() if m else None
            cuerpo = []
        elif actual:
            cuerpo.append(linea)
    if actual:
        fichas[actual] = "\n".join(cuerpo)
    return fichas


def _ficha_completa(cuerpo: str) -> str | None:
    """None si la ficha vale; si no, qué le falta."""
    if not re.search(r"\*\*Tipo:\*\*\s*\S", cuerpo):
        return "sin `**Tipo:**`"
    m = re.search(r"\*\*Si muere:\*\*(.*?)(?=\n\s*\n|\Z)", cuerpo, re.S)
    if not m:
        return "sin `**Si muere:**`"
    if len(m.group(1).strip()) < _MINIMO_SI_MUERE:
        return f"su `**Si muere:**` tiene menos de {_MINIMO_SI_MUERE} caracteres: no dice una consecuencia"
    return None


def censo_de_guardianes() -> tuple[bool, str]:
    vivos, rotas = guardianes()
    if rotas:
        return False, ("no se pudo enumerar (" + "; ".join(rotas)
                       + "). Una fuente que no contesta NO es una fuente sin guardianes.")
    if not vivos:
        return False, "0 guardianes enumerados: eso es no haber podido mirar, no una maquina limpia"

    extra, rotas_vuelta = existentes()
    if rotas_vuelta:
        return False, ("no se pudo comprobar que cada ficha nombre algo que existe ("
                       + "; ".join(rotas_vuelta) + ")")

    fichas = _fichas()
    faltan, flojas = [], []
    for gid in vivos:
        if gid not in fichas:
            faltan.append(gid)
        else:
            pega = _ficha_completa(fichas[gid])
            if pega:
                flojas.append(f"{gid} ({pega})")
    sobran = sorted(set(fichas) - set(vivos) - extra)

    if faltan or flojas or sobran:
        detalle = []
        if faltan:
            detalle.append(f"{len(faltan)} sin ficha: " + ", ".join(faltan[:4])
                           + (" ..." if len(faltan) > 4 else ""))
        if flojas:
            detalle.append(f"{len(flojas)} con ficha incompleta: " + ", ".join(flojas[:3])
                           + (" ..." if len(flojas) > 3 else ""))
        if sobran:
            detalle.append(f"{len(sobran)} fichas de algo que YA NO EXISTE: " + ", ".join(sobran[:4])
                           + (" ..." if len(sobran) > 4 else ""))
        return False, (f"{len(vivos) - len(faltan) - len(flojas)}/{len(vivos)} guardianes descritos en "
                       f"{CENSO.name}. " + " · ".join(detalle))

    return True, (f"los {len(vivos)} guardianes vivos tienen ficha, con su tipo y con lo que se rompe "
                  f"si mueren; y las {len(fichas)} fichas nombran algo que existe hoy")


if __name__ == "__main__":
    ok, msg = censo_de_guardianes()
    print(("VERDE: " if ok else "ROJO: ") + msg)
    sys.exit(0 if ok else 1)
