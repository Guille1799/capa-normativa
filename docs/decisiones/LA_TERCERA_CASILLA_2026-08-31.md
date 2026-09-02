# La tercera casilla, y el inspector que hablaba un idioma que aquí no se usa

**2026-08-30 / 09-01.** Tres decisiones durables sobre el contrato del tablero y sobre cómo se
verifica a los verificadores. Las tres salieron de medir, y las tres corrigen algo que yo mismo
había afirmado con seguridad unas horas antes.

---

## 1 · El tablero pasa de dos casillas a tres

**Decisión.** Un comprobador puede devolver `True`, `False` o **`None`** (⚪ MUDO). El tablero sale
con **3 = NO CONCLUYENTE** cuando hay mudos y ningún rojo.

**Por qué.** El contrato era `tuple[bool, str]`. Y entonces *«no he podido mirar»* no tenía dónde
ir: como aquí está prohibido aprobar en vacío, acababa en ROJO — la misma casilla que *«he mirado
y está mal»*, que es una cosa completamente distinta.

**La medida que lo destapó.** La ronda del 2026-08-30 marcó 12 comprobadores que salían rojos
durante la ronda y verdes al repreguntarles a solas. Al mirarlos: no eran 12 sino **10 distintos**
(`mcp-ralph` es un worktree de `mcp_smart_context` y se contaban dos veces), **2 ya ni existían**,
y ninguno mentía sobre su promesa — mentían sobre **haber podido medirla**.

**Lo que la hace legítima, y no un descanso.** Un mudo:

- **no cuenta como promesa cumplida** (`1/2`, no `2/2`),
- saca al tablero de cero,
- **un rojo le gana**: con una infracción real delante, no poder medir otra cosa no rebaja nada,
- y una **excepción sigue siendo ROJO**, no mudo: un comprobador roto no se perdona.

**La cuenta atrás, decidida por G.** Un mudo que insiste asciende a ROJO — no por la promesa que
vigila, sino **por el vigilante**: uno que nunca consigue medir está muerto aunque jamás haya
dicho una mentira.

> **2 días DISTINTOS en los que la ronda CORRIÓ**, mudo en los dos, sin ninguna medición conseguida
> entre medias.

El denominador es de G y es el corazón de la regla:

> *«2 días, pero que esos días se haya trabajado — si no, en un finde que no curre va a saltar.»*

Tenía razón. La primera versión contaba tiempo de calendario, y con eso un fin de semana sin rondas
hacía que el lunes, **al primer tropiezo**, el contador marcara tres días y saltara. El vigilante no
había fallado dos veces: le habían preguntado una.

De ahí salen las otras dos: varias rondas del mismo día cuentan como una, y **lo resetea cualquier
medición conseguida, incluido un ROJO** — un rojo significa que sí consiguió mirar.

**Compatible hacia atrás a propósito.** `True`/`False` significan lo mismo que siempre y `None` es
opcional. Los otros cuatro repos pueden adoptarlo sin tocar sus comprobadores.

⚠️ **Y hay que enseñárselo a las dos a la vez.** `leer_tablero()` CONTRASTA los emojis contados
contra la línea de resumen; sin conocer la marca nueva contaría 1 verde + 0 rojos contra un total
de 2 y declararía el tablero **ILEGIBLE**. El tablero aprende a hablar y la ronda se queda sorda.

---

## 2 · El pase de mutación NO se retira: estaba dormido, no muerto

**Decisión.** `--verifica` conserva `ARTEFACTOS` y su mutación. Lo único que cambia es **lo que
dice**.

**La premisa que resultó falsa.** Se iba a jubilar por muerta: `ARTEFACTOS` vacío, `0/0
verificados` —que en un informe se lee como un 100 %— y sin forma de revivir, porque su única
mentira es *plantar un fichero* y ninguno de los comprobadores de esta casa mira el suelo: todos
preguntan a git, a GitHub o al sistema operativo.

**Lo que dijo su historia, mirada en vez de razonada.** En los commits `4376c18` y `a71b5e0`
tuvo **una entrada real**: `inv-para-que-el-healthcheck-si-el-tablero`, cuya aceptación era
escribir un documento. Se plantó el fichero, el comprobador se puso verde, quedó verificado. Luego
la promesa se cumplió, pasó a `CUMPLIDAS`, y **la lista se vació sola**.

> Sirve para **promesas pendientes cuya aceptación es un artefacto con nombre**, y volverá a
> llenarse la próxima vez que nazca una. Retirarla por estar vacía habría sido tirar algo que
> funciona.

