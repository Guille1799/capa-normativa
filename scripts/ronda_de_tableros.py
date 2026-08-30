"""La RONDA: corre los siete tableros de aceptación sin que nadie se acuerde de lanzarlos.

## Por qué existe (medido el 2026-08-23)

Ese día se hizo el censo de lo que corre solo en esta máquina. Corren solos: el `pre-commit` de
los cinco repos (en cada commit), los tres Ralph de madrugada (23:00 / 23:30 / 00:00) y
`ContextWatcher-Healthcheck` (cada 30 min). **Los siete tableros de aceptación completos no los
ejecutaba nadie.** Se corrían a mano, cuando alguien se acordaba.

> Un guarda que nadie ejecuta es decoración. Puede llevar semanas en rojo y nadie se entera,
> y entonces no protege de nada — sólo *parece* que protege, que es peor que no tenerlo.

Esto es el lanzador. Su trabajo es correr los siete —cada uno con su `--verifica`, que es quien
comprueba que los comprobadores siguen sabiendo ponerse rojos—, dejar un informe legible y **avisar
cuando algo CAMBIA de color**. Nada más: no arregla, no juzga, no interpreta.

    python scripts/ronda_de_tableros.py              # la ronda, a mano
    python scripts/ronda_de_tableros.py --programada # la ronda, desde la tarea de Windows
    python scripts/ronda_de_tableros.py --donde      # dónde deja los informes, sin correr nada

No lleva promesa propia: es la IMPLEMENTACIÓN de `tableros-corren-solos`, que vive en el tablero de
`capa-normativa`. Su veredicto lo da `veredicto()`, aquí abajo, que es una función pura para que se
la pueda comprobar dándole el mundo en vez de montándolo.

## Las cuatro decisiones que no son obvias

**1 · El registro se declara, y los huérfanos se denuncian.** Cuáles son «los tableros que
importan» es un juicio de G: en el disco hay doce `scripts/aceptacion.py` y sólo siete están en
la ronda (los otros cinco son clones de trabajo y experimentos, declarados abajo con su motivo).
Pero una lista escrita envejece en silencio — el día que nazca un tablero nuevo, la ronda seguiría
diciendo que están todos. Así que además de la lista hay un barrido del disco: **todo tablero que
no esté ni en `_TABLEROS` ni en `_NO_VIGILADOS` sale denunciado como huérfano** y pone la ronda en
falta. El andamio se retira solo: la lista no puede envejecer sin que grite.

**2 · El color viaja en un emoji, y un emoji se muere en una tubería.** Los tableros imprimen
`🟢`/`🔴`. Cuando se les captura la salida, Python escribe en la tubería con la codificación de la
consola (cp1252 aquí) y, como todos llaman a `reconfigure(errors="replace")`, **los dos círculos se
degradan al MISMO `?`**: verde y rojo dejan de distinguirse y la ronda contaría cero rojos sin
enterarse. Por eso se les fuerza `PYTHONIOENCODING=utf-8` al hijo. Y como confiar en que eso
funcione siempre es exactamente el error que este arnés persigue, el recuento se **contrasta contra
la línea de resumen del propio tablero** (`N/M promesas cumplidas.`). Si no cuadran, el tablero se
declara ILEGIBLE — nunca «cero rojos».

**3 · El exit code dice si la RONDA corrió, no si los tableros están verdes.** Si saliera 1 con
cada rojo, la tarea de Windows aparecería fallando para siempre y `LastTaskResult` dejaría de
significar nada. Los rojos son el DATO que la ronda recoge; que haya rojos es normal. Sale != 0
sólo cuando la ronda no pudo hacer su trabajo (cero tableros, no se pudo escribir el informe).

**4 · Se avisa en el CAMBIO de estado.** La lección es de esta misma casa y tiene número:
`inv-el-healthcheck-avisa-cada-30` midió 19 avisos idénticos en 19 corridas por UNA sola causa.
Avisar cada pasada por lo mismo entrena a ignorar los avisos, y entonces el aviso que importa
tampoco se lee. Aquí la firma es el conjunto de rojos; sólo se avisa cuando cambia, con un
recordatorio como mucho semanal si el rojo se enquista.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

#: La raíz donde viven los repos. Se deja sobrescribir por entorno porque es lo que hace los
#: tests posibles: sin esto, comprobar la ronda exigiría tener los siete repos de verdad.
RAIZ_PROYECTOS = Path(os.environ.get("RONDA_PROYECTOS") or Path.home() / "proyectos")

#: Los informes NO van dentro de ningún repo de proyecto: la ronda es de la máquina, no de
#: `capa-normativa`. Van a `proyectos/.rondas/`, que se autoignora con su propio `.gitignore`.
CARPETA_RONDAS = Path(os.environ.get("RONDA_INFORMES", str(RAIZ_PROYECTOS / ".rondas")))

#: El nombre de la tarea de Windows. Lo lee el comprobador para exigir EVIDENCIA DE ARRANQUE.
TAREA = "ronda-de-tableros"

#: Cuántas horas puede tener el último informe antes de que la promesa se ponga roja. La ronda es
#: diaria, así que 48 h tolera UNA ausencia (portátil apagado un día entero) y grita a la segunda.
#: Más apretado produciría rojos falsos, y un rojo falso al día es cómo se aprende a ignorar.
VENTANA_H = 48

#: Cuántos tableros tiene que haber corrido la ronda para que valga. Es un SUELO, no un adorno:
#: sin él, una ronda que descubre cero tableros escribe «0 rojos» y saldría verde. Aprobar en
#: vacío es el modo de fallo más caro de un guarda, porque su silencio se lee como buenas noticias.
SUELO_TABLEROS = 8

#: Tiempo máximo por tablero. El de `capa-normativa` corre doce nodos de pytest, así que hay que
#: ser generoso; pero un tablero colgado no puede secuestrar la ronda entera.
TIMEOUT_TABLERO_S = 45 * 60

#: Tiempo máximo del `--verifica` de un tablero. Menos que el tablero entero: la mutación corre
#: cada comprobador hasta tres veces, pero sólo los que NO están declarados no-mutables.
TIMEOUT_VERIFICA_S = 30 * 60

#: Cada cuánto se REPITE el aviso de un rojo que no cambia. Semanal: lo justo para que un rojo
#: enquistado no desaparezca del todo, lo bastante espaciado para que no sea ruido.
RECORDATORIO_S = 7 * 24 * 3600

VERDE, ROJO, CUMPLIDA = chr(0x1F7E2), chr(0x1F534), chr(0x2705)

#: La tercera casilla del tablero, estrenada el 2026-08-30: «no he podido mirar». Aqui hace
#: falta por una razon que no se ve a simple vista: `leer_tablero` CONTRASTA los emojis contados
#: contra la linea de resumen, y sin conocer esta marca contaria 1 verde + 0 rojos contra un
#: total de 2 y declararia el tablero ILEGIBLE. O sea que el tablero aprende a hablar y la ronda
#: se queda sorda: hay que ensenarsela a las dos a la vez.
MUDO = chr(0x26AA)

#: `(nombre, subruta desde la raíz, intérprete relativo o None para el `python` del PATH)`.
#: Los comandos son LITERALMENTE los que G documentó; si uno cambia, cambia aquí y en ningún
#: otro sitio.
_TABLEROS = (
    ("capa-normativa", "capa-normativa", None),
    ("cn-ralph", "cn-ralph", None),
    ("eu-ralph", "eu-ralph", None),
    ("mcp-ralph", "mcp-ralph", None),
    ("mcp_smart_context", "mcp_smart_context", "venv/Scripts/python.exe"),
    ("ponerse_wenorro", "ponerse_wenorro/backend", "venv/Scripts/python.exe"),
    ("pw-ralph", "pw-ralph/backend", "venv/Scripts/python.exe"),
    # Anadido el 2026-08-26. Faltaba, y no era inocuo: `jh-ralph` lleva corriendo cada
    # noche a las 02:00 desde hace dias, con 8 comprobadores propios que NADIE miraba.
    # Se declara el worktree del BUCLE, no el checkout humano, igual que `eu-ralph` y
    # `pw-ralph`. Sin interprete propio: `jh-ralph` no tiene venv.
    ("jh-ralph", "jh-ralph", None),
)

#: Repos enteros que quedan fuera de la ronda, **con todos sus worktrees**. Se excluye por REPO y
#: no por carpeta, y la diferencia se midió el 2026-08-23: la primera versión excluía las cuatro
#: carpetas `JobHunter-*` que había, y ocho minutos después nació `JobHunter-herramienta` — un
#: worktree más, con su tablero dentro — y la ronda lo denunció como huérfano. Excluir por nombre
#: de carpeta habría producido un rojo falso cada vez que alguien abre una rama de trabajo, y un
#: rojo falso recurrente es exactamente cómo se aprende a ignorar los avisos.
_REPOS_NO_VIGILADOS = {
    "JobHunter": ("su tablero lo corre `jh-ralph`, que es el worktree del bucle y el que entra "
                  "en la ronda — igual que `eu-ralph` y `pw-ralph`. El REPO sigue excluido para "
                  "que los `JobHunter-*` que G abre a menudo (5 el 2026-08-23) no salgan como "
                  "huérfanos; declarar un tablero no choca con excluir su repo, porque "
                  "`vigilados` sale de _TABLEROS sin consultar esta lista y el barrido de "
                  "huérfanos salta lo declarado. ⚠️ El motivo anterior decía «proyecto sin bucle "
                  "ni Ralph vigilándolo» y era FALSO desde que nació `ralph_jh.cmd`: la frase "
                  "sobrevivió al hecho. Medido el 2026-08-26 — tarea programada `ralph-jh` a las "
                  "02:00, 7 commits esa noche, MAX=6 con racha segura CERO, y ninguna de las tres "
                  "guardas mirándolo."),
}

#: Carpetas sueltas que quedan fuera aunque su repo SÍ esté vigilado por otra carpeta. Aquí no
#: vale excluir el repo entero cuando dos worktrees del mismo repo tienen tablero y sólo uno debe
#: entrar en la ronda.
#:
#: VACÍA desde el 2026-08-30, y el motivo merece quedarse escrito porque la exclusión que vivía
#: aquí dejó de tener sentido sin que nadie la tocara.
#:
#: Excluía `eu-political-observatory` —el checkout humano— porque su tablero lo corría `eu-ralph`,
#: el worktree del bucle, y meter los dos habría contado cada rojo dos veces.
#:
#: El 2026-08-29 otra sesión sacó del repo PÚBLICO de eu todo el arnés de trabajo: los cuatro
#: subagentes, los hooks, las skills, `settings.json` y `scripts/` entero, y metió el LICENSE. Es
#: la regla del escaparate aplicada a fondo, y está bien. Pero con eso el checkout humano de eu
#: dejó de tener tablero — así que ya no hay nada que excluir, y la exclusión pasó a ser un
#: FANTASMA: una excepción que protege algo que no existe y despista a quien la lea.
#:
#: Lo cazó `test_los_excluidos_declarados_existen_de_verdad`, que existe exactamente para esto.
_CARPETAS_NO_VIGILADAS: dict[str, str] = {}


# ── descubrir ────────────────────────────────────────────────────────────────────────────────

def _clave(sub: str) -> str:
    """La carpeta de primer nivel de una subruta: `ponerse_wenorro/backend` -> `ponerse_wenorro`.

    Los tableros se declaran y se excluyen POR PROYECTO, no por ruta exacta, porque dos de ellos
    viven en `<proyecto>/backend` y nadie debería tener que acordarse de eso al excluir.
    """
    return sub.replace(chr(92), "/").split("/")[0]


def tableros_en_disco(raiz: Path) -> list[str]:
    """Toda subruta bajo `raiz` que tenga un `scripts/aceptacion.py`, a uno o dos niveles.

    Se mira el disco en vez de fiarse de la lista, que es el punto entero: la lista dice lo que
    creemos que hay, el disco dice lo que hay.
    """
    hallados = []
    for patron in ("*/scripts/aceptacion.py", "*/*/scripts/aceptacion.py"):
        for p in sorted(raiz.glob(patron)):
            hallados.append(str(p.parent.parent.relative_to(raiz)).replace(chr(92), "/"))
    # Un mismo proyecto puede aparecer dos veces (raíz y backend); se conserva el orden y se
    # quitan los repetidos sin usar `set`, para que el informe salga siempre igual.
    vistos, unicos = set(), []
    for h in hallados:
        if h not in vistos:
            vistos.add(h)
            unicos.append(h)
    return unicos


def repo_de(carpeta: Path) -> str:
    """El nombre del repo al que pertenece esta carpeta, preguntándoselo a git.

    Se pregunta en vez de deducirlo del nombre, por la misma razón que `arboles_hermanos`:
    `pw-ralph` y `ponerse_wenorro` no se parecen en nada y son el mismo repo, y dos carpetas que
    se parezcan mucho pueden no serlo. `--git-common-dir` es el que contesta lo mismo desde un
    worktree y desde el árbol principal, que es justo lo que hace falta aquí.

    Si git no contesta —no es un repo, no está instalado—, el nombre de la carpeta hace de
    identidad. Degradar así es correcto: en el peor caso una exclusión por repo no aplica y la
    carpeta sale denunciada como huérfana, que es el lado seguro del error.
    """
    try:
        r = subprocess.run(["git", "-C", str(carpeta), "rev-parse", "--path-format=absolute",
                            "--git-common-dir"], capture_output=True, timeout=60)
        if r.returncode == 0:
            comun = r.stdout.decode("utf-8", "replace").strip()
            if comun:
                return Path(comun).parent.name
    except Exception:
        pass
    return carpeta.name


def descubrir(raiz: Path = None) -> tuple[list[dict], list[str], list[str]]:
    """`(vigilados, ausentes, huerfanos)`.

    · *vigilados*: los declarados que SÍ están en el disco, listos para correr.
    · *ausentes*: declarados que ya no están. Un tablero que desaparece es una noticia.
    · *huerfanos*: tableros en el disco que nadie ha declarado ni excluido. La lista no puede
      envejecer en silencio: cualquiera nuevo obliga a decidir.
    """
    raiz = raiz or RAIZ_PROYECTOS
    en_disco = tableros_en_disco(raiz)
    vigilados, ausentes = [], []
    for nombre, sub, interprete in _TABLEROS:
        guion = raiz / sub / "scripts" / "aceptacion.py"
        if not guion.exists():
            ausentes.append(nombre + " (" + sub + ")")
            continue
        vigilados.append({"nombre": nombre, "sub": sub, "interprete": interprete,
                          "cwd": raiz / sub})
    declarados = {_clave(sub) for _, sub, _ in _TABLEROS}
    huerfanos = [d for d in en_disco
                 if _clave(d) not in declarados
                 and _clave(d) not in _CARPETAS_NO_VIGILADAS
                 and repo_de(raiz / d) not in _REPOS_NO_VIGILADOS]
    return vigilados, ausentes, huerfanos


def _interprete_de(t: dict) -> tuple[str, str | None]:
    """El ejecutable con el que se corre este tablero, y el motivo si no se puede."""
    if t["interprete"]:
        exe = t["cwd"] / t["interprete"]
        if not exe.exists():
            return "", "no existe su intérprete: " + str(exe)
        return str(exe), None
    # `python` del PATH, que es lo que dice el comando documentado. NO se usa `sys.executable`:
    # si la ronda se lanzara desde el venv de otro proyecto, los tableros heredarían un
    # `capa_normativa` INSTALADO y viejo tapando al fuente — el fallo nº 2 de `arbol_propio`.
    exe = shutil.which("python")
    if not exe:
        return "", "no hay `python` en el PATH"
    return exe, None


# ── leer la salida de un tablero ─────────────────────────────────────────────────────────────

_RESUMEN = re.compile(r"(\d+)\s*/\s*(\d+)\s+promesas cumplidas")
#: La coleta que el tablero anade cuando hay mudos. Se contrasta igual que el resto: si el
#: tablero dice que hay 3 sin medir y solo se han contado 2, la salida no es fiable.
_RESUMEN_MUDOS = re.compile(r"(\d+)\s+sin poder medirse")


def leer_tablero(salida: str) -> dict:
    """Convierte la salida de un tablero en `{verdes, rojos, cumplidas, legible, porque}`.

    ⚠️ El contraste contra la línea de resumen es la mitad del valor. Los marcadores son emojis y
    un emoji sobrevive o no según la codificación de la tubería; si un día deja de sobrevivir,
    esta función contaría cero de todo y la ronda diría «ningún rojo», que es la mentira exacta
    que un guarda no puede permitirse. Con el contraste, ese día dice ILEGIBLE.
    """
    verdes, rojos, cumplidas, mudos = [], [], [], []
    for linea in salida.splitlines():
        t = linea.strip()
        if not t:
            continue
        marca, resto = t[0], t[1:].strip()
        destino = {VERDE: verdes, ROJO: rojos, CUMPLIDA: cumplidas, MUDO: mudos}.get(marca)
        if destino is None:
            continue
        destino.append(resto.split(None, 1)[0] if resto else "(sin nombre)")
    m = _RESUMEN.search(salida)
    if not m:
        return {"verdes": verdes, "rojos": rojos, "cumplidas": cumplidas, "mudos": mudos, "legible": False,
                "porque": "el tablero no imprimio su linea de resumen «N/M promesas cumplidas»"}
    dice_verdes, dice_total = int(m.group(1)), int(m.group(2))
    dice_mudos = int(m2.group(1)) if (m2 := _RESUMEN_MUDOS.search(salida)) else 0
    if (len(verdes) != dice_verdes or len(mudos) != dice_mudos
            or len(verdes) + len(rojos) + len(mudos) != dice_total):
        return {"verdes": verdes, "rojos": rojos, "cumplidas": cumplidas, "mudos": mudos, "legible": False,
                "porque": ("el recuento no cuadra con el resumen del tablero: contados "
                           + str(len(verdes)) + " verdes y " + str(len(rojos)) + " rojos y " + str(len(mudos)) + " mudos, el "
                           "tablero dice " + str(dice_verdes) + "/" + str(dice_total) + " y " + str(dice_mudos) + " mudos"
                           + ". Casi seguro que los emojis no sobrevivieron a la tuberia")}
    return {"verdes": verdes, "rojos": rojos, "cumplidas": cumplidas, "mudos": mudos, "legible": True,
            "porque": ""}



#: Cuantos DIAS DISTINTOS con ronda puede un vigilante no conseguir medir antes de que el mudo se
#: convierta en rojo. Decidido por G el 2026-08-30, y la parte importante es el denominador:
#:
#:   > «2 dias, pero que esos dias se haya trabajado — si no, en un finde que no curre va a saltar»
#:
#: Y tenia razon. La primera version contaba TIEMPO TRANSCURRIDO desde la ultima medicion buena, y
#: con eso un fin de semana sin rondas hacia que el lunes, al primer tropiezo, el contador ya
#: marcara tres dias y saltara la alarma. El vigilante no habia fallado dos veces: le habian
#: preguntado una. Contar ocasiones en las que DE VERDAD se le pregunto es lo unico honesto.
DIAS_MUDO_HASTA_ROJO = 2


def escalar_mudos(historial: dict, tablero: str, mudos: list, medidos: list,
                  dia: str) -> tuple[dict, list]:
    """Actualiza la memoria de mudos y devuelve los que ya son ROJO por vigilante muerto.

    Un mudo suelto es normal: la maquina iba ahogada. Un mudo que INSISTE es otra cosa, y el rojo
    que devuelve esta funcion no acusa a la promesa vigilada sino AL VIGILANTE: uno que nunca
    consigue medir esta muerto aunque jamas haya dicho una mentira.

    Tres decisiones que valen mas que el codigo:

    · **Solo cuentan dias en los que la ronda corrio**, porque esta funcion solo se llama entonces.
      Un finde sin rondas no gasta paciencia.
    · **Varias rondas del mismo dia cuentan como una.** Correr la ronda a mano tres veces seguidas
      no puede matar a un vigilante en diez minutos.
    · **Lo resetea CUALQUIER medicion conseguida, incluido un ROJO.** Un rojo significa que si
      consiguio mirar, que es exactamente lo que aqui se estaba poniendo en duda. Confundir «mide y
      dice que mal» con «no consigue medir» seria repetir el error que abrio todo esto.
    """
    h = dict(historial)
    for nombre in medidos:                       # midio: se le perdona todo lo anterior
        h.pop(tablero + "::" + nombre, None)
    muertos = []
    for nombre in mudos:
        clave = tablero + "::" + nombre
        dias = sorted(set(h.get(clave, []) + [dia]))
        h[clave] = dias
        if len(dias) >= DIAS_MUDO_HASTA_ROJO:
            muertos.append(nombre)
    return h, muertos




def aplicar_mudos(resultados: list, memoria_f, dia: str) -> dict:
    """Escala los mudos de cada tablero, MUTA sus fichas y guarda la memoria. Devuelve la memoria.

    Vive fuera de `main` para poder atacarla: enterrada dentro, la unica forma de probarla seria
    correr la ronda entera —nueve minutos y ocho repos— y entonces no se probaria nunca. Un trozo
    de logica que solo se puede ejercitar de esa manera es un trozo de logica sin probar.

    La memoria vive en su propio fichero y NO en `aviso.json` a proposito: si se corrompe se
    pierde la cuenta de los mudos, pero no el aviso de rojos, que es lo que no puede fallar.
    Por eso tambien se lee y se escribe a prueba de balas — un fichero de memoria ilegible
    equivale a empezar la cuenta de cero, nunca a tumbar la ronda.
    """
    try:
        memoria = json.loads(memoria_f.read_text(encoding="utf-8"))
        if not isinstance(memoria, dict):
            memoria = {}
    except (OSError, ValueError):
        memoria = {}

    for ficha in resultados:
        mudos = ficha.get("mudos") or []
        memoria, muertos = escalar_mudos(memoria, ficha["nombre"], mudos,
                                         ficha.get("medidos") or [], dia)
        if not muertos:
            continue
        # Pasan a ROJO por la puerta de delante: entran en `rojos`, cambian la firma y avisan
        # como cualquier otro. Pero la acusacion NO es sobre la promesa vigilada sino sobre el
        # VIGILANTE, asi que se guardan aparte para poder decirlo con esas palabras en el informe.
        ficha["muertos"] = muertos
        ficha["rojos"] = list(ficha["rojos"]) + [m for m in muertos if m not in ficha["rojos"]]
        ficha["mudos"] = [m for m in mudos if m not in muertos]

    try:
        memoria_f.parent.mkdir(parents=True, exist_ok=True)
        memoria_f.write_text(json.dumps(memoria, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return memoria


# ── correr ───────────────────────────────────────────────────────────────────────────────────

def _entorno_limpio() -> dict:
    """El entorno con el que se arranca a un tablero: emojis vivos y sin git heredado."""
    entorno = dict(os.environ)
    # Sin esto los dos círculos se degradan al mismo `?` y el color se pierde. Ver el docstring
    # del módulo, decisión 2.
    entorno["PYTHONIOENCODING"] = "utf-8"
    entorno["PYTHONUTF8"] = "1"
    # Un `GIT_DIR` heredado ya secuestró una vez a los detectores (commit d216e5e): escanearon
    # otro repo, no encontraron nada y declararon todo limpio. La ronda arranca a los hijos sin
    # las variables de git que pueda traer puestas quien la lance.
    for fuga in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        entorno.pop(fuga, None)
    return entorno


def correr_verifica(t: dict, exe: str) -> dict:
    """El `--verifica` del tablero: la prueba por mutación de sus propios comprobadores.

    ⚠️ Se recoge su resultado, pero **no manda sobre el veredicto de la promesa**, y la distinción
    importa. `--verifica` puede salir 1 porque un comprobador de OTRO repo se ha estropeado, y eso
    no dice nada sobre si la ronda corre sola. Convertir un rojo ajeno en rojo propio es el fallo
    que el 2026-08-22 dejó cinco tareas imposibles de cerrar.

    Lo que sí exige la promesa es que **haya corrido**. Y si su resultado cambia —empieza a fallar
    donde antes pasaba—, eso entra en la firma del aviso, que es el canal correcto: se avisa del
    cambio, no se bloquea un tablero ajeno.
    """
    t0 = time.monotonic()
    try:
        r = subprocess.run([exe, "scripts/aceptacion.py", "--verifica"], cwd=str(t["cwd"]),
                           env=_entorno_limpio(), capture_output=True,
                           timeout=TIMEOUT_VERIFICA_S)
    except subprocess.TimeoutExpired:
        return {"exit": None, "duracion_s": round(time.monotonic() - t0, 1),
                "resumen": "se cuelga (>" + str(TIMEOUT_VERIFICA_S // 60) + " min)"}
    except OSError as e:
        return {"exit": None, "duracion_s": round(time.monotonic() - t0, 1),
                "resumen": "no se pudo arrancar: " + type(e).__name__}
    lineas = [l.strip() for l in (r.stdout + r.stderr).decode("utf-8", "replace").splitlines()
              if l.strip()]
    # La línea que resume («N/M verificados por mutación») si está; si no, la última que haya.
    resumen = next((l for l in reversed(lineas) if "verificados por mutaci" in l),
                   lineas[-1] if lineas else "sin salida")
    return {"exit": r.returncode, "duracion_s": round(time.monotonic() - t0, 1),
            "resumen": resumen[:150]}


def correr_tablero(t: dict) -> dict:
    """Corre UN tablero y su `--verifica`. Nunca lanza: un tablero roto es un dato, no un crash."""
    exe, problema = _interprete_de(t)
    base = {"nombre": t["nombre"], "sub": t["sub"], "interprete": exe}
    sin_verifica = {"exit": None, "duracion_s": 0.0, "resumen": "no se llego a correr"}
    if problema:
        return dict(base, estado="caido", verdes=0, rojos=[], cumplidas=[], exit=None,
                    duracion_s=0.0, detalle=problema, verifica=sin_verifica)
    entorno = _entorno_limpio()
    t0 = time.monotonic()
    try:
        r = subprocess.run([exe, "scripts/aceptacion.py"], cwd=str(t["cwd"]), env=entorno,
                           capture_output=True, timeout=TIMEOUT_TABLERO_S)
    except subprocess.TimeoutExpired:
        return dict(base, estado="caido", verdes=0, rojos=[], cumplidas=[], exit=None,
                    duracion_s=round(time.monotonic() - t0, 1), verifica=sin_verifica,
                    detalle="se cuelga (>" + str(TIMEOUT_TABLERO_S // 60) + " min)")
    except OSError as e:
        return dict(base, estado="caido", verdes=0, rojos=[], cumplidas=[], exit=None,
                    duracion_s=round(time.monotonic() - t0, 1), verifica=sin_verifica,
                    detalle="no se pudo arrancar: " + type(e).__name__ + ": " + str(e)[:120])
    tardo = round(time.monotonic() - t0, 1)
    salida = r.stdout.decode("utf-8", "replace")
    err = r.stderr.decode("utf-8", "replace").strip()
    lectura = leer_tablero(salida)
    # El `--verifica` se corre aunque el tablero haya salido ilegible: que su salida no se
    # entienda no impide preguntarle si sus comprobadores siguen sabiendo ponerse rojos, y son
    # dos averías distintas que conviene no confundir en una sola.
    verifica = correr_verifica(t, exe)
    if not lectura["legible"]:
        cola = (err or salida).strip().splitlines()
        return dict(base, estado="ilegible", verdes=len(lectura["verdes"]),
                    rojos=lectura["rojos"], cumplidas=lectura["cumplidas"], exit=r.returncode,
                    duracion_s=tardo, verifica=verifica,
                    detalle=lectura["porque"] + (" | ultima linea: " + cola[-1][:120]
                                                 if cola else ""))
    return dict(base, estado="ok", verdes=len(lectura["verdes"]), rojos=lectura["rojos"],
                cumplidas=lectura["cumplidas"], exit=r.returncode, duracion_s=tardo,
                verifica=verifica, detalle=(err.splitlines()[-1][:120] if err else ""),
                mudos=lectura.get("mudos", []),
                medidos=lectura["verdes"] + lectura["rojos"])


def leer_nombrados(salida: str, pedidos: list[str]) -> dict | None:
    """Los rojos de una corrida `aceptacion.py <n1> <n2>`, o `None` si la salida no es fiable.

    ⚠️ Aquí NO hay línea de resumen: el tablero solo la imprime cuando se le llama sin argumentos.
    La invariante equivalente es que salga **un veredicto por cada nombre pedido**. Si no cuadra,
    se devuelve `None` — y quien llama conserva el rojo. En la duda se conserva la alarma: tragarse
    un rojo de verdad es mucho más caro que dar uno de más.
    """
    veredictos = {}
    for linea in salida.splitlines():
        t = linea.strip()
        if not t or t[0] not in (VERDE, ROJO):
            continue
        resto = t[1:].strip()
        if resto:
            veredictos[resto.split(None, 1)[0]] = (t[0] == ROJO)
    if set(veredictos) != set(pedidos):
        return None
    return veredictos


def reconfirmar(t: dict, exe: str, nombres: list[str]) -> tuple[list[str], list[str]]:
    """Vuelve a preguntar por unos rojos concretos. Devuelve `(confirmados, inestables)`.

    ## Por qué existe (medido el 2026-08-23, la primera vez que la tarea corrió de verdad)

    La ronda avisó de cuatro rojos nuevos —`canario-de-los-hooks` y tres hermanos suyos— y al
    volver a preguntar por ellos, con la máquina tranquila, **estaban verdes**. No había ningún
    rojo: los tumbó la carga. Correr siete tableros seguidos carga la máquina, y hay
    comprobadores que interrogan procesos con timeout y se caen si el equipo va justo.

    Un guarda que da falsas alarmas es peor que uno silencioso, porque enseña a no mirarlo — es la
    misma lección de `inv-el-healthcheck-avisa-cada-30` entrando por otra puerta. Así que **un
    rojo NUEVO no se cree a la primera**: se le vuelve a preguntar, a él solo, y solo se avisa de
    los que insisten.

    Sale barato justamente porque se pregunta solo por lo nuevo, que casi siempre son cero.

    Y los que NO se reconfirman no se tiran a la basura: van al informe como `inestables`, que es
    un hallazgo por sí mismo — un comprobador que cambia de color según la carga está roto aunque
    su promesa esté bien.
    """
    if not nombres:
        return [], []
    try:
        r = subprocess.run([exe, "scripts/aceptacion.py", *nombres], cwd=str(t["cwd"]),
                           env=_entorno_limpio(), capture_output=True,
                           timeout=TIMEOUT_TABLERO_S)
    except (subprocess.TimeoutExpired, OSError):
        return list(nombres), []       # sin respuesta se conserva la alarma
    veredictos = leer_nombrados(r.stdout.decode("utf-8", "replace"), nombres)
    if veredictos is None:
        return list(nombres), []       # salida no fiable: se conserva la alarma
    return ([n for n in nombres if veredictos[n]],
            [n for n in nombres if not veredictos[n]])


# ── comparar con la pasada anterior ──────────────────────────────────────────────────────────

def leer_ultimo(carpeta: Path = None) -> dict | None:
    """El informe de la pasada anterior, o `None` si no hay o está ilegible."""
    f = (carpeta or CARPETA_RONDAS) / "ultima.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


def comparar(actual: list[dict], previo: dict | None) -> tuple[dict, dict]:
    """`(nuevos_rojos, resueltos)` por tablero. Lo NUEVO es lo que importa de un informe.

    Sin previo, todo rojo es nuevo — y está bien que lo sea: la primera ronda es, literalmente, la
    primera vez que alguien mira.
    """
    antes = {}
    for t in (previo or {}).get("tableros", []):
        antes[t.get("nombre")] = set(t.get("rojos", []))
    nuevos, resueltos = {}, {}
    for t in actual:
        ya = antes.get(t["nombre"])
        ahora = set(t.get("rojos", []))
        if ya is None:
            if ahora:
                nuevos[t["nombre"]] = sorted(ahora)
            continue
        if ahora - ya:
            nuevos[t["nombre"]] = sorted(ahora - ya)
        if ya - ahora:
            resueltos[t["nombre"]] = sorted(ya - ahora)
    return nuevos, resueltos


# ── avisar: SÓLO en el cambio de estado ──────────────────────────────────────────────────────

def firma(tableros: list[dict], huerfanos: list[str], ausentes: list[str]) -> str:
    """El estado del mundo, reducido a una cadena comparable.

    Van los NOMBRES de los rojos, no su número: pasar de tres rojos a otros tres distintos es un
    cambio de estado, y contarlos no lo vería.

    Y va el resultado de `--verifica`, que es el único canal por el que se entera nadie de que la
    prueba por mutación de un tablero ha empezado a fallar. Bloquear una promesa por eso sería
    importar un rojo ajeno; avisar del cambio es lo correcto.
    """
    piezas = [t["nombre"] + "=" + t["estado"]
              + ":" + ",".join(sorted(t.get("rojos", [])))
              + ":v" + str((t.get("verifica") or {}).get("exit"))
              for t in sorted(tableros, key=lambda x: x["nombre"])]
    return " | ".join(piezas + ["huerfanos:" + ",".join(sorted(huerfanos)),
                                "ausentes:" + ",".join(sorted(ausentes))])


#: Lo que de verdad cabe en un globo de Windows antes de que lo corte. Se deja corto a propósito:
#: el globo desaparece solo, así que lo que no quepa hay que ir a buscarlo al informe igualmente.
_CABE_EN_EL_GLOBO = 3


def cuerpo_del_aviso(nuevos: dict, carpeta: Path) -> str:
    """El texto del globo cuando hay rojos nuevos. Corto, accionable, y siempre con la ruta.

    ⚠️ Escrito el 2026-08-23 después de preguntarle a G si había visto alguna vez un globo del
    healthcheck. Sí los había visto, y su recuerdo fue literalmente **«ponía fallo sin más»**.

    Eso es la avería que importa, y no es el canal: el globo llega, y lo que no sirve es lo que
    lleva dentro. Un aviso que no dice QUÉ ni DÓNDE MIRAR no se puede accionar, así que se ignora
    — y entonces da igual que el canal funcione.

    Dos reglas, las dos sacadas de ese «fallo sin más»:

      · con pocos rojos nuevos se dicen POR SU NOMBRE, que es lo accionable;
      · con muchos no se intenta caber —se cortaría a mitad de palabra— y se dan la cuenta y los
        tableros, que es lo que orienta.

    Y en los dos casos va la ruta del informe, porque el globo se va solo de la pantalla y el
    informe no.
    """
    cuantos = sum(len(v) for v in nuevos.values())
    donde = str(carpeta / "ULTIMA.md")
    if cuantos <= _CABE_EN_EL_GLOBO:
        detalle = "; ".join(k + ": " + ", ".join(v) for k, v in sorted(nuevos.items()))
    else:
        detalle = (str(cuantos) + " en " + str(len(nuevos)) + " tablero(s): "
                   + ", ".join(sorted(nuevos)))
    return detalle + " -- detalle en " + donde


def _toast(titulo: str, mensaje: str) -> bool:
    """Globo de Windows, igual que el healthcheck. Devuelve si se pudo lanzar."""
    limpio = mensaje.replace("'", "").replace(chr(10), " - ")[:230]
    tit = titulo.replace("'", "")[:60]
    ps = ("Add-Type -AssemblyName System.Windows.Forms; "
          "$n = New-Object System.Windows.Forms.NotifyIcon; "
          "$n.Icon = [System.Drawing.SystemIcons]::Warning; $n.Visible = $true; "
          "$n.ShowBalloonTip(10000, '" + tit + "', '" + limpio
          + "', [System.Windows.Forms.ToolTipIcon]::Warning); Start-Sleep -Seconds 11; "
          "$n.Dispose()")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


def decidir_aviso(nueva: str, estado: dict | None, ahora_ts: float) -> tuple[bool, str]:
    """`(avisar, motivo)`. La regla entera de cuándo se molesta a alguien, aislada y comprobable.

    ⚠️ Esta función es la lección de `inv-el-healthcheck-avisa-cada-30` hecha código: aquel
    healthcheck emitió 19 avisos en 19 corridas por UNA causa que no cambiaba. Avisar por lo
    mismo cada pasada no informa, entrena a ignorar.
    """
    if estado is None or "firma" not in estado:
        return True, "primera ronda con estado: no habia nada con lo que comparar"
    if estado["firma"] != nueva:
        return True, "el estado CAMBIO respecto a la ronda anterior"
    if ahora_ts - float(estado.get("ts", 0)) > RECORDATORIO_S:
        return True, "misma causa, pero lleva mas de una semana sin recordarse"
    return False, "misma causa que el ultimo aviso y aun dentro del recordatorio semanal"


def avisar(tableros: list[dict], nuevos: dict, resueltos: dict, huerfanos: list[str],
           ausentes: list[str], carpeta: Path) -> str:
    """Aplica `decidir_aviso` y, si toca, lanza el globo. Devuelve qué se hizo, para el informe."""
    f = firma(tableros, huerfanos, ausentes)
    estado_f = carpeta / "aviso.json"
    try:
        estado = json.loads(estado_f.read_text(encoding="utf-8"))
    except Exception:
        estado = None
    ahora_ts = time.time()
    toca, motivo = decidir_aviso(f, estado, ahora_ts)
    if not toca:
        return "omitido: " + motivo
    rotos = [t for t in tableros if t["estado"] != "ok"]
    total_rojos = sum(len(t.get("rojos", [])) for t in tableros)
    donde = " -- detalle en " + str(carpeta / "ULTIMA.md")
    if nuevos:
        cuantos = sum(len(v) for v in nuevos.values())
        titulo = "Tableros de aceptacion - " + str(cuantos) + " ROJO(S) NUEVO(S)"
        cuerpo = cuerpo_del_aviso(nuevos, carpeta)
    elif rotos or huerfanos or ausentes:
        titulo = "Tableros de aceptacion - la ronda NO pudo mirarlo todo"
        cuerpo = ("no se pudieron leer: " + (", ".join(t["nombre"] for t in rotos) or "ninguno")
                  + " | sin vigilar: " + (", ".join(huerfanos + ausentes) or "ninguno") + donde)
    elif resueltos and total_rojos == 0:
        titulo = "Tableros de aceptacion - TODO VERDE"
        cuerpo = "se cerro el ultimo rojo" + donde
    else:
        mal = [t["nombre"] for t in tableros if (t.get("verifica") or {}).get("exit") not in (0,)]
        titulo = "Tableros de aceptacion - cambio de estado"
        cuerpo = (str(total_rojos) + " rojo(s) en total, se cerraron "
                  + str(sum(len(v) for v in resueltos.values()))
                  + ("" if not mal else "; --verifica falla en " + ", ".join(mal)) + donde)
    lanzado = _toast(titulo, cuerpo)
    try:
        estado_f.parent.mkdir(parents=True, exist_ok=True)
        estado_f.write_text(json.dumps({"firma": f, "ts": ahora_ts, "titulo": titulo}),
                            encoding="utf-8")
    except OSError:
        pass
    return ("enviado (" + motivo + "): " + titulo) if lanzado else (
        "NO se pudo enviar el globo (" + motivo + "): " + titulo)


# ── el informe ───────────────────────────────────────────────────────────────────────────────

def _md(informe: dict) -> str:
    L = []
    ap = L.append
    ap("# Ronda de tableros — " + informe["terminado"][:16].replace("T", " "))
    ap("")
    ap("Lanzada por: **" + informe["lanzador"] + "** · duró "
       + str(round(informe["duracion_s"] / 60, 1)) + " min · "
       + str(informe["corridos"]) + " de " + str(informe["declarados"]) + " tableros.")
    ap("")
    nuevos = informe.get("nuevos_rojos") or {}
    ap("## Lo nuevo")
    ap("")
    if not nuevos:
        ap("Ningún rojo nuevo respecto a la ronda anterior.")
    else:
        for tab, cuales in sorted(nuevos.items()):
            ap("- 🔴 **" + tab + "** — " + ", ".join(cuales))
    resueltos = informe.get("resueltos") or {}
    if resueltos:
        ap("")
        for tab, cuales in sorted(resueltos.items()):
            ap("- 🟢 **" + tab + "** — se cerró: " + ", ".join(cuales))
    inestables = informe.get("inestables") or {}
    if inestables:
        ap("")
        ap("### ⚠️ Salieron rojos y al repreguntar estaban verdes")
        ap("")
        ap("No se ha avisado de éstos. Un comprobador que cambia de color según la carga de la "
           "máquina está roto aunque su promesa esté bien, así que la lista es un hallazgo:")
        for tab, cuales in sorted(inestables.items()):
            ap("- **" + tab + "** — " + ", ".join(cuales))
    ap("")
    ap("## Los tableros")
    ap("")
    ap("| tablero | estado | verdes | rojos | --verifica | min |")
    ap("|---|---|---:|---:|---|---:|")
    for t in informe["tableros"]:
        v = t.get("verifica") or {}
        cod = v.get("exit")
        pinta = "no corrio" if cod is None else ("pasa" if cod == 0 else "FALLA (" + str(cod) + ")")
        total = t["duracion_s"] + v.get("duracion_s", 0.0)
        ap("| " + t["nombre"] + " | " + t["estado"] + " | " + str(t["verdes"]) + " | "
           + str(len(t.get("rojos", []))) + " | " + pinta + " | " + str(round(total / 60, 1)) + " |")
    for t in informe["tableros"]:
        ap("")
        ap("### " + t["nombre"] + " (" + t["estado"] + ")")
        if t.get("detalle"):
            ap("")
            ap("> " + t["detalle"])
        v = t.get("verifica") or {}
        if v.get("resumen"):
            ap("")
            ap("`--verifica`: " + v["resumen"])
        if t.get("rojos"):
            ap("")
            for r in t["rojos"]:
                ap("- 🔴 " + r)
        elif t["estado"] == "ok":
            ap("")
            ap("Todo verde.")
    if informe.get("huerfanos"):
        ap("")
        ap("## ⚠️ Tableros huérfanos")
        ap("")
        ap("Existen en el disco y nadie los ha declarado ni excluido. Hasta que se decida, la "
           "ronda está incompleta:")
        for h in informe["huerfanos"]:
            ap("- `" + h + "`")
    if informe.get("ausentes"):
        ap("")
        ap("## ⚠️ Tableros declarados que ya no están")
        ap("")
        for a in informe["ausentes"]:
            ap("- " + a)
    ap("")
    ap("## Aviso")
    ap("")
    ap(informe.get("aviso", "(sin dato)"))
    ap("")
    return chr(10).join(L)


def aviso_para_la_sesion(informe: dict) -> str:
    """Lo que hay que decirle a G al abrir su próxima sesión. Vacío si no hay nada que hacer.

    ## Por qué existe (2026-08-23, y sale de una respuesta suya)

    Le pregunté qué haría si a las 22:40 le saltara un globo avisando de dos rojos nuevos.
    Contestó: **«lo miro mañana»**. Dos cosas se siguen de ahí, y la segunda no era obvia:

      · la ronda de las 08:30 está bien puesta, porque coincide con cuando mira;
      · pero **un globo dura diez segundos**. Si no está delante a las 08:35, el aviso muere y la
        información se queda en un informe que tiene que acordarse de abrir — que es justo la
        dependencia que este encargo existía para quitar.

    Así que el aviso se cuelga también de `session_start.py`, que ya avisa igual de las entradas
    vencidas del REGISTRO y que él lee cada mañana sin acordarse de nada.

    ⚠️ **Devuelve vacío cuando no hay nada que hacer, y eso es la mitad del diseño.** Un aviso que
    aparece todos los días se convierte en parte del decorado en una semana; entonces el día que
    diga algo, tampoco se lee. El silencio es lo que hace que hablar signifique algo.

    Y el que formatea es la ronda, no el hook: el hook corre en CADA arranque de sesión, así que se
    queda tonto —imprimir un fichero— en vez de aprender a leer JSON.
    """
    lineas = []
    nuevos = informe.get("nuevos_rojos") or {}
    if nuevos:
        cuantos = sum(len(v) for v in nuevos.values())
        lineas.append("TABLEROS: " + str(cuantos) + " rojo(s) NUEVO(S) — "
                      + "; ".join(k + ": " + ", ".join(v) for k, v in sorted(nuevos.items())))
    rotos = [t.get("nombre") for t in informe.get("tableros", []) if t.get("estado") != "ok"]
    sin_vigilar = list(informe.get("huerfanos") or []) + list(informe.get("ausentes") or [])
    if rotos or sin_vigilar:
        lineas.append("TABLEROS: la ronda no pudo mirarlo todo — sin leer: "
                      + (", ".join(str(x) for x in rotos) or "ninguno")
                      + " | sin vigilar: " + (", ".join(sin_vigilar) or "ninguno"))
    inestables = informe.get("inestables") or {}
    if inestables:
        cuantos = sum(len(v) for v in inestables.values())
        lineas.append("TABLEROS: " + str(cuantos) + " comprobador(es) cambian de color segun la "
                      "carga (" + "; ".join(k + ": " + ", ".join(v)
                                            for k, v in sorted(inestables.items()))
                      + ") — no es un rojo, es un comprobador roto")
    if not lineas:
        return ""
    lineas.append("   detalle: " + str(CARPETA_RONDAS / "ULTIMA.md"))
    return chr(10).join(lineas) + chr(10)


def _rotar(carpeta: Path, cuantos: int = 30) -> None:
    viejos = sorted(carpeta.glob("ronda-*.md"))[:-cuantos]
    for v in viejos:
        try:
            v.unlink()
        except OSError:
            pass


def _autoignorar(carpeta: Path) -> None:
    """`.rondas/` vive dentro del repo `proyectos`, y sus informes no son del repo."""
    gi = carpeta / ".gitignore"
    if not gi.exists():
        gi.write_text("*" + chr(10), encoding="utf-8")


# ── el veredicto que lee el tablero de capa-normativa ────────────────────────────────────────

def ultimo_arranque_de_la_tarea(nombre: str = TAREA) -> datetime | None:
    """Cuándo arrancó por última vez la tarea de Windows, o `None` si nunca / no existe.

    ⚠️ Esto es lo que separa «registrada» de «arrancando», y esa distinción ya nos costó una:
    con `ollama_chain` se dio por buena una tarea porque estaba REGISTRADA, y llevaba meses sin
    ejecutarse ni una vez. Un registro es una intención; `LastRunTime` es un hecho.
    """
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$i = Get-ScheduledTaskInfo -TaskName '" + nombre + "' -ErrorAction Stop; "
             "$i.LastRunTime.ToString('yyyy-MM-ddTHH:mm:ss')"],
            capture_output=True, timeout=120)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    texto = r.stdout.decode("utf-8", "replace").strip()
    try:
        cuando = datetime.strptime(texto, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    # Windows contesta 1899-12-30 para una tarea registrada que jamás ha corrido.
    return None if cuando.year < 2000 else cuando


def veredicto(informe: dict | None, ahora: datetime, arranque: datetime | None,
              ventana_h: int = VENTANA_H, suelo: int = SUELO_TABLEROS,
              verifica_por_tarea: bool = False) -> tuple[bool, str]:
    """¿Está la ronda corriendo SOLA y completa? Función pura: se le da el mundo, no lo mira.

    Que sea pura es lo que la hace comprobable por mutación — se le puede pasar un informe viejo,
    uno ausente o uno de cero tableros sin tocar el disco ni la tarea real.

    El orden de las preguntas no es casual: primero *¿ha arrancado sola?*, después *¿hay informe
    fresco?*, y sólo al final *¿está completo?*. Así el motivo que se imprime señala la causa
    más de fondo, en vez de la más visible.
    """
    if arranque is None:
        return False, ("la tarea '" + TAREA + "' no existe o NUNCA ha arrancado: registrada no es "
                       "lo mismo que arrancando")
    edad_arranque = (ahora - arranque).total_seconds() / 3600
    if edad_arranque > ventana_h:
        return False, ("la tarea existe pero su ultimo arranque fue hace "
                       + str(int(edad_arranque)) + " h (>" + str(ventana_h) + "): ha dejado de correr")
    if informe is None:
        return False, "no hay informe de ronda: la tarea arranca pero no deja evidencia"
    terminado = informe.get("terminado")
    try:
        fin = datetime.strptime(str(terminado)[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return False, "el informe no dice cuando termino: no sirve como evidencia"
    edad = (ahora - fin).total_seconds() / 3600
    if edad > ventana_h:
        return False, ("el ultimo informe es de hace " + str(int(edad)) + " h (>" + str(ventana_h)
                       + "): la ronda ha dejado de correr")
    if informe.get("lanzador") != "tarea-programada":
        return False, ("el ultimo informe lo lanzo una persona a mano: eso demuestra que el "
                       "guion funciona, no que la ronda corra sola")
    corridos = int(informe.get("corridos") or 0)
    if corridos < suelo:
        return False, ("la ronda solo corrio " + str(corridos) + " tablero(s) de los " + str(suelo)
                       + " que tiene que cubrir: una ronda incompleta no vigila lo que falta")
    rotos = [t.get("nombre") for t in informe.get("tableros", []) if t.get("estado") != "ok"]
    if rotos:
        return False, ("la ronda no pudo leer " + str(len(rotos)) + " tablero(s): "
                       + ", ".join(str(x) for x in rotos))
    # `--verifica` es quien comprueba que cada comprobador sigue sabiendo ponerse rojo. Tableros
    # corriendo solos con comprobadores que ya no saben fallar son verdes que no significan nada.
    # Se exige que HAYA CORRIDO, no que pase: su fallo es un rojo del tablero ajeno, y esa
    # distinción es la que evita que un rojo de otro repo deje esta promesa incerrable.
    #
    # `verifica_por_tarea` es la otra puerta: si hay una tarea programada que ya lo ejecuta por su
    # cuenta, la condición se cumple sin que tenga que hacerlo la ronda. Está para no estrechar el
    # contrato original a una sola implementación.
    sin_mutar = [] if verifica_por_tarea else [
        t.get("nombre") for t in informe.get("tableros", [])
        if (t.get("verifica") or {}).get("exit") is None]
    if sin_mutar:
        return False, ("en " + str(len(sin_mutar)) + " tablero(s) no llego a correr `--verifica`, "
                       "que es quien vigila a los vigilantes: " + ", ".join(str(x) for x in sin_mutar))
    if informe.get("huerfanos"):
        return False, ("hay " + str(len(informe["huerfanos"])) + " tablero(s) que nadie vigila ni "
                       "ha declarado: " + ", ".join(informe["huerfanos"]))
    if informe.get("ausentes"):
        return False, "hay tablero(s) declarados que ya no estan: " + ", ".join(informe["ausentes"])
    rojos = sum(len(t.get("rojos", [])) for t in informe.get("tableros", []))
    mutacion_mal = [t.get("nombre") for t in informe.get("tableros", [])
                    if (t.get("verifica") or {}).get("exit") != 0]
    return True, ("la ronda corrio sola hace " + str(int(edad)) + " h sobre " + str(corridos)
                  + " tableros con su --verifica (" + str(rojos) + " rojo(s) recogidos, que es su "
                  "trabajo" + ("" if not mutacion_mal else "; --verifica falla en "
                               + ", ".join(str(x) for x in mutacion_mal) + ", avisado aparte")
                  + ")")


# ── main ─────────────────────────────────────────────────────────────────────────────────────

def _di(texto: str) -> None:
    """Imprime si hay dónde. Bajo `pythonw` o una tarea sin consola, `sys.stdout` puede no estar.

    Se hace `flush` a mano porque la salida va redirigida a un fichero, y ahí Python usa búfer de
    bloque: sin esto el log de la tarea aparecía entero al terminar, así que durante la media hora
    que dura la ronda no había forma de saber por qué tablero iba ni si se había colgado.
    """
    try:
        print(texto, flush=True)
    except Exception:
        pass


def main(argv: list[str]) -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except Exception:
            pass
    programada = "--programada" in argv
    carpeta = CARPETA_RONDAS
    if "--donde" in argv:
        _di(str(carpeta))
        return 0

    vigilados, ausentes, huerfanos = descubrir()
    if not vigilados:
        # Cero tableros no es «todo bien»: es que la ronda no encontró nada que vigilar. Se grita
        # y se sale != 0, porque este es el silencio que se lee como buenas noticias.
        _di("RONDA ABORTADA: cero tableros descubiertos bajo " + str(RAIZ_PROYECTOS))
        return 1

    t0 = time.monotonic()
    inicio = datetime.now()
    resultados = []
    for t in vigilados:
        _di("  ... " + t["nombre"])
        r = correr_tablero(t)
        resultados.append(r)
        v = r.get("verifica") or {}
        _di("      " + r["estado"] + " · " + str(r["verdes"]) + " verdes · "
            + str(len(r.get("rojos", []))) + " rojos · --verifica=" + str(v.get("exit"))
            + " · " + str(round(r["duracion_s"] + v.get("duracion_s", 0.0), 1)) + " s")

    # Un mudo que INSISTE deja de ser «la maquina iba ahogada» y pasa a ser un vigilante muerto.
    aplicar_mudos(resultados, carpeta / "mudos.json", inicio.strftime("%Y-%m-%d"))

    previo = leer_ultimo(carpeta)
    nuevos, resueltos = comparar(resultados, previo)

    # Un rojo NUEVO no se cree a la primera: se le vuelve a preguntar antes de molestar a nadie.
    # Ver `reconfirmar()` — la primera ronda de verdad dio cuatro falsas alarmas por carga.
    inestables = {}
    por_nombre = {t["nombre"]: t for t in vigilados}
    for t, ficha in zip(vigilados, resultados):
        t["resultado"] = ficha
    for tab in sorted(nuevos):
        exe, problema = _interprete_de(por_nombre[tab])
        if problema:
            continue
        _di("  ... reconfirmando " + str(len(nuevos[tab])) + " rojo(s) nuevo(s) de " + tab)
        confirmados, dudosos = reconfirmar(por_nombre[tab], exe, nuevos[tab])
        if dudosos:
            inestables[tab] = dudosos
            _di("      " + str(len(dudosos)) + " no se reconfirman: " + ", ".join(dudosos))
            # Salen de `rojos` y cuentan como verdes, que es lo que contestó la repregunta.
            #
            # ⚠️ No basta con no avisar de ellos: si se quedan en la lista, cambian la FIRMA y el
            # globo sale igual, solo que con otro título. La falsa alarma volvería por la puerta
            # de atrás. Y la ronda siguiente los vería «resueltos», que es un segundo aviso falso.
            ficha = por_nombre[tab]["resultado"]
            ficha["rojos"] = [r for r in ficha["rojos"] if r not in dudosos]
            ficha["verdes"] += len(dudosos)
        if confirmados:
            nuevos[tab] = confirmados
        else:
            del nuevos[tab]

    # Y lo mismo por el otro lado, que es la mitad que faltaba: un rojo que DESAPARECE tampoco se
    # cree a la primera.
    #
    # ⚠️ Sin esto, un comprobador que parpadea produce un globo falso en cada vuelta completa:
    # aparece (se reconfirma, se calla), y al desaparecer sale como «se cerró» y ESO sí avisa. La
    # falsa alarma se colaba por la puerta de salida. Medido con `canario-de-los-hooks`, que bajo
    # la carga de la ronda sale rojo y a solas sale verde.
    #
    # La dirección segura es la misma: si la repregunta no se entiende, NO se celebra el cierre.
    for tab in sorted(resueltos):
        if tab not in por_nombre:
            continue                      # un tablero que ya no está no puede repreguntarse
        exe, problema = _interprete_de(por_nombre[tab])
        if problema:
            continue
        _di("  ... comprobando " + str(len(resueltos[tab])) + " cierre(s) de " + tab)
        aun_rojos, de_verdad = reconfirmar(por_nombre[tab], exe, resueltos[tab])
        if aun_rojos:
            ficha = por_nombre[tab]["resultado"]
            ficha["rojos"] = sorted(set(ficha["rojos"]) | set(aun_rojos))
            ficha["verdes"] = max(0, ficha["verdes"] - len(aun_rojos))
            inestables.setdefault(tab, []).extend(aun_rojos)
            _di("      " + str(len(aun_rojos)) + " no estaban cerrados: " + ", ".join(aun_rojos))
        if de_verdad:
            resueltos[tab] = de_verdad
        else:
            del resueltos[tab]

    fin = datetime.now()
    informe = {
        "version": 1,
        "iniciado": inicio.strftime("%Y-%m-%dT%H:%M:%S"),
        "terminado": fin.strftime("%Y-%m-%dT%H:%M:%S"),
        "lanzador": "tarea-programada" if programada else "a mano",
        "duracion_s": round(time.monotonic() - t0, 1),
        "declarados": len(_TABLEROS),
        "corridos": len(resultados),
        "tableros": resultados,
        "huerfanos": huerfanos,
        "ausentes": ausentes,
        "nuevos_rojos": nuevos,
        "resueltos": resueltos,
        "inestables": inestables,
    }
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        _autoignorar(carpeta)
        informe["aviso"] = avisar(resultados, nuevos, resueltos, huerfanos, ausentes, carpeta)
        cuerpo = _md(informe)
        (carpeta / ("ronda-" + fin.strftime("%Y%m%d-%H%M%S") + ".md")).write_text(
            cuerpo, encoding="utf-8")
        (carpeta / "ULTIMA.md").write_text(cuerpo, encoding="utf-8")
        (carpeta / "ultima.json").write_text(
            json.dumps(informe, ensure_ascii=False, indent=1), encoding="utf-8")
        # Se escribe SIEMPRE, aunque sea vacio: asi el fichero de ayer no se queda diciendo lo de
        # ayer. Un aviso que no se apaga al resolverse ensena a ignorar los avisos.
        (carpeta / "AVISO.txt").write_text(aviso_para_la_sesion(informe), encoding="utf-8")
        _rotar(carpeta)
    except OSError as e:
        _di("RONDA SIN INFORME: no se pudo escribir en " + str(carpeta) + " — " + str(e))
        return 1

    _di("")
    _di("  informe: " + str(carpeta / "ULTIMA.md"))
    _di("  " + str(sum(len(t.get("rojos", [])) for t in resultados)) + " rojos en total, "
        + str(sum(len(v) for v in nuevos.values())) + " nuevos.")
    _di("  aviso: " + informe["aviso"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
