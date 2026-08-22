"""`emit` — sacar los valores del registro a otro lenguaje, CON su procedencia.

Es la pieza que decide **a qué proyectos sirve esto**. Hasta ahora la única interfaz era
`load()` + `resolve()` **en proceso Python**, y eso dejaba fuera a cualquier consumidor que no
sea Python: los umbrales metodológicos en R de un proyecto de investigación, o el frontend en
TypeScript que hoy **duplica a mano** lo que el backend decide.

## La regla que no se negocia

**Si `emit` solo saca números, ha reinventado el problema en un sitio nuevo.** Un
`EA_FLOOR <- 30` en un `.R` generado es el mismo número mágico del que se venía, ahora con un
paso de build de por medio. Así que **cada valor viaja con su procedencia**: sus identificadores
de evidencia, su certeza, su unidad y su fecha de caducidad. Si el consumidor quiere el número
pelado, lo saca de ahí; lo que no puede es no tenerla.

## Qué se emite, y qué NO

Solo las **constantes** (`Norm.constant`): las que no ramifican por el sujeto. Medido en el
primer inquilino, son el **54 %** de las normas, y de las que quedan sin migrar el **90 %**
tampoco ramifica — así que esto cubre la gran mayoría.

Una norma que **sí** ramifica no se emite, y no es una limitación que se calle: sale en
`omitidas` con su motivo. Emitirla obligaría a reproducir la tabla de decisión y su hit policy
en cada lenguaje destino, que es exactamente el acoplamiento que §5.47 diagnosticó como el
problema del molde. **El que ramifica, llama a `resolve()`.**

Y **no se emite lo que el registro no serviría**: retiradas, bloqueadas y caducadas quedan
fuera. Es la misma regla que hace que `resolve()` no emita valor, aplicada a la exportación —
si no, `emit` sería la puerta de atrás por la que sale un valor que el registro niega.

## Por qué existe `--check`

Un fichero generado que se commitea **puede derivar** de su fuente. `--check` re-emite y
compara: si difiere, sale con **1**. Ese es el patrón de `protobuf`, `OpenAPI` y
`kubernetes/hack/verify-codegen.sh`, y es lo que evita que `emit` añada un artefacto más que
tenga que decir lo mismo — el criterio con el que se cerró la decisión de arquitectura.

**Sin `--check` en CI, `emit` empeora el problema que viene a resolver.**
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

from .registry import NormRegistry, Norm

FORMATOS = ("json", "python", "typescript", "r")

#: Estados cuyo valor el registro NO serviría. Emitirlos sería la puerta de atrás.
_NO_EMITIBLES = {"retirada", "bloqueada", "superseded"}


class Constante(NamedTuple):
    """Un valor exportable con todo lo que necesita para no ser un número mágico."""

    slug: str
    valor: Any
    unidad: str
    evidencia: tuple[str, ...]
    certeza: str
    fuerza: str
    caduca: str | None
    nota: str | None          # el matiz clínico/de diseño de la rama (`Branch.note`)
    procedencia: str | None   # de dónde salió el número (`Branch.provenance_note`)


def _omision(n: Norm, hoy: date) -> str | None:
    """Motivo por el que una norma no se emite, o `None` si sí se emite."""
    if n.status in _NO_EMITIBLES:
        return f"estado `{n.status}`: el registro no serviría su valor"
    if n.expires is not None and n.expires < hoy:
        return f"CADUCADA el {n.expires.isoformat()}: hay que re-adjudicarla"
    if not n.constant:
        return "ramifica por el sujeto: no es una constante. El consumidor debe usar resolve()"
    if not n.branches:
        return "sin ramas: no hay valor que emitir"
    return None


def recoger(registro: NormRegistry, *, hoy: date | None = None
            ) -> tuple[list[Constante], dict[str, str]]:
    """(constantes emitibles, {slug: motivo de omisión}). Nada se calla."""
    hoy = hoy or date.today()
    fuera: list[Constante] = []
    omitidas: dict[str, str] = {}
    for n in registro.normas():
        motivo = _omision(n, hoy)
        if motivo:
            omitidas[n.slug] = motivo
            continue
        rama = n.branches[0]
        fuera.append(Constante(
            slug=n.slug, valor=rama.value, unidad=n.unit,
            # v0.14.0 · la certeza y la procedencia son de LA RAMA (que en una constante es
            # la sintetizada, así que para las emitibles de hoy no cambia nada). Antes esto
            # emitía `n.certainty`, y con procedencia por rama eso volvería a ser la mentira
            # que la v0.14.0 cierra: exportar un número con la certeza de su hermana.
            evidencia=tuple(rama.evidence), certeza=rama.certainty, fuerza=n.strength,
            caduca=n.expires.isoformat() if n.expires else None,
            # `note` y `provenance_note` NO son alternativas: el parser los admite juntos
            # (con `certainty=sin_respaldo` no hay evidencia y `note` sigue siendo válida), y
            # son cosas distintas —el matiz de diseño vs. de dónde salió el número—. Tratarlos
            # como excluyentes (`note if note else provenance`) tiraba la procedencia cuando
            # coexistían: el número salía con la nota que suena a justificación y SIN la frase
            # que dice que no tiene fuente localizable. Cada uno viaja en su propio campo.
            nota=rama.note, procedencia=rama.provenance_note,
        ))
    return fuera, omitidas


# ───────────────────────────── formatos ─────────────────────────────

def _cabecera(comentario: str, orden: str) -> str:
    return (f"{comentario} GENERADO POR capa-normativa · NO EDITAR A MANO\n"
            f"{comentario} Regenerar:  {orden}\n"
            f"{comentario} Si esto difiere de la fuente, `--check` falla en CI. Es a propósito.\n")


def _lit_py(v: Any) -> str:
    return repr(v)


def _lit_js(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def _lit_r(v: Any) -> str:
    """Literal de R. Los `dict` son `list(k = v)`, y eso NO era un detalle.

    ⚠️ Sin esta rama, un valor compuesto salía con sintaxis de PYTHON dentro del `.R`:
    `CALORIE_BANK_PUSH <- {'threshold_kcal': 800.0, …}`. Un fichero generado que no parsea es
    peor que ninguno. Lo destapó correr `emit` contra el registro real —12 de sus 38 constantes
    son compuestas— y no los tests, que usaban solo escalares: **la forma del test copiaba la
    forma del bug**, igual que en el falso negativo de PTR001.
    """
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if v is None:
        return "NULL"
    if isinstance(v, dict):
        return "list(" + ", ".join(f"`{k}` = {_lit_r(x)}" for k, x in v.items()) + ")"
    if isinstance(v, (list, tuple)):
        return "c(" + ", ".join(_lit_r(x) for x in v) + ")"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    return repr(v)


def _una_linea(texto: str | None) -> str:
    """Aplana un texto para meterlo en un comentario de UNA línea.

    Las notas del registro son prosa larga y llevan saltos: 12 de las 38 constantes reales los
    tienen. Un salto dentro de un comentario `#` deja la segunda línea como CÓDIGO en R y en
    Python. Y en TypeScript un `*/` dentro de la nota cierra el comentario antes de tiempo.
    """
    if not texto:
        return ""
    return " ".join(texto.split()).replace("*/", "* /")


def _proc(c: Constante) -> str:
    """La procedencia en una línea, para ponerla al lado del valor."""
    trozos = [f"ev={','.join(c.evidencia) or 'ninguna'}", f"certeza={c.certeza}", c.fuerza]
    if c.unidad:
        trozos.insert(0, c.unidad)
    if c.caduca:
        trozos.append(f"caduca={c.caduca}")
    return " · ".join(trozos)


def emitir(registro: NormRegistry, formato: str, *, orden: str = "capa-normativa-emit …",
           hoy: date | None = None) -> str:
    """El texto del fichero a generar. Determinista: mismo registro ⇒ mismo texto."""
    if formato not in FORMATOS:
        raise ValueError(f"formato desconocido `{formato}`. Válidos: {', '.join(FORMATOS)}")
    cs, omitidas = recoger(registro, hoy=hoy)

    if formato == "json":
        return json.dumps({
            "_generado_por": "capa-normativa · NO EDITAR A MANO",
            "_regenerar": orden,
            "constantes": {c.slug: {"valor": c.valor, "unidad": c.unidad,
                                    "evidencia": list(c.evidencia), "certeza": c.certeza,
                                    "fuerza": c.fuerza, "caduca": c.caduca, "nota": c.nota,
                                    "procedencia": c.procedencia}
                           for c in cs},
            "omitidas": omitidas,
        }, ensure_ascii=False, indent=2, sort_keys=False) + "\n"

    if formato == "python":
        ls = [_cabecera("#", orden), '"""Constantes del registro normativo, con su procedencia."""\n']
        for c in cs:
            ls.append(f"# {_proc(c)}"
                      + (f"\n# {_una_linea(c.nota)}" if c.nota else "")
                      + (f"\n# {_una_linea(c.procedencia)}" if c.procedencia else ""))
            ls.append(f"{c.slug.upper()} = {_lit_py(c.valor)}\n")
        ls.append("#: {slug: {evidencia, certeza, caduca}} — la procedencia, consultable en runtime")
        ls.append("PROCEDENCIA = " + repr({c.slug: {"evidencia": list(c.evidencia),
                                                    "certeza": c.certeza, "caduca": c.caduca}
                                           for c in cs}) + "\n")
        return "\n".join(ls)

    if formato == "typescript":
        ls = [_cabecera("//", orden)]
        for c in cs:
            ls.append(f"/** {_proc(c)}"
                      + (f" — {_una_linea(c.nota)}" if c.nota else "")
                      + (f" — {_una_linea(c.procedencia)}" if c.procedencia else "") + " */")
            ls.append(f"export const {c.slug.upper()} = "
                      f"{_lit_js(c.valor)} as const;\n")
        ls.append("export const PROCEDENCIA = " + json.dumps(
            {c.slug: {"evidencia": list(c.evidencia), "certeza": c.certeza, "caduca": c.caduca}
             for c in cs}, ensure_ascii=False, indent=2) + " as const;\n")
        return "\n".join(ls)

    ls = [_cabecera("#", orden)]                                     # r
    for c in cs:
        ls.append(f"# {_proc(c)}"
                  + (f" — {_una_linea(c.nota)}" if c.nota else "")
                  + (f" — {_una_linea(c.procedencia)}" if c.procedencia else ""))
        ls.append(f"{c.slug.upper()} <- {_lit_r(c.valor)}\n")
    ls.append("# La procedencia, consultable: PROCEDENCIA[['slug']]$evidencia")
    ls.append("PROCEDENCIA <- list(")
    ls.append(",\n".join(
        f"  `{c.slug}` = list(evidencia = {_lit_r(list(c.evidencia))}, "
        f"certeza = {_lit_r(c.certeza)}, caduca = {_lit_r(c.caduca)})" for c in cs))
    ls.append(")\n")
    return "\n".join(ls)


#: La línea del comando de regeneración, en los cuatro formatos: comentario `# Regenerar:  …`
#: (python/r), `// Regenerar:  …` (typescript) y el campo `"_regenerar": …` (json).
_MARCA_ORDEN = re.compile(r'^(?:(?:#|//) Regenerar:  |\s*"_regenerar": ).*\n', re.M)


def _sin_orden(texto: str) -> str:
    """Quita la línea del comando de regeneración antes de comparar.

    Esa línea se compone interpolando los argv tal cual (`emisión.main` → `orden`), así que
    depende de **cómo se escribió la ruta** en la línea de órdenes —`reg` vs `./reg`, `/` vs `\\`,
    relativa vs absoluta—, no del contenido del registro. Compararla ponía `--check` en rojo por
    una diferencia que NO es deriva real (el fichero es byte a byte el mismo salvo un `./`), y un
    check con falsos rojos se desactiva: es justo lo que la invariante de `comprobar` prohíbe.
    """
    return _MARCA_ORDEN.sub("", texto)


def comprobar(registro: NormRegistry, formato: str, fichero: Path | str, *,
              orden: str = "capa-normativa-emit …", hoy: date | None = None) -> str | None:
    """`None` si el fichero coincide con lo que se emitiría; si no, el motivo.

    Compara **normalizando los finales de línea** e **ignorando la línea de regeneración**: un
    check que falla por algo que no es una deriva real se desactiva. Los CRLF vs LF (un repo con
    `core.autocrlf`) y la ortografía de la ruta con la que se invocó (`reg` vs `./reg`) son
    diferencias de forma, no de contenido. Lo primero se aprendió midiendo —un `settings.json` dio
    «70 líneas de diferencia» que eran 35 × 2—; lo segundo, que el comando de regeneración
    empotrado en la cabecera arrastraba los argv literales al artefacto comparado.
    """
    p = Path(fichero)
    if not p.exists():
        return f"no existe `{p}`: hay que generarlo"
    esperado = _sin_orden(emitir(registro, formato, orden=orden, hoy=hoy).replace("\r\n", "\n"))
    actual = _sin_orden(p.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n"))
    if actual != esperado:
        return (f"`{p}` NO coincide con el registro. Alguien editó el fichero generado, o el "
                f"registro cambió y no se regeneró. Ejecuta: {orden}")
    return None


# ─────────────────────────────── CLI ───────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """`0` limpio · `1` hay que regenerar (con `--check`) · `2` no se pudo ejecutar.

    Mismo contrato que el vigilante, y por el mismo motivo: el consumidor previsto es un agente
    sin contexto, y «falló» y «hay deriva» exigen reacciones opuestas.
    """
    import argparse
    import sys

    p = argparse.ArgumentParser(
        prog="capa-normativa-emit",
        description="Exporta las constantes del registro a otro lenguaje, con su procedencia.")
    p.add_argument("registro", help="directorio con schema.yaml, evidence.yaml y norms.yaml")
    p.add_argument("--formato", required=True, choices=FORMATOS)
    p.add_argument("--salida", required=True, metavar="FICHERO")
    p.add_argument("--check", action="store_true",
                   help="no escribe: comprueba que el fichero coincide con el registro. "
                        "Esto es lo que va en CI.")
    a = p.parse_args(argv)

    orden = (f"capa-normativa-emit {a.registro} --formato {a.formato} --salida {a.salida}")
    try:
        registro = NormRegistry.load(a.registro)
    except Exception as e:                                  # noqa: BLE001 — cargar mal es exit 2
        print(f"error: no se pudo cargar el registro: {type(e).__name__}: "
              f"{str(e).splitlines()[0]}", file=sys.stderr)
        return 2

    try:
        if a.check:
            motivo = comprobar(registro, a.formato, a.salida, orden=orden)
            if motivo:
                print(f"DERIVA: {motivo}", file=sys.stderr)
                return 1
            print(f"al día: {a.salida} coincide con el registro.")
            return 0

        texto = emitir(registro, a.formato, orden=orden)
        destino = Path(a.salida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
    except Exception as e:                                  # noqa: BLE001
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    cs, omitidas = recoger(registro)
    print(f"escrito {a.salida}: {len(cs)} constante(s) · {len(omitidas)} omitida(s)")
    if omitidas:
        print("  omitidas (con su motivo, para que no sea una ausencia silenciosa):")
        for slug, motivo in list(omitidas.items())[:8]:
            print(f"    · {slug}: {motivo}")
        if len(omitidas) > 8:
            print(f"    … y {len(omitidas) - 8} más (están todas en el formato json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
