# capa-normativa

**Conocimiento externo que gobierna código, como datos verificables.**

Para sistemas cuyo comportamiento depende de conocimiento que viene de fuera —literatura
científica, metodología, regulación— y que además **se contradice, cambia con el tiempo, y
debe aplicarse distinto según a quién**.

El código deja de contener los números. Se los pide al registro, que devuelve **el valor
junto a su procedencia**. Y una norma mal formada **no se construye**: si el registro no se
construye, el programa no arranca.

```python
from capa_normativa import NormRegistry

NORMS = NormRegistry.load("norms/")           # falla al arrancar si algo está mal

r = NORMS.resolve("watch_threshold", kind="alpha")
r.value        # 25.0
r.evidence     # ('EV-0007', 'EV-0009')
r.certainty    # 'baja'  → nunca podrá ser una recomendación fuerte
r.is_fallback  # False   → hubo rama específica para este sujeto
```

## Estados ilegales que no se pueden construir

Cada uno corresponde a un modo de fallo real y observado:

| No se construye si… | Evita |
|---|---|
| `strength: vinculante` con certeza débil | tratar como dogma lo que la evidencia no sostiene |
| certeza débil sin fecha de caducidad | que lo frágil se quede para siempre |
| una norma vigente está **caducada** | que "revisar esto algún día" nunca llegue |
| una rama no cita evidencia | números sin procedencia |
| se cita evidencia **inexistente** | punteros colgantes |
| **falta la rama del sujeto desconocido** | **especificar solo para quien tienes delante** |
| dos normas comparten identificador | colisiones silenciosas entre documentos |
| hay contradicción declarada sin resolución | recoger conflictos y no adjudicarlos nunca |
| una norma retirada se intenta leer | el comentario fósil que sobrevive a su supersesión |
| se cuela lógica en una condición | convertir esto en un motor de reglas |

## Lo que NO hace, a propósito

- **No ejecuta lógica.** Devuelve un valor y de dónde sale.
- **No encadena normas.** El encadenamiento lo hace el código llamante, donde se depura.

Es la diferencia con un motor de reglas. Veinte años de experiencia documentada muestran que
esos sistemas fracasan justo ahí: cuando las reglas dependen unas de otras aparecen
prioridades, bucles y una depuración imposible, y los equipos acaban volviendo a código plano.
Aquí la lógica se queda en tu lenguaje; solo salen **los valores y su respaldo**.

## Expresividad, deliberadamente pobre

Una condición solo puede ser **comodín**, **igualdad simple** o **rango numérico**
(`">=100"`, `"[10,100)"`). Nada más — ni disyunciones, ni composición, ni orden de evaluación.
El límite **está en el código**, no en la documentación: intentar colar un operador falla.

## Ausencia de respaldo, declarada

La mayoría de las constantes de un sistema real no tienen fuente. Si el registro las
rechazara, se quedarían escondidas en el código — el problema de partida. Así que pueden
entrar con `certainty: sin_respaldo`, a cambio de **decir de dónde salieron**:

```yaml
certainty: sin_respaldo
provenance_note: >
  Nadie sabe de dónde salió. Estaba en el código sin cita ni comentario.
```

*"Nadie lo sabe"* es una respuesta válida y mucho más útil que el silencio. Y por estar bajo
el umbral de certeza débil, hereda gratis: no puede ser vinculante y **caduca sí o sí**.

> El objetivo no es que todo tenga evidencia. Es que **la ausencia de evidencia sea visible,
> caduque, y no gobierne como si fuera dogma**.

## Estructura

Tres ficheros en el directorio que le pases:

- `schema.yaml` — la escala de certeza, **declarada, no cableada**: cada dominio usa la suya.
- `evidence.yaml` — lo que dicen las fuentes. **Append-only.** No gobierna nada directamente.
- `norms.yaml` — lo que *tu* sistema hace. Es lo único que el código puede citar.

## Instalación

```bash
pip install git+https://github.com/Guille1799/capa-normativa.git
```

## Origen

Extraído de un sistema de prescripción de entrenamiento y nutrición donde el mismo parámetro
se re-decidía en cada sesión de trabajo, y donde los valores tendían a quedar ajustados al
único usuario que había. Ambos problemas resultaron ser el mismo: **una contradicción entre
fuentes que se resuelve eligiendo un número produce un sistema hecho a medida de una persona;
resolverla ramificando produce uno que sirve para cualquiera.**

MIT.
