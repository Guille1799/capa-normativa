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

import difflib
import os
import re
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

#: Dos copias son «la misma pieza» si se parecen al menos esto.
_PARECIDO = 0.60

#: Sólo funciones de nivel superior o de un nivel de anidamiento: las de más adentro son detalle
#: interno y su ausencia no dice nada útil.
_DEF = re.compile(r"^\s{0,4}def\s+([a-zA-Z_]\w*)", re.M)

_TOPE_COMPARACION = 20_000


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


def desfases() -> list[tuple[str, str, list[str], list[str]]]:
    """(ruta, funcion, quien la tiene, a quien le falta) por cada pieza que se quedó atrás."""
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
        textos = {}
        for repo in repos_con:
            try:
                textos[repo.name] = (repo / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        if len(textos) < 2:
            continue

        base = max(textos, key=lambda r: len(textos[r]))
        parecidos = {base}
        for nombre, t in textos.items():
            if nombre == base:
                continue
            ratio = difflib.SequenceMatcher(
                None, textos[base][:_TOPE_COMPARACION], t[:_TOPE_COMPARACION]).quick_ratio()
            if ratio >= _PARECIDO:
                parecidos.add(nombre)
        if len(parecidos) < 2:
            continue

        defs = {r: set(_DEF.findall(textos[r])) for r in parecidos}
        for funcion in sorted(set().union(*defs.values())):
            tienen = {r for r in parecidos if funcion in defs[r]}
            faltan = parecidos - tienen
            if faltan and len(tienen) >= 2:
                fuera.append((rel, funcion, sorted(tienen), sorted(faltan)))
    return fuera


def piezas_compartidas_al_dia() -> tuple[bool, str]:
    try:
        atrasadas = desfases()
    except NoSePudoMirar as e:
        return False, f"no se pudo mirar ({e}). Eso NO es «todo al dia»."

    if not atrasadas:
        return True, ("ninguna pieza compartida se ha quedado atras en ningun repo")

    porq: dict[str, int] = {}
    for _, _, _, faltan in atrasadas:
        for r in faltan:
            porq[r] = porq.get(r, 0) + 1
    detalle = ", ".join(f"{k} le faltan {v}" for k, v in sorted(porq.items(), key=lambda x: -x[1]))
    return False, (f"{len(atrasadas)} pieza(s) compartida(s) sin propagar: {detalle}. "
                   f"El repo que se queda atras NO se pone rojo por su cuenta: simplemente no "
                   f"tiene el detector, asi que no detecta.")


if __name__ == "__main__":
    ok, msg = piezas_compartidas_al_dia()
    print(("VERDE: " if ok else "ROJO: ") + msg)
    if not ok and "--detalle" in sys.argv:
        print()
        for rel, funcion, tienen, faltan in desfases():
            print(f"  {rel} :: {funcion}")
            print(f"      la tienen: {', '.join(tienen)}")
            print(f"      le falta a: {', '.join(faltan)}")
    sys.exit(0 if ok else 1)
