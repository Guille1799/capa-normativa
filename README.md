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

---

# Dos módulos

Un artefacto, dos módulos, y **no se importan entre sí** (verificado por un test que lo comprueba
por AST — una frontera que no se verifica es una frontera que deriva):

| Módulo | Qué hace | Cuándo corre |
|---|---|---|
| **`capa_normativa`** — el registro | los números viven como datos con procedencia y caducidad. **Fail-fast**: si algo está mal, el programa no arranca | en tu proceso, al arrancar |
| **`capa_normativa.vigilante`** — el vigilante | chequeos **deterministas** sobre un repo. **Enumera** en vez de parar en el primer error | en pre-commit, en CI, o a mano |

## `init` — empieza aquí si no tienes registro todavía

```bash
capa-normativa-init norms/            # crea schema.yaml, evidence.yaml y norms.yaml
capa-normativa-validate norms/        # y compruébalo: sale verde tal cual
```

Genera los tres YAML **comentados y válidos**: cargan y resuelven sin tocar nada. Traen **las dos
formas que existen** —una norma constante con evidencia y una ramificada por un atributo del
sujeto— porque con una sola, la primera norma real que ramifique se escribe adivinando.

**Un generador cuya salida no valida es peor que no tenerlo**: la primera experiencia sería un error
en un fichero que te acaba de dar el paquete, y no sabrías si el problema es tuyo o del ejemplo. Hay
un test que lo fija y es el único que no se puede relajar.

- **No sobreescribe.** Si ya hay ficheros sale con `1` y **no toca ninguno** — todo-o-nada, porque un
  registro medio sobrescrito es peor que no haber tocado nada. `--forzar` si de verdad quieres.
- **No trae dominio de nadie.** Los ejemplos son genéricos a propósito (un test lo comprueba): meter
  aquí umbrales de nutrición o de entrenamiento ataría el paquete a su primer inquilino.

Los comentarios explican **por qué** cada campo existe, no solo qué acepta — en particular que
`subject_dimensions` es una **lista cerrada** y que eso es lo único que impide encadenar normas, y
que una `expires` vencida **impide arrancar la aplicación**.

## `emit` — si tu consumidor no es Python

El registro se lee con `load()`+`resolve()` **en proceso Python**. `emit` saca las constantes a
otro lenguaje **con su procedencia**, para el frontend en TypeScript, los umbrales en R, o un
JSON universal.

```bash
capa-normativa-emit norms/ --formato typescript --salida frontend/norms.ts
capa-normativa-emit norms/ --formato r          --salida R/constants.R
capa-normativa-emit norms/ --formato json       --salida build/norms.json
capa-normativa-emit norms/ --formato python     --salida app/norms_gen.py
```

**Y esto es lo que hace que `emit` no sea un problema nuevo:**

```bash
capa-normativa-emit norms/ --formato typescript --salida frontend/norms.ts --check
```

`--check` no escribe: **re-emite y compara**. Si difiere, sale con **1**. Commitea el fichero
generado **y pon `--check` en CI** — es el patrón de `protobuf`, `OpenAPI` y
`kubernetes/hack/verify-codegen.sh`. **Sin `--check`, `emit` añade un artefacto más que puede
derivar, que es exactamente el problema que este paquete existe para impedir.**

Cada valor sale con su unidad, sus IDs de evidencia, su certeza, su fuerza y su caducidad:

```typescript
/** puntos porcentuales de grasa · ev=EV-0113 · certeza=baja · condicional · caduca=2027-01-30 */
export const BIA_MEASUREMENT_ERROR_MARGIN = 3.0 as const;
```

> **Si `emit` solo sacara números, habría reinventado el problema en un sitio nuevo.** Un
> `EA_FLOOR <- 30` generado es el mismo número mágico, con un paso de build de por medio.

