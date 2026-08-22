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
