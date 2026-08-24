# Cerrar el CVE de verdad — la política de máquina, preparada y sin activar

**Fecha:** 2026-08-24 · **Estado:** LISTO PARA ACTIVAR · **Lo activa G**, no un agente

Continúa `HOOKS_ANTES_DE_CONFIAR_2026-08-24.md`, que retiró el guarda que no podía avisar y dejó
encolada la defensa real. Aquí está construida y verificada; falta un paso, y es de G.

## Lo que cierra

**CVE-2025-59536**: los hooks declarados en un `settings.json` se ejecutan **antes** de que aceptes
el diálogo de confianza de la carpeta. Abres un repo que no escribiste y su código ya ha corrido.

Y lo que hace imposible defenderse con configuración propia: la precedencia. Tu
`~/.claude/settings.json` es el **nivel 5**; el `settings.json` del repo ajeno es el **4**. La
documentación lo dice sin rodeos sobre el interruptor `disableAllHooks`:

> *«Ponerlo sólo en tus settings de usuario no basta, porque los settings del proyecto tienen
> precedencia sobre los tuyos y pueden volver a ponerlo a `false`.»*

El **nivel 1** —la política de máquina— es el único que un repositorio no puede pisar. Y
`allowManagedHooksOnly` es una clave *managed-only*: un proyecto ni siquiera puede intentar
declararla.

Efecto verificado contra la documentación de la v2.1.239:

| | |
|---|---|
| hooks de usuario, proyecto, local y plugins | **bloqueados** |
| hooks declarados en la propia política | **corren** |
| `disableAllHooks` desde fuera | **no puede apagar los gestionados** |

Esa última línea es el remate: un repo hostil tampoco puede apagar los tuyos.

## El problema que había que resolver, y no era mudar hooks

Con `allowManagedHooksOnly` todos los hooks tienen que estar declarados en la política. Los 9 de
usuario son rutas absolutas y viajan tal cual. Los 8 de proyecto se rompen, y de dos formas
distintas:

- Los de `eu` usan `$CLAUDE_PROJECT_DIR`. En un fichero **global** eso resuelve al proyecto
  **abierto**, así que buscarían su script dentro de `capa-normativa`, donde no existe.
- Los de `mcp` llevan ruta absoluta. En un fichero global **correrían en todos los proyectos** —
  incluido el gate de MRR de mcp dentro de `ponerse_wenorro`.

## La solución: un despachador por evento

La política declara **un** hook por evento: `.claude/hooks/despachador.py`. Él mira qué proyecto
está abierto y delega en los hooks de ESE repo.

**La tabla vive fuera de los repos** (`proyectos/.claude/hooks_por_repo.json`). Leerla del
`.claude/settings.json` de cada proyecto habría sido lo cómodo y habría reintroducido exactamente
el agujero que esto cierra: un repo ajeno declarando qué se ejecuta. La carpeta `proyectos/` no se
clona de ningún sitio; los repos de dentro, sí.

Tres detalles que no son adorno:

1. **Un repo sin entrada no ejecuta nada, y sale 0.** Ése es el caso de un repositorio recién
   clonado, y es justo lo que se quiere.
2. **Se propaga el PEOR código de salida, no el último.** Un hook que bloquea no puede quedar
   tapado por otro que pase después.
3. **Una tabla ilegible es un error ruidoso, no una tabla vacía.** Si un JSON roto devolviera `{}`,
   todos los guardianes de proyecto quedarían apagados y desde fuera se vería igual que «este repo
   no tiene hooks». Distinto de *no hay tabla*, que sí es un estado legítimo.

## Verificado antes de proponerlo

- **Reproduce exactamente lo de hoy**: para los 4 repos con hooks y sus 8 entradas, lo que el
  despachador devuelve es idéntico a lo que declara su `settings.json`. Nada se pierde.
- **12 tests** en `capa-normativa/tests/test_despachador.py`, incluidos los dos que importan: que
  los hooks de un repo no se cuelen en otro, y que una tabla ilegible no se lea como «sin hooks».

## Cómo se activa — LO HACE G

1. Copiar `proyectos/.claude/managed-settings.PREPARADO.json` a
   `C:\Program Files\ClaudeCode\managed-settings.json` (hace falta **administrador**).
2. Abrir una sesión nueva y ejecutar `/status`. La línea `Setting sources` debe decir
   `Enterprise managed settings (file)`.
3. Comprobar que los hooks siguen vivos: `python capa-normativa/scripts/aceptacion.py canario-de-los-hooks`.

⚠️ **Un agente no coloca ese fichero.** Es una política de seguridad del sistema, y su sitio pide
privilegios de administrador. Lo que sí se puede preparar y verificar es todo lo demás — y está.

## Lo que esto NO hace, dicho en voz alta

`git push --no-verify` y los flags de arranque siguen existiendo. Esto hace imposible el caso
**accidental** —abrir un repo y que se ejecute algo— no el deliberado de quien decide saltárselo.
Y `--bare` / `--setting-sources user` siguen siendo la respuesta correcta para abrir un repo
concreto en el que no confías nada.