**Solo emite las constantes** (las que no ramifican por el sujeto). Una que ramifica no se puede
volcar sin reproducir su tabla de decisión y su hit policy en cada lenguaje, así que **no se
emite y sale en `omitidas` con su motivo** — una ausencia silenciosa haría parecer completo al
fichero generado. En el registro real del primer inquilino: **38 constantes emitidas, 36
omitidas**, cada una con su razón. Y **lo que el registro no serviría tampoco se emite**:
retiradas y bloqueadas quedan fuera, o `emit` sería la puerta de atrás.

## `validate` — comprueba el registro sin arrancar la app, y avisa de lo que va a caducar

```bash
capa-normativa-validate norms/                          # 0 válido · 1 problemas · 2 no se pudo
capa-normativa-validate norms/ --avisa-en 90            # horizonte del aviso (por defecto 60 días)
capa-normativa-validate norms/ --falla-si-caduca-en 30  # para CI: el aviso pasa a ser un GATE
capa-normativa-validate norms/ --json                   # para consumo por máquina
```

**No es `load()` con otro nombre.** Cubre dos huecos que `load()` deja, y ninguno es cosmético.

### ① Una norma caducada es una caída de producción, y nada la anunciaba

Una norma `vigente` cuya `expires` ya pasó **hace que `load()` lance**: el día que caduca, **la
aplicación no arranca**. Ese diseño es deliberado —es la mitad *«niégate a servir lo rancio»* del
modelo de gettext— pero sin aviso previo es una mina: el mecanismo que te protege de la información
vieja se manifiesta como un despliegue que falla un martes, sin relación aparente con nada que
hayas tocado.

**`--avisa-en` es la otra mitad**, y `--falla-si-caduca-en` la convierte en un gate de CI. Caducar
pronto **no** es un error —si lo fuera, alguien apagaría el aviso—, así que sale en verde con
advertencia hasta que tú decidas lo contrario.

El gate mira **solo a las normas que EMITEN** (v0.16.1). Una `retirada` o `bloqueada` vencida se
sigue reportando —una fecha muerta en el YAML miente a quien la lee— pero no lo falla: no emite
valor, así que su caducidad no puede tirar nada. Hasta la v0.16.0 sí lo fallaba, y eso ponía un
gate rojo por un no-motivo: en una norma que no emite, la fecha que manda es la de `retirement`,
y ponerle además un `expires` solo duplica esa fecha donde no gobierna nada.

### ② `load()` para en el primer error; quien escribe YAML quiere los siete

Mismo reparto que entre el registro y el vigilante: el registro **para** porque su trabajo es no
arrancar; esto **enumera** porque su trabajo es que alguien arregle un fichero.

Se enumeran los errores **por norma**, que son independientes. Los de `schema.yaml` y de la
evidencia **no**, y es deliberado: todo lo demás depende de ellos, así que seguir tras un esquema
roto produce una cascada de errores derivados que oculta el único que importa.

> ⚠️ **No reimplementa ninguna comprobación**: llama al mismo validador que `load()`. Dos
> validadores que se pretenden equivalentes divergen, y entonces `validate` diría verde sobre un
> registro que no arranca — peor que no tenerlo. Un test lo comprueba por AST.

### Lo que encontró en su primera corrida

Contra el registro real del primer inquilino, y sin arrancar su aplicación:

```
✗ [working_sets_by_mode] rama #0 viaja con certainty='baja' pero la MEJOR evidencia
  que ELLA cita es 'muy_baja'.
```

Una rama que **se presentaba como más fiable que su única fuente**, heredando certeza de la rama de
al lado. Habría impedido arrancar la app al actualizar el paquete. Eso es exactamente el caso de
uso: enterarse antes, y sin levantar nada.

## El vigilante — empieza por aquí si solo quieres los chequeos

No necesita el registro. Funciona en cualquier repo, incluso sin un solo `.yaml`.

```bash
capa-normativa-vigilante <ruta>                      # todos los detectores
capa-normativa-vigilante <ruta> --detector sintaxis  # uno solo
capa-normativa-vigilante <dir-de-md> --detector punteros --tambien ../otro/docs
capa-normativa-vigilante <ruta> --json               # salida para consumo por máquina
```

**Contrato de salida**, porque el consumidor previsto es un agente sin contexto:

