"""ARB — un comprobador que, al ejecutarse, mira un árbol HERMANO en vez del suyo.

## Por qué existe (medido el 2026-08-22)

Un agente autónomo trabaja encerrado en su propio *worktree* —una copia del repo en otra
carpeta— para no pisar lo que el humano tenga a medias. El trato es: dentro puede equivocarse
gratis, porque si la aceptación sale roja el bucle deshace y queda como estaba.

Ese trato se rompe entero si el comprobador mira **la copia de al lado**. El agente arregla su
árbol, el comprobador abre el otro, lo ve sin arreglar, dice ROJO, y el bucle **destruye el
trabajo correcto**. Y por la mañana el registro dice lo mismo que si el agente no hubiera hecho
nada, porque lo único que se guarda es el veredicto, no el motivo del veredicto.

> Un rojo no dice «falta trabajo». Dice «la comprobación no salió bien». Son dos hechos
> distintos que emiten exactamente la misma señal.

Peor: la reacción del bucle —deshacer— **borra la prueba** que habría distinguido un caso del
otro. Es un fallo sin síntoma, y por eso hay que cazarlo con una máquina y no con la vista.

## Por qué se OBSERVA en vez de LEERSE

La versión barata de esto es un *lint*: buscar rutas absolutas escritas a mano en el fuente de
cada comprobador. Se descartó porque **el fuente no es donde ocurre el fallo**. Tres formas
reales, de estos mismos repos, en las que una ruta acaba mal sin que nadie la haya escrito:

  1. **Variable de entorno.** Ya pasó: `GIT_DIR` secuestró a los detectores, que escanearon
     otro repositorio, no encontraron nada y **declararon todo limpio** (commit `d216e5e`).
  2. **Paquete instalado que tapa al fuente.** Medido el 2026-08-23: el venv de
     `mcp_smart_context` tiene `capa_normativa` **0.7.0** instalada mientras el repo va por la
     0.16.2. Una sonda que ahí haga `import capa_normativa` examina código congelado hace nueve
     versiones. Cero rutas escritas.
  3. **Rutas relativas que se escapan.** `../otro-arbol/x.py` no tiene nada de absoluto y sale
     del árbol igual.

Ninguna de las tres la ve un lint. Las tres las ve esto, porque no pregunta *«¿está bien escrita
la dirección?»* —que tiene mil formas de salir mal— sino **«¿qué has tocado?»**, que tiene una.

Y hay una cuarta que ni se detecta ni hace falta detectar, porque se **impide**: la deriva del
directorio de trabajo. Cada comprobador se ejecuta desde su propio árbol (`os.chdir`), así que
una ruta relativa normal resuelve dentro de él por construcción. Prevenir sale más barato que
diagnosticar, y aquí además evita acusar a sondas sanas de un fallo que sería de quien mide.

## La frontera exacta: hermano, no «fuera»

Sólo se acusa de tocar un **worktree hermano del mismo repo**. Y es a propósito:

- tocar OTRO repo puede ser legítimo (un comprobador que audita el manifiesto de al lado);
- tocar la carpeta propia es lo normal;
- pero tocar *el mismo fichero, en la otra copia* no tiene ningún caso de uso honesto. Es
  siempre el mismo error: «esto, pero en el árbol equivocado».

Esa es la única regla con señal alta, y por eso es la única que hay.
"""

from __future__ import annotations

import builtins
import io
import os
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .hallazgo import Hallazgo

DETECTOR = "arbol_propio"
CODIGO = "ARB001"

#: Cómo se tocó la ruta. No es cosmético: `ejecuto` es el caso que un lint jamás vería, porque
#: la ruta puede venir de una variable de entorno resuelta en ese instante.
_ABRIO, _CONSULTO, _EJECUTO = "abrio", "consulto", "ejecuto"

