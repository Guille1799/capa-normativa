"""PTR — un puntero `§N.M` que no resuelve a ninguna sección del corpus.

Es el detector de la clase de fallo dominante («lo escrito se separa de su fuente») en su
forma más barata: no comprueba que la sección DIGA lo que se le atribuye —eso no es
automatizable—, comprueba que **exista**. Verificar la vigencia del ancla, no la verdad de
la frase.
"""

from __future__ import annotations

import re
from pathlib import Path

from .hallazgo import Hallazgo

_CABECERA = re.compile(r"^#{1,6}\s+§?(\d+\.\d+)\b", re.M)

# El `(?!\.\d)` final es un arreglo medido, no una precaución teórica: sin él, `§10.3.2.10`
# —una referencia a la especificación DMN— se leía como un puntero interno a `10.3` y salía
# como colgante. Era el único «hallazgo» del corpus de 229 referencias, y era falso.
#
# Y el lookahead tiene que ser `\.\d` y NO `[.\d]`: la primera versión de este arreglo
# rechazaba `§9.9.` al final de una frase —un puntero interno legítimo seguido de punto— y
# los tests lo cazaron en su primera ejecución. Solo descarta el punto SEGUIDO DE DÍGITO,
# que es lo que distingue una referencia a especificación (`§10.3.2.10`) de una frase que
# termina (`§9.9.`). Defendido por `test_un_puntero_al_final_de_una_frase_SI_cuenta`.
_REFERENCIA = re.compile(
    r"(?:(?P<doc>[A-Z][A-Za-z_]{2,}(?:\.md)?)\s+)?§(?P<sec>\d+\.\d+)(?!\.\d)"
)


#: Al recorrer en profundidad hay que excluir lo que no es documentación del proyecto.
_EXCLUIR = ("node_modules", ".git", "venv", "site-packages", "__pycache__", ".next", "/dist/")


def _markdowns(d: Path) -> list[Path]:
    """Todos los `.md` del árbol, **en profundidad**.

    ⚠️ Antes era `glob("*.md")` —solo el primer nivel— y eso producía un FALSO NEGATIVO, que es
    la peor forma de fallo para un detector: `… docs --detector punteros` decía «limpio, 0
    hallazgos» y exit 0 mientras `docs/fundamentos/` tenía **8 punteros colgantes** reales.
    Un detector que da confianza falsa es peor que ninguno.

    Lo encontró un agente sin contexto al adoptar el paquete leyendo solo el README (experimento
    del 2026-08-11), no sus propios tests: todos usaban corpus de un solo nivel. La forma del
    test copiaba la forma del bug.
    """
    return sorted(p for p in d.rglob("*.md")
                  if not any(x in "/" + str(p).replace("\\", "/") for x in _EXCLUIR))


def _cabeceras(dirs: list[Path]) -> set[str]:
    vistas: set[str] = set()
    for d in dirs:
        for f in _markdowns(d):
            vistas.update(_CABECERA.findall(f.read_text(encoding="utf-8", errors="replace")))
    return vistas


def revisar_punteros(
    corpus: Path | str,
    *,
    tambien: list[Path | str] | None = None,
) -> list[Hallazgo]:
    """Revisa los `§N.M` de `corpus` contra las cabeceras de `corpus` + `tambien`.

    `tambien` existe por un falso positivo medido el 2026-08-09: al correr esto sobre
    `ponerse_wenorro/docs`, los `§5.40`/`§5.50` salieron colgantes — y eran **correctos**,
    apuntando a un documento que vive en OTRO repo. 17 de 18 hallazgos de aquella corrida
    eran de esa clase. Un puntero entre repos es inverificable si no le declaras el otro
    corpus; declararlo es el precio de que esta clase deje de ser ciega.
    """
    principal = Path(corpus)
    if not principal.is_dir():
        raise NotADirectoryError(f"no es un directorio: {principal}")

    extra = [Path(p) for p in (tambien or [])]
    conocidas = _cabeceras([principal, *[p for p in extra if p.is_dir()]])

    hallazgos: list[Hallazgo] = []
    for f in _markdowns(principal):
        texto = f.read_text(encoding="utf-8", errors="replace")
        for m in _REFERENCIA.finditer(texto):
            sec, doc = m.group("sec"), m.group("doc")
            # Referencia externa declarada («DMN §10.3», «RFC_2119 §4»): no es nuestra.
            if doc and doc.isupper():
                continue
            if sec in conocidas:
                continue
            # Ruta RELATIVA al corpus, no `f.name`: al bajar a subdirectorios dos ficheros con
            # el mismo nombre en carpetas distintas serían indistinguibles, y un hallazgo que
            # no se puede localizar no es un hallazgo. Consecuencia del arreglo de la recursión.
            try:
                donde = str(f.relative_to(principal)).replace("\\", "/")
            except ValueError:
                donde = f.name
            hallazgos.append(Hallazgo(
                detector="punteros",
                codigo="PTR001",
                fichero=donde,
                linea=texto[: m.start()].count("\n") + 1,
                mensaje=f"§{sec} no existe en el corpus revisado",
                arreglo=("Corrige el número, o declara el corpus donde vive con "
                         "`--tambien <dir>` si el puntero cruza a otro repo, o marca la "
                         "referencia como externa poniéndole delante el documento en "
                         "MAYÚSCULAS (p. ej. `DMN §10.3`)."),
            ))
    return hallazgos
