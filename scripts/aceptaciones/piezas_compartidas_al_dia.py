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

#: No hay umbral de parecido, y es deliberado. Hubo dos —uno para «divergida» y otro para «son la
#: misma»— y los dos sobraban en cuanto se comparó el CÓDIGO CANÓNICO en vez del texto: medido el
#: 2026-08-26, de las 19 funciones compartidas entre los cinco repos **17 son idénticas byte a
#: byte** y sólo 2 difieren. Después de quitar docstring y formato, una diferencia ya no puede ser
#: de estilo: es de comportamiento, y se reporta sin grados.


#: Divergencias DELIBERADAS, con su motivo escrito. Mismo trato que `SIN_MUTACION`: una exención
#: escrita se revisa; una implícita se hereda.
#:
#: Existe porque sin ella hay rojos que no se pueden cerrar NUNCA. Y un rojo permanente no informa:
#: entrena a mirar para otro lado, que es como muere un tablero.
#:
#: ⚠️ Lo que NO vale aquí es «son distintos y ya». Hace falta decir **por qué las dos versiones son
#: correctas**, o si una lo es y la otra no, arreglarla en vez de apuntarla.
_DIVERGENCIAS_ACEPTADAS = {
    "_verifica": (
        "la misma invariante, en dos sitios distintos y a proposito. mcp_smart_context la mete "
        "DENTRO del gate: `_verifica` exige que el motivo de cada exencion nombre un .py que "
        "exista. capa-normativa la saca a la SUITE, y mas estricta — `tests/"
        "test_coartada_de_los_no_mutables.py` la parte en tres exigencias (que nombre una "
        "coartada, que la coartada EXISTA, y que HABLE del mecanismo que cubre) y ademas vigila "
        "que la lista no nombre fantasmas ni la cuenta salga negativa. "
        "Portar la version de mcp aqui duplicaria una guarda que ya esta, y en el sitio donde se "
        "ejecuta con todo lo demas. Medido el 2026-08-29: de las 31 exenciones de capa-normativa, "
        "la comprobacion de mcp tumbaria UNA (`revista-de-runtimes`, cuya coartada es una "
        "autoprueba dentro del propio guion y no un fichero .py), y las de capa-normativa la dan "
        "por buena a proposito."
    ),
    "main": (
        "capa-normativa imprime con un ✅ las promesas ya CUMPLIDAS y retiradas del tablero, para "
        "que retirar una no sea lo mismo que borrarla. Los otros repos no tienen esa diferencia "
        "porque NO TIENEN la tabla `CUMPLIDAS` — medido el 2026-08-29: cero entradas en eu y en "
        "mcp. Asi que no es que su `main` se haya quedado atras: es que no han adoptado la "
        "facilidad, y copiar las tres lineas alli solo añadiria codigo que nunca entra. "
        "⚠️ Esto NO es «da igual»: que una promesa cumplida siga visible es util, y adoptarlo en "
        "los otros dos merece la pena. Pero es ADOPTAR una facilidad, con su tabla, no propagar "
        "una linea — y eso es una decision de cada tablero."
    ),
}


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


def _codigo(nodo) -> str:
    """El cuerpo EJECUTABLE de una función, sin su docstring y reimpreso de forma canónica.

    ## Por qué se quita la docstring

    Medido el 2026-08-26: `_solo_el_comando` daba 0,46 de parecido entre capa-normativa y
    mcp_smart_context, y el detector la marcaba como divergida. Comparando **sólo lo ejecutable**
    da **1,00**: son idénticas. Los cinco de diferencia eran prosa — cada repo cuenta la misma
    historia con sus palabras.

    En un código con docstrings de veinte líneas como éste, comparar el texto entero convierte cada
    pieza compartida en un falso positivo permanente. Y un detector que grita siempre se apaga.

    ## Por qué se reimprime en vez de comparar el fuente

    `ast.unparse` normaliza sangrías, comillas y saltos, así que una diferencia de formato deja de
    contar como diferencia de comportamiento — que es lo único que aquí importa.
    """
    cuerpo = list(nodo.body)
    if (cuerpo and isinstance(cuerpo[0], ast.Expr)
            and isinstance(cuerpo[0].value, ast.Constant)
            and isinstance(cuerpo[0].value.value, str)):
        cuerpo = cuerpo[1:]
    try:
        return "\n".join(ast.unparse(x) for x in cuerpo)
    except Exception:  # noqa: BLE001
        return ""


