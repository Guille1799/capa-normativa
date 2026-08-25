# Qué interrumpe a G y qué espera — 2026-08-25

**Decisión de G, literal:** *«lo que bloquea que me interrumpa, lo demás que espere.»*

Es una regla de una línea y se puede aplicar sin interpretarla, que es justo lo que hacía falta.
Hasta ahora el reparto entre «avisar» y «encolar» lo decidía cada mecanismo por su cuenta.

## La regla

| | canal | ejemplo real |
|---|---|---|
| **Bloquea** — no puedes seguir trabajando hasta que se arregle | interrumpe: notificación ahora | el reindexado murió y dejó el índice sin actualizar (2026-08-25, 14:00) |
| **No bloquea** — es trabajo pendiente, pero se puede seguir | espera: cola de Ralph o aviso al abrir sesión | un SUMMARY desfasado, una ruta de casa en un repo público |

«Bloquea» se juzga desde G: *¿me impide seguir haciendo lo que iba a hacer?* No desde la gravedad
técnica. Un bug feo que no te para es trabajo pendiente; un índice caído que hace que el RAG conteste
mal **sí** te para, aunque el fichero roto sea de una línea.

## Por qué esta regla y no «avisar de todo»

Porque un aviso que interrumpe de más se aprende a ignorar, y después se apaga. No es teoría: el
mismo 2026-08-25 hubo que arreglar `promesa_gate.py`, que saltaba en **cada cierre de turno** por un
checkpoint de hacía 55 horas cuyas promesas ya estaban cumplidas. Denunciaba el final feliz, y por
algo que además no se podía arreglar — el pasado no se reescribe. Ese gate iba camino de acabar
desactivado, no por malo, sino por ruidoso.

## El agujero que esta decisión NO tapa, y hay que decirlo

Medido el 2026-08-25: la **detección** está bien montada (ronda diaria de los 7 tableros, healthcheck
cada 30 min, aviso global que sale en cualquier sesión de cualquier proyecto). La **entrega** tiene
dos fugas comprobadas:

1. **Encolar no es arreglar.** Las 5 tareas `HC-DOCS-*-SUMMARY` estaban en las posiciones #21-#25 de
   la cola y el robot corría con tope 20. Detectadas, encoladas, no duplicadas (71 «ya encolada») y
   **silenciadas** porque «todo encaminado a un robot» — y el robot no llegaba. El silencio decía
   que estaba atendido. Tras cerrar 7 tareas ya hechas que seguían abiertas, subieron a #8-#12 y
   entran dentro del tope actual (12).
2. **Un guardián muerto tarda hasta 24 h en verse.** `ContextWatcher-Reindex` reventó a las 14:00
   con 0xC0000005 y se descubrió a las 19:30 mirando a mano. Quien lo vigila es `guardianes-vivos`,
   que vive en la ronda **diaria**. Por la regla de arriba eso es un caso de «bloquea», así que su
   sitio no es la ronda: es el healthcheck.

## Consecuencia pendiente

Mover a `guardianes-vivos` (o su equivalente) del ciclo diario al de 30 min, para que un guardián
muerto se note en minutos y no al día siguiente. Sin eso, la regla queda escrita pero no aplicada
al caso que la motivó.
