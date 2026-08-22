"""Los ficheros VERSIONADOS de un repo. Una sola implementación, y a prueba de `GIT_DIR`.

## El fallo que lo motiva (2026-08-20), porque es de los que no se ven

`secretos` y `sintaxis` tenían cada uno su copia de esto:

    subprocess.run(["git", "ls-files"], cwd=repo)

Parece correcto y no lo es. **Git exporta `GIT_DIR` a sus hooks**, y en un *worktree* ese valor
es una ruta ABSOLUTA al gitdir del repo principal. Con `GIT_DIR` en el entorno, `cwd=` deja de
decidir nada: `git ls-files` contesta sobre el repo del `GIT_DIR`, no sobre `repo`. Los nombres
que devuelve se unen a `repo`, dan rutas que NO EXISTEN, y el detector recorre una lista de
fantasmas.

Resultado medido: el vigilante corriendo como hook pre-commit **dentro de un worktree** escanea
CERO ficheros y responde «limpio». No falla: miente. Un escáner de secretos que dice «limpio»
sin haber mirado nada es peor que no tenerlo, porque se despliega confiando en él.

Se cazó de rebote — el canario de `vigilante_pre_commit.py` bloqueó un commit diciendo que el
detector no detectaba nada. Esa autocomprobación es lo único que separó este fallo de vivir
años en silencio.

## Las tres defensas, y por qué hacen falta las tres

1. **Entorno limpio**: se borran las variables `GIT_*` que redirigen el repo.
2. **`git -C repo`**: se dice explícitamente sobre qué repo se pregunta, sin depender del `cwd`.
3. **Se descartan las rutas que no existen**: si algo volviera a envenenar la lista, se nota en
   vez de escanear fantasmas. Es el cinturón después de los tirantes, y es barato.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

#: Variables con las que git redirige a QUÉ repo se refiere una orden. Heredadas de un hook,
#: secuestran cualquier `git` que se lance después — incluido el nuestro.
_GIT_REDIRECTORAS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                     "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                     "GIT_PREFIX", "GIT_NAMESPACE")


def entorno_limpio() -> dict[str, str]:
    """El entorno sin las variables con las que git redirige el repo.

    Es pública porque la necesita todo el que lance un `git` desde dentro de un hook, no
    solo la enumeración: el canario monta su repo de pega con `git init`, y con `GIT_DIR`
    heredado ese `init` inicializaría el gitdir AJENO en vez del suyo.
    """
    return {k: v for k, v in os.environ.items() if k not in _GIT_REDIRECTORAS}


def versionados(repo: Path, patron: str | None = None) -> list[Path] | None:
    """Ficheros versionados de `repo` (opcionalmente filtrados por `patron` de git).

    Devuelve `None` si el repo no es un repo git o git no está — el llamador decide entonces
    si recorre el disco. Se distingue de la lista vacía a propósito: «no es un repo» y «un repo
    sin ficheros» exigen reacciones distintas.
    """
    # `-z`: nombres separados por NUL y SIN citar. Con el default `core.quotePath=true`, un
    # `ls-files` normal envuelve los nombres no-ASCII entre comillas y escapa cada byte en octal
    # (`"docs/se\303\261al.md"`). Ese texto NO es una ruta: `repo / esa_cadena` no existe y la
    # «defensa 3» lo descartaba callando, dejando de escanear cualquier fichero con ñ/tilde. Con
    # `-z` git emite el nombre tal cual (bytes UTF-8), así que no hay nada que des-escapar.
    orden = ["git", "-C", str(repo), "ls-files", "-z"] + ([patron] if patron else [])
    try:
        r = subprocess.run(orden, capture_output=True, timeout=120,
                           env=entorno_limpio())
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    nombres = r.stdout.decode("utf-8", "surrogateescape").split("\0")
    rutas = [repo / n for n in nombres if n]
    # Cinturón: una lista envenenada da rutas inexistentes. Mejor escanear menos que escanear
    # fantasmas y llamarlo «limpio».
    return [p for p in rutas if p.exists()] or None
