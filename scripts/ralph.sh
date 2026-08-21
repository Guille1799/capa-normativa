#!/usr/bin/env bash
# ralph.sh — loop autónomo "Ralph" GENÉRICO y ENDURECIDO (sirve para los 5 proyectos).
#
# Uso (desde una terminal NORMAL, NO anidado en una conversación de Claude):
#   bash ralph.sh <project_dir> [max_iter]
#   bash scripts/ralph.sh                 # sin arg -> proyecto = carpeta padre del script
#
# Config por proyecto: <project_dir>/.ralph.conf define LEDGER, LOG, PY, GATE_CMD, SECTION,
#   y opcionalmente ITER_TIMEOUT (s, default 1800) y MAX_STUCK (default 3).
#   AVISO: .ralph.conf se ejecuta con `source` (puede correr código). Úsalo solo en repos de confianza.
#
# POR QUÉ FUNCIONA: (1) contexto FRESCO por iteración (no se agota); (2) FILESYSTEM=memoria
#   (ledger + git + PROGRESS); (3) CONTRATOS verificados por la RUNTIME, no por el modelo:
#   el loop re-corre el gate y REVIERTE si el commit no pasa (no se fía del "hecho" del agente).
set -u

PROJ="${1:-}"
if [ -z "$PROJ" ]; then PROJ="$(cd "$(dirname "$0")/.." && pwd)"; fi
MAX="${2:-20}"
cd "$PROJ" || { echo "ERROR: no existe $PROJ"; exit 1; }

# ---- Defaults (sobreescribibles por .ralph.conf) ----
LEDGER="PENDIENTES.md"; [ -f "auditoria/PENDIENTES.md" ] && LEDGER="auditoria/PENDIENTES.md"
LOG="PROGRESS.md"; [ -f "auditoria/PROGRESS.md" ] && LOG="auditoria/PROGRESS.md"
PY="venv/Scripts/python.exe"; [ -x "$PY" ] || PY="python"
GATE_CMD="$PY -m pytest tests/ -q"
SECTION="🟢 PENDIENTE — SEGURO"
ITER_TIMEOUT=1800   # s por iteración (R2)
MAX_STUCK=3         # iters sin progreso seguidas antes de parar (R3)
[ -f ".ralph.conf" ] && source ".ralph.conf"
# Config LOCAL de esta máquina/worktree. Va DESPUÉS para poder pisar a .ralph.conf, y NO está
# versionada a propósito. Nace del 2026-08-21: la config del worktree de Ralph se escribió en
# .ralph.conf, que SÍ está versionado — así que el primer `git reset --hard` del propio loop se la
# llevó, y Ralph habría vuelto EN SILENCIO a la config del árbol de G (un PY que allí no existe).
# Un fichero que git ignora es intocable para el reset: ésa es justo la propiedad que hace falta.
[ -f ".ralph.local.conf" ] && source ".ralph.local.conf"

# ---- Preflight (R4/R7) ----
command -v claude >/dev/null 2>&1 || { echo "ERROR: 'claude' no está en PATH"; exit 1; }
command -v git    >/dev/null 2>&1 || { echo "ERROR: 'git' no está en PATH"; exit 1; }
[ -f "$LEDGER" ] || { echo "ERROR: no hay ledger '$LEDGER' en $PROJ"; exit 1; }
# El "subprocess env scrub" (hardening de Claude Code) anula --dangerously-skip-permissions
# en cada `claude -p` → el agente no podría escribir/commitear. Lo desactivamos para ESTE loop
# (vía documentada por el propio aviso) para que el bypass aplique de verdad.
export CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=0
if [ -n "${CLAUDE_CODE_SESSION_ID:-}" ]; then
  echo "AVISO: entorno Claude Code detectado; bypass forzado (scrub=0)."
  echo "       NO lances esto pegándolo dentro de un tool-call de un chat ACTIVO (conflictos)."
