"""INVARIANTE DE COARTADA: declararse «no mutable» no exime de haberse visto cambiar de color.

## Por qué existe (medido el 2026-08-23)

`SIN_MUTACION` es la lista de comprobadores a los que `--verifica` no puede atacar: no se les
puede fabricar un artefacto que los ponga verdes, porque su color sale de la fecha de hoy, de
las tareas del sistema o de lo que un hook conteste por stdin. La exención es legítima. El
agujero es lo que la exención se llevaba puesto: **explica cómo NO se comprueba, y ahí se
quedaba**. De las 26 entradas, sólo 3 nombraban algún mecanismo que sí hubiera visto a ese
comprobador moverse.

Y eso importa porque un comprobador SIN ESTRENAR y uno ROTO emiten exactamente la misma señal:
siempre el mismo color. Es el mismo hecho que motiva al canario de los hooks —«un guardián
instalado del que nadie ha visto morder no es un guardián que funciona»— aplicado a los
guardianes de este tablero. Sin coartada, `SIN_MUTACION` era el sitio donde un comprobador roto
podía quedarse a vivir sin que nada lo delatara.

## Qué se exige, exactamente

Cada entrada nombra una COARTADA, en una de dos formas — y las dos se COMPRUEBAN, no se creen:

  1. **Un fichero de tests**: `tests/algo.py` que EXISTE y que además nombra al mecanismo que
     dice cubrir. Lo segundo es lo que impide la coartada barata: citar cualquier fichero de la
     carpeta pasaría el «existe» y no probaría nada.
  2. **Un `--autoprueba`**: el comprobador invoca un comando que trae dentro el check *y* la
     prueba de que el check sabe fallar. Se verifica leyendo el FUENTE del comprobador, no su
     texto: la coartada tiene que estar en lo que se ejecuta.

Para los comprobadores fabricados, el mecanismo es la FÁBRICA (`_fabrica_bug`, `_fabrica_inv`),
no cada entrada: entre las doce de una familia sólo cambia una cadena, así que ver a la máquina
cambiar de color una vez las cubre a todas. Se saca de `__qualname__`, no de una lista escrita a
mano, para que una fábrica nueva no herede la coartada de la vieja en silencio.

⚠️ Esta guarda no puede probar que la coartada sea BUENA — eso lo dice el contenido del test que
nombra. Prueba que exista, que se pueda abrir y que hable de lo que dice hablar. Es el mismo
reparto que en `test_inv_ejecutan_de_verdad.py`: no se afirma el color de nadie, se afirma la
invariante que debe cumplirse siempre.
"""
from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TABLERO = RAIZ / "scripts" / "aceptacion.py"

#: La forma de una coartada de tipo fichero. Se busca dentro del texto de la exención.
_RUTA_DE_TEST = re.compile(r"tests/[A-Za-z0-9_./-]*\.py")

#: La otra forma: el comprobador lleva dentro el comando que se autoprueba.
_AUTOPRUEBA = "--autoprueba"


def _tablero():
    spec = importlib.util.spec_from_file_location("tablero_coartada", str(TABLERO))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TB = _tablero()
EXENTOS = sorted(TB.SIN_MUTACION)


def _cuerpo_ejecutable(fn) -> str:
    """El fuente del comprobador SIN su docstring.

    ⚠️ No es un detalle de estilo, y se cazó mutando: la primera versión miraba
    `inspect.getsource()` entero, y el docstring de `revista_de_runtimes` menciona
    `--autoprueba` dos veces explicando por qué existe. Así que al quitar el `--autoprueba` de la
    llamada real —dejando al comprobador sin su mitad de autoprueba— la guarda seguía en VERDE:
    estaba leyendo la PROSA del comprobador y dándola por ejecutada.

    Es la misma trampa que ya costó cara en `_INV`, donde una explicación viajaba en el campo del
    comando. Una coartada tiene que estar en lo que corre, no en lo que se cuenta.
    """
    import ast
    import textwrap
    definicion = ast.parse(textwrap.dedent(inspect.getsource(fn))).body[0]
    cuerpo = list(getattr(definicion, "body", []))
    if (cuerpo and isinstance(cuerpo[0], ast.Expr)
            and isinstance(cuerpo[0].value, ast.Constant)
            and isinstance(cuerpo[0].value.value, str)):
        cuerpo = cuerpo[1:]
    return chr(10).join(ast.unparse(n) for n in cuerpo)


