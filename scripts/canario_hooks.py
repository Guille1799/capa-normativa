"""Canario de los hooks: ¿los diez guardianes que hay registrados hacen lo que dicen?

## Por qué existe

`~/.claude/settings.json` registra **10 entradas de hook**. Ninguna tiene hoy una prueba de que
haga lo suyo, y eso ya costó caro una vez: el 2026-08-20 el escáner de secretos recorría CERO
ficheros y contestaba «limpio» por un `GIT_DIR` heredado. Un guardián instalado del que nadie ha
visto morder no es un guardián que funciona: es uno sin estrenar.

## Las dos mitades, y por qué la segunda nace roja

**1 · Robustez (se comprueba hoy, para los diez).** Los hooks declaran fallar ABIERTO: ante
cualquier error salen 0 para no bloquear la sesión. Eso se puede verificar sin inventar nada —
se les da una carga malformada y se exige que terminen rápido, sin traza de error y sin bloquear.
Un hook que revienta con una entrada rara puede romper todas las sesiones, y su fallo aparecería
lejos de aquí.

**2 · Carga envenenada (el contrato de CASOS).** Lo que de verdad prueba a un guardián es darle
la entrada que DEBE rechazar y exigir que grite. Eso no se puede escribir en general: depende de
qué vigila cada hook. Así que se declara caso por caso, y —copiando a `canario(DETECTORES)` del
vigilante— **este canario SALTA cuando un hook registrado no tiene caso**, en vez de pasar de
largo. Un hook sin caso es un hook que nadie ha comprobado, y esa distinción no puede ser
silenciosa.

Por eso nace ROJO: hoy hay 10 hooks registrados y 0 casos envenenados declarados. Se pone verde
declarándolos, que es el trabajo — no se aprueba escribiendo nada aquí.

    python scripts/canario_hooks.py            # las dos mitades
    python scripts/canario_hooks.py --robustez # solo la primera, para depurar
"""

from __future__ import annotations

import ast
import json
import subprocess
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

#: Derivada, no escrita: repo publico (la nota esta en `scripts/aceptacion.py`).
SETTINGS = Path(os.environ.get("CLAUDE_SETTINGS") or Path.home() / ".claude" / "settings.json")

#: Cargas malformadas que TODO hook debe sobrevivir saliendo 0. No es una lista caprichosa: son
#: las tres formas en que un hook recibe algo que no esperaba — nada, texto que no es JSON, y
#: JSON valido sin los campos que busca.
_MALFORMADAS = {
    "vacio": b"",
    "no-es-json": b"esto no es json{{{",
    "json-sin-campos": b"{}",
}

#: Hooks que NO bloquean nada: informan, registran o inyectan contexto, y salen 0 siempre. No se
#: les puede pedir una carga envenenada porque no hay entrada que deban RECHAZAR — pedirsela seria
#: inventarles una semantica que no tienen.
#:
#: Medido el 2026-08-23 contando sus salidas: de los diez registrados, solo CUATRO tienen alguna
#: distinta de cero. `audit_settings_source.sh` lo dice en su propia cabecera: «exit 0 siempre
#: (warning, no bloqueo)».
#:
#: Se declaran con motivo, como `SIN_MUTACION`, en vez de silenciarse: una exencion escrita se
#: revisa, una implicita se hereda. Y si alguno pasa a bloquear algun dia, hay que sacarlo de aqui.
SOLO_INFORMAN = {
    "audit_settings_source.sh": "avisa de settings.json tocado por otro autor; sale 0 siempre",
    # Fue `session_start.sh` hasta el 2026-08-24. Se porto a Python porque estaba registrado como
    # `bash …`, y en Windows `bash` a secas NO es Git Bash: resuelve al lanzador de WSL, que sin
    # distro sale 1 sin imprimir nada. O sea que el hook vivia o moria segun quien ganara el PATH,
    # y moria EN SILENCIO, porque SessionStart falla abierto. Era el unico de los nueve que
    # necesitaba un shell; los otros ocho ya eran Python.
    "session_start.py": "imprime contexto de arranque; no veta nada",
    "inject_context.py": "inyecta contexto en el prompt; no veta nada",
    "save_state.py": "guarda el estado en PreCompact y SessionEnd; no veta nada",
    "prompt_router.py": "inyecta directivas [AUTO] en el prompt; sus 8 salidas son todas 0",
    # Contado a mano tras un falso positivo del propio conteo: su UNICA salida es `sys.exit(0)`,
    # en la linea 125. El grep inicial le vio una "bloqueante" que no existe.
    "autohealth_monitor.py": "avisa de la salud del indice en PostToolUse; su unica salida es 0",
}

