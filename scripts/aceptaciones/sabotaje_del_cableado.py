"""Ninguna pieza del tablero puede quedarse INCAPAZ DE PONERSE ROJA sin que nadie lo note.

## Qué hace, en una frase

Coge cada pieza de **cableado** del tablero, le voltea sus `return False` —dejándola físicamente
incapaz de dar un veredicto negativo— y corre la suite entera. Si nadie protesta, esa pieza no
está vigilada por nada, y todos los comprobadores que cuelgan de ella son decorativos.

## Por qué existe, y por qué esta forma y no otra

`--verifica` tenía un pase adversarial que el 2026-08-30 se descubrió **muerto**: `ARTEFACTOS`
estaba vacío, imprimía `0/0 verificados` —que en un informe se lee como un 100 %— y no podía
revivir. Su única mentira era *plantar un fichero en el suelo*, y ninguno de los 33 comprobadores
de esta casa decide mirando el suelo: todos preguntan a git, a GitHub o al sistema operativo. La
máquina hablaba un idioma que aquí no se usa.

Ésta le da la vuelta: en vez de engañar al comprobador **por fuera**, lo opera **por dentro**.

## El argumento que decidió construirla, y no es de opinión

Ese mismo día se midió seis veces, por métodos estáticos, qué partes del arnés estaban probadas:
mirar si un test NOMBRA una función, contar `except` por su forma, buscar con `grep`. Las seis
medidas salieron **falsas**, y las seis eran plausibles — números redondos con nombres de verdad
al lado.

Lo único que dijo la verdad fue romper la pieza y ver quién gritaba. Sobre esa primera corrida:

    _delega                7 comprobadores    694 passed   <- CIEGO
    _fabrica_bug          12 comprobadores      2 failed
    _fabrica_inv           9 comprobadores      1 failed
    canario_de_los_hooks   1 comprobador        5 failed
    guardia_de_commit      1 comprobador        3 failed
    revista_de_runtimes    1 comprobador      694 passed   <- CIEGO

Ocho comprobadores colgando de dos piezas que nadie vigilaba. Ninguna medida estática lo vio.

## Por qué esta mutación y no un catálogo de mutaciones

Las herramientas de mutación al uso generan decenas de variantes por función. Aquí sobra: la
pregunta de este proyecto es una sola, **«¿puede este guardián decir que no?»**, y su negación es
exactamente voltear los `return False`. Una mutación que corresponde 1:1 con el fallo que se teme
vale más que cincuenta que no.

## Lo que NO prueba, dicho antes de que alguien lo confunda

Que la suite cace el sabotaje demuestra que **alguien mira** esa pieza. NO demuestra que la mire
bien, ni que el comprobador sea correcto. Es un suelo, no un techo.

## La trampa prohibida

Si no se puede mutar —el árbol tiene cambios sin guardar, no hay pytest, no se puede escribir el
fichero— esto es **MUDO**. Un 0 de 0 sería «todo verificado», que es la mentira exacta que mató a
la máquina anterior.
"""
from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
TABLERO = RAIZ / "scripts" / "aceptacion.py"

#: Cuánto se le da a la suite entera por cada pieza. Son ~65 s por corrida en esta máquina y hay
#: seis piezas, así que el pase completo ronda los 7 minutos. Es caro y se dice: no se llama en
#: cada ronda, se llama desde `--verifica`, que es el pase adversarial y ya era el sitio.
TIMEOUT_SUITE_S = 900

#: Tests que se descartan del oráculo, con su motivo. ⚠️ Cada entrada aquí AGRANDA el punto ciego,
#: así que va con nombre y fecha o no va.
_DESCARTADOS: dict[str, str] = {
    "tests/test_sabotaje_del_cableado.py":
        "CONTAMINACION PROPIA, medida el 2026-09-01. Mutando `_delega` fallaban 8 tests y SIETE "
        "eran de este fichero: leen `scripts/aceptacion.py` como DATO —para derivar la lista de "
        "piezas, o para calcular la huella de la memoria— asi que cualquier mutacion del tablero "
        "los rompe. Y un test que falla porque EL TEXTO cambio no verifica COMPORTAMIENTO: contarlo "
        "como protesta daba `_delega` por vigilado cuando no lo esta. Quitarlo hace el juez mas "
        "correcto, no mas flojo — se comprobo despues: sin este fichero, `_delega` sale ciego, que "
        "es la verdad. Siguen corriendo en la suite normal; lo que no pueden es hacer de oraculo "
        "sobre el fichero del que ellos mismos leen.",
    "tests/test_ronda_de_tableros.py::test_los_siete_declarados_estan_en_esta_maquina":
        "ROJO desde el 2026-08-31 por un motivo REAL y ajeno a este repo: al sacar el arnes del "
        "repo publico eu-political-observatory, la sincronizacion del worktree del robot borro su "
        "tablero entero, y ese test lo denuncia. Se descarta SOLO como oraculo —un juez que ya "
        "grita no puede distinguir si ha gritado por lo mio— y sigue corriendo en la suite normal, "
        "donde su rojo es la alarma. Se retira de aqui el dia que se decida que hacer con ese "
        "worktree.",
}