fi
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  echo "AVISO: estás en '$BRANCH' — Ralph commiteará aquí. Ctrl-C en 5s para crear una rama..."
  sleep 5
fi

# Cuenta tareas '- [ ]' bajo el header que contiene SECTION (multi-señal de completion, R6)
remaining_tasks() {
  awk -v sec="$SECTION" '
    /^#/ && index($0, sec) {ins=1; next}
    ins && (/^## / || /^---[[:space:]]*$/) {ins=0}
    ins && /^- \[ \]/ {c++}
    END {print c+0}
  ' "$LEDGER"
}

# El loop es la autoridad del gate (R1) → desactiva el Stop hook del proyecto (stop_gate_mcp)
# y, donde se respete, el PostToolUse (ollama_chain), evitando oracle x2-3 y thrashing por iter.
export RALPH_ACTIVE=1
# Señal-fichero para el watcher (F1): la env RALPH_ACTIVE no llega a un daemon aparte, pero un
# fichero sí. El watcher (UP2) sondea .ralph_active y pausa el re-index mientras exista. Append PID
# soporta varios Ralph en paralelo; se limpia en el trap EXIT.
echo "$$" >> .ralph_active

RUNLOG="ralph_run_$(date '+%Y%m%d_%H%M%S').log"

PROMPT="Trabajas en el proyecto $(basename "$PROJ") (lee CLAUDE.md para reglas/convenciones).

1) CONTEXTO: lee $LOG (qué se hizo/falló + sección 'Patrones'), RALPH_SETUP.md si dudas del método,
   y los ficheros que cite la tarea (ARCHIVOS). Carga contexto leyendo ficheros directos; no adivines.
2) ELIGE UNA sola tarea: la PRIMERA sin marcar ([ ]) de la sección \"$SECTION\". Nunca varias.
3) IMPLEMÉNTALA con el MÍNIMO cambio necesario, reusando el código existente, según su
   OBJETIVO/ARCHIVOS/ACEPTACIÓN. NO toques ni rompas código/tests de OTRAS tareas. Respeta los
   'Patrones' de $LOG (p.ej. qué ficheros NO editar — el código real vive en src/, la raíz es stub).
