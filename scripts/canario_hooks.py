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

import json
import subprocess
import sys
from pathlib import Path

SETTINGS = Path("C:/Users/Guille/.claude/settings.json")

#: Cargas malformadas que TODO hook debe sobrevivir saliendo 0. No es una lista caprichosa: son
#: las tres formas en que un hook recibe algo que no esperaba — nada, texto que no es JSON, y
#: JSON valido sin los campos que busca.
_MALFORMADAS = {
    "vacio": b"",
    "no-es-json": b"esto no es json{{{",
    "json-sin-campos": b"{}",
}

#: Carga que cada hook DEBE rechazar, y como se sabe que la rechazo.
#: Vacio a proposito: declararlo es el trabajo que este canario existe para obligar. Formato:
#:     "<nombre del hook>": (b"<carga>", "<que se espera: 'exit!=0' o un texto que deba salir>")
CASOS_ENVENENADOS: dict[str, tuple[bytes, str]] = {}


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


def sin_caso() -> list[str]:
    """Hooks registrados que no tienen carga envenenada declarada.

    Se DENUNCIAN en vez de saltarse, que es el contrato de `canario(DETECTORES)`: un guardian sin
    caso rojo es un guardian que nadie ha comprobado.
    """
    return sorted({_nombre(cmd) for _, cmd in hooks_registrados()
                   if _nombre(cmd) not in CASOS_ENVENENADOS})


def envenenados() -> list[str]:
    """Los casos declarados: se le da la carga y se exige que grite."""
    problemas = []
    for evento, cmd in hooks_registrados():
        n = _nombre(cmd)
        caso = CASOS_ENVENENADOS.get(n)
        if not caso:
            continue
        carga, espera = caso
        try:
            r = subprocess.run(cmd, shell=True, input=carga, capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            problemas.append(n + ": se cuelga con su carga envenenada")
            continue
        salida = (r.stdout + r.stderr).decode("utf-8", "replace")
        grito = (r.returncode != 0) if espera == "exit!=0" else (espera in salida)
        if not grito:
            problemas.append(n + ": NO grita ante su carga envenenada (esperaba " + espera + ")")
    return problemas


def main(argv: list[str]) -> int:
    registrados = hooks_registrados()
    if not registrados:
        print("ROJO: no se pudo leer ningun hook de settings.json — sin lista no hay canario")
        return 1
    fallos = robustez()
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
