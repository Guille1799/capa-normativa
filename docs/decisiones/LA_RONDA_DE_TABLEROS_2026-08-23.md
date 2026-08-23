# Un guarda que nadie ejecuta es decoración

**2026-08-23.** El censo de lo que corre solo en esta máquina salió así:

| corre solo | no corre solo |
|---|---|
| el `pre-commit` de los cinco repos, en cada commit | **los siete tableros de aceptación completos** |
| los tres Ralph de madrugada (23:00 / 23:30 / 00:00) | |
| `ContextWatcher-Healthcheck`, cada 30 min | |

Los tableros son el instrumento con el que este arnés decide si una promesa está cumplida. Y eran
justamente lo único que dependía de que alguien se acordara de lanzarlo.

> Un guarda que nadie ejecuta es decoración. Puede llevar semanas en rojo sin que nadie se entere,
> y entonces no protege de nada — sólo **parece** que protege, que es peor que no tener nada,
> porque ocupa el sitio de la protección que sí harías.

Este documento es lo que se montó y, sobre todo, las seis decisiones que no eran obvias.

## Lo que hay ahora

| pieza | dónde |
|---|---|
| el lanzador | `capa-normativa/scripts/ronda_de_tableros.py` |
| el envoltorio de la tarea | `proyectos/ronda_de_tableros.cmd` |
| la tarea de Windows | `ronda-de-tableros`, diaria a las 08:30 |
| los informes | `proyectos/.rondas/` — `ULTIMA.md`, `ultima.json`, 30 `ronda-*.md` |
| la promesa | `capa-normativa/scripts/aceptacion.py tableros-corren-solos` |
| el comprobador | `capa-normativa/scripts/aceptaciones/tableros_corren_solos.py` |
| sus pruebas | `tests/test_ronda_de_tableros.py` + `tests/test_tableros_corren_solos.py` |
| su entrada de censo | `proyectos/REGISTRO.md` |

Las 08:30 no son arbitrarias: van **después** de la ventana de los tres Ralph, así que la ronda
mide el mundo que dejó la noche, no el que está a medio hacer.

## Decisión A · El exit code dice si la RONDA corrió, no si los tableros están verdes

La tentación es salir 1 cuando hay rojos. Sería un error, y de los que se cobran tarde: la tarea
de Windows aparecería fallando **todas las mañanas**, `LastTaskResult` dejaría de significar nada
y en dos semanas nadie miraría ni la tarea ni los informes.

Los rojos son el **dato** que la ronda recoge; que haya rojos es lo normal y no es una avería suya.
La ronda sale != 0 sólo cuando no pudo hacer su trabajo: cero tableros descubiertos, o no se pudo
escribir el informe.

Eso deja `LastTaskResult == 0` como una señal limpia, y por eso la promesa la puede usar.

## Decisión B · Se avisa en el CAMBIO de estado, y la lección tiene número

`inv-el-healthcheck-avisa-cada-30` midió el caso: **19 avisos en 19 corridas por UNA sola causa
que no cambiaba**. Avisar cada pasada por lo mismo no informa — entrena a ignorar, y entonces el
aviso que sí importa tampoco se lee.

La regla entera vive aislada en `decidir_aviso()`, que es una función pura de tres líneas para que
se pueda comprobar sin montar nada:

- la **firma** es el conjunto de rojos, por NOMBRE. Cambiar tres rojos por otros tres distintos es
  un cambio de estado, y contarlos no lo vería;
- se avisa cuando la firma cambia;
- y como mucho una vez por semana si el rojo se enquista, para que un rojo viejo no desaparezca
  del todo sin convertirse en ruido diario.

## Decisión C · Dos sesiones atacaron esto a la vez, y se integra — no se acumula

A las 18:57 de ese mismo día, **otra sesión commiteó en `main` la promesa** `tableros-corren-solos`
(commit `b807021`) para este mismo objetivo: el examinador, sin la implementación. Esta sesión
había salido del commit anterior y estaba construyendo el lanzador, con su propia promesa.

Se descubrió por accidente y por el mecanismo: la primera ronda real corrió el tablero de
`capa-normativa` en el checkout principal y en su lista de rojos apareció un nombre que yo no había
escrito.