#: Carga que cada GUARDIAN debe rechazar, y como se sabe que la rechazo. Formato:
#:     "<nombre del hook>": (b"<carga>", "<que se espera: 'exit!=0' o un texto que deba salir>")
#: Cada caso es un CONTEXTO que monta su escenario envenenado en un temporal y devuelve la carga.
#: Tiene que ser un contexto y no una cadena fija porque el veneno de estos tres no vive en el
#: payload, vive en el ESTADO al que el payload apunta: un transcript con lenguaje de decision, un
#: checkpoint con una cita muerta, un repo con un secreto. Se monta, se dispara y se tira.


@contextmanager
def _veneno_doc_decision():
    """Lenguaje de decision reciente + ningun doc tocado -> el gate DEBE bloquear."""
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        tr = tmp / "transcript.jsonl"
        tr.write_text(json.dumps({"message": {"role": "user",
                                              "content": "decidimos que a partir de ahora usamos X"}})
                      + chr(10), encoding="utf-8")
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], capture_output=True, timeout=60)
        yield json.dumps({"transcript_path": str(tr), "cwd": str(repo)}).encode()


@contextmanager
def _veneno_promesa():
    """Un checkpoint escrito en la sesion que cita un comprobador inexistente -> DEBE bloquear."""
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        ck = tmp / "Contexto" / "mcp_smart_context" / "2026-01-01_00-00_canario.md"
        ck.parent.mkdir(parents=True)
        ck.write_text("## PRÓXIMO PASO EXACTO" + chr(10)
                      + "1. `aceptacion.py comprobador-que-no-existe-jamas`" + chr(10),
                      encoding="utf-8")
        tr = tmp / "transcript.jsonl"
        tr.write_text(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Write", "input": {"file_path": str(ck)}}]}})
            + chr(10), encoding="utf-8")
        yield json.dumps({"transcript_path": str(tr)}).encode()


@contextmanager
def _veneno_vigilante():
    """Un repo versionado con un secreto conocido -> el vigilante DEBE bloquear el cierre.

    Reusa `repo_de_pega` del propio canario del vigilante, que ya monta un repo efimero con un
    caso rojo por detector y es independiente del CWD. Escribir otro seria tener dos definiciones
    de «entrada envenenada» que pueden divergir.
    """
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from capa_normativa.vigilante.canario import repo_de_pega
    with repo_de_pega() as repo:
        yield json.dumps({"cwd": str(repo)}).encode()


#: Carga que cada GUARDIAN debe rechazar, y como se sabe que la rechazo.
CASOS_ENVENENADOS = {
    "doc_decision_gate.py": (_veneno_doc_decision, "exit!=0"),
    "promesa_gate.py": (_veneno_promesa, "exit!=0"),
    "vigilante_pre_commit.py": (_veneno_vigilante, "exit!=0"),
}


