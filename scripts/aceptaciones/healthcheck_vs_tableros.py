"""Aceptación de `inv-para-que-el-healthcheck-si-el-tablero`.

## La promesa que mide

G, 2026-08-25, al ver que el tablero tiene mutación y `healthcheck.py` no:

> *«apunta como promesa revisar para qué tenemos healthcheck si los tableros funcionan mejor»*

Nace de una comparación concreta. Los dos mecanismos vigilan, pero solo uno se ataca a sí mismo:

| | tablero (`aceptacion.py`) | `healthcheck.py` |
|---|---|---|
| cadencia | diaria, 08:30 | cada 30 min |
| al fallar | ROJO, avisa al CAMBIAR de color | crea tarea-CONTRATO en la cola del robot |
| se verifica a sí mismo | **sí** (`--verifica`, mutación) | **no** |

La última fila es la que abre la pregunta: un check de `healthcheck.py` que no sepa dispararse se
ve exactamente igual que uno que está pasando. Ya pasó —un guardián que fue no-op en 3 registros y
1.105 transcripts— y por eso la duda no es retórica.

## Por qué esto no se cierra escribiendo prosa

La respuesta puede ser perfectamente *«se queda como está»*: la cadencia de 30 min y el encolado
automático son cosas que el tablero hoy no hace. Lo que NO vale es dejarlo sin decidir. Así que la
aceptación no pide una conclusión concreta — pide que **el veredicto exista y nombre a cada uno de
los checks**, que son los que se quedarían huérfanos si el healthcheck se retirase.

Los nueve nombres se escriben aquí a mano, congelados el 2026-08-25, en vez de leerlos de
`healthcheck.py`. Es a propósito: si se leyeran, añadir un check décimo pondría ROJA esta promesa
por un motivo que no tiene nada que ver con ella, y un comprobador que se pone rojo por algo ajeno
es ruido. La promesa es sobre la DECISIÓN, no sobre mantener un registro al día para siempre.
"""
from __future__ import annotations

import sys
from pathlib import Path

#: El propio árbol, nunca el checkout principal: desde un worktree hay que juzgar el worktree.
#: `scripts/aceptaciones/x.py` -> `scripts/aceptaciones` -> `scripts` -> raíz del repo.
RAIZ = Path(__file__).resolve().parent.parent.parent
DOC = RAIZ / "docs" / "decisiones" / "HEALTHCHECK_VS_TABLEROS.md"

#: Los checks que corría `healthcheck.py` el 2026-08-25, cuando se hizo la promesa.
CHECKS = (
    "HTTP Server", "SQLite", "LanceDB", "Sync", "Proyectos",
    "Docs freshness", "Ultimo reindex", "Procesos", "Fuga AppX",
)


def veredicto(texto: str) -> tuple[bool, str]:
    """El juicio, separado de la lectura del disco — que es lo que se puede testear."""
    if not texto.strip():
        return False, ("no hay veredicto: falta " + DOC.name + ". La promesa es decidir para qué"
                       " sirve healthcheck.py si el tablero se verifica a sí mismo y él no")
    faltan = [c for c in CHECKS if c not in texto]
    if faltan:
        return False, (DOC.name + " existe pero no dice qué pasa con " + str(len(faltan))
                       + " de los " + str(len(CHECKS)) + " checks: " + ", ".join(faltan))
    return True, ("decidido: " + DOC.name + " da veredicto para los " + str(len(CHECKS))
                  + " checks")


def main() -> int:
    texto = DOC.read_text("utf-8") if DOC.is_file() else ""
    ok, msg = veredicto(texto)
    print(("VERDE: " if ok else "ROJO: ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