#: Las puertas por las que un proceso puede tocar un fichero. La lista es larga a la fuerza, y
#: la razón se midió: **parchear `os.stat` no captura NADA en Windows**. Desde CPython 3.12
#: `os.path.exists` es una función escrita en C (`nt._path_exists`) que no pasa por `os.stat`,
#: y `pathlib.Path.exists` delega en ella. O sea que la puerta más usada de todas —preguntar si
#: un fichero existe— era invisible para la primera versión de esto, y el test lo cazó.
#:
#: Por eso se parchea por NOMBRE en cada módulo y clase, en vez de confiar en que todo acabe
#: pasando por una función común: en CPython moderno ya no es verdad que lo haga.
_PUERTAS = [
    (builtins, "open", _ABRIO),
    (io, "open", _ABRIO),
    # ⚠️ `Path.open` NO es redundante con `io.open`, y sólo se nota en Python 3.10.
    #
    # En 3.11+ `pathlib.Path.open()` llama a `io.open` por su nombre de módulo, así que el parche
    # de arriba lo caza. En 3.10 pasa antes por el *accessor* interno de pathlib —una capa que
    # desapareció en 3.11— y NO toca `io.open`: el detector se quedaba ciego a la forma más
    # habitual de abrir un fichero en código moderno.
    #
    # MEDIDO el 2026-08-30, el día en que la CI empezó a probar 3.10 de verdad:
    # `test_se_ve_a_traves_de_pathlib` esperaba 1 hallazgo y encontraba 0. Y 3.10 no es una
    # versión cualquiera aquí: es la que `requires-python = ">=3.10"` PROMETE, o sea que el
    # detector llevaba ciego desde siempre en la versión mínima que el paquete declara soportar.
    (Path, "open", _ABRIO),
    (os, "stat", _CONSULTO),
    (os, "lstat", _CONSULTO),
    (os, "listdir", _CONSULTO),
    (os, "scandir", _CONSULTO),
    (os.path, "exists", _CONSULTO),
    (os.path, "lexists", _CONSULTO),
    (os.path, "isfile", _CONSULTO),
    (os.path, "isdir", _CONSULTO),
    (os.path, "getmtime", _CONSULTO),
    (Path, "stat", _CONSULTO),
    (Path, "exists", _CONSULTO),
    (Path, "is_file", _CONSULTO),
    (Path, "is_dir", _CONSULTO),
    (Path, "read_text", _ABRIO),
    (Path, "read_bytes", _ABRIO),
    (Path, "write_text", _ABRIO),
    (Path, "write_bytes", _ABRIO),
    (Path, "iterdir", _CONSULTO),
    (Path, "glob", _CONSULTO),
    (Path, "rglob", _CONSULTO),
]


@dataclass(frozen=True)
class Fuga:
    """Una ruta de un árbol hermano tocada durante la ejecución."""

    ruta: str
    como: str


def _norm(p) -> str:
    return str(p).replace(chr(92), "/").rstrip("/").lower()


def arboles_hermanos(arbol: Path) -> list[Path]:
    """Los demás worktrees del mismo repo. Vacío si no es un repo o git no está.

    Se pregunta a git en vez de deducirlo de los nombres de carpeta: `pw-ralph` y
    `ponerse_wenorro` no se parecen en nada y son el mismo repo, y `capa-normativa` y
    `capa-normativa-otro` se parecen mucho y podrían no serlo.
    """
    try:
        r = subprocess.run(["git", "-C", str(arbol), "worktree", "list", "--porcelain"],
                           capture_output=True, timeout=30)
        rutas = [Path(l.split(" ", 1)[1])
                 for l in r.stdout.decode("utf-8", "replace").splitlines()
                 if l.startswith("worktree ")]
    except Exception:
        return []
    propio = _norm(Path(arbol).resolve())
    return [p for p in rutas if _norm(p) != propio]


def _de_quien_es(ruta, arboles_norm: list[str]) -> str | None:
    """El árbol al que pertenece esta ruta: el MÁS PROFUNDO que la contenga.

    ⚠️ Lo de «más profundo» no es un refinamiento, es la diferencia entre funcionar y no. Un
    worktree puede vivir DENTRO del árbol principal —`capa-normativa/.claude/worktrees/xxx/` es
    un caso real de este repo—, y entonces la ruta del principal es prefijo de todas las del
    anidado. Quedándose con el primer encaje, cada fichero del worktree se atribuye al padre y
    **todo** sale acusado. Salió así en la primera pasada real, y el acusado era un comprobador
    perfectamente sano.
    """
    try:
        r = _norm(Path(ruta).resolve()) if not os.path.isabs(str(ruta)) else _norm(ruta)
    except Exception:
        return None
    dueño = None
    for a in arboles_norm:
        if r == a or r.startswith(a + "/"):
            if dueño is None or len(a) > len(dueño):
                dueño = a
    return dueño