| Código | Significa | Qué hacer |
|---|---|---|
| **0** | limpio | nada |
| **1** | hay hallazgos | arreglarlos: cada hallazgo **dice qué hacer** |
| **2** | no se pudo ejecutar | investigar: «falló» y «encontró cosas» exigen reacciones opuestas |

### Los detectores

| Código | Caza | Nota |
|---|---|---|
| **`SYN001`** | un `.py` versionado que no parsea | encontró un `SyntaxError` de **dos meses** que ningún otro mecanismo había visto |
| **`PTR001`** | un puntero `§N.M` que no resuelve | no comprueba que la sección *diga* lo atribuido —eso no es automatizable—: comprueba que **exista**. Recorre el árbol **en profundidad** (ver el aviso de abajo) |
| **`SEC001`** | una credencial con forma reconocible en un fichero versionado | escanea **todo** lo versionado, informes incluidos. El hallazgo **nunca contiene el secreto**. `# nosec` al final de la línea lo suprime |
| **`TRI001`-`TRI007`** | el **trinquete**: una deuda declarada que solo puede decrecer | es API, no subcomando: necesita tu baseline y tu extractor. Ver abajo |
| **`SEM001`** | una constante cuyo **nombre** dice `..._CAP` y resuelve una norma con `semantics: suelo` (o al revés) | es API: necesita el mapa `slug → semantics` de **tu** registro. Ver abajo |

### `SEM001` — la migración correcta al número equivocado

Es el detector más joven (`v0.13.0`) y nace de un fallo **medido**, no imaginado.

Migrando una constante llamada `_PLANNED_LOAD_CARB_GKG_CAP` —un **tope** de carbohidrato extra— la
herramienta de triaje la propuso como candidata a la norma `carb_floor_g_per_kg_ffm`, que es un
**suelo** diario. Los dos valían `1.5`, y la candidatura era razonable: mismo valor, y los nombres
comparten la palabra `CARB`. Lo único que lo impidió fue leer el comentario del sitio.

Después se midió qué habría pasado sin leerlo. Se hizo la migración equivocada con el ritual
completo y se corrió el gate del proyecto:

```
2634 passed, 1 skipped, 1 xfailed
```

**Verde.** Y se entiende: todo el arnés comprueba que el **valor** no cambie, y el valor era `1.5`
antes y `1.5` después. **Nada miraba el significado.** El error habría quedado permanente e
invisible — un techo funcionando como piso, con procedencia falsa y aspecto de estar resuelto.

Peor: la condición que lo hace posible —que los dos números coincidan— es exactamente la condición
que hace que un triaje por valor te lo proponga. **No es un fallo raro: es el modo de fallo natural
de este trabajo.**

```python
from capa_normativa.vigilante import revisar_semantica

# El mapa sale de TU registro en una línea. Se pasa (no se lee) para que el vigilante
# no conozca el formato del registro: la frontera entre los dos módulos es del paquete.
mapa = {s: NORMS.norma(s).semantics for s in NORMS.slugs()}
for h in revisar_semantica("backend", mapa):
    print(h)
```

**Cómo se mantiene callado.** Exige **dos** condiciones a la vez: que el nombre traiga una palabra
de polaridad *semántica*, y que la norma declare la contraria. Sobre un backend real con 81 normas
da **0 hallazgos** — y encuentra el caso de arriba en cuanto se introduce. Un slug que no esté en tu
mapa se **ignora en silencio**, así que puedes pasar un mapa parcial sin generar ruido.

`_MIN` y `_MAX` desnudos **no** están en el vocabulario, y es deliberado: en el proyecto de origen
esa misma tentación marcaba el 100 % de las constantes, porque casi siempre son tamaños de muestra
(`_MIN_READINGS`). Un señalizador que dispara para todo no señaliza nada.

> ⚠️ **Lo que NO cubre, y conviene tenerlo claro para no confundirlo con cobertura:** dos
> constantes que responden preguntas distintas cuando **ninguna** se llama tope ni suelo — cuatro
> dosis de proteína (pre-entreno, post-entreno, pre-sueño…) son todas «gramos de proteína» y para
> esto son invisibles. Ahí el único defensor sigue siendo **leer el comentario del sitio**. Este
> detector tapa **una** clase de fallo: la que se pudo hacer determinista.

