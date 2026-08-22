"""`init` — genera los tres YAML de un registro nuevo, comentados y VÁLIDOS.

## La propiedad que lo hace útil o inútil

**Lo que genera tiene que pasar `validate` y cargar con `NormRegistry.load()` tal cual.** Un
generador cuya salida no valida es peor que no tenerlo: la primera experiencia del adoptante sería un
error en un fichero que le acaba de dar el propio paquete, y a partir de ahí no sabe si el problema
es suyo o del ejemplo. Hay un test que lo fija y es el único que no se puede relajar.

## Por qué un ejemplo que FUNCIONA y no un andamio vacío

El adoptante declarado es una sesión de agente sin contexto, y su interfaz son los mensajes de error
y el README. Un `norms.yaml` vacío pasa la validación y no enseña nada; un ejemplo mínimo que
**carga y resuelve** enseña las dos formas que existen —constante y ramificada— y se puede borrar
cuando ya no hace falta.

Se generan las dos a propósito: con una sola, la primera norma real que ramifique se escribe
adivinando.

## Y lo que NO hace

- **No trae dominio de nadie.** Los ejemplos son deliberadamente genéricos (`ejemplo_*`): el paquete
  es agnóstico y meter aquí umbrales de nutrición o de entrenamiento sería atarlo a su primer
  inquilino.
- **No sobreescribe.** Si ya hay ficheros, sale con `2` y no toca nada — pisar el registro de alguien
  es el único fallo de esta herramienta que no se puede deshacer con un `git checkout` si no estaba
  commiteado.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

LIMPIO, PROBLEMAS, ERROR = 0, 1, 2

FICHEROS = ("schema.yaml", "evidence.yaml", "norms.yaml")

# El molde lleva este token donde va la caducidad del ejemplo; `generar` lo sustituye por una fecha
# CALCULADA en el momento de escribir (ver `_expires_ejemplo`). No se puede usar `str.format` porque
# el molde de `norms.yaml` tiene llaves literales (`{grupo: any}`), así que se sustituye por texto.
# Es un valor a propósito INVÁLIDO como fecha: si la sustitución fallara, el YAML no cargaría —
# ruidoso — en vez de escribir un `expires` erróneo en silencio.
_EXPIRES_TOKEN = "__EXPIRES_EJEMPLO__"


def _expires_ejemplo(hoy: date | None = None) -> str:
    """Fecha de caducidad del ejemplo, ANCLADA a la generación en vez de cableada.

    Un literal envejece solo: el `2027-12-31` que traía antes hacía que, a partir de esa fecha,
    `init` generara un registro que `load()` RECHAZA (`R2`, registry.py:464) — el adoptante recibe
    un error en su primer minuto, dentro de un fichero que le acaba de dar el paquete. Se calcula
    a ~3-4 años vista (31-dic de `año+3`) para que lo generado cargue el día que se genera, siempre.
    """
    hoy = hoy or date.today()
    return date(hoy.year + 3, 12, 31).isoformat()

SCHEMA = """\
# ═══ ESQUEMA — lo que ENCIENDE Y APAGA las reglas del registro ════════════════
#
# ⚠️ Este fichero decide qué comprobaciones existen. Una errata de una letra en un nombre de campo
# APAGA la regla que depende de él, así que el registro valida sus propias claves y no arranca si
# encuentra una desconocida. Es deliberado: la puerta blindada no sirve con la ventana abierta.

# La escala de certeza, DE MÁS a MENOS. El orden importa: es lo que permite decir «esta norma
# afirma más de lo que su fuente sostiene».
certainty_scale: [alta, moderada, baja, muy_baja, sin_respaldo]

# Desde qué nivel la certeza se considera DÉBIL. Una norma débil está obligada a caducar (`expires`)
# y no puede ser `vinculante`. Cambiar esto relaja el registro entero.
weak_from: baja

# El nivel que significa «no hay fuente». Una norma así NO puede citar evidencia: va con
# `provenance_note` explicando de dónde sale el número. Y una entrada de evidencia no puede
# declararse en este nivel — una afirmación que no respalda nada no es evidencia.
unsupported_level: sin_respaldo

# Valores que significan «cualquiera» en un `when`. La rama comodín es la respuesta a «no te
# conozco», y tenerla declarada es lo que impide que sea un default escondido.
wildcards: [unknown, any]

