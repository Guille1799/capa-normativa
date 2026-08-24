"""Todo repo PÚBLICO tiene la guarda del escaparate instalada, y esa guarda sabe saltar.

## Por qué existe

La guarda `pre-push` impide que salga a un repo público lo que no debe. Pero una guarda es un
fichero, y un fichero se borra, se renombra o simplemente nunca se instaló en el repo que creaste
ayer. **Un repo público sin guarda empuja libre, y no hay señal de ello.**

Es el mismo hueco que este arnés persigue en todas partes: el guardián existe, nadie comprueba que
siga ahí. Aquí se comprueba, y de la única forma que vale — **ejecutándola**, no mirando si el
fichero existe. Un `pre-push` que existe y revienta al arrancar protege exactamente igual que
ninguno, y desde fuera se ven idénticos.

## De dónde sale la lista de repos públicos

Se le pregunta a GitHub, repo por repo, en vez de mantenerla a mano: una lista escrita caduca el
día que haces público uno privado — que es justo el día en que más falta hace la guarda, y el día
en que nadie se acuerda de actualizar la lista.

## La trampa prohibida

Si no se puede saber qué repos son públicos —falta `gh`, no hay red—, esto es **ROJO por no haber
podido mirar**, nunca verde. Y si la lista sale vacía en una máquina que tiene repos con remoto de
GitHub, también: cero repos públicos es un resultado sospechoso, no una máquina limpia.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ_PROYECTOS = Path(os.environ.get("PROYECTOS_RAIZ") or Path.home() / "proyectos")

#: El guion compartido al que apuntan todos los shims. Se comprueba aparte: si falta, ninguna
#: guarda de ningun repo puede funcionar, y ese es un fallo de una sola causa.
GUION = RAIZ_PROYECTOS / ".claude" / "hooks" / "escaparate_pre_push.py"


class NoSePudoMirar(Exception):
    """No se pudo determinar algo. Nunca se traduce a «esta bien»."""


def _git(*a, cwd=None):
    return subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120, cwd=str(cwd) if cwd else None)


def _shell() -> str:
    """El `sh` con el que git ejecutaria la guarda de verdad.

    NO se coge del PATH a secas. Medido el 2026-08-24 en esta maquina: `git.exe` esta en el PATH
    (via `C:/Program Files/Git/cmd`) pero **`sh` NO** — Git para Windows no publica su `bin/`. Asi
    que este comprobador funcionaba cuando yo lo lanzaba desde Git Bash, que si lo trae, y
    REVENTABA con FileNotFoundError en la ronda programada, que corre desde otro entorno.

    Y reventar es lo peor que puede hacer: el tablero no leia «los repos publicos estan sin guarda»
    —que seria una alarma— sino una traza, que es ruido. Un instrumento roto y un hallazgo se ven
    igual de rojos desde fuera, y solo uno de los dos pide trabajo.

    Se DERIVA de donde este git, en vez de cablear la ruta: si git se mueve, el shell se mueve con
    el, porque son el mismo paquete. Una constante escrita apuntaria al sitio de ayer.
    """
    directo = shutil.which("sh") or shutil.which("bash")
    if directo:
        return directo
    git = shutil.which("git")
    if git:
        raiz = Path(git).resolve().parent.parent
        for cand in ("bin/sh.exe", "usr/bin/sh.exe", "bin/bash.exe"):
            if (raiz / cand).is_file():
                return str(raiz / cand)
    raise NoSePudoMirar(
        "no hay ningun `sh` con el que ejecutar las guardas, ni en el PATH ni junto a git")


def _repos_con_remoto() -> list[Path]:
    if not RAIZ_PROYECTOS.exists():
        raise NoSePudoMirar(f"no existe {RAIZ_PROYECTOS}")
    fuera = []
    for d in sorted(RAIZ_PROYECTOS.iterdir()):
        if not d.is_dir() or not (d / ".git").exists():
            continue
        if _git("remote", "get-url", "origin", cwd=d).stdout.strip():
            fuera.append(d)
    if not fuera:
        raise NoSePudoMirar("ningun repo con remoto: eso es no haber podido mirar")
    return fuera


def publicos() -> list[Path]:
    """Los repos publicos, preguntandoselo a GitHub. Repos del MISMO remoto cuentan una vez."""
    vistos, fuera = set(), []
    for d in _repos_con_remoto():
        url = _git("remote", "get-url", "origin", cwd=d).stdout.strip()
        if "github.com" not in url:
            continue
        nombre = url.rstrip("/").removesuffix(".git").split("github.com")[-1].lstrip(":/")
        r = subprocess.run(["gh", "repo", "view", nombre, "--json", "visibility"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        if r.returncode != 0 or not r.stdout.strip():
            raise NoSePudoMirar(f"gh no pudo decir si {nombre} es publico")
        try:
            vis = json.loads(r.stdout).get("visibility")
        except Exception as e:  # noqa: BLE001
            raise NoSePudoMirar(f"respuesta de gh ilegible para {nombre}: {e}") from e
        if vis == "PUBLIC" and nombre not in vistos:
            vistos.add(nombre)
            fuera.append(d)
    return fuera


def _guarda_de(repo: Path) -> Path | None:
    """El `pre-push` que git ejecutaria de verdad en ese repo, o `None` si no hay."""
    hp = _git("config", "--get", "core.hooksPath", cwd=repo).stdout.strip()
    base = Path(hp) if hp and Path(hp).is_absolute() else (repo / (hp or ".git/hooks"))
    guarda = base / "pre-push"
    return guarda if guarda.is_file() else None


def _arranca(repo: Path, guarda: Path) -> tuple[bool, str]:
    """La guarda se EJECUTA de verdad. Que el fichero exista no prueba que corra."""
    r = subprocess.run([_shell(), str(guarda.resolve())], cwd=str(repo), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    salida = (r.stdout + r.stderr)
    if r.returncode == 127 or "not found" in salida.lower():
        return False, f"no llega a arrancar (exit {r.returncode})"
    if "falta" in salida and "escaparate" in salida.lower():
        return False, "arranca pero no encuentra el guion compartido"
    return True, ""


def escaparate_con_guarda() -> tuple[bool, str]:
    if not GUION.is_file():
        return False, (f"falta {GUION.name}: ningun repo publico tiene guarda, porque todos los "
                       "shims apuntan a ese unico guion")
    try:
        pubs = publicos()
    except NoSePudoMirar as e:
        return False, f"no se pudo mirar ({e}). Eso NO es «todos tienen guarda»."
    if not pubs:
        return False, "cero repos publicos detectados: sospechoso, no limpio"

    sin, rotas = [], []
    try:
        for repo in pubs:
            guarda = _guarda_de(repo)
            if guarda is None:
                sin.append(repo.name)
                continue
            ok, motivo = _arranca(repo, guarda)
            if not ok:
                rotas.append(f"{repo.name} ({motivo})")
    except NoSePudoMirar as e:
        # Un comprobador que lanza no dice nada: el tablero enseña una traza donde deberia haber un
        # veredicto. Aqui se traduce a ROJO CON MOTIVO, que es lo unico accionable.
        return False, f"no se pudo ejecutar las guardas ({e}). Eso NO es «todas arrancan»."

    if sin or rotas:
        partes = []
        if sin:
            partes.append(f"{len(sin)} sin guarda: " + ", ".join(sin))
        if rotas:
            partes.append(f"{len(rotas)} con guarda que no arranca: " + ", ".join(rotas))
        return False, (f"{len(pubs)} repos publicos y " + " · ".join(partes))

    return True, (f"los {len(pubs)} repos publicos tienen la guarda del escaparate y arranca en "
                  f"todos")


if __name__ == "__main__":
    ok, msg = escaparate_con_guarda()
    print(("VERDE: " if ok else "ROJO: ") + msg)
    sys.exit(0 if ok else 1)
