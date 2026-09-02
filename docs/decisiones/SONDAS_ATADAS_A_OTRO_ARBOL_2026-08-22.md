# Cuatro comprobadores de capa-normativa juzgan el árbol equivocado

**2026-08-22.** Medido al clasificar las 52 tareas bloqueadas con `<proyecto-A>/bin/contratar.py`.

## Qué pasa

Cuatro comprobadores del tablero de `cn-ralph` escriben la ruta a mano:

| comprobador | ruta que hardcodea |
|---|---|
| `inv-revista-de-runtimes-quien-corre` | `~/proyectos/capa-normativa` |
| `inv-capa-normativa-es-el-unico` | `~/proyectos/capa-normativa/scripts/aceptacion.py` |
| `inv-autohealth-monitor-py-con-guion` | `~/proyectos/capa-normativa/scripts/aceptacion.py` |
| `inv-canario-py-aceptacion-py-verifica` | `~/proyectos/capa-normativa/scripts/aceptacion.py` |

El agente corre en `cn-ralph`, que es **otro worktree del mismo repo**. Así que arregla su copia
y el comprobador sigue mirando el checkout principal: **el veredicto no se mueve nunca**, la tarea
se bloquea, y no hay síntoma que apunte a la causa.

> Es exactamente el fallo que `ralph_aislado` existe para cazar, dentro de los comprobadores del
> propio arnés. En `<proyecto-B>` apareció la misma noche y en la misma forma: las tres sondas
> `AGUJERO-*` hardcodeaban la ruta a `<proyecto-B>` y se arreglaron derivándola de `__file__`
> (commit `3b129da` de `<proyecto-B>-robot`).

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

Derivar de `__file__`, como en `<proyecto-B>-robot`:

```python
SCRIPTS = Path(__file__).resolve().parent.parent   # en vez de la ruta escrita a mano
```

Y la señal de que el arreglo es correcto **no es que el comprobador se ponga verde**: es que siga
rojo mientras el agujero exista, pero ahora mirando su propio árbol. Las tres sondas de
`<proyecto-B>` siguieron rojas después de arreglarlas, y eso fue la confirmación, no el problema.

## Lo que NO se toca aquí

Otros tres comprobadores de este repo (`inv-audit-settings-source-sh-no`,
`inv-registro-md-session-start-sh`, `inv-capa-normativa-declarado-en-el`) salen `fuera-del-repo`:
su arreglo vive en `~/.claude/` o en `<proyecto-A>`. Ésos no son de puntería sino de permiso,
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
| `<proyecto-A>-robot` | 0 | limpio |
| `<proyecto-A>` | 0 | limpio |
| `<proyecto-B>/backend` | 2 | **NO es el mismo defecto.** Ahí `RAIZ` es `backend/`, así que `RAIZ.parent` significa «la raíz de MI repo» (comprobado: hay `.git` en las tres), y se usa como `git -C`. Eso es relativo al propio árbol y es correcto en cualquier worktree. No se toca. |
| `<proyecto-B>-robot/backend` | 2 | igual que el anterior. No se toca. |

---

# La tercera forma: la CONFIG del repo nombra UN árbol, y los worktrees son N

**2026-08-23.** Las tres sondas que quedaban después del arreglo anterior. Y aquí la decisión de
reparto que pedía la sección primera —*¿apuntar al árbol propio, o declararla en `permitidos`?*—
sale **la misma para las tres: apuntar al árbol propio.** El motivo se dice abajo.

## Qué pasa

| sonda | de dónde sale la ruta al árbol vecino |
|---|---|
| `guardia-de-commit` | `git config --get core.hooksPath` → `~/proyectos/capa-normativa/hooks`, absoluta |
| `inv-audit-settings-source-sh-no` | la ruta escrita a mano dentro de su campo de aceptación |
| `inv-canario-py-aceptacion-py-verifica` | ídem, y ésta **sí llegaba a ejecutarse** |

Las dos últimas son la sección primera otra vez, en dos entradas que se le escaparon. La primera
es nueva y es la interesante.

## Por qué `core.hooksPath` no se puede usar tal cual, nunca

`core.hooksPath` **no vive en el worktree**: vive en el `.git` común, así que los N árboles leen
el mismo valor. Y un valor único sólo puede nombrar una carpeta, o sea **un** árbol. Entonces una
sonda que lo use literalmente no es que se equivoque a veces:

> puede acertar en **1 árbol de N**, y falla en los otros N−1 por construcción.

Hoy N = 8 en este repo. Y desde los otros siete el fallo llegaba con la firma exacta que este
documento persigue: el agente añade su `hooks/pre-commit` en su copia, la sonda abre la del
vecino, no lo encuentra, dice ROJO, y el bucle deshace trabajo correcto.

