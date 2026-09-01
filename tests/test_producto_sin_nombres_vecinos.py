"""El paquete publicado no nombra los otros proyectos de quien lo escribe.

## Por qué existe

`src/` es lo único que viaja dentro del wheel. Lo instala cualquiera, y sus docstrings se leen
desde el IDE de un desconocido. Una frase como «el venv de <otro-proyecto> tiene 0.7.0 instalada»
es una evidencia excelente y un dato que ahí no pinta nada: quien lee no sabe qué es ese proyecto,
no puede comprobarlo, y aprende el nombre de algo privado a cambio de nada.

MEDIDO el 2026-09-01: tres docstrings de `src/` nombraban dos proyectos vecinos. La evidencia se
conservó entera reescribiéndolas como «un proyecto vecino» — el caso medido sigue ahí, el nombre no.

## La trampa que este test tiene que esquivar, y es la de siempre aquí

La lista de nombres a prohibir **no se puede escribir**: escribirla convertiría este fichero en la
fuga que persigue. Así que se DERIVA del disco, igual que `escaparate_sin_rutas_de_casa.py` deriva
el nombre de usuario en vez de cablearlo.

🔴 Y eso abre el agujero de verdad: **en CI no hay repos hermanos.** Una lista vacía haría que el
`assert` pasara siempre, y el test diría VERDE sin haber mirado nada. Eso es aprobar en vacío, que
en este repo ya costó caro una vez.

Por eso el test tiene TRES salidas y no dos:

  · **pasa**  — se derivaron N vecinos y ninguno aparece en `src/`
  · **falla** — se derivaron N vecinos y alguno aparece
  · **skip**  — no se pudieron derivar, y lo DICE en vez de aprobar

El gate real es local, donde los vecinos existen. En CI queda como skip declarado, que es
información: nadie puede leer el verde de CI como «comprobado».
"""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"


#: Un vecino cuenta solo si es un REPOSITORIO, no cualquier carpeta.
#:
#: MEDIDO el 2026-09-01: la primera versión admitía cualquier carpeta hermana, y el directorio
#: padre tiene `hooks/` y `logs/` sueltas. «hooks» sale en la prosa legítima de medio
#: `vigilante/`, así que el gate denunció CUATRO ficheros correctos en su primera corrida. Un
#: detector que grita por prosa normal se acaba desactivando, y entonces no protege de nada.
#:
#: «Tiene un `.git`» es una propiedad comprobable del disco, no una lista de palabras que alguien
#: tenga que mantener al día.
def _es_repo(d: Path) -> bool:
    return (d / ".git").exists()


def _vecinos() -> list[str]:
    """Nombres de los repos hermanos de este. Vacío si no se pueden enumerar."""
    try:
        candidatos = [d for d in RAIZ.parent.iterdir() if d.is_dir()]
    except OSError:
        return []
    return sorted(
        d.name for d in candidatos
        if d.name != RAIZ.name and not d.name.startswith(".") and _es_repo(d)
    )


def _buscar(raiz: Path, vecinos: list[str], base: Path) -> list[str]:
    """El detector, en UNA función. El canario llama a esta misma, no a una copia suya.

    Un canario que reimplementa la búsqueda prueba la copia y deja al original sin vigilar: si la
    expresión regular del gate se rompe, la del canario sigue funcionando y el verde miente.
    """
    hallazgos = []
    for f in sorted(raiz.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        texto = f.read_text(encoding="utf-8", errors="replace")
        for n, linea in enumerate(texto.splitlines(), 1):
            for vecino in vecinos:
                if re.search(r"\b" + re.escape(vecino) + r"\b", linea):
                    hallazgos.append(
                        "%s:%d nombra un proyecto vecino" % (f.relative_to(base).as_posix(), n))
    return hallazgos


def test_el_paquete_no_nombra_ningun_proyecto_vecino():
    vecinos = _vecinos()
    if not vecinos:
        pytest.skip(
            "no se pudo enumerar ningun repo hermano en %s — este gate solo mide donde los "
            "proyectos vecinos existen en disco. NO leer este skip como 'comprobado'."
            % RAIZ.parent
        )

    hallazgos = _buscar(SRC, vecinos, RAIZ)
    assert not hallazgos, (
        "el paquete publicado nombra %d vez/veces un proyecto vecino:\n    %s\n\n"
        "El nombre no aporta nada a quien instala el wheel y no puede comprobarlo. Reescribe la "
        "frase como «un proyecto vecino» y conserva el caso medido: la evidencia es el caso, no "
        "el nombre.\n"
        "(Se compararon %d repos hermanos. Este mensaje no los lista a proposito.)"
        % (len(hallazgos), "\n    ".join(hallazgos), len(vecinos))
    )


def test_el_gate_muerde_y_no_grita_por_todo(tmp_path):
    """Canario: un detector que no puede fallar, y uno que falla siempre, valen lo mismo: nada.

    Se comprueban las dos mitades sobre la MISMA función que usa el gate:
      · le ponemos delante un nombre real → tiene que cazarlo
      · le pedimos un nombre que no existe → no puede inventárselo
    """
    vecinos = _vecinos()
    if not vecinos:
        pytest.skip("sin repos hermanos no se puede montar el canario")

    cebo = tmp_path / "cebo.py"
    cebo.write_text('"""Habla del proyecto %s por su nombre."""\n' % vecinos[0], encoding="utf-8")

    assert _buscar(tmp_path, vecinos, tmp_path), (
        "el detector no caza un nombre que esta literalmente ahi: su verde no significa nada")
    assert not _buscar(tmp_path, ["nombre-que-no-aparece-en-ningun-sitio"], tmp_path), (
        "el detector encuentra algo que NO esta: grita por todo, y eso tambien es inutil")
