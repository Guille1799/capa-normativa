"""La cobertura REAL, contando también lo que corre en procesos hijos.

## Por qué hace falta un guion y no basta `pytest --cov`

MEDIDO el 2026-08-30: el informe de siempre decía **80 %**, y ese número era del PRODUCTO.
`scripts/canario_hooks.py` salía al **0 %** teniendo seis tests, y no porque no se probara: sus
tests lo lanzan como **proceso aparte** y `coverage` no ve dentro de un hijo. Con la medición de
hijos activada sale al **86 %**, y aparecen once ficheros de `scripts/` que antes ni figuraban.

Catorce de los treinta y un ficheros de test lanzan procesos (42 llamadas). Es lo correcto — es la
única forma de probar que un guardián *arranca de verdad* — pero deja el informe ciego.

## Lo que este guion hace y `pytest --cov` no

Poner `COVERAGE_PROCESS_START`. El fichero `.pth` que arranca la medición en cada intérprete hijo
ya está instalado con `coverage`, pero **sólo se activa si esa variable apunta a la configuración**.
Sin ella el informe vuelve a dar 0 % para todo lo que corra en un hijo, y **no avisa de nada**: un
cero que parece un dato es peor que un error.

## Lo que NO es esto

No es subir el porcentaje: es dejar de no saberlo. El número que sale con los hijos medidos puede
ser peor que el de antes, y eso es el éxito. Un 80 % que no mira la mitad del código no es mejor
que un 70 % que la mira: es menos honesto.

Cuesta unas 2,6× (75 s → 195 s), y por eso la suite normal no lo hace.

    python scripts/cobertura.py            # informe completo
    python scripts/cobertura.py --breve    # solo el total y los peores
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "pyproject.toml"


def main(argv: list[str]) -> int:
    if not CONFIG.is_file():
        print(f"ROJO: no existe {CONFIG.name}, que es donde vive la configuracion de cobertura")
        return 2

    entorno = dict(os.environ)
    # ⚠️ LA LINEA QUE LO HACE TODO. Sin ella los procesos hijos no se miden y el informe miente
    # por omision: dice 0 % de un fichero que SI se prueba, y no hay forma de distinguir ese cero
    # de un cero de verdad.
    entorno["COVERAGE_PROCESS_START"] = str(CONFIG)

    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no", "-p", "no:cacheprovider",
         f"--cov-config={CONFIG}", "--cov=src", "--cov=scripts",
         "--cov-report=term-missing:skip-covered"],
        cwd=str(RAIZ), env=entorno, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)

    lineas = (r.stdout or "").splitlines()
    if "--breve" not in argv:
        print(r.stdout)
        return r.returncode

    filas = []
    for x in lineas:
        m = re.match(r"^(\S+)\s+(\d+)\s+(\d+)\s+(\d+)%", x.strip())
        if m:
            filas.append((int(m.group(4)), m.group(1), m.group(2)))
    total = next((x for x in lineas if x.startswith("TOTAL")), "")
    resumen = [x for x in lineas if " passed" in x or " failed" in x]

    print(f"  {total.strip()}")
    print(f"  {resumen[-1].strip() if resumen else ''}")
    print()
    print("  --- los peor cubiertos ---")
    for pct, nombre, stmts in sorted(filas)[:8]:
        print(f"    {pct:>3}%  {nombre[:58]:<58} {stmts} sentencias")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
