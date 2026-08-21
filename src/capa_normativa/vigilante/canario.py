"""El canario: comprobar que los detectores DETECTAN, antes de creerles un «limpio».

## Por qué existe

Responde a un fallo que ya ocurrió tres veces: **dar por buena una verificación cuya mutación
nunca entró**. Un `PATRONES` vacío, un módulo a medio importar o una enumeración secuestrada
dejan un escáner que contesta «limpio» siempre — indistinguible de no tener escáner, y peor,
porque ocupa su hueco.

Y funciona: el secuestro por `GIT_DIR` del 2026-08-20 (§ `versionados.py`) se cazó justo así,
porque el canario bloqueó un commit diciendo que el detector no detectaba nada.

## Por qué el repo de pega es un repo DE VERDAD (2026-08-20)

La versión anterior de esto vivía en el hook y montaba su caso en un `TemporaryDirectory` **sin
`git init`**. Dos consecuencias, y las dos son el mismo error que el canario existe para cazar:

1. **No era determinista.** Sin repo propio, `git ls-files` contesta sobre el repo que encuentre
   —el del `GIT_DIR` heredado, o el que envuelva a `%TEMP%`—, devuelve nombres de OTRO árbol,
   y el detector recorre rutas que no existen. Medido: 0 hallazgos, canario en rojo, commit
   bloqueado sin causa en el repo que se estaba commiteando. Irreproducible a mano, porque a
   mano no hay `GIT_DIR`: git solo lo exporta a los hooks, y solo desde un *worktree*.
2. **Medía el camino que NO corre.** Al no ser repo, la enumeración por git fallaba y el
   detector caía a su `rglob` de reserva. O sea: el canario daba verde sobre el camino de
   respaldo mientras el de producción podía estar muerto. Medido el 2026-08-20 anulando
   `versionados()` por completo: el canario **seguía dando 1 hallazgo y pasando**.

De ahí las tres exigencias de `_correr`, que son tres formas de «la mutación tiene que entrar»:
cada detector caza su caso rojo, la enumeración por git está viva y devuelve EXACTAMENTE los
casos, y un detector sin caso rojo es un error en vez de un salto silencioso.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from .versionados import entorno_limpio, versionados

Revisor = Callable[[Path], list]

#: Un caso ROJO por detector: `(fichero, contenido)` que ESE detector tiene que cazar.
#:
#: La credencial va partida a propósito. Escrita de una pieza, este fichero sería un hallazgo
#: de `secretos` en cuanto el vigilante se corriera sobre su propio repo — y lo hace, es un
#: trabajo del CI. Un canario que dispara el detector que comprueba no es una gracia: obliga a
#: excluirlo, y una exclusión es por donde se apagan los detectores.
CASOS: dict[str, tuple[str, str]] = {
    "secretos": ("credencial.md", "clave = " + "gsk" + "_" + "A" * 24 + "\n"),
    "sintaxis": ("roto.py", "def f(:\n"),
    # `preguntas` caza «lo escrito que su fuente no sostiene»: el catálogo declara un productor
    # cuyo fichero (`no_existe.py`) NO está en el repo → PRG001. El catálogo ES su caso rojo,
    # y `_invocar` se lo pasa como el CLI hace con `--catalogo` (su autoridad vive en el
    # inquilino, no se puede adivinar). El productor referido no se crea a propósito: que falte
    # es justo lo que dispara.
    "preguntas": ("preguntas_pega.yml",
                  'tdee:\n'
                  '  autoridad: "daily_plan.tdee_kcal"\n'
                  '  tope: 1\n'
                  '  productores:\n'
                  '    - sitio: "no_existe.py:1"\n'
                  '      ancla: "total_kcal_day"\n'
                  '      clase: productor\n'),
    # `punteros` caza un `§N.M` que no resuelve a ninguna cabecera del corpus: este `.md` cita
    # `§9.9` y no hay cabecera `§9.9` en ningún sitio → PTR001.
    "punteros": ("punteros_pega.md",
                 "Este texto remite a una sección que no existe: ver §9.9 para el detalle.\n"),
}


def _git(repo: Path, *args: str) -> None:
    """`git` sobre `repo`, dicho explícitamente y con el entorno limpio.

    `-C` en vez de `cwd=`, y sin las `GIT_*` heredadas: con un `GIT_DIR` en el entorno, este
    `git init` inicializaría el gitdir AJENO en lugar del repo de pega.
    """
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       timeout=60, env=entorno_limpio())
    if r.returncode != 0:
        raise RuntimeError(
            f"el canario no pudo montar su repo de pega (`git {args[0]}` salió {r.returncode}): "
            f"{r.stderr.strip()[:200]}")


@contextmanager
def repo_de_pega() -> Iterator[Path]:
    """Un repo git real y efímero con un caso rojo por detector, ya versionados.

    Que sea repo propio es lo que lo hace **independiente del CWD y del entorno**: git para de
    buscar en el `.git` más cercano, así que da igual dónde esté `%TEMP%` y da igual desde
    dónde se llame.
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        for fichero, contenido in CASOS.values():
            (repo / fichero).write_text(contenido, encoding="utf-8")
        _git(repo, "init", "-q")
        # `-f`: un `.gitignore` global del usuario no puede decidir si el canario cubre o no.
        _git(repo, "add", "-f", "--", *(fichero for fichero, _ in CASOS.values()))
        yield repo


