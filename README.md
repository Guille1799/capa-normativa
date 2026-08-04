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
| **un `status` no se reconoce** (`vigent:`) | que una errata desactive la caducidad en silencio |
| **un puntero apunta a una norma inexistente** | mandar al lector a algo que no está |
| una norma **bloqueada** se intenta leer | resolver un conflicto a escondidas, por orden de fichero |
| **una norma declara más certeza de la que sostiene su evidencia** | **que la escala de certeza sea decorativa** |
| dos entradas de evidencia comparten `id` | colisiones en la capa que nunca se borra |
| una cita antigua se marca como reciente | citar un clásico sin decir que lo es |
| **se PREGUNTA por una dimensión no declarada** | **que una errata del llamante caiga al comodín en silencio** |
| hay **dos** ramas del sujeto desconocido | que el orden del fichero decida el valor por defecto |

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

### Estados y punteros reales (v0.5.0)

Tres agujeros de la misma familia — *lo que declaras tiene que ser de verdad*:

**`status` solo admite valores conocidos.** No es pulcritud: la caducidad se comprobaba
`if status == "vigente"`, así que una errata la **desactivaba**. `status: vigent` con una
fecha pasada cargaba y seguía emitiendo.

**Los punteros apuntan a algo que existe.** `retirement.replaced_by` no se validaba, y el
daño no era pasivo: el error de retirada **compone su mensaje con el puntero** y se lo
enseña al lector como si fuera ayuda (`→ usa: norma_que_no_existe`). Ahora
`replaced_by: []` sí es válido —*"no hay sustituto"* es una respuesta— pero tiene que estar
escrito; antes el mensaje lo sugería y lo rechazaba a la vez.

**`bloqueada` existe de verdad.** Una norma con evidencia en conflicto y sin adjudicar
**se niega a emitir**:

```yaml
status: bloqueada
blocking:
  reason: dos fuentes dan cortes distintos y nadie ha adjudicado
  conflicting_evidence: [EV-001, EV-002]
```

```python
NORMS.resolve("mi_umbral", kind="alpha")   # BlockedNormError, con el motivo dentro
```

Emitir ahí sería resolver el conflicto a escondidas, eligiendo por orden de fichero. Una
norma **tiene valor o está explícitamente bloqueada, nunca ambigua**.

Sus ramas **sí** pueden solaparse, y no es una excepción sino la semántica: son las
candidatas en conflicto. Exigirle ramas disjuntas sería pedirle que estuviera adjudicada,
que es justo lo que declara no estar. Tampoco se le exige caducidad: en una norma que no
emite, caducar no significa nada.

No es breaking: `bloqueada` es nueva, y los otros dos solo rechazan lo que ya estaba roto.

### La capa ① evidencia, por fin verificada (v0.6.0)

Durante cinco versiones el parser comprobó **solo los IDs** de la evidencia. Todo lo demás
—qué dice la fuente, de qué año es, cuánto de fiable— entraba sin que nadie lo mirara.

Lo grave era esto: **la certeza de una norma era autodeclarada**. R1 impide que algo
`vinculante` tenga certeza débil… y bastaba escribir `alta` a mano para saltárselo, aunque
toda la evidencia citada fuese la más floja de la escala. La escala entera era decorativa.

```yaml
# schema.yaml — todo opcional. El registro no sabe cómo se llaman TUS campos.
evidence_certainty_field: certeza
evidence_year_field: anio
evidence_recent_field: reciente
recency_horizon: 2018
```

Con eso declarado: una norma no puede afirmar más de lo que sostiene su mejor fuente, dos
entradas no pueden compartir `id`, y una cita antigua no puede marcarse como reciente
—citar un clásico está bien, disfrazarlo no—.

**Opt-in de verdad**: sin declarar los campos, el comportamiento es el de la v0.5.0.

### La otra mitad del contrato: `resolve()` (v0.7.0)

Seis versiones protegiendo lo que se **escribe** en el YAML. Nadie miraba qué pasa cuando el
código **pregunta** — y ahí estaba la mitad del contrato sin cubrir:

```python
NORMS.resolve("pain_threshold", tisue="tendon")   # errata del llamante
```

