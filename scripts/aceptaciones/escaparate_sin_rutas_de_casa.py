"""Ningún repo público publica la ruta de casa de G ni su nombre de usuario.

## Por qué hace falta, habiendo ya una guarda `pre-push`

La guarda vigila **la puerta**: mira lo que va a salir en el próximo empujón. Y eso deja fuera todo
lo que ya está dentro — lo que se publicó antes de que la guarda existiera, o lo que entró con un
`--no-verify`. Un portero no es un inventario.

Medido el 2026-08-24, con la guarda instalada y funcionando en los seis repos públicos:

    capa-normativa               0 ficheros con la ruta de casa
    cn-ralph                     0
    eu-political-observatory    12
    eu-ralph                    12

O sea que la guarda estaba verde y había 24 ficheros publicados con la ruta de casa dentro. Los
dos hechos son compatibles y las dos comprobaciones hacen falta: una mira el futuro y otra el
presente.

## Por qué importa, que no es privacidad

Es **presentación**. Estos repos los va a mirar un reclutador. Una ruta absoluta de Windows con el
nombre de usuario dentro dice «esto sólo corre en mi máquina» — y lo dice en el sitio donde uno
quiere decir justo lo contrario. El coste no es un riesgo de seguridad; es la impresión.

## La distinción que este comprobador SÍ hace

Separa lo que ya está empujado de lo que aún no, porque el arreglo es de otro precio:

  · **no empujado** — limpiar es una reescritura local, sin víctimas. La puerta barata.
  · **ya publicado** — exige un force-push sobre historia pública, y GitHub conserva los commits
    huérfanos alcanzables por su SHA. Eso es una decisión de G, no de un comprobador.

Sin esa distinción el rojo diría «hay 24» y no diría lo único que decide qué hacer.

## Su primera captura fue él mismo

Merece quedar escrito: la primera vez que corrió en la ronda, lo único que encontró en `capa-normativa`
fue **este fichero**, porque su propio docstring citaba la ruta de casa como ejemplo. Se quitó la
cita — la explicación no la necesitaba — y quedó limpio.

No es una anécdota: un comprobador que no sobrevive a su propia regla es sospechoso, porque suele
significar que la regla es impracticable. Ésta no lo era.

## La trampa prohibida

Si no se puede saber qué repos son públicos, esto es **ROJO por no haber podido mirar**. Y cero
repos públicos detectados también: es un resultado sospechoso, no una máquina limpia.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

#: Se reutiliza la enumeración de repos públicos del comprobador hermano en vez de copiarla: si un
#: día cambia cómo se decide qué es público, tiene que cambiar en un solo sitio o los dos dejarán
#: de estar de acuerdo sin que nadie se entere.
_spec = importlib.util.spec_from_file_location(
    "escaparate_con_guarda", str(AQUI / "escaparate_con_guarda.py"))
_hermano = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hermano)

NoSePudoMirar = _hermano.NoSePudoMirar
publicos = _hermano.publicos

#: El usuario se DERIVA, no se escribe. Una constante `Guille` sería falsa en cualquier otra máquina
#: y convertiría este comprobador en decoración el día que el repo se clone en otro sitio.
_USUARIO = Path.home().name

#: `C:/Users/X`, `C:\Users\X` y la forma con barras dobles que aparece dentro de los .ipynb.
_RUTA_DE_CASA = re.compile(
    r"[A-Za-z]:[/\\]{1,2}Users[/\\]{1,2}" + re.escape(_USUARIO), re.IGNORECASE)

#: Ficheros que no son texto publicado o que son enormes. Los .ipynb SÍ se miran: un cuaderno es de
#: lo primero que abre quien viene a mirar el trabajo, y la ruta absoluta se ve en la primera celda.
_EXTENSIONES_MUDAS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".parquet", ".db",
                      ".sqlite", ".lance", ".woff", ".woff2", ".ico"}
_TOPE_BYTES = 4_000_000


def _git(*a, cwd=None) -> str:
    return subprocess.run(["git", *a], cwd=str(cwd) if cwd else None, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300).stdout


def _publicado_hasta(repo: Path) -> str | None:
    """La referencia que de verdad ha salido a GitHub, o None si la rama no tiene upstream."""
    r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                       cwd=str(repo), capture_output=True, text=True, timeout=120)
    ref = r.stdout.strip()
    return ref if r.returncode == 0 and ref else None


def _con_ruta(repo: Path) -> tuple[list[str], list[str], list[str]]:
    """(ya publicados, aún no empujados, NO MIRADOS) — ficheros seguidos con la ruta de casa.

    ⚠️ La tercera lista es la que faltaba, y faltaba de la peor manera posible.

    MEDIDO el 2026-08-30: un fichero que no se podía leer se saltaba con un `continue` **en
    silencio**. Y un fichero saltado no puede aportar ningún hallazgo, o sea que aportaba VERDE:
    el veredicto final decía «ninguno de los N repos lleva la ruta de casa» sin mencionar que a M
    ficheros ni se les había mirado. Eso es **aprobar en vacío, fichero a fichero**, escondido
    dentro de un `continue`.

    Y no hacía falta ningún caso exótico: un fichero por encima del tope de tamaño, uno sin
    permisos, o uno a medio escribir por otro proceso caían todos por la misma rendija.

    El tope de tamaño se sigue respetando —rastrear un binario de 50 MB buscando texto no tiene
    sentido—, pero **saltárselo se DICE**. Eso es lo único que cambia, y es todo lo que hacía falta.
    """
    upstream = _publicado_hasta(repo)
    fuera_publicados: list[str] = []
    fuera_locales: list[str] = []
    no_mirados: list[str] = []

    for rel in _git("ls-files", cwd=repo).splitlines():
        if not rel or Path(rel).suffix.lower() in _EXTENSIONES_MUDAS:
            continue
        f = repo / rel
        try:
            if not f.is_file():
                continue          # borrado del disco pero aun seguido: no hay nada que leer
            if f.stat().st_size > _TOPE_BYTES:
                no_mirados.append(rel + " (mas de " + str(_TOPE_BYTES // 1024) + " KB)")
                continue
            texto = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            no_mirados.append(rel + " (" + type(e).__name__ + ")")
            continue
        if not _RUTA_DE_CASA.search(texto):
            continue

        if upstream is None:
            # Sin upstream no se ha publicado nada todavia: todo es puerta barata.
            fuera_locales.append(rel)
            continue
        publicado = _git("show", f"{upstream}:{rel}", cwd=repo)
        (fuera_publicados if _RUTA_DE_CASA.search(publicado) else fuera_locales).append(rel)

    return fuera_publicados, fuera_locales, no_mirados


def escaparate_sin_rutas_de_casa() -> tuple[bool | None, str]:
    """VERDE / ROJO / MUDO. Un hallazgo manda sobre un fichero no mirado; la duda manda sobre el
    verde."""
    try:
        pubs = publicos()
    except NoSePudoMirar as e:
        return None, f"no se pudo mirar ({e}). Eso NO es «no hay rutas de casa»."
    if not pubs:
        # gh ha contestado, y ha contestado algo imposible: eso es haber mirado, no lo contrario.
        return False, "cero repos publicos detectados: sospechoso, no limpio"

    publicados: dict[str, int] = {}
    locales: dict[str, int] = {}
    ciegos: dict[str, list[str]] = {}
    for repo in pubs:
        pub, loc, ciego = _con_ruta(repo)
        if pub:
            publicados[repo.name] = len(pub)
        if loc:
            locales[repo.name] = len(loc)
        if ciego:
            ciegos[repo.name] = ciego

    # El ORDEN de estas dos ramas es la decision entera, y va asi por un motivo: un hallazgo REAL
    # manda sobre la duda —si ya hay una ruta de casa publicada, que ademas quedaran ficheros sin
    # mirar no rebaja nada—, pero la duda manda sobre el VERDE. Al reves seria tapar una infraccion
    # confirmada con un «no estoy seguro», y tambien seria aprobar sin haber mirado del todo.
    if not publicados and not locales and ciegos:
        cuantos = sum(len(v) for v in ciegos.values())
        muestra = "; ".join(k + ": " + ", ".join(v[:3]) for k, v in sorted(ciegos.items()))
        return None, (f"no se pudo leer {cuantos} fichero(s), asi que NO se puede decir que no "
                      f"haya rutas de casa — solo que no se han visto en lo que si se leyo. "
                      f"{muestra[:300]}")

    if not publicados and not locales:
        return True, (f"ninguno de los {len(pubs)} repos publicos lleva la ruta de casa "
                      f"(`…/Users/{_USUARIO}`) en lo que versiona, y se pudieron leer todos")

    partes = []
    if locales:
        partes.append("AUN NO EMPUJADO (limpiar es gratis hoy): "
                      + ", ".join(f"{k} {v}" for k, v in sorted(locales.items())))
    if publicados:
        partes.append("YA PUBLICADO (limpiarlo exige force-push, lo decide G): "
                      + ", ".join(f"{k} {v}" for k, v in sorted(publicados.items())))
    return False, " · ".join(partes)


if __name__ == "__main__":
    ok, msg = escaparate_sin_rutas_de_casa()
    print(("MUDO: " if ok is None else "VERDE: " if ok else "ROJO: ") + msg)
    if not ok and "--detalle" in sys.argv:
        for repo in publicos():
            pub, loc, _ciego = _con_ruta(repo)
            if pub or loc:
                print(f"\n  {repo.name}")
                for x in loc:
                    print(f"     [barato]   {x}")
                for x in pub:
                    print(f"     [publicado] {x}")
    sys.exit(3 if ok is None else 0 if ok else 1)