def _invocar(nombre: str, revisor: Revisor, repo: Path) -> list:
    """Llama a `revisor` sobre `repo` como lo haría su consumidor real.

    Casi todos los detectores son `Callable[[Path], list]` y se llaman con el repo a secas.
    `preguntas` es la excepción, por la misma razón que en el CLI: su autoridad vive en la
    persistencia del inquilino, así que hay que declararle un catálogo — aquí ese catálogo ES
    su fichero de caso rojo, ya escrito y versionado en el repo de pega.
    """
    if nombre == "preguntas":
        return revisor(repo, repo / CASOS["preguntas"][0])
    return revisor(repo)


def _correr(revisores: Mapping[str, Revisor], repo: Path) -> None:
    """Exige que cada revisor cace su caso rojo en `repo`. Lanza `RuntimeError` si no."""
    if not revisores:
        raise RuntimeError("el canario no recibió ningún detector que comprobar")

    esperados = sorted(fichero for fichero, _ in CASOS.values())
    lista = versionados(repo)
    if lista is None or sorted(p.name for p in lista) != esperados:
        # Sin esto, una enumeración por git muerta pasa inadvertida: el `rglob` de reserva
        # encuentra los casos igual y el canario da verde sobre el camino equivocado.
        raise RuntimeError(
            f"el canario no enumeró por git ({'nada' if lista is None else sorted(p.name for p in lista)} "
            f"en vez de {esperados}): se estaría midiendo el camino de reserva, no el de producción")

    for nombre, revisor in revisores.items():
        if nombre not in CASOS:
            raise RuntimeError(
                f"no hay caso rojo para `{nombre}`: el canario NO lo cubre. Añádelo a `CASOS` "
                f"— un detector sin caso rojo es un detector que nadie ha comprobado.")
        if not _invocar(nombre, revisor, repo):
            raise RuntimeError(f"el canario de `{nombre}` no saltó: el detector no detecta nada")


def canario(revisores: Mapping[str, Revisor], repo: Path | None = None) -> None:
    """Comprueba que cada revisor detecta, y **que esta comprobación puede fallar**.

    Lo segundo no es adorno. Un canario que no distingue «el detector funciona» de «yo soy un
    no-op» es la misma avería que persigue, un piso más arriba. Así que después del pase real
    se repite el mismo camino con detectores SORDOS —devuelven siempre `[]`— y se exige que
    ese pase LANCE. Cuesta lo mismo: reusa el repo de pega ya montado.

    Lanza `RuntimeError` con el motivo. Que lance es el comportamiento correcto: «no pude
    comprobarlo» tiene que tener salida propia, nunca compartir la de «limpio».
    """
    if repo is None:
        with repo_de_pega() as nuevo:
            canario(revisores, nuevo)
        return

    _correr(revisores, repo)

    # `*_a`: `_invocar` llama a `preguntas` con dos argumentos (repo + catálogo), así que el
    # sordo tiene que tragarse cualquier aridad — si no, el pase de autocomprobación lanzaría
    # por `TypeError` en vez de por «el sordo no saltó», y no es lo mismo.
    sordos = {nombre: (lambda *_a: []) for nombre in revisores}
    try:
        _correr(sordos, repo)
    except RuntimeError:
        return
    raise RuntimeError("el canario dio verde incluso con los detectores SORDOS: es un no-op, "
                       "y su verde no significa nada")
