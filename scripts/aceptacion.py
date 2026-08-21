"""Comprobadores de ACEPTACIÓN de las promesas abiertas de capa-normativa.

## Por qué existe (2026-08-20)

Se midieron 28 parejas de checkpoints consecutivos en los dos repos que más se trabajan: el
`PRÓXIMO PASO EXACTO` de uno se recogió en el siguiente el 46 % / 60 % de las veces. Y al
intentar automatizar «¿se hizo lo prometido?» fallaron CINCO instrumentos seguidos, todos por
lo mismo: preguntaban por el SIGNIFICADO de un texto.

**La regla:** una aceptación fiable pregunta por la EXISTENCIA de un artefacto nombrado o por
el EXIT CODE de un comando. Nunca por el significado de un texto. Y nace ROJA: si ya pasa el
día que se escribe, no obliga a nada.

    python scripts/aceptacion.py              # el tablero
    python scripts/aceptacion.py --verifica   # mutación: cada comprobador tiene que cambiar de color

Sin este fichero, el Stop hook `promesa_gate.py` FALLA ABIERTO en este proyecto: no puede
comprobar nada, así que deja pasar cualquier `PRÓXIMO PASO` en prosa. Existir ya es la mitad
del valor — el gate deja de fallar abierto
aquí aunque hoy no haya ninguna promesa abierta.

Su ultimo checkpoint (2026-08-17) dice literalmente «la linea de la capa normativa esta
sana y puede esperar», asi que aqui no hay promesas caducadas de codigo. La unica
entrada es una DECISION pendiente sobre su propia cadena de checkpoints.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

CONTEXTO = Path(r"C:/Users/Guille/proyectos/Contexto/capa-normativa")
CONFIG_RAG = Path(r"C:/Users/Guille/proyectos/mcp_smart_context/projects_config.yaml")
CORE = RAIZ / "docs/CN_REFERENCIA_CORE.md"
DECISION = RAIZ / "docs/decisiones/CONTEXTO_PROPIO.md"


def contexto_propio():
    """¿Tiene capa-normativa cadena de checkpoints PROPIA, o se decide por escrito que no?

    EL DANO ESTA MEDIDO, no es cuestion de orden. Hoy sus sesiones se guardan dentro de
    `Contexto/mcp_smart_context/` y `Contexto/ponerse_wenorro/`, y eso hace dos cosas:

      · En la medicion del 2026-08-20, las parejas 11-14 de la cadena de `mcp` eran trabajo de
        capa-normativa archivado bajo mcp. Por eso "el proximo paso no se recogio" quedo
        ambiguo: el checkpoint siguiente era de OTRO proyecto. Corrompio la unica medicion
        que tenemos.
      · El paso B de `/checkpoint` copia ESTADO ACTUAL al CORE del proyecto de la carpeta, asi
        que el CORE de mcp acaba describiendo estado de capa-normativa.

    Pero montarla no es un `mkdir`: son CINCO piezas (carpeta, entrada en projects_config.yaml,
    CN_REFERENCIA_CORE.md, SUMMARY.md, reindexado del RAG). Media cableada es peor que ninguna
    — el drift-check del paso F reportaria stale para siempre.

    Forma DECISION: se monta entera, o se declara por escrito que no y por que.
    """
    import re
    if DECISION.exists():
        t = DECISION.read_text("utf-8", errors="replace")
        if re.search(r"^decidido:\s*no\s*$", t, re.M) and re.search(r"^motivo:\s*\S", t, re.M):
            return True, "declarado por escrito que NO se monta, con motivo"
    faltan = []
    if not CONTEXTO.exists():
        faltan.append("la carpeta Contexto/capa-normativa")
    if not CORE.exists():
        faltan.append("docs/CN_REFERENCIA_CORE.md")
    try:
        if "capa-normativa" not in CONFIG_RAG.read_text("utf-8", errors="replace"):
            faltan.append("su entrada en projects_config.yaml")
    except Exception:
        faltan.append("no se pudo leer projects_config.yaml")
    if faltan:
        return False, "faltan " + str(len(faltan)) + "/3 piezas: " + ", ".join(faltan)
    return True, "cadena propia montada"

# Nota: `emit --check` NO está cableado al CI de este repo, y eso NO es una promesa abierta
# sino una decisión ya tomada y escrita con su motivo en `.github/workflows/ci.yml`: este repo
# es el paquete, no un inquilino, así que no tiene registro que emitir. Es justo la forma que
# este tablero persigue — decidir y dejar el porqué, en vez de dejarlo pendiente en prosa.

def canario_completo():
    """Los CUATRO detectores del vigilante tienen que estar cubiertos por el canario.

    Hoy `CASOS` solo trae caso rojo para `secretos` y `sintaxis` — los dos que corre el hook
    pre-commit. `preguntas` y `punteros` estan registrados en DETECTORES y NO tienen ninguno, asi
    que `canario(DETECTORES)` LANZA en vez de pasar de largo. Eso ya es la decision correcta y
    esta escrita en vigilante/__init__.py: un detector sin caso rojo es un detector que nadie ha
    comprobado, y esa distincion no puede ser silenciosa.

    Pero lanzar no es estar cubierto. Mientras falten, el canario solo puede correrse sobre un
    subconjunto elegido a mano — y un canario que hay que llamar con la lista buena es justo el
    tipo de guarda que un dia se llama con la lista de ayer.

    EL DANO QUE PREVIENE ESTA MEDIDO: el 2026-08-20 el escaner de secretos recorria CERO ficheros
    y contestaba «limpio» por un GIT_DIR heredado. Lo cazo el canario. `preguntas` y `punteros`
    hoy no tienen quien les haga eso.

    Forma EXIT CODE: se ejecuta el canario sobre TODOS los detectores registrados y se pide que
    no lance. Ni una pregunta sobre el contenido de nada.
    """
    import subprocess
    import sys
    codigo = (
        "import sys; sys.path.insert(0, r'" + str(RAIZ / "src") + "');"
        " from capa_normativa.vigilante import DETECTORES;"
        " from capa_normativa.vigilante.canario import canario;"
        " canario(DETECTORES)"
    )
    try:
        r = subprocess.run([sys.executable, "-c", codigo], capture_output=True,
                           timeout=300, cwd=str(RAIZ))
    except subprocess.TimeoutExpired:
        return False, "el canario se cuelga (>5 min) sobre los cuatro detectores"
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip().splitlines()
        return False, (err[-1][:150] if err else "canario(DETECTORES) falla sin mensaje")
    return True, "los cuatro detectores registrados tienen caso rojo y el canario los ve saltar"


SIN_MUTACION = {}
ARTEFACTOS = {
    "contexto-propio": [(str(DECISION), "decidido: no" + chr(10) + "motivo: stub" + chr(10))],
}
COMPROBADORES = {
    "canario-completo": canario_completo,
    "contexto-propio": contexto_propio,
}

# ── MUTACIÓN: un comprobador en el que se puede confiar es uno que se ha VISTO cambiar ──
#
# Un comprobador rojo porque la promesa sigue abierta y uno rojo porque su ruta está mal son
# indistinguibles mirando el tablero — y el segundo se queda rojo para siempre, convirtiendo el
# tablero en ruido. Así que el tablero se ataca a sí mismo: fabrica el artefacto → tiene que
# ponerse VERDE → lo quita → tiene que volver a ROJO.
#
#     python scripts/aceptacion.py --verifica
#
# Nació de un pase adversarial del 2026-08-20 que encontró que el gate aceptaba comprobadores
# VERDES DE NACIMIENTO. Esto es ese pase, mecanizado, para no depender de que a alguien se le
# ocurra pedirlo.


def _verifica() -> int:
    import hashlib
    malos = []
    for nombre, fn in COMPROBADORES.items():
        if nombre in SIN_MUTACION:
            print("  " + chr(9898) + " " + nombre.ljust(24) + "sin mutar: " + SIN_MUTACION[nombre])
            continue
        artefactos = ARTEFACTOS.get(nombre)
        if not artefactos:
            malos.append((nombre, "ni ARTEFACTOS ni SIN_MUTACION: nadie ha dicho como se comprueba"))
            continue
        antes = fn()[0]
        creados = []
        try:
            for ruta, contenido in artefactos:
                p = Path(ruta)
                if p.exists():
                    continue  # jamás se toca algo que ya existe
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(contenido, encoding="utf-8")
                # Se hashea lo que QUEDA EN DISCO, no lo que creiamos escribir: en Windows
                # write_text traduce el salto de linea, el hash no cuadraba y la limpieza no
                # borraba nada. Dejo tres stubs sueltos en el repo la primera vez que corrio.
                creados.append((p, hashlib.sha256(p.read_bytes()).hexdigest()))
            despues = fn()[0]
        finally:
            for p, h in creados:
                # se borra SOLO lo que se creó aquí y SOLO si nadie lo ha tocado
                if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == h:
                    p.unlink()
        final = fn()[0]
        if antes is not False:
            malos.append((nombre, "no estaba ROJO de partida (¿ya cumplida? entonces retírala)"))
        elif despues is not True:
            malos.append((nombre, "con su artefacto puesto NO se pone verde: está roto o mal apuntado"))
        elif final is not False:
            malos.append((nombre, "no vuelve a rojo al quitar el artefacto: no discrimina"))
        else:
            print(f"  🟢 {nombre:24} muta bien (rojo → verde → rojo)")
    for nombre, motivo in malos:
        print(f"  🔴 {nombre:24} {motivo}")
    print()
    verificados = len(COMPROBADORES) - len(malos) - len(SIN_MUTACION)
    print(f"  {verificados}/{len(COMPROBADORES) - len(SIN_MUTACION)} verificados por mutación"
          f" ({len(SIN_MUTACION)} declarados no mutables).")
    return 1 if malos else 0


def _salida_resistente() -> None:
    """El VEREDICTO no puede depender de si la consola sabe pintar un emoji.

    ⚠️ Medido el 2026-08-21, y costó revertir trabajo correcto. Ralph corrió desde un task de
    Windows —consola cp1252, no UTF-8— y este script REVENTÓ al imprimir el 🟢 con
    `UnicodeEncodeError: charmap codec can't encode '🟢'`. El crash dio código de salida
    distinto de cero, el loop lo leyó como «la aceptación sigue roja» y revirtió un commit que
    estaba PERFECTO.

    O sea: la aceptación se cumplió, y lo que falló fue IMPRIMIRLA. El instrumento tumbando la
    medida — el mismo patrón que el `GIT_DIR` en el vigilante y el campo equivocado en el token.

    `errors="replace"` conserva la codificación de la consola y degrada lo impintable a `?`. Se
    prefiere a forzar UTF-8 porque estos mensajes van llenos de acentos: forzarlo los convertiría
    a todos en basura, y aquí solo se pierde el color del círculo.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")
        except Exception:
            pass


def main(argv: list[str]) -> int:
    _salida_resistente()
    if argv and argv[0] == "--verifica":
        return _verifica()
    nombres = argv or list(COMPROBADORES)
    fallos = 0
    for n in nombres:
        fn = COMPROBADORES.get(n)
        if fn is None:
            print(f"desconocida: {n}. Conocidas: {', '.join(COMPROBADORES)}", file=sys.stderr)
            return 2
        try:
            ok, motivo = fn()
        except Exception as e:  # noqa: BLE001 — un comprobador roto es un rojo, no una excepción
            ok, motivo = False, f"el comprobador falló: {type(e).__name__}: {e}"
        print(f"  {'🟢' if ok else '🔴'} {n:24} {motivo}")
        fallos += not ok
    if not argv:
        print(f"\n  {len(nombres) - fallos}/{len(nombres)} promesas cumplidas.")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
