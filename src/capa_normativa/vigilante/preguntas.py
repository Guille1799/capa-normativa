"""PRG — «una pregunta, una respuesta»: el detector de F13.

El síntoma que lo origina, en palabras del usuario: *«cada vez que hablo con Claude me dice un
TDEE distinto»*. Medido, la causa no era un bug: el prompt del coach llevaba **dos números
distintos con la misma etiqueta**, y cuál salía dependía de a qué línea atendiera el modelo.

## Qué es de este paquete y qué es del inquilino

**La autoridad vive en la persistencia del inquilino** (una fila, una tabla, un fichero), no en
el registro: una respuesta calculada cambia a diario y un YAML versionado no puede sostenerla.
Así que **el paquete no puede adivinar cuál es la autoridad: hay que declarársela.**

Es el mismo reparto que `Trinquete` (extractor y vocabulario del inquilino) y `punteros`
(corpus del inquilino). Aquí el inquilino declara **sus preguntas y sus productores**; el
paquete **cuenta, verifica las anclas y no deja que el número suba**.

## Lo que este detector NO hace, y hay que decirlo

**No rastrea la procedencia de un valor por el código.** Eso exige saber cómo habla el
inquilino con su base de datos —`db.table("daily_plan")` es Supabase— y no se generaliza. El
guard que hace eso vive, correctamente, en el inquilino.

Este hace tres cosas más humildes y comprobables:

1. **`PRG001` — un productor declarado cuyo ancla ya no está.** Es la clase de fallo nº 1 del
   sistema: la afirmación escrita que su fuente no sostiene. Un catálogo de productores que
   nadie re-verifica envejece igual que cualquier otro documento.
2. **`PRG002` — el trinquete de productores.** `productores(Q)` no puede subir. Es el criterio
   de legitimidad acordado: *una capa nueva vale solo si ABSORBE productores*. Sin esto, añadir
   un catálogo y dejar los 6 productores vivos parecería un avance.
3. **`PRG003` — candidatos sin declarar**, por una señal barata y de alta cobertura. Sale como
   informativo **a propósito**: la señal tiene falsos positivos por construcción, y *lo
   computable es la forma, no la intención*. Que algo sea un productor lo decide un humano; lo
   que la máquina puede hacer es no dejar que se le olvide mirarlo.

Y **`PRG004`**: una pregunta sin autoridad declarada. No es un error —es el «patrón B» del
paso 0, y en el primer inquilino son 3 de 9— pero **no puede quedar implícito**: mientras no
haya autoridad, *todos* sus productores son bypass y el trinquete no tiene contra qué medir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .hallazgo import Hallazgo

#: Clases del paso 0. `productor` es el único que el trinquete cuenta.
CLASES = ("productor", "fuente", "mutador", "latente")

#: ⚠️ `.claude/worktrees` está aquí por una corrida real: el detector propuso 50 candidatos y
#: los primeros eran COPIAS del propio repo dentro de worktrees de tareas. Un candidato que es
#: una copia del fichero que ya tienes declarado no es señal, es ruido — y el ruido apaga
#: detectores. Lo mismo con `_archivo`/`obs-fix`: árboles paralelos que ya causaron un
#: `SyntaxError` de dos meses en otro repo del usuario.
_EXCLUIR = ("node_modules", ".git/", "venv", "site-packages", "__pycache__", ".next",
            ".claude/", "_archivo", "obs-fix", "/dist/", "/build/", ".pytest_cache")
_CODIGO = ("*.py", "*.ts", "*.tsx", "*.js", "*.R", "*.r", "*.sql")


@dataclass(frozen=True)
class Productor:
    sitio: str
    """`ruta/al/fichero.py:123`. La línea es orientativa: el ancla es lo que manda."""
    ancla: str
    """Texto que TIENE que seguir estando en ese fichero. Es lo que hace falsable la entrada."""
    clase: str
    nota: str = ""


@dataclass(frozen=True)
class Pregunta:
    nombre: str
    autoridad: str | None
    tope: int
    productores: tuple[Productor, ...] = ()
    señales: tuple[str, ...] = field(default=())
    """Regex de alta cobertura para proponer candidatos. Con FP por construcción: informativo."""


def _norm(p: str) -> str:
    return p.replace("\\", "/")


def _cargar(crudo: dict[str, Any]) -> list[Pregunta]:
    fuera = []
    for nombre, d in crudo.items():
        ps = []
        for x in d.get("productores", []):
            clase = x.get("clase", "productor")
            if clase not in CLASES:
                raise ValueError(
                    f"[{nombre}] clase `{clase}` desconocida. Válidas: {', '.join(CLASES)}. "
                    "Las define PASO0_QUE_ES_UN_PRODUCTOR: solo `productor` cuenta para el tope, "
                    "porque `fuente` escribe la autoridad y eso es sano.")
            ps.append(Productor(sitio=x["sitio"], ancla=x["ancla"], clase=clase,
                                nota=x.get("nota", "")))
        fuera.append(Pregunta(
            nombre=nombre, autoridad=d.get("autoridad"),
            tope=int(d.get("tope", 1)), productores=tuple(ps),
            señales=tuple(d.get("senales", d.get("señales", ())))))
    return fuera


def revisar_preguntas(repo: Path | str, catalogo: Path | str | dict[str, Any]
                      ) -> list[Hallazgo]:
    """Comprueba el catálogo de preguntas del inquilino contra su código.

    `catalogo` es un YAML (o el dict ya cargado) con la forma:

        tdee:
          autoridad: "daily_plan.tdee_kcal"
          tope: 2
          productores:
            - sitio: "backend/api/chat.py:548"
              ancla: "total_kcal_day"
              clase: productor
              nota: "BYPASS: lee Garmin crudo y lo rotula TDEE"
          senales: ["def .*tdee", "tdee_kcal"]
    """
    repo = Path(repo)
    if isinstance(catalogo, (str, Path)):
        import yaml
        crudo = yaml.safe_load(Path(catalogo).read_text(encoding="utf-8")) or {}
        donde_cat = _norm(str(catalogo))
    else:
        crudo, donde_cat = catalogo, "<catálogo en memoria>"

    preguntas = _cargar(crudo)
    hallazgos: list[Hallazgo] = []

    def add(codigo: str, fichero: str, mensaje: str, arreglo: str, linea: int | None = None):
        hallazgos.append(Hallazgo(detector="preguntas", codigo=codigo, fichero=fichero,
                                  linea=linea, mensaje=mensaje, arreglo=arreglo))

    for q in preguntas:
        # ── PRG001 · el ancla de un productor declarado ya no está ──
        for p in q.productores:
            ruta, _, ln = p.sitio.partition(":")
            f = repo / ruta
            if not f.exists():
                add("PRG001", donde_cat,
                    f"[{q.nombre}] el productor `{p.sitio}` apunta a un fichero que no existe",
                    "El fichero se movió o se borró. Actualiza el catálogo o retira la entrada: "
                    "un productor que no se puede localizar no se puede contar ni arreglar.")
                continue
            texto = f.read_text(encoding="utf-8-sig", errors="replace")
            if p.ancla not in texto:
                add("PRG001", _norm(ruta),
                    f"[{q.nombre}] el ancla `{p.ancla}` ya NO está en este fichero",
                    "O el productor desapareció —y entonces bórralo del catálogo y BAJA el "
                    "tope— o se renombró y el ancla hay que actualizarla. Mientras no coincida, "
                    "el catálogo afirma algo que su fuente no sostiene.",
                    linea=int(ln) if ln.isdigit() else None)

        # ── PRG004 · sin autoridad declarada ──
        if not q.autoridad:
            add("PRG004", donde_cat,
                f"[{q.nombre}] no declara AUTORIDAD: no hay respuesta canónica",
                "Es el «patrón B» del paso 0. Mientras no haya autoridad, todos sus productores "
                "son bypass y el tope no tiene contra qué medir. Declara dónde vive la respuesta "
                "buena (una columna, una tabla, un fichero) aunque todavía no exista: eso es lo "
                "que convierte el arreglo en algo que se puede comprobar.")

        # ── PRG002 · el trinquete de productores ──
        cuenta = sum(1 for p in q.productores if p.clase == "productor")
        if cuenta > q.tope:
            add("PRG002", donde_cat,
                f"[{q.nombre}] {cuenta} productores declarados y el tope es {q.tope}",
                "El trinquete solo gira en un sentido. Si has AÑADIDO un productor, no subas el "
                "tope: quítalo. Si has hecho VISIBLE uno que ya existía, súbelo y escribe por "
                "qué — no son lo mismo, y esto no puede distinguirlas.")
        elif cuenta < q.tope:
            add("PRG005", donde_cat,
                f"[{q.nombre}] el tope está flojo: {cuenta} productor(es) contra un tope de {q.tope}",
                f"Bájalo a {cuenta}. Un tope por encima del recuento real deja hueco para meter "
                "un productor sin que nada se queje, y convierte el trinquete en decoración.")

        # ── PRG003 · candidatos sin declarar (informativo) ──
        if not q.señales:
            continue
        declarados = {_norm(p.sitio.partition(":")[0]) for p in q.productores}
        patrones = [re.compile(s, re.I) for s in q.señales]
        candidatos: set[str] = set()
        for patron in _CODIGO:
            for f in repo.rglob(patron):
                rel = _norm(str(f.relative_to(repo)))
                if rel in declarados or any(x in "/" + rel for x in _EXCLUIR):
                    continue
                try:
                    texto = f.read_text(encoding="utf-8-sig", errors="replace")
                except OSError:
                    continue
                if any(pat.search(texto) for pat in patrones):
                    candidatos.add(rel)
        if candidatos:
            muestra = ", ".join(sorted(candidatos)[:6])
            add("PRG003", donde_cat,
                f"[{q.nombre}] {len(candidatos)} fichero(s) sin declarar casan con sus señales: "
                f"{muestra}{'…' if len(candidatos) > 6 else ''}",
                "INFORMATIVO: la señal tiene falsos positivos por construcción, así que esto no "
                "afirma que sean productores. Míralos y decide: si lo son, declárarlos con su "
                "clase; si no, no hagas nada. Lo computable es la forma; la intención se declara.")

    return hallazgos
