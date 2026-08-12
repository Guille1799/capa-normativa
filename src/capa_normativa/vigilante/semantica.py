"""SEM001 — la POLARIDAD del nombre contra la `semantics` de la norma que resuelve.

## Por qué existe (medido, no supuesto — 2026-08-12)

Migrando el caso 55 estuve a punto de apuntar `_PLANNED_LOAD_CARB_GKG_CAP` —un **tope** del
carbohidrato extra en días largos— a la norma `carb_floor_g_per_kg_ffm`, que es un **suelo**
diario. Los dos valen 1,5. La candidatura era legítima (comparten valor y el token `CARB`) y lo
único que lo impidió fue leer el comentario del sitio.

Después se midió qué habría pasado si no lo hubiera leído: se hizo la migración equivocada con el
ritual completo (constante fuera del baseline, tope bajado) y se corrió el gate del inquilino.

    2634 passed, 1 skipped, 1 xfailed

**Pasa en verde.** Y se entiende: todo el arnés comprueba que el VALOR no cambie, y el valor era
1,5 antes y 1,5 después. Nada miraba el SIGNIFICADO. El error habría quedado permanente e
invisible: un techo funcionando como piso, con procedencia falsa y aspecto de estar bien hecho.

Y la condición que lo hace posible —que los dos números coincidan— es exactamente la condición que
hace que un triaje por valor te lo proponga. O sea: el fallo no es raro, es el modo de fallo
NATURAL de este trabajo.

## Qué hace, y qué NO

Salta cuando el NOMBRE de una constante declara una polaridad (`..._CAP`, `..._FLOOR`) y la norma
que resuelve declara la CONTRARIA (`semantics: suelo` frente a `semantics: techo`). Es una
contradicción que una máquina puede ver **sin entender el dominio**: no sabe de carbohidratos, sabe
que un tope no es un piso.

⚠️ **Lo que NO cubre, dicho aquí para que nadie lo confunda con cobertura:** dos constantes que son
preguntas distintas cuando **ninguna** se llama tope ni suelo. El caso de las cuatro dosis de
proteína del caso 56 —pre-entreno, post-entreno, pre-sueño, todas «gramos de proteína»— es
invisible para esto. Ahí el único defensor sigue siendo leer el comentario del sitio. Este detector
tapa **una** clase de fallo, la que se pudo hacer determinista, y presentarlo como más que eso
sería el guardián que falla en silencio otra vez.

## Cómo se mantiene callado

Dos condiciones a la vez, y la conjunción es lo que evita el detector que dispara para todo:

1. el nombre trae una palabra de polaridad **semántica**, y
2. la norma que resuelve declara la polaridad opuesta.

Un slug que no esté en el mapa se ignora **en silencio y a propósito**: el inquilino puede pasar
solo las normas que le interesen sin que el detector invente hallazgos sobre lo que no conoce.

Y se descartó a conciencia meter `_MIN`/`_MAX` desnudos en el vocabulario: en el triaje del
inquilino esa misma tentación marcó el 100 % de las constantes —casi siempre son tamaños de muestra
(`_MIN_READINGS`, `_LAPS_MIN_N`)— o sea que no marcaba nada. Solo lo SEMÁNTICO.

## Frontera

No importa `capa_normativa.registry`, igual que el resto del vigilante: recibe el mapa
`slug → semantics` ya construido. El inquilino lo saca de su registro en una línea. Así el módulo
se puede probar con un `dict` y la frontera de arquitectura del 2026-08-09 sigue en pie.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .hallazgo import Hallazgo

#: Polaridad que declara el NOMBRE de la constante. Solo palabras SEMÁNTICAS (ver docstring).
#: El delimitador es `(?:^|_)…(?:_|$)` y no `\b` porque el guion bajo ES carácter de palabra:
#: con `\b` no casaría `_CARB_FLOOR_G_PER_KG_FFM`, que es justo la forma más común.
#: De paso, así `_CAPACITY_X` no cuenta como `CAP`.
_POLARIDAD_NOMBRE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("techo", re.compile(r"(?:^|_)(CAP|TOPE|TECHO|CEILING)(?:_|$)", re.I)),
    ("suelo", re.compile(r"(?:^|_)(FLOOR|SUELO|PISO)(?:_|$)", re.I)),
)

#: `semantics` de norma que CONTRADICEN cada polaridad de nombre. Vocabulario por defecto: el que
#: usa el inquilino real (`techo`, `cap`, `suelo`) más los equivalentes en inglés, porque un
#: registro nuevo puede escribirlo en cualquiera de los dos y fallar en silencio no es opción.
#: Es un parámetro: crece con la evidencia, no con la imaginación.
OPUESTOS: Mapping[str, frozenset[str]] = {
    "techo": frozenset({"suelo", "piso", "floor", "minimo", "mínimo"}),
    "suelo": frozenset({"techo", "tope", "cap", "ceiling", "maximo", "máximo"}),
}

_EXCLUIR = {".git", "__pycache__", "venv", ".venv", "node_modules", "build", "dist",
            ".claude", "_archivo", "site-packages"}


def _pythons(raiz: Path) -> Iterable[Path]:
    for p in sorted(raiz.rglob("*.py")):
        if not _EXCLUIR.intersection(p.parts):
            yield p


def _polaridad(nombre: str) -> str | None:
    for pol, rx in _POLARIDAD_NOMBRE:
        if rx.search(nombre):
            return pol
    return None


def _slug_resuelto(nodo: ast.AST) -> str | None:
    """El slug de un `X.resolve("slug", ...)`, con o sin `.value` detrás.

    No exige que el receptor se llame `NORMS`: cualquier `.resolve()` con un literal de texto
    vale. Es deliberado —el inquilino puede nombrar su registro como quiera— y es seguro porque
    un slug que no esté en el mapa se ignora.
    """
    if isinstance(nodo, ast.Attribute):        # …resolve(...).value
        nodo = nodo.value
    if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
            and nodo.func.attr == "resolve" and nodo.args):
        return None
    primero = nodo.args[0]
    if isinstance(primero, ast.Constant) and isinstance(primero.value, str):
        return primero.value
    return None


def _asignaciones(arbol: ast.Module) -> Iterable[tuple[str, str, int]]:
    """(nombre, slug, línea) de cada constante que resuelve una norma."""
    for n in ast.walk(arbol):
        if isinstance(n, ast.AnnAssign):
            pares = [(n.target, n.value)] if n.value else []
        elif isinstance(n, ast.Assign):
            pares = []
            for destino in n.targets:
                # `A, B = resolve(x), resolve(y)` — se emparejan por posición. Si las longitudes
                # no cuadran se descarta el grupo: adivinar el emparejamiento sería peor que
                # no mirarlo.
                if isinstance(destino, ast.Tuple) and isinstance(n.value, ast.Tuple):
                    if len(destino.elts) == len(n.value.elts):
                        pares.extend(zip(destino.elts, n.value.elts))
                else:
                    pares.append((destino, n.value))
        else:
            continue
        for destino, valor in pares:
            if isinstance(destino, ast.Name) and valor is not None:
                slug = _slug_resuelto(valor)
                if slug:
                    yield destino.id, slug, getattr(destino, "lineno", 0)


def revisar_semantica(repo: Path | str,
                      semantica: Mapping[str, str] | None = None,
                      *,
                      opuestos: Mapping[str, frozenset[str]] | None = None,
                      ) -> list[Hallazgo]:
    """Busca constantes cuyo nombre contradice la `semantics` de la norma que resuelven.

    `semantica` es el mapa `slug -> semantics` del inquilino. Se construye en una línea desde el
    registro, y pasarlo (en vez de leerlo) es lo que mantiene la frontera:

        {s: NORMS.norma(s).semantics for s in NORMS.slugs()}

    Sin mapa no hay nada que comparar y devuelve `[]` — pero NO en silencio: eso sería el gate
    que pasa por vacío, el modo de fallo que este arnés persigue. El inquilino tiene que
    comprobar con un test que su mapa llega lleno (ver README).
    """
    repo = Path(repo)
    if not repo.exists():
        raise FileNotFoundError(repo)
    tabla = dict(semantica or {})
    if not tabla:
        return []
    contrarios = dict(opuestos or OPUESTOS)

    fuera: list[Hallazgo] = []
    for f in _pythons(repo):
        try:
            arbol = ast.parse(f.read_text("utf-8-sig", errors="ignore"))
        except SyntaxError:
            continue                       # lo suyo es SYN001, no este detector
        for nombre, slug, linea in _asignaciones(arbol):
            sem = tabla.get(slug)
            if not sem:
                continue                   # slug desconocido: callar, no inventar
            pol = _polaridad(nombre)
            if pol and str(sem).strip().lower() in contrarios.get(pol, frozenset()):
                rel = f.relative_to(repo).as_posix()
                fuera.append(Hallazgo(
                    detector="semantica",
                    codigo="SEM001",
                    fichero=rel,
                    linea=linea,
                    mensaje=(f"`{nombre}` dice {pol.upper()} y resuelve `{slug}`, que declara "
                             f"`semantics: {sem}` — la polaridad CONTRARIA. Mismo número, "
                             f"significado opuesto."),
                    arreglo=(
                        f"Comprueba qué pregunta responde de verdad `{nombre}` leyendo su "
                        f"COMENTARIO en {rel}:{linea}, no su valor. Si es un {pol}, `{slug}` no "
                        f"es su norma aunque el número coincida: necesita su PROPIA norma con su "
                        f"propia evidencia. Si de verdad es lo mismo, el nombre miente y hay que "
                        f"renombrarlo. Lo que NO vale es dejarlo: un valor correcto con "
                        f"procedencia equivocada es peor que un valor sin procedencia, porque "
                        f"parece resuelto."),
                ))
    return fuera
