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


# `contexto_propio()` vivia aqui. Retirada el 2026-08-23 al cumplirse (ver CUMPLIDAS):
# mientras siguio en el tablero salia VERDE y no obligaba a nada.


# `canario_completo()` vivia aqui. Retirada el 2026-08-23 al cumplirse (ver CUMPLIDAS):
# los cuatro detectores del vigilante ya tienen caso rojo y el canario los ve saltar.
# Su relevo es `canario-de-los-hooks`, que hace lo mismo con los diez hooks del sistema.


#: Los defectos que la caza adversarial del 2026-08-21 encontro y su esceptico verifico. Cada
#: uno llego YA con su aceptacion: un nodo de pytest que hoy NO EXISTE (pytest sale 4) y que
#: solo pasara cuando el defecto este cerrado. En 8 de los 28 el esceptico TUMBO la aceptacion
#: del cazador y escribio una mejor — ese segundo trabajo es la mitad del valor de la tanda.
_BUGS = {
    "bug-git-como-subcadena-apaga": ("tests/test_secretos.py::test_ROJO_un_secreto_en_github_workflows_SI_se_caza",
        "`.git` como subcadena apaga TODO `.github/`: los workflows versionados nunca se escanean"),
    "bug-versionados-descarta-en-silencio": ("tests/test_versionados.py::test_ROJO_un_nombre_no_ASCII_no_se_pierde",
        "`versionados()` descarta en silencio los nombres que git CITA (no-ASCII): un fichero real deja de escanearse"),
    "bug-emit-check-grita-deriva": ("tests/test_emision.py::test_el_check_NO_falla_por_COMO_SE_ESCRIBA_la_ruta",
        "`emit --check` grita DERIVA por cómo se ESCRIBIÓ la ruta, no por lo que cambió"),
    "bug-el-pip-install-del": ("tests/test_empaquetado.py::test_el_pip_install_del_README_fija_la_version_PUBLICADA",
        "El `pip install` del README fija v0.16.1 — la versión SIN el arreglo de «escanea cero y dice limpio»"),
    "bug-el-barrido-dice-4": ("tests/test_vigilante.py::test_el_barrido_no_CUENTA_los_detectores_que_OMITE",
        "El barrido dice «4 detector(es)» habiendo corrido 3: omite `preguntas` en silencio"),
    "bug-init-reparte-un-expires": ("tests/test_arranque.py::test_lo_generado_CARGA_tambien_dentro_de_tres_anios",
        "`init` reparte un `expires: '2027-12-31'` cableado: a partir de esa fecha genera un registro que NO carga"),
    "bug-el-usage-del-vigilante": ("tests/test_empaquetado.py::test_el_usage_NOMBRA_un_comando_que_EXISTE",
        "El `usage:` del vigilante nombra `capa-normativa vigilante`, un comando que no existe"),
    "bug-una-rama-sin-la": ("tests/test_registry.py::test_rama_sin_when_se_rechaza_como_when_vacio",
        "Una rama SIN la clave `when` esquiva las tres guardas de solape: con dos, gana la última del fichero"),
    "bug-un-operador-de-comparacion": ("tests/test_registry.py::test_operador_de_comparacion_mal_escrito_no_carga",
        "Un operador de comparación mal escrito (`=>65`) se acepta como igualdad literal y crea una rama MUERTA que cae al comodí"),
    "bug-branch-note-se-parsea": ("tests/test_registry.py::test_resolve_entrega_la_note_de_la_rama_que_contesto",
        "`Branch.note` se parsea, se valida y se guarda, pero `resolve()` no lo entrega: 60 ramas del inquilino real no llegan a "),
    "bug-emit-pierde-el-provenance": ("tests/test_emision.py::test_una_constante_sin_respaldo_emite_note_Y_provenance",
        "`emit` pierde el `provenance_note` cuando la constante también tiene `note`: 3 de las 116 constantes reales salen sin de"),
    "bug-check-sale-con-1": ("tests/test_emision.py::test_check_no_falla_por_como_se_escribe_la_ruta",
        "`--check` sale con 1 gritando «DERIVA» por cómo se escribió la ruta en la línea de órdenes, no por deriva real"),
}


def _fabrica_bug(nombre: str, nodo: str, resumen: str):
    """Fabrica el comprobador de UN defecto: correr su nodo de pytest y leer el exit code.

    No opina sobre el contenido del test. Pregunta por un EXIT CODE, que es la regla.

    ⚠️ Distingue el rojo POR AUSENCIA del rojo POR FALLO, y no es cosmetico: pytest sale 4
    cuando no encuentra el nodo y 1 cuando el test existe y falla. Los dos son "rojo", pero solo
    el segundo significa que alguien escribio el test. Si el tablero no los separa, un test mal
    nombrado se lee como trabajo pendiente para siempre.
    """
    def comprobador():
        import subprocess
        import sys as _s
        try:
            r = subprocess.run([_s.executable, "-m", "pytest", nodo, "-q",
                                "-p", "no:cacheprovider"],
                               capture_output=True, timeout=900, cwd=str(RAIZ))
        except subprocess.TimeoutExpired:
            return False, "el test se cuelga (>15 min)"
        if r.returncode == 0:
            return True, "cerrado: " + resumen
        if r.returncode == 4:
            return False, "sin escribir: " + resumen
        sal = r.stdout.decode("utf-8", "replace").strip().splitlines()
        ultima = next((l for l in reversed(sal) if l.strip()), "")
        return False, "el test existe y FALLA (el defecto sigue): " + ultima[:90]
    comprobador.__name__ = nombre.replace("-", "_")
    return comprobador


