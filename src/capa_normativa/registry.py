"""
Registro normativo — el motor.

PRINCIPIO: *parse, don't validate*. Una `Norm` SOLO existe si es válida. No hay
"validar después": los estados ilegales no se construyen, y si no se construyen,
el programa no arranca.

LO QUE ESTE REGISTRO NO HACE, A PROPÓSITO:
  - NO ejecuta lógica. Devuelve un valor y su procedencia.
  - NO encadena normas. El encadenamiento lo hace el código llamante, donde se depura.
  Es lo que separa esto de un motor de reglas (Drools), que fracasa justo ahí.

Lo segundo dejó de ser una promesa y pasó a ser una comprobación en v0.2.0 (R11):
`schema.yaml` declara `subject_dimensions`, la lista CERRADA de atributos del sujeto,
y una condición que ramifique por cualquier otra cosa NO se construye. Antes de eso el
límite se cumplía por disciplina: `when: {otra_norma: ">=0.30"}` era un rango bien
formado y el parser lo aceptaba tan campante.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

@dataclass(frozen=True)
class Schema:
    """El esquema se DECLARA (schema.yaml), no se cablea: la escala de certeza es
    específica de cada dominio y no puede vivir dentro de la infraestructura.

    `subject_dimensions` es la lista CERRADA de atributos del sujeto por los que una
    norma puede ramificar. Es lo que convierte el límite "una norma no referencia a
    otra" en algo que el parser puede comprobar: sin ella, el registro no distingue
    un atributo del sujeto del valor de otra norma — para él ambos son un string que
    llega a `resolve()`.
    """
    certainty_scale: tuple[str, ...]
    weak_from: str
    wildcards: frozenset[str]
    subject_dimensions: frozenset[str]
    unsupported_level: str | None = None

    @classmethod
    def load(cls, path: Path) -> "Schema":
        raw = yaml.safe_load(path.read_text("utf-8"))
        scale = tuple(raw["certainty_scale"])
        for key in ("weak_from", "unsupported_level"):
            if raw.get(key) and raw[key] not in scale:
                raise NormError(f"{key}={raw[key]!r} no está en certainty_scale")
        dims = raw.get("subject_dimensions")
        if not dims:
            raise NormError(
                "falta `subject_dimensions` en schema.yaml: la lista CERRADA de atributos "
                "del sujeto por los que se puede ramificar. Sin ella no hay forma de "
                "distinguir un atributo del sujeto del valor de otra norma, y encadenar "
                "normas queda permitido por accidente. Declara las que ya usas: es la "
                "unión de las claves `when` de tus normas"
            )
        if isinstance(dims, str) or not all(isinstance(d, str) for d in dims):
            raise NormError("`subject_dimensions` debe ser una lista de nombres")
        return cls(scale, raw["weak_from"], frozenset(raw["wildcards"]),
                   frozenset(dims), raw.get("unsupported_level"))

    def is_weak(self, certainty: str) -> bool:
        if certainty not in self.certainty_scale:
            raise NormError(f"certeza desconocida: {certainty!r} (escala: {self.certainty_scale})")
        return self.certainty_scale.index(certainty) >= self.certainty_scale.index(self.weak_from)


class NormError(Exception):
    """El registro no pudo construirse. El programa NO debe arrancar."""


class RetiredNormError(NormError):
    """Se pidió una norma RETIRADA. Es lo que impide que el código siga leyendo algo
    que ya no gobierna. Es el fallo del comentario fósil que sobrevive a su propia
    supersesión — aquí, imposible."""


# Rangos numéricos: lo único que el límite de expresividad permite además de
# igualdad y pertenencia a conjunto. Deliberadamente pobre — sin aritmética.
_CMP = re.compile(r"^(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)$")
_ITV = re.compile(r"^([\[(])\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*([\])])$")


def _range_match(value: str, spec: str) -> bool | None:
    """True/False si `spec` es un rango; None si no lo es (⇒ comparar por igualdad)."""
    m = _CMP.match(spec)
    itv = _ITV.match(spec)
    if not (m or itv):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    if m:
        op, n = m.group(1), float(m.group(2))
        return {">=": x >= n, "<=": x <= n, ">": x > n, "<": x < n}[op]
    lo_b, lo, hi, hi_b = itv.group(1), float(itv.group(2)), float(itv.group(3)), itv.group(4)
    return ((x >= lo if lo_b == "[" else x > lo)
            and (x <= hi if hi_b == "]" else x < hi))


@dataclass(frozen=True)
class Branch:
    when: dict[str, str]
    value: Any
    evidence: tuple[str, ...]
    note: str | None = None


@dataclass(frozen=True)
class Norm:
    slug: str
    title: str
    status: str
    strength: str
    certainty: str
    unit: str
    semantics: str
    branches: tuple[Branch, ...]
    adjudication: dict[str, Any] | None
    expires: date | None
    requires: tuple[str, ...] = ()
    retirement: dict[str, Any] | None = None
    provenance_note: str | None = None


@dataclass(frozen=True)
class Resolution:
    """Lo que el motor recibe: el valor Y de dónde sale. Nunca un número pelado."""
    slug: str
    value: Any
    unit: str
    semantics: str
    matched: dict[str, str]
    evidence: tuple[str, ...]
    strength: str
    certainty: str
    is_fallback: bool          # True = se aplicó la rama del sujeto desconocido
    missing: tuple[str, ...] = ()   # datos del sujeto que faltan (declarados, no adivinados)

    def __str__(self) -> str:
        via = " (rama por defecto)" if self.is_fallback else ""
        falta = f" ⚠ falta: {','.join(self.missing)}" if self.missing else ""
        return (f"{self.slug}={self.value} {self.unit}{via} · {self.matched} · "
                f"{self.strength}/{self.certainty} · ev={','.join(self.evidence)}{falta}")


# Caracteres que delatan un operador inventado (glob, regex, alternancia, negación).
_OPERATOR_CHARS = set("*?|!~&^$+")


def _check_condition(key: str, value: Any, schema: Schema, bad, i: int) -> None:
    """Una condición SOLO puede ser: comodín · igualdad simple · rango numérico, y
    SOBRE UNA DIMENSIÓN DECLARADA. Es el límite de expresividad, convertido en código."""
    # ── R11 · solo se ramifica por dimensiones DECLARADAS del sujeto ────────
    # Sin esto, R9 comprueba la FORMA de la condición pero no su SEMÁNTICA: un
    # `when: {otra_norma: ">=0.30"}` es un rango bien formado y pasaba. O sea que una
    # norma podía referenciar a otra —lo que el límite prohíbe— y el encadenamiento
    # quedaba en manos de la disciplina, no de la construcción. De regalo, esto caza
    # las erratas: una dimensión mal escrita no matchea nunca y falla EN SILENCIO
    # cayendo al fallback, que es el peor modo de fallo posible.
    if key not in schema.subject_dimensions:
        raise bad(f"rama #{i}: '{key}' no es una dimensión declarada del sujeto "
                  f"({'|'.join(sorted(schema.subject_dimensions))}). Si es el nombre de otra "
                  f"norma, resuélvelas por separado y compón el resultado en tu código: el "
                  f"registro devuelve valores, no encadena reglas. Si es un atributo legítimo "
                  f"del sujeto, decláralo en `subject_dimensions`")
    if isinstance(value, (list, tuple, set)):
        raise bad(f"rama #{i}, '{key}': una LISTA es una disyunción — prohibida. "
                  f"Parte la rama en varias, o la lógica se queda en el código")
    if isinstance(value, dict):
        raise bad(f"rama #{i}, '{key}': condición compuesta — prohibida")
    if isinstance(value, bool):
        raise bad(f"rama #{i}, '{key}': usa la cadena 'true'/'false', no un booleano "
                  f"(evita que YAML convierta valores del dominio en booleanos)")
    s = str(value)
    if s.lower() in schema.wildcards:
        return
    if _range_match("0", s) is not None:      # es un rango bien formado
        return
    if _OPERATOR_CHARS & set(s):
        raise bad(f"rama #{i}, '{key}'={s!r}: parece un operador inventado. "
                  f"Solo se permite: comodín, igualdad simple o rango numérico")


def _parse_norm(raw: dict, known_evidence: set[str], today: date, schema: Schema) -> Norm:
    slug = raw.get("slug")
    if not slug:
        raise NormError("norma sin slug")

    def bad(msg: str) -> NormError:
        return NormError(f"[{slug}] {msg}")

    # ── R1 · certeza débil ⇒ jamás vinculante (en medicina, GRADE) ─────────
    strength, certainty = raw.get("strength"), raw.get("certainty")
    weak = schema.is_weak(certainty)
    if strength == "vinculante" and weak:
        raise bad(f"strength=vinculante con certainty={certainty}: la escala declarada lo prohíbe")

    # ── R2 · caducidad (OPA-style): lo frágil expira solo ──────────────────
    status = raw.get("status")
    expires = raw.get("expires")
    expires = date.fromisoformat(expires) if expires else None
    if weak and expires is None:
        raise bad("certeza débil sin fecha de expiración")
    if status == "vigente" and expires and expires < today:
        raise bad(f"norma vigente CADUCADA el {expires}: hay que re-adjudicarla")

    # ── R8 · retirar una norma es un ACTO, con motivo y sustituto ──────────
    # Sin esto, una norma retirada se queda ahí y alguien la vuelve a leer: es
    # exactamente el comentario fósil que sobrevive a su propia supersesión.
    retirement = raw.get("retirement")
    if status in {"retirada", "superseded"}:
        if not retirement or not retirement.get("reason"):
            raise bad(f"status={status} sin `retirement.reason`")
        if not retirement.get("replaced_by"):
            raise bad(f"status={status} sin `retirement.replaced_by` "
                      f"(si de verdad no hay sustituto, decláralo como lista vacía)")
    elif retirement:
        raise bad("tiene `retirement` pero su status no es retirada/superseded")

    # ── R3 · un conflicto declarado exige adjudicación ────────────────────
    adjudication = raw.get("adjudication")
    if adjudication and not adjudication.get("resolution"):
        raise bad("adjudicación sin `resolution`")

    # ── R4 · ramas: toda rama lleva evidencia, y la evidencia debe EXISTIR ──
    unsupported = (certainty == schema.unsupported_level)
    if unsupported and not raw.get("provenance_note"):
        raise bad(f"certainty={certainty} exige `provenance_note`: de dónde salió el número "
                  f"(y 'nadie lo sabe' es una respuesta válida y útil)")
    if not unsupported and raw.get("provenance_note"):
        raise bad("`provenance_note` solo se usa cuando NO hay evidencia; aquí cita la evidencia")

    branches: list[Branch] = []
    for i, b in enumerate(raw.get("branches") or []):
        ev = tuple(b.get("evidence") or ())
        if not ev and not unsupported:
            raise bad(f"rama #{i} sin evidencia (si de verdad no la hay, declara "
                      f"certainty={schema.unsupported_level} y su `provenance_note`)")
        if ev and unsupported:
            raise bad(f"rama #{i}: si hay evidencia, la certeza no puede ser "
                      f"{schema.unsupported_level}")
        missing = [e for e in ev if e not in known_evidence]
        if missing:
            raise bad(f"rama #{i} cita evidencia inexistente: {missing}")
        # ── R9 · LÍMITE DE EXPRESIVIDAD, mecanizado ────────────────────
        # Sin esto el límite vive en un doc y no impide nada: un `when` con una
        # LISTA (disyunción) o un comodín inventado se acepta y **falla en
        # silencio** cayendo al fallback. Encontrado intentando colar el
        # cayendo al fallback. El `value` no se restringe: solo la CONDICIÓN.
        for k, v in (b.get("when") or {}).items():
            _check_condition(k, v, schema, bad, i)
        branches.append(Branch(when=dict(b.get("when") or {}), value=b.get("value"),
                               evidence=ev, note=b.get("note")))
    if not branches:
        raise bad("sin ramas: una norma sin valor no es una norma")

    # ── R10 · dos ramas no pueden matchear al mismo sujeto ─────────────────
    # Si dos ramas solapan, gana la primera del fichero: el ORDEN decide el valor,
    # que es justo lo que el límite de expresividad prohíbe. La rama del sujeto
    # desconocido queda fuera de la comprobación — solapa por definición, y el
    # motor la prueba SIEMPRE la última (orden fijo del motor, no del fichero).
    #
    # LIMITACIÓN: detecta igualdad y subsunción exacta de condiciones. NO detecta
    # solapamiento entre RANGOS (">=50" y ">=100" solapan y aquí pasan).
    concretas = [b for b in branches
                 if not all(str(v).lower() in schema.wildcards for v in b.when.values())]
    for i, a in enumerate(concretas):
        for c in concretas[i + 1:]:
            sa, sc = set(a.when.items()), set(c.when.items())
            if sa <= sc or sc <= sa:
                raise bad(f"dos ramas matchean al mismo sujeto ({dict(sa)} y {dict(sc)}): "
                          f"el orden del fichero decidiría el valor. Hazlas disjuntas")

    # ── R5 · ANTI-HARDCODEO: hay que declarar qué pasa con quien NO conoces ─
    dims = {d for b in branches for d in b.when}
    for dim in dims:
        if not any(str(b.when.get(dim, "")).lower() in schema.wildcards for b in branches):
            raise bad(f"la dimensión '{dim}' no cubre el caso desconocido "
                      f"(falta una rama {dim}: {'|'.join(sorted(schema.wildcards))})")

    # ── R7 · `requires`: datos del sujeto que la norma necesita ────────────
    # NO es una referencia a otra norma (eso el límite lo prohíbe): es declarar qué
    # dimensiones del sujeto hacen falta. Si faltan, resuelve a la rama por defecto
    # y lo DECLARA — que es como se bloquea S1.4 por no capturar la edad.
    requires = tuple(raw.get("requires") or ())
    for r in requires:
        if r not in dims:
            raise bad(f"requires '{r}' pero ninguna rama ramifica por esa dimensión")

    return Norm(slug=slug, title=raw.get("title", ""), status=status or "",
                strength=strength, certainty=certainty, unit=raw.get("unit", ""),
                semantics=raw.get("semantics", ""), branches=tuple(branches),
                adjudication=adjudication, expires=expires, requires=requires,
                retirement=retirement, provenance_note=raw.get("provenance_note"))


class NormRegistry:
    def __init__(self, norms: dict[str, Norm], schema: Schema):
        self._norms = norms
        self._schema = schema

    @classmethod
    def load(cls, base_dir: Path | str | None = None, *, norms_path: Path | None = None,
             evidence_path: Path | None = None, schema_path: Path | None = None,
             today: date | None = None) -> "NormRegistry":
        """Parsea el registro. Cualquier estado ilegal ⇒ NormError ⇒ el programa no arranca.

        `base_dir` es el directorio con `schema.yaml`, `evidence.yaml` y `norms.yaml`
        — los datos son del proyecto consumidor, no del paquete. Las rutas sueltas
        siguen disponibles para tests y casos mixtos.
        """
        today = today or date.today()
        base = Path(base_dir) if base_dir is not None else None
        if base is None and not (norms_path and evidence_path and schema_path):
            raise NormError("indica `base_dir`, o las tres rutas (schema/evidence/norms)")

        def _p(explicit: Path | None, name: str) -> Path:
            return explicit if explicit is not None else base / name   # type: ignore[operator]

        schema = Schema.load(_p(schema_path, "schema.yaml"))
        ev_raw = yaml.safe_load(_p(evidence_path, "evidence.yaml").read_text("utf-8"))
        known = {e["id"] for e in (ev_raw or [])}

        norms: dict[str, Norm] = {}
        for raw in yaml.safe_load(_p(norms_path, "norms.yaml").read_text("utf-8")) or []:
            n = _parse_norm(raw, known, today, schema)
            if n.slug in norms:                       # R6 · IDs únicos (mata el caso `S4.2`)
                raise NormError(f"slug duplicado: {n.slug}")
            norms[n.slug] = n

        # ── R11 (2ª mitad) · se cierra la puerta trasera de R11 ─────────────
        # R11 obliga a que toda condición ramifique por una dimensión declarada. Sin
        # esto quedaría la salida fácil: DECLARAR el nombre de una norma como si fuera
        # un atributo del sujeto, y encadenar igual. Un nombre no puede ser las dos
        # cosas — esa ambigüedad es justo lo que hay que impedir.
        colision = sorted(schema.subject_dimensions & set(norms))
        if colision:
            raise NormError(
                f"estos nombres están declarados como dimensión del sujeto Y son slugs de "
                f"normas: {colision}. Un nombre es una cosa o la otra: si ramificas por él, "
                f"estarías encadenando normas por la puerta de atrás. Renombra uno de los dos"
            )
        return cls(norms, schema)

    def resolve(self, slug: str, **subject: str) -> Resolution:
        """Devuelve valor + procedencia para ESTE sujeto. No ejecuta lógica."""
        norm = self._norms.get(slug)
        if norm is None:
            raise NormError(f"norma inexistente: {slug}")
        if norm.retirement:
            rep = ", ".join(norm.retirement.get("replaced_by") or []) or "(sin sustituto)"
            raise RetiredNormError(
                f"[{slug}] RETIRADA el {norm.retirement.get('date')} → usa: {rep}. "
                f"Motivo: {' '.join(str(norm.retirement['reason']).split())[:160]}")

        # `requires` no cubierto ⇒ dato ausente. No se adivina: se va a la rama por
        # defecto y se DECLARA (`missing`), para que el motor pueda decirlo al usuario.
        missing = tuple(r for r in norm.requires if not subject.get(r))

        fallback: Branch | None = None
        for b in norm.branches:
            if all(str(v).lower() in self._schema.wildcards for v in b.when.values()):
                fallback = b          # rama del sujeto desconocido: se prueba la última
                continue
            if missing:
                continue
            if self._matches(subject, b.when):
                return self._mk(norm, b, is_fallback=False, missing=())

        if fallback is None:
            raise NormError(f"[{slug}] sin rama aplicable a {subject} y sin rama por defecto")
        return self._mk(norm, fallback, is_fallback=True, missing=missing)

    def _matches(self, subject: dict[str, str], when: dict[str, str]) -> bool:
        """Un comodín DENTRO de una rama específica ('age_years: any') acepta cualquier
        valor — la rama dice 'esta dimensión no me discrimina'. Sin esto, una rama mixta
        (específica en una dimensión, comodín en otra) no matchea nunca. Bug encontrado
        por un caso con varias dimensiones; uno de una sola dimensión no puede
        encontrarlo."""
        for k, v in when.items():
            if str(v).lower() in self._schema.wildcards:
                continue
            rng = _range_match(str(subject.get(k, "")), str(v))
            if rng is not None:
                if not rng:
                    return False
                continue
            if str(subject.get(k, "")).lower() != str(v).lower():
                return False
        return True

    @staticmethod
    def _mk(norm: Norm, b: Branch, *, is_fallback: bool,
            missing: tuple[str, ...]) -> Resolution:
        return Resolution(slug=norm.slug, value=b.value, unit=norm.unit,
                          semantics=norm.semantics, matched=b.when, evidence=b.evidence,
                          strength=norm.strength, certainty=norm.certainty,
                          is_fallback=is_fallback, missing=missing)