def _se_autoprueba(nombre: str, texto: str) -> bool:
    """La segunda forma de coartada: el comprobador invoca un comando que se prueba a sí mismo.

    Se exigen las DOS mitades, y ese es todo el truco: que la exención lo diga (`texto`) **y**
    que el comprobador lo EJECUTE (su cuerpo, sin docstring). Sólo con el texto, cualquiera se
    declara autoprobado escribiendo la palabra; sólo con el fuente, no queda dicho en la lista
    que es ahí donde vive su coartada.
    """
    if _AUTOPRUEBA not in texto:
        return False
    fn = TB.COMPROBADORES.get(nombre)
    return fn is not None and _AUTOPRUEBA in _cuerpo_ejecutable(fn)


def _mecanismo(nombre: str) -> str:
    """Qué pieza tiene que nombrar la coartada de este comprobador.

    Para uno escrito a mano, él mismo. Para uno fabricado, la FÁBRICA que lo produce: es la
    máquina que decide su color, y es lo único que un test puede observar cambiar.

    De un fantasma —exención sin comprobador— se devuelve su nombre a secas en vez de reventar
    con un `KeyError`: quien denuncia ese caso es `test_SIN_MUTACION_no_nombra_fantasmas`, con su
    motivo escrito, y una excepción cruda aquí sólo taparía ese mensaje con ruido.
    """
    fn = TB.COMPROBADORES.get(nombre)
    if fn is None:
        return nombre.replace("-", "_")
    cualificado = getattr(fn, "__qualname__", fn.__name__)
    return cualificado.split(".")[0] if "<locals>" in cualificado else fn.__name__


#: DEUDA DECLARADA: comprobadores que todavia no tienen coartada, con el motivo por el que no la
#: tienen. Va con `xfail(strict=True)` a proposito — **el andamio se retira solo**: el dia que
#: alguien escriba la coartada de uno, este test FALLA y obliga a sacarlo de aqui. Es el mismo
#: mecanismo que el 2026-08-24 cazo a `inv-audit-settings-source-sh-no` el mismo dia que se arreglo.
#:
#: Los tres primeros TIENEN test escrito —rescatado de `bold-blackburn`— pero contra OTRO diseño de
#: `aceptacion.py`: piden costuras (`_hook_efectivo`, `REGISTRO...`) que este no tiene. Citarlos
#: igualmente habria puesto la invariante verde con los tests saltados, que es este mismo agujero
#: un piso mas arriba.
#: VACIA desde el 2026-08-24, y ese es el estado bueno: ninguna exencion de `SIN_MUTACION` se
#: queda sin alguien que haya visto a ese comprobador cambiar de color. Nacio con cuatro
#: entradas esa misma noche y se vacio en la misma sesion, cerrando cada una con su test en vez
#: de con una excusa. Si vuelve a llenarse, que sea con motivo escrito y por poco tiempo.
#:
#: `test_la_deuda_declarada_SIGUE_siendo_deuda` se salta con la lista vacia («got empty parameter
#: set»), y eso es correcto: no hay deuda que vigilar.
_SIN_COARTADA_TODAVIA: dict[str, str] = {}


@pytest.mark.parametrize("nombre", sorted(_SIN_COARTADA_TODAVIA))
def test_la_deuda_declarada_SIGUE_siendo_deuda(nombre):
    """EL ANDAMIO QUE SE RETIRA SOLO.

    Saltar los tres tests para los declarados deja un agujero obvio: nadie se entera de que la
    deuda esta pagada, y el nombre se queda en la lista para siempre. Este test mira lo contrario
    —que la coartada SIGUE sin existir— asi que el dia que alguien la escriba, FALLA y obliga a
    sacar el nombre de `_SIN_COARTADA_TODAVIA`.
    """
    texto = str(TB.SIN_MUTACION[nombre])
    pieza = _mecanismo(nombre)
    validas = [r for r in _RUTA_DE_TEST.findall(texto)
               if (RAIZ / r).is_file()
               and pieza in (RAIZ / r).read_text("utf-8", errors="replace")]
    assert not validas, (
        nombre + ": ya tiene una coartada valida (" + ", ".join(validas) + "). Sacalo de "
        "_SIN_COARTADA_TODAVIA: la lista de deuda solo vale si se vacia.")


def test_la_deuda_declarada_existe_de_verdad():
    """Un nombre en la lista de deuda que ya no esta exento es un fantasma, y los fantasmas hacen
    que la lista deje de leerse."""
    fantasmas = sorted(set(_SIN_COARTADA_TODAVIA) - set(EXENTOS))
    assert not fantasmas, (
        "estos nombres estan declarados sin coartada pero ya no son exentos: " + ", ".join(fantasmas)
        + ". Sacalos de _SIN_COARTADA_TODAVIA.")


