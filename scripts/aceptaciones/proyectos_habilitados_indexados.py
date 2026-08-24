"""Todo proyecto habilitado en `projects_config.yaml` tiene documentos en el índice RAG.

## Qué se exige, y por qué esto es lo que importa

El índice es lo que contesta cuando una sesión pregunta «¿qué decidimos sobre X?». Un proyecto
declarado y **no indexado** no da error: da menos respuestas, y nadie sabe que faltan. Es la misma
familia que las instrucciones que decían «5 proyectos»: lo que no se nombra, no se busca.

## Por qué se REEMPLAZA la aceptación anterior

La anterior contaba líneas `Watching:` en el log de `context_watcher_master`, y exigía tantas como
proyectos habilitados. Medido el 2026-08-23, eso ya no medía lo que representaba:

  · El proceso del watcher **no está corriendo** y su último log es del 18-ago. Quien mantiene el
    índice hoy es la tarea programada `ContextWatcher-Reindex`, que corrió a las 14:00 con
    resultado 0.
  · Y el índice **sí está al día**: los ficheros internos de `vectors.lancedb` se escribieron a las
    17:18 de hoy. (El mtime del *directorio* marca el 6-jul y engaña; hay que mirar dentro.)
  · Y `capa_normativa` **sí está indexado**: 61 documentos, y una búsqueda real devuelve fragmentos
    de su `PROGRESS.md` y su `PENDIENTES.md`.

O sea que la aceptación estaba ROJA por un proxy que se había despegado de la cosa: contaba las
huellas de un mecanismo retirado. No es ablandarla medir el índice — es más fuerte, porque unas
líneas de log se pueden emitir sin que se indexe nada, y esto no.

⚠️ Nace VERDE, y por eso NO es una promesa sino una GUARDA: se pone roja sola el día que alguien
habilite un proyecto que no llegue al índice, que es exactamente el fallo que la tarea perseguía.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

#: Derivada, no escrita: repo publico (la nota gemela esta en `scripts/aceptacion.py`).
MCP = Path(os.environ.get("PROYECTOS_RAIZ") or Path.home() / "proyectos") / "mcp_smart_context"
CONFIG = MCP / "projects_config.yaml"
INDICE = MCP / "context_memory.db"


def habilitados() -> list[str]:
    import yaml
    datos = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return [p["name"] for p in datos["projects"] if p.get("enabled")]


def indexados() -> dict:
    """Documentos por proyecto, tal y como estan HOY en el indice."""
    con = sqlite3.connect("file:" + INDICE.as_posix() + "?mode=ro", uri=True)
    try:
        return {p: n for p, n in con.execute(
            "SELECT project_name, COUNT(*) FROM messages GROUP BY 1")}
    finally:
        con.close()


def main() -> int:
    if not CONFIG.is_file():
        print("ROJO: no existe " + str(CONFIG) + ": sin config no hay nada que comprobar")
        return 1
    if not INDICE.is_file():
        print("ROJO: no existe " + str(INDICE) + ": el indice no esta donde se dice")
        return 1

    esperados = habilitados()
    if not esperados:
        print("ROJO: projects_config.yaml no declara ningun proyecto habilitado — sin eso esta"
              " comprobacion aprobaria en vacio")
        return 1

    tiene = indexados()
    ausentes = [p for p in esperados if tiene.get(p, 0) == 0]
    if ausentes:
        print("ROJO: habilitados en el YAML y SIN documentos en el indice: " + ", ".join(ausentes)
              + " (un proyecto que no se indexa no da error: da menos respuestas, y no se nota)")
        return 1
    detalle = ", ".join(p + "=" + str(tiene[p]) for p in esperados)
    print("VERDE: los " + str(len(esperados)) + " proyectos habilitados tienen documentos en el"
          " indice (" + detalle + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
