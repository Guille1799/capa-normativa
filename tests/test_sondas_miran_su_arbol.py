"""La coartada de `sondas-miran-su-arbol`: verlo ponerse ROJO, no sólo verlo verde.

## Por qué existe

`sondas-miran-su-arbol` está declarado no mutable —su rojo no sale de que exista un fichero, sino
de **dónde miran las demás sondas al ejecutarse**— y su exención citaba `tests/test_arbol_propio.py`
como coartada. Ese fichero prueba el MÓDULO (`vigilante/arbol_propio.py`), no el comprobador del
tablero: nunca menciona `sondas_miran_su_arbol` ni lo ejecuta. O sea que el comprobador que vigila
a todos los demás era el único sin nadie que lo hubiera visto moverse.

Aquí se le monta un mundo de mentira —un repo con un worktree anidado, como el de verdad— y se le
mete una sonda que lee el árbol de al lado. Si no salta, este fichero falla.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

GUION = Path(__file__).resolve().parent.parent / "scripts" / "aceptacion.py"


def _git(*a, **k):
    import subprocess
    r = subprocess.run(["git", *a], capture_output=True, text=True, timeout=120, **k)
    if r.returncode != 0:
        raise RuntimeError("git " + " ".join(a) + " -> " + r.stderr.strip())
    return r


@pytest.fixture
def mundo(tmp_path):
    """Un repo con un worktree ANIDADO, que es la disposición real de estos repos."""
    repo = tmp_path / "repo-de-pega"
    repo.mkdir(parents=True)
    _git("init", "-q", str(repo))
    (repo / "algo.txt").write_text("x", encoding="utf-8")
    _git("-C", str(repo), "add", "-A")
    _git("-C", str(repo), "-c", "user.email=t@local", "-c", "user.name=t", "commit", "-qm", "raiz")
    hermano = repo / ".claude" / "worktrees" / "simulado"
    _git("-C", str(repo), "worktree", "add", "-q", "--detach", str(hermano))
    (hermano / "algo.txt").write_text("y", encoding="utf-8")
    return repo, hermano


def _tablero(raiz: Path, comprobadores: dict):
    m = importlib.util.module_from_spec(importlib.util.spec_from_file_location(
        "tablero_sondas", str(GUION)))
    m.__spec__.loader.exec_module(m)
    m.RAIZ = raiz
    m.COMPROBADORES = dict(comprobadores)
    return m


def test_una_sonda_que_lee_el_arbol_de_al_lado_lo_pone_ROJO(mundo):
    """El rojo que nadie había visto: la razón de ser de este comprobador."""
    repo, hermano = mundo

    def sonda_fisgona():
        (hermano / "algo.txt").read_text(encoding="utf-8")
        return True, "yo creo que miro mi arbol"

    m = _tablero(repo, {"sonda-fisgona": sonda_fisgona})
    ok, motivo = m.sondas_miran_su_arbol()
    assert ok is False, motivo
    assert "sonda-fisgona" in motivo, motivo


def test_una_sonda_que_solo_mira_lo_suyo_lo_deja_VERDE(mundo):
    repo, _hermano = mundo

    def sonda_educada():
        (repo / "algo.txt").read_text(encoding="utf-8")
        return True, "miro lo mio"

    m = _tablero(repo, {"sonda-educada": sonda_educada})
    ok, motivo = m.sondas_miran_su_arbol()
    assert ok is True, motivo


def test_el_VEREDICTO_de_la_sonda_da_igual_solo_importa_DONDE_miro(mundo):
    """Una sonda puede estar perfectamente ROJA y perfectamente mal apuntada a la vez — y ese es
    el caso que costó una noche de trabajo destruido, porque el bucle lee el rojo como «el trabajo
    no vale» y deshace trabajo correcto."""
    repo, hermano = mundo

    def sonda_roja_y_fisgona():
        (hermano / "algo.txt").read_text(encoding="utf-8")
        return False, "estoy roja por mi propio motivo"

    m = _tablero(repo, {"sonda-roja": sonda_roja_y_fisgona})
    ok, motivo = m.sondas_miran_su_arbol()
    assert ok is False, motivo


def test_una_sonda_que_REVIENTA_no_es_asunto_de_este_comprobador(mundo):
    """El límite del contrato, escrito para que no se relea como un descuido.

    Si la sonda vigilada explota antes de tocar nada, este comprobador la deja pasar en VERDE.
    Suena a aprobar en vacío —no se observó nada, y «no observé» no es «miró donde debía»— y se
    consideró cambiarlo el 2026-08-24. No se cambió, por dos razones:

      · `revisar_arbol_propio` se traga la excepción A PROPÓSITO y lo dice en su código: «que
        reviente es asunto de su propio comprobador, no de éste». Separar el «dónde miró» del
        «funcionó» es justamente lo que permite acusar a una sonda ROJA de mirar mal.
      · Una sonda que revienta NO pasa desapercibida: el tablero la pinta de rojo por su propia
        rama de excepción. La señal existe, sólo que la da otro.

    Cambiar esto tocaría un paquete ya publicado (v0.17.0) por un matiz que no deja ningún fallo
    sin señal. Si algún día se cambia, este test es el sitio donde discutirlo.
    """
    repo, _hermano = mundo

    def sonda_que_revienta():
        raise RuntimeError("me caigo antes de mirar")

    m = _tablero(repo, {"sonda-rota": sonda_que_revienta})
    ok, _motivo = m.sondas_miran_su_arbol()
    assert ok is True


def test_sin_hermanos_no_puede_haber_fuga(tmp_path):
    """Un repo sin worktrees no tiene árbol de al lado que tocar. Verde legítimo, no verde vacío."""
    repo = tmp_path / "solo"
    repo.mkdir()
    _git("init", "-q", str(repo))

    def sonda():
        return True, "ok"

    m = _tablero(repo, {"sonda": sonda})
    ok, _motivo = m.sondas_miran_su_arbol()
    assert ok is True
