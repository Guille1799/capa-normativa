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
| **dos ramas matchean al mismo sujeto** | que el orden del fichero decida el valor |
| **una norma ramifica por otra norma** | **encadenar reglas por la puerta de atrás** |
| **dos rangos solapan** (`">=40"` y `">=60"`) | que un sujeto de 70 se lleve el valor de la banda equivocada |
| **un rango está vacío** (`"[5,3]"`) | una rama muerta que cae al comodín sin avisar |
| **una clave no se reconoce** (`valeu:`, `certainy:`) | que lo escrito y lo que hace el registro no coincidan |

## Lo que NO hace, a propósito

- **No ejecuta lógica.** Devuelve un valor y de dónde sale.
- **No encadena normas.** El encadenamiento lo hace el código llamante, donde se depura.

Es la diferencia con un motor de reglas. Veinte años de experiencia documentada muestran que
esos sistemas fracasan justo ahí: cuando las reglas dependen unas de otras aparecen
prioridades, bucles y una depuración imposible, y los equipos acaban volviendo a código plano.
Aquí la lógica se queda en tu lenguaje; solo salen **los valores y su respaldo**.

Desde la **v0.2.0** eso no es una promesa sino una comprobación — ver `subject_dimensions`.

## Expresividad, deliberadamente pobre

Una condición solo puede ser **comodín**, **igualdad simple** o **rango numérico**
(`">=100"`, `"[10,100)"`), **sobre una dimensión declarada del sujeto**. Nada más — ni
disyunciones, ni composición, ni orden de evaluación. El límite **está en el código**, no en
la documentación: intentar colar un operador falla.

### `subject_dimensions` — por qué existe (v0.2.0)

`schema.yaml` declara la lista **cerrada** de atributos del sujeto por los que se puede
ramificar:

```yaml
subject_dimensions: [kind, mode, size]
```

Sin ella, *"una norma no puede referenciar a otra"* se cumplía por disciplina y no por
construcción: el registro comprobaba la **forma** de la condición, pero no podía ver su
**semántica**. Para el parser, `{otra_norma: ">=0.30"}` era un rango perfectamente válido —
y pasaba. Se encontró usando el registro en producción, buscándolo a propósito; se coló al
primer intento.

De regalo, caza las **erratas de dimensión**, que eran el peor modo de fallo posible: una
clave mal escrita no matchea nunca, así que caía al fallback **en silencio** y devolvía el
valor por defecto sin que nada fallara.

> **Breaking respecto a v0.1.0**, y deliberadamente: hacerlo opcional habría dejado el
> agujero abierto por defecto, que es la forma exacta de tener un límite que no impide nada.
> Migrar es una línea — la unión de las claves `when` que ya usas.

### Solapamiento entre rangos (v0.3.0)

Hasta la v0.2.0, *"dos ramas no pueden matchear al mismo sujeto"* se comprobaba comparando
**conjuntos de pares**: detectaba igualdad y subsunción, pero dos rangos son literales
distintos y convivían tan tranquilos. Con un eje partido en bandas eso no es un aviso que
falta, es la **respuesta equivocada en silencio**:

```yaml
- when: {age_band: ">=40"}   # master
- when: {age_band: ">=60"}   # adulto mayor   ← nunca se alcanzaba
```

Un sujeto de 70 se llevaba el valor de la primera rama del fichero. Ahora la pregunta que se
hace el parser es la que de verdad importa —**¿existe algún sujeto que cumpla las dos
ramas?**— resuelta con aritmética de intervalos sobre la gramática de rangos. Dos condiciones
sobre dimensiones distintas no se estorban; el choque solo puede venir de las claves
compartidas.

Se rechaza también el **rango vacío** (`"[5,3]"`, `"(4,4)"`): una rama que no puede matchear
nunca cae al comodín y devuelve un valor plausible que no es el suyo.

No es breaking: si tus rangos ya eran disjuntos, no cambia nada. Si no lo eran, tenías un bug.

### Claves desconocidas (v0.4.0)

El parser aceptaba cualquier clave que no entendiera y la **descartaba en silencio**. Se
encontró intentando poner `certainty` en una **rama**: se aceptaba, se tiraba, y `resolve()`
seguía devolviendo la certeza de la norma — quien la escribió creía haber ramificado la
confianza y no había hecho nada.

El caso peor era una errata en `value`:

```yaml
- when: {kind: alpha}
  valeu: 55.0          # la norma CARGABA y emitía None
```

…indistinguible de un `value: null` deliberado. Ahora ninguna de las dos construye, y el
mensaje sugiere la clave correcta.

**Limitación declarada:** dentro de `adjudication` y `retirement` las claves siguen siendo
libres. Son metadatos de prosa —quién adjudicó, con qué conflicto, por qué— y no gobiernan lo
que el registro emite, así que una errata ahí es cosmética.

No es breaking: solo rechaza claves que ya se estaban ignorando.

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

- `schema.yaml` — la escala de certeza y las dimensiones del sujeto, **declaradas, no
  cableadas**: cada dominio usa las suyas.
- `evidence.yaml` — lo que dicen las fuentes. **Append-only.** No gobierna nada directamente.
- `norms.yaml` — lo que *tu* sistema hace. Es lo único que el código puede citar.

## Instalación

```bash
pip install git+https://github.com/Guille1799/capa-normativa.git@v0.4.0
```

## Migrar

**De v0.3.0 a v0.4.0** — nada que hacer. R13 solo rechaza claves que ya se ignoraban.

**De v0.2.0 a v0.3.0** — nada que hacer. R12 solo rechaza rangos que ya estaban mal.

**De v0.1.0 a v0.2.0** — una línea en `schema.yaml`. Si el registro no arranca, el mensaje
dice qué falta:

```yaml
subject_dimensions: [las, claves, de, tus, when]
```

Si al declararlas descubres que una es el nombre de otra norma, eso **era** el bug: resuelve
las dos por separado y compón el resultado en tu código.

## Origen

Extraído de un sistema de prescripción de entrenamiento y nutrición donde el mismo parámetro
se re-decidía en cada sesión de trabajo, y donde los valores tendían a quedar ajustados al
único usuario que había. Ambos problemas resultaron ser el mismo: **una contradicción entre
fuentes que se resuelve eligiendo un número produce un sistema hecho a medida de una persona;
resolverla ramificando produce uno que sirve para cualquiera.**

MIT.