> ⚠️ **Sin mapa devuelve `[]`.** Es el no-op silencioso, así que **comprueba con un test que tu
> mapa llega lleno** (`assert len(mapa) >= N`). Un gate que no encuentra sus datos pasa en verde
> sin haber mirado nada, y ese es el modo de fallo que este paquete existe para impedir.

### ⚠️ Sobre `PTR001`: qué cuenta como «el corpus»

**Recorre el directorio en profundidad** (excluyendo `node_modules`, `venv`, `.git` y similares),
y las cabeceras de los subdirectorios **también** cuentan como destino válido.

> **En la `v0.10.0` NO recorría**: solo miraba el primer nivel. Sobre un `docs/` con
> subcarpetas decía **«limpio, 0 hallazgos»** y salía con **0** mientras había **8 punteros
> colgantes** una carpeta más abajo. Un falso negativo es la peor forma de fallo para un
> detector: da confianza. **Si usas la `0.10.0`, actualiza.**
>
> Lo encontró un agente sin contexto adoptando el paquete con solo este README — no los tests
> del propio detector, cuyos corpus eran todos de un nivel. *La forma del test copiaba la forma
> del bug.*

Y una consecuencia que conviene saber: al recorrer en profundidad aparecen **referencias a
secciones de documentos ajenos** (una especificación, un estándar) escritas sin prefijo. Eso sale
como colgante y es un falso positivo legítimo. Dos salidas: poner el documento delante en
MAYÚSCULAS (`DMN §10.3`), o declarar su corpus con `--tambien`. **El detector no adivina qué es
tuyo: se lo dices.**

### El trinquete

Un gate absoluto sale rojo el día 1 y **se desactiva**. El trinquete se calibra sobre el estado
actual y solo prohíbe empeorar, así que entra en un repo con deuda sin bloquearlo. Y no muere de
fatiga: no pide atención por evento, pide que un número no suba.

```python
from capa_normativa.vigilante import Trinquete

t = Trinquete("tests/const_baseline.json", tope=206,
              vocabulario={"norma", "tecnica", "mundo", "clasificador"},
              que_migrar_a="engine/norms/norms.yaml")

for h in t.revisar(mi_extractor_de_constantes()):
    print(h)          # cada uno con su código estable y su arreglo
```

El **extractor y el vocabulario son tuyos**: este módulo no sabe qué constantes tiene tu dominio.
Comprueba seis cosas, y **cada una salió de un fallo real**: entradas nuevas · valores cambiados sin
cambiar el nombre · **entradas obsoletas** (una entrada que ya no existe es un *permiso de
reentrada*: sin esta comprobación, lo migrado se puede volver a escribir a mano sin que nada se
queje) · el tope superado · entradas sin explicar por qué siguen ahí · y **el tope flojo**, porque un
tope por encima del recuento real es decoración.

Lo que **no** puede hacer, y el mensaje lo dice en vez de esconderlo: distinguir *«la deuda creció»*
de *«el instrumento dejó de estar ciego»*. Eso es intención, y la intención no se calcula.

### Cablearlo a un pre-commit

```bash
#!/bin/sh
capa-normativa-vigilante . --detector sintaxis --detector secretos || exit 1
```

⚠️ **Los hooks locales son cortesía: la copia que de verdad puede bloquear es la de CI.** Un
pre-commit se salta con `--no-verify` y no existe en el clon de nadie más.

### Por qué determinista y no un LLM

Un detector que oscila **es otra respuesta viva más**: empeora el problema que viene a resolver. Y no
cuesta tokens, así que sigue funcionando cuando el presupuesto baja. Los módulos del vigilante tienen
un test que verifica por AST que **no importan nada de red** — la ley se mecaniza, no se confía.

---

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

### …y declarada POR RAMA (v0.14.0)

