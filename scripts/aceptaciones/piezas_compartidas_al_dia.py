"""Una pieza que vive en varios repos no puede quedarse atrás en uno solo.

## El problema, medido el 2026-08-25

Cinco repos independientes comparten piezas: el mismo `scripts/aceptacion.py`, el mismo
`tests/test_inv_ejecutan_de_verdad.py`. No son librerías compartidas — son **copias**. Y nada sabe
que son la misma cosa: git no las relaciona, ningún tablero las compara, y el único vínculo es que
alguien se acuerde de que existen en plural.

Ese día se arregló una comprobación en `capa-normativa` y `mcp_smart_context` y **no llegó a los
otros tres**. La comprobación anterior de la misma familia sí estaba en los seis árboles — o sea
que la propagación funciona *cuando alguien se acuerda*, y falla en silencio cuando no.

Y falla hacia el lado peligroso: el repo que se queda atrás **no se pone rojo**. Simplemente no
tiene el detector, así que no detecta, y su tablero sigue verde diciendo que todo está bien.

## Por qué la lista de piezas se DERIVA y no se escribe

Una lista escrita a mano envejece exactamente igual que el problema que intenta resolver: el día
que nace una pieza compartida nueva, nadie la añade. Aquí se deriva de los propios ficheros — misma
ruta relativa en dos o más repos — y así una pieza nueva entra sola.

Para que no sea ruido, «la misma pieza» no es «el mismo nombre»: se exige que el contenido se
parezca de verdad. `README.md` está en los cinco y no son la misma pieza.

## Qué cuenta como quedarse atrás

Una **función con nombre** que está en dos o más copias y falta en otra. Se eligen funciones y no
líneas porque son unidades con nombre: se puede decir *qué* falta y *dónde*, que es lo único que
convierte un aviso en trabajo. Un diff línea a línea entre copias que han divergido legítimamente
sería ruido puro.

Exigir **dos o más** presencias, y no una, es deliberado: algo que existe en un solo sitio no es
una pieza compartida que se quedó atrás, es código propio de ese repo.

## La trampa prohibida

Si no se puede leer un repo, esto es **ROJO por no haber podido mirar**. Y si no se descubre
ninguna pieza compartida, también: los cinco repos comparten el arnés, así que cero es un
resultado sospechoso, no una máquina limpia.
"""
from __future__ import annotations

import ast
import difflib
import os
import subprocess
import sys
from pathlib import Path

RAIZ_PROYECTOS = Path(os.environ.get("PROYECTOS_RAIZ") or Path.home() / "proyectos")

#: Los repos INDEPENDIENTES. Los `*-ralph` se excluyen a propósito: son worktrees de éstos, así que
#: una diferencia con ellos no es falta de propagación — es una rama sin fusionar, que ya tiene su
#: propio guardián (`trabajo-del-robot-sin-fusionar`). Confundir las dos cosas convierte un problema
#: mecánico en uno de arquitectura.
_REPOS = ("capa-normativa", "mcp_smart_context", "eu-political-observatory",
          "ponerse_wenorro", "JobHunter")

#: Por debajo de esto, dos funciones con el mismo nombre **han divergido**: comparten poco más que
#: el nombre. Medido el 2026-08-25: `_solo_el_comando` coincide 0,46 entre capa-normativa y mcp.
_PARECIDO = 0.60

#: Por encima de esto, dos copias **son la misma pieza**. Medido el mismo día: la maquinaria que sí
#: está sincronizada coincide al 1,00 (`_fabrica_inv`, `_salida_resistente`) o al 0,97 (`main`).
#: 0,90 deja sitio a una diferencia de una línea sin llamarla desincronización.
_COINCIDEN = 0.90

#: `ratio()` es cuadrático, así que se compara sobre una muestra. 4.000 caracteres son unas cien
#: líneas: de sobra para una función, y barato de calcular.
_TOPE_MUESTRA = 4_000


class NoSePudoMirar(Exception):
    """No se pudo leer algo. Nunca se traduce a «está todo al día»."""


