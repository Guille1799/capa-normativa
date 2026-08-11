"""TRI — el trinquete: una deuda declarada que solo puede decrecer.

Generalización del patrón con el mejor historial demostrado del sistema de origen: **277 → 206
en 14 pasos fechados**. Estaba atrapado en los tests de un solo proyecto (`test_const_ratchet.py`),
acoplado a su extractor y a su vocabulario. Aquí queda el mecanismo; el extractor y el
vocabulario **siguen siendo del inquilino**, que es donde deben estar.

## Por qué el trinquete y no un gate

Un gate absoluto sale rojo el día 1 y **se desactiva**. El trinquete se calibra sobre el estado
actual y solo prohíbe empeorar, así que puede entrar en un repo con deuda sin bloquearlo. Y no
muere de fatiga: no exige atención por evento, exige que un número no suba.

## Las SEIS comprobaciones, y por qué son seis

Cada una salió de un fallo real, no de un diseño:

1. **Entradas nuevas** — la obvia.
2. **Valores cambiados** — cambiar `3.3` por `4.1` en un número sin procedencia es tan grave como
   añadir uno nuevo, y **un baseline de solo nombres lo dejaría pasar**.
3. **Entradas obsoletas** — la no obvia, y la que se descubrió tarde: una entrada que ya no existe
   en el código es un **permiso de reentrada**. Sin esta comprobación, algo migrado seguía en el
   baseline para siempre, así que **volver a escribirlo a mano no disparaba nada**: la migración se
   podía deshacer en silencio. Y de paso el contador mentía.
4. **El tope** — solo gira en un sentido.
5. **Toda entrada explica por qué sigue ahí** (`razon`). Sin esto, salir de la lista de pendientes
   es gratis, y en el proyecto de origen **108 de 206 entradas salieron sin que nadie escribiera
   por qué**.
6. **El tope flojo** — si el recuento real está por debajo del tope, el tope es decoración. Sale
   como hallazgo informativo (`TRI006`), porque la nota original del autor decía: *«Si baja, BAJA
   EL TOPE. Dejarlo alto convierte el trinquete en decoración.»*

## Lo que este módulo NO puede hacer, y hay que decirlo

Distinguir *«la deuda creció»* de *«el instrumento dejó de estar ciego»*. Pasó de verdad: el
contador subió de 277 a 279 al arreglar la ceguera del extractor al desempaquetado de tuplas, y
**279 era el primer número que no mentía**. Eso es intención, y la intención no es computable
(ley 1). Lo único que se puede hacer —y se hace— es que el mensaje **obligue a declarar cuál de
las dos cosas es**.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .hallazgo import Hallazgo


@dataclass(frozen=True)
class Entrada:
    """Una entrada del baseline. `razon` no es documentación: es el precio de seguir ahí."""

    valor: Any
    razon: str = ""
    clase: str | None = None

    @classmethod
    def desde(cls, crudo: Any) -> "Entrada":
        if isinstance(crudo, Entrada):
            return crudo
        if isinstance(crudo, Mapping):
            return cls(valor=crudo.get("value", crudo.get("valor")),
                       razon=crudo.get("reason", crudo.get("razon")) or "",
                       clase=crudo.get("clase", crudo.get("class")))
        return cls(valor=crudo)


def _comparable(v: Any) -> Any:
    """JSON no distingue tupla de lista. Sin esto, un baseline releído del disco reporta
    cambiados todos los valores que sean secuencias."""
    if isinstance(v, (list, tuple)):
        return tuple(_comparable(x) for x in v)
    if isinstance(v, Mapping):
        return tuple(sorted((k, _comparable(x)) for k, x in v.items()))
    return v


class Trinquete:
    """Compara el estado actual contra un baseline congelado y devuelve hallazgos.

    Args:
        baseline: ruta a un JSON `{clave: {value, reason, clase}}`, o el dict ya cargado.
        tope: número máximo de entradas. Solo se baja, y se baja A MANO: bajarlo es el acto
            que convierte «he limpiado algo» en una propiedad que el gate defiende a partir
            de ahora.
        vocabulario: si se da, toda entrada debe tener `clase` dentro de él. El vocabulario es
            del inquilino: este módulo no sabe qué clases tiene tu dominio.
        que_migrar_a: texto que aparece en los mensajes para decirle al que los lee **adónde**
            mover la entrada. El adoptante previsto es un agente sin contexto: un mensaje que
            no dice qué hacer obliga a leer este código para entenderlo.
    """

    def __init__(
        self,
        baseline: Path | str | Mapping[str, Any],
        *,
        tope: int,
        vocabulario: Iterable[str] | None = None,
        que_migrar_a: str = "el registro",
    ) -> None:
        if isinstance(baseline, (str, Path)):
            self.ruta: Path | None = Path(baseline)
            crudo = json.loads(self.ruta.read_text(encoding="utf-8"))
        else:
            self.ruta = None
            crudo = dict(baseline)
        self.baseline: dict[str, Entrada] = {k: Entrada.desde(v) for k, v in crudo.items()}
        self.tope = tope
        self.vocabulario = frozenset(vocabulario) if vocabulario is not None else None
        self.que_migrar_a = que_migrar_a

    # ── las seis comprobaciones ──

    def revisar(self, actual: Mapping[str, Any]) -> list[Hallazgo]:
        """Devuelve TODOS los hallazgos. No lanza en el primero: el consumidor necesita la
        lista entera de una pasada, al contrario que el registro, que es fail-fast a propósito."""
        act = {k: Entrada.desde(v) for k, v in actual.items()}
        base = self.baseline
        donde = str(self.ruta) if self.ruta else "<baseline en memoria>"
        h: list[Hallazgo] = []

        def add(codigo: str, mensaje: str, arreglo: str) -> None:
            h.append(Hallazgo(detector="trinquete", codigo=codigo, fichero=donde,
                              linea=None, mensaje=mensaje, arreglo=arreglo))

        nuevas = sorted(set(act) - set(base))
        if nuevas:
            add("TRI001",
                f"{len(nuevas)} entrada(s) nueva(s) sin declarar: "
                + ", ".join(f"{k}={act[k].valor!r}" for k in nuevas[:8])
                + ("…" if len(nuevas) > 8 else ""),
                f"Dos salidas, y la primera es la buena: (a) migrarla a {self.que_migrar_a}, "
                "con su procedencia — o declarándola sin respaldo, pero declarándolo; "
                "(b) si de verdad no procede, añadirla al baseline CON SU `reason`, que queda "
                "en el diff para que alguien pueda discutirla.")

        cambiadas = [(k, base[k].valor, act[k].valor) for k in sorted(set(act) & set(base))
                     if _comparable(base[k].valor) != _comparable(act[k].valor)]
        if cambiadas:
            add("TRI002",
                f"{len(cambiadas)} valor(es) cambiado(s) sin procedencia: "
                + ", ".join(f"{k}: {v!r}→{n!r}" for k, v, n in cambiadas[:8])
                + ("…" if len(cambiadas) > 8 else ""),
                "Cambiar un número sin respaldo es una decisión, no un ajuste. O lo migras a "
                f"{self.que_migrar_a} (que te obliga a decir por qué), o actualizas el baseline "
                "explicando el cambio en su `reason`.")

        obsoletas = sorted(set(base) - set(act))
        if obsoletas:
            add("TRI003",
                f"{len(obsoletas)} entrada(s) del baseline que ya no existen: "
                + ", ".join(obsoletas[:8]) + ("…" if len(obsoletas) > 8 else ""),
                "Una entrada obsoleta es un PERMISO DE REENTRADA, no un residuo inofensivo: "
                "mientras siga ahí, volver a escribir eso a mano no dispara nada y la limpieza "
                "se puede deshacer en silencio. Bórrala del baseline y baja el tope.")

        if len(base) > self.tope:
            add("TRI004",
                f"el baseline tiene {len(base)} entradas y el tope es {self.tope}",
                "El trinquete solo gira en un sentido. Antes de subir el tope, DECLARA cuál de "
                "las dos cosas ha pasado, porque no son lo mismo y esto no puede distinguirlas: "
                "(a) la deuda ha CRECIDO — entonces no subas el tope, arréglalo; o (b) el "
                "instrumento ha dejado de estar CIEGO y ha hecho visible deuda que ya existía — "
                "entonces súbelo y escribe por qué en el historial del tope.")

        sin_razon = sorted(k for k, e in base.items() if not (e.razon or "").strip())
        if sin_razon:
            add("TRI005",
                f"{len(sin_razon)} entrada(s) del baseline sin `reason`: "
                + ", ".join(sin_razon[:8]) + ("…" if len(sin_razon) > 8 else ""),
                "Salir de la lista de pendientes es una DECISIÓN. Sin `reason` es gratis, y "
                "gratis significa que nadie podrá discutirlo después.")

        if self.vocabulario is not None:
            sin_clase = sorted(k for k, e in base.items() if e.clase not in self.vocabulario)
            if sin_clase:
                add("TRI007",
                    f"{len(sin_clase)} entrada(s) con `clase` fuera del vocabulario: "
                    + ", ".join(sin_clase[:8]) + ("…" if len(sin_clase) > 8 else ""),
                    f"Clases admitidas: {' | '.join(sorted(self.vocabulario))}. Clasificar antes "
                    "de entrar obliga a decidir QUÉ ES la entrada, no a decidirlo después.")

        # Informativo y a propósito el último: un tope flojo no rompe nada hoy, pero convierte
        # el trinquete en decoración. El consumidor decide si lo hace fallar (filtrando por código).
        if len(base) < self.tope:
            add("TRI006",
                f"el tope está flojo: {len(base)} entradas contra un tope de {self.tope}",
                f"Bájalo a {len(base)}. Dejarlo alto deja hueco para meter deuda sin que nada "
                "se queje, y convierte el trinquete en decoración.")

        return h

    def cuenta(self) -> int:
        return len(self.baseline)
