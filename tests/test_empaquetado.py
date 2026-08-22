"""El paquete no puede prometer en sus metadatos lo que nadie comprueba.

`pyproject.toml` declara `requires-python = ">="` con una versión mínima, y **pip usa ese campo para
decidir si el paquete se puede instalar**. O sea que una promesa falsa ahí no rompe un test: rompe
una instalación, en la máquina de alguien que hizo todo bien.

Y hasta el 2026-08-12 esa promesa no se había verificado nunca: el desarrollo iba sobre 3.14 y el
paquete llegó a la v0.15.0 **sin CI ninguno** — 242 tests que solo corrían cuando alguien se
acordaba. Es el patrón que el propio paquete persigue (un mecanismo que depende de que alguien se
acuerde no es un mecanismo) aplicado a sí mismo.

El CI (`.github/workflows/ci.yml`) prueba la matriz 3.10 · 3.12 · 3.14 — el mínimo declarado, lo
que corre el inquilino real, y donde se desarrolla. Este fichero comprueba lo que se puede
comprobar SIN esperar al CI: que la sintaxis del paquete entero es válida en la versión mínima que
promete.
"""
from __future__ import annotations

import ast
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def _minimo_declarado() -> tuple[int, int]:
    """La versión mínima que `pyproject.toml` promete. Se LEE, no se escribe a mano aquí: un test
    que repitiera el número dejaría de comprobar nada el día que el `pyproject` cambie."""
    txt = (RAIZ / "pyproject.toml").read_text("utf-8")
    m = re.search(r'requires-python\s*=\s*"[><=~^]*\s*(\d+)\.(\d+)', txt)
    assert m, "no se pudo leer `requires-python` de pyproject.toml"
    return int(m.group(1)), int(m.group(2))


def _version_publicada() -> str:
    """La versión que el paquete DECLARA. Se LEE de `pyproject.toml`: el mismo número que
    `tests/test_registry.py` ata a `__init__.__version__`, así que basta una fuente aquí."""
    txt = (RAIZ / "pyproject.toml").read_text("utf-8")
    m = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', txt)
    assert m, "no se pudo leer `version` de pyproject.toml"
    return m.group(1)


def _fuentes() -> list[pathlib.Path]:
    fuera = []
    for base in ("src", "tests"):
        for p in (RAIZ / base).rglob("*.py"):
            if "__pycache__" not in p.parts:
                fuera.append(p)
    return fuera


def test_la_sintaxis_es_valida_en_la_version_MINIMA_que_se_promete():
    """Parsea cada fichero con `feature_version` = el mínimo declarado.

    ⚠️ LO QUE ESTO **NO** COMPRUEBA, y conviene decirlo para no confundirlo con cobertura: una
    llamada a la biblioteca estándar que solo existe en una versión posterior (`datetime.UTC`,
    `tomllib`, `itertools.batched`) **parsea sin problema** y reventaría en tiempo de ejecución. Eso
    solo lo caza correr los tests en esa versión, y de eso se encarga la matriz del CI.

    Aquí se cubre el error más fácil de cometer y el más silencioso en local: escribir sintaxis
    nueva en una máquina moderna sin enterarse de que rompe el mínimo prometido.
    """
    minimo = _minimo_declarado()
    fuentes = _fuentes()
    assert len(fuentes) > 10, f"solo {len(fuentes)} ficheros: ¿se movió el paquete de sitio?"

    fallos = []
    for p in fuentes:
        try:
            ast.parse(p.read_text("utf-8"), filename=str(p), feature_version=minimo)
        except SyntaxError as e:
            fallos.append(f"{p.relative_to(RAIZ)}:{e.lineno} — {e.msg}")
    assert not fallos, (
        f"sintaxis que NO es válida en Python {minimo[0]}.{minimo[1]}, que es lo que "
        f"`requires-python` promete:\n  " + "\n  ".join(fallos) +
        "\n\nO se arregla, o se sube `requires-python`. Lo que no vale es prometerlo y no cumplirlo: "
        "pip usa ese campo para decidir si se puede instalar.")


def test_el_CI_prueba_la_version_MINIMA_y_la_del_inquilino():
    """El fichero de CI es un dato, no una intención: si alguien quita 3.10 de la matriz, la promesa
    de `requires-python` vuelve a no estar verificada y nadie se enteraría.

    Y 3.12 está por un motivo concreto: es lo que corre el ÚNICO inquilino real (su CI y su
    runtime). Si algo se rompe ahí, se rompe en producción de alguien.
    """
    ci = RAIZ / ".github" / "workflows" / "ci.yml"
    assert ci.exists(), "no hay CI: los tests volverían a correr solo cuando alguien se acuerde"
    txt = ci.read_text("utf-8")

    ma, mi = _minimo_declarado()
    assert f'"{ma}.{mi}"' in txt, (
        f"la matriz del CI no prueba {ma}.{mi}, que es el mínimo que `requires-python` promete")
    assert '"3.12"' in txt, "la matriz dejó de probar 3.12, que es lo que corre el inquilino real"
    assert "pytest" in txt, "el CI dejó de correr los tests"
    assert "capa-normativa-vigilante" in txt, (
        "el CI dejó de aplicarse los detectores a SÍ MISMO. Un paquete que vende detectores y no "
        "se los aplica es difícil de defender")


def test_el_pip_install_del_README_fija_la_version_PUBLICADA():
    """El comando `pip install …@vX.Y.Z` del README es lo que ejecuta un adoptante nuevo. Si el
    tag que fija no es la versión que el paquete DECLARA, se lleva código anterior que se comporta
    distinto sin avisar — el caso literal que este repo persigue (`v0.16.1` escaneaba cero y decía
    «limpio»). El pin está escrito a mano en prosa, sin nada que lo ate al número real; este test
    es esa atadura, y lee la versión de `pyproject.toml` en vez de repetirla aquí.

    Es reincidente: `v0.10.0` ya se coló igual una semana antes.
    """
    version = _version_publicada()
    readme = (RAIZ / "README.md").read_text("utf-8")

    pins = re.findall(r'pip install\s+git\+\S+@v([^\s`]+)', readme)
    assert pins, (
        "no hay ningún `pip install git+…@vX.Y.Z` en el README: ¿se movió el comando de "
        "instalación? Si no hay pin, nadie puede seguir la instalación que el README promete.")
    malos = [p for p in pins if p != version]
    assert not malos, (
        f"el `pip install` del README fija {malos}, pero el paquete publica la v{version} "
        f"(`pyproject.toml` → `version`). Quien siga el README se lleva un tag anterior que se "
        f"comporta distinto sin avisar. El pin y la versión declarada tienen que coincidir.")
