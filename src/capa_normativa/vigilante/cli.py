"""CLI del vigilante. La primera superficie de línea de comandos del paquete.

Contrato: **0** limpio · **1** hay hallazgos · **2** no se pudo ejecutar. Los tres se
distinguen porque el consumidor previsto es un agente sin contexto, y «falló» y «encontró
cosas» exigen reacciones opuestas: la primera se investiga, la segunda se arregla.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import DETECTORES
from .hallazgo import Hallazgo

LIMPIO, HALLAZGOS, ERROR = 0, 1, 2


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="capa-normativa vigilante",
        description="Chequeos deterministas sobre un repo. Sin red, sin LLM, sin dependencias.",
    )
    p.add_argument("ruta", help="repo (para sintaxis) o directorio de .md (para punteros)")
    p.add_argument("--detector", action="append", choices=sorted(DETECTORES),
                   help="detector a correr; repetible. Por defecto: todos")
    p.add_argument("--tambien", action="append", default=[], metavar="DIR",
                   help="corpus adicional para resolver punteros entre repos; repetible")
    p.add_argument("--json", action="store_true", help="salida JSON (para consumo por máquina)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    ruta = Path(args.ruta)
    if not ruta.exists():
        print(f"error: no existe: {ruta}", file=sys.stderr)
        return ERROR

    elegidos = args.detector or sorted(DETECTORES)
    hallazgos: list[Hallazgo] = []
    for nombre in elegidos:
        fn = DETECTORES[nombre]
        try:
            if nombre == "punteros":
                hallazgos.extend(fn(ruta, tambien=args.tambien))
            else:
                hallazgos.extend(fn(ruta))
        except Exception as e:  # noqa: BLE001 — un detector que revienta es exit 2, no 1
            print(f"error: el detector {nombre!r} no pudo ejecutarse: "
                  f"{type(e).__name__}: {e}", file=sys.stderr)
            return ERROR

    if args.json:
        print(json.dumps([asdict(h) for h in hallazgos], ensure_ascii=False, indent=2))
    elif hallazgos:
        for h in hallazgos:
            print(h)
        print(f"\n{len(hallazgos)} hallazgo(s) en {len(elegidos)} detector(es).")
    else:
        print(f"limpio: {len(elegidos)} detector(es), 0 hallazgos.")

    return HALLAZGOS if hallazgos else LIMPIO


if __name__ == "__main__":
    sys.exit(main())