#: Dónde se recuerda la última medición. Existe por un motivo de supervivencia, no de comodidad:
#: el pase completo son ~10 min, y un guardián que cuesta diez minutos al día termina desactivado
#: «un momento», que es como mueren los guardianes buenos.
#:
#: Y la caché es SEGURA porque su llave es exactamente lo que puede cambiar la respuesta: el
#: tablero (las piezas y su código) y la suite (el juez). Si ninguno se ha tocado, volver a medir
#: daría lo mismo con certeza, no con esperanza. Se guarda fuera del repo por la misma razón que
#: `.rondas/`: es estado de esta máquina, no del proyecto.
CACHE = Path.home() / "proyectos" / ".rondas" / "sabotaje_cableado.json"


def _llave() -> str:
    """La huella de todo lo que puede cambiar el veredicto: el tablero, la suite, y ESTE fichero.

    ⚠️ Incluirse a sí mismo no es celo: el 2026-08-31 este comprobador dio un VERDE falso por un
    bug propio, y al arreglarlo la memoria habría seguido sirviendo el verde envenenado — porque
    ni el tablero ni un test habían cambiado. Un guardián que se arregla y sigue contestando lo
    que decía roto es peor que uno roto.
    """
    h = hashlib.sha256()
    h.update(Path(__file__).read_bytes())
    h.update(TABLERO.read_bytes())
    for f in sorted((RAIZ / "tests").glob("*.py")):
        h.update(f.name.encode("utf-8"))
        h.update(hashlib.sha256(f.read_bytes()).digest())
    conftest = RAIZ / "tests" / "conftest.py"
    if conftest.is_file():
        h.update(conftest.read_bytes())
    return h.hexdigest()


class NoSePudoMutar(Exception):
    """No se pudo hacer el experimento. Nunca se traduce a «todo vigilado»."""


def _lineas_que_dicen_que_no(fn) -> list[int]:
    """Las líneas de `fn` con un `return False` DE VERDAD, mirando la estructura y no las letras.

    ⚠️ Buscar el texto `return False` fue un error, y se pagó el 2026-09-01: el envoltorio de este
    mismo comprobador no tiene ninguno —es `return _delega(...)`—, pero **su docstring menciona la
    frase** al explicar qué hace. El comprobador mutó su propia prosa, no cambió ningún
    comportamiento, la suite no protestó, y se acusó a sí mismo de estar ciego.

    Un comentario que habla de código no es código. Mirando el árbol sintáctico eso deja de poder
    confundirse: un `ast.Return` cuyo valor es `False`, o una tupla que empieza por `False`, que
    es la forma que usa este tablero (`return False, "motivo"`).
    """
    fuera = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.Return) or n.value is None:
            continue
        v = n.value
        if isinstance(v, ast.Tuple) and v.elts:
            v = v.elts[0]
        if isinstance(v, ast.Constant) and v.value is False:
            fuera.append(n.lineno)
    return sorted(set(fuera))


def piezas_de_cableado(fuente: str) -> list[str]:
    """Las funciones del tablero de las que cuelga al menos un comprobador.

    Se DERIVAN de `COMPROBADORES` en vez de escribirse: una lista a mano envejecería igual que el
    problema que intenta resolver — el día que nazca una pieza nueva, nadie la añadiría, y su punto
    ciego no aparecería en ningún sitio.
    """
    arbol = ast.parse(fuente)
    comp = next((n.value for n in arbol.body
                 if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "COMPROBADORES"),
                None)
    if comp is None:
        raise NoSePudoMutar("el tablero no expone COMPROBADORES")

    directas, fabricas = set(), set()
    for v in comp.values:
        if isinstance(v, ast.Call):
            fabricas.add(getattr(v.func, "id", ""))
        elif getattr(v, "id", None):
            directas.add(v.id)

    # Entra una función sólo si tiene un `return False` PROPIO que negar. Eso deja fuera, a
    # propósito, a los siete envoltorios de una línea (`return _delega(...)`): su cable es
    # `_delega`, y mutarlos por separado gastaría un minuto de suite cada uno para no medir nada
    # nuevo. La pieza que se muta es aquella donde vive de verdad la decisión de decir que no.
    funcs = {n.name: n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)}
    candidatas = (directas | {f for f in fabricas if f}) & set(funcs)
    candidatas.add("_delega")               # la pieza de la que cuelgan mas comprobadores
    return sorted(n for n in candidatas
                  if n in funcs and _lineas_que_dicen_que_no(funcs[n]))


