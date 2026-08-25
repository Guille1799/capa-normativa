"""Los tests prueban ESTE repo, no la copia instalada.

Sin esto, `pytest` importa `capa_normativa` de site-packages si está instalado, así
que la suite mide una versión distinta de la que se está editando. Se vio en la v0.2.0:
cinco tests nuevos fallaron contra la 0.1.0 instalada. Fallar por el motivo equivocado
se detecta; el peligro real es el simétrico — **pasar** por el motivo equivocado, con el
código del repo roto y la copia instalada tapándolo.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture(autouse=True, scope="session")
def _subprocesos_con_entrada_valida():
    """Ningún subproceso de la suite hereda la entrada estándar del que lanzó pytest.

    ## El fallo, medido el 2026-08-25

    La suite dio **60 fallos y 20 errores**. No había ninguna regresión: los 13 ficheros de tests
    que lanzan procesos morían todos con

        OSError: [WinError 6] The handle is invalid

    antes de ejecutar nada. La consola desde la que se lanzó pytest tenía la entrada estándar en un
    estado que Windows no puede duplicar para un hijo, y `subprocess` falla al preparar los
    descriptores — o sea **antes** de arrancar el programa. Con una entrada válida: 634 pasan, 0
    fallan.

    Lo peligroso no es perder una hora: es que 60 rojos falsos y una regresión de verdad **se ven
    exactamente igual**. Un instrumento que miente así entrena a desconfiar de los rojos, y ése es
    el camino por el que una suite acaba ignorada.

    ## Por qué aquí y no en cada llamada

    Se podría poner `stdin=DEVNULL` en las trece. Pero entonces la regla vive en trece sitios y el
    test número catorce que alguien escriba mañana no la tendrá — y fallará por esto, no por lo que
    prueba. Aquí se arregla en un sitio y **no se puede olvidar**, que es la diferencia entre
    detectar un fallo e impedirlo.

    ## Lo que NO toca

    Si la llamada ya trae `stdin` o `input`, se respeta tal cual: hay tests que alimentan al
    proceso a propósito —los del canario de hooks le dan cargas envenenadas— y pisarles la entrada
    los rompería de verdad. Sólo se rellena cuando no se dijo nada.
    """
    run_original = subprocess.run
    popen_original = subprocess.Popen

    def run(*a, **kw):
        if "stdin" not in kw and "input" not in kw:
            kw["stdin"] = subprocess.DEVNULL
        return run_original(*a, **kw)

    class Popen(popen_original):
        def __init__(self, *a, **kw):
            if "stdin" not in kw:
                kw["stdin"] = subprocess.DEVNULL
            super().__init__(*a, **kw)

    subprocess.run = run
    subprocess.Popen = Popen
    try:
        yield
    finally:
        subprocess.run = run_original
        subprocess.Popen = popen_original
