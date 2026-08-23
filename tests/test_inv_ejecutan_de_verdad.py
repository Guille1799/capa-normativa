"""Toda aceptación del inventario tiene que LLEGAR A EJECUTARSE.

Un `exit != 0` puede significar dos cosas —«falta trabajo» o «el comando no arrancó»— y sólo la
primera es un veredicto. El tablero no las distingue: lee el exit code y escribe «pendiente». Un
comprobador cuyo comando no arranca está ROJO PARA SIEMPRE y su tarea es incerrable, hiciera nadie
lo que hiciera.

No se afirma el COLOR de ninguna aceptación: eso importaría un rojo permanente a la suite, que es
justo lo que la cabecera del tablero prohíbe. Lo que se afirma es la invariante que debe cumplirse
siempre —**todas arrancan**— y esa no se pudre cuando una tarea se cierra.

## Por qué existe este fichero en este tablero (medido el 2026-08-23)

De los 36 `_INV` repartidos por los cinco tableros que NO tenían este test, **cuatro morían en el
shell** y llevaban meses marcando «pendiente» sin haber arrancado ni una vez:

  · `inv-decision-recall-y-session-restorer` — comillas de PowerShell dentro de cmd.exe
  · `inv-ollama-chain-py-registrado-con`     — el campo contenía prosa, no un comando
  · `inv-dos-pre-commit-con-el`              — la prosa iba DELANTE del comando
  · `inv-audit-settings-source-sh-no`        — roto de fábrica, y su arreglo es decisión de G

Los tres primeros se arreglaron ese día; dos de ellos revelaron trabajo **ya hecho** que el
examinador roto ocultaba. Este test los habría cazado el día que se escribieron.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TABLERO = RAIZ / "scripts" / "aceptacion.py"

#: Firmas de que fallo el INTERPRETE, no el programa. Se buscan solo en las primeras lineas: mas
#: abajo ya es salida del comprobador, y una sonda legitima puede mencionar un error de sintaxis
#: en su diagnostico sin estar rota.
_ERROR_DE_SHELL = re.compile(
    r"no se reconoce como un comando|is not recognized as an internal"
    r"|command not found|no se esperaba|was unexpected at this time"
    r"|s.ntaxis del comando no es correcta",
    # ⚠️ `can't open file` NO entra: varias aceptaciones apuntan a proposito a un artefacto que la
    # tarea debe CREAR, y que Python no lo encuentre es su rojo correcto, no una averia.
    re.I)

#: cmd.exe devuelve esto cuando no encuentra el ejecutable. No es «falta trabajo».
_EXIT_NO_EXISTE = 9009

#: Aceptaciones que se SABE que no arrancan, con el motivo por el que no se han arreglado.
#:
#: ⚠️ Van marcadas `xfail(strict=True)`, o sea que **el andamio se retira solo**: el dia que
#: alguien arregle una, este test FALLA y obliga a sacarla de aqui. Una lista de excepciones que
#: no se entera de que sobra es como acaban siendo permanentes.
_ROTOS_DECLARADOS = {
    "inv-audit-settings-source-sh-no":
        "roto de fabrica (su campo de comando no es ejecutable) Y su arreglo es DECISION DE"
        " G: lo que la tarea pide es RETIRAR un hook de SEGURIDAD (CVE-2025-59536). Arreglar"
        " el comando lo volveria accionable por el robot, y un agente autonomo retirando un"
        " control de seguridad no es algo que deba poder pasar por descuido. Se deja roto A"
        " PROPOSITO, y declarado aqui para que se vea que es a proposito y no un olvido.",
}


def _tablero():
    spec = importlib.util.spec_from_file_location("tablero_bajo_prueba", str(TABLERO))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TB = _tablero()
INV = sorted(getattr(TB, "_INV", {}))

_CASOS = [
    pytest.param(n, marks=pytest.mark.xfail(strict=True, reason=_ROTOS_DECLARADOS[n]))
    if n in _ROTOS_DECLARADOS else n
    for n in INV
]


@pytest.mark.parametrize("nombre", _CASOS)
def test_la_aceptacion_llega_a_ejecutarse(nombre):
    """El comando arranca: su exit code es un veredicto y no un accidente del shell."""
    bruto = str(TB._INV[nombre][0])
    comando = TB._solo_el_comando(bruto) if hasattr(TB, "_solo_el_comando") else bruto
    try:
        r = subprocess.run(comando, shell=True, capture_output=True, timeout=600, cwd=str(RAIZ))
    except subprocess.TimeoutExpired:
        pytest.fail(nombre + ": se cuelga (>10 min). Un comprobador que no termina no informa de "
                             "nada, y ademas bloquea la tanda entera.")
    salida = (r.stdout + r.stderr).decode("utf-8", "replace")
    cabeza = chr(10).join(salida.splitlines()[:3])
    assert r.returncode != _EXIT_NO_EXISTE, (
        nombre + ": exit 9009, cmd.exe no encuentra el ejecutable. El tablero leeria esto como "
                 "«pendiente» y la tarea seria incerrable.")
    assert not _ERROR_DE_SHELL.search(cabeza), (
        nombre + ": el SHELL falla antes de medir nada -> " + cabeza.strip()[:160]
        + chr(10) + "   comando: " + comando[:160])


def test_hay_algo_que_comprobar():
    """Si `_INV` se vacia o deja de leerse, el test de arriba pasa sin probar nada.

    Un parametrize sobre una lista vacia son cero tests, y cero tests en verde parecen exito.
    """
    assert INV, "no se leyo ninguna entrada de _INV: el test estaria pasando en vacio"


def test_los_rotos_declarados_existen_de_verdad():
    """Una excepcion a un nombre que ya no esta en el tablero no protege nada, y despista."""
    fantasmas = sorted(set(_ROTOS_DECLARADOS) - set(INV))
    assert not fantasmas, ("declarados como rotos pero ya no estan en _INV: " + ", ".join(fantasmas))


def test_ningun_diccionario_del_tablero_tiene_claves_repetidas():
    """Una clave repetida en un literal de Python convierte una definicion en CODIGO MUERTO.

    Y muerto en silencio, que es lo grave: gana la ULTIMA, asi que quien edite cualquier otra ve
    que su cambio no hace nada y concluye que el tablero esta roto, en vez de que ha editado la que
    no era. Al medirlo el 2026-08-23 habia 36 repetidas en seis tableros.
    """
    import ast
    arbol = ast.parse(TABLERO.read_text(encoding="utf-8"))
    interesantes = {"_INV", "SIN_MUTACION", "COMPROBADORES", "ARTEFACTOS", "_ARREGLOS",
                    "_AGUJEROS", "CUMPLIDAS"}
    repetidas = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        destino = getattr(nodo.targets[0], "id", None)
        if destino not in interesantes or not isinstance(nodo.value, ast.Dict):
            continue
        vistas = set()
        for k in nodo.value.keys:
            if isinstance(k, ast.Constant):
                if k.value in vistas:
                    repetidas.append(destino + "[" + repr(k.value) + "] linea " + str(k.lineno))
                vistas.add(k.value)
    assert not repetidas, ("claves repetidas (la primera queda muerta y nadie lo ve): "
                           + "; ".join(repetidas))