# HALLAZGOS DEL INVENTARIO DEL ARNES (2026-08-22).
#
# Un fan-out clasifico 45 piezas de andamiaje (hooks, scripts, skills, el RAG) como vivo,
# muerto, usado-mal o desaprovechado, y un ESCEPTICO independiente verifico cada veredicto
# buscando activamente la prueba de lo contrario — porque aqui el error caro no es dejar un
# muerto sin detectar, es declarar MUERTO algo VIVO y que alguien lo retire.
#
# Cada entrada trae el COMANDO de aceptacion que escribio el esceptico, y se comprobo
# EJECUTANDOLO que los 17 nacen ROJOS. Un comprobador verde el dia que se escribe no obliga a
# nada; los que salian 0 se descartaron en vez de encolarse.
_INV = {
    # Comando reescrito el 2026-08-23. El anterior hacia `cd <ruta absoluta al arbol
    # principal> && ... && ! ...`: dos fallos a la vez. La ruta absoluta hacia que desde un
    # worktree se juzgara el arbol de al lado, y el `!` lo expande cmd.exe y rompe el
    # comando antes de medir nada. Las dos mitades de la comprobacion viven ahora dentro
    # de `revista_runtimes.py --autoprueba`, que no depende de la sintaxis del shell.
    'inv-revista-de-runtimes-quien-corre': ('python scripts/aceptacion.py revista-de-runtimes',
        'construir: Revista de runtimes «quien-corre-que» — manifiesto interprete->paquete->version ejecutable'),
    'inv-test-hechos-que-caducan-barre': ('`C:/Users/Guille/proyectos/mcp_smart_context/venv/Scripts/python.exe -B -m pytest "tests/test_hechos_que_caducan.py::test_ninguna_afirmacion_sobre_un_DIRECTORIO_esta_caducada" -q -p no:cacheprovider` (exit 0), desde mcp_smart_context. Es la mas dura de las seis, porque nace roja por dos motivos independientes: hoy pytest sale 4 (el nodo no existe), y en cuanto se escriba de verdad saldra 1 hasta que se corrija promesa_gate.py:61 — el directorio Contexto/capa-normativa EXISTE, asi que el defecto que el nodo tiene que cazar esta ahi ahora mismo. Escribir el test no lo aprueba; solo lo aprueba arreglar el hecho.',
        'exprimir: test_hechos_que_caducan — barre rutas y versiones, pero no las afirmaciones sobre DIRECTORIOS'),
    'inv-test-hechos-que-caducan-barre': ('C:/Users/Guille/proyectos/mcp_smart_context/venv/Scripts/python.exe -c "import sys;sys.path.insert(0,r\'C:/Users/Guille/proyectos/mcp_smart_context/tests\');import test_hechos_que_caducan as t;sys.exit(0 if t._dir_muerto(\'Contexto/no_existe_xyz/\') and not t._dir_muerto(\'Contexto/capa-normativa/\') else 1)"   (HOY ROJO: `_dir_muerto` no existe, AttributeError. No lo aprueba un stub constante: tiene que decir True para la carpeta inexistente Y False para una que existe desde ayer, o sea mirar el disco. Nace roja aunque hoy no haya ningun puntero-a-carpeta muerto en el arbol, porque interroga al detector, no a la cosecha.)',
        'exprimir: test_hechos_que_caducan — barre rutas muertas y versiones falsas pero se le escapan las afirmaciones de existe'),
    # Comando reescrito el 2026-08-23: el anterior citaba `--verifica guardia-de-commit`,
    # que sobre un comprobador no-mutable salia 0 SIEMPRE (aceptacion verde para siempre),
    # y ademas por ruta absoluta al arbol principal. La forma directa dice la verdad.
    'inv-capa-normativa-es-el-unico': ('python scripts/aceptacion.py guardia-de-commit',
        'arreglar: capa-normativa es el unico repo sin pre-commit — y es el que ALOJA al vigilante'),
    'inv-audit-settings-source-sh-no': ('Si se retira: `python -c "import json,os,sys; t=json.dumps(json.load(open(r\'C:/Users/Guille/.claude/settings.json\',encoding=\'utf-8\'))); sys.exit(1 if (\'audit_settings_source\' in t or os.path.exists(r\'C:/Users/Guille/.claude/hooks/audit_settings_source.sh\')) else 0)"` — hoy ROJO por las dos mitades (registrado Y presente en disco); solo pasa desregistrandolo y borrandolo. Si en vez de retirarlo se quiere conservar la capacidad, entonces la aceptacion es un CANARIO, no un diff: `python C:/Users/Guille/proyectos/capa-normativa/scripts/aceptacion.py --verifica canario-settings`, que copia el settings.json vigente a un sandbox de %TEMP%, le INYECTA un hook de laboratorio que el snapshot revisado no contiene, corre el guardian contra esa copia y EXIGE exit != 0 o el aviso por stderr. Hoy ROJO porque el guardian pregunta por la autoria y no por el contenido, asi que ante un settings envenenado se calla. Un diff contra el snapshot NO vale como aceptacion: hoy los dos ficheros son identicos y nacería verde.',
        'retirar: audit_settings_source.sh — no puede avisar nunca, por dos motivos independientes'),
    # Comando reescrito el 2026-08-23. El anterior era PROSA con el comando citado dentro,
    # asi que el shell nunca lo ejecutaba y el tablero traducia ese fallo a «pendiente».
    # Y citaba `--verifica <nombre>`, que sobre un comprobador no-mutable sale 0 SIEMPRE:
    # habria sido una aceptacion verde para siempre. Se comprobo caducando una entrada a
    # proposito — el comprobador se ponia rojo y `--verifica` seguia diciendo 0.
    'inv-autohealth-monitor-py-con-guion': ('python scripts/aceptacion.py registro-sin-caducados',
        'retirar: autohealth-monitor.py (con guion) — fichero de hook que no registra nadie'),
    'inv-registro-md-session-start-sh': ("`python C:/Users/Guille/proyectos/scripts/aceptacion.py censo-de-guardianes` — hoy ROJA porque C:/Users/Guille/proyectos/scripts/ NO EXISTE (verificado: Test-Path = False), y un fichero vacío tampoco la aprueba: el tablero contesta `desconocida: censo-de-guardianes` y sale 2. Solo pasa cuando el comprobador ENUMERE los guardianes de sus fuentes vivas (entradas de hook de ~/.claude/settings.json, repos con pre-commit, `Get-ScheduledTask` de TaskPath '\\', ficheros aceptacion.py) y exija una cabecera '## ' en REGISTRO.md por cada uno — hoy 14 contra 29.",
        'exprimir: REGISTRO.md + session_start.sh — el censo que existe pero no censa a los guardianes'),
    'inv-canario-py-aceptacion-py-verifica': ('`python C:/Users/Guille/proyectos/capa-normativa/scripts/aceptacion.py canario-de-los-hooks` — hoy ROJA: el nombre no existe en COMPROBADORES, el tablero imprime `desconocida:` y sale 2. Solo pasa cuando exista un comprobador que, para CADA una de las 10 entradas de hook de ~/.claude/settings.json, le entregue por stdin una carga envenenada conocida y exija que el hook grite (exit≠0 o mensaje de bloqueo), y que LANCE — no que salte en silencio — ante cualquier hook sin caso, replicando el contrato de CASOS. Un stub que devuelva True no la aprueba: `python scripts/aceptacion.py --verifica` la tumba con «no estaba ROJO de partida». Acción gemela y verificable: `canario-completo` debe desaparecer del tablero (hoy sale 0, medido).',
        'exprimir: canario.py + aceptacion.py --verifica — la prueba por mutación existe y cubre 4 detectores de ~29 guardianes'),
    'inv-capa-normativa-declarado-en-el': ('python -c "import re,glob,yaml,sys,pathlib;R=pathlib.Path(r\'C:\\\\Users\\\\Guille\\\\proyectos\\\\mcp_smart_context\');y=yaml.safe_load((R/\'projects_config.yaml\').read_text(encoding=\'utf-8\'));esp={p[\'name\'] for p in y[\'projects\'] if p.get(\'enabled\')};L=max(glob.glob(str(R/\'logs\'/\'context_watcher_master_*.log\')),key=lambda f:pathlib.Path(f).stat().st_mtime);seg=open(L,encoding=\'utf-8\',errors=\'ignore\').read().rsplit(\'=\'*80,1)[-1];w={m.strip() for m in re.findall(r\'Watching:\\\\s*(\\\\S.*)\',seg)};sys.exit(0 if len(w)>=len(esp) else 1)"  — EJECUTADO HOY: vigiladas=5, esperadas=6, EXIT=1 (ROJO). Solo pasa reiniciando el demonio, que reemite las lineas \'Watching:\'; ni un touch ni un fichero vacio lo aprueban porque cuenta rutas realmente vigiladas contra proyectos enabled del YAML.',
        'arreglar: capa_normativa declarado en el YAML pero fuera del vigilante'),
}