@pytest.mark.parametrize("nombre", EXENTOS)
def test_cada_exencion_nombra_una_coartada(nombre):
    """Una exención que no dice quién ha visto moverse a este comprobador no es una exención:
    es un comprobador sin estrenar con permiso escrito para seguir sin estrenarse."""
    if nombre in _SIN_COARTADA_TODAVIA:
        pytest.skip("deuda declarada: " + _SIN_COARTADA_TODAVIA[nombre])
    texto = str(TB.SIN_MUTACION[nombre])
    if _se_autoprueba(nombre, texto):
        return
    assert _RUTA_DE_TEST.search(texto), (
        nombre + ": declarado no mutable y sin coartada. Su texto explica como NO se comprueba, "
        "pero no nombra nada que lo haya visto cambiar de color — asi que un fallo suyo y su "
        "estado normal son el mismo color para siempre. Se arregla nombrando un fichero "
        "tests/*.py que lo ejerza, o un `--autoprueba` que el propio comprobador invoque. Si no "
        "se puede tener ninguno de los dos, la exencion debe CONFESARLO con su motivo en vez de "
        "callarlo, y este test hay que cambiarlo a la vez.")


@pytest.mark.parametrize("nombre", EXENTOS)
def test_la_coartada_que_nombra_EXISTE(nombre):
    """Una coartada que apunta a un fichero borrado o renombrado se lee igual de bien que una
    buena. Es la forma en que estas listas se pudren: nadie vuelve a abrirlas."""
    if nombre in _SIN_COARTADA_TODAVIA:
        pytest.skip("deuda declarada: " + _SIN_COARTADA_TODAVIA[nombre])
    texto = str(TB.SIN_MUTACION[nombre])
    if _se_autoprueba(nombre, texto):
        return
    ausentes = [r for r in _RUTA_DE_TEST.findall(texto) if not (RAIZ / r).is_file()]
    assert not ausentes, (
        nombre + ": su coartada nombra " + ", ".join(ausentes) + ", que no existe.")


@pytest.mark.parametrize("nombre", EXENTOS)
def test_la_coartada_HABLA_del_mecanismo_que_cubre(nombre):
    """La guarda contra la coartada barata: citar un fichero cualquiera de `tests/`.

    Se exige que el fichero nombrado mencione la pieza que dice ejercer —el comprobador, o la
    fábrica que lo produce—. No demuestra que el test sea bueno; sí impide que sea de otro.
    """
    if nombre in _SIN_COARTADA_TODAVIA:
        pytest.skip("deuda declarada: " + _SIN_COARTADA_TODAVIA[nombre])
    texto = str(TB.SIN_MUTACION[nombre])
    if _se_autoprueba(nombre, texto):
        return
    pieza = _mecanismo(nombre)
    rutas = _RUTA_DE_TEST.findall(texto)
    hablan = [r for r in rutas
              if (RAIZ / r).is_file() and pieza in (RAIZ / r).read_text("utf-8", errors="replace")]
    assert hablan, (
        nombre + ": nombra " + ", ".join(rutas) + " como coartada, pero ninguno menciona `"
        + pieza + "`. Una coartada que no habla del mecanismo que cubre no lo ha visto moverse.")


def test_hay_exenciones_que_comprobar():
    """Un parametrize sobre una lista vacía son cero tests, y cero tests en verde parecen éxito.

    Ya pasó en este mismo tablero por otra puerta: `sin_caso()` del canario existe precisamente
    porque saltarse lo que no está declarado se lee como «todo cubierto».
    """
    assert EXENTOS, "no se leyo SIN_MUTACION: los tests de arriba estarian pasando en vacio"


def test_SIN_MUTACION_no_nombra_fantasmas():
    """Una exención a un comprobador que ya no está en el tablero no protege nada y descuadra.

    No es hipotético: `canario-completo` se jubiló a `CUMPLIDAS` el 2026-08-23 y su exención se
    quedó atrás. Con 27 exenciones para 26 comprobadores, `--verifica` imprimía
    «-1/-1 verificados por mutación», que es un instrumento contando mal delante de todos.
    """
    fantasmas = sorted(set(TB.SIN_MUTACION) - set(TB.COMPROBADORES))
    assert not fantasmas, (
        "declarados no mutables pero ya no estan en COMPROBADORES: " + ", ".join(fantasmas)
        + ". Se retiran con el comprobador, no despues.")


def test_la_cuenta_de_verificados_por_mutacion_no_sale_negativa():
    """La consecuencia observable del test de arriba, medida donde el usuario la lee.

    Se comprueba la aritmética que imprime `--verifica`, no el texto: un total negativo o un
    denominador negativo son la señal de que las dos listas se han desincronizado.
    """
    verificables = len(TB.COMPROBADORES) - len(TB.SIN_MUTACION)
    assert verificables >= 0, (
        "hay " + str(len(TB.SIN_MUTACION)) + " exenciones para " + str(len(TB.COMPROBADORES))
        + " comprobadores: --verifica imprimiria una cuenta negativa.")