4) VERIFICA DOS cosas antes de commitear: (a) el gate global sale sin fallos ($GATE_CMD), y
   (b) la cláusula ACEPTACIÓN ESPECÍFICA de la tarea. Si cualquiera falla, NO commitees.
   ⚠️ Si la ACEPTACIÓN nombra un comprobador (\`aceptacion.py <nombre>\`), CÓRRELO de verdad: el
   loop lo va a ejecutar despues del commit y REVIERTE si sigue en rojo. El gate global esta
   verde antes y despues de tu tarea, asi que no demuestra que la hayas hecho; el comprobador si.
5) SI DUDAS O TE BLOQUEAS (falta grounding, aceptación poco clara, decisión de diseño/datos que
   no es tuya, o el mismo fallo se repite): NO improvises ni marques [x]. Mueve la tarea a la
   sección '⛔ BLOQUEADAS' de $LEDGER con 'confianza: baja', la PREGUNTA concreta y el plan que
   propondrías; COMMITEA ese movimiento; anótalo en $LOG; e imprime la palabra STUCK.
6) SI EL GATE PASA: haz UN ÚNICO commit con 'git add' SELECTIVO — solo los ficheros que TÚ tocaste
   + $LEDGER + $LOG. NUNCA 'git add -A' ni 'git add .' (barrería ficheros regenerados por el watcher
   como SUMMARY/CORE → contaminaría el commit; pasó en un run real). El commit incluye (a) tu cambio de
   código, (b) la tarea [x] en $LEDGER y (c) una línea arriba en $LOG. UNA tarea = UN commit. Tras
   commitear, **TERMINA tu respuesta de inmediato**: NO cojas otra tarea (la siguiente iteración la hará
   con contexto fresco). Hacer varias tareas en una invocación está PROHIBIDO.
7) STOP: si NO queda NINGUNA [ ] en \"$SECTION\", imprime EXACTAMENTE COMPLETE y termina."

echo "Ralph: proyecto=$PROJ | rama=$BRANCH | ledger=$LEDGER | max=$MAX | runlog=$RUNLOG" | tee "$RUNLOG"
echo "Gate (lo re-verifica el loop): $GATE_CMD" | tee -a "$RUNLOG"
echo "(el ⚠ 'Permission mode forced to default' es cosmético — allowedTools gestiona los permisos)" | tee -a "$RUNLOG"
echo "Tareas 🟢 al empezar: $(remaining_tasks)" | tee -a "$RUNLOG"

# Resumen automático al terminar (cualquier salida): qué commiteó Ralph (revisión matinal).
RUN_START_HEAD="$(git rev-parse HEAD 2>/dev/null)"
_summary() {
  # Limpia la señal de ESTE run (su PID); si no queda ningún Ralph, borra el fichero.
  if [ -f .ralph_active ]; then
    grep -vxF "$$" .ralph_active > .ralph_active.tmp 2>/dev/null || true
    mv .ralph_active.tmp .ralph_active 2>/dev/null || true
    [ -s .ralph_active ] || rm -f .ralph_active
  fi
  echo "" | tee -a "$RUNLOG"
  echo "=== Resumen del run — commits hechos por Ralph ===" | tee -a "$RUNLOG"
  git log --oneline "${RUN_START_HEAD}..HEAD" 2>/dev/null | tee -a "$RUNLOG"
  echo "Tareas 🟢 restantes: $(remaining_tasks) · runlog: $RUNLOG" | tee -a "$RUNLOG"
}
trap _summary EXIT

stuck=0
for i in $(seq 1 "$MAX"); do
  echo "" | tee -a "$RUNLOG"
  echo "=== Ralph iter $i/$MAX — $(date '+%Y-%m-%d %H:%M:%S') — stuck=$stuck ===" | tee -a "$RUNLOG"
  REM_BEFORE="$(remaining_tasks)"
  HEAD_BEFORE="$(git rev-parse HEAD 2>/dev/null)"

  # Stream EN VIVO a consola + runlog, capturando la salida para los checks.
  ITER_TMP="$(mktemp)"
  # Filtra el aviso cosmético "Permission mode forced to default" (allowedTools gestiona los permisos;
  # no es un error). --line-buffered para no romper el streaming en vivo. PIPESTATUS[0] = claude.
  timeout "$ITER_TIMEOUT" claude -p "$PROMPT" --dangerously-skip-permissions \
      --allowedTools "Read Write Edit Bash Grep Glob" 2>&1 \
      | grep --line-buffered -v "Permission mode forced to default" \
      | tee -a "$RUNLOG" | tee "$ITER_TMP"
  rc=${PIPESTATUS[0]}
  OUT="$(cat "$ITER_TMP")"; rm -f "$ITER_TMP"
  [ $rc -eq 124 ] && echo "  ⏱ timeout (>${ITER_TIMEOUT}s) en la iteración $i" | tee -a "$RUNLOG"

  HEAD_AFTER="$(git rev-parse HEAD 2>/dev/null)"

  # ---- R1: re-verificar el gate tras un commit; revertir si falla. Gate a fichero aparte
  #         (no inundar el runlog con el INFO del Oracle); solo el resumen va al runlog. ----
  if [ "$HEAD_AFTER" != "$HEAD_BEFORE" ]; then
    echo "  → commit nuevo; re-verificando el gate..." | tee -a "$RUNLOG"
    GATE_LOG="$(mktemp)"
    if bash -c "$GATE_CMD" >"$GATE_LOG" 2>&1; then
      echo "  ✓ gate OK: $(grep -iE 'passed|Oracle OK' "$GATE_LOG" | tail -1)" | tee -a "$RUNLOG"

      # ---- R1b (2026-08-20): la ACEPTACION ESPECIFICA de la tarea, EJECUTADA ----
      # El gate global esta verde ANTES y DESPUES de cualquier tarea, asi que re-correrlo no
      # distingue "hecha" de "no he roto nada". La clausula de ACEPTACION si distingue, pero
      # hasta hoy la comprobaba el propio agente a ojo y el loop se fiaba de esa parte -- justo
      # donde dice que no se fia. Ahora se ejecuta.
      # Si la tarea no declara comprobador, ACEPT sale vacio y el loop se comporta como siempre:
      # fallar abierto aqui es deliberado, una tarea vieja no debe empezar a revertirse sola.
      ACEPT="$($PY scripts/aceptacion_de_la_tarea.py "$LEDGER" "$HEAD_BEFORE" "$HEAD_AFTER" 2>/dev/null)"
      for a in $ACEPT; do
        if $PY scripts/aceptacion.py "$a" >/dev/null 2>&1; then
          echo "  ✓ aceptacion '$a' VERDE (la tarea esta hecha de verdad)" | tee -a "$RUNLOG"
        else
          echo "  ✗ aceptacion '$a' SIGUE ROJA → REVIERTO a $HEAD_BEFORE" | tee -a "$RUNLOG"
          $PY scripts/aceptacion.py "$a" 2>&1 | tail -2 | tee -a "$RUNLOG"
          git reset --hard "$HEAD_BEFORE" >/dev/null 2>&1
          break
        fi
      done
    else
      echo "  ✗ gate FALLA → REVIERTO a $HEAD_BEFORE" | tee -a "$RUNLOG"
      grep -iE 'failed|error|MRR' "$GATE_LOG" | tail -6 | tee -a "$RUNLOG"
      git reset --hard "$HEAD_BEFORE" >/dev/null 2>&1
    fi
    rm -f "$GATE_LOG"
  fi

  # ---- Completion multi-señal: COMPLETE en la salida Y cola vacía ----
  REM_AFTER="$(remaining_tasks)"
  if printf '%s' "$OUT" | grep -q "COMPLETE" && [ "$REM_AFTER" -eq 0 ]; then
    echo "=== ✅ COMPLETE verificado (0 tareas 🟢) en la iteración $i ===" | tee -a "$RUNLOG"; exit 0
  fi

  # ---- Progreso REAL = la cola DECRECIÓ (una tarea marcada [x]) y sin STUCK. Esto pilla:
  #      (a) el agente que escala (STUCK), (b) el que commitea pero no marca [x] (cola igual),
  #      (c) el commit revertido por el gate (la marca [x] vuelve atrás → cola igual). ----
  if printf '%s' "$OUT" | grep -q "STUCK"; then
    stuck=$((stuck+1)); echo "  ⚠ el agente ESCALÓ (STUCK) → no-progreso (stuck=$stuck)" | tee -a "$RUNLOG"
  elif [ "$REM_AFTER" -lt "$REM_BEFORE" ]; then
    stuck=0; echo "  ✓ progreso real: cola $REM_BEFORE→$REM_AFTER" | tee -a "$RUNLOG"
  else
    stuck=$((stuck+1)); echo "  ∅ la cola NO decreció ($REM_BEFORE→$REM_AFTER) → no-progreso (stuck=$stuck)" | tee -a "$RUNLOG"
  fi

  # ---- R3: parar ante no-progreso repetido ----
  if [ "$stuck" -ge "$MAX_STUCK" ]; then
    echo "=== ⛔ $MAX_STUCK iteraciones sin progreso → paro. Revisa ⛔ BLOQUEADAS y $RUNLOG ===" | tee -a "$RUNLOG"
    exit 2
  fi
done
echo "" | tee -a "$RUNLOG"
echo "=== ⏹ máximo $MAX iteraciones. Tareas 🟢 restantes: $(remaining_tasks) (ver $RUNLOG) ===" | tee -a "$RUNLOG"