# ── Los campos de TU evidencia ────────────────────────────────────────────────
# El paquete no impone la forma de tus entradas de evidencia: solo necesita saber CÓMO SE LLAMAN
# los tres campos de los que dependen sus comprobaciones. Si no declaras uno, la regla que lo usa
# simplemente no existe — y eso es una decisión tuya, no un descuido silencioso.
evidence_certainty_field: certeza     # de él sale «una norma no puede afirmar más que su fuente»
evidence_year_field: anio             # con el horizonte de abajo, «un clásico se marca como tal»
evidence_recent_field: reciente
recency_horizon: 2018                 # a partir de aquí una fuente cuenta como reciente

# ── La lista CERRADA de atributos del SUJETO por los que se puede ramificar ───
# ⚠️ ESTA LISTA ES LO QUE IMPIDE ENCADENAR NORMAS. Sin ella, un `when: {otra_norma: ">=0.30"}` es
# un rango bien formado y pasaría — una norma referenciando a otra, que es exactamente donde
# fracasan los motores de reglas. Aquí la composición vive en TU código, donde se puede depurar.
#
# Añadir una dimensión es barato y queda en el diff. Lo que no se puede es inventarla al vuelo
# dentro de una rama.
#
# Sustituye estas por las tuyas: son la unión de las claves `when` de tus normas.
subject_dimensions:
  - grupo        # ejemplo: el atributo por el que ramifica la norma de abajo
"""

EVIDENCIA = """\
# ═══ EVIDENCIA — las AFIRMACIONES que respaldan los números ═══════════════════
#
# Una entrada por afirmación, NO por documento: si un mismo paper sostiene dos cosas distintas,
# van en dos entradas. Una norma que cite «el paper» sin decir cuál de sus frases la sostiene es
# cómo una afirmación se aleja de su fuente.
#
# ⚠️ El `claim` es lo que hace falsable la entrada. Escribe lo que la fuente DICE, lo más cerca del
# original que puedas — no lo que tú concluyes de ella. La diferencia entre «X reduce Y» y «X
# reduce Y un 15 %» es la que decide si tu número tiene respaldo o solo tiene una cita al lado.
#
# Y esta capa es append-only en la práctica: los ids no se reutilizan nunca, porque una norma
# vieja puede seguir citándolos.

- id: EV-0001
  cita: "Autor A, Autor B. Título del trabajo. Revista 2021;10(2):100-110 (PMID 00000000)"
  claim: "Lo que la fuente dice LITERALMENTE, no lo que se deduce de ella"
  certeza: moderada
  anio: 2021
  reciente: true
  nota: "Para lo que la fuente NO dice y conviene no olvidar: tamaño de muestra, población que no
         cubre, o qué parte del número es interpretación tuya."
"""

NORMAS = """\
# ═══ NORMAS — los números que gobiernan tu código ═════════════════════════════
#
# Dos formas, y las dos están abajo a propósito: con una sola, la primera norma real que ramifique
# se escribe adivinando.
#
#   · CONSTANTE   — un `value`. La mayoría de las normas son esto.
#   · RAMIFICADA  — `branches` con un `when` por atributo del sujeto.
#
# Borra las dos cuando tengas las tuyas. Están aquí para que el registro CARGUE desde el primer
# minuto y para enseñar la forma, no como contenido.

# ── 1) Una norma CONSTANTE, con evidencia ────────────────────────────────────
- slug: ejemplo_umbral
  title: Ejemplo de norma con una fuente detrás
  status: vigente              # vigente | bloqueada | retirada
  strength: condicional        # condicional | precautorio | vinculante
  certainty: moderada          # tiene que ser <= la de la MEJOR evidencia que cita
  unit: unidades de lo que sea # ⚠️ ESCRÍBELA BIEN: una unidad mal puesta es peor que ninguna,
                               # porque invita a razonar sobre una aritmética que no ocurre

  value: 10.0
  evidence: [EV-0001]
  note: "para el matiz que hace falta al leer el valor: qué parte sale de la fuente y qué parte
         es una elección dentro de lo que la fuente permite"
  semantics: umbral            # vocabulario LIBRE y tuyo (umbral, suelo, techo, dosis, factor…).
                               # No lo lee el código: lo leen las personas y los detectores que
                               # comparan el nombre de una constante con lo que la norma dice ser.
  expires: "__EXPIRES_EJEMPLO__"  # ⚠️ OBLIGATORIA si la certeza es débil, y con motivo: lo frágil
                               # tiene que volver a mirarse. Cuando esta fecha pase, `load()`
                               # LANZARÁ y tu aplicación no arrancará — usa
                               # `capa-normativa-validate --avisa-en 90` para enterarte ANTES.

