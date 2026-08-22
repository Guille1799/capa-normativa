# La noche del arnés: nueve comprobadores que nunca se ejecutaron

**2026-08-23, de madrugada.** El encargo era «todo lo que esté pendiente, y entre paso y paso
pregúntate si es lo más sólido». Esa segunda mitad del encargo cambió tres decisiones, y las tres
están abajo.

## Lo que se encontró, por orden de daño

### 1 · Nueve aceptaciones estaban entrecomilladas en markdown

```python
_INV['x'] = ("`python scripts/algo.py` — hoy ROJA porque ...", "resumen")
```

El tablero ejecuta esa cadena entera con `shell=True`. cmd.exe contesta *«'`python' is not
recognized as an internal or external command»*, el tablero lee el exit distinto de cero y lo
traduce a **«pendiente»**. O sea que durante semanas dijo que faltaba trabajo cuando el comando
**no había llegado a arrancar**. Ninguna de las nueve se podía cerrar hiciera nadie lo que hiciera.

Es el fallo del arnés en su forma más pura, el mismo que costó la noche del 22:

> Un rojo no dice «falta trabajo». Dice «esto no salió bien». Dos hechos distintos, la misma señal.

Al desentrecomillarlas y ejecutarlas: **5 salen rojas de verdad**, **2 salen VERDES —el trabajo ya
estaba hecho—** y 2 rojas porque el artefacto que piden crear aún no existe, que es su rojo
correcto. Tableros: mcp 14/31 → 15/31, eu 11/20 → 12/20.

**Se corrigió en la fábrica, no en las nueve cadenas.** Tocar a mano literales llenos de comillas y
escapes es justo como se meten estos fallos — y de hecho el primer intento de hacerlo así rompió la
indentación de los cuatro ficheros a la vez.

### 2 · Los cuatro topes estaban por encima de su cola segura

```
ralph_diario.cmd: MAX=24 > 23     ralph_cn.cmd: MAX=7 > 1
ralph_eu.cmd:     MAX=8  > 0      ralph_pw.cmd: MAX=18 > 6
```

Pasado el tope de la cola segura, R1b no encuentra comprobador que citar y **falla abierto por
diseño**. Un MAX más alto no da más trabajo hecho: da más trabajo creído. La invariante se pudre
sola, y esta vez se pudrió por el segundo camino: **la cola cambió debajo de los topes**.

### 3 · Cinco tareas estaban en la caja equivocada, no mal escritas

Bloqueadas en `pw-ralph` y `eu-ralph` con el motivo correcto —*el arreglo vive fuera de este
worktree*— cuando su arreglo vive en un repo que **tiene su propio worktree y su propia cola**.
Re-ubicadas con el comprobador y la ruta reescrita a relativa: una tarea re-ubicada que conserve la
ruta vieja se bloquea otra vez el primer día, y por lo mismo.

## Las tres veces que «¿es lo más sólido?» cambió la decisión

**No requeué las 7 de `capa-normativa`.** El clasificador decía `atado-a-otro-arbol` y era verdad,
pero al abrir el ledger las siete llevaban una **«PREGUNTA concreta para G»** y su sección dice
*«Ralph NO toma tareas de aquí»*. El diagnóstico técnico era correcto y no era el bloqueo operativo.

**No «arreglé» la guarda de `ralph_diario.sh`.** La tenía anotada como defectuosa —hace
`git reset --hard`, que no borra ficheros sin seguir—. Al leerla, ya los excluía (`grep -v '^??'`)
con el motivo escrito al lado. El defecto estaba en mi lectura, no en el código.

**Quité una defensa mía en vez de añadir otra.** La guarda filtraba a rutas absolutas para no
confundir un id de pytest con un fichero. Una mutación sobrevivió y enseñó que esa versión era la
**peor**: dejaba escapar `../hermano/x.py`, que es relativo y sale del árbol igual. Como el `chdir`
ya resolvía el ruido, la restricción sobraba. Una defensa que se puede probar, en vez de dos que se
tapan entre sí.

## Corrección al mapa de anoche

**`C:/Users/Guille/proyectos/` es un repositorio git** (165 ficheros, 55 commits), y versiona los
lanzadores y `proyectos/.claude/hooks/`. Anoche los metí en el saco de «sin repo, sin red de
revert» junto a `~/.claude/`. No es lo mismo: sólo `~/.claude/` carece de red.

## Lo que sigue sin poder hacerse solo

Cuatro tareas cuyo arreglo vive en `~/.claude/` —la única carpeta sin control de versiones— y las
siete de `capa-normativa` que esperan una decisión. **La cola de `eu-ralph` está en cero y es
correcto que lo esté**: todo lo suyo es de una de esas dos clases.

## Lo que queda montado pero sin desplegar

`capa_normativa.vigilante.arbol_propio` sólo vive en esta rama. Para que los otros tres tableros lo
usen hace falta fusionar, y fusionar es decisión de G. Medido hoy sobre los cuatro tableros:
**cn-ralph 5 sondas mal apuntadas · mcp-ralph 4 · pw-ralph 0 · eu-ralph 0** — los dos ceros son los
árboles cuyas sondas ya se arreglaron, o sea el antes y el después de la misma medida.

## Dos que quedan rotos, y por qué no los toqué

Después de sacar la prosa del campo del comando, dos siguen creando ficheros basura al ejecutarse:

| comprobador | basura que deja |
|---|---|
| `inv-ess-variable-checker-su-unica` (eu) | `'+$x.Value)` |
| `inv-decision-recall-y-session-restorer` (eu/mcp) | ``1` `` |

No es prosa: son comandos **PowerShell con el entrecomillado mal anidado** —`powershell -Command
"…$($x.Value)…"` dentro de una cadena de Python dentro de una cadena de shell—, y el trozo que se
escapa acaba como nombre de fichero. Que dejen basura es lo de menos: significa que **el comando no
mide lo que su autor creía**, así que su veredicto no vale ni en rojo ni en verde.

No los reescribí porque arreglar comillas anidadas de PowerShell a ojo, de madrugada y sin poder
preguntar, es exactamente cómo se mete el siguiente fallo de esta familia. Y porque los dos están
además en el grupo de *fuera del repo*, que espera decisión. `bin/contratar.py` ya los clasifica
como `comando-roto` por el backtick, así que no se colarán en una cola por descuido.
