"""MENTIROSOS de `canario-de-los-hooks`: siete hooks de pega, cada uno inútil por un sitio.

## Qué es un mentiroso

Una implementación **completa** de la cosa que el comprobador juzga —aquí, un hook registrado en
`settings.json`, con su fichero y su caso envenenado— rota por **UNA sola razón**, con el test
exigiendo que caiga **en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

## Qué protege

Los hooks son los guardianes que corren en CADA turno, y casi todos **fallan abierto**: si uno
muere, no pasa nada visible y todo sigue igual de verde. `autohealth_monitor.py` llevaba al menos
dos días sin compilar —un `\\n` convertido en un salto de línea de verdad— muriendo con
`SyntaxError` detrás de cada herramienta, y su ficha en el censo decía tan tranquila cuál era su
única salida, **contada a mano leyendo el fuente**. Leer demostró cuál era la salida; sólo
ejecutarlo mostraba que no se llega nunca.

El canario pregunta dos cosas distintas, y la lista de hooks la LEE en vez de escribirla —una
lista a mano envejece en silencio, y el día que se registre uno nuevo seguiría diciendo que están
todos cubiertos—:

  · **ROBUSTEZ**: ante una carga malformada, terminan sin reventar y sin bloquear;
  · **ENVENENADA**: la entrada que cada uno DEBE rechazar. Y ante un hook **sin caso declarado**
    el canario SALTA, en vez de pasar de largo: un guardián sin caso rojo es un guardián que nadie
    ha comprobado.

⚠️ `no_compila` está roto por una sola CAUSA —el fichero no parsea— que produce dos síntomas: no
compila y además sale 1. Por eso `compilan()` vive separado de `robustez()`: un `SyntaxError` no
imprime «Traceback», así que ni siquiera caía en la rama de REVIENTA, y «sale 1 con vacío» es el
mismo síntoma que da un hook que decide bloquear. Confundir un instrumento roto con un hallazgo
cuesta horas, así que lo que se exige aquí es que el motivo lo NOMBRE.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parent.parent / "scripts" / "canario_hooks.py"

#: El canario invoca cada hook con `shell=True` y lee el nombre del trozo del comando que acaba en
#: `.py`, así que una ruta con espacios lo rompería — y eso sería un fallo del test, no del
#: comprobador. Se declara en vez de fingir que se ha medido.
_HAY_ESPACIOS = " " in sys.executable or " " in tempfile.gettempdir()
pytestmark = pytest.mark.skipif(
    _HAY_ESPACIOS,
    reason="el interprete o el TEMP llevan espacios: el comando del hook no se puede escribir sin "
           "comillas, y con comillas el canario no reconoce el nombre. No es un rojo: es no medir")


def _cargar():
    spec = importlib.util.spec_from_file_location("canario_para_mentirosos", str(MODULO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CH = _cargar()

_RAIZ = Path(tempfile.mkdtemp(prefix="mentirososhooks"))

#: La carga que el hook honesto DEBE rechazar. Se declara aquí y se le inyecta al canario como su
#: caso envenenado, igual que los tres casos reales.
_VENENO = b'{"prompt": "esto lleva VENENO dentro"}'

#: El hook HONESTO. Sobrevive a las tres cargas malformadas saliendo 0, y grita ante la suya.
_HONESTO = '''import json
import sys

crudo = sys.stdin.read()
try:
    d = json.loads(crudo or "{}")
except Exception:
    sys.exit(0)                      # basura que no es JSON: no es asunto suyo, falla abierto
if not isinstance(d, dict):
    sys.exit(0)
if "VENENO" in str(d.get("prompt", "")):
    print("bloqueado: la carga trae VENENO", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
'''

#: Mismo hook, sin el `try`. Ante texto que no es JSON sube la excepción: revienta.
_REVIENTA = _HONESTO.replace("try:\n    d = json.loads(crudo or \"{}\")\nexcept Exception:\n"
                             "    sys.exit(0)                      # basura que no es JSON: no es asunto suyo, falla abierto",
                             "d = json.loads(crudo or \"{}\")")

#: Mismo hook, y ante basura sale 1: bloquearía la sesión por algo que no es asunto suyo.
_FALLA_ABIERTO = _HONESTO.replace("    sys.exit(0)                      # basura que no es JSON: no es asunto suyo, falla abierto",
                                  "    sys.exit(1)")

#: Mismo hook, y su veneno le da igual. Es el que más se parece a uno sano: sobrevive a todo.
_NO_GRITA = _HONESTO.replace('    print("bloqueado: la carga trae VENENO", file=sys.stderr)\n'
                             "    sys.exit(2)", "    sys.exit(0)")

#: Un `\\n` convertido en un salto de línea de verdad: el destrozo típico de un reemplazo de texto
#: descuidado sobre una secuencia de escape. Es el caso literal de `autohealth_monitor.py`.
_NO_COMPILA = 'import sys\nmsg = "\n".join(["a", "b"])\nsys.exit(0)\n'


@contextlib.contextmanager
def _montar_veneno():
    yield _VENENO


def _fabrica(nombre, *, cuerpo=_HONESTO, declara_caso=True, hooks=True, existe=True):
    """Un hook registrado, de pega. Por defecto el HONESTO; cada argumento mete UNA mentira."""
    carpeta = _RAIZ / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    fichero = carpeta / (nombre + ".py")
    fichero.write_text(cuerpo, encoding="utf-8")
    ajustes = carpeta / "settings.json"
    if existe:
        entradas = {} if not hooks else {
            "UserPromptSubmit": [{"hooks": [{"type": "command",
                                             "command": sys.executable + " " + str(fichero)}]}]}
        ajustes.write_text(json.dumps({"hooks": entradas}), encoding="utf-8")
    return {"settings": ajustes,
            "casos": {fichero.name: (_montar_veneno, "exit!=0")} if declara_caso else {}}


HONESTO = _fabrica("honesto")


def _sonda(mundo):
    """`canario_hooks.main([])` de verdad, leyendo un `settings.json` de pega.

    Se le cambian sus dos fuentes —dónde está la lista de hooks y qué casos envenenados conoce— y
    se restauran en `finally`: un test que se deja los parches puestos contamina lo que corra
    después, y el daño aparecería lejos de aquí.
    """
    buf = io.StringIO()
    orig = (CH.SETTINGS, CH.CASOS_ENVENENADOS)
    CH.SETTINGS, CH.CASOS_ENVENENADOS = mundo["settings"], mundo["casos"]
    try:
        with contextlib.redirect_stdout(buf):
            codigo = CH.main([])
    finally:
        CH.SETTINGS, CH.CASOS_ENVENENADOS = orig
    return codigo == 0, buf.getvalue()


MENTIROSOS = {
    # No hay lista. Un canario sin nada que vigilar es un canario roto, y su silencio se leería
    # como que los hooks están bien.
    "no_hay_settings": (_fabrica("sin_settings", existe=False), "sin lista no hay canario"),
    # El fichero se lee y no declara ningún hook. Es una RESPUESTA, no un impedimento: en esta
    # máquina es imposible, así que es haber mirado y ver algo que no cuadra.
    "settings_sin_hooks": (_fabrica("sin_hooks", hooks=False), "no declara ningun hook"),
    # El hook no parsea. Está registrado, así que muere detrás de cada herramienta — y como el
    # evento falla abierto, nadie se entera.
    "no_compila": (_fabrica("nocompila", cuerpo=_NO_COMPILA), "NO COMPILA"),
    # Ante texto que no es JSON sube la excepción. Un hook que revienta con basura revienta el día
    # que alguien pegue algo raro en el prompt.
    "revienta_con_basura": (_fabrica("revienta", cuerpo=_REVIENTA), "REVIENTA con"),
    # Sobrevive, y sale 1 ante una carga que no es asunto suyo: bloquearía la sesión por nada.
    "falla_abierto_con_basura": (_fabrica("fallaabierto", cuerpo=_FALLA_ABIERTO),
                                 "declara fallar ABIERTO"),
    # Sobrevive a todo y deja pasar su propia carga envenenada. Es el que más se parece a uno sano
    # — y el único que no protege de nada.
    "no_grita_con_su_veneno": (_fabrica("nogrita", cuerpo=_NO_GRITA), "NO grita"),
    # Un hook perfecto del que nadie ha declarado qué debe rechazar. El canario SALTA en vez de
    # pasar de largo: sin caso rojo, nadie lo ha comprobado nunca.
    "sin_caso_declarado": (_fabrica("sincaso", declara_caso=False),
                           "SIN carga envenenada declarada"),
}


@pytest.fixture(scope="module", autouse=True)
def _limpiar():
    yield
    shutil.rmtree(_RAIZ, ignore_errors=True)


def test_el_hook_honesto_APRUEBA():
    """Sobrevive a las tres cargas malformadas y grita con la suya. Sin esto nada de abajo vale."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    mundo, pista = MENTIROSOS[nombre]
    ok, motivo = _sonda(mundo)
    assert not ok, nombre + " aprobo, y ese hook no vigila nada"
    assert pista in motivo, nombre + " cae por la razon equivocada -> " + motivo