…se ignoraba en silencio y caía al comodín. Es la misma errata que `subject_dimensions`
cerró del otro lado, y **peor**: en el fichero la escribes una vez, pero una llamada mal
escrita puede estar en cualquiera de los treinta sitios que consultan el registro. En una
norma de bandas el comodín significa *"no hay dato"*, así que la errata convierte una señal
real en silencio.

Con ella, tres más de la misma familia:

- **`0` ya no es "dato ausente".** `missing` se calculaba por veracidad, así que un cero, un
  `False` o una cadena vacía contaban como *"no me lo has dado"*. Un cero es un valor.
- **El registro entrega copias, no sus tripas.** `value` y `matched` eran referencias: un
  `.append()` de quien preguntaba cambiaba la norma para todos. Era la negación literal de
  *"solo hay una copia"*.
- **Como mucho UNA rama del sujeto desconocido.** Con dos, gana la última del fichero — el
  orden decidiendo el valor, justo en el punto ciego que la regla anti-solapamiento se dejó
  al excluir las ramas comodín *"porque solapan por definición"*. Las normas `bloqueada`
  quedan fuera: sus ramas **son** las candidatas en conflicto.

Lo único que puede requerir un cambio es lo primero — y si falla, ahí tenías un bug.

### Obligar por PRECAUCIÓN, y una afirmación que no afirma (v0.8.0)

Dos huecos que aparecieron migrando reglas de seguridad reales.

**`strength: precautorio`.** Hasta aquí una norma obligaba (`vinculante`) o no
(`condicional`), y *"nada vinculante con certeza débil"* lo impedía cuando la evidencia era
floja. En general acierta. Pero deja fuera un caso que existe:

> Un veto **precautorio** obliga *precisamente porque* la evidencia es débil. No obliga
> porque sepamos que hace daño: obliga porque **no sabemos que sea seguro**.

Con dos valores, esas reglas había que escribirlas `condicional` mientras el código las
aplicaba a rajatabla — el registro describiendo mal lo que el sistema hace, y justo en
seguridad. Ahora se declaran, a cambio de decir **de qué protegen**:

```yaml
strength: precautorio
certainty: baja
precaution: >
  Impacto excéntrico alto sobre un tendón ya cargado por carrera y déficit.
  No hay evidencia de que sea seguro a esta densidad; el veto no espera a tenerla.
```

Para que no sea la puerta de atrás de la regla anterior, `precautorio` **exige** ese campo y
**rechaza la certeza fuerte**: si la evidencia sostiene la regla, es `vinculante`, y decirlo
así informa más. Y `strength` pasa a ser vocabulario cerrado — hasta ahora solo se comparaba
contra el literal `"vinculante"`, así que `vinculnte` degradaba una norma obligatoria a
sugerencia en silencio.

Los consumidores no deberían conocer el vocabulario: usa **`norm.is_binding`**. Todo
`if strength == "vinculante"` escrito antes de la v0.8.0 dejó de ser correcto al aparecer
`precautorio`, y falla **hacia el lado malo** — tratando un veto de seguridad como una
sugerencia.

**Una evidencia `sin_respaldo` se rechaza donde está.** Antes se aceptaba y reventaba después,
en la norma que la citara, culpando a la norma. Y no había salida: si la cita no puede
declararse `sin_respaldo`, y si declara más se salta la regla de la certeza. La entrada era
inutilizable por construcción y nada lo decía. Si un número no tiene fuente, va en la NORMA
(`certainty: sin_respaldo` + `provenance_note`), sin entrada de evidencia.

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
pip install git+https://github.com/Guille1799/capa-normativa.git@v0.8.0
```

## Migrar

**De v0.7.0 a v0.8.0** — dos cosas. (1) Si tu `evidence.yaml` tiene entradas con la certeza
más baja de tu escala, bórralas: no eran citables. (2) Busca `strength ==` en tu código y
cámbialo por `norm.is_binding`, o `precautorio` te pasará por delante como si no obligara.

**De v0.6.0 a v0.7.0** — comprueba tus LLAMADAS: `resolve()` ya no acepta kwargs que no
sean dimensiones declaradas. Si alguna falla, ahí tenías una errata que caía al comodín.

**De v0.5.0 a v0.6.0** — nada que hacer. R15 es opt-in: sin declarar los campos de tu
evidencia en `schema.yaml`, no comprueba nada.

**De v0.4.0 a v0.5.0** — nada que hacer. R14 solo rechaza estados y punteros que ya estaban rotos.

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
