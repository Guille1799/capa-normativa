"""`validate` — comprueba un registro SIN arrancar la aplicación, y avisa de lo que va a caducar.

## Por qué existe, y por qué no es `load()` con otro nombre

`NormRegistry.load()` ya es fail-fast: cualquier estado ilegal lanza y el programa no arranca. Eso
es correcto en RUNTIME —un registro roto no debe gobernar nada— pero deja dos huecos que este
módulo cubre, y ninguno es cosmético.

### ① El registro CADUCADO es una caída de producción, y nada la anuncia

`registry.py:464`: una norma `vigente` cuya `expires` ya pasó **hace que `load()` lance**. O sea que
el día que caduca, **la aplicación no arranca**.

Ese diseño es deliberado y bueno —es la mitad «niégate a servir lo rancio» del modelo gettext— pero
sin un aviso previo es una mina: el mecanismo que protege de la información vieja se manifiesta como
un despliegue que falla un martes por la mañana, sin relación aparente con nada que se haya tocado.

**`validate --avisa-en N` es la otra mitad.** Contesta «qué caduca en los próximos N días» ANTES de
que lo haga, que es lo único que convierte la caducidad en un mecanismo utilizable en vez de un
sobresalto.

### ② `load()` para en el PRIMER error; quien escribe YAML quiere los siete

Mismo reparto que entre el registro y el vigilante, y por el mismo motivo: el registro **para**
porque su trabajo es no arrancar; esto **enumera** porque su trabajo es que alguien arregle un
fichero. Siete errores en siete corridas son seis viajes de más.

Se enumeran los errores POR NORMA, que son independientes entre sí. Los de `schema.yaml` y de la
evidencia **no se enumeran a propósito**: todo lo demás depende de ellos, así que seguir tras un
esquema roto produciría una cascada de errores derivados que ocultaría el único que importa.

⚠️ **Y NO se reimplementa ninguna comprobación.** Se llama al mismo `_parse_norm` que usa `load()`.
Dos validadores que se pretenden equivalentes divergen —es cuestión de tiempo— y entonces `validate`
diría verde sobre un registro que no arranca, que es peor que no tenerlo.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yaml

from .registry import _EMITEN, NormError, NormRegistry, Schema, _parse_norm

LIMPIO, PROBLEMAS, ERROR = 0, 1, 2


@dataclass
class Informe:
    """Lo que `validate` sabe del registro. `ok` es el veredicto; el resto, para leerlo."""

    errores: list[str] = field(default_factory=list)
    #: (slug, fecha, status) de normas ya vencidas que **NO EMITEN** — retiradas, superseded,
    #: bloqueadas. Se reportan porque una fecha muerta en el YAML miente a quien la lee, pero
    #: **no deciden nada**: sin emisión, caducar no significa nada (`registry.py:378`).
    #:
    #: El nombre lleva `_inertes` porque el anterior (`caducadas`) no decía cuál era, su
    #: docstring afirmaba lo contrario de su comentario, y `--falla-si-caduca-en` acabó cableado
    #: a él: gate ROJO por una norma que por construcción no puede romper nada (pasó el
    #: 2026-08-13 con `long_run_share_cap` en un inquilino real). Un nombre que no distingue
    #: acaba conectado al revés — así que ahora lo distingue.
    #:
    #: Una que EMITA no puede aparecer aquí: si una `vigente` hubiera vencido, `load()` habría
    #: lanzado y esto sería un `errores`, no un aviso. Por eso NO hay un campo hermano
    #: `caducadas_que_emiten`: sería un campo estructuralmente imposible de rellenar.
    caducadas_inertes: list[tuple[str, date, str]] = field(default_factory=list)
    #: (slug, fecha, días) de las que EMITEN y caducan dentro del horizonte de aviso. Solo las
    #: que emiten: es la lista que decide el gate, y en las demás caducar no cuenta.
    caducan_pronto: list[tuple[str, date, int]] = field(default_factory=list)
    total: int = 0
    por_certeza: dict[str, int] = field(default_factory=dict)
    por_estado: dict[str, int] = field(default_factory=dict)
    sin_fecha: int = 0

    @property
    def ok(self) -> bool:
        return not self.errores


def _cuenta(valores) -> dict[str, int]:
    fuera: dict[str, int] = {}
    for v in valores:
        fuera[str(v)] = fuera.get(str(v), 0) + 1
    return dict(sorted(fuera.items()))


def validar(base_dir: Path | str, *, hoy: date | None = None,
            avisa_en: int = 60) -> Informe:
    """Valida el registro de `base_dir` y devuelve un `Informe`.

    `avisa_en`: horizonte en días para «esto va a caducar». No afecta al veredicto — caducar todavía
    no es un error, y confundir «roto» con «va a romperse» es lo que hace que la gente apague los
    avisos.
    """
    base = Path(base_dir)
    hoy = hoy or date.today()
    inf = Informe()

    for nombre in ("schema.yaml", "evidence.yaml", "norms.yaml"):
        if not (base / nombre).exists():
            inf.errores.append(f"falta {nombre} en {base}")
    if inf.errores:
        return inf

    # ── el camino REAL primero: si el registro carga, es que carga ──
    try:
        reg = NormRegistry.load(base, today=hoy)
    except NormError as e:
        inf.errores.append(str(e))
        # Y ahora se intenta ENUMERAR el resto, por norma. Si el esquema o la evidencia son lo
        # roto, esto no llega a nada y el único error sigue siendo el de arriba — que es lo
        # correcto: no hay nada útil que decir sobre normas cuyo esquema no se pudo leer.
        try:
            esquema = Schema.load(base / "schema.yaml")
            ev = {e_["id"]: e_ for e_ in (yaml.safe_load((base / "evidence.yaml")
                                                         .read_text("utf-8")) or [])}
            crudas = yaml.safe_load((base / "norms.yaml").read_text("utf-8")) or []
        except Exception:
            return inf
        primero = inf.errores[0]
        for cruda in crudas:
            try:
                _parse_norm(cruda, ev, hoy, esquema)
            except NormError as e2:
                if str(e2) != primero and str(e2) not in inf.errores:
                    inf.errores.append(str(e2))
        return inf
    except Exception as e:  # noqa: BLE001 — un YAML ilegible no es un NormError
        inf.errores.append(f"no se pudo leer el registro: {type(e).__name__}: {e}")
        return inf

    # ── carga: ahora el informe de salud ──
    normas = reg.normas()
    inf.total = len(normas)
    inf.por_certeza = _cuenta(n.certainty for n in normas)
    inf.por_estado = _cuenta(n.status for n in normas)
    limite = hoy + timedelta(days=avisa_en)
    for n in normas:
        if n.expires is None:
            inf.sin_fecha += 1
            continue
        if n.status not in _EMITEN:
            # Caducar no significa NADA en una norma que no emite (`registry.py:378-380`): no se
            # resuelve, no emite valor, y `load()` ni le mira la fecha. Se REPORTA si ya venció
            # —una fecha muerta miente a quien lee el YAML— pero ni entra en el aviso ni decide
            # el gate. Y se pregunta por `_EMITEN`, no por `status == "vigente"`, por lo mismo
            # que el módulo entero no reimplementa nada: si el registro cambiara qué emite, esto
            # cambiaría con él en vez de quedarse con una copia que ya no es verdad.
            if n.expires < hoy:
                inf.caducadas_inertes.append((n.slug, n.expires, n.status))
            continue
        if n.expires < hoy:
            # No debería poder pasar: `load()` ya habría lanzado (`registry.py:464`) y `validar`
            # habría vuelto arriba con el error. Se comprueba igual, y como ERROR y no como
            # aviso: si el registro y este módulo divergieran, el único fallo que este módulo no
            # puede permitirse es decir VERDE sobre un registro que no arranca.
            inf.errores.append(f"{n.slug}: norma vigente CADUCADA el {n.expires}: "
                               f"hay que re-adjudicarla")
        elif n.expires <= limite:
            inf.caducan_pronto.append((n.slug, n.expires, (n.expires - hoy).days))
    inf.caducan_pronto.sort(key=lambda t: t[1])
    return inf


def _imprime(inf: Informe, base: Path, avisa_en: int) -> None:
    if inf.errores:
        print(f"✗ {base}: {len(inf.errores)} problema(s)\n", file=sys.stderr)
        for i, e in enumerate(inf.errores, 1):
            print(f"  {i}. {e}\n", file=sys.stderr)
        print("  El registro NO arrancaría con estos errores. Cada mensaje dice qué hacer.\n",
              file=sys.stderr)
        return

    print(f"✓ {base}: {inf.total} normas, el registro carga.")
    print(f"    estados:  {', '.join(f'{k}={v}' for k, v in inf.por_estado.items())}")
    print(f"    certezas: {', '.join(f'{k}={v}' for k, v in inf.por_certeza.items())}")
    if inf.sin_fecha:
        print(f"    sin `expires`: {inf.sin_fecha} (permitido solo si su certeza no es débil)")

    if inf.caducadas_inertes:
        print(f"\n  ⚠ {len(inf.caducadas_inertes)} CADUCADAS pero INERTES "
              f"(no emiten: ni rompen ni fallan el gate — pero mienten):")
        for slug, f, estado in inf.caducadas_inertes:
            print(f"      {slug} ({estado}) — venció el {f}")
        print("     En una que no emite, la fecha que manda es la de `retirement`/`blocking`.")
        print("     Quítale el `expires`: ahí no gobierna nada y duplica una fecha que sí manda.")

    if inf.caducan_pronto:
        print(f"\n  ⏳ {len(inf.caducan_pronto)} caducan en los próximos {avisa_en} días.")
        print("     Cuando una norma VIGENTE caduca, `load()` lanza y la aplicación NO ARRANCA:")
        for slug, f, d in inf.caducan_pronto:
            print(f"      {d:>4}d  {slug} — {f}")
        print("     Re-adjudícalas o renuévalas ANTES de esa fecha.")
    else:
        # Decirlo, no omitirlo: una ausencia no distingue «no hay nada» de «no lo miré».
        print(f"\n  ⏳ nada caduca en los próximos {avisa_en} días.")


def main(argv: list[str] | None = None) -> int:
    """`0` válido · `1` hay problemas · `2` no se pudo ejecutar.

    Mismo contrato que el vigilante y que `emit`, y por el mismo motivo: el consumidor previsto es
    un agente sin contexto, y «falló» y «encontró cosas» exigen reacciones opuestas.
    """
    p = argparse.ArgumentParser(
        prog="capa-normativa-validate",
        description="Comprueba un registro sin arrancar la app, y avisa de lo que va a caducar.")
    p.add_argument("registro", help="directorio con schema.yaml, evidence.yaml y norms.yaml")
    p.add_argument("--avisa-en", type=int, default=60, metavar="DIAS",
                   help="horizonte del aviso de caducidad (por defecto 60)")
    p.add_argument("--falla-si-caduca-en", type=int, default=None, metavar="DIAS",
                   help="salir con 1 si algo que EMITE caduca dentro de DIAS. Para CI: convierte "
                        "el aviso en un gate ANTES de que la caducidad tire la aplicación. Las "
                        "retiradas y bloqueadas vencidas se reportan, pero no lo fallan: no "
                        "emiten, así que no pueden tirar nada.")
    p.add_argument("--json", action="store_true", help="salida JSON (para consumo por máquina)")
    args = p.parse_args(argv)

    base = Path(args.registro)
    if not base.exists():
        print(f"error: no existe: {base}", file=sys.stderr)
        return ERROR

    horizonte = max(args.avisa_en, args.falla_si_caduca_en or 0)
    try:
        inf = validar(base, avisa_en=horizonte)
    except Exception as e:  # noqa: BLE001
        print(f"error: no se pudo validar: {type(e).__name__}: {e}", file=sys.stderr)
        return ERROR

    if args.json:
        import json
        print(json.dumps({
            "ok": inf.ok,
            "errores": inf.errores,
            "total": inf.total,
            "por_estado": inf.por_estado,
            "por_certeza": inf.por_certeza,
            "sin_expires": inf.sin_fecha,
            "caducadas_inertes": [[s, f.isoformat(), e] for s, f, e in inf.caducadas_inertes],
            "caducan_pronto": [[s, f.isoformat(), d] for s, f, d in inf.caducan_pronto],
        }, ensure_ascii=False, indent=2))
    else:
        _imprime(inf, base, horizonte)

    if not inf.ok:
        return PROBLEMAS
    if args.falla_si_caduca_en is not None:
        # SOLO las que emiten. `caducan_pronto` ya no trae otra cosa, y `caducadas_inertes` no
        # entra a propósito: una retirada vencida se sigue REPORTANDO —el aviso es útil, la
        # fecha miente— pero no decide el veredicto de un gate que existe para anticipar que la
        # aplicación no arranque. Una norma que no emite no puede impedir que arranque nada.
        pronto = [t for t in inf.caducan_pronto if t[2] <= args.falla_si_caduca_en]
        if pronto:
            if not args.json:
                print(f"\n✗ --falla-si-caduca-en {args.falla_si_caduca_en}: "
                      f"{len(pronto)} norma(s) que EMITEN dentro del plazo.",
                      file=sys.stderr)
            return PROBLEMAS
    return LIMPIO


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