**Lo que sí se arregla.** El `0/0` deja de viajar solo: el significado va pegado, en la misma
línea, donde no se puede leer sin él. Se conserva la forma «N/M verificados por mutación» porque
`ronda_de_tableros.py` la busca literalmente.

---

## 3 · Cómo se verifica de verdad a un comprobador que ya funciona

**Decisión.** Nace `sabotaje-del-cableado`: coge cada pieza de cableado del tablero, le **voltea
sus `return False`** —dejándola físicamente incapaz de dar un veredicto negativo— y corre la suite
entera. Si nadie protesta, esa pieza no la vigila nada.

**Por qué esta forma.** La máquina vieja intenta engañar al comprobador **por fuera** y sólo sabe
atacar a uno que esté ROJO de partida. Contra uno verde no tiene ataque — y el proyecto existe para
poner todo en verde. Ésta le opera **por dentro**, y por eso funciona justo donde la otra no llega.

**El argumento que la decidió, y no es de opinión.** Se midió **seis veces por métodos estáticos**
qué partes del arnés estaban probadas —si un test *nombra* una función, contar `except` por su
forma, un `grep`—. **Las seis salieron falsas**, y las seis eran plausibles: números redondos con
nombres de verdad al lado. Dos llevaron a proponer un trabajo diez veces mayor del necesario y una
a proponerlo diez veces menor.

Lo único que dijo la verdad, siempre, fue romper la pieza y ver quién gritaba:

| pieza | comprobadores | ¿alguien protesta? |
|---|---:|---|
| `_delega` | 7 | **nadie** |
| `_fabrica_bug` | 12 | sí |
| `_fabrica_inv` | 9 | sí |
| `canario_de_los_hooks` | 1 | sí |
| `guardia_de_commit` | 1 | sí |
| `revista_de_runtimes` | 1 | **nadie** |

Ocho comprobadores colgando de dos piezas que no vigilaba nada. **Los dos agujeros quedaron
cerrados** el 2026-09-01 (`tests/test_delega.py`, `tests/test_revista_de_runtimes_traduce.py`).

### Las cuatro guardas que la hacen fiable, todas nacidas de un fallo real

1. **El juez tiene que estar sano antes de juzgar.** Se corre la suite sin mutar nada primero: si
   ya falla, protestaría igual ante cualquier sabotaje y esto saldría VERDE sin haber medido nada.
2. **El tablero vuelve intacto**, comprobado por huella. Si se quedara a medias, el repo tendría
   *todos* los guardianes incapaces de decir que no, y en silencio.
3. **La mutación no puede tocar nada más que la mutación.** `return False` → `return True` quita
   exactamente un byte por volteo; cualquier otro tamaño y **no se mide**. Nace de un fallo real:
   la primera versión escribía con `write_text`, que sobre un fichero con CRLF produce `\r\r\n` en
   cada línea. Corrompía las 1.169 del tablero, la suite protestaba **por la corrupción**, y el
   comprobador dio un VERDE perfecto diciendo que las 9 piezas estaban vigiladas cuando dos no lo
   estaban. Un verde falso dentro del comprobador escrito para cazar verdes falsos.
4. **Sus propios tests no pueden hacer de oráculo.** Leen `scripts/aceptacion.py` como *dato*, así
   que cualquier mutación los rompe — y un test que falla porque **el texto cambió** no verifica
   **comportamiento**. Contarlos daba `_delega` por vigilado cuando no lo estaba.

**Y una memoria, por supervivencia.** El pase son ~10 min. Un guardián que cuesta diez minutos al
día se desactiva «un momento» y no vuelve. Recuerda su veredicto mientras ni el tablero, ni un solo
test, ni **su propio código** cambien — las tres cosas que pueden cambiar la respuesta. Un verde
recordado lo dice. Un MUDO no se recuerda: no es una medición.

---

## Lo que NO decide este documento

- Qué se hace con `eu-ralph`, que perdió su arnés al limpiarse el repo público y lleva días con el
  robot muerto. Está en la cola; es de otro repo.
- Cuándo se integra y empuja: `main` local y el remoto divergieron mientras se trabajaba.

## La lección del día, que vale más que las tres decisiones

**Siete instrumentos rotos en una sesión**, todos míos, todos creíbles, y todos con la misma forma:
**leer la etiqueta de la caja en vez de abrir la caja**. Lo único que no falló ni una vez fue
romper algo y ver quién grita.
