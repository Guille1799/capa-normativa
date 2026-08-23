# Cuatro comprobadores de capa-normativa juzgan el árbol equivocado

**2026-08-22.** Medido al clasificar las 52 tareas bloqueadas con `mcp_smart_context/bin/contratar.py`.

## Qué pasa

Cuatro comprobadores del tablero de `cn-ralph` escriben la ruta a mano:

| comprobador | ruta que hardcodea |
|---|---|
| `inv-revista-de-runtimes-quien-corre` | `C:/Users/Guille/proyectos/capa-normativa` |
| `inv-capa-normativa-es-el-unico` | `C:/Users/Guille/proyectos/capa-normativa/scripts/aceptacion.py` |
| `inv-autohealth-monitor-py-con-guion` | `C:/Users/Guille/proyectos/capa-normativa/scripts/aceptacion.py` |
| `inv-canario-py-aceptacion-py-verifica` | `C:/Users/Guille/proyectos/capa-normativa/scripts/aceptacion.py` |

El agente corre en `cn-ralph`, que es **otro worktree del mismo repo**. Así que arregla su copia
y el comprobador sigue mirando el checkout principal: **el veredicto no se mueve nunca**, la tarea
se bloquea, y no hay síntoma que apunte a la causa.

> Es exactamente el fallo que `ralph_aislado` existe para cazar, dentro de los comprobadores del
> propio arnés. En `ponerse_wenorro` apareció la misma noche y en la misma forma: las tres sondas
> `AGUJERO-*` hardcodeaban la ruta a `ponerse_wenorro` y se arreglaron derivándola de `__file__`
> (commit `3b129da` de `pw-ralph`).

## Por qué cuesta verlo

Porque el diagnóstico sale **del revés** si se compara contra un solo árbol. `cn-ralph` y
`capa-normativa` son el mismo repo, pero una comparación ingenua los ve distintos y concluye «esto
vive en otro repo» — o sea *no puedes tocarlo*, cuando lo que pasa es *puedes, pero apuntas mal*.
Son arreglos opuestos: uno saca la tarea de la cola y el otro la deja dentro y cambia tres líneas.
Por eso el clasificador pregunta a `git worktree list` en vez de fiarse de la raíz que le pasan.

Y hay un matiz que separa el defecto de su contrario: una ruta absoluta al árbol **propio** suele
salir de `Path(__file__).resolve()`, o sea de haberlo hecho bien. Solo delata a un árbol
**hermano**, que `__file__` no puede producir.

## El arreglo

Derivar de `__file__`, como en `pw-ralph`:

```python
SCRIPTS = Path(__file__).resolve().parent.parent   # en vez de la ruta escrita a mano
```

Y la señal de que el arreglo es correcto **no es que el comprobador se ponga verde**: es que siga
rojo mientras el agujero exista, pero ahora mirando su propio árbol. Las tres sondas de
`ponerse_wenorro` siguieron rojas después de arreglarlas, y eso fue la confirmación, no el problema.

## Lo que NO se toca aquí

Otros tres comprobadores de este repo (`inv-audit-settings-source-sh-no`,
`inv-registro-md-session-start-sh`, `inv-capa-normativa-declarado-en-el`) salen `fuera-del-repo`:
su arreglo vive en `~/.claude/` o en `mcp_smart_context`. Ésos no son de puntería sino de permiso,
y **no pertenecen a una cola aislada por worktree** — encolarlos otra vez sería encolar otro
bloqueo. Decisión de reparto pendiente con G.

---

# La segunda forma: `RAIZ.parent`, que solo es verdad desde el checkout principal

**2026-08-23.** Misma familia, distinto disfraz — y este no lo cazaba nada de lo de arriba, porque
**no hay ninguna ruta escrita a mano**.

## Qué pasa

Dos sondas de `scripts/aceptacion.py` buscaban su fichero en la carpeta que CONTIENE los repos, y
la resolvían con `RAIZ.parent`:

| sonda | lo que abre |
|---|---|
| `registro_sin_caducados()` | `RAIZ.parent / "REGISTRO.md"` |
| `revista_de_runtimes()` | `RAIZ.parent / ".claude/hooks/revista_runtimes.py"`, y `cwd=RAIZ.parent` |

Desde el checkout principal `RAIZ` es `proyectos/capa-normativa`, así que `RAIZ.parent` es
`proyectos` y los dos ficheros están ahí. Desde un worktree `RAIZ` es
`capa-normativa/.claude/worktrees/<x>` y `RAIZ.parent` es `.../worktrees`, donde no hay ni
registro ni hooks: las dos sondas caían por su rama de «no existe el fichero».