def _solo_el_comando(bruto: str) -> str:
    """El comando de dentro de las comillas de markdown, si las lleva.

    Medido el 2026-08-23: nueve aceptaciones estaban escritas como `python x.py` seguido de
    la explicacion. El shell recibe eso tal cual y cmd.exe contesta que `python no se reconoce;
    el tablero lee el exit != 0 y lo traduce a «pendiente». O sea que decia que faltaba trabajo
    cuando el comando NO HABIA LLEGADO A ARRANCAR, y la tarea era incerrable.

    SOLO se desnuda lo que empieza por comilla. Hubo una version que ademas recortaba la prosa
    de detras y buscaba comillas en medio: produjo TRES falsos verdes, porque adivinar que trozo
    de una cadena es el comando falla justo hacia el lado que este arnes existe para impedir.
    """
    t = str(bruto).strip()
    if not t.startswith('`'):
        return t
    # Se corta en la SIGUIENTE comilla, no en la ultima: detras viene la explicacion, que suele
    # traer mas comillas, y cortar por la ultima se tragaria la prosa entera.
    fin = t.find('`', 1)
    return t[1:fin].strip() if fin > 1 else t


def _fabrica_inv(nombre, comando, resumen):
    """Corre el comando de aceptacion del inventario y lee su EXIT CODE.

    No opina sobre nada: pregunta por un exit code, que es la regla. El comando lo escribio el
    esceptico que verifico el hallazgo, no quien va a hacer el trabajo — esa separacion es lo
    que impide aprobar ablandando la prueba.
    """
    comando = _solo_el_comando(comando)

    def comprobador():
        import subprocess
        try:
            r = subprocess.run(comando, shell=True, capture_output=True,
                               timeout=900, cwd=str(RAIZ))
        except subprocess.TimeoutExpired:
            return False, 'la comprobacion se cuelga (>15 min)'
        if r.returncode == 0:
            return True, 'hecho: ' + resumen[:110]
        return False, 'pendiente: ' + resumen[:110]
    comprobador.__name__ = nombre.replace('-', '_')
    return comprobador