@contextmanager
def vigilando(arbol: Path, hermanos: list[Path] | None = None):
    """Acumula, mientras dure el bloque, las rutas de árboles hermanos que se toquen.

    Se parchean las DOS puertas de entrada, `builtins.open` e `io.open`, y no es redundancia:
    `pathlib.Path.open()` llama a `io.open` por su nombre de módulo, así que parchear sólo
    `builtins` deja pasar todo lo que vaya por `pathlib` — que es casi todo el código moderno.

    ⚠️ Se restaura en `finally`. Un vigilante que se deja los parches puestos al fallar
    contamina todo lo que corra después en ese proceso, y el daño aparecería lejos de aquí.
    """
    if hermanos is None:
        hermanos = arboles_hermanos(arbol)
    propio = _norm(Path(arbol).resolve())
    hn = [_norm(Path(h).resolve()) for h in hermanos]
    fugas: list[Fuga] = []
    if not hn:                      # sin hermanos no hay nada que confundir
        yield fugas
        return
    # El árbol propio entra en la comparación aunque no sea sospechoso: sin él no se puede
    # saber si un encaje con un hermano es el verdadero dueño o sólo un prefijo suyo.
    todos = hn + [propio]

    def anota(ruta, como):
        if _de_quien_es(ruta, todos) not in (None, propio):
            fugas.append(Fuga(str(ruta), como))

    def _mk(orig, como):
        def envuelto(p, *a, **k):
            anota(p, como)
            return orig(p, *a, **k)
        return envuelto

    def _mk_proc(orig):
        def envuelto(args, *a, **k):
            # El `cwd` primero: es la forma silenciosa de acabar en otro árbol sin escribir
            # ninguna ruta, y además manda sobre cómo resuelven las relativas del comando.
            if k.get("cwd"):
                anota(k["cwd"], _EJECUTO)
            # Cualquier trozo con pinta de ruta, absoluta o no. Hubo una versión que sólo
            # miraba las absolutas, para no confundir un id de pytest (`tests/x.py::test_y`)
            # con un fichero — y era peor por dos motivos: dejaba escapar un `../hermano/x.py`,
            # que es relativo y sale del árbol igual; y el ruido que pretendía evitar ya no
            # existe, porque cada comprobador se ejecuta DESDE su propio árbol y una relativa
            # resuelve dentro de él. Una sola defensa que se puede probar, en vez de dos que se
            # tapan entre sí.
            piezas = args if isinstance(args, (list, tuple)) else [args]
            for pieza in piezas:
                for trozo in str(pieza).replace(chr(92), "/").split():
                    if "/" in trozo:
                        anota(trozo.rstrip("'\");,"), _EJECUTO)
            return orig(args, *a, **k)
        return envuelto

    previos = [(obj, attr, getattr(obj, attr)) for obj, attr, _ in _PUERTAS]
    o_run, o_popen = subprocess.run, subprocess.Popen
    for obj, attr, como in _PUERTAS:
        setattr(obj, attr, _mk(getattr(obj, attr), como))
    subprocess.run, subprocess.Popen = _mk_proc(o_run), _mk_proc(o_popen)
    try:
        yield fugas
    finally:
        for obj, attr, orig in previos:
            setattr(obj, attr, orig)
        subprocess.run, subprocess.Popen = o_run, o_popen


def revisar_arbol_propio(comprobadores: dict, arbol: Path,
                         hermanos: list[Path] | None = None,
                         permitidos: dict | None = None) -> list[Hallazgo]:
    """Ejecuta cada comprobador vigilado y denuncia a los que tocan un árbol hermano.

    **Enumera, no es fail-fast** (contrato del vigilante): interesa saber cuántas sondas están
    mal apuntadas de una pasada, no la primera.

    El VEREDICTO del comprobador da igual aquí — rojo o verde es asunto suyo. Lo único que se
    mira es DÓNDE miró. Un comprobador puede estar perfectamente rojo y perfectamente mal
    apuntado a la vez, que es justo el caso que costó una noche entera de trabajo destruido.

    `permitidos` es `{nombre: motivo}` para los que miran fuera **a propósito**: un auditor
    cruzado como «todos los repos tienen su pre-commit» toca los demás árboles porque ese ES su
    trabajo. Se declara con su motivo, igual que `SIN_MUTACION`, en vez de silenciarse a secas:
    una excepción escrita se revisa, una excepción implícita se hereda. Y sin esta puerta el
    guarda gritaría en falso para siempre en ese tablero, que es la forma segura de que alguien
    lo acabe apagando.
    """
    if hermanos is None:
        hermanos = arboles_hermanos(arbol)
    permitidos = permitidos or {}
    fuera: list[Hallazgo] = []
    for nombre, fn in sorted(comprobadores.items()):
        if nombre in permitidos:
            continue
        with vigilando(arbol, hermanos) as fugas:
            # Se ejecuta DESDE el árbol que se juzga, que es como lo ejecuta el bucle. Sin esto,
            # toda ruta relativa del comprobador resuelve contra el directorio de quien lanza la
            # revisión — y si ése resulta ser otro worktree, la sonda queda acusada por un fallo
            # que es de quien mide, no suyo. Pasó: doce sondas sanas de `capa-normativa`
            # señaladas de golpe en la primera pasada real.
            antes = os.getcwd()
            try:
                os.chdir(str(arbol))
                fn()
            except Exception:
                pass        # que reviente es asunto de su propio comprobador, no de éste
            finally:
                os.chdir(antes)
        if not fugas:
            continue
        vistas, unicas = set(), []
        for f in fugas:
            if f.ruta not in vistas:
                vistas.add(f.ruta)
                unicas.append(f)
        primera = unicas[0]
        fuera.append(Hallazgo(
            detector=DETECTOR, codigo=CODIGO, fichero=nombre, linea=None,
            mensaje=("juzga un arbol HERMANO: " + primera.como + " " + primera.ruta
                     + ("" if len(unicas) == 1 else " (y " + str(len(unicas) - 1) + " ruta(s) mas)")),
            arreglo=("derivar la ruta de `Path(__file__).resolve()` en vez de escribirla, y "
                     "pasar `cwd=` explicito a subprocess. Si la ruta viene de una variable de "
                     "entorno o de un paquete instalado, fijarla al arbol propio antes de usarla."),
        ))
    return fuera
