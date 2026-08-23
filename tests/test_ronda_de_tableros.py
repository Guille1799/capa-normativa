"""La ronda de tableros: que sepa ponerse ROJA, y que no apruebe en vacío.

`ronda-de-tableros` no se puede verificar con `aceptacion.py --verifica` —está en `SIN_MUTACION`—
porque su rojo no depende de que exista un fichero, sino de dos hechos que no se escriben: el
`LastRunTime` que Windows guarda de la tarea y un informe que diga que lo lanzó ella. Si bastara
con dejar un fichero en su sitio, la promesa se aprobaría **falsificando la evidencia**.

Así que su prueba por mutación está aquí, y es mejor que la del tablero: `veredicto()` es una
función **pura** —se le entregan el informe, la hora y el último arranque, y no mira el disco—,
así que se le puede pasar el mundo que haga falta sin tocar la máquina.

Los cinco rojos que exigió G, cada uno con su caso:

  · informe ausente          -> `test_rojo_sin_informe`
  · informe viejo            -> `test_rojo_con_informe_viejo`
  · cero tableros            -> `test_rojo_con_cero_tableros_descubiertos`
  · la tarea nunca arrancó   -> `test_rojo_si_la_tarea_no_ha_arrancado_nunca`
  · lanzado a mano           -> `test_rojo_si_lo_lanzo_una_persona`

Y el que hace que los otros signifiquen algo: **`test_verde_cuando_todo_esta_en_su_sitio`**. Un
comprobador que no sabe ponerse verde es tan inútil como uno que no sabe ponerse rojo — parece
severo y en realidad no mide.
"""
from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
GUION = RAIZ / "scripts" / "ronda_de_tableros.py"
AHORA = datetime(2026, 8, 24, 9, 0, 0)


def _cargar(**entorno):
    """Una instancia FRESCA del lanzador, con el entorno que se le diga.

    Se recarga en vez de reutilizar el módulo porque sus rutas se resuelven al importar: sin esto,
    un test que apunta a un árbol de mentira contaminaría al siguiente.
    """
    previos = {k: os.environ.get(k) for k in entorno}
    os.environ.update({k: str(v) for k, v in entorno.items()})
    try:
        spec = importlib.util.spec_from_file_location("ronda_bajo_prueba", str(GUION))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        for k, v in previos.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


RONDA = _cargar()


