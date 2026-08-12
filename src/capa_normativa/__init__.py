"""capa_normativa — conocimiento externo que gobierna código, como datos verificables.

El código no contiene los números: se los pide al registro, que devuelve el valor
JUNTO A SU PROCEDENCIA. Una norma mal formada no se construye, y si el registro no
se construye, el programa no arranca.

Uso mínimo:

    from capa_normativa import NormRegistry

    NORMS = NormRegistry.load(Path("norms/"))          # falla si algo está mal
    r = NORMS.resolve("mi_umbral", kind="alpha")
    r.value, r.evidence, r.certainty, r.is_fallback

Lo que este registro NO hace, a propósito: no ejecuta lógica y no encadena normas.
Es lo que lo separa de un motor de reglas — el patrón donde estos sistemas fracasan.
"""
from .registry import (
    BlockedNormError,
    Branch,
    Norm,
    NormError,
    NormRegistry,
    Resolution,
    RetiredNormError,
    Schema,
)

__version__ = "0.12.0"
__all__ = ["NormRegistry", "Norm", "Branch", "Resolution", "Schema",
           "NormError", "RetiredNormError", "BlockedNormError"]