def sondas_miran_su_arbol() -> tuple[bool, str]:
    """Ninguna sonda de ESTE tablero puede juzgar un worktree hermano.

    Es la guarda que faltaba, y su historia dice por qué hace falta: el 2026-08-22 tres sondas
    de `ponerse_wenorro` —escritas justamente para cazar fallos de aislamiento— llevaban la ruta
    al checkout principal ESCRITA A MANO. El agente arreglaba su copia, ellas abrian la de al
    lado, decian ROJO, y el bucle destruia el trabajo correcto. Sin sintoma: por la manana el
    registro decia lo mismo que si el agente no hubiera hecho nada.

    ⚠️ Observa en vez de leer el fuente, y ahi esta el valor. Un lint que busque rutas escritas
    no ve las tres formas que ya han ocurrido en estos repos: `GIT_DIR` secuestrando a los
    detectores (commit d216e5e), un paquete instalado y viejo tapando al fuente, y una ruta
    relativa resuelta contra el directorio equivocado. En las tres, el fuente esta limpio.

    Se excluye a si misma, obviamente: ejecutarse bajo su propia vigilancia no termina.
    """
    # El FUENTE manda sobre lo instalado, y no es precaucion teorica: sin esta linea el
    # comprobador reventaba con ModuleNotFoundError porque `capa_normativa` resolvia al paquete
    # INSTALADO, que no tiene `arbol_propio`. Anoche paso desapercibido porque se corrio con
    # PYTHONPATH=src a mano; el bucle no hace eso.
    #
    # Es exactamente el fallo numero 2 del docstring de este modulo —un paquete instalado y viejo
    # tapando al fuente— cometido por la guarda escrita para cazarlo.
    import sys
    fuente = str(RAIZ / "src")
    if fuente not in sys.path:
        sys.path.insert(0, fuente)
    for mod in [k for k in list(sys.modules) if k.startswith("capa_normativa")]:
        del sys.modules[mod]
    from capa_normativa.vigilante.arbol_propio import revisar_arbol_propio
    otras = {n: f for n, f in COMPROBADORES.items() if n != "sondas-miran-su-arbol"}
    hallazgos = revisar_arbol_propio(otras, RAIZ)
    if hallazgos:
        return False, (str(len(hallazgos)) + " sonda(s) juzgan otro arbol: "
                       + ", ".join(h.fichero for h in hallazgos))
    return True, "las " + str(len(otras)) + " sondas miran su propio arbol"


