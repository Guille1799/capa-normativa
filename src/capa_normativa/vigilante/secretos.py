"""SEC — una credencial con forma reconocible en un fichero versionado.

Sustituye a un hook que existía para esto y **no veía nada**: leía el nivel equivocado del
JSONL (0 de 663 escrituras vistas, 0 disparos en 1.105 transcripts) y además no era un
escáner de texto sino un `POST` a un LLM (`/v1/chat/completions`). Medido: arreglarle el
parser bloqueaba ~1 de cada 10 sesiones, siempre en falso.

Aquí es determinista y local. Tres consecuencias de eso:

* **No oscila.** Un detector que un día dice que sí y otro que no es otra respuesta viva más.
* **No cuesta tokens**, así que sobrevive a un downgrade de plan.
* **Solo caza prefijos conocidos.** Nada de heurísticas de entropía: son fábricas de falsos
  positivos, y la fatiga apaga detectores.

## Dos decisiones que vienen de un incidente real

Un subagente pegó tres claves en claro en un informe que se commiteó (2026-06-26), y la
redacción que se hizo después **no escaneó `auditoria/runs/`**, así que la fuga sobrevivió en
un fichero versionado. De ahí:

1. **Se escanea TODO lo versionado**, incluidos informes y artefactos generados. La superficie
   de fuga no es solo el código.
2. **El hallazgo nunca incluye el secreto.** Solo fichero, línea y qué patrón casó. Un detector
   de fugas que imprime la fuga en su informe —que a su vez se commitea— es el mismo bug.

Y `# nosec` está **implementado de verdad**. El hook anterior lo anunciaba en su mensaje de
error y no tenía código que lo leyera: una vía de escape ficticia obliga a desactivar el
detector entero cuando aparece el primer falso positivo.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .versionados import versionados
from .hallazgo import Hallazgo

#: Solo prefijos publicados por sus emisores. Precisión sobre cobertura, a propósito.
#:
#: Cada patrón nuevo se mide antes de entrar: se corre sobre los 8 repos reales del usuario y
#: solo pasa si no produce falsos positivos. La medición del 2026-08-11 rechazó por eso el
#: `SUPABASE.{0,20}(key|KEY)` que se había propuesto: **35 aciertos, los 35 falsos** (nombres
#: de variable en código y placeholders de `.env.example`). Un patrón así no añade cobertura,
#: apaga el detector — que es el modo de fallo que este módulo existe para no repetir.
PATRONES: dict[str, re.Pattern[str]] = {
    "groq": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "github-pat-clasico": re.compile(r"gh[pousr]_[A-Za-z0-9]{36}"),
    "github-pat-fino": re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),
    "anthropic": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    # El `-` en la clase cubre el formato moderno `sk-proj-…`, que el patrón anterior no veía.
    # El `\b` es lo que hace que eso no cueste falsos positivos: sin él, `task-management-…`
    # y `disk-usage-…` contienen un `sk-` seguido de 20+ caracteres válidos.
    "openai": re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_-]{20,}"),
    "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "slack-bot": re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    "clave-privada": re.compile(r"-----BEGIN [A-Z ]{0,20}PRIVATE KEY-----"),
    # Estaba en el hook al que esto sustituye y se había perdido al reescribirlo: una
    # regresión de cobertura, no una decisión.
    "google-api": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    # No es un prefijo tan publicado como los demás, y entra igual porque es la forma exacta
    # de la clave de Gemini que SOBREVIVIÓ a la redacción del incidente de 2026-06-26 y sigue
    # hoy en un fichero versionado. Cobertura pagada con evidencia: 1 acierto en 8 repos, real.
    "google-oauth": re.compile(r"\bAQ\.[A-Za-z0-9_-]{40,}"),
    "supabase-secret": re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}"),
    "supabase-pat": re.compile(r"sbp_[a-f0-9]{40}"),
}

_SUPRESION = re.compile(r"#\s*(?:nosec|noqa)\b")
#: Directorios que no son código del repo. La comparación es por COMPONENTE de ruta
#: (`p.parts`), no por subcadena: `".git" in str(p)` casaba `.github/` entero —`.git` es
#: subcadena de `.github`— y dejaba fuera del barrido los workflows de CI versionados, que es
#: justo donde vive una credencial en `env:`. Medido el 2026-08-21 sobre el propio repo.
_EXCLUIR = {"venv", "site-packages", "__pycache__", "node_modules", ".git"}
_BINARIO = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".ico", ".woff",
            ".woff2", ".ttf", ".pyc", ".so", ".dll", ".xlsx", ".db", ".sqlite", ".lance"}


def _ficheros_versionados(repo: Path) -> list[Path]:
    """TODO lo versionado. Deliberadamente sin filtrar por tipo: la fuga real de 2026-06-26
    vivía en un `.md` de un directorio de informes, no en código."""
    # ⚠️ Misma enumeración que `sintaxis`, en UN sitio. La copia anterior se dejaba secuestrar
    # por el `GIT_DIR` de los hooks de git: en un worktree, este escáner de secretos recorría
    # CERO ficheros y respondía «limpio». Un escáner que miente es peor que no tenerlo.
    lista = versionados(repo)
    if lista is not None:
        return lista
    return [p for p in repo.rglob("*") if p.is_file()]


def revisar_secretos(repo: Path | str) -> list[Hallazgo]:
    """Un hallazgo por línea versionada con forma de credencial.

    El valor del secreto **no aparece** en el hallazgo: solo fichero, línea y patrón.
    """
    repo = Path(repo)
    hallazgos: list[Hallazgo] = []
    for p in _ficheros_versionados(repo):
        s = str(p)
        if _EXCLUIR.intersection(p.parts) or p.suffix.lower() in _BINARIO:
            continue
        try:
            texto = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if "\x00" in texto[:4096]:  # binario sin extensión conocida
            continue
        for i, linea in enumerate(texto.splitlines(), start=1):
            if _SUPRESION.search(linea):
                continue
            for nombre, patron in PATRONES.items():
                if patron.search(linea):
                    try:
                        donde = str(p.relative_to(repo))
                    except ValueError:
                        donde = s
                    hallazgos.append(Hallazgo(
                        detector="secretos",
                        codigo="SEC001",
                        fichero=donde,
                        linea=i,
                        # El secreto NO se imprime. Ni truncado.
                        mensaje=f"forma de credencial ({nombre}) en un fichero versionado",
                        arreglo=("Rota la credencial —asume que está comprometida desde el "
                                 "primer commit— y muévela a `.env` (gitignored). Si es un "
                                 "valor de prueba, añade `# nosec` al final de ESA línea: "
                                 "queda en el diff y alguien puede discutirlo."),
                    ))
                    break  # una línea, un hallazgo: N patrones sobre la misma línea es ruido
    return hallazgos