Hasta aquí eso era todo-o-nada **a nivel de norma**, así que *"esta rama está respaldada y
esta otra es convención"* no se podía escribir: la norma mixta tenía que mentir en un sentido
u otro — inflar la certeza de la rama sin respaldo, o borrar el respaldo real de la otra.

```yaml
certainty: sin_respaldo          # = la de su rama MÁS DÉBIL
branches:
  - when: {mode: alfa}
    value: 3
    certainty: moderada
    evidence: [EV-A]
  - when: {mode: any}
    value: 9
    certainty: sin_respaldo
    provenance_note: convención del motor — es lo que el código hace hoy, sin fuente
```

Y donde se paga es en `resolve()`: **la certeza y la procedencia que recibes son las de la
rama que contestó**, no las de la norma.

Tres reglas lo sujetan, para que el campo nuevo no sea una etiqueta libre:

- **Cada rama responde de SU evidencia.** La comprobación de que nadie afirma más de lo que
  sostiene su fuente miraba la **unión** de todas las ramas, o sea la mejor fuente de la
  norma entera — así que una rama que solo citaba una fuente floja viajaba con la certeza que
  sostiene la fuente de su hermana. Ahora se mira rama a rama.
- **La certeza de la norma es la de su rama más débil**, y se comprueba que la declarada
  coincide. Sigue escrita a mano en vez de calcularse: es lo que lee un humano en el diff, y
  lo que hay que impedir no es que exista — es que mienta.
- **`strength` NO se parte.** El consumidor lee `norm.is_binding` sin saber qué rama le
  contestó, así que una norma vinculante con una rama sin respaldo obligaría a obedecer un
  número que no sostiene nadie. Si una banda del sujeto sí puede obligar y otra no, **son dos
  normas con `when` disjuntos**, una declarando `null` donde gobierna la otra.

## Estructura

**El registro** lee tres ficheros del directorio que le pases:

- `schema.yaml` — la escala de certeza y las dimensiones del sujeto, **declaradas, no
  cableadas**: cada dominio usa las suyas.
- `evidence.yaml` — lo que dicen las fuentes. **Append-only.** No gobierna nada directamente.
- `norms.yaml` — lo que *tu* sistema hace. Es lo único que el código puede citar.

**El vigilante** no lee nada de eso: se le pasa una ruta y trabaja sobre lo que git conoce.

## Instalación

```bash
pip install git+https://github.com/Guille1799/capa-normativa.git@v0.16.2
```

Instala las dos cosas: el registro (`from capa_normativa import NormRegistry`) y el comando
`capa-normativa-vigilante`.

> ⚠️ **No instales `v0.10.0`.** Hasta el 2026-08-14 este bloque fijaba ese tag, que es anterior a
> **SEC001** (añadido en `v0.13.0`) y arrastra el bug de recorrido descrito más arriba: **solo miraba
> el primer nivel** del árbol. La verificación en entorno limpio del 2026-08-11 era real, pero se hizo
> **sobre ese tag antiguo** — se conserva la nota porque el método vale, no la versión.

<details>
<summary>Sin instalar nada, desde un clon</summary>

```bash
PYTHONPATH=src python -m capa_normativa.vigilante.cli <ruta> --detector sintaxis
```
</details>

## Migrar

**De v0.13.0 a v0.14.0** — el YAML **no necesita cambios**: sin campos por rama, cada rama
hereda la certeza de la norma y todo significa lo mismo. Dos cosas que sí pueden morder:

1. La regla de la certeza pasa a mirarse **por rama**, así que puede rechazar una norma que
   antes cargaba: aquella cuya rama floja viajaba con la certeza de la evidencia de su
   hermana. No es daño colateral — es una inflación real que nadie veía. Medido en el primer
   inquilino: **1 norma de 74**, y estaba `vigente` resolviendo en producción.
2. `Resolution.certainty` es ahora la de **la rama**. Para una norma que no use los campos
   nuevos es idéntica; si adoptas la procedencia por rama, cambia a propósito — hacia arriba
   en la rama respaldada y hacia abajo en la que no.

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