**Se integran en una sola promesa, no en dos.** Dos promesas para el mismo mecanismo en el mismo
tablero se contradicen en cuanto alguien toca una, y la duplicación no se ve hasta que ya ha hecho
daño. Sobrevive `tableros-corren-solos` —llegó primero y su nombre es mejor— y la ronda pasa a ser
su implementación. Hay un test que lo sujeta: `test_la_ronda_NO_añade_una_promesa_propia_al_tablero`.

### Lo que la otra sesión pedía y yo no había construido: `--verifica`

Su promesa exigía dos cosas, y la segunda es buena y no estaba en el encargo: que **`--verifica`
también corra solo**. Es quien comprueba que cada comprobador sigue sabiendo ponerse rojo; tableros
corriendo solos con comprobadores que ya no saben fallar son verdes que no significan nada.

Así que la ronda lo corre ahora en cada tablero, y su resultado va al informe.

**Pero su fallo NO pone roja la promesa**, y la distinción es la que costó cinco tareas incerrables
el 2026-08-22: `--verifica` puede salir 1 porque un comprobador de *otro* repo se ha estropeado, y
eso no dice nada sobre si la ronda corre sola. Lo que se exige es que **haya corrido**. Que empiece
a fallar entra en la firma del aviso — se avisa del cambio, que es el canal correcto, en vez de
bloquear un tablero con un rojo ajeno.

### 🔎 Lo que hay que revisar de esto: se le cambió el examinador a otro

La versión original de `tableros_corren_solos.py` preguntaba **sólo** al Programador de tareas, y
dejaba escrito por qué: *«no se puede dictar el formato del informe de un trabajo que aún no está
hecho»*. Ese motivo caducó al existir el informe — y con él caducó su punto débil: buscar
`aceptacion.py` dentro de la cadena de la acción es buscar una **subcadena**, y una tarea puede
arrancar, salir 0 y no haber corrido ni un tablero.

Ahora pide las dos mitades. Contra las tres preguntas de `ARREGLAR_EL_EXAMINADOR_2026-08-23.md`:

1. **¿La lógica del exit code es la misma?** Sí: sigue exigiendo que algo dispare los tableros y
   que `--verifica` corra. Se le añade una condición, no se le quita ninguna.
2. **¿Lo que era rojo legítimo sigue rojo?** Sí — comprobado ejecutándolo: hoy sale rojo, y los
   seis tests originales siguen en verde (dos de ellos ahora con el informe inyectado, para que
   fallen por su motivo y no por otro).
3. **¿El cambio está en la parte que impide EJECUTAR, no en la que decide APROBAR?** Aquí no: está
   en la que decide aprobar, y **la endurece**. Eso no es ablandar, pero sí es tocar el examinador
   de otro, así que queda marcado para que G lo mire.

## Decisión D · La promesa pide EVIDENCIA DE EJECUCIÓN, y hacen falta las dos mitades

Este error ya lo cometimos: con `ollama_chain` se dio por bueno un hook porque estaba
**registrado**, y llevaba meses sin arrancar ni una vez. Registrar es una intención; arrancar es un
hecho.

Así que `tableros-corren-solos` exige dos cosas **a la vez**, porque cada una tapa el agujero de la
otra:

1. el `LastRunTime` que Windows guarda de la tarea, fresco — *la tarea arrancó*;
2. un informe fresco que diga `lanzador: tarea-programada` — *y llegó al final y dejó rastro*.

Sin (1), un informe escrito a mano aprobaría la promesa. Sin (2), una tarea que arranca y muere en
la primera línea la aprobaría igual.

**Y no aprueba en vacío.** Si la ronda descubre cero tableros —o menos de los siete que tiene que
cubrir— es ROJO. Aprobar por no haber encontrado nada es el modo de fallo más caro de un guarda,
porque su silencio se lee como buenas noticias.

### La ventana: 48 horas, y el motivo es la decisión B otra vez

La ronda es diaria, así que 48 h tolera **una** ausencia —el portátil apagado un día entero— y
grita a la segunda. Más apretado produciría un rojo falso cada vez que G se va un fin de semana, y
un rojo falso recurrente es exactamente cómo se aprende a ignorar un tablero.