def voltear(fuente: str, funcion: str) -> tuple[str, int]:
    """La fuente con los `return False` de `funcion` vueltos `return True`, y cuántos fueron.

    Es la negación exacta de lo único que se le pide a un guardián: poder decir que no.
    """
    arbol = ast.parse(fuente)
    fn = next((n for n in ast.walk(arbol)
               if isinstance(n, ast.FunctionDef) and n.name == funcion), None)
    if fn is None:
        raise NoSePudoMutar(f"no existe la funcion {funcion}")
    lineas = fuente.split("\n")
    n = 0
    # Sólo las líneas que el ÁRBOL dice que llevan un `return False` de verdad. Recorrer el rango
    # entero buscando el texto mutaba también docstrings y comentarios — ver el porqué, con su
    # caso real, en `_lineas_que_dicen_que_no`.
    for numero in _lineas_que_dicen_que_no(fn):
        i = numero - 1
        if "return False" in lineas[i]:
            lineas[i] = lineas[i].replace("return False", "return True", 1)
            n += 1
    return "\n".join(lineas), n


def _corre_la_suite() -> bool:
    """True si la suite PROTESTA. Un error de pytest cuenta como protesta, no como silencio."""
    orden = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:randomly"]
    for nodo in _DESCARTADOS:
        orden += ["--deselect", nodo]
    r = subprocess.run(orden, cwd=str(RAIZ), capture_output=True,
                       timeout=TIMEOUT_SUITE_S, stdin=subprocess.DEVNULL)
    return r.returncode != 0