def test_un_hook_que_NO_COMPILA_se_nombra_APARTE_de_los_que_fallan():
    """La razón exacta por la que `compilan()` no se fusionó con `robustez()`.

    Un `SyntaxError` no imprime «Traceback (most recent call last)» —es un error de compilación, no
    una excepción en ejecución— así que ni siquiera caía en la rama de REVIENTA; y el «sale 1 con
    vacío» que sí producía es el mismo mensaje que da un hook que decide bloquear. Sin nombrarlo
    aparte, el diagnóstico correcto no está en ningún sitio.
    """
    mundo, _ = MENTIROSOS["no_compila"]
    _, motivo = _sonda(mundo)
    assert "NO COMPILA" in motivo, motivo
    assert "no llega a arrancar nunca" in motivo, "dice que falla, no que no existe: " + motivo


def test_el_modo_robustez_NO_afirma_que_griten():
    """Un mensaje no puede afirmar más de lo que se comprobó, y aquí no se ha tocado ningún veneno.

    Con `--robustez` el canario ni siquiera monta las cargas envenenadas. Decir que los hooks
    «gritan» sería exactamente la clase de verde que no obliga a nada.
    """
    buf = io.StringIO()
    orig = (CH.SETTINGS, CH.CASOS_ENVENENADOS)
    CH.SETTINGS, CH.CASOS_ENVENENADOS = HONESTO["settings"], {}
    try:
        with contextlib.redirect_stdout(buf):
            codigo = CH.main(["--robustez"])
    finally:
        CH.SETTINGS, CH.CASOS_ENVENENADOS = orig
    assert codigo == 0, buf.getvalue()
    assert "NO se ha probado que rechacen nada" in buf.getvalue(), buf.getvalue()
