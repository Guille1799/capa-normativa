"""SYN — un fichero Python versionado que no parsea.

El detector más barato que existe, y el que faltaba en el catálogo: en el barrido del
2026-08-09 encontró un `SyntaxError` que llevaba **dos meses** commiteado y que ninguno de
los 31 mecanismos de solidez del sistema había visto.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from .versionados import versionados
from .hallazgo import Hallazgo

# Comparación por COMPONENTE de ruta (`p.parts`), no por subcadena: `".git" in str(p)` casaba
# `.github/` entero (`.git` es subcadena de `.github`), así que un `.py` bajo `.github/scripts/`
# —versionado— nunca se parseaba. Medido el 2026-08-21.
_EXCLUIR = {"venv", "site-packages", "__pycache__", "node_modules", ".git", "_archive"}


def _ficheros_py(repo: Path) -> list[Path]:
    """Los `.py` que git conoce. Si no hay git, cae a recorrer el árbol.

    Se pregunta a git a propósito: un fichero sin versionar que no parsea es ruido del
    directorio de trabajo, no deuda del repo.
    """
    # ⚠️ La enumeración vive en `versionados` y NO se copia aquí: la copia que había se dejaba
    # secuestrar por el `GIT_DIR` que git exporta a sus hooks, y dentro de un worktree eso hacía
    # que este detector escaneara CERO ficheros y dijera «limpio» (medido el 2026-08-20).
    lista = versionados(repo, "*.py")
    if lista is not None:
        return lista
    return [p for p in repo.rglob("*.py") if not _EXCLUIR.intersection(p.parts)]


def revisar_sintaxis(repo: Path | str) -> list[Hallazgo]:
    """Devuelve un hallazgo por fichero versionado que no parsea."""
    repo = Path(repo)
    hallazgos: list[Hallazgo] = []
    for p in _ficheros_py(repo):
        if _EXCLUIR.intersection(p.parts):
            continue
        try:
            # `utf-8-sig`, NO `utf-8`. Con `utf-8` el BOM sobrevive a la lectura, `ast` lo
            # ve como carácter ilegal en la columna 1 y el detector reporta roto un fichero
            # que Python compila sin problema. Medido el 2026-08-09 en su primera ejecución:
            # 8 falsos positivos de 9 hallazgos (89 %) por esta única palabra. La afirmación
            # «ast.parse tiene 0 FP por construcción» es falsa: los tiene 0 solo si lees el
            # fichero como lo lee Python. Defendido por
            # `test_un_BOM_no_es_un_error_de_sintaxis` — el caso rojo real, no inventado.
            fuente = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        try:
            ast.parse(fuente, filename=str(p))
        except SyntaxError as e:
            try:
                donde = str(p.relative_to(repo))
            except ValueError:
                donde = str(p)
            hallazgos.append(Hallazgo(
                detector="sintaxis",
                codigo="SYN001",
                fichero=donde,
                linea=e.lineno,
                mensaje=f"no parsea: {e.msg}",
                arreglo=("Arregla la sintaxis. Si el fichero está abandonado, sácalo del "
                         "control de versiones: mientras esté versionado, es deuda."),
            ))
    return hallazgos