# ── 2) Una norma RAMIFICADA por un atributo del sujeto ───────────────────────
- slug: ejemplo_por_grupo
  title: Ejemplo de norma que depende de a quién se aplica
  status: vigente
  strength: condicional
  certainty: sin_respaldo      # sin fuente: se declara así y se explica abajo

  provenance_note: >
    NÚMERO DE LA CASA. Cuando no hay fuente, esto es lo que sustituye a la evidencia: de dónde
    salió, quién lo decidió y qué pasa si se cambia. Un número sin fuente es aceptable; uno sin
    explicación no, porque nadie podrá discutirlo después.
  unit: unidades

  branches:
    # Las ramas se resuelven por PRIMERA COINCIDENCIA, así que el orden importa: lo específico va
    # antes que el comodín.
    - when: {grupo: especifico}
      value: 20.0
      note: "por qué este grupo tiene un valor propio"
    - when: {grupo: any}
      value: 15.0
      note: "la rama COMODÍN es la respuesta a «no te conozco», y tenerla explícita es lo que
             impide que sea un default escondido. Si para un sujeto desconocido no debe gobernar
             nada, pon `value: null` — eso significa «aquí esta norma no manda», que es distinto
             de «no lo sé»"

  semantics: umbral
  expires: "__EXPIRES_EJEMPLO__"
"""

CONTENIDO = {"schema.yaml": SCHEMA, "evidence.yaml": EVIDENCIA, "norms.yaml": NORMAS}


def generar(destino: Path | str, *, forzar: bool = False) -> list[Path]:
    """Escribe los tres YAML en `destino`. Devuelve las rutas escritas.

    Si alguno existe y `forzar` es falso, **no escribe ninguno** y lanza `FileExistsError`. Es
    todo-o-nada a propósito: dejar un registro medio sobrescrito es peor que no haber tocado nada.
    """
    d = Path(destino)
    d.mkdir(parents=True, exist_ok=True)
    if not forzar:
        ya = [f for f in FICHEROS if (d / f).exists()]
        if ya:
            raise FileExistsError(
                f"ya existen en {d}: {', '.join(ya)}. No se ha tocado NADA — pisar el registro de "
                f"alguien es el único fallo de esta herramienta que no se deshace. Usa otro "
                f"directorio, o `--forzar` si de verdad quieres sobreescribir.")
    fecha = _expires_ejemplo()
    escritos = []
    for f in FICHEROS:
        (d / f).write_text(CONTENIDO[f].replace(_EXPIRES_TOKEN, fecha), encoding="utf-8")
        escritos.append(d / f)
    return escritos


def main(argv: list[str] | None = None) -> int:
    """`0` generado · `1` no se generó (ya existía) · `2` no se pudo ejecutar."""
    p = argparse.ArgumentParser(
        prog="capa-normativa-init",
        description="Genera los tres YAML de un registro nuevo, comentados y válidos.")
    p.add_argument("destino", help="directorio donde escribirlos (se crea si no existe)")
    p.add_argument("--forzar", action="store_true",
                   help="sobreescribir si ya existen. Por defecto NO se toca nada.")
    args = p.parse_args(argv)

    try:
        escritos = generar(args.destino, forzar=args.forzar)
    except FileExistsError as e:
        print(f"error: {e}", file=sys.stderr)
        return PROBLEMAS
    except OSError as e:
        print(f"error: no se pudo escribir: {e}", file=sys.stderr)
        return ERROR

    for f in escritos:
        print(f"  escrito  {f}")
    print(f"\n✓ registro de ejemplo en {args.destino}. Carga y resuelve tal cual:\n")
    print("    from capa_normativa import NormRegistry")
    print(f'    NORMS = NormRegistry.load("{args.destino}")')
    print('    NORMS.resolve("ejemplo_umbral").value           # 10.0')
    print('    NORMS.resolve("ejemplo_por_grupo", grupo="").value   # 15.0 (la rama comodín)')
    print(f"\n  Compruébalo:  capa-normativa-validate {args.destino}")
    print("  Y borra las dos normas de ejemplo cuando tengas las tuyas.")
    return LIMPIO


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
