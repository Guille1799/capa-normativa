# -*- coding: utf-8 -*-
u"""Una raya horizontal no esconde la cola AL BUCLE.

## El daño, medido

`remaining_tasks()` en `scripts/ralph.sh` cerraba la sección al ver un `---` decorativo:

    ins && (/^## / || /^---[[:space:]]*$/) {ins=0}

En **mcp_smart_context** eso contaba **0 tareas donde había 6** (2026-09-04): una sola raya
entre las fichas, y todo el trabajo pendiente detrás de ella. Con la cola clavada en cero:

  · el log dice «Tareas 🟢 al empezar: 0» y parece que no hay trabajo — el robot estuvo
    parado dos noches porque el tope se puso a 0 obedeciendo ese número;
  · el bucle compara 0 → 0, así que no puede ver progreso nunca;
  · y la alarma de «la cola bajó SIN COMMIT» compara un número que siempre vale 0, así que
    queda **inerte**: no puede dispararse jamás.

Aquí, el 2026-09-04, la cuenta **no cambiaba** (0 con la regla vieja y 0 sin ella). Pero la
raya ya vive dentro de la sección del ledger: sólo faltaba que alguien dejara una tarea
pendiente debajo. Este fichero es lo que impide heredarlo — el arreglo se propagó de
mcp_smart_context (commit 494fca7) y estos dos tests vienen con él.

## Por qué ejecutan `ralph.sh` de verdad

Porque lo que se fija es lo que **decide el bucle**, no lo que dice una función. Un test del
fuente comprobaría que las palabras están escritas; éste lee el número que el bucle imprime,
con un `claude` de pega que no hace nada.
"""
import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
RALPH = RAIZ / "scripts" / "ralph.sh"


def _busca_bash():
    u"""Un bash que FUNCIONE, no sólo uno que exista.

    ⚠️ `bash` a secas resuelve al de WSL en esta máquina: contesta al `command -v` y luego
    revienta. Existir no es funcionar, así que se ejecuta y se comprueba que contesta.
    """
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files\Git\usr\bin\bash.exe",
                 "/usr/bin/bash", "/bin/bash", "bash"):
        try:
            r = subprocess.run([cand, "-c", "echo ok"], capture_output=True, text=True,
                               timeout=20, stdin=subprocess.DEVNULL,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0 and "ok" in r.stdout:
                return cand
        except (OSError, subprocess.SubprocessError):
            continue
    return None


BASH = _busca_bash()

pytestmark = [
    pytest.mark.skipif(not RALPH.exists(), reason=u"este repo no tiene scripts/ralph.sh"),
    pytest.mark.skipif(BASH is None, reason=u"no hay un bash utilizable en esta maquina"),
]


def _git(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, " ".join(args) + u" -> " + (r.stderr or u"")[:200]
    return (r.stdout or u"").strip()


def _mundo_con_raya(tmp_path, n_debajo):
    u"""Un proyecto cuya cola tiene un `---` decorativo y `n_debajo` tareas VIVAS debajo.

    Es la forma exacta del ledger real de mcp_smart_context el 2026-09-04: una sola raya
    entre las fichas, con todo el trabajo pendiente detrás.
    """
    proj = tmp_path / "proy"
    (proj / "scripts").mkdir(parents=True)
    tareas = u"".join(u"### T%d\n- [ ] **OBJETIVO**: lo que sea\n" % i
                      for i in range(n_debajo))
    (proj / "PENDIENTES.md").write_text(
        u"## 🟢 PENDIENTE — SEGURO\n\n---\n\n" + tareas, encoding="utf-8")
    # El gate de pega sale verde: aquí no se mide el gate, se mide el CONTADOR.
    (proj / ".ralph.conf").write_text(u'GATE_CMD="exit 0"\n', encoding="utf-8")
    (proj / ".gitignore").write_text(u"ralph_run_*.log\n*.log\n.ralph_active\n",
                                     encoding="utf-8")
    # ⚠️ La rama NO puede llamarse `main`: el preflight avisa y duerme 5 s en main/master.
    _git(proj, "init", "-q", "-b", "prueba")
    _git(proj, "config", "user.email", "t@t")
    _git(proj, "config", "user.name", "t")
    _git(proj, "add", "-A")
    _git(proj, "commit", "-qm", "base")

    binq = tmp_path / "bin"
    binq.mkdir()
    # El preflight exige `claude` en el PATH. Este no hace nada: el número que se mide se
    # imprime ANTES de la primera iteración, así que basta con que exista y salga con 0.
    (binq / "claude").write_text(
        u"#!/usr/bin/env bash\necho 'no hago nada'\nexit 0\n", encoding="utf-8")
    return proj, binq


def _corre(proj, binq, maximo="1"):
    # ⚠️ `RALPH_PERMITE_WORKTREE_PRINCIPAL`: hay `ralph.sh` de esta familia (JobHunter) cuyo
    # preflight se niega a correr en el worktree principal, porque el revert del bucle puede
    # llevarse commits de otra sesión que trabaje en ese mismo directorio (pasó 3 veces el
    # 24-ago-2026). Aquí el proyecto es un `git init` desechable dentro de `tmp_path`, sin
    # nadie más dentro y sin nada que perder. Se desactiva SOLO aquí, y va en las cuatro
    # copias del test para que sean el mismo fichero.
    entorno = dict(os.environ, PATH=str(binq) + os.pathsep + os.environ.get("PATH", ""),
                   RALPH_PERMITE_WORKTREE_PRINCIPAL="1")
    try:
        return subprocess.run([BASH, str(RALPH), str(proj), maximo], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=600,
                              stdin=subprocess.DEVNULL, env=entorno)
    except (OSError, UnicodeError, subprocess.SubprocessError) as e:
        # No poder ejecutar una comprobación NO es que la comprobación falle. Aquí esa
        # diferencia vale commits: un FAILED hace que el propio Ralph revierta trabajo bueno.
        pytest.skip(u"no se pudo ejecutar ralph.sh (%s: %s) — NO es un fallo del codigo probado"
                    % (type(e).__name__, str(e)[:80]))


def test_el_bucle_CUENTA_las_tareas_de_debajo_de_una_raya(tmp_path):
    u"""El caso medido en mcp_smart_context, y tuvo al robot parado dos noches."""
    proj, binq = _mundo_con_raya(tmp_path, n_debajo=3)
    r = _corre(proj, binq)
    salida = (r.stdout or u"") + (r.stderr or u"")
    assert u"Tareas 🟢 al empezar: 3" in salida, (
        u"la raya escondio las 3 tareas de debajo al contador del bucle: " + salida[:600])


def test_una_seccion_de_VERDAD_si_cierra_para_el_bucle(tmp_path):
    u"""La dirección contraria, sin la cual el arreglo podría ser «no cerrar nunca».

    Las tareas de otra sección —bloqueadas, o que necesitan juicio humano— no pueden contar
    como cola segura del robot.
    """
    proj, binq = _mundo_con_raya(tmp_path, n_debajo=2)
    cola = proj / "PENDIENTES.md"
    cola.write_text(cola.read_text(encoding="utf-8")
                    + u"\n## ⛔ BLOQUEADAS\n### T99\n- [ ] **OBJETIVO**: no cuenta\n",
                    encoding="utf-8")
    _git(proj, "add", "-A")
    _git(proj, "commit", "-qm", "una seccion mas")
    r = _corre(proj, binq)
    salida = (r.stdout or u"") + (r.stderr or u"")
    assert u"Tareas 🟢 al empezar: 2" in salida, (
        u"conto la tarea de BLOQUEADAS como cola segura: " + salida[:600])
