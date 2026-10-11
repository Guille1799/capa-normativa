"""La guarda del escaparate, y la guarda de que la guarda sigue puesta.

Los tests que importan son los de **no aprobar por no haber podido mirar**. Es donde estos dos
comprobadores salen más barato de engañar: si `gh` no contesta, lo cómodo es seguir adelante, y
«seguir adelante» se lee igual que «está todo bien».
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
GUARDA = RAIZ.parent / ".claude" / "hooks" / "escaparate_pre_push.py"
CENTINELA = RAIZ / "scripts" / "aceptaciones" / "escaparate_con_guarda.py"


def _cargar(ruta: Path, nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*a, cwd=None):
    r = subprocess.run(["git", *a], capture_output=True, text=True, timeout=120,
                       cwd=str(cwd) if cwd else None)
    if r.returncode != 0:
        raise RuntimeError("git " + " ".join(a) + " -> " + r.stderr.strip())
    return r


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    _git("init", "-q", str(d))
    (d / "codigo.py").write_text("print('hola')\n", encoding="utf-8")
    _git("-C", str(d), "add", "-A")
    _git("-C", str(d), "-c", "user.email=t@l", "-c", "user.name=t", "commit", "-qm", "raiz")
    return d


# ---------- la guarda ---------------------------------------------------------


@pytest.mark.skipif(not GUARDA.is_file(), reason="la guarda compartida no esta instalada")
def test_un_cuaderno_interno_versionado_se_denuncia(repo):
    m = _cargar(GUARDA, "guarda_bajo_prueba")
    (repo / "PENDIENTES.md").write_text("- [ ] cosas\n", encoding="utf-8")
    _git("-C", str(repo), "add", "-A")
    _git("-C", str(repo), "-c", "user.email=t@l", "-c", "user.name=t", "commit", "-qm", "cuaderno")
    malos = m.hallazgos(repo)
    assert any("PENDIENTES.md" in x for x in malos), malos


@pytest.mark.skipif(not GUARDA.is_file(), reason="la guarda compartida no esta instalada")
def test_un_CORE_en_cualquier_carpeta_se_denuncia(repo):
    """Se compara por NOMBRE, no por ruta: da igual dónde acabe."""
    m = _cargar(GUARDA, "guarda_bajo_prueba")
    (repo / "docs").mkdir()
    (repo / "docs" / "EU_REFERENCIA_CORE.md").write_text("estado\n", encoding="utf-8")
    _git("-C", str(repo), "add", "-A")
    _git("-C", str(repo), "-c", "user.email=t@l", "-c", "user.name=t", "commit", "-qm", "core")
    assert any("_CORE.md" in x for x in m.hallazgos(repo))


@pytest.mark.skipif(not GUARDA.is_file(), reason="la guarda compartida no esta instalada")
def test_un_repo_limpio_no_da_hallazgos(repo):
    m = _cargar(GUARDA, "guarda_bajo_prueba")
    assert m.hallazgos(repo) == []


@pytest.mark.skipif(not GUARDA.is_file(), reason="la guarda compartida no esta instalada")
def test_un_remoto_que_no_es_github_no_es_publico(repo, monkeypatch):
    m = _cargar(GUARDA, "guarda_bajo_prueba")
    _git("-C", str(repo), "remote", "add", "origin", "https://gitlab.com/x/y.git")
    assert m.es_publico(repo) is False


@pytest.mark.skipif(not GUARDA.is_file(), reason="la guarda compartida no esta instalada")
def test_si_no_se_puede_preguntar_devuelve_None_y_no_False(repo, monkeypatch):
    """`None` y `False` son cosas distintas: «no pude preguntar» no es «es privado». Quien llama
    decide, pero el dato tiene que llegarle sin mentir."""
    m = _cargar(GUARDA, "guarda_bajo_prueba")
    _git("-C", str(repo), "remote", "add", "origin", "https://github.com/x/y.git")

    class Falla:
        returncode, stdout, stderr = 1, "", "gh: not found"

    # Solo se rompe `gh`. La primera version parcheaba `subprocess.run` ENTERO y tumbaba tambien
    # el `git remote get-url` de dos lineas antes: la funcion se salia por «no hay remoto» y
    # devolvia False. El test daba por bueno un camino que nunca se ejecuto.
    real = m.subprocess.run

    def solo_gh_falla(cmd, *a, **k):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "gh":
            return Falla()
        return real(cmd, *a, **k)

    monkeypatch.setattr(m.subprocess, "run", solo_gh_falla)
    assert m.es_publico(repo) is None


_TOKENS_QUE_GH_PREFIERE = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


@pytest.mark.skipif(not GUARDA.is_file(), reason="la guarda compartida no esta instalada")
def test_un_TOKEN_HEREDADO_no_le_llega_a_gh_y_el_resto_del_entorno_si(repo, monkeypatch):
    """ESCAPARATE-GH-CON-TOKEN-HEREDADO. Un `GITHUB_TOKEN` viejo o revocado en el entorno de quien empuja
    —lo mete cualquier `load_dotenv` del `.env` de mcp— le gana a la sesion guardada de `gh`: `gh` falla o
    no ve el repo, `es_publico` da None y el push de un repo PUBLICO sale sin revisar. Paso de verdad en el
    tablero el 2026-10-02 (65076f8). La pregunta tiene que hacerse con la sesion guardada, siempre.

    Y el RESTO del entorno tiene que llegar: sin el, `gh` no encuentra ni su configuracion, falla, y es el
    mismo agujero por el otro lado. Sin red: `gh` es un espia que contesta PUBLIC."""
    m = _cargar(GUARDA, "guarda_bajo_prueba")
    _git("-C", str(repo), "remote", "add", "origin", "https://github.com/x/y.git")
    for t in _TOKENS_QUE_GH_PREFIERE:
        monkeypatch.setenv(t, "token-de-pega-revocado")
    monkeypatch.setenv("VARIABLE_QUE_GH_PUEDE_NECESITAR", "se-queda")

    class Publico:
        returncode, stdout, stderr = 0, '{"visibility": "PUBLIC"}', ""

    visto = {}
    real = m.subprocess.run

    def espia(cmd, *a, **k):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "gh":
            visto["env"] = k.get("env")
            return Publico()
        return real(cmd, *a, **k)

    monkeypatch.setattr(m.subprocess, "run", espia)
    assert m.es_publico(repo) is True
    assert visto["env"] is not None, "gh hereda el entorno ENTERO: el token viejo le llega"
    assert not set(_TOKENS_QUE_GH_PREFIERE) & {k.upper() for k in visto["env"]}, sorted(visto["env"])
    assert visto["env"].get("VARIABLE_QUE_GH_PUEDE_NECESITAR") == "se-queda", "se quito el entorno entero"


# ---------- la guarda de la guarda -------------------------------------------


def test_un_repo_publico_SIN_guarda_es_ROJO(monkeypatch, tmp_path):
    m = _cargar(CENTINELA, "centinela_bajo_prueba")
    desnudo = tmp_path / "desnudo"
    desnudo.mkdir()
    monkeypatch.setattr(m, "publicos", lambda: [desnudo])
    monkeypatch.setattr(m, "GUION", CENTINELA)      # que exista algo, da igual cual
    ok, motivo = m.escaparate_con_guarda()
    assert ok is False
    assert "sin guarda" in motivo and "desnudo" in motivo


def test_si_gh_no_contesta_es_ROJO_y_no_todos_tienen_guarda(monkeypatch):
    m = _cargar(CENTINELA, "centinela_bajo_prueba")
    monkeypatch.setattr(m, "GUION", CENTINELA)

    def revienta():
        raise m.NoSePudoMirar("gh no pudo decir si x es publico")

    monkeypatch.setattr(m, "publicos", revienta)
    ok, motivo = m.escaparate_con_guarda()
    assert ok is False
    assert "no se pudo mirar" in motivo


def test_cero_repos_publicos_es_SOSPECHOSO_no_limpio(monkeypatch):
    m = _cargar(CENTINELA, "centinela_bajo_prueba")
    monkeypatch.setattr(m, "GUION", CENTINELA)
    monkeypatch.setattr(m, "publicos", lambda: [])
    ok, motivo = m.escaparate_con_guarda()
    assert ok is False
    assert "sospechoso" in motivo


def test_sin_el_guion_compartido_es_ROJO(monkeypatch, tmp_path):
    """Un fallo de una sola causa: si falta el guion, los seis shims apuntan a nada."""
    m = _cargar(CENTINELA, "centinela_bajo_prueba")
    monkeypatch.setattr(m, "GUION", tmp_path / "no_existe.py")
    ok, motivo = m.escaparate_con_guarda()
    assert ok is False
    assert "falta" in motivo


def test_contra_la_maquina_real_la_pregunta_se_puede_hacer():
    """Sin fixtures: no exige verde, exige que la pregunta se pueda formular."""
    m = _cargar(CENTINELA, "centinela_bajo_prueba")
    ok, motivo = m.escaparate_con_guarda()
    assert "no se pudo mirar" not in motivo, motivo
