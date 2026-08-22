"""Cada test es una forma REAL de acabar mirando el árbol equivocado.

Los tres primeros son los que motivan que esto observe en vez de leer el fuente: en los tres,
el código del comprobador no contiene ninguna ruta absoluta, así que un lint le daría el visto
bueno. Y los tres han ocurrido de verdad en estos repos.

Los negativos también importan: una guarda que acusa a sondas sanas se desactiva en una semana.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from capa_normativa.vigilante.arbol_propio import (
    CODIGO,
    arboles_hermanos,
    revisar_arbol_propio,
    vigilando,
)


@pytest.fixture
def dos_arboles(tmp_path):
    """Un árbol propio y un hermano, cada uno con el MISMO fichero dentro.

    Que el fichero se llame igual en los dos no es decorado: es exactamente la confusión que
    se persigue —«esto, pero en la copia equivocada»— y sin el homónimo el test no reproduce
    el fallo, sólo se le parece.
    """
    propio, hermano = tmp_path / "mio", tmp_path / "hermano"
    for d in (propio, hermano):
        (d / "scripts").mkdir(parents=True)
        (d / "scripts" / "aceptacion.py").write_text("# tablero", encoding="utf-8")
    return propio, hermano


def revisar(fn, propio, hermano, nombre="sonda"):
    return revisar_arbol_propio({nombre: fn}, propio, [hermano])


# ------------------------------------------------- las tres que un lint NO vería

def test_la_ruta_viene_de_una_variable_de_entorno(dos_arboles, monkeypatch):
    """Ya pasó: `GIT_DIR` secuestró a los detectores, que escanearon otro repo, no encontraron
    nada y declararon todo limpio (commit d216e5e). En el fuente no hay ninguna ruta."""
    propio, hermano = dos_arboles
    monkeypatch.setenv("RAIZ_DE_TURNO", str(hermano))

    def sonda():
        return Path(os.environ["RAIZ_DE_TURNO"], "scripts", "aceptacion.py").read_text()

    h = revisar(sonda, propio, hermano)
    assert len(h) == 1 and h[0].codigo == CODIGO
    assert "HERMANO" in h[0].mensaje


def test_el_arnes_FIJA_el_directorio_y_la_deriva_deja_de_ocurrir(dos_arboles, monkeypatch):
    """La deriva de CWD no se detecta: se IMPIDE, que es mejor.

    `Path("scripts/aceptacion.py")` no lleva ninguna ruta absoluta y resuelve a donde se haya
    lanzado el proceso. Aquí se lanza la revisión desde el HERMANO a propósito, y aun así la
    sonda queda limpia — porque cada comprobador se ejecuta desde su propio árbol.

    ⚠️ Este test existe porque ese `chdir` ya desapareció una vez sin que nadie se enterara: un
    script de parcheo hizo `replace` sin comprobar que encajara, escribió «ok», y la única señal
    fue que doce sondas sanas volvieron a salir acusadas al pasar por los tableros de verdad.
    """
    propio, hermano = dos_arboles
    monkeypatch.chdir(hermano)

    def sonda():
        return Path("scripts/aceptacion.py").read_text(encoding="utf-8")

    assert revisar(sonda, propio, hermano) == []


def test_el_subproceso_se_lanza_en_el_arbol_de_al_lado(dos_arboles):
    """Ni ruta escrita ni CWD del proceso: el `cwd=` del subproceso. Silenciosa del todo."""
    propio, hermano = dos_arboles

    def sonda():
        return subprocess.run([sys.executable, "-c", "print(1)"], cwd=str(hermano),
                              capture_output=True)

    assert len(revisar(sonda, propio, hermano)) == 1


# ------------------------------------------------------------- el caso clásico

def test_la_ruta_escrita_a_mano(dos_arboles):
    propio, hermano = dos_arboles
    ruta = str(hermano / "scripts" / "aceptacion.py")

    def sonda():
        return open(ruta, encoding="utf-8").read()

    h = revisar(sonda, propio, hermano)
    assert len(h) == 1
    assert "derivar la ruta" in h[0].arreglo


def test_se_ve_a_traves_de_pathlib(dos_arboles):
    """`Path.open()` entra por `io.open`, no por `builtins.open`. Parchear sólo uno de los dos
    deja pasar casi todo el código moderno."""
    propio, hermano = dos_arboles

    def sonda():
        with (hermano / "scripts" / "aceptacion.py").open(encoding="utf-8") as fh:
            return fh.read()

    assert len(revisar(sonda, propio, hermano)) == 1


def test_se_ve_un_simple_exists(dos_arboles):
    """Muchas sondas sólo preguntan si un fichero existe. Eso ya es juzgar el árbol."""
    propio, hermano = dos_arboles

    def sonda():
        return (hermano / "scripts" / "aceptacion.py").exists()

    assert len(revisar(sonda, propio, hermano)) == 1


# ------------------------------------------------------------------ negativos

def test_la_sonda_que_mira_SU_arbol_no_se_acusa(dos_arboles):
    propio, hermano = dos_arboles

    def sonda():
        return (propio / "scripts" / "aceptacion.py").read_text(encoding="utf-8")

    assert revisar(sonda, propio, hermano) == []


def test_derivar_de_file_es_la_forma_correcta_y_pasa(dos_arboles, monkeypatch):
    """El arreglo que se recomienda tiene que pasar la guarda, o la recomendación es falsa."""
    propio, hermano = dos_arboles
    guion = propio / "scripts" / "sonda.py"
    guion.write_text("# sonda", encoding="utf-8")
    monkeypatch.chdir(hermano)          # aunque el CWD sea el hermano, __file__ manda

    def sonda():
        return (Path(guion).resolve().parent / "aceptacion.py").read_text(encoding="utf-8")

    assert revisar(sonda, propio, hermano) == []


def test_tocar_OTRO_repo_no_se_acusa(dos_arboles, tmp_path):
    """Sólo se persigue al hermano. Auditar un repo distinto puede ser el trabajo de la sonda,
    y acusarlo mandaría a revisión manual comprobadores legítimos."""
    propio, hermano = dos_arboles
    ajeno = tmp_path / "otro_repo"
    ajeno.mkdir()
    (ajeno / "cosa.txt").write_text("x", encoding="utf-8")

    def sonda():
        return (ajeno / "cosa.txt").read_text(encoding="utf-8")

    assert revisar(sonda, propio, hermano) == []


# --------------------------------------------------------- higiene del vigilante

def test_los_parches_se_retiran_aunque_la_sonda_reviente(dos_arboles):
    """Un vigilante que se deja los parches puestos contamina todo lo que corra después, y el
    daño aparece lejos de aquí. Por eso se restaura en `finally`."""
    propio, hermano = dos_arboles
    import builtins
    import io
    antes = (builtins.open, io.open, os.stat, subprocess.run)

    def sonda():
        raise RuntimeError("revienta")

    revisar(sonda, propio, hermano)
    assert (builtins.open, io.open, os.stat, subprocess.run) == antes


def test_una_sonda_que_revienta_no_tumba_la_revision(dos_arboles):
    """Que un comprobador falle es asunto suyo. Esta guarda mira DÓNDE miró, no si aprobó."""
    propio, hermano = dos_arboles

    def revienta():
        raise ValueError("yo fallo")

    def fuga():
        return (hermano / "scripts" / "aceptacion.py").read_text(encoding="utf-8")

    h = revisar_arbol_propio({"a_revienta": revienta, "b_fuga": fuga}, propio, [hermano])
    assert [x.fichero for x in h] == ["b_fuga"]


def test_el_veredicto_de_la_sonda_es_irrelevante(dos_arboles):
    """Una sonda puede estar en ROJO legítimo y mal apuntada a la vez — es el caso que costó
    una noche de trabajo destruido."""
    propio, hermano = dos_arboles

    def roja_y_mal_apuntada():
        (hermano / "scripts" / "aceptacion.py").read_text(encoding="utf-8")
        return False, "rojo"

    assert len(revisar(roja_y_mal_apuntada, propio, hermano)) == 1


def test_sin_hermanos_no_hay_nada_que_confundir(tmp_path):
    """Un repo de un solo árbol no puede tener este fallo, y la guarda no debe inventárselo."""
    solo = tmp_path / "solo"
    solo.mkdir()

    def sonda():
        return (tmp_path / "cualquiera.txt").exists()

    assert revisar_arbol_propio({"s": sonda}, solo, []) == []


def test_varias_fugas_de_la_misma_sonda_se_cuentan_una_vez(dos_arboles):
    propio, hermano = dos_arboles

    def sonda():
        for _ in range(4):
            (hermano / "scripts" / "aceptacion.py").read_text(encoding="utf-8")

    h = revisar(sonda, propio, hermano)
    assert len(h) == 1 and "mas)" not in h[0].mensaje


def test_los_hermanos_se_descubren_con_git(tmp_path):
    """Se pregunta a git, no se deduce del nombre: `pw-ralph` y `ponerse_wenorro` no se parecen
    y son el mismo repo."""
    repo, wt = tmp_path / "repo", tmp_path / "wt"
    repo.mkdir()

    def git(*a, cwd=repo):
        return subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, timeout=60)

    git("init", "-q", "-b", "main")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x")
    if git("worktree", "add", "-q", str(wt), "-b", "rama").returncode != 0:
        pytest.skip("git worktree no disponible")
    hermanos = [str(h).replace(chr(92), "/").lower() for h in arboles_hermanos(wt)]
    assert any(str(repo).replace(chr(92), "/").lower() in h for h in hermanos), hermanos
    assert not any(str(wt).replace(chr(92), "/").lower() == h for h in hermanos)


def test_vigilando_es_reentrante_y_no_se_pisa(dos_arboles):
    """Se usa una vez por comprobador, en serie. Si anidarlo rompiera la restauración, el
    segundo pase mediría con las puertas ya parcheadas."""
    propio, hermano = dos_arboles
    with vigilando(propio, [hermano]) as fuera:
        with vigilando(propio, [hermano]) as dentro:
            (hermano / "scripts" / "aceptacion.py").read_text(encoding="utf-8")
        # UNA lectura deja VARIOS registros a propósito: pasa por `Path.read_text` y por el
        # `io.open` de debajo, y las dos son puertas vigiladas. Registrar de más es lo correcto
        # —perder un acceso sería el fallo caro—; quien deduplica es `revisar_arbol_propio`,
        # que es donde importa que un comprobador salga acusado una vez y no cuatro.
        assert len(dentro) >= 1
        assert all("hermano" in f.ruta for f in dentro)
    # y tras cerrar el interior, el exterior sigue vigilando: la restauración no lo desarmó
    (hermano / "scripts" / "aceptacion.py").exists()
    assert len(fuera) >= 1


def test_la_puerta_mas_usada_es_os_path_exists(dos_arboles):
    """Regresión de la lección más cara de este módulo.

    La primera versión parcheaba `os.stat` y daba por hecho que todo pasaba por ahí. En Windows
    NO: desde CPython 3.12 `os.path.exists` es una función en C (`nt._path_exists`) que nunca
    llama a `os.stat`, y `Path.exists` delega en ella. O sea que la puerta más transitada de
    todas era invisible. Si alguien simplifica la tabla de puertas, esto se pone rojo.

    ⚠️ Una puerta por test, a propósito. La primera versión de este test usaba `exists` **y**
    `isfile` en la misma sonda, así que al quitar una de las dos de la tabla seguía pasando: no
    aislaba nada. Lo cazó la verificación por mutación, no la lectura.
    """
    propio, hermano = dos_arboles
    ruta = str(hermano / "scripts" / "aceptacion.py")

    def sonda():
        return os.path.exists(ruta)

    assert len(revisar(sonda, propio, hermano)) == 1


def test_tambien_por_os_path_isfile(dos_arboles):
    propio, hermano = dos_arboles
    ruta = str(hermano / "scripts" / "aceptacion.py")

    def sonda():
        return os.path.isfile(ruta)

    assert len(revisar(sonda, propio, hermano)) == 1


def test_un_worktree_ANIDADO_dentro_del_principal(tmp_path):
    """Caso real de `capa-normativa`: sus worktrees viven en `.claude/worktrees/<nombre>/`,
    o sea DENTRO del árbol principal. Con comparación por prefijo, la ruta del padre encaja con
    todo lo del hijo y **cada fichero propio sale acusado**. Pasó en la primera pasada real, y
    el acusado era un comprobador sano.
    """
    principal = tmp_path / "repo"
    anidado = principal / ".claude" / "worktrees" / "wt"
    (anidado / "docs").mkdir(parents=True)
    propio = anidado / "docs" / "mio.md"
    propio.write_text("x", encoding="utf-8")

    def sonda():
        return propio.read_text(encoding="utf-8")

    # el hermano declarado es el PADRE, que contiene al hijo
    assert revisar_arbol_propio({"s": sonda}, anidado, [principal]) == []


def test_el_anidado_SI_se_acusa_si_toca_al_padre(tmp_path):
    """El contraejemplo del anterior: no vale con dejar de acusar siempre. Tocar un fichero que
    de verdad es del padre —y no del hijo— sigue siendo la fuga que se persigue."""
    principal = tmp_path / "repo"
    anidado = principal / ".claude" / "worktrees" / "wt"
    anidado.mkdir(parents=True)
    (principal / "docs").mkdir()
    del_padre = principal / "docs" / "suyo.md"
    del_padre.write_text("x", encoding="utf-8")

    def sonda():
        return del_padre.read_text(encoding="utf-8")

    assert len(revisar_arbol_propio({"s": sonda}, anidado, [principal])) == 1


def test_un_auditor_cruzado_se_declara_y_no_se_acusa(dos_arboles):
    """Hay sondas que tocan otros árboles porque ése ES su trabajo — «todos los repos tienen su
    pre-commit», por ejemplo. Sin una puerta para declararlas, el guarda gritaría en falso para
    siempre en ese tablero, que es la forma segura de que alguien lo acabe apagando."""
    propio, hermano = dos_arboles

    def auditor():
        return (hermano / "scripts" / "aceptacion.py").exists()

    sin_declarar = revisar_arbol_propio({"auditor": auditor}, propio, [hermano])
    declarado = revisar_arbol_propio({"auditor": auditor}, propio, [hermano],
                                     permitidos={"auditor": "audita todos los repos a proposito"})
    assert len(sin_declarar) == 1 and declarado == []


def test_declarar_a_UNO_no_tapa_a_los_demas(dos_arboles):
    """La excepción es nominal, no un interruptor general."""
    propio, hermano = dos_arboles

    def fuga():
        return (hermano / "scripts" / "aceptacion.py").exists()

    h = revisar_arbol_propio({"declarado": fuga, "otro": fuga}, propio, [hermano],
                             permitidos={"declarado": "motivo"})
    assert [x.fichero for x in h] == ["otro"]


def test_una_relativa_que_SE_ESCAPA_con_dos_puntos(dos_arboles):
    """`../hermano/scripts/aceptacion.py` no tiene nada de absoluto y sale del árbol igual.

    Lo cazó la verificación por mutación: había una versión que sólo miraba rutas absolutas en
    los comandos, y ésta se le colaba entera. Es el falso NEGATIVO más barato de escribir sin
    querer, porque la ruta parece local.
    """
    propio, hermano = dos_arboles
    relativa = "../" + hermano.name + "/scripts/aceptacion.py"

    def sonda():
        return subprocess.run([sys.executable, relativa], capture_output=True)

    assert len(revisar(sonda, propio, hermano)) == 1


def test_un_id_de_pytest_no_es_una_ruta_que_se_escape(dos_arboles):
    """El contraejemplo: `tests/x.py::test_y` tiene forma de ruta y NO debe acusar, porque cada
    comprobador se ejecuta desde su propio árbol y eso resuelve dentro de él."""
    propio, hermano = dos_arboles

    def sonda():
        return subprocess.run([sys.executable, "-m", "pytest", "tests/test_x.py::test_y"],
                              capture_output=True)

    assert revisar(sonda, propio, hermano) == []
