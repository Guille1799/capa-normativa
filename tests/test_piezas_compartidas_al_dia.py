"""`piezas-compartidas-al-dia` cambia de color de verdad, y por los motivos que dice.

Se le montan repos de pega en un temporal en vez de tocar los cinco de verdad: así se puede exigir
el VERDE, que es la mitad que casi nunca se prueba. Un comprobador que sólo se ha visto en rojo
podría estar rojo por estar roto.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "scripts" / "aceptaciones" / "piezas_compartidas_al_dia.py"

_CUERPO = '''"""Una pieza compartida de mentira."""


def comun_uno():
    return 1


def comun_dos():
    return 2
'''

_EXTRA = '''

def solo_en_dos():
    return 3
'''


def _modulo():
    if not GUION.is_file():
        pytest.skip("no existe piezas_compartidas_al_dia.py")
    spec = importlib.util.spec_from_file_location("piezas_bajo_prueba", str(GUION))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _repo(base: Path, nombre: str, contenido: str) -> None:
    d = base / nombre
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    # `stdin=DEVNULL` no es adorno: bajo la captura de pytest en Windows, un subprocess sin stdin
    # explicito revienta con «WinError 6: The handle is invalid» antes de llegar a ejecutarse.
    subprocess.run(["git", "init", "-q"], cwd=str(d), capture_output=True,
                   stdin=subprocess.DEVNULL, timeout=120)
    (d / "scripts" / "pieza.py").write_text(contenido, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(d), capture_output=True,
                   stdin=subprocess.DEVNULL, timeout=120)


def _montar(mod, tmp_path, contenidos: dict[str, str]):
    for nombre, texto in contenidos.items():
        _repo(tmp_path, nombre, texto)
    mod.RAIZ_PROYECTOS = tmp_path
    mod._REPOS = tuple(contenidos)


def test_verde_cuando_las_copias_estan_al_dia(tmp_path):
    """La mitad que se olvida: si no puede cerrarse, su rojo no significa nada."""
    mod = _modulo()
    _montar(mod, tmp_path, {"uno": _CUERPO, "dos": _CUERPO, "tres": _CUERPO})
    ok, msg = mod.piezas_compartidas_al_dia()
    assert ok, f"tres copias identicas y ha salido ROJO: {msg}"


def test_rojo_cuando_un_TEST_se_queda_atras(tmp_path):
    """El caso real del 2026-08-25: un test en dos copias y ausente en la tercera.

    Es rojo porque un test no tiene nunca sitio donde se le llame y esta pensado para estar en
    todas partes: su ausencia siempre es un hueco.
    """
    mod = _modulo()
    extra = _EXTRA.replace("solo_en_dos", "test_solo_en_dos")
    _montar(mod, tmp_path, {"uno": _CUERPO + extra, "dos": _CUERPO + extra, "tres": _CUERPO})
    ok, msg = mod.piezas_compartidas_al_dia()
    assert not ok, "un test se ha quedado atras y ha salido VERDE"
    assert "tres" in msg

    atrasadas = mod.desfases()
    assert any(f == "test_solo_en_dos" and que == "sin propagar" and otros == ["tres"]
               for _, f, que, _, otros in atrasadas), \
        f"no nombra QUE falta ni DONDE: {atrasadas}"


def test_maquinaria_que_un_repo_no_usa_se_informa_pero_NO_pone_rojo(tmp_path):
    """«Falta» no es «deberia tenerla», y confundirlas es ruido.

    MEDIDO el 2026-08-26: `_fabrica_bug` falta en mcp_smart_context, pero mcp no tiene tabla
    `_BUGS` ni una sola llamada a esa funcion. Copiarla seria meter codigo muerto. Decidir si un
    repo adopta una facilidad del otro es criterio, no automatismo — y un rojo que no se puede
    cerrar sin tomar una decision de diseño se aprende a ignorar.
    """
    mod = _modulo()
    _montar(mod, tmp_path, {"uno": _CUERPO + _EXTRA, "dos": _CUERPO + _EXTRA, "tres": _CUERPO})
    ok, msg = mod.piezas_compartidas_al_dia()
    assert ok, f"una pieza de maquinaria que un repo no usa ha puesto ROJO: {msg}"
    assert "sin poner rojo" in msg, f"tampoco la informa, o sea que se pierde: {msg}"
    assert any(f == "solo_en_dos" and que == "sin adoptar" for _, f, que, _, _ in mod.desfases())


def test_rojo_cuando_una_copia_DIVERGE(tmp_path):
    """El caso que un detector de ausencias NO ve, y es peor: la funcion esta en todas partes,
    pero un cuerpo se fue por su cuenta. Desde fuera parece propagada.

    Medido el 2026-08-25 en los repos de verdad: `_solo_el_comando` esta en los tres y solo
    coincide un 0,46 — y es justo la funcion del fallo de esa noche.
    """
    mod = _modulo()
    distinta = _CUERPO.replace("def comun_dos():\n    return 2",
                               'def comun_dos():\n'
                               '    total = 0\n'
                               '    for i in range(100):\n'
                               '        total += i * 7 - 3\n'
                               '    return total, "nada que ver con la otra version"')
    _montar(mod, tmp_path, {"uno": _CUERPO, "dos": _CUERPO, "tres": distinta})
    ok, msg = mod.piezas_compartidas_al_dia()
    assert not ok, "una copia ha divergido y ha salido VERDE"
    assert "DIVERGIDA" in msg.upper(), f"no distingue divergir de faltar: {msg}"

    assert any(f == "comun_dos" and que == "divergida" for _, f, que, _, _ in mod.desfases()), \
        "no nombra la funcion que divergio"


def test_dos_copias_con_dos_versiones_es_ROJO_aunque_no_haya_mayoria(tmp_path):
    """La rama que estuvo sin un solo test, y es donde se escondia un desacuerdo de verdad.

    ## Que cambio, y por que

    Antes esto solo se INFORMABA, con este argumento: con dos copias y dos versiones no hay
    mayoria, asi que no se sabe cual es la buena y decidirlo es criterio, no automatismo.

    El argumento falla, y se vio con un caso real el 2026-08-30. `_git`, en
    `scripts/aceptacion_de_la_tarea.py` —maquinaria que decide si una tarea del robot cuenta como
    hecha— tenia dos versiones:

        mcp_smart_context   subprocess.run(["git", *args], capture_output=True, ...)
        JobHunter           subprocess.run(["git", *args], cwd=str(RAIZ), ...,
                                           stdin=subprocess.DEVNULL)

    Una de las dos es CLARAMENTE mejor: `cwd` es lo que evita juzgar el arbol equivocado desde el
    worktree del robot (el fallo que bloqueo 34 tareas), y `stdin=DEVNULL` es la proteccion contra
    el `[WinError 6]`. Si se sabia cual era la buena, y el tablero lo mencionaba de pasada al final
    de una linea verde.

    ## Lo que el guardian necesita saber, y lo que no

    No necesita saber cual version es correcta — eso sigue siendo criterio. Necesita saber si
    ALGUIEN HA MIRADO, y eso si lo puede decir una maquina. El rojo ya no significa «alineala con
    la mayoria»: significa «nadie ha decidido esto», y se cierra unificando o escribiendo en
    `_DIVERGENCIAS_ACEPTADAS` por que las dos son correctas.

    Y por eso la popularidad deja de ser el criterio: con tres copias viejas y una arreglada, la
    mayoria es la vieja, y usarla de referencia señalaria el ARREGLO como el error.
    """
    mod = _modulo()
    otra = _CUERPO.replace("def comun_dos():\n    return 2",
                           "def comun_dos():\n    return 2, 'otra version, y nadie ha decidido'")
    _montar(mod, tmp_path, {"uno": _CUERPO, "dos": otra})
    ok, msg = mod.piezas_compartidas_al_dia()
    assert not ok, f"dos versiones sin mayoria han salido VERDE: {msg}"
    assert "comun_dos" in msg, f"no nombra la pieza, asi que no hay nada que mirar: {msg}"
    assert any(f == "comun_dos" and que == "sin decidir" for _, f, que, _, _ in mod.desfases()), \
        "no la clasifica como pendiente de decision"


def test_una_divergencia_SIN_MAYORIA_tambien_se_cierra_por_ESCRITO(tmp_path):
    """La salida del rojo no es solo unificar: tambien vale decir por que las dos son correctas.

    Sin esto, el cambio de criterio crearia rojos incerrables cuando las dos versiones son
    legitimas — y un rojo que no se puede cerrar se aprende a ignorar, que es como muere un
    tablero.
    """
    mod = _modulo()
    otra = _CUERPO.replace("def comun_dos():\n    return 2",
                           "def comun_dos():\n    return 2, 'legitima en su repo'")
    _montar(mod, tmp_path, {"uno": _CUERPO, "dos": otra})
    mod._DIVERGENCIAS_ACEPTADAS = dict(mod._DIVERGENCIAS_ACEPTADAS)
    mod._DIVERGENCIAS_ACEPTADAS["comun_dos"] = ("las dos son correctas y aqui esta escrito por que:"
                                                " cada repo la usa para una cosa distinta. Este es"
                                                " el test de que la exencion escrita cierra el"
                                                " rojo.")
    ok, msg = mod.piezas_compartidas_al_dia()
    assert ok, f"una divergencia ACEPTADA por escrito sigue en rojo: {msg}"


def test_una_sola_presencia_no_cuenta(tmp_path):
    """Algo que existe en UN solo sitio no es una pieza que se quedo atras: es codigo propio.
    Sin esta regla, cada funcion privada de cada repo seria un hallazgo y el aviso seria ruido."""
    mod = _modulo()
    _montar(mod, tmp_path, {"uno": _CUERPO + _EXTRA, "dos": _CUERPO, "tres": _CUERPO})
    ok, _ = mod.piezas_compartidas_al_dia()
    assert ok, "una funcion presente en UNA sola copia no puede contar como desfase"


def test_mismo_nombre_pero_otro_fichero_no_es_la_misma_pieza(tmp_path):
    """`README.md` esta en los cinco y no son la misma pieza. Aqui: mismo nombre, contenido
    completamente distinto — no se comparan."""
    mod = _modulo()
    otro = '"""Otra cosa."""\n\n\ndef nada_que_ver():\n    return "x" * 400\n'
    _montar(mod, tmp_path, {"uno": _CUERPO + _EXTRA, "dos": otro})
    ok, _ = mod.piezas_compartidas_al_dia()
    assert ok, "dos ficheros que solo comparten NOMBRE se han comparado como si fueran la pieza"


def test_una_divergencia_ACEPTADA_no_pone_rojo(tmp_path):
    """Sin esto hay rojos que no se pueden cerrar nunca, y un rojo permanente entrena a mirar para
    otro lado — que es como muere un tablero.

    El caso real del 2026-08-29: `_verifica` difiere entre capa-normativa y mcp porque cada uno
    pone la MISMA invariante en un sitio distinto (mcp dentro del gate, capa-normativa en tres
    tests de la suite). Las dos versiones son correctas.
    """
    mod = _modulo()
    distinta = _CUERPO.replace("return 2", 'return 2 + len("otra version deliberada")')
    _montar(mod, tmp_path, {"uno": _CUERPO, "dos": _CUERPO, "tres": distinta})

    ok, _ = mod.piezas_compartidas_al_dia()
    assert not ok, "sin declararla, la divergencia tiene que poner ROJO"

    mod._DIVERGENCIAS_ACEPTADAS = {"comun_dos": "las dos son correctas, por este motivo escrito"}
    ok, msg = mod.piezas_compartidas_al_dia()
    assert ok, f"declarada como aceptada, no deberia poner rojo: {msg}"
    assert "sin poner rojo" in msg, "y aun asi tiene que SEGUIR APARECIENDO, no desaparecer"


def test_las_divergencias_aceptadas_no_nombran_fantasmas():
    """Una exencion a una funcion que ya no diverge —o que ya no existe— no protege nada y
    despista. Mismo trato que el resto de listas de tolerancia de la casa."""
    mod = _modulo()
    declaradas = set(getattr(mod, "_DIVERGENCIAS_ACEPTADAS", {}))
    if not declaradas:
        pytest.skip("no hay divergencias aceptadas que comprobar")
    try:
        vivas = {f for _, f, que, _, _ in mod.desfases() if que == "divergencia aceptada"}
    except mod.NoSePudoMirar as e:
        pytest.skip(f"no se pudo mirar los repos reales: {e}")
    fantasmas = sorted(declaradas - vivas)
    assert not fantasmas, (
        "declaradas como divergencia aceptada pero ya no divergen (o ya no estan): "
        + ", ".join(fantasmas) + ". Se retiran: una exencion que sobra parece revisada.")


def test_si_no_se_puede_mirar_es_rojo(tmp_path):
    """No haber podido mirar nunca es «todo al dia». La trampa de aprobar en vacio."""
    mod = _modulo()
    mod.RAIZ_PROYECTOS = tmp_path / "no_existe_jamas"
    mod._REPOS = ("uno", "dos")
    ok, msg = mod.piezas_compartidas_al_dia()
    assert not ok and "no se pudo mirar" in msg