**Medido antes de tocar nada, la misma sonda y el mismo commit:**

```
principal   🟢 registro-sin-caducados  ninguna entrada de REGISTRO.md esta vencida
worktree    🔴 registro-sin-caducados  no existe ...\.claude\worktrees\REGISTRO.md
worktree    🔴 revista-de-runtimes     no existe .claude/hooks/revista_runtimes.py
```

Ese rojo no habla de la promesa: habla de dónde se corrió. Es el instrumento tumbando la medida,
como el `GIT_DIR` del vigilante y el `-1/-1` de `--verifica`.

## La confirmación que no se buscaba

`sondas-miran-su-arbol` **ya las estaba acusando** y nadie lo había leído así: antes del arreglo
denunciaba **5** sondas, después **3**, y las dos que desaparecen son exactamente éstas. El motivo
es que los worktrees viven DENTRO del checkout principal, así que `.../worktrees/REGISTRO.md` cae
en territorio del árbol principal — un hermano. La guarda escrita para el caso de arriba había
cazado el de abajo sin que su mensaje lo dijera.

## El arreglo, y por qué no es `__file__`

`__file__` da el árbol propio, que es justo lo que aquí NO se quiere: el fichero está fuera de
todo árbol. Se le pregunta a git por `--git-common-dir`, que desde cualquier worktree apunta al
`.git` del checkout **principal**; su padre es el repo y el padre de ése es la carpeta de
proyectos.

```python
git -C <RAIZ> rev-parse --path-format=absolute --git-common-dir
#   <proyectos>/<repo>/.git  →  .parent = el repo  →  .parent.parent = la carpeta de proyectos
```

Escribirla a mano no era opción: `sondas_miran_su_arbol()` existe para cazar eso. Deducirla del
nombre de la carpeta tampoco: `cn-ralph` y `capa-normativa` son el mismo repo y no se parecen.

Si git no contesta quedan dos redes, en orden: la FORMA del worktree (`<repo>/.claude/worktrees/<x>`),
que es el caso que se rompía, y `RAIZ.parent`, que es lo que había — el camino de emergencia no
puede dejar esto peor de como estaba.

Y el mensaje de `revista_de_runtimes()` pasa a imprimir la ruta ENTERA. Decía
`no existe .claude/hooks/revista_runtimes.py` y sonaba a que faltaba el guion, cuando lo que
fallaba era la carpeta desde la que se miraba. Si algún día ese rojo vuelve a ser legítimo, ahora
se distingue del otro leyéndolo.

## Aceptación

`tests/test_sondas_desde_un_worktree.py` monta un worktree **de verdad** (`git worktree add`, no
un `tmp_path` con la forma parecida — el arreglo consiste en preguntarle a git, así que un decorado
sin git pasaría por el camino de emergencia y no probaría nada), le inyecta ese `RAIZ` a las dos
sondas y exige que no salga la rama de «no existe». El guion de pega solo sale con 0 si su `cwd`
es la carpeta de proyectos, así que cubre también la tercera línea. Verificado por mutación: **2
fallan** con el código anterior y **3 pasan** con el arreglo (el tercero es el control desde el
checkout principal, que ya funcionaba y tenía que seguir funcionando).

## Los otros seis tableros

`grep -n "RAIZ.parent" scripts/aceptacion.py` en cada uno:

| tablero | apariciones | veredicto |
|---|---|---|
| `cn-ralph` | 3 | **mismo defecto, hoy inocuo**: es un worktree de este mismo repo en `proyectos/cn-ralph`, así que su `RAIZ.parent` ya es `proyectos` por posición. Es el mismo fichero versionado: el arreglo le llega cuando `ralph/cn` integre. No se toca su copia — tocar un árbol hermano es el fallo que persigue este documento. |
| `eu-ralph` | 0 | limpio |
| `mcp-ralph` | 0 | limpio |
| `mcp_smart_context` | 0 | limpio |
| `ponerse_wenorro/backend` | 2 | **NO es el mismo defecto.** Ahí `RAIZ` es `backend/`, así que `RAIZ.parent` significa «la raíz de MI repo» (comprobado: hay `.git` en las tres), y se usa como `git -C`. Eso es relativo al propio árbol y es correcto en cualquier worktree. No se toca. |
| `pw-ralph/backend` | 2 | igual que el anterior. No se toca. |
