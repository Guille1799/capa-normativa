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
def _subprocesos_con_descriptores_validos():
    """Ningún subproceso de la suite hereda los descriptores del proceso que lanzó pytest.

    ## El fallo, medido el 2026-08-25 y REMEDIDO el 2026-08-26

    La suite dio **60 fallos y 20 errores**. No había ninguna regresión: los 13 ficheros de tests
    que lanzan procesos morían todos con

        OSError: [WinError 6] The handle is invalid

    en `Popen._make_inheritable`, o sea **antes** de arrancar el programa: Windows no puede
    duplicar para el hijo un descriptor que el padre tiene en un estado raro.

    ⚠️ La primera versión de este fixture (2026-08-25) sólo rellenaba `stdin`, y **no bastaba**.
    Medido el 2026-08-26 sobre `tests/test_secretos.py`: **7 corridas rojas de 10**, con `stdin`
    ya en DEVNULL y la traza señalando el duplicado de OTRO descriptor. Los tres se heredan; cerrar
    uno deja los otros dos abiertos. La pista está en el reloj: las corridas malas duran 0,2-0,7 s
    y las buenas 2,0 s — una suite ocho veces más rápida no está pasando más rápido, no está
    corriendo.

    ## Por qué esto es grave y no una molestia

    El gate de `scripts/ralph.sh` es exactamente `pytest tests/ -q`, y **revierte el commit si no
    pasa**. Con 7 de cada 10 corridas rojas por un artefacto, el bucle autónomo deshace trabajo
    correcto la mayoría de las noches y lo apunta como «la tarea no vale». Un instrumento que
    miente así no sólo pierde tiempo: fabrica conclusiones falsas sobre el trabajo hecho.

    ## Por qué aquí y no en cada llamada

    Se podría poner `stdin=DEVNULL, stdout=PIPE, stderr=PIPE` en las trece. Pero entonces la regla
    vive en trece sitios y el test número catorce que alguien escriba mañana no la tendrá — y
    fallará por esto, no por lo que prueba. Aquí se arregla en un sitio y **no se puede olvidar**.

    ## Lo que NO toca, y por qué `run` y `Popen` no se tratan igual

    Si la llamada ya trae `stdin`, `input`, `stdout`, `stderr` o `capture_output`, se respeta tal
    cual: hay tests que alimentan al proceso a propósito —los del canario de hooks le dan cargas
    envenenadas— y otros que leen su salida. Sólo se rellena lo que nadie dijo.

    `run` recibe PIPE y `Popen` recibe DEVNULL, y la asimetría es deliberada: `run` lee las
    tuberías él mismo, así que PIPE es seguro y además deja la salida dentro de
    `CalledProcessError` cuando `check=True`. En `Popen` no hay quien las lea, y una tubería que
    nadie vacía es un cuelgue esperando a un proceso hablador.
    """
    run_original = subprocess.run
    popen_original = subprocess.Popen

    def run(*a, **kw):
        if "stdin" not in kw and "input" not in kw:
            kw["stdin"] = subprocess.DEVNULL
        if not ({"stdout", "stderr", "capture_output"} & set(kw)):
            kw["stdout"] = subprocess.PIPE
            kw["stderr"] = subprocess.PIPE
        return run_original(*a, **kw)

    class Popen(popen_original):
        def __init__(self, *a, **kw):
            if "stdin" not in kw:
                kw["stdin"] = subprocess.DEVNULL
            if "stdout" not in kw:
                kw["stdout"] = subprocess.DEVNULL
            if "stderr" not in kw:
                kw["stderr"] = subprocess.DEVNULL
            super().__init__(*a, **kw)

    subprocess.run = run
    subprocess.Popen = Popen
    try:
        yield
    finally:
        subprocess.run = run_original
        subprocess.Popen = popen_original
