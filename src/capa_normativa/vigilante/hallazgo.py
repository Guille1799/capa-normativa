"""El tipo de un hallazgo. Deliberadamente pequeño."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hallazgo:
    """Un hallazgo de un detector.

    `arreglo` no es decoración: el adoptante de esto es una sesión de agente **sin
    contexto**, así que el mensaje de error ES la interfaz. Un hallazgo que no dice qué
    hacer obliga a leer el código del detector para entenderlo.
    """

    detector: str
    codigo: str
    """Identificador estable (`PTR001`, `SYN001`). Estable = se puede silenciar y contar
    en un trinquete sin que el número baile al reformular el mensaje."""
    fichero: str
    linea: int | None
    mensaje: str
    arreglo: str

    def __str__(self) -> str:
        donde = f"{self.fichero}:{self.linea}" if self.linea else self.fichero
        return f"{donde}: [{self.codigo}] {self.mensaje}\n    → {self.arreglo}"