### Y ni siquiera daba un rojo: reventaba

`RAIZ / <ruta absoluta>` **se traga el prefijo entero** — es la regla de `pathlib`, no un
descuido de quien lo escribió. Así que `hook` acababa siendo el del checkout principal, y el
`hook.relative_to(RAIZ)` de dos líneas más abajo lanzaba `ValueError`. Medido con los valores
reales de hoy:

```
RAIZ         C:\...\capa-normativa\.claude\worktrees\gracious-hellman-a92dc2
RAIZ / ruta  C:\...\capa-normativa\hooks\pre-commit          ← el árbol de al lado
relative_to  ValueError: ... is not in the subpath of ...
```

El tablero convierte esa excepción en `el comprobador falló: ValueError`, o sea otro rojo más.
Desde un worktree esta sonda **no medía nada**.

## Por qué NINGUNA de las tres va a `permitidos`

`permitidos` es para las sondas que miran fuera **a propósito** —un auditor cruzado del estilo
«todos los repos tienen su pre-commit»—. Ninguna de éstas lo es:

- `guardia-de-commit` juzga *el pre-commit de este repo*, y el árbol donde corre **es** este repo.
  Además es la sonda que un agente autónomo puede tener que arreglar: mandarla a mirar fuera es
  exactamente construir el rojo inarreglable.
- las dos `inv-*` invocan **este mismo tablero**. Correr el del vecino no tiene caso de uso.

La regla, por si vuelve a aparecer: *si la sonda juzga algo que quien la ejecuta podría arreglar,
tiene que mirar el árbol de quien la ejecuta.* `permitidos` es para lo que se audita, no para lo
que se arregla.

## El arreglo

`_en_el_arbol_propio(ruta)` **reancla**: si la ruta cuelga del checkout principal, se le quita
ese prefijo y se cuelga de `RAIZ`. Comparte con `_carpeta_de_proyectos()` la única pregunta a git
(`_checkout_principal()`, vía `--git-common-dir`), para que no haya dos sitios contestando lo
mismo.

Y tiene una segunda mitad que no es decorativa: **si la ruta NO cuelga del checkout principal, se
respeta tal cual.** Una carpeta de hooks compartida por varios repos es una configuración
legítima, y reanclarla sería inventarse un sitio. Sin esa mitad, «arreglar la puntería»
degeneraría en «traérselo todo a casa».

Las dos `inv-*` pasan a ruta relativa: su comando ya corre con `cwd=RAIZ`, así que la relativa
sigue a quien lo ejecuta, que es justo lo que se quiere.

## Aceptación

**La medida de arriba, con la sonda de verdad y desde este worktree:**

```
antes    🔴 sondas-miran-su-arbol  5 sonda(s) juzgan otro arbol: guardia-de-commit,
            inv-audit-settings-source-sh-no, inv-canario-py-aceptacion-py-verifica,
            registro-sin-caducados, revista-de-runtimes
después  🟢 sondas-miran-su-arbol  las 25 sondas miran su propio arbol        (exit 0, 33 s)
```

*(las dos últimas del «antes» son las de la sección anterior: su arreglo vivía en una rama sin
integrar, y la aceptación pedida —exit 0— era inalcanzable sin traerlo. Se integró.)*

Y tres tests, verificados por mutación deshaciendo cada arreglo por separado:

| test | mutación que lo tumba |
|---|---|
| `test_la_guardia_de_commit_juzga_el_pre_commit_de_SU_arbol` | volver a `RAIZ / ruta` → `ValueError` |
| `test_el_rojo_de_la_guardia_dice_DONDE_ha_buscado` | ídem |
| `test_una_carpeta_de_hooks_de_VERDAD_fuera_del_repo_se_respeta` | reanclar también lo de fuera |
| `test_ninguna_aceptacion_nombra_un_arbol_por_su_ruta_absoluta` | devolver la absoluta a un `_INV` |

El de los dos hooks distintos —permisivo en el vecino, gritón en el propio— no lee ninguna ruta:
distingue **cuál de los dos se ejecutó** por el veredicto. Un arreglo cosmético que sólo cambiara
el mensaje no lo pasa.

El último vive en `tests/test_inv_ejecutan_de_verdad.py`, con la familia de invariantes de `_INV`,
y es el que generaliza: prohíbe que **cualquier** aceptación nombre por ruta absoluta un árbol de
este repo. Dentro del repo, relativa; fuera, absoluta está bien. No caza la ruta escrita en una
máquina donde el repo viva en otro sitio — para eso está `sondas-miran-su-arbol`, que observa lo
que se toca en vez de leer el fuente.