def _informe(**cambios) -> dict:
    """Un informe SANO, del que cada test estropea exactamente una cosa.

    Partir de lo sano y romper una pieza es lo que hace que el rojo se pueda atribuir: si cada
    test construyera su propio informe, un rojo podría venir de cualquier parte.
    """
    base = {
        "version": 1,
        "iniciado": (AHORA - timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%S"),
        "terminado": (AHORA - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S"),
        "lanzador": "tarea-programada",
        "duracion_s": 1800.0,
        "declarados": 7,
        "corridos": 7,
        "tableros": [{"nombre": "t" + str(i), "estado": "ok", "verdes": 3, "rojos": ["r" + str(i)],
                      "cumplidas": [], "exit": 1, "duracion_s": 10.0, "detalle": "",
                      "verifica": {"exit": 0, "duracion_s": 2.0, "resumen": "3/3 verificados"}}
                     for i in range(7)],
        "huerfanos": [],
        "ausentes": [],
        "nuevos_rojos": {},
        "resueltos": {},
    }
    base.update(cambios)
    return base


ARRANQUE_FRESCO = AHORA - timedelta(minutes=45)


# ── los rojos que G exigió ───────────────────────────────────────────────────────────────────

def test_verde_cuando_todo_esta_en_su_sitio():
    """Sin este, los demás no prueban nada: un comprobador que jamás se pone verde no mide."""
    ok, motivo = RONDA.veredicto(_informe(), AHORA, ARRANQUE_FRESCO)
    assert ok, motivo
    assert "7 tableros" in motivo


def test_rojo_sin_informe():
    ok, motivo = RONDA.veredicto(None, AHORA, ARRANQUE_FRESCO)
    assert not ok
    assert "no deja evidencia" in motivo


def test_rojo_con_informe_viejo():
    """La ronda es diaria; a las 60 h ya se ha saltado dos, y eso es que ha dejado de correr."""
    viejo = _informe(terminado=(AHORA - timedelta(hours=60)).strftime("%Y-%m-%dT%H:%M:%S"))
    ok, motivo = RONDA.veredicto(viejo, AHORA, ARRANQUE_FRESCO)
    assert not ok
    assert "hace 60 h" in motivo


def test_verde_con_informe_de_ayer():
    """La ventana tolera UNA ausencia a propósito: un rojo falso al día enseña a ignorar."""
    ayer = _informe(terminado=(AHORA - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%S"))
    ok, _ = RONDA.veredicto(ayer, AHORA, ARRANQUE_FRESCO)
    assert ok


def test_rojo_con_informe_sin_fecha():
    """Un informe que no dice cuándo terminó no es evidencia de nada."""
    ok, motivo = RONDA.veredicto(_informe(terminado=None), AHORA, ARRANQUE_FRESCO)
    assert not ok
    assert "cuando termino" in motivo


@pytest.mark.parametrize("corridos", [0, 1, 6])
def test_rojo_con_cero_tableros_descubiertos(corridos):
    """**No aprueba en vacío.** Cero tableros no es «todo verde», es «no he mirado nada».

    Es el modo de fallo más caro de un guarda, porque su silencio se lee como buenas noticias, y
    por eso va parametrizado hasta el suelo: seis de siete tampoco vale.
    """
    flojo = _informe(corridos=corridos, tableros=_informe()["tableros"][:corridos])
    ok, motivo = RONDA.veredicto(flojo, AHORA, ARRANQUE_FRESCO)
    assert not ok
    assert "solo corrio " + str(corridos) in motivo


def test_rojo_si_la_tarea_no_ha_arrancado_nunca():
    """Registrada no es lo mismo que arrancando — el error exacto de `ollama_chain`."""
    ok, motivo = RONDA.veredicto(_informe(), AHORA, None)
    assert not ok
    assert "NUNCA ha arrancado" in motivo


def test_rojo_si_la_tarea_dejo_de_arrancar():
    ok, motivo = RONDA.veredicto(_informe(), AHORA, AHORA - timedelta(hours=200))
    assert not ok
    assert "ha dejado de correr" in motivo


def test_rojo_si_lo_lanzo_una_persona():
    """Un informe escrito a mano demuestra que el guion funciona, no que la ronda corra sola."""
    ok, motivo = RONDA.veredicto(_informe(lanzador="a mano"), AHORA, ARRANQUE_FRESCO)
    assert not ok
    assert "a mano" in motivo


def test_rojo_si_un_tablero_no_se_pudo_leer():
    """Rojos DENTRO de un tablero son el dato que la ronda recoge; un tablero caído es un agujero."""
    roto = _informe()
    roto["tableros"][2]["estado"] = "ilegible"
    ok, motivo = RONDA.veredicto(roto, AHORA, ARRANQUE_FRESCO)
    assert not ok
    assert "no pudo leer 1 tablero" in motivo


def test_verde_aunque_todos_los_tableros_esten_rojos():
    """Recoger rojos ES su trabajo. Si los rojos la pusieran roja, se confundirían dos hechos."""
    muy_rojo = _informe()
    for t in muy_rojo["tableros"]:
        t["rojos"] = ["a", "b", "c"]
    ok, motivo = RONDA.veredicto(muy_rojo, AHORA, ARRANQUE_FRESCO)
    assert ok, motivo
    assert "21 rojo(s) recogidos" in motivo


def test_rojo_si_no_llego_a_correr_verifica():
    """`--verifica` es quien vigila a los vigilantes: comprueba que cada comprobador sabe ponerse
    rojo. Tableros corriendo solos con comprobadores que ya no saben fallar son verdes que no
    significan nada, y eso es peor que no tener tablero."""
    sin = _informe()
    sin["tableros"][3]["verifica"] = {"exit": None, "duracion_s": 0.0, "resumen": "se cuelga"}
    ok, motivo = RONDA.veredicto(sin, AHORA, ARRANQUE_FRESCO)
    assert not ok
    assert "no llego a correr `--verifica`" in motivo


def test_verde_si_verifica_lo_corre_OTRA_tarea():
    """La segunda puerta: si ya hay una tarea programada que ejecuta `--verifica` por su cuenta, la
    ronda no tiene que hacerlo. Está para no atar la promesa a esta implementación concreta."""
    sin = _informe()
    for t in sin["tableros"]:
        t["verifica"] = {"exit": None, "duracion_s": 0.0, "resumen": "no se llego a correr"}
    assert not RONDA.veredicto(sin, AHORA, ARRANQUE_FRESCO)[0]
    ok, _ = RONDA.veredicto(sin, AHORA, ARRANQUE_FRESCO, verifica_por_tarea=True)
    assert ok


def test_que_verifica_FALLE_no_pone_roja_la_promesa():
    """Distinción que costó cinco tareas incerrables el 2026-08-22: un `--verifica` que falla es un
    rojo del tablero AJENO, no una avería de la ronda. Se recoge, se avisa del cambio, y se dice en
    el motivo — pero no bloquea esta promesa."""
    fallando = _informe()
    fallando["tableros"][1]["verifica"] = {"exit": 1, "duracion_s": 3.0, "resumen": "2/3"}
    ok, motivo = RONDA.veredicto(fallando, AHORA, ARRANQUE_FRESCO)
    assert ok, motivo
    assert "--verifica falla en t1" in motivo


def test_la_firma_cambia_cuando_verifica_empieza_a_fallar():
    """Si no entrara en la firma, el día que la prueba por mutación de un tablero se rompa no se
    enteraría nadie: no hay rojo nuevo que contar."""
    antes = RONDA.firma([{"nombre": "t", "estado": "ok", "rojos": ["x"],
                          "verifica": {"exit": 0}}], [], [])
    despues = RONDA.firma([{"nombre": "t", "estado": "ok", "rojos": ["x"],
                            "verifica": {"exit": 1}}], [], [])
    assert antes != despues


def test_rojo_con_un_tablero_huerfano():
    """Un tablero que nadie vigila ni ha declarado deja la ronda incompleta sin que se note."""
    ok, motivo = RONDA.veredicto(_informe(huerfanos=["nuevo-repo"]), AHORA, ARRANQUE_FRESCO)
    assert not ok
    assert "nadie vigila" in motivo


def test_rojo_con_un_tablero_declarado_que_desaparecio():
    ok, motivo = RONDA.veredicto(_informe(ausentes=["cn-ralph (cn-ralph)"]), AHORA,
                                 ARRANQUE_FRESCO)
    assert not ok
    assert "ya no estan" in motivo


# ── leer la salida de un tablero: el color viaja en un emoji ─────────────────────────────────

_SALIDA_REAL = (
    "  \U0001F7E2 guardia-de-commit        el pre-commit esta versionado y grita" + chr(10)
    + "  \U0001F534 canario-de-los-hooks     9 hooks sin caso declarado" + chr(10)
    + "  \U0001F534 revista-de-runtimes      cuatro interpretes divergentes" + chr(10)
    + chr(10) + "  1/3 promesas cumplidas." + chr(10))


def test_lee_una_salida_normal():
    r = RONDA.leer_tablero(_SALIDA_REAL)
    assert r["legible"]
    assert r["verdes"] == ["guardia-de-commit"]
    assert r["rojos"] == ["canario-de-los-hooks", "revista-de-runtimes"]


def test_los_emojis_muertos_dan_ILEGIBLE_y_no_cero_rojos():
    """El fallo que la ronda no se puede permitir: contar cero rojos porque el color se perdió.

    En una tubería con codificación de consola (cp1252 aquí), y con el `errors="replace"` que
    todos los tableros se ponen, 🟢 y 🔴 se degradan al MISMO `?`. Sin el contraste contra la
    línea de resumen, esto se leería como «ningún rojo» — la mentira exacta que un guarda no
    puede decir.
    """
    degradada = _SALIDA_REAL.replace("\U0001F7E2", "?").replace("\U0001F534", "?")
    r = RONDA.leer_tablero(degradada)
    assert not r["legible"]
    assert r["rojos"] == []          # y por eso NO se puede confiar en el recuento
    assert "no cuadra" in r["porque"]


def test_una_salida_sin_resumen_es_ILEGIBLE():
    """Sin la línea de resumen no hay con qué contrastar, así que no hay veredicto que dar."""
    r = RONDA.leer_tablero("  \U0001F534 lo-que-sea    algo" + chr(10))
    assert not r["legible"]
    assert "resumen" in r["porque"]


def test_un_tablero_que_revienta_a_medias_es_ILEGIBLE():
    """Si el tablero muere tras imprimir dos líneas, el recuento parcial no cuadra y se dice."""
    a_medias = _SALIDA_REAL.replace("  1/3 promesas cumplidas.", "  1/9 promesas cumplidas.")
    r = RONDA.leer_tablero(a_medias)
    assert not r["legible"]


def test_las_cumplidas_no_se_cuentan_como_promesas():
    """Las ✅ son promesas retiradas: informan, pero no entran en el N/M del tablero."""
    con_cumplida = "  ✅ contexto-propio cumplida el 2026-08-23" + chr(10) + _SALIDA_REAL
    r = RONDA.leer_tablero(con_cumplida)
    assert r["legible"]
    assert r["cumplidas"] == ["contexto-propio"]


# ── lo NUEVO es lo que importa ───────────────────────────────────────────────────────────────

def test_solo_se_denuncia_lo_que_no_estaba_antes():
    previo = {"tableros": [{"nombre": "a", "rojos": ["viejo"]}]}
    ahora = [{"nombre": "a", "rojos": ["viejo", "recien"]}]
    nuevos, resueltos = RONDA.comparar(ahora, previo)
    assert nuevos == {"a": ["recien"]}
    assert resueltos == {}


def test_se_registra_lo_que_se_ha_cerrado():
    previo = {"tableros": [{"nombre": "a", "rojos": ["uno", "dos"]}]}
    nuevos, resueltos = RONDA.comparar([{"nombre": "a", "rojos": ["dos"]}], previo)
    assert nuevos == {}
    assert resueltos == {"a": ["uno"]}


def test_en_la_primera_ronda_todo_rojo_es_nuevo():
    """Y está bien que lo sea: es literalmente la primera vez que alguien mira."""
    nuevos, _ = RONDA.comparar([{"nombre": "a", "rojos": ["x"]}], None)
    assert nuevos == {"a": ["x"]}


def test_un_tablero_que_aparece_por_primera_vez_no_ensucia_el_diff():
    """Sólo sus rojos son nuevos; los del tablero que ya estaba y no cambió, no."""
    previo = {"tableros": [{"nombre": "a", "rojos": ["x"]}]}
    nuevos, _ = RONDA.comparar([{"nombre": "a", "rojos": ["x"]},
                                {"nombre": "b", "rojos": ["y"]}], previo)
    assert nuevos == {"b": ["y"]}


# ── avisar en el CAMBIO, no en cada corrida ──────────────────────────────────────────────────

def test_no_se_reavisa_por_la_misma_causa():
    """La lección de `inv-el-healthcheck-avisa-cada-30`: 19 avisos en 19 corridas por una causa."""
    estado = {"firma": "F", "ts": 1000.0}
    toca, motivo = RONDA.decidir_aviso("F", estado, 1000.0 + 3600)
    assert not toca
    assert "misma causa" in motivo


def test_se_avisa_cuando_la_firma_cambia():
    toca, _ = RONDA.decidir_aviso("G", {"firma": "F", "ts": 1000.0}, 1000.0 + 60)
    assert toca


def test_se_recuerda_una_vez_por_semana_si_el_rojo_se_enquista():
    toca, motivo = RONDA.decidir_aviso("F", {"firma": "F", "ts": 1000.0},
                                       1000.0 + RONDA.RECORDATORIO_S + 1)
    assert toca
    assert "semana" in motivo


def test_se_avisa_la_primera_vez():
    toca, _ = RONDA.decidir_aviso("F", None, 1000.0)
    assert toca


def test_la_firma_lleva_los_NOMBRES_y_no_el_numero_de_rojos():
    """Tres rojos que se cambian por otros tres distintos son un cambio de estado, y contarlos
    no lo vería."""
    a = RONDA.firma([{"nombre": "t", "estado": "ok", "rojos": ["x", "y", "z"]}], [], [])
    b = RONDA.firma([{"nombre": "t", "estado": "ok", "rojos": ["p", "q", "r"]}], [], [])
    assert a != b


def test_un_tablero_caido_cambia_la_firma_aunque_no_tenga_rojos():
    a = RONDA.firma([{"nombre": "t", "estado": "ok", "rojos": []}], [], [])
    b = RONDA.firma([{"nombre": "t", "estado": "caido", "rojos": []}], [], [])
    assert a != b


# ── la lista de tableros no puede envejecer en silencio ──────────────────────────────────────

def _arbol_de_mentira(tmp: Path, subrutas) -> Path:
    for s in subrutas:
        d = tmp / s / "scripts"
        d.mkdir(parents=True, exist_ok=True)
        (d / "aceptacion.py").write_text("# de mentira" + chr(10), encoding="utf-8")
    return tmp


def test_un_tablero_nuevo_sale_denunciado_como_huerfano(tmp_path):
    """El día que nazca un tablero, la lista escrita seguiría diciendo que están todos.

    Por eso además de la lista hay un barrido del disco: el andamio se retira solo.
    """
    raiz = _arbol_de_mentira(tmp_path, [s for _, s, _ in RONDA._TABLEROS] + ["repo-recien-nacido"])
    m = _cargar(RONDA_PROYECTOS=raiz)
    _, ausentes, huerfanos = m.descubrir()
    assert huerfanos == ["repo-recien-nacido"]
    assert ausentes == []


def test_un_tablero_declarado_que_desaparece_sale_como_ausente(tmp_path):
    subrutas = [s for _, s, _ in RONDA._TABLEROS if not s.startswith("cn-ralph")]
    raiz = _arbol_de_mentira(tmp_path, subrutas)
    m = _cargar(RONDA_PROYECTOS=raiz)
    vigilados, ausentes, _ = m.descubrir()
    assert len(vigilados) == 6
    assert ausentes == ["cn-ralph (cn-ralph)"]


def test_las_carpetas_excluidas_no_salen_como_huerfanas(tmp_path):
    raiz = _arbol_de_mentira(tmp_path, [s for _, s, _ in RONDA._TABLEROS]
                             + list(RONDA._CARPETAS_NO_VIGILADAS))
    m = _cargar(RONDA_PROYECTOS=raiz)
    _, _, huerfanos = m.descubrir()
    assert huerfanos == []


def _git(*a, cwd):
    import subprocess
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, timeout=120)


def test_un_worktree_nuevo_de_un_repo_EXCLUIDO_no_es_huerfano(tmp_path):
    """El caso que costó la primera versión, reproducido con git de verdad.

    La v1 excluía las cuatro carpetas `JobHunter-*` que había en el disco. Ocho minutos después
    nació `JobHunter-herramienta` —otro worktree del mismo repo, con su tablero dentro— y la
    ronda lo denunció. Un repo con ramas de trabajo habría generado un rojo falso por rama.

    Por eso la exclusión es por REPO, y por eso esto monta un repo real con un worktree real: la
    identidad la contesta git, no el parecido de los nombres.
    """
    principal = _arbol_de_mentira(tmp_path, ["JobHunter"]) / "JobHunter"
    assert _git("init", "-q", cwd=principal).returncode == 0
    _git("add", "-A", cwd=principal)
    _git("-c", "user.email=t@local", "-c", "user.name=t", "commit", "-qm", "base", cwd=principal)
    hecho = _git("worktree", "add", "-q", "-b", "rama-nueva",
                 str(tmp_path / "JobHunter-rama-nueva"), cwd=principal)
    assert hecho.returncode == 0, hecho.stderr.decode("utf-8", "replace")
    assert (tmp_path / "JobHunter-rama-nueva" / "scripts" / "aceptacion.py").exists()

    m = _cargar(RONDA_PROYECTOS=tmp_path)
    assert m.repo_de(tmp_path / "JobHunter-rama-nueva") == "JobHunter"
    _, _, huerfanos = m.descubrir()
    assert huerfanos == [], ("un worktree de un repo excluido no es un tablero nuevo: "
                            + ", ".join(huerfanos))


def test_una_carpeta_sin_git_se_identifica_por_su_nombre(tmp_path):
    """Degradar hacia el lado seguro: sin git, la identidad es la carpeta y el desconocido sale
    denunciado en vez de colarse por una exclusión que no le tocaba."""
    raiz = _arbol_de_mentira(tmp_path, ["JobHunter-pero-sin-git"])
    m = _cargar(RONDA_PROYECTOS=raiz)
    assert m.repo_de(raiz / "JobHunter-pero-sin-git") == "JobHunter-pero-sin-git"
    _, _, huerfanos = m.descubrir()
    assert huerfanos == ["JobHunter-pero-sin-git"]


def test_una_raiz_vacia_no_descubre_nada(tmp_path):
    """Y entonces `main` aborta con != 0 en vez de escribir un informe de cero tableros."""
    m = _cargar(RONDA_PROYECTOS=tmp_path, RONDA_INFORMES=tmp_path / "sin-usar")
    vigilados, _, _ = m.descubrir()
    assert vigilados == []
    assert m.main([]) != 0
    assert not (tmp_path / "sin-usar").exists(), "no puede dejar informe de una ronda que no hubo"


def test_los_excluidos_declarados_existen_de_verdad():
    """Una exclusión a algo que ya no está no protege nada, y despista a quien la lea.

    Mismo contrato que `_ROTOS_DECLARADOS` en `test_inv_ejecutan_de_verdad`: la excepción se
    entera de que sobra.
    """
    en_disco = RONDA.tableros_en_disco(RONDA.RAIZ_PROYECTOS)
    carpetas = {RONDA._clave(d) for d in en_disco}
    repos = {RONDA.repo_de(RONDA.RAIZ_PROYECTOS / d) for d in en_disco}
    fantasmas = sorted((set(RONDA._CARPETAS_NO_VIGILADAS) - carpetas)
                       | (set(RONDA._REPOS_NO_VIGILADOS) - repos))
    assert not fantasmas, "excluidos que ya no tienen tablero en el disco: " + ", ".join(fantasmas)


def test_los_siete_declarados_estan_en_esta_maquina():
    """La lista dice lo que creemos que hay; esto lo contrasta con lo que hay."""
    vigilados, ausentes, huerfanos = RONDA.descubrir()
    assert ausentes == [], "declarados y no encontrados: " + ", ".join(ausentes)
    assert huerfanos == [], ("tableros sin declarar ni excluir: " + ", ".join(huerfanos)
                            + ". Decidir si entran en la ronda o van a _NO_VIGILADOS con su motivo")
    assert len(vigilados) == RONDA.SUELO_TABLEROS


def test_cada_tablero_declarado_tiene_interprete_utilizable():
    """Un venv borrado convierte un tablero en «caído» todas las noches; mejor cazarlo aquí."""
    vigilados, _, _ = RONDA.descubrir()
    malos = [t["nombre"] + ": " + (m or "") for t in vigilados
             for _, m in [RONDA._interprete_de(t)] if m]
    assert not malos, "; ".join(malos)


# ── una sola promesa, no dos ─────────────────────────────────────────────────────────────────

def test_la_ronda_NO_añade_una_promesa_propia_al_tablero():
    """La ronda es la IMPLEMENTACIÓN de `tableros-corren-solos`, no una promesa aparte.

    Se comprueba porque estuvo a punto de haber dos. El 2026-08-23, dos sesiones en paralelo
    atacaron el mismo objetivo: una escribió la promesa a las 18:57 y la otra el lanzador. Dos
    promesas para un mismo mecanismo en el mismo tablero se contradicen en cuanto una se toca, y
    la segunda que llega tiene que integrarse, no acumularse.
    """
    spec = importlib.util.spec_from_file_location("tablero_bajo_prueba",
                                                  str(RAIZ / "scripts" / "aceptacion.py"))
    tablero = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tablero)
    assert "tableros-corren-solos" in tablero.COMPROBADORES
    duplicadas = [n for n in tablero.COMPROBADORES if "ronda" in n]
    assert not duplicadas, ("la ronda no lleva promesa propia; su promesa es "
                            "`tableros-corren-solos`: " + ", ".join(duplicadas))