def hooks_registrados() -> list[tuple[str, str]]:
    """(evento, comando) de cada entrada de `settings.json`. Se leen, no se listan a mano.

    Una lista escrita a mano envejece en silencio: el dia que se registre un hook nuevo, el
    canario seguiria diciendo que estan todos cubiertos.
    """
    if not SETTINGS.exists():
        return []
    try:
        d = json.loads(SETTINGS.read_text("utf-8", errors="replace"))
    except Exception:
        return []
    fuera = []
    for evento, entradas in (d.get("hooks") or {}).items():
        for e in entradas or []:
            for c in e.get("hooks") or []:
                cmd = (c.get("command") or "").strip()
                if not cmd:
                    continue
                # ⚠️ El script puede venir en un campo `args` APARTE, no dentro de `command`.
                # Cinco de los diez estan asi. Leyendo solo `command` se invoca un `python`
                # pelado, que se come stdin como si fuera un programa — y entonces el canario
                # denuncia cinco hooks sanos por un fallo suyo. Paso en la primera pasada.
                args = c.get("args") or []
                if isinstance(args, str):
                    args = [args]
                partes = [cmd] + ['"' + str(a) + '"' if " " in str(a) else str(a) for a in args]
                fuera.append((evento, " ".join(partes)))
    return fuera


def _nombre(cmd: str) -> str:
    """Un identificador legible del hook, para poder declararle un caso sin pegar el comando."""
    for trozo in cmd.replace(chr(92), "/").split():
        if trozo.endswith((".py", ".sh")):
            return trozo.rsplit("/", 1)[-1]
    return cmd.split()[0].rsplit("/", 1)[-1]


def robustez() -> list[str]:
    """Cada hook, ante una carga malformada: termina, no revienta y no bloquea."""
    problemas = []
    for evento, cmd in hooks_registrados():
        n = _nombre(cmd)
        for etiqueta, carga in _MALFORMADAS.items():
            try:
                r = subprocess.run(cmd, shell=True, input=carga, capture_output=True, timeout=120)
            except subprocess.TimeoutExpired:
                problemas.append(n + " [" + evento + "] se cuelga con " + etiqueta
                                 + " (>2 min): bloquearia la sesion")
                continue
            err = r.stderr.decode("utf-8", "replace")
            if "Traceback (most recent call last)" in err:
                problemas.append(n + " [" + evento + "] REVIENTA con " + etiqueta
                                 + ": " + err.strip().splitlines()[-1][:90])
            elif r.returncode != 0:
                problemas.append(n + " [" + evento + "] sale " + str(r.returncode) + " con "
                                 + etiqueta + ", y declara fallar ABIERTO")
    return problemas


def compilan() -> list[str]:
    """Cada hook en Python tiene que PARSEAR. Un fichero que no compila no es un hook: es ruido.

    Nace de un caso real del 2026-08-25. `autohealth_monitor.py` llevaba al menos dos dias sin
    compilar: en la linea 120 tenia

        msg = "
    ".join(alerts)

    o sea un `\\n` convertido en un salto de linea DE VERDAD — el destrozo tipico de un reemplazo
    de texto descuidado sobre una secuencia de escape. El hook esta registrado en PostToolUse, asi
    que moria con SyntaxError DETRAS DE CADA HERRAMIENTA, y nadie se entero porque PostToolUse
    falla abierto.

    Y su ficha en el censo decia «su UNICA salida es sys.exit(0), en la linea 125», contado a mano
    LEYENDO el fuente. Leer demostro cual era la salida; solo ejecutarlo mostraba que no se llega
    nunca. Esa es la leccion, y por eso esto se comprueba aparte.

    Se separa de `robustez()` a proposito: alli el sintoma era «sale 1 con vacio», que es el mismo
    mensaje que da un hook que decide bloquear. Un `SyntaxError` NO imprime «Traceback (most recent
    call last)» —es un error de compilacion, no una excepcion en ejecucion—, asi que ni siquiera
    caia en la rama de REVIENTA. Confundir un instrumento roto con un hallazgo cuesta horas.
    """
    problemas = []
    for evento, cmd in hooks_registrados():
        ruta = None
        for trozo in cmd.replace(chr(92), "/").split():
            if trozo.endswith(".py"):
                ruta = Path(trozo)
                break
        if ruta is None or not ruta.is_file():
            continue
        try:
            ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as e:
            problemas.append(f"{ruta.name} [{evento}] NO COMPILA: linea {e.lineno}, {e.msg}. "
                             "No es que falle: es que no llega a arrancar nunca.")
    return problemas


