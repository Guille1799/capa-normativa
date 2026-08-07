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

v0.3.0 (R12) cierra el otro agujero de la misma familia: dos RANGOS que solapan. R10
comparaba conjuntos de pares, así que ">=40" y ">=60" eran literales distintos y convivían
— y con un eje partido en bandas eso no es un aviso que falta, es la respuesta equivocada
en silencio. Ahora se calcula si existe algún sujeto que cumpla las dos ramas.

v0.4.0 (R13) aplica el mismo principio a la FORMA: las claves que el parser no conoce se
aceptaban y se descartaban en silencio, así que lo escrito y lo que el registro hace podían
no coincidir sin que nada fallara. Una errata en `value` llegaba a producir una norma que
emitía None como si fuera una respuesta deliberada.

v0.5.0 (R14) cierra la familia de "lo declarado tiene que ser de verdad": un `status`
desconocido ya no se acepta (una errata desactivaba la caducidad), los punteros de
retirada tienen que apuntar a normas que existen, y `bloqueada` pasa a existir — una
norma con evidencia en conflicto sin adjudicar se NIEGA a emitir en vez de elegir por
orden de fichero.

v0.6.0 (R15) baja por fin a la capa ① EVIDENCIA, que en cinco versiones nadie había
mirado: el parser solo comprobaba los IDs. Ahora los ids no pueden repetirse, las marcas
de recencia no pueden mentir y —lo importante— una norma NO puede declarar más certeza de
la que sostiene su evidencia. Hasta aquí la certeza era autodeclarada, así que R1 ("nada
vinculante con certeza débil") se saltaba escribiendo `alta` a mano y toda la escala era
decorativa. Los tres chequeos son OPT-IN: el nombre de los campos es del consumidor.

v0.7.0 (R16) cubre por fin la OTRA MITAD del contrato. Todo lo anterior protege lo que se
ESCRIBE en el YAML; nadie miraba qué pasa cuando el código PREGUNTA. Una errata en la
llamada se ignoraba en silencio y caía al comodín; un 0 contaba como dato ausente; el
registro entregaba referencias a sus propias tripas (un `.append()` de quien preguntaba
cambiaba la norma para todos); y dos ramas comodín convivían dejando que el orden del
fichero decidiera el valor — en el único sitio donde R10 decidió no mirar.
"""
from __future__ import annotations

import difflib
import re
from copy import deepcopy
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
    # ── Capa ① EVIDENCIA (R15, v0.6.0) — todo OPCIONAL ────────────────────
    # El registro no sabe cómo se llaman los campos de tu evidencia: son tuyos. Si los
    # declaras, comprueba dos cosas que hasta ahora no miraba NADIE — que una norma no
    # declare más certeza de la que su evidencia sostiene, y que las marcas de recencia
    # no mientan. Si no los declaras, no comprueba nada y todo sigue igual.
    evidence_certainty_field: str | None = None
    evidence_year_field: str | None = None
    evidence_recent_field: str | None = None
    recency_horizon: int | None = None

    @classmethod
    def load(cls, path: Path) -> "Schema":
        raw = yaml.safe_load(path.read_text("utf-8"))
        # ── R13 aplicado al PROPIO ESQUEMA (v0.9.0) ────────────────────────
        # El agujero más embarazoso del paquete: R13 rechaza una clave desconocida en una
        # norma o en una rama desde la v0.4.0, y este fichero —el que ENCIENDE Y APAGA
        # reglas— se las tragaba. Una errata de UNA letra en `evidence_certainty_field`
        # desactivaba R15b y R17 **sin un solo aviso**: el registro cargaba, y la regla
        # que impide que una norma se declare más segura de lo que su fuente sostiene
        # dejaba de existir. La puerta blindada y la ventana abierta al lado.
        _check_keys(raw, _SCHEMA_KEYS, "en schema.yaml", NormError)
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
                   frozenset(dims), raw.get("unsupported_level"),
                   raw.get("evidence_certainty_field"), raw.get("evidence_year_field"),
                   raw.get("evidence_recent_field"), raw.get("recency_horizon"))

    def rank(self, certainty: str) -> int:
        """Posición en la escala: 0 es la más fuerte. Sirve para comparar dos certezas."""
        if certainty not in self.certainty_scale:
            raise NormError(f"certeza desconocida: {certainty!r} (escala: {self.certainty_scale})")
        return self.certainty_scale.index(certainty)

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


class BlockedNormError(NormError):
    """Se pidió una norma BLOQUEADA: hay evidencia en conflicto y nadie la ha adjudicado.

    Emitir un valor aquí sería resolver el conflicto a escondidas, eligiendo por orden de
    fichero o por descuido. El registro prefiere no responder: una norma tiene valor o
    está explícitamente bloqueada, nunca ambigua."""


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


# ── Aritmética de intervalos (R12) ─────────────────────────────────────────
# El intervalo se representa como (lo, lo_cerrado, hi, hi_cerrado). Existe SOLO para
# poder decidir si dos condiciones pueden cumplirse a la vez: no se expone, no se
# evalúa en runtime y no amplía lo que el registro sabe expresar.
_INF = float("inf")


def _interval(spec: str) -> tuple[float, bool, float, bool] | None:
    """El rango como intervalo; None si `spec` no es un rango."""
    m = _CMP.match(spec)
    if m:
        op, n = m.group(1), float(m.group(2))
        return {">=": (n, True, _INF, False), ">": (n, False, _INF, False),
                "<=": (-_INF, False, n, True), "<": (-_INF, False, n, False)}[op]
    itv = _ITV.match(spec)
    if itv:
        return (float(itv.group(2)), itv.group(1) == "[",
                float(itv.group(3)), itv.group(4) == "]")
    return None


def _is_empty(iv: tuple[float, bool, float, bool]) -> bool:
    """Un intervalo vacío es una rama MUERTA: no matchea nunca y cae al fallback en
    silencio, que es el peor modo de fallo posible."""
    lo, lo_c, hi, hi_c = iv
    return lo > hi or (lo == hi and not (lo_c and hi_c))


def _intervals_overlap(a: tuple[float, bool, float, bool],
                       b: tuple[float, bool, float, bool]) -> bool:
    lo, lo_c = max((a[0], a[1]), (b[0], b[1]), key=lambda p: (p[0], not p[1]))
    hi, hi_c = min((a[2], a[3]), (b[2], b[3]), key=lambda p: (p[0], p[1]))
    return not _is_empty((lo, lo_c, hi, hi_c))


def _conditions_compatible(va: Any, vb: Any, wildcards: frozenset[str]) -> bool:
    """¿Existe algún sujeto que cumpla las DOS condiciones a la vez?

    Es la pregunta que R10 respondía solo para igualdad y subsunción. Con rangos hay
    que calcularla: `">=40"` y `">=60"` son literales distintos y solapan de todas formas.
    """
    sa, sb = str(va), str(vb)
    if sa.lower() in wildcards or sb.lower() in wildcards:
        return True
    ia, ib = _interval(sa), _interval(sb)
    if ia and ib:
        return _intervals_overlap(ia, ib)
    if ia or ib:                       # rango contra literal: ¿el literal cae dentro?
        rango, literal = (sa, sb) if ia else (sb, sa)
        return _range_match(literal, rango) is True
    return sa.lower() == sb.lower()


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
    # v0.9.0 · True si la norma NO ramifica: un valor con procedencia, no una decisión.
    # Es lo que permite al consumidor distinguir "no hay sujeto" de "no te conozco".
    constant: bool = False
    blocking: dict[str, Any] | None = None
    precaution: str | None = None

    @property
    def is_binding(self) -> bool:
        """¿OBLIGA? `vinculante` y `precautorio` obligan igual; cambia en qué se apoyan.

        Existe para que el consumidor no tenga que conocer el vocabulario: sin esto, cada
        `if norm.strength == "vinculante"` que hay por ahí dejó de ser correcto el día que
        apareció `precautorio` — y habría fallado hacia el lado malo, tratando un veto de
        seguridad como una sugerencia.
        """
        return self.strength in _OBLIGAN


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
    iv = _interval(s)
    if iv is not None:                        # es un rango bien formado
        # R12 · un rango VACÍO ("[5,3]", "(4,4)") es una rama muerta: no matchea nunca,
        # cae al fallback en silencio y devuelve un valor plausible que no es el suyo.
        if _is_empty(iv):
            raise bad(f"rama #{i}, '{key}'={s!r}: el rango está VACÍO, así que esa rama "
                      f"no puede matchear nunca y caería al comodín sin avisar")
        return
    if _OPERATOR_CHARS & set(s):
        raise bad(f"rama #{i}, '{key}'={s!r}: parece un operador inventado. "
                  f"Solo se permite: comodín, igualdad simple o rango numérico")


# ── R13 · claves conocidas (parse, don't validate aplicado a la FORMA) ─────
# Un parser permisivo con las claves que no entiende las DESCARTA en silencio, y entonces
# lo que alguien escribió y lo que el registro hace dejan de coincidir sin que nada falle.
# Encontrado intentando poner `certainty` en una rama: se aceptaba, se tiraba, y `resolve`
# devolvía la certeza de la norma. Y una errata en `value` (`valeu: 55.0`) hacía que la
# norma cargara y emitiera None como si fuera una respuesta deliberada.
_NORM_KEYS = frozenset({
    "value", "evidence", "note",  # v0.9.0 · la forma constante (sin `branches`)
    "slug", "title", "status", "strength", "certainty", "unit", "semantics",
    "branches", "adjudication", "expires", "requires", "retirement", "provenance_note",
    "blocking", "precaution",
})
_BRANCH_KEYS = frozenset({"when", "value", "evidence", "note"})

# Los estados que el registro ENTIENDE. No es una etiqueta libre: cada uno cambia lo que
# hace (si emite, si exige motivo, si caduca), así que uno desconocido es una norma que
# se comporta de forma imprevista.
_STATUS = frozenset({"vigente", "retirada", "superseded", "bloqueada"})

# R18 (v0.8.0) · con cuánta fuerza OBLIGA una norma. Vocabulario cerrado por el mismo motivo
# que `status`: hasta la v0.7.0 solo se comparaba contra "vinculante", así que `vinculnte`
# convertía una norma obligatoria en una sugerencia, en silencio.
#
# `precautorio` es la pieza nueva, y existe porque faltaba un caso REAL: un veto de seguridad
# obliga *precisamente porque* la evidencia es débil — no porque sepamos que hace daño, sino
# porque NO sabemos que sea seguro. R1 ("nada vinculante con certeza débil") lo prohibía, así
# que esas reglas tenían que declararse `condicional` mientras el código las aplicaba a
# rajatabla: el registro describiendo mal lo que el motor hace, y justo en seguridad.
_STRENGTH = frozenset({"vinculante", "condicional", "precautorio"})
# Las que OBLIGAN. `precautorio` obliga igual que `vinculante`; lo que cambia es en qué se apoya.
_OBLIGAN = frozenset({"vinculante", "precautorio"})
# Los que pueden emitir un valor. Solo a estos les aplican las reglas de vigencia: en una
# norma retirada o bloqueada, caducar no significa nada (roce anotado desde §5.6).
_EMITEN = frozenset({"vigente"})


# Claves del ESQUEMA. `format_version` entra ya declarada aunque todavía no se use: si se
# añadiera después, la propia comprobación de arriba la rechazaría — el gate nuevo mordiendo
# a la fase siguiente.
_SCHEMA_KEYS = frozenset({
    "certainty_scale", "weak_from", "wildcards", "subject_dimensions", "unsupported_level",
    "evidence_certainty_field", "evidence_year_field", "evidence_recent_field",
    "recency_horizon", "format_version",
})


def _check_keys(raw: dict, permitidas: frozenset[str], donde: str, bad) -> None:
    sobran = sorted(set(raw) - permitidas)
    if not sobran:
        return
    pistas = []
    for k in sobran:
        cerca = difflib.get_close_matches(k, sorted(permitidas), n=1, cutoff=0.7)
        pistas.append(f"'{k}'" + (f" (¿querías decir '{cerca[0]}'?)" if cerca else ""))
    raise bad(f"{donde}: claves desconocidas {', '.join(pistas)}. Se aceptaban y se "
              f"DESCARTABAN en silencio, así que lo escrito y lo que hace el registro "
              f"podían no coincidir. Conocidas: {'|'.join(sorted(permitidas))}")


def _parse_norm(raw: dict, known_evidence: dict[str, dict], today: date,
                schema: Schema) -> Norm:
    slug = raw.get("slug")
    if not slug:
        raise NormError("norma sin slug")

    def bad(msg: str) -> NormError:
        return NormError(f"[{slug}] {msg}")

    _check_keys(raw, _NORM_KEYS, "en la norma", bad)

    # ── R18 · `strength` es vocabulario cerrado ────────────────────────────
    strength, certainty = raw.get("strength"), raw.get("certainty")
    if strength not in _STRENGTH:
        cerca = difflib.get_close_matches(str(strength), sorted(_STRENGTH), n=1, cutoff=0.6)
        raise bad(f"strength={strength!r} desconocido{f' (¿querías decir {cerca[0]!r}?)' if cerca else ''}. "
                  f"Conocidos: {'|'.join(sorted(_STRENGTH))}")

    # ── R1 · certeza débil ⇒ jamás vinculante (en medicina, GRADE) ─────────
    weak = schema.is_weak(certainty)
    if strength == "vinculante" and weak:
        raise bad(f"strength=vinculante con certainty={certainty}: la escala declarada lo prohíbe. "
                  f"Si obliga POR PRECAUCIÓN —porque no sabes que sea seguro— eso es "
                  f"strength=precautorio, y exige declarar de qué protege")

    # ── R18b · `precautorio` obliga, pero tiene que decir de qué protege ───
    # Sin esto sería la puerta de atrás de R1: cualquiera vincula cualquier cosa con
    # evidencia floja sin más que cambiar una palabra. El daño evitado es texto libre y
    # nadie puede verificarlo, pero obliga a NOMBRARLO y deja la afirmación en el diff —
    # el mismo trato que `provenance_note`.
    precaution = raw.get("precaution")
    if strength == "precautorio":
        if not precaution:
            raise bad("strength=precautorio exige `precaution`: de qué daño protege, y por qué "
                      "obliga aun sin evidencia fuerte")
        if not weak:
            raise bad(f"strength=precautorio con certainty={certainty}: si la evidencia SOSTIENE "
                      f"la regla, es `vinculante`. `precautorio` significa 'obliga porque NO "
                      f"sabemos que sea seguro', y con certeza fuerte eso ya no es cierto")
    elif precaution:
        raise bad("tiene `precaution` pero su strength no es precautorio")

    # ── R14a · el status solo puede ser uno de los que el registro ENTIENDE ─
    # Cada uno cambia lo que el registro hace, así que un valor desconocido no es una
    # etiqueta libre: es una norma que se comporta de forma imprevista. Y la caducidad
    # solo se comprueba en las que EMITEN, así que una errata la desactivaba entera:
    # `status: vigent` + una fecha pasada cargaba y seguía emitiendo.
    status = raw.get("status")
    if status not in _STATUS:
        cerca = difflib.get_close_matches(str(status), sorted(_STATUS), n=1, cutoff=0.6)
        raise bad(f"status={status!r} desconocido{f' (¿querías decir {cerca[0]!r}?)' if cerca else ''}. "
                  f"Conocidos: {'|'.join(sorted(_STATUS))}")

    # ── R2 · caducidad (OPA-style): lo frágil expira solo ──────────────────
    expires = raw.get("expires")
    expires = date.fromisoformat(expires) if expires else None
    if weak and expires is None and status in _EMITEN:
        raise bad("certeza débil sin fecha de expiración")
    if status in _EMITEN and expires and expires < today:
        raise bad(f"norma vigente CADUCADA el {expires}: hay que re-adjudicarla")

    # ── R8 · retirar una norma es un ACTO, con motivo y sustituto ──────────
    # Sin esto, una norma retirada se queda ahí y alguien la vuelve a leer: es
    # exactamente el comentario fósil que sobrevive a su propia supersesión.
    retirement = raw.get("retirement")
    if status in {"retirada", "superseded"}:
        if not retirement or not retirement.get("reason"):
            raise bad(f"status={status} sin `retirement.reason`")
        # `replaced_by` puede ser una lista VACÍA —"no hay sustituto" es una respuesta—,
        # pero tiene que estar ESCRITA. Antes el mensaje decía justo eso y luego lo
        # rechazaba: `not []` es cierto, así que seguir la instrucción no funcionaba.
        if "replaced_by" not in retirement:
            raise bad(f"status={status} sin `retirement.replaced_by` "
                      f"(si de verdad no hay sustituto, decláralo como lista vacía)")
    elif retirement:
        raise bad("tiene `retirement` pero su status no es retirada/superseded")

    # ── R14c · BLOQUEADA: evidencia en conflicto SIN adjudicar ─────────────
    # La propiedad que §5.1 prometía y no existía: una norma tiene valor o está
    # explícitamente bloqueada, nunca ambigua. Bloquear es un acto y lleva motivo,
    # igual que retirar; resolverla FALLA en vez de emitir un valor que nadie ha
    # adjudicado.
    blocking = raw.get("blocking")
    if status == "bloqueada":
        if not blocking or not blocking.get("reason"):
            raise bad("status=bloqueada sin `blocking.reason`: bloquear es un acto y "
                      "hay que decir qué conflicto lo motiva")
    elif blocking:
        raise bad("tiene `blocking` pero su status no es bloqueada")

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

    # ── v0.9.0 · la forma CONSTANTE: un valor sin ramas ────────────────────
    # Medido en el primer inquilino: **el 54 % de las normas no ramifica por nada** — son
    # un número con procedencia y caducidad, escrito con la ceremonia de una rama
    # `{sex: any}` cuya dimensión el autor elegía a capricho (`sex` ×18, `event` ×12,
    # `modality` ×8: si el eje llevara información no se podría elegir así).
    #
    # El molde hace TRES cosas —ramificar por el sujeto, declarar procedencia, y caducar—
    # y **solo la primera exige un sujeto**. Acopladas, un proyecto que quiera procedencia
    # y caducidad sin ramificación paga una rama vacía. Aquí se separan.
    #
    # Se implementa sintetizando la rama, no salteándola: así R4, R15b y el resto siguen
    # mirando exactamente lo mismo, y esta forma no abre una puerta de atrás.
    constante = "value" in raw or "evidence" in raw
    if constante and raw.get("branches"):
        raise bad("tiene `value`/`evidence` en la norma Y `branches`: o es una constante o "
                  "ramifica, no las dos. Si la rama no discrimina nada, quita el `when`")
    if constante:
        raw = dict(raw, branches=[{"value": raw.get("value"), "evidence": raw.get("evidence"),
                                   "note": raw.get("note")}])

    branches: list[Branch] = []
    for i, b in enumerate(raw.get("branches") or []):
        _check_keys(b, _BRANCH_KEYS, f"rama #{i}", bad)
        # `when: {}` explícito NO es la forma constante: es una rama que no discrimina, y
        # R16d no la ve (filtra con `if b.when`), así que DOS de ellas cargaban y ganaba la
        # última del fichero — el bug que R16d existe para cerrar, en la forma que esta
        # versión vuelve canónica. Verificado en vivo antes de cerrarlo (55.0 y 99.0 → 99.0).
        if "when" in b and not b["when"]:
            raise bad(f"rama #{i} con `when` vacío: no discrimina nada y dos así se pisan en "
                      f"silencio. Si es una constante, quita `branches` y pon `value` en la norma")
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
        raise bad("sin ramas y sin `value`: una norma sin valor no es una norma. Si es una constante, declara `value` (y su `evidence` o su `provenance_note`) en la norma")

    # ── R15b · la certeza NO puede superar a la de su evidencia ────────────
    # Hasta la v0.6.0 la certeza era AUTODECLARADA y no estaba anclada a nada, así que R1
    # —"nada vinculante con certeza débil"— se saltaba escribiendo `alta` a mano. Toda la
    # escala era decorativa. Ahora una norma no puede afirmar más de lo que sostiene su
    # mejor fuente. Solo se comprueba si el consumidor declara dónde vive la certeza de su
    # evidencia: el nombre del campo es suyo, no del registro.
    campo = schema.evidence_certainty_field
    if campo and not unsupported:
        citadas = {i for b in branches for i in b.evidence}
        certezas = [known_evidence[i][campo] for i in citadas
                    if i in known_evidence and campo in known_evidence[i]]
        if certezas:
            mejor = min(certezas, key=schema.rank)
            if schema.rank(certainty) < schema.rank(mejor):
                raise bad(
                    f"declara certainty={certainty!r} pero la MEJOR evidencia que cita es "
                    f"{mejor!r}. La certeza no es una etiqueta libre: es lo que decide si "
                    f"algo puede ser vinculante, así que no puede afirmar más de lo que la "
                    f"fuente sostiene")

    # ── R10 + R12 · dos ramas no pueden matchear al mismo sujeto ───────────
    # Si dos ramas solapan, gana la primera del fichero: el ORDEN decide el valor,
    # que es justo lo que el límite de expresividad prohíbe. La rama del sujeto
    # desconocido queda fuera de la comprobación — solapa por definición, y el
    # motor la prueba SIEMPRE la última (orden fijo del motor, no del fichero).
    #
    # v0.3.0 (R12): antes esto comparaba CONJUNTOS de pares (igualdad y subsunción), y
    # por eso no veía los rangos: ">=40" y ">=60" son literales distintos, así que
    # convivían — y un sujeto de 70 se llevaba el valor de la primera rama del fichero,
    # en silencio. Ahora se pregunta lo que de verdad importa: ¿existe algún sujeto que
    # cumpla las dos ramas a la vez? Dos condiciones sobre dimensiones DISTINTAS no se
    # estorban; el choque solo puede venir de las claves compartidas.
    # Una norma BLOQUEADA queda fuera: sus ramas SON las candidatas en conflicto, así que
    # solapan por definición. Exigirle ramas disjuntas sería pedirle que estuviera
    # adjudicada, que es justo lo que declara no estar. Y no hay riesgo de que el orden
    # decida nada, porque no emite: resolverla falla.
    comodines = [b for b in branches
                 if b.when and all(str(v).lower() in schema.wildcards for v in b.when.values())]
    if len(comodines) > 1 and status != "bloqueada":
        # R16d · punto ciego creado por la propia R10: excluye las ramas todo-comodín
        # "porque solapan por definición", lo cual es correcto para UNA y deja pasar DOS.
        # Con dos, el motor sobrescribe `fallback` y gana la ÚLTIMA del fichero — o sea que
        # el ORDEN decide el valor, justo donde la regla que lo impide decidió no mirar.
        # Las bloqueadas quedan fuera: sus ramas SON las candidatas en conflicto.
        raise bad(f"{len(comodines)} ramas del sujeto desconocido ({[b.value for b in comodines]}): "
                  f"solo puede haber UNA, porque si no gana la última del fichero y el orden "
                  f"decide el valor")

    concretas = [] if status == "bloqueada" else [
        b for b in branches
        if not all(str(v).lower() in schema.wildcards for v in b.when.values())]
    for i, a in enumerate(concretas):
        for c in concretas[i + 1:]:
            comunes = set(a.when) & set(c.when)
            if all(_conditions_compatible(a.when[k], c.when[k], schema.wildcards)
                   for k in comunes):
                raise bad(f"dos ramas matchean al mismo sujeto ({a.when} y {c.when}): "
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
                retirement=retirement, provenance_note=raw.get("provenance_note"),
                constant=constante,
                blocking=blocking, precaution=precaution)


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
        ev_raw = yaml.safe_load(_p(evidence_path, "evidence.yaml").read_text("utf-8")) or []

        # ── R13 aplicado a la EVIDENCIA (v0.9.0) — el cuarto sitio, y el peor ──
        # Aquí NO se puede cerrar el vocabulario: los campos de la evidencia son del
        # consumidor (§5.25, y es lo que mantiene esto agnóstico). Pero eso no obliga a
        # tragarse una ERRATA. Un `certza` o un `verifed` no es vocabulario propio: es un
        # campo declarado escrito mal, y el efecto es que la comprobación que depende de
        # él **se apaga sin avisar** — en el único sitio donde eso significa que algo
        # parece comprobado y no lo está.
        # Solo se queja de lo que se PARECE a un campo declarado: un nombre nuevo pasa.
        _conocidas = {"id"} | {c for c in (schema.evidence_certainty_field,
                                           schema.evidence_year_field,
                                           schema.evidence_recent_field) if c}
        erratas = []
        for e in ev_raw:
            for k in e:
                if k in _conocidas:
                    continue
                cerca = difflib.get_close_matches(str(k), sorted(_conocidas), n=1, cutoff=0.7)
                if cerca:
                    erratas.append(f"{e.get('id', '?')}: '{k}' (¿'{cerca[0]}'?)")
        if erratas:
            raise NormError(
                f"claves de evidencia que parecen una errata: {'; '.join(erratas)}. Un campo "
                f"declarado escrito mal no da error — apaga en silencio la regla que lo usa. "
                f"Si el nombre es intencionado y no un typo, decláralo en schema.yaml")

        # ── R15a · los ids de la evidencia son ÚNICOS ──────────────────────
        # Antes esto era un `set` a secas, así que dos entradas DISTINTAS con el mismo id
        # colapsaban en silencio y nadie sabía cuál estaba citando una norma. Es la
        # colisión de identificadores que este registro persigue, en la capa que se
        # suponía append-only — donde además nunca se borra, así que el choque es para
        # siempre.
        vistos: set[str] = set()
        repetidos = sorted({e["id"] for e in ev_raw if e["id"] in vistos or vistos.add(e["id"])})
        if repetidos:
            raise NormError(
                f"ids de evidencia repetidos: {repetidos}. Dos entradas con el mismo id "
                f"colapsan y nadie puede saber cuál cita una norma")

        evidencia = {e["id"]: e for e in ev_raw}

        # ── R17 (v0.8.0) · una afirmación `sin_respaldo` NO es evidencia ────
        # El registro las aceptaba y luego reventaba en la NORMA que las citara, con un
        # mensaje que culpaba a la norma: si cita evidencia no puede declararse
        # `sin_respaldo` (R4), y si declara más se salta R15b. No hay salida — la entrada
        # era inutilizable por construcción y nadie lo decía. El sitio de la queja es
        # aquí, donde está el error.
        if schema.evidence_certainty_field and schema.unsupported_level:
            campo = schema.evidence_certainty_field
            huecas = sorted(i for i, e in evidencia.items()
                            if e.get(campo) == schema.unsupported_level)
            if huecas:
                raise NormError(
                    f"evidencia con {campo}={schema.unsupported_level}: {huecas}. Una "
                    f"afirmación que no respalda nada no es evidencia — ninguna norma puede "
                    f"citarla sin romper una regla u otra. Si el número no tiene fuente, la "
                    f"norma va con certainty={schema.unsupported_level} y `provenance_note`, "
                    f"SIN entrada de evidencia")

        # ── R15c · las marcas de recencia no mienten ───────────────────────
        # Un clásico se puede citar; lo que no se puede es citarlo sin marcarlo. Solo se
        # comprueba si el consumidor declara los campos y el horizonte: qué cuenta como
        # reciente es su criterio, no del registro.
        if schema.evidence_year_field and schema.evidence_recent_field and schema.recency_horizon:
            mal = [i for i, e in evidencia.items()
                   if schema.evidence_year_field in e and schema.evidence_recent_field in e
                   and bool(e[schema.evidence_recent_field])
                   != (e[schema.evidence_year_field] >= schema.recency_horizon)]
            if mal:
                raise NormError(
                    f"evidencia con la marca de recencia incoherente con su año "
                    f"(horizonte {schema.recency_horizon}): {sorted(mal)}")


        norms: dict[str, Norm] = {}
        for raw in yaml.safe_load(_p(norms_path, "norms.yaml").read_text("utf-8")) or []:
            n = _parse_norm(raw, evidencia, today, schema)
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

        # ── R14b · los punteros apuntan a algo que EXISTE ──────────────────
        # `replaced_by` no se validaba, y el daño no era pasivo: `RetiredNormError`
        # compone su mensaje con el puntero y se lo enseña al desarrollador como si
        # fuera ayuda ("→ usa: norma_que_no_existe"). Es el puntero colgante que este
        # registro existe para impedir, cometido dentro del propio registro.
        for slug, n in norms.items():
            colgantes = [s for s in (n.retirement or {}).get("replaced_by", [])
                         if s not in norms]
            if colgantes:
                raise NormError(
                    f"[{slug}] `retirement.replaced_by` apunta a normas que no existen: "
                    f"{colgantes}. El mensaje de retirada manda al lector justo ahí, así que "
                    f"un puntero roto aquí no es un detalle: es una instrucción falsa")
        return cls(norms, schema)

    def resolve(self, slug: str, **subject: str) -> Resolution:
        """Devuelve valor + procedencia para ESTE sujeto. No ejecuta lógica."""
        norm = self._norms.get(slug)
        if norm is None:
            raise NormError(f"norma inexistente: {slug}")

        # ── R16a · el que PREGUNTA tampoco puede inventarse dimensiones ─
        # R11 protege lo que se escribe en el fichero; esto protege la llamada, que es la
        # otra mitad del contrato y estaba sin cubrir. Una errata aquí se ignoraba en
        # silencio y caía al comodín, devolviendo un valor plausible que no era el pedido
        # — y no siempre hacia el lado seguro: en una norma de bandas, el comodín significa
        # "no hay dato", así que la errata convierte una señal real en silencio.
        inventadas = sorted(set(subject) - self._schema.subject_dimensions)
        if inventadas:
            pistas = [f"'{k}'" + (f" (¿querías decir '{c[0]}'?)" if (c := difflib.get_close_matches(
                k, sorted(self._schema.subject_dimensions), n=1, cutoff=0.7)) else "")
                for k in inventadas]
            raise NormError(
                f"[{slug}] la consulta usa dimensiones no declaradas: {', '.join(pistas)}. "
                f"Se ignoraban en silencio y la respuesta caía al comodín")
        if norm.blocking:
            raise BlockedNormError(
                f"[{slug}] BLOQUEADA: hay evidencia en conflicto sin adjudicar, así que el "
                f"registro NO emite valor. Motivo: "
                f"{' '.join(str(norm.blocking['reason']).split())[:200]}")
        if norm.retirement:
            rep = ", ".join(norm.retirement.get("replaced_by") or []) or "(sin sustituto)"
            raise RetiredNormError(
                f"[{slug}] RETIRADA el {norm.retirement.get('date')} → usa: {rep}. "
                f"Motivo: {' '.join(str(norm.retirement['reason']).split())[:160]}")

        # `requires` no cubierto ⇒ dato ausente. No se adivina: se va a la rama por
        # defecto y se DECLARA (`missing`), para que el motor pueda decirlo al usuario.
        # R16b · AUSENTE no es lo mismo que CERO. Antes esto era `not subject.get(r)`, así
        # que un 0, un False o una cadena vacía contaban como "no me lo has dado". Para la
        # edad coincidía con la guarda del propio código y no mordía — por suerte, no por
        # diseño: en cualquier dimensión donde el cero signifique algo, mentía.
        missing = tuple(r for r in norm.requires if subject.get(r) is None)

        # v0.9.0 · una CONSTANTE no tiene sujeto que desconocer. Sin este atajo su única
        # rama (sintetizada, `when` vacío) satisfaría el `all()` de abajo y saldría marcada
        # `is_fallback=True` — o sea, el registro diría "he aplicado la rama del sujeto
        # desconocido" del 54 % de las normas, y `__str__` imprimiría "(rama por defecto)"
        # para todas. Es la diferencia entre "no te conozco" y "aquí no hay a quién conocer".
        if norm.constant:
            return self._mk(norm, norm.branches[0], is_fallback=False, missing=missing)

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
        # R16c · se entrega una COPIA, no las tripas. Antes `value` y `matched` eran
        # referencias a lo que vive dentro del registro, así que un `.append()` de quien
        # preguntaba cambiaba la norma para todos los demás. Era la negación literal de
        # "solo hay una copia", que es la tesis entera de esta capa.
        return Resolution(slug=norm.slug, value=deepcopy(b.value), unit=norm.unit,
                          semantics=norm.semantics, matched=dict(b.when), evidence=b.evidence,
                          strength=norm.strength, certainty=norm.certainty,
                          is_fallback=is_fallback, missing=missing)