def _seguidos(repo: Path) -> list[str]:
    r = subprocess.run(["git", "ls-files"], cwd=str(repo), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300,
                       stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise NoSePudoMirar(f"git no contesta en {repo.name}")
    return [x for x in r.stdout.splitlines() if x.endswith(".py")]


def _repos_vivos() -> list[Path]:
    fuera = [RAIZ_PROYECTOS / n for n in _REPOS]
    fuera = [p for p in fuera if (p / ".git").exists()]
    if len(fuera) < 2:
        raise NoSePudoMirar(f"solo {len(fuera)} repos legibles: no hay nada que comparar")
    return fuera


def _funciones(texto: str) -> dict[str, str]:
    """{nombre: fuente} de las funciones de nivel superior. Con `ast`, no con regex.

    Un regex sobre `def` no sabe dónde acaba la función, así que no puede comparar cuerpos — y
    comparar cuerpos es justo lo que hace falta para distinguir «la misma pieza» de «dos funciones
    que casualmente se llaman igual».
    """
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return {}
    lineas = texto.splitlines(keepends=True)
    return {n.name: "".join(lineas[n.lineno - 1:n.end_lineno])
            for n in arbol.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def desfases() -> list[tuple[str, str, str, list[str], list[str]]]:
    """(ruta, función, qué pasa, quién la tiene, a quién le falta o quién divergió).

    ## Por qué la unidad es la FUNCIÓN y no el fichero

    La primera versión comparaba ficheros enteros y no servía, medido el 2026-08-25: los
    `scripts/aceptacion.py` de capa-normativa y mcp_smart_context se parecen un **3 %**, porque el
    grueso de cada uno es su tabla de promesas, que es distinta por definición. Comparándolos como
    ficheros, o no son la misma pieza —y entonces no se mira nada— o el umbral se afloja tanto que
    «misma ruta» pasa a ser el único filtro.

    Pero **dentro** de esos ficheros al 3 % hay maquinaria idéntica: `_fabrica_inv` y
    `_salida_resistente` coinciden al **1.00** en los tres repos. Ésa es la pieza compartida de
    verdad, y es la que puede quedarse atrás.

    ## Los dos desenlaces

    - **sin propagar**: la función está en 2+ repos con cuerpos que coinciden, y falta en otro.
    - **divergida**: está en todos, pero un cuerpo se ha ido por su cuenta. Medido el mismo día:
      `_solo_el_comando` está en los tres y sólo coincide un 0,46 — y es justo la función del fallo
      de esa noche. Ese caso el detector de ausencias no lo ve, y es más peligroso, porque desde
      fuera parece propagado.
    """
    repos = _repos_vivos()

    por_ruta: dict[str, list[Path]] = {}
    for repo in repos:
        for rel in _seguidos(repo):
            por_ruta.setdefault(rel, []).append(repo)

    compartidas = {k: v for k, v in por_ruta.items() if len(v) >= 2}
    if not compartidas:
        raise NoSePudoMirar("no se descubrio ninguna pieza compartida: los cinco repos comparten "
                            "el arnes, asi que cero es sospechoso")

    fuera = []
    for rel, repos_con in sorted(compartidas.items()):
        funcs: dict[str, dict[str, str]] = {}
        for repo in repos_con:
            try:
                funcs[repo.name] = _funciones(
                    (repo / rel).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
        if len(funcs) < 2:
            continue

        for nombre in sorted(set().union(*[set(d) for d in funcs.values()])):
            donde = sorted(r for r in funcs if nombre in funcs[r])
            if len(donde) < 2:
                # En un solo sitio no es una pieza que se quedo atras: es codigo propio.
                continue
            base = donde[0]
            ratios = {
                otro: difflib.SequenceMatcher(
                    None, funcs[base][nombre][:_TOPE_MUESTRA],
                    funcs[otro][nombre][:_TOPE_MUESTRA]).ratio()
                for otro in donde[1:]
            }

            iguales = [r for r, v in ratios.items() if v >= _COINCIDEN]
            divergidas = sorted(r for r, v in ratios.items() if v < _PARECIDO)

            faltan = sorted(set(funcs) - set(donde))
            if faltan and len(iguales) + 1 >= 2:
                fuera.append((rel, nombre, "sin propagar", donde, faltan))
            if divergidas:
                fuera.append((rel, nombre, "divergida", [base], divergidas))
    return fuera


def piezas_compartidas_al_dia() -> tuple[bool, str]:
    try:
        atrasadas = desfases()
    except NoSePudoMirar as e:
        return False, f"no se pudo mirar ({e}). Eso NO es «todo al dia»."

    if not atrasadas:
        return True, "ninguna pieza compartida se ha quedado atras ni ha divergido"

    sin_propagar = [x for x in atrasadas if x[2] == "sin propagar"]
    divergidas = [x for x in atrasadas if x[2] == "divergida"]

    partes = []
    if sin_propagar:
        porq: dict[str, int] = {}
        for _, _, _, _, faltan in sin_propagar:
            for r in faltan:
                porq[r] = porq.get(r, 0) + 1
        partes.append(f"{len(sin_propagar)} SIN PROPAGAR (" +
                      ", ".join(f"{k} le faltan {v}" for k, v in
                                sorted(porq.items(), key=lambda x: -x[1])) + ")")
    if divergidas:
        nombres = sorted({f"{f}" for _, f, _, _, _ in divergidas})
        partes.append(f"{len(divergidas)} DIVERGIDA(S): " + ", ".join(nombres[:5]))

    return False, (" · ".join(partes) + ". El repo que se queda atras NO se pone rojo por su "
                   "cuenta: simplemente no tiene el detector, asi que no detecta. Y una funcion "
                   "divergida es peor, porque desde fuera parece propagada.")


if __name__ == "__main__":
    ok, msg = piezas_compartidas_al_dia()
    print(("VERDE: " if ok else "ROJO: ") + msg)
    if not ok and "--detalle" in sys.argv:
        print()
        for rel, funcion, que, tienen, otros in desfases():
            print(f"  [{que}] {rel} :: {funcion}")
            print(f"      la tienen igual: {', '.join(tienen)}")
            print(f"      {'le falta a' if que == 'sin propagar' else 'divergida en'}: "
                  f"{', '.join(otros)}")
    sys.exit(0 if ok else 1)