Por el mismo motivo la tarea se registró con `AllowStartIfOnBatteries`, apartándose del molde que
copia (`ralph-diario-mcp` y `ContextWatcher-Healthcheck` llevan la opción contraria): un guarda que
se calla cuando el portátil está desenchufado produce el silencio que este mecanismo existe para
impedir.

## Decisión E · El color viaja en un emoji, y un emoji se muere en una tubería

Los tableros imprimen `🟢` y `🔴`. Cuando se les captura la salida, Python escribe en la tubería
con la codificación de la consola (cp1252 aquí) y, como **todos** llaman a
`reconfigure(errors="replace")` —la defensa que se puso el 2026-08-21, cuando un `UnicodeEncodeError`
tumbó una aceptación correcta—, los dos círculos se degradan al **mismo `?`**.

O sea: la defensa contra un crash convierte, aguas abajo, verde y rojo en el mismo carácter. La
ronda contaría cero rojos y diría que todo está bien.

Dos medidas, y la segunda es la que importa:

1. se le fuerza `PYTHONIOENCODING=utf-8` al hijo, para que el emoji sobreviva;
2. **el recuento se contrasta contra la línea de resumen del propio tablero** (`N/M promesas
   cumplidas.`). Si no cuadran, el tablero se declara `ILEGIBLE`.

La primera es la que funciona hoy; la segunda es la que se entera el día que la primera deje de
funcionar. Confiar sólo en la primera sería el patrón que este arnés persigue entero: el
instrumento fallando en silencio y su fallo leyéndose como una medida.

## Decisión F · Los tableros se excluyen por REPO, no por carpeta — y esto se midió en vivo

En el disco hay **doce** `scripts/aceptacion.py` y en la ronda entran **siete**. Los cinco de fuera
se declaran con su motivo, en vez de filtrarse a mano, y además hay un barrido del disco: todo
tablero que no esté ni declarado ni excluido sale denunciado como **huérfano** y pone la ronda en
falta. Una lista escrita envejece en silencio; ésta no puede.

La primera versión excluía por nombre de carpeta las cuatro `JobHunter-*` que había. **Ocho minutos
después nació `JobHunter-herramienta`** —otro worktree del mismo repo, con su tablero dentro— y el
test de huérfanos falló. No fue un susto teórico: fue el mecanismo cazándose a sí mismo antes de
salir de la sesión.

La identidad se le pregunta a git (`rev-parse --git-common-dir`), no al parecido de los nombres,
por la misma razón que `arboles_hermanos`. Y al preguntarla apareció el mapa real, que no se veía
mirando carpetas: **los doce tableros son cinco repos.**

| repo | carpetas con tablero | en la ronda |
|---|---|---|
| `capa-normativa` | `capa-normativa`, `cn-ralph` | las dos |
| `eu-political-observatory` | `eu-political-observatory`, `eu-ralph` | sólo `eu-ralph` |
| `mcp_smart_context` | `mcp_smart_context`, `mcp-ralph` | las dos |
| `ponerse_wenorro` | `ponerse_wenorro/backend`, `pw-ralph/backend` | las dos |
| `JobHunter` | 5 carpetas y subiendo | ninguna |

Por eso hay dos listas y no una: `_REPOS_NO_VIGILADOS` saca un repo **con todos sus worktrees**
(JobHunter, que abre ramas a menudo), y `_CARPETAS_NO_VIGILADAS` saca una carpeta suelta cuyo repo
sí está vigilado por otra (`eu-political-observatory`, porque su tablero ya lo corre `eu-ralph` y
meter las dos duplicaría cada rojo).

## Por qué la promesa nace ROJA, y no es una formalidad

El lanzador viaja en la rama `claude/mystifying-mirzakhani-81a4bc`. La tarea apunta al **checkout
principal**, donde el guion todavía no está, así que hasta que la rama no se fusione en `main` la
tarea arrancará, no encontrará el guion, lo dirá en su log y saldrá 2.

Podría haberse apuntado la tarea al worktree para que saliera verde hoy. Habría sido exactamente el
fallo que `SONDAS_ATADAS_A_OTRO_ARBOL_2026-08-22.md` documenta, y además una mentira: la ronda no
corre sola hasta que corre sola.

Se pondrá verde ella sola la primera mañana que corra después de la fusión. Esa es la forma
correcta de que una promesa se cierre — porque el mundo cambió, no porque alguien la reescribió.
