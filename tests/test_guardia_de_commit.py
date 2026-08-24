"""La coartada de `guardia-de-commit`: se le ve distinguir un hook que GRITA de uno que no.

De sus tres condiciones, las dos primeras las aprueba un `touch` —existe el fichero, está
versionado— y **la tercera es la única que prueba algo**: corre el hook contra un repo de pega
con un caso rojo conocido y exige `exit != 0`. Esa tercera nunca se había visto fallar. Para
observarla haría falta romper el `pre-commit` de verdad de este repo, así que en la práctica
estaba sin estrenar: un guardián vigilando a otro guardián, y ninguno de los dos comprobado.

Se le inyecta el mundo por `aceptacion._hook_efectivo()`, que es donde viven las dos primeras
condiciones. El test le devuelve por ahí un `pre-commit` de pega y observa las dos respuestas:

  · un hook que se TRAGA la carga envenenada (sale 0) -> ROJO
  · un hook que GRITA (sale != 0)                     -> VERDE

El primero es el que da sentido a todo: un hook instalado que no muerde es peor que no tener
ninguno, porque parece que sí. Es literalmente el fallo del 2026-08-20 —el escáner recorría cero
ficheros y contestaba «limpio»— y hasta ahora nada había demostrado que este comprobador lo
cazara.
"""

from __future__ import annotations

import pytest

# APARCADO el 2026-08-24, no borrado. Rescatado de `bold-blackburn`, donde llevaba desde
# el 23 sin fusionar: pide `_hook_efectivo`, una costura que el diseño de main no expone.
#
# No se salta en silencio: `guardia_de_commit`
# figura en `_SIN_COARTADA_TODAVIA` de tests/test_coartada_de_los_no_mutables.py, con
# y `test_la_deuda_declarada_SIGUE_siendo_deuda`, asi que el dia que se reescriba este fichero aquel test falla y
# obliga a cerrar las dos puntas a la vez.
pytest.skip("pide `_hook_efectivo`, una costura que el diseño de main no expone", allow_module_level=True)

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TABLERO = RAIZ / "scripts" / "aceptacion.py"


def _tablero():
    spec = importlib.util.spec_from_file_location("tablero_guardia", str(TABLERO))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _hook_de_pega(carpeta: Path, salida: int, grito: str) -> Path:
    """Un `pre-commit` de pega que sale con el código que se le pida.

    Es un script `sh` porque es lo que git ejecuta como hook también en Windows (usa el `sh` que
    trae Git for Windows). No se le da lógica: lo que se está probando es que el COMPROBADOR sepa
    leer el veredicto del hook, no que el hook sepa decidirlo.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    hook = carpeta / "pre-commit"
    hook.write_text("#!/bin/sh" + chr(10)
                    + 'echo "' + grito + '" >&2' + chr(10)
                    + "exit " + str(salida) + chr(10),
                    encoding="utf-8", newline=chr(10))
    hook.chmod(0o755)
    return hook


@pytest.fixture(autouse=True)
def hay_git():
    if shutil.which("git") is None:
        pytest.skip("sin git no hay repo de pega que montar")


def test_un_hook_que_DEJA_PASAR_la_carga_envenenada_es_ROJO(tmp_path, monkeypatch):
    """El caso que motiva este fichero. Un `pre-commit` que sale 0 ante un repo lleno de casos
    rojos conocidos existe, está versionado, y no protege de nada."""
    m = _tablero()
    hook = _hook_de_pega(tmp_path / "hooks_ciegos", 0, "no miro nada y digo que si")
    monkeypatch.setattr(m, "_hook_efectivo", lambda: (hook, ""))
    ok, motivo = m.guardia_de_commit()
    assert ok is False
    assert "DEJO PASAR" in motivo


def test_un_hook_que_GRITA_es_VERDE(tmp_path, monkeypatch):
    """El control. Sin este, un comprobador que dijera ROJO SIEMPRE pasaría el de arriba."""
    m = _tablero()
    hook = _hook_de_pega(tmp_path / "hooks_que_muerden", 1, "secreto detectado, no paso")
    monkeypatch.setattr(m, "_hook_efectivo", lambda: (hook, ""))
    ok, motivo = m.guardia_de_commit()
    assert ok is True, motivo
    assert "grita" in motivo


def test_el_hook_de_pega_se_ejecuta_de_verdad(tmp_path, monkeypatch):
    """La comprobación de que el instrumento mide.

    Un hook que git NUNCA llegara a ejecutar —permisos, `core.hooksPath` mal puesto, `sh` que no
    está— produciría un commit con éxito, o sea el mismo VERDE-que-no-es del test de arriba... y
    los dos tests seguirían pasando. Así que se exige la huella: el hook escribe un fichero al
    correr, y aquí se comprueba que ese fichero apareció.

    Es el instrumento fallando más que lo medido, que en este repo ya ha pasado tres veces.
    """
    m = _tablero()
    carpeta = tmp_path / "hooks_con_huella"
    carpeta.mkdir()
    huella = tmp_path / "corri.txt"
    hook = carpeta / "pre-commit"
    hook.write_text("#!/bin/sh" + chr(10)
                    + 'echo corrido > "' + str(huella).replace(chr(92), "/") + '"' + chr(10)
                    + "exit 1" + chr(10),
                    encoding="utf-8", newline=chr(10))
    hook.chmod(0o755)
    monkeypatch.setattr(m, "_hook_efectivo", lambda: (hook, ""))
    ok, _motivo = m.guardia_de_commit()
    assert huella.exists(), ("git no llego a ejecutar el pre-commit de pega: entonces este "
                             "fichero no prueba nada de lo que dice probar")
    assert ok is True


def test_sin_hook_efectivo_el_motivo_llega_entero(tmp_path, monkeypatch):
    """Las dos primeras condiciones siguen siendo rojas, y con su texto: extraerlas a
    `_hook_efectivo()` no podía ablandarlas."""
    m = _tablero()
    monkeypatch.setattr(m, "_hook_efectivo", lambda: (None, "core.hooksPath sin definir: prueba"))
    ok, motivo = m.guardia_de_commit()
    assert ok is False
    assert motivo == "core.hooksPath sin definir: prueba"


def test_el_repo_de_pega_lleva_casos_rojos_versionados():
    """El repo contra el que se dispara el hook no puede estar vacío.

    Si `repo_de_pega()` dejara de poner ficheros, cualquier `pre-commit` honesto saldría 0 —no
    hay nada que denunciar— y el comprobador diría ROJO acusando al hook de ciego. El
    instrumento culpando a lo medido, otra vez.
    """
    import sys
    sys.path.insert(0, str(RAIZ / "src"))
    from capa_normativa.vigilante.canario import repo_de_pega
    with repo_de_pega() as pega:
        r = subprocess.run(["git", "-C", str(pega), "diff", "--cached", "--name-only"],
                           capture_output=True, text=True, timeout=120)
        assert r.stdout.split(), "el repo de pega no tiene nada versionado que escanear"
