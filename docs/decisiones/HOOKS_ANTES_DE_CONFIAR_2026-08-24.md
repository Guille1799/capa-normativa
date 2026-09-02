# El guarda que preguntaba por la autoría — CVE-2025-59536, y dónde está la puerta de verdad

**Decidido el 2026-08-24 por G.** Vigilado por `python scripts/aceptacion.py inv-audit-settings-source-sh-no`,
que sale ROJO si `audit_settings_source.sh` reaparece en disco o vuelve a registrarse en
`settings.json`.

## El problema

**CVE-2025-59536**: los hooks declarados en `settings.json` se ejecutan **antes** de que aceptes el
diálogo de confianza de la carpeta. Abres un repositorio que no escribiste y su código ya ha
corrido; no hay ventana para decir «no me fío».

La documentación de la v2.1.239 lo confirma sin rodeos. En la tabla *«qué se ejecuta antes de que
confíes en una carpeta»*, la fila de los hooks de ficheros de settings dice **`Used`**. Lo que se
arregló en la v2.1.218 fueron los hooks de *frontmatter* de subagentes y skills, no éstos.

## Lo que había, y por qué no servía

`~/.claude/hooks/audit_settings_source.sh`, 24 líneas: al arrancar la sesión miraba el historial de
git de `.claude/settings.json` y buscaba **commits de los últimos 7 días hechos por un email
distinto al del usuario**.

Preguntaba **quién** tocó el fichero, no **qué** dice. Con un solo desarrollador, ningún commit es
de otro, así que no puede dispararse nunca:

| caso | ¿lo ve? |
|---|---|
| `settings.json` envenenado sin commitear | no |
| commiteado por el propio usuario sin darse cuenta | no |
| escrito por un agente con su identidad de git | no |
| repo sin `.git` | no — se sale en la primera línea |

**Es un guarda que protege de un compañero de equipo que no existe.** Y eso es peor que no tener
nada: ocupa el sitio de la defensa real y da sensación de cobertura.

## Por qué ninguna configuración TUYA te salva

La precedencia de settings tiene cinco niveles. Los relevantes:

```
1. managed-settings.json      ← política de máquina
2. línea de comandos          ← --bare, --setting-sources, --settings
3. .claude/settings.local.json
4. .claude/settings.json      ← EL REPO AJENO
5. ~/.claude/settings.json    ← el tuyo de siempre
```

Tu configuración es el nivel **5**; la del repo ajeno, el **4**. Por eso la documentación avisa,
literalmente, sobre el interruptor `disableAllHooks`:

> *«Ponerlo sólo en tus settings de usuario no basta, porque los settings del proyecto tienen
> precedencia sobre los tuyos y pueden volver a ponerlo a `false`.»*

Y las listas **se fusionan** en vez de sustituirse, así que tampoco se pueden «quitar» los hooks del
proyecto declarando otros. Por eso lo único que quedaba era detectar — y de ahí venía el guarda.

## La decisión

**Retirado.** Desregistrado de `settings.json` (hooks 10 → 9, el de `SessionStart`) y borrado del
disco. El comprobador deja de pedir trabajo y pasa a vigilar que no vuelva.

Se reparó además su comando, que estaba **roto a propósito**: iba escrito como
`Si se retira: \`comando\` — prosa`, y `_solo_el_comando` sólo desnuda lo que **empieza** por
comilla, así que devolvía la frase entera y el shell no la entendía. Rojo pasara lo que pasara. Era
deliberado mientras retirar un control de seguridad fuese decisión pendiente de G. Tomada la
decisión, repararlo es lo correcto.

Y el `xfail(strict=True)` de `_ROTOS_DECLARADOS` hizo exactamente su trabajo: **falló el mismo día**
y obligó a sacar la excepción en vez de dejarla de adorno. `_ROTOS_DECLARADOS` queda vacío.

## Lo que queda encolado, y ya investigado

La defensa real **no es un detector**: es cerrar la puerta en el nivel 1, que ningún repositorio
puede alcanzar. Dos claves *managed-only* —un proyecto ni siquiera puede intentar ponerlas:

| clave | efecto |
|---|---|
| `allowManagedHooksOnly` | sólo corren los hooks declarados en la política gestionada |
| `strictPluginOnlyCustomization.hooks` | bloquea hooks de fuentes de usuario **y** de proyecto |

Efecto verificado de `allowManagedHooksOnly: true`:

- hooks de **usuario, proyecto, local y plugins** → bloqueados
- hooks declarados **dentro del propio `managed-settings.json`** → siguen corriendo
- plugins forzados en `enabledPlugins` de la política → exentos
- estrecha también `statusLine`, `fileSuggestion` y `subagentStatusLine` a la política
- desactiva plugins de fuente `command` salvo `disableCommandPluginSources: false`
- y **`disableAllHooks` no puede desactivar los hooks gestionados desde fuera**: un repo hostil
  tampoco puede apagar los tuyos

Ruta en Windows: `C:\Program Files\ClaudeCode\managed-settings.json`. La documentación reconoce el
caso: *«un desarrollador que es administrador de su máquina puede editar la fuente gestionada»*.

### El coste, medido — por eso NO se hizo hoy

No son 10 hooks: son **18**, y ocho necesitan una guarda que hoy no tienen.

```
usuario  (~/.claude/settings.json)          9 hooks   (eran 10)
proyecto A · su worktree del robot        2+2       usan $CLAUDE_PROJECT_DIR
proyecto B · su worktree del robot        2+2       rutas absolutas + --project <nombre>
```

En un fichero **global**, los de `eu-*` buscarían `preuse_dispatcher.py` en el proyecto que esté
abierto —donde no existe— y los de `mcp-*` correrían el gate de mcp **en todos los proyectos**.
Consolidarlos exige darles una guarda por repositorio. Es un trabajo con su propio diseño y sus
propias pruebas, no un ajuste.

⚠️ **El fichero de `C:\Program Files` lo coloca G**, no un agente: es una política de seguridad del
sistema. Lo que sí se puede preparar y verificar aquí es el JSON exacto.

## Lo que se aprende, más allá de este hook

**Un guarda que pregunta por la identidad del actor no protege a quien actúa solo.** La pregunta
útil casi siempre es sobre el CONTENIDO, no sobre la procedencia.

**Y antes de mejorar un detector, hay que preguntar si la puerta se puede cerrar.** Las tres
primeras salidas que se plantearon aquí —arreglarlo, retirarlo, declararlo inútil— eran todas
«detectar mejor». La cuarta, la única sólida, era de otra categoría.
