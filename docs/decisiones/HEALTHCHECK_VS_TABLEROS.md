# Para qué sirve `healthcheck.py` si el tablero se verifica a sí mismo — 2026-08-26

**La pregunta, de G:** *«¿para qué tenemos el healthcheck? ¿No sería más sólido meter lo que hace en
la lógica de los tableros?»*

Nace de una comparación justa. Los dos vigilan, pero sólo uno se ataca a sí mismo:

| | tablero (`aceptacion.py`) | `healthcheck.py` |
|---|---|---|
| cadencia | diaria, 08:30 | cada 30 min |
| al fallar | ROJO; avisa al CAMBIAR de color | crea tarea-CONTRATO en la cola del robot |
| se verifica a sí mismo | **sí** (`--verifica`, mutación) | **no** |

## El veredicto

**El healthcheck se queda.** Pero no por la razón que parecía —la cadencia— sino por una anterior:
**vigila una clase distinta de cosa.**

Un tablero vigila **promesas**: cosas que sólo cambian si alguien las cambia. Un healthcheck vigila
**el mundo**: cosas que se rompen solas. La prueba de una línea, que es la que hay que aplicar ante
cualquier vigilancia nueva:

> **¿Esto puede cambiar mientras duermes, sin que nadie toque nada?**

Y no es teoría. El **2026-08-25 a las 14:00**, `ContextWatcher-Reindex` murió con `0xC0000005` y
dejó un `.reindex_lock` huérfano que tuvo el índice sin reindexar **5 h 26 min**. Ninguna promesa
se rompió. Nadie cambió una línea de código. **El tablero habría dicho verde, y con razón.**

## Veredicto por cada uno de los nueve checks

| check | ¿cambia mientras duermes? | dónde va |
|---|---|---|
| **HTTP Server** | Sí — el proceso muere solo | healthcheck |
| **SQLite** | Sí — el recuento se mueve con cada indexado (16.135 → 16.149 en una noche) | healthcheck |
| **LanceDB** | Sí — y además es el que mató el proceso el 25-ago | healthcheck |
| **Sync** | Sí — los tres índices se desalinean durante el indexado | healthcheck |
| **Ultimo reindex** | Sí — es tiempo puro: «hace N min» crece solo | healthcheck |
| **Procesos** | Sí — un proceso se cae sin avisar | healthcheck |
| **Fuga AppX** | Sí — una fuga de handles crece sola | healthcheck |
| **Proyectos** | **No** — las rutas sólo cambian si alguien edita el config o mueve una carpeta | **tablero** |
| **Docs freshness** | **No** — un CORE queda viejo cuando alguien escribe un checkpoint | tablero, pero **se queda** (ver abajo) |

**Siete de nueve** vigilan cosas que se rompen solas. Ésa es la respuesta: fundirlo en los tableros
no sería más sólido — sería perder siete vigilancias o darle a un tablero una cadencia de 30 min
que no necesita para el 90 % de lo que mide.

## Los dos que están en el sitio equivocado, y qué se hace con cada uno

**`Proyectos` → mover al tablero.** Es una promesa pura: las rutas de los seis proyectos no se
mueven solas. Preguntarlo 48 veces al día no aporta nada.

**`Docs freshness` → se queda donde está, y a propósito.** Por la prueba le tocaría el tablero. Pero
es el único check enchufado al **encolado automático**: detecta, crea la tarea-CONTRATO en la cola
del robot, deduplica por firma y calla. Medido el 24-ago: 71 detecciones de la misma causa, 1 tarea
creada, 0 avisos a G. Esa fontanería funciona y moverla costaría más de lo que la pureza vale. Se
deja escrito que está fuera de sitio para que no se descubra dentro de un año como si fuera un
error.

## Y el movimiento contrario, que es el que faltaba

**`guardianes-vivos` está en el tablero y vigila el mundo.** Comprueba si las tareas programadas
siguen vivas — y una tarea se muere sola. Por la prueba, su sitio es el healthcheck.

No es una sutileza: es exactamente lo que falló. El reindexado reventó a las 14:00 y quien lo
vigila corre en la **ronda diaria**, así que el rojo se quedó esperando a la mañana siguiente. Se
descubrió a las 19:30 mirando a mano.

Por la regla de [QUE_INTERRUMPE_Y_QUE_ESPERA](QUE_INTERRUMPE_Y_QUE_ESPERA_2026-08-25.md) —*«lo que
bloquea que me interrumpa»*— un guardián muerto **bloquea**, así que su vigilancia no puede vivir en
un ciclo de 24 h.

## Lo que esta decisión NO resuelve

El healthcheck **no se verifica a sí mismo**, y eso sigue siendo cierto. El tablero tiene
`--verifica`, que muta sus detectores y exige que se pongan rojos; el healthcheck no tiene nada
equivalente. La consecuencia se vio el 25-ago: `check_lancedb` llevaba quién sabe cuánto abriendo el
índice a media reescritura, y sólo se supo porque el proceso murió de una forma tan violenta que
Windows dejó rastro.

Eso queda abierto, y merece su propia promesa.
