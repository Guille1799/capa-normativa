# «Migrar el repo a inglés» no es una tarea: son cuatro, y una puede ser un NO

**Fecha:** 2026-09-10 · **Lo levanta:** G · **Estado:** decidido el ENCUADRE, no el trabajo

## El punto de partida

G, mirando el GitHub: *«el repo está en español, y todos deben estar en inglés»*. Es cierto y el
motivo es sólido — los seis repos públicos los abre un reclutador, y el estándar del oficio es
inglés.

Lo que se decide aquí **no es hacerlo** (no se hace ahora, G está en `mcp_smart_context` con
cambios que afectan a los cinco proyectos). Lo que se decide es **cómo se mira el problema**,
porque tratarlo como una sola tarea lleva a un trabajo enorme y a un `force-push`.

## La decisión: se descompone en capas, y cada una se decide por separado

| capa | qué es | quién la ve | precio |
|---|---|---|---|
| **1 · superficie** | README, título y descripción del repo | lo primero, y a menudo lo único | barato, impacto máximo |
| **2 · nombres** | funciones, clases, ficheros | quien entra en el código | **caro y arriesgado** |
| **3 · prosa interna** | docstrings y comentarios | quien lee un fichero | caro en tiempo, cero riesgo |
| **4 · historial** | mensajes de commit | quien mira la pestaña de commits | **puede que imposible** |

El valor de la tabla no es ordenar: es que **las cuatro tienen precios que no se parecen en nada**,
así que una decisión única sobre «el idioma del repo» sería cuatro decisiones tomadas a la vez sin
mirarlas.

## Las dos restricciones que hay que llevarse decididas

### La capa 4 es un NO por defecto

Los commits **ya están publicados**. Cambiarlos es reescribir historia, y sobre historia publicada
eso es un `force-push`: la operación sin vuelta atrás que este proyecto ha evitado siempre —
está escrito en la memoria como *«sacar algo del historial es gratis hasta que empujas; después es
un force-push»*.

Así que la respuesta por defecto a *«¿traducimos los commits?»* es **no**, y cambiarla exige que G
lo decida explícitamente sabiendo el precio. Un historial en español no le cuesta el puesto a
nadie; un `force-push` sobre un repo público sí puede romperle el clon a quien lo tuviera.

### La capa 2 tiene un hilo largo que no se ve

`escaparate_sin_rutas_de_casa` no es sólo un nombre de fichero. Aparece en el tablero, en sus
tests, en las exenciones declaradas, en los documentos de decisión — y **en los otros cuatro repos
que comparten el arnés**.

O sea que renombrar en uno solo **desincroniza las cinco copias**, y eso lo caza
`piezas-compartidas-al-dia`, que compara el código canónico entre repos. La migración de nombres o
es **coordinada en los cinco a la vez**, o rompe una guarda que funciona.

Eso convierte la capa 2 en una decisión de arquitectura sobre cinco repos, no en una traducción.

## Lo que NO se sabe, y se dice

Se lanzó un medidor por capas sobre los seis repos públicos y **no había terminado al cerrar la
sesión** (`eu-political-observatory` es enorme). Así que **hoy no se sabe cuánto español hay ni en
qué capa está**, en ninguno de los seis.

Por eso no hay aceptación para las capas 2 y 3: escribirla sin saber el tamaño sería inventarse el
trabajo. El primer paso al retomar es **terminar de medir**, no empezar a traducir — puede que dos
de los seis ya estén en inglés y el trabajo real sea mucho menor, o mucho mayor.

## Por qué esto está aquí y no sólo en la cola

La cola (`PENDIENTES.md`) está fuera de git a propósito: es el cuaderno interno. Pero el
**encuadre** —las cuatro capas, el NO por defecto de la 4, y el hilo cruzado de la 2— es
razonamiento durable que sobrevive a la tarea, y perderlo obligaría a redescubrirlo. La cola dice
*qué falta*; esto dice *cómo se piensa*.
