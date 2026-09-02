# «Cambian de color según la carga» era falso: no cambia ni uno

**Decisión de G, 2026-09-02.** Este doc guarda el **porqué**. El **qué** vivía en la cola
(`cn-ralph/PENDIENTES.md`, sección BLOQUEADAS) hasta que G lo desbloqueó.

## El aviso que llevaba dos días dirigiendo mal la investigación

Desde el 2026-08-31 la ronda avisaba de esto, y el número crecía — 16 por la mañana, 22 por la
tarde:

```
TABLEROS: 22 comprobador(es) cambian de color segun la carga (...)
          — no es un rojo, es un comprobador roto
```

Se midió: los 22, uno a uno, a solas, dos veces cada uno, en el mismo `cwd`, intérprete y entorno
que usa la ronda.

```
preguntados             22
cambian entre vueltas    0        ← ni uno
DESCONOCIDOS             5        ← su tablero no conoce el nombre
con veredicto estable   16        (15 verde, 1 rojo)
```

> **De los 22 no cambia de color ninguno.** La frase no describía lo que pasaba.

Y eso importa más que el bug, porque **un hallazgo mal nombrado dirige a quien venga detrás**. El
2026-08-30 se descartaron dos hipótesis —el arranque de procesos y la contención de ficheros— y
las dos miraban la MÁQUINA, porque eso es lo que dice «según la carga». No fallaron por mal
buscadas: fallaron porque no había nada que buscar ahí.

## La causa, probada llamando a la propia función

`reconfirmar()` pedía **todo el lote en una sola llamada**. `aceptacion.py` se para en el primer
nombre que no conoce (`desconocida:` por stderr, exit 2, sin veredictos), `leer_nombrados` exige
un veredicto por nombre pedido y devuelve `None`, y con `None` la función devolvía **todos** los
nombres en el primer hueco. En la rama de rojos nuevos ese hueco es `confirmados` y es seguro; en
la de `resueltos` es `aun_rojos`, y de ahí al cubo de inestables.

```
A · el lote de mcp tal cual lo pide la ronda (11 nombres, 2 desconocidos)
        -> confirmados 11 · dudosos 0        los 11 a INESTABLES enteros
B · el mismo lote sin los dos desconocidos (9 nombres)
        -> se lee perfecto: 1 rojo de verdad, 8 verdes
C · contraprueba: el lote de cn-ralph, que no tenía desconocidos
        -> se lee perfecto
```

Las cuentas cuadran exactas, no aproximadas: **1 + 10 + 11 = 22**, cada lote con al menos un
desconocido, y el único tablero con el lote limpio —`cn-ralph`— fue el único cuyo `resueltos`
sobrevivió en `ultima.json`.

**Y se realimentaba sola**, que es por qué crecía: los `aun_rojos` se reescribían en
`ficha["rojos"]`, así que al día siguiente volvían a faltar en los rojos de hoy, volvían a leerse
como «resueltos», y volvían a envenenar el lote — arrastrando además a todos los que se hubieran
puesto verdes ese día.

## Lo que se decide

1. **La repregunta va de UNO EN UNO, un proceso por nombre.** Sin lote no hay acoplamiento: un
   nombre que el tablero no conoce sólo puede envenenarse a sí mismo. Es hacer el fallo
   imposible, no detectarlo. Cuesta ~35 s sobre los ~16 min que ya tarda la ronda.
2. **Un nombre que el tablero YA NO CONOCE es una tercera cosa: `jubilado`.** Ni rojo ni cierre.
   No se ha resuelto — **ha dejado de existir**, y meterlo en cualquiera de los dos montones
   miente. No se reescribe en `rojos`, que es lo que corta la realimentación, y se dice una vez
   en su propio apartado del informe y del aviso.
3. **Sólo cuenta como jubilación si el tablero lo dice DE ÉL, con su nombre.** Un
   `"desconocida" in err` casaría con la lista de `Conocidas:` que viene detrás y con un mensaje
   sobre otro nombre del mismo lote. Si el tablero cambiara su forma de decirlo, esto deja de
   reconocerlo y todo cae en «no se pudo leer», que **conserva la alarma**: la dirección del
   fallo es la segura a propósito — dejar de tirar un rojo bueno cuesta ruido, tirarlo cuesta el
   rojo.

## De dónde salen los jubilados, y por qué va a volver a pasar

Las dos causas son legítimas, y ninguna es un error:

| | |
|---|---|
| **jubilar bien un comprobador** | `aae4054` (29-ago) retiró `inv-mode-max-mode-pro-cero` e `inv-route-task-herramienta-mcp-con` por decisión de G. Su propio mensaje dice «retirar bien no es borrar» |
| **nacer en un árbol y no en el otro** | `sabotaje-del-cableado` está 4 veces en `cn-ralph/scripts/aceptacion.py` y 0 en `capa-normativa/scripts/aceptacion.py` |

Por eso no bastaba con limpiar la lista a mano: **retirar un comprobador envenenaba su tablero de
forma permanente**, y retirar comprobadores es algo que esta casa hace a propósito.

## Lo que esto tapaba, y es la razón de que corriera prisa

`el-indice-no-traga-colas-del-robot` salía ROJO a solas —«job_hunter=75»— **escondido dentro del
cubo de inestables**, que es justo el cubo del que se decidió no avisar. Es la clase de rojo que
ya costó dos días de gate parado en agosto.

## Lo que este arreglo NO promete

Que la ronda siga corriendo sola. Eso sólo lo demuestra la siguiente pasada **programada**: el
comprobador `ronda-de-tableros` únicamente acepta como evidencia los informes lanzados con
`--programada` por la tarea de Windows. Una corrida a mano demuestra que el guion lee bien el
lote, que es otra cosa. **Las dos mitades se declaran por separado a propósito**, porque un verde
que se presenta entero sin serlo es exactamente lo que este arnés existe para cazar.

## Lo que queda fuera, y por qué

Enseñarle al tablero a contestar «no la conozco» como **tercer estado** (⚪ `MUDO` ya existe en la
ronda y `leer_tablero` ya sabe leerlo, así que sería propagarlo y no inventarlo). Es la más cara
de las tres, toca las cinco puntas —el tablero tiene que decirlo y la ronda leerlo— y las dos de
arriba ya cierran el agujero. Se deja escrita aquí para que no se redescubra.