#: Promesas RETIRADAS por cumplidas. No viven en COMPROBADORES: una promesa cumplida sale VERDE,
#: y una promesa verde no obliga a nada — es el defecto que se arreglo aqui mismo el 2026-08-20,
#: cuando el gate eran 256 tests que ya pasaban antes de empezar. Se conservan para que quien cite
#: el nombre viejo lea «cumplida el X» y no «desconocida», que es un error y se lee como averia.
def registro_sin_caducados() -> tuple[bool, str]:
    """Ninguna entrada de REGISTRO.md puede estar vencida y sin aplicar su propia regla.

    El REGISTRO se dio a si mismo esta norma en su primera linea: «llegada la fecha de CADUCA, o
    hay SEÑAL DE USO, o la cosa se quita». Una norma que solo esta escrita es una intencion; esto
    la convierte en un exit code.

    ⚠️ Lo importante de este comprobador es que **se pone rojo el solo**. No hace falta que nadie
    se acuerde de revisarlo: se apoya en la fecha de hoy, asi que la proxima vez que algo caduque
    saltara sin que nadie lo toque. Es la diferencia entre una guarda y un recordatorio.

    Y no se puede aprobar escribiendo: solo pasa RETIRANDO lo caducado o renovando su fecha con
    una señal de uso de verdad, que es exactamente lo que la norma pide.
    """
    import datetime
    import re
    reg = RAIZ.parent / "REGISTRO.md"
    if not reg.exists():
        return False, "no existe " + str(reg) + ": la norma no puede hacerse cumplir sin registro"
    hoy = datetime.date.today()
    vencidas = []
    bloque, titulo = [], None
    def cerrar(titulo, bloque):
        if not titulo:
            return
        texto = chr(10).join(bloque)
        m = re.search(r"CADUCA:\s*(\d{4})-(\d{2})-(\d{2})", texto)
        if not m:
            return
        fecha = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if fecha >= hoy:
            return
        estado = re.search(r"ESTADO:\s*(.+)", texto)
        dice = (estado.group(1) if estado else "").upper()
        if "RETIRADO" not in dice:
            vencidas.append(titulo[:42] + " (caduco " + fecha.isoformat() + ")")
    for linea in reg.read_text("utf-8", errors="replace").splitlines():
        if linea.startswith("## "):
            cerrar(titulo, bloque)
            titulo, bloque = linea[3:].strip(), []
        bloque.append(linea)
    cerrar(titulo, bloque)
    if vencidas:
        return False, (str(len(vencidas)) + " entrada(s) vencidas sin retirar: "
                       + "; ".join(vencidas))[:200]
    return True, "ninguna entrada de REGISTRO.md esta vencida sin aplicar su regla"


def revista_de_runtimes() -> tuple[bool, str]:
    """Quien corre que version de `capa_normativa`, y si alguien lo ha declarado.

    Delega en `proyectos/.claude/hooks/revista_runtimes.py --autoprueba`, que hace DOS cosas: el
    check y la prueba de que el check sabe fallar (le inyecta una deriva y exige enterarse). Un
    comprobador que nunca se ha visto fallar no esta verificado, esta sin estrenar.

    ⚠️ La aceptacion original pedia `check && ! check --inyecta-deriva`. Ese `!` lo expande
    cmd.exe y rompe el comando antes de medir nada, asi que las dos mitades viven ahora dentro de
    `--autoprueba`: un comprobador no puede depender de la sintaxis del shell.

    Nace ROJO y no por capricho: hoy hay cuatro interpretes divergentes y medidos —el venv de
    mcp_smart_context resuelve 0.7.0 con el fuente en 0.16.2, el de eu no tiene el paquete— y
    ninguno esta declarado. Solo pasa arreglando la divergencia o DECLARANDOLA con su motivo, que
    es lo unico que distingue «esto esta pensado» de «esto se pudrio».
    """
    import subprocess
    import sys
    guion = RAIZ.parent / ".claude" / "hooks" / "revista_runtimes.py"
    if not guion.exists():
        return False, "no existe .claude/hooks/revista_runtimes.py: nadie mide quien corre que"
    try:
        r = subprocess.run([sys.executable, str(guion), "--autoprueba"],
                           capture_output=True, timeout=600, cwd=str(RAIZ.parent))
    except subprocess.TimeoutExpired:
        return False, "la revista se cuelga (>10 min)"
    salida = (r.stdout + r.stderr).decode("utf-8", "replace").strip().splitlines()
    if r.returncode != 0:
        return False, (salida[-1] if salida else "la revista falla sin mensaje")[:170]
    return True, "los interpretes cuadran con el manifiesto, y la revista sabe detectar una deriva"


def guardia_de_commit() -> tuple[bool, str]:
    """El pre-commit de este repo tiene que estar VERSIONADO y tiene que GRITAR de verdad.

    Tres condiciones, y las tres hacen falta:

      1. `core.hooksPath` apunta a una carpeta del repo. Un hook que solo vive en `.git/hooks`
         no viaja en un clon, no se revisa en un diff y puede desaparecer sin que nadie se entere.
      2. Ahi hay un `pre-commit` y esta SEGUIDO por git (`git ls-files --error-unmatch`).
         Que exista el fichero no basta: sin versionar no hay red de revert.
      3. Ese hook, corrido contra un repo de pega con un caso ROJO conocido, sale con exit != 0.

    ⚠️ La tercera es la unica que prueba algo. Las dos primeras las aprueba un `touch`, y ese es
    justo el fallo que se persigue: el 2026-08-20 el escaner recorria CERO ficheros y contestaba
    «limpio» por un GIT_DIR heredado. Existir no es funcionar.

    Y se pregunta a git por la ruta EFECTIVA (`rev-parse --git-path hooks`) en vez de mirar
    `.git/hooks` a ciegas: asi se colo el shim fantasma de eu, un pre-commit que git ignoraba y
    que aun asi mentia a quien lo leyera.
    """
    import subprocess
    import sys

    def git(*a, cwd=RAIZ):
        return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True,
                              timeout=120)

    ruta = git("config", "--get", "core.hooksPath").stdout.strip()
    if not ruta:
        return False, ("core.hooksPath sin definir: el pre-commit solo vive en .git/hooks, que no "
                       "viaja en un clon ni se revisa en un diff")
    hook = (RAIZ / ruta / "pre-commit")
    if not hook.exists():
        return False, "core.hooksPath apunta a " + ruta + " y ahi no hay pre-commit"
    if git("ls-files", "--error-unmatch", "--", str(hook.relative_to(RAIZ)).replace(chr(92), "/")).returncode != 0:
        return False, ("existe " + ruta + "/pre-commit pero NO esta versionado: sin red de revert "
                       "y sin revisarse en ningun diff")
    try:
        sys.path.insert(0, str(RAIZ / "src"))
        from capa_normativa.vigilante.canario import repo_de_pega
    except Exception as e:
        return False, "no se puede montar el repo de pega (" + type(e).__name__ + ")"
    with repo_de_pega() as pega:
        subprocess.run(["git", "-C", str(pega), "config", "core.hooksPath",
                        str(hook.parent)], capture_output=True, timeout=60)
        r = subprocess.run(["git", "-C", str(pega), "-c", "user.email=canario@local",
                            "-c", "user.name=canario", "commit", "-m", "carga envenenada"],
                           capture_output=True, timeout=600)
    if r.returncode == 0:
        return False, ("el hook DEJO PASAR un commit con un caso rojo conocido: existe pero no "
                       "protege, que es peor que no tenerlo porque parece que si")
    return True, "el pre-commit esta versionado y grita ante una carga envenenada conocida"