def sin_caso() -> list[str]:
    """Hooks registrados que no tienen carga envenenada declarada.

    Se DENUNCIAN en vez de saltarse, que es el contrato de `canario(DETECTORES)`: un guardian sin
    caso rojo es un guardian que nadie ha comprobado.
    """
    return sorted({_nombre(cmd) for _, cmd in hooks_registrados()
                   if _nombre(cmd) not in CASOS_ENVENENADOS
                   and _nombre(cmd) not in SOLO_INFORMAN})


def envenenados() -> list[str]:
    """Los casos declarados: se le da la carga y se exige que grite."""
    problemas = []
    for evento, cmd in hooks_registrados():
        n = _nombre(cmd)
        caso = CASOS_ENVENENADOS.get(n)
        if not caso:
            continue
        montar, espera = caso
        try:
            with montar() as carga:
                r = subprocess.run(cmd, shell=True, input=carga, capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            problemas.append(n + ": se cuelga con su carga envenenada")
            continue
        except Exception as e:
            problemas.append(n + ": no se pudo montar su escenario (" + type(e).__name__ + ")")
            continue
        salida = (r.stdout + r.stderr).decode("utf-8", "replace")
        grito = (r.returncode != 0) if espera == "exit!=0" else (espera in salida)
        if not grito:
            problemas.append(n + ": NO grita ante su carga envenenada (esperaba " + espera + ")")
    return problemas


def main(argv: list[str]) -> int:
    # `hooks_registrados()` devuelve [] por tres motivos distintos, y hasta el 2026-08-30 los tres
    # salian ROJO con el mismo mensaje. Dos de ellos SI son rojo; el tercero no, y confundirlos es
    # la misma trampa que este canario existe para cazar en los demas.
    try:
        SETTINGS.read_text("utf-8", errors="replace")
    except FileNotFoundError:
        # No es «no he podido leerlo»: es una respuesta clara, y dice que aqui no hay nada
        # registrado. Un canario sin nada que vigilar es un canario roto.
        print("ROJO: no existe " + str(SETTINGS) + " — sin lista no hay canario")
        return 1
    except OSError as e:
        # ESTE es el que no era rojo. Permisos, disco, el fichero en uso: no se ha podido mirar,
        # y no mirar no es una acusacion. Si el impedimento persiste, la ronda lo sube a rojo sola.
        print("MUDO: no se pudo leer " + SETTINGS.name + " (" + type(e).__name__ + "): no se ha "
              "comprobado nada, que no es lo mismo que estar mal")
        return 3
    registrados = hooks_registrados()
    if not registrados:
        # Se ha leido bien y no declara hooks (o el JSON esta corrupto). Es una respuesta, y es
        # imposible en esta maquina: eso es haber mirado y ver algo que no cuadra.
        print("ROJO: " + SETTINGS.name + " se lee pero no declara ningun hook — sin lista no hay "
              "canario")
        return 1
    # Primero si COMPILAN: un fichero que no parsea da un «sale 1» indistinguible de un hook que
    # decide bloquear, y ese diagnostico equivocado cuesta horas. Que salga nombrado y aparte.
    fallos = compilan()
    fallos += robustez()
    if "--robustez" not in argv:
        fallos += envenenados()
        faltan = sin_caso()
        if faltan:
            fallos.append(str(len(faltan)) + " hook(s) SIN carga envenenada declarada: "
                          + ", ".join(faltan[:6]) + (" ..." if len(faltan) > 6 else ""))
    if fallos:
        print("ROJO (" + str(len(registrados)) + " hooks registrados):")
        for f in fallos:
            print("   · " + f)
        return 1
    # El mensaje NO puede afirmar mas de lo que se comprobo: en modo `--robustez` no se ha
    # tocado ninguna carga envenenada, y decir que «gritan» seria exactamente la clase de verde
    # que no obliga a nada.
    if "--robustez" in argv:
        print("VERDE (solo robustez): los " + str(len(registrados)) + " hooks sobreviven a una "
              "carga malformada. NO se ha probado que rechacen nada.")
    else:
        print("VERDE: los " + str(len(registrados)) + " hooks sobreviven a una carga malformada "
              "y gritan con la suya envenenada")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
