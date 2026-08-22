# Arreglar el examinador no es ablandarlo

**2026-08-23.** Respuesta a las siete tareas de `capa-normativa` que quedaron paradas esperando
decisión de G, y que él delegó ese día («contéstalas tú y documenta»).

## Las siete eran tres

Cinco de las siete preguntaban lo mismo con distinta ropa:

> *El comprobador que la ACEPTACIÓN nombra no existe, o su comando no es ejecutable. Arreglarlo
> exige tocar `scripts/aceptacion.py`, que es justo lo que el ⚠ del contrato PROHÍBE. ¿Cuenta como
> «arreglar el examinador» o me lo re-autorizas?*

Y las otras dos preguntaban por contenido: qué es la revista de runtimes, y cuál es la lista
canónica de guardianes.

## Decisión A · La frontera entre arreglar y ablandar

> **Ablandar es cambiar QUÉ se exige. Arreglar es conseguir que lo que se exige llegue a
> ejecutarse.** Lo primero sigue prohibido. Lo segundo está autorizado.

El ⚠ existe por un motivo concreto y medido: el 2026-08-21, con `encargo`, se aprobó una tarea
editando su prueba. Esa es la puerta que hay que tener cerrada. Pero cerrar también la puerta de
«el comando no arranca» tiene un coste que se midió la noche del 22: **nueve comprobadores en
cuatro tableros llevaban el comando entrecomillado en markdown**, cmd.exe contestaba que `` `python ``
no se reconoce, y el tablero traducía ese error a «pendiente». Ninguna de las nueve se podía cerrar
hiciera nadie lo que hiciera.

**La autorización viene con su comprobación, no con confianza.** Al desentrecomillar las nueve:

| resultado | n | qué significa |
|---|---|---|
| siguieron rojas | 5 | el arreglo no ablandó nada |
| pasaron a verde | 2 | el trabajo ya estaba hecho y nadie lo sabía |
| rojas por artefacto ausente | 2 | su rojo correcto |

Cero casos de «se puso verde sin haber trabajo». Ése es el dato que convierte esto en una regla y
no en una excusa.

### Cómo se distingue en la práctica, sin criterio

Tres preguntas mecánicas. Si las tres se responden que sí, es arreglo:

1. **¿La lógica del exit code es la misma?** Si el comprobador exigía A y ahora exige A, es
   arreglo. Si exige menos que A, es ablandar.
2. **¿Lo que era rojo legítimo sigue rojo?** Se comprueba ejecutándolo antes y después. Un arreglo
   que pone verdes las cosas es sospechoso hasta demostrar que el trabajo estaba hecho.
3. **¿El cambio está en la parte que impide EJECUTAR, no en la que decide APROBAR?** Quitar unas
   comillas de markdown, un prefijo de prosa o una ruta rota es lo primero. Bajar un umbral,
   quitar una condición o ampliar lo aceptable es lo segundo.

⚠️ Y una cautela que sale de esta misma noche: quien arregla el examinador **no debería ser quien
hace el trabajo en el mismo turno**. El agente que bloqueó `NUTRI-BUG-1` lo dijo mejor que yo —se
negó a registrar su propio comprobador porque sería *«juez y parte»*, y tenía razón. La regla que
lo hace mecánico: **el arreglo del examinador va en un commit distinto del arreglo que examina.**

## Decisión B · `contexto-propio` se retira, no se arregla

Estaba cumplida —existen sus tres piezas— y seguía en el tablero saliendo verde. Una promesa
cumplida y registrada deja `--verifica` en **rojo permanente para todo lo demás**, que es la forma
más rápida de que alguien deje de correr la verificación. Retirada a `CUMPLIDAS`, con fecha y
evidencia, para que quien cite el nombre viejo lea «cumplida el X» y no «desconocida».

Es el mismo tratamiento que ya recibieron `tokens-render`, `categorias-garmin` y
`plan-semanal-madre`. Deja de ser un caso y pasa a ser el procedimiento.

## Decisión C · `--verifica <nombre>` selecciona

Ignoraba el nombre y corría la mutación entera. Los contratos que lo citan pedían verificar SU
comprobador y recibían el veredicto de los otros treinta: **un rojo ajeno los hacía inaprobables
para siempre**. Ahora selecciona; sin nombre sigue corriéndolo todo; con un nombre inexistente,
exit 2.

## Las dos de contenido: medir en vez de decidir

Aquí es donde la delegación podía salir mal, porque inventarme un estado-objetivo y luego escribir
el examen que lo aprueba es exactamente ser juez y parte. La salida no es decidir mejor: es **no
decidir**.

**La revista de runtimes** preguntaba qué formato, qué cuatro intérpretes y qué significa «cuadrar».
No hay que elegirlo: hay que *medirlo*. El manifiesto no es una tabla de deseos, es el **registro de
lo que hoy resuelve cada intérprete**, y el comprobador no exige que los números sean unos
concretos — exige que **no hayan cambiado sin que nadie lo declare**. Así el examen no lo diseña
quien lo aprueba: lo dicta la máquina. Y nace rojo solo, porque hoy hay divergencia real y medida
(el venv de `mcp_smart_context` tiene `capa_normativa` **0.7.0** con el repo en **0.16.2**).

**La lista canónica de guardianes** tiene la misma salida: la lista canónica es la que está
registrada en `~/.claude/settings.json`, no una que yo escriba. La cifra objetivo es «los que haya»,
y la exigencia es que cada uno tenga su caso de carga envenenada. Si mañana se añade un hook, el
comprobador se pone rojo solo.

> Cuando una pregunta pide elegir un número, casi siempre hay una versión que lo mide en vez de
> elegirlo. Esa versión además no caduca.

## Lo que sigue siendo de G

Nada de lo de arriba toca criterio suyo. Lo que sí lo toca y se queda parado: los umbrales de salud
(`arreglo-polz-profundidad`, `nutri-bug-6`) y las candidaturas de JobHunter — donde **`cand-cir`
cierra el 2026-08-31**.