def canario_de_los_hooks() -> tuple[bool, str]:
    """Los diez hooks registrados tienen que sobrevivir a basura Y rechazar su carga envenenada.

    Delega en `scripts/canario_hooks.py`, que lee los hooks de `~/.claude/settings.json` en vez de
    listarlos a mano — una lista escrita envejece en silencio, y el dia que se registre uno nuevo
    el canario seguiria diciendo que estan todos cubiertos.

    Dos mitades, y solo la primera se puede comprobar hoy:
      · ROBUSTEZ: ante una carga malformada, terminan sin reventar y sin bloquear. Los diez pasan.
      · ENVENENADA: la entrada que cada uno DEBE rechazar. Eso depende de que vigila cada hook y
        no se puede escribir en general, asi que se declara caso por caso — y el canario SALTA
        ante un hook sin caso, en vez de pasar de largo, copiando a `canario(DETECTORES)`.

    Nace ROJO con 9 hooks sin caso declarado. Se pone verde declarandolos, que es el trabajo: no
    se aprueba escribiendo nada en el comprobador.
    """
    import subprocess
    import sys
    guion = RAIZ / "scripts" / "canario_hooks.py"
    if not guion.exists():
        return False, "no existe scripts/canario_hooks.py: nadie comprueba los hooks"
    try:
        r = subprocess.run([sys.executable, str(guion)], capture_output=True, timeout=900,
                           cwd=str(RAIZ))
    except subprocess.TimeoutExpired:
        return False, "el canario de los hooks se cuelga (>15 min)"
    salida = (r.stdout + r.stderr).decode("utf-8", "replace").strip().splitlines()
    if r.returncode != 0:
        util = [l for l in salida if l.strip().startswith(chr(183))]
        return False, (util[0].strip() if util else (salida[-1] if salida else "falla sin mensaje"))[:180]
    return True, "los 10 hooks sobreviven a basura y rechazan su carga envenenada"


CUMPLIDAS = {
    "canario-completo": (
        "cumplida el 2026-08-23, retirada del tablero ese mismo dia. Pedia que los CUATRO "
        "detectores del vigilante tuvieran caso rojo en CASOS, para que `canario(DETECTORES)` "
        "dejara de lanzar por falta de cobertura. Los cuatro lo tienen y el canario los ve "
        "saltar. Su relevo natural es `canario-de-los-hooks`: el mismo contrato aplicado a los "
        "diez hooks de settings.json, que hoy nace ROJO con nueve sin caso declarado."),
    "contexto-propio": (
        "cumplida el 2026-08-23, retirada del tablero ese mismo dia. Pedia que capa-normativa "
        "tuviera cadena de checkpoints PROPIA en vez de archivar sus sesiones bajo mcp y "
        "ponerse_wenorro, que fue lo que corrompio la medicion del 2026-08-20. Existen las tres "
        "piezas: Contexto/capa-normativa, docs/CN_REFERENCIA_CORE.md y su entrada en "
        "projects_config.yaml. Mientras siguio en el tablero salia VERDE y dejaba --verifica en "
        "ROJO PERMANENTE para todo lo demas, que es como se deja de correr una verificacion."),
}

