"""Vigilante — chequeos DETERMINISTAS sobre un repo. El segundo módulo del artefacto.

Frontera con el registro: este módulo **no importa nada** de `capa_normativa.registry`.
Un test permanente lo comprueba (`test_la_frontera_entre_modulos_se_mantiene`), porque la
frontera es la decisión de arquitectura del 2026-08-09 y una decisión que no se verifica
es una decisión que deriva.

Por qué determinista y no un LLM (regla del 2026-08-08, medida): un detector que oscila es
otra respuesta viva más — empeora el problema que viene a resolver. Y sobrevive a un
downgrade de plan porque no cuesta tokens.

Contrato de salida (para el adoptante declarado: una sesión de agente sin contexto):
    0 = limpio · 1 = hay hallazgos · 2 = no se pudo ejecutar

**Enumera, no es fail-fast.** El registro lanza en el primer error porque su trabajo es no
arrancar; el vigilante tiene que poder decirte los 12 hallazgos de una pasada.
"""

from __future__ import annotations

from .hallazgo import Hallazgo
from .preguntas import revisar_preguntas
from .punteros import revisar_punteros
from .secretos import revisar_secretos
from .sintaxis import revisar_sintaxis
from .trinquete import Entrada, Trinquete

__all__ = ["Hallazgo", "revisar_preguntas", "revisar_punteros", "revisar_secretos", "revisar_sintaxis",
           "Trinquete", "Entrada", "DETECTORES"]

#: Detectores que el CLI puede correr sobre una ruta, sin configuración.
#: `Trinquete` NO está aquí a propósito: necesita un baseline, un tope y el extractor del
#: inquilino, así que es API, no subcomando. Meterlo aquí exigiría inventarle un formato de
#: configuración antes de tener un segundo consumidor que lo justifique.
DETECTORES = {
    "preguntas": revisar_preguntas,
    "punteros": revisar_punteros,
    "secretos": revisar_secretos,
    "sintaxis": revisar_sintaxis,
}