def sabotaje_del_cableado(sin_cache: bool = False) -> tuple[bool | None, str]:
    try:
        llave = _llave()
    except OSError as e:
        return None, f"no se pudo leer el tablero ni la suite ({type(e).__name__}): nada medido"
    if not sin_cache:
        try:
            import json
            guardado = json.loads(CACHE.read_text(encoding="utf-8"))
            if guardado.get("llave") == llave:
                # Ni el tablero ni un solo test han cambiado, asi que volver a medir daria lo
                # mismo CON CERTEZA. Se dice que viene de la memoria, porque un verde que no se
                # ha medido hoy tiene que poder distinguirse de uno que si.
                return guardado["ok"], (str(guardado["motivo"])
                                        + f" [medido el {guardado.get('cuando', '?')}; ni el "
                                          "tablero ni la suite han cambiado desde entonces]")
        except (OSError, ValueError, KeyError):
            pass                            # sin memoria utilizable se mide, que es lo caro pero cierto

    ok, motivo = _medir()
    if ok is not None:                      # un MUDO no se recuerda: no es una medicion
        try:
            import datetime
            import json
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps({"llave": llave, "ok": ok, "motivo": motivo,
                                         "cuando": datetime.date.today().isoformat()},
                                        ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return ok, motivo


def _medir() -> tuple[bool | None, str]:
    try:
        sucio = subprocess.run(["git", "status", "--porcelain", str(TABLERO)], cwd=str(RAIZ),
                               capture_output=True, text=True, timeout=120,
                               stdin=subprocess.DEVNULL)
    except OSError as e:
        return None, f"no se pudo preguntar a git ({type(e).__name__}): no se ha mutado nada"
    if sucio.returncode != 0 or sucio.stdout.strip():
        # Mutar sobre cambios sin guardar arriesga perderlos al restaurar. Y no poder hacer el
        # experimento NUNCA es «todo vigilado».
        return None, ("el tablero tiene cambios sin guardar: no se muta sobre trabajo sin "
                      "commitear. Eso NO es «todas las piezas estan vigiladas»")

    original = TABLERO.read_bytes()
    huella = hashlib.sha256(original).hexdigest()
    # El final de línea del fichero se preserva a mano. `write_text` traduce `\n` a `\r\n` en
    # Windows, y sobre un fichero que YA lleva CRLF eso produce `\r\r\n` en cada línea.
    salto = "\r\n" if b"\r\n" in original else "\n"
    try:
        texto = original.decode("utf-8").replace("\r\n", "\n")
        piezas = piezas_de_cableado(texto)
    except (UnicodeDecodeError, SyntaxError, NoSePudoMutar) as e:
        return None, f"no se pudo leer el tablero ({e}): no se ha mutado nada"
    if not piezas:
        return False, "cero piezas de cableado detectadas: sospechoso, no limpio"

    # ⚠️ EL JUEZ TIENE QUE ESTAR SANO ANTES DE JUZGAR, y esto no es ceremonia: si la suite ya
    # falla por su cuenta, TODA mutación parecería «cazada» —la suite protesta igual— y este
    # comprobador saldría VERDE afirmando que las piezas están vigiladas cuando no ha medido nada.
    # Sería la misma mentira que mató a la máquina anterior, con otro disfraz.
    try:
        if _corre_la_suite():
            return None, ("la suite ya falla ANTES de mutar nada, asi que no puede hacer de juez: "
                          "protestaria igual con cualquier sabotaje y esto saldria verde sin haber "
                          "medido nada. Arregla el rojo (o declaralo en _DESCARTADOS con su "
                          "motivo) y vuelve")
    except subprocess.TimeoutExpired:
        return None, f"la suite se cuelga (>{TIMEOUT_SUITE_S // 60} min) ya sin mutar nada"
    except OSError as e:
        return None, f"no se pudo lanzar la suite ({type(e).__name__}): no se ha medido nada"

    ciegas, sin_mutar = [], []
    try:
        for pieza in piezas:
            try:
                mutada, cuantos = voltear(texto, pieza)
            except NoSePudoMutar:
                sin_mutar.append(pieza + " (no se pudo localizar)")
                continue
            if not cuantos:
                # Sin `return False` no hay nada que negar: esa pieza no puede decir que no de
                # todas formas, y eso lo denuncia otro sitio, no aqui.
                sin_mutar.append(pieza + " (sin ningun `return False`)")
                continue
            crudo = mutada.replace("\n", salto).encode("utf-8")
            # ⚠️ LA GUARDA QUE HACE IMPOSIBLE EL FALLO DEL 2026-08-31, y merece leerse.
            #
            # `return False` -> `return True` quita EXACTAMENTE un byte por volteo. Cualquier otro
            # tamaño significa que la escritura ha tocado algo más que la mutación, y entonces la
            # suite puede protestar por ESO — y todas las piezas parecerían vigiladas.
            #
            # Paso de verdad: la primera versión escribía con `write_text`, que sobre un fichero
            # con CRLF produce `\r\r\n` en cada línea. Corrompía las 1.169 líneas, la suite
            # protestaba por la corrupción, y este comprobador dio un VERDE perfecto diciendo que
            # las 9 piezas estaban vigiladas — cuando dos no lo estaban. Un verde falso dentro del
            # comprobador escrito para cazar verdes falsos.
            #
            # Detectarlo no basta: se hace imposible. Si el tamaño no cuadra, no se mide.
            if len(crudo) != len(original) - cuantos:
                raise NoSePudoMutar(
                    f"mutando {pieza} el fichero cambio {len(original) - len(crudo)} bytes y "
                    f"debia cambiar {cuantos} (uno por volteo): la escritura ha tocado algo mas "
                    f"que la mutacion, asi que cualquier veredicto seria falso")
            TABLERO.write_bytes(crudo)
            if not _corre_la_suite():
                ciegas.append(f"{pieza} ({cuantos} retorno(s) volteado(s))")
    except NoSePudoMutar as e:
        return None, f"{e}"
    except subprocess.TimeoutExpired:
        return None, f"la suite se cuelga (>{TIMEOUT_SUITE_S // 60} min): no es un veredicto"
    except OSError as e:
        return None, f"no se pudo lanzar la suite ({type(e).__name__}): no se ha medido nada"
    finally:
        # Se restaura SIEMPRE y se comprueba por huella. Si esto fallara, el repo se quedaria con
        # el tablero saboteado — o sea con todos los guardianes incapaces de decir que no.
        TABLERO.write_bytes(original)
        if hashlib.sha256(TABLERO.read_bytes()).hexdigest() != huella:
            raise SystemExit("FATAL: no se pudo restaurar scripts/aceptacion.py. "
                             "Recuperalo YA con: git checkout -- scripts/aceptacion.py")

    cola = f" ({len(sin_mutar)} sin mutar: {', '.join(sin_mutar)})" if sin_mutar else ""
    if ciegas:
        return False, ("piezas que pueden quedarse INCAPACES DE PONERSE ROJAS sin que ninguna "
                       "prueba se entere: " + "; ".join(ciegas)
                       + ". Todo comprobador que cuelgue de ellas es decorativo" + cola)
    return True, (f"las {len(piezas) - len(sin_mutar)} piezas de cableado estan vigiladas: "
                  f"volver a cada una incapaz de dar un rojo rompe la suite" + cola)


if __name__ == "__main__":
    ok, msg = sabotaje_del_cableado(sin_cache="--sin-cache" in sys.argv)
    print(("MUDO: " if ok is None else "VERDE: " if ok else "ROJO: ") + msg)
    sys.exit(3 if ok is None else 0 if ok else 1)