SIN_MUTACION = {
    "canario-de-los-hooks": ("no se muta creando un fichero: interroga a los hooks REALES registrados en settings.json, dandoles cargas por stdin y leyendo su exit code. Su rojo de hoy son 9 hooks sin caso envenenado declarado, y solo baja declarandolos."),
    "guardia-de-commit": ("no se muta creando un fichero: su condicion que importa es que el hook GRITE ante una carga envenenada, y eso lo prueba montando un repo de pega e intentando un commit real. Un touch pasa las dos primeras condiciones y falla la tercera, que es el punto."),
    "revista-de-runtimes": ("no se muta creando un fichero: su rojo sale de INTERROGAR a cada interprete del sistema por la version que resuelve. Y su propia `--autoprueba` ya hace la verificacion por mutacion: inyecta una deriva y exige que el check se entere."),
    "registro-sin-caducados": ("no se muta creando un fichero: su rojo depende de la FECHA de hoy contra las de REGISTRO.md, no de que exista nada. Se pone rojo el solo cuando algo caduca, y solo pasa retirando lo caducado o renovando su fecha con señal de uso real."),
    "sondas-miran-su-arbol": ("no se muta creando un fichero: su rojo no depende de que exista "
                              "nada, sino de lo que TOCAN las demas sondas al ejecutarse. Se "
                              "verifica al reves — apuntando una sonda a un arbol hermano y "
                              "exigiendo que salte —, y eso lo cubre tests/test_arbol_propio.py, "
                              "donde cada puerta vigilada tiene su propio caso rojo."),
    'bug-git-como-subcadena-apaga': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-versionados-descarta-en-silencio': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-emit-check-grita-deriva': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-el-pip-install-del': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-el-barrido-dice-4': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-init-reparte-un-expires': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-el-usage-del-vigilante': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-una-rama-sin-la': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-un-operador-de-comparacion': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-branch-note-se-parsea': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-emit-pierde-el-provenance': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'bug-check-sale-con-1': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'canario-completo': 'no se muta creando un fichero: exige que un TEST NOMBRADO exista y PASE. Un stub vacio sale 4 (sin escribir), no 0 — y el comprobador distingue esos dos rojos. Su ROJO es su estado natural hoy: el defecto lo verifico un esceptico EJECUTANDO el codigo.',
    'inv-revista-de-runtimes-quien-corre': 'no se muta creando un fichero: su aceptacion interroga el estado real del sistema (tareas programadas, logs, config, indices). Nacio ROJO —comprobado ejecutandolo— y lo escribio un esceptico independiente, no quien hara el trabajo.',
    'inv-test-hechos-que-caducan-barre': 'no se muta creando un fichero: su aceptacion interroga el estado real del sistema (tareas programadas, logs, config, indices). Nacio ROJO —comprobado ejecutandolo— y lo escribio un esceptico independiente, no quien hara el trabajo.',
    'inv-test-hechos-que-caducan-barre': 'no se muta creando un fichero: su aceptacion interroga el estado real del sistema (tareas programadas, logs, config, indices). Nacio ROJO —comprobado ejecutandolo— y lo escribio un esceptico independiente, no quien hara el trabajo.',
    'inv-capa-normativa-es-el-unico': 'no se muta creando un fichero: su aceptacion interroga el estado real del sistema (tareas programadas, logs, config, indices). Nacio ROJO —comprobado ejecutandolo— y lo escribio un esceptico independiente, no quien hara el trabajo.',
    'inv-audit-settings-source-sh-no': 'no se muta creando un fichero: su aceptacion interroga el estado real del sistema (tareas programadas, logs, config, indices). Nacio ROJO —comprobado ejecutandolo— y lo escribio un esceptico independiente, no quien hara el trabajo.',
    'inv-autohealth-monitor-py-con-guion': 'no se muta creando un fichero: su aceptacion interroga el estado real del sistema (tareas programadas, logs, config, indices). Nacio ROJO —comprobado ejecutandolo— y lo escribio un esceptico independiente, no quien hara el trabajo.',
    'inv-registro-md-session-start-sh': 'no se muta creando un fichero: su aceptacion interroga el estado real del sistema (tareas programadas, logs, config, indices). Nacio ROJO —comprobado ejecutandolo— y lo escribio un esceptico independiente, no quien hara el trabajo.',
    'inv-canario-py-aceptacion-py-verifica': 'no se muta creando un fichero: su aceptacion interroga el estado real del sistema (tareas programadas, logs, config, indices). Nacio ROJO —comprobado ejecutandolo— y lo escribio un esceptico independiente, no quien hara el trabajo.',
    'inv-capa-normativa-declarado-en-el': 'no se muta creando un fichero: su aceptacion interroga el estado real del sistema (tareas programadas, logs, config, indices). Nacio ROJO —comprobado ejecutandolo— y lo escribio un esceptico independiente, no quien hara el trabajo.',
}
ARTEFACTOS = {
}
COMPROBADORES = {
    "canario-de-los-hooks": canario_de_los_hooks,
    "guardia-de-commit": guardia_de_commit,
    "revista-de-runtimes": revista_de_runtimes,
    "registro-sin-caducados": registro_sin_caducados,
    'inv-revista-de-runtimes-quien-corre': _fabrica_inv('inv-revista-de-runtimes-quien-corre', *_INV['inv-revista-de-runtimes-quien-corre']),
    'inv-test-hechos-que-caducan-barre': _fabrica_inv('inv-test-hechos-que-caducan-barre', *_INV['inv-test-hechos-que-caducan-barre']),
    'inv-test-hechos-que-caducan-barre': _fabrica_inv('inv-test-hechos-que-caducan-barre', *_INV['inv-test-hechos-que-caducan-barre']),
    'inv-capa-normativa-es-el-unico': _fabrica_inv('inv-capa-normativa-es-el-unico', *_INV['inv-capa-normativa-es-el-unico']),
    'inv-audit-settings-source-sh-no': _fabrica_inv('inv-audit-settings-source-sh-no', *_INV['inv-audit-settings-source-sh-no']),
    'inv-autohealth-monitor-py-con-guion': _fabrica_inv('inv-autohealth-monitor-py-con-guion', *_INV['inv-autohealth-monitor-py-con-guion']),
    'inv-registro-md-session-start-sh': _fabrica_inv('inv-registro-md-session-start-sh', *_INV['inv-registro-md-session-start-sh']),
    'inv-canario-py-aceptacion-py-verifica': _fabrica_inv('inv-canario-py-aceptacion-py-verifica', *_INV['inv-canario-py-aceptacion-py-verifica']),
    'inv-capa-normativa-declarado-en-el': _fabrica_inv('inv-capa-normativa-declarado-en-el', *_INV['inv-capa-normativa-declarado-en-el']),
    "bug-git-como-subcadena-apaga": _fabrica_bug("bug-git-como-subcadena-apaga", *_BUGS["bug-git-como-subcadena-apaga"]),
    "bug-versionados-descarta-en-silencio": _fabrica_bug("bug-versionados-descarta-en-silencio", *_BUGS["bug-versionados-descarta-en-silencio"]),
    "bug-emit-check-grita-deriva": _fabrica_bug("bug-emit-check-grita-deriva", *_BUGS["bug-emit-check-grita-deriva"]),
    "bug-el-pip-install-del": _fabrica_bug("bug-el-pip-install-del", *_BUGS["bug-el-pip-install-del"]),
    "bug-el-barrido-dice-4": _fabrica_bug("bug-el-barrido-dice-4", *_BUGS["bug-el-barrido-dice-4"]),
    "bug-init-reparte-un-expires": _fabrica_bug("bug-init-reparte-un-expires", *_BUGS["bug-init-reparte-un-expires"]),
    "bug-el-usage-del-vigilante": _fabrica_bug("bug-el-usage-del-vigilante", *_BUGS["bug-el-usage-del-vigilante"]),
    "bug-una-rama-sin-la": _fabrica_bug("bug-una-rama-sin-la", *_BUGS["bug-una-rama-sin-la"]),
    "bug-un-operador-de-comparacion": _fabrica_bug("bug-un-operador-de-comparacion", *_BUGS["bug-un-operador-de-comparacion"]),
    "bug-branch-note-se-parsea": _fabrica_bug("bug-branch-note-se-parsea", *_BUGS["bug-branch-note-se-parsea"]),
    "bug-emit-pierde-el-provenance": _fabrica_bug("bug-emit-pierde-el-provenance", *_BUGS["bug-emit-pierde-el-provenance"]),
    "bug-check-sale-con-1": _fabrica_bug("bug-check-sale-con-1", *_BUGS["bug-check-sale-con-1"]),
    "sondas-miran-su-arbol": sondas_miran_su_arbol,
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


def _verifica(solo: str | None = None) -> int:
    import hashlib
    malos = []
    for nombre, fn in COMPROBADORES.items():
        if solo is not None and nombre != solo:
            continue
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
        # `--verifica <nombre>` selecciona UNO. Antes el nombre se ignoraba y se corria la
        # mutacion entera, y eso rompia en silencio a los contratos que lo citan: pedian
        # verificar SU comprobador y recibian el veredicto de los otros treinta — asi que un
        # rojo ajeno los dejaba imposibles de aprobar para siempre. Cinco tareas se
        # bloquearon por esto el 2026-08-22.
        solo = argv[1] if len(argv) > 1 else None
        if solo is not None and solo not in COMPROBADORES:
            print('desconocida: ' + solo, file=sys.stderr)
            return 2
        if solo is not None and solo in SIN_MUTACION:
            # Pedir verificacion POR MUTACION de algo declarado NO MUTABLE es una contradiccion,
            # y contestarla con 0 es peor que un error: tres contratos citaban
            # `--verifica <nombre>` como su ACEPTACION y habrian salido VERDES para siempre
            # —comprobado el 2026-08-23 caducando una entrada a proposito: el comprobador se
            # ponia rojo y `--verifica` seguia diciendo 0—. Se grita en vez de mentir.
            print("no se puede verificar por mutacion: " + solo + " esta declarado en "
                  "SIN_MUTACION. Para leer su veredicto usa `aceptacion.py " + solo + "`.",
                  file=sys.stderr)
            return 2
        return _verifica(solo)
    nombres = argv or list(COMPROBADORES)
    fallos = 0
    for n in nombres:
        fn = COMPROBADORES.get(n)
        if fn is None and n in CUMPLIDAS:
            print("  ✅ " + n + " " + CUMPLIDAS[n])
            continue
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