def _funciones(texto: str) -> dict[str, str]:
    """{nombre: código ejecutable} de las funciones de nivel superior. Con `ast`, no con regex.

    Un regex sobre `def` no sabe dónde acaba la función, así que no puede comparar cuerpos — y
    comparar cuerpos es justo lo que hace falta para distinguir «la misma pieza» de «dos funciones
    que casualmente se llaman igual».
    """
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return {}
    return {n.name: _codigo(n) for n in arbol.body
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
            # Comparación EXACTA sobre el código canónico, sin umbral difuso. Medido el
            # 2026-08-26: de las 19 funciones compartidas entre los cinco repos, **17 son
            # idénticas byte a byte** una vez quitadas docstring y formato, y sólo 2 difieren
            # (`main` y `_verifica`). Con esos números un umbral no aporta nada y se lleva por
            # delante lo que sí importa: la diferencia real de `main` es del 5 % —
            # capa-normativa muestra las promesas ya cumplidas y los demás no— y cualquier
            # umbral razonable la habría dado por igual.
            #
            # Después de canonicalizar, una diferencia YA NO PUEDE ser de estilo: es de
            # comportamiento. Así que se reporta, sin grados.
            por_codigo: dict[str, list[str]] = {}
            for r in donde:
                por_codigo.setdefault(funcs[r][nombre], []).append(r)
            mayoria = max(por_codigo.values(), key=len)
            divergidas = sorted(r for r in donde if r not in mayoria)

            faltan = sorted(set(funcs) - set(donde))
            # Se exige que al menos DOS copias coincidan antes de llamar «falta» a la ausencia en
            # una tercera. Si cada copia dice una cosa distinta, no hay version de referencia que
            # propagar — hay que decidir cual es la buena, y eso es criterio.
            if faltan and len(mayoria) >= 2:
                # «Falta» no es lo mismo que «deberia tenerla», y confundirlas produce ruido.
                # MEDIDO el 2026-08-26: `_fabrica_bug` falta en mcp_smart_context, pero mcp NO
                # TIENE tabla `_BUGS` ni una sola llamada a esa funcion. Copiarla alli seria
                # meter codigo muerto — peor que no propagar.
                #
                # Se intento distinguirlas mirando si el nombre aparece en el repo destino, y NO
                # discrimina: las cinco piezas que faltan dan cero apariciones, tests incluidos.
                # Lo que si separa los dos casos es QUE CLASE de pieza es:
                #
                #   · un TEST no tiene nunca sitio donde se le llame, y esta pensado para estar en
                #     todas partes: su ausencia es un hueco de verdad.
                #   · una pieza de maquinaria solo hace falta si ese repo usa la facilidad. Que mcp
                #     no lleve `_BUGS` no es un desfase: es una diferencia de diseño, y decidir si
                #     la adopta es criterio, no automatismo.
                clase = "sin propagar" if nombre.startswith("test_") else "sin adoptar"
                fuera.append((rel, nombre, clase, donde, faltan))
            if divergidas:
                # Sin mayoria NO se puede decir «esta se desvio», pero SI se puede decir que
                # nadie ha decidido cual vale — y eso es lo que se reporta (`sin decidir`), en
                # ROJO. Corregido el 2026-08-30: antes esto solo se informaba, con el argumento de
                # que decidir es criterio y no automatismo. El argumento falla, y se vio con un
                # caso real: `_git` en `scripts/aceptacion_de_la_tarea.py` tenia dos versiones, y
                # una era CLARAMENTE mejor —la de JobHunter lleva `cwd` (lo que evita juzgar el
                # arbol equivocado desde el worktree del robot) y `stdin=DEVNULL` (la proteccion
                # contra el WinError 6)—. Se sabia cual era la buena, y el tablero lo mencionaba
                # de pasada al final de una linea VERDE.
                #
                # El guardian no necesita saber cual version es correcta: eso sigue siendo
                # criterio. Necesita saber si ALGUIEN HA MIRADO, y eso si lo puede decir una
                # maquina. Se cierra unificando, o escribiendo en _DIVERGENCIAS_ACEPTADAS por que
                # las dos son correctas.
                #
                # ⚠️ Y por eso la mayoria NO es la referencia: con tres copias viejas y una
                # arreglada, la mayoria es la vieja, y usarla como patron señalaria el ARREGLO
                # como el error. Los grupos se imprimen como informacion, no como veredicto.
                #
                # Cuando SI hay mayoria se nombra el grupo entero, no un representante: saber que
                # dos repos coinciden y otros dos se salieron dice de que lado esta el arreglo.
                if nombre in _DIVERGENCIAS_ACEPTADAS:
                    clase = "divergencia aceptada"
                else:
                    clase = "divergida" if len(mayoria) >= 2 else "sin decidir"
                fuera.append((rel, nombre, clase, sorted(mayoria), divergidas))
    return fuera


def piezas_compartidas_al_dia() -> tuple[bool, str]:
    try:
        atrasadas = desfases()
    except NoSePudoMirar as e:
        return False, f"no se pudo mirar ({e}). Eso NO es «todo al dia»."

    sin_propagar = [x for x in atrasadas if x[2] == "sin propagar"]
    # `divergida` y `sin decidir` van JUNTAS al rojo: en las dos la pieza EXISTE en dos o mas
    # sitios con codigo distinto, o sea que hay una diferencia de comportamiento que nadie ha
    # resuelto. Que haya mayoria o no cambia lo que se puede DECIR, no si hay que mirarlo.
    divergidas = [x for x in atrasadas if x[2] in ("divergida", "sin decidir")]
    # `sin adoptar` se queda informando, y su argumento SI se sostiene: la pieza no esta, y su
    # ausencia puede ser diseño —que mcp no lleve `_fabrica_bug` es que no tiene tabla `_BUGS`—.
    # Ausencia y desacuerdo no son lo mismo, y meterlos en el mismo saco escondia el segundo.
    sin_adoptar = [x for x in atrasadas if x[2] in ("sin adoptar", "divergencia aceptada")]

    # `sin adoptar` se INFORMA pero no pone rojo: es una diferencia de diseño entre repos, y
    # decidir si uno adopta una facilidad del otro es criterio. Un rojo que no se puede cerrar sin
    # tomar una decisión de diseño se aprende a ignorar, y ahí empieza a morir el tablero.
    cola = ""
    if sin_adoptar:
        nombres = sorted({f for _, f, _, _, _ in sin_adoptar})
        # Ya no hay «sin referencia» aqui: esas pasaron al rojo el 2026-08-30. Queda el
        # recuento de las aceptadas por escrito, que es lo unico que conviene tener a la vista
        # —una exencion escrita se revisa; una implicita se hereda—.
        cuantas_sin_ref = sum(1 for x in sin_adoptar if x[2] == "divergencia aceptada")
        detalle_ref = (f", {cuantas_sin_ref} divergencia(s) aceptada(s) por escrito"
                       if cuantas_sin_ref else "")
        cola = (f" (aparte, sin poner rojo: {len(sin_adoptar)} pieza(s) que piden criterio y no "
                f"automatismo{detalle_ref} — {', '.join(nombres[:4])})")

    if not sin_propagar and not divergidas:
        return True, ("ninguna pieza compartida se ha quedado atras ni ha divergido" + cola)

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
        # Se separan al IMPRIMIR aunque compartan destino, porque piden cosas distintas: una
        # divergida tiene un grupo mayoritario del que salió, y una sin decidir no tiene de que
        # salirse — tiene dos versiones y ningun arbitro.
        con_patron = sorted({f for _, f, q, _, _ in divergidas if q == "divergida"})
        sin_arbitro = sorted({f for _, f, q, _, _ in divergidas if q == "sin decidir"})
        if con_patron:
            partes.append(f"{len(con_patron)} DIVERGIDA(S): " + ", ".join(con_patron[:5]))
        if sin_arbitro:
            partes.append(f"{len(sin_arbitro)} SIN DECIDIR (dos versiones y nadie ha elegido; "
                          "se cierra unificando o escribiendo por que las dos valen): "
                          + ", ".join(sin_arbitro[:5]))

    return False, (" · ".join(partes) + ". El repo que se queda atras NO se pone rojo por su "
                   "cuenta: simplemente no tiene el detector, asi que no detecta. Y una funcion "
                   "divergida es peor, porque desde fuera parece propagada." + cola)


if __name__ == "__main__":
    ok, msg = piezas_compartidas_al_dia()
    print(("VERDE: " if ok else "ROJO: ") + msg)
    if not ok and "--detalle" in sys.argv:
        print()
        for rel, funcion, que, tienen, otros in desfases():
            print(f"  [{que}] {rel} :: {funcion}")
            print(f"      la tienen igual: {', '.join(tienen)}")
            etiqueta = {"divergencia aceptada": "distinta A PROPOSITO en",
                        "sin decidir": "otra version, sin arbitro, en",
                        "sin propagar": "le falta a",
                        "sin adoptar": "no usa esa facilidad",
                        "divergida": "divergida en"}[que]
            print(f"      {etiqueta}: {', '.join(otros)}")
    sys.exit(0 if ok else 1)
