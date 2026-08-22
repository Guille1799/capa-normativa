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
    'inv-revista-de-runtimes-quien-corre': ("cd C:/Users/Guille/proyectos/capa-normativa && python scripts/aceptacion.py revista-de-runtimes   (exit 0). HOY sale 2: 'desconocida: revista-de-runtimes. Conocidas: bug-git-como-subcadena-apaga, ...'. Rojo dos veces: no existe el comprobador, y aunque se escriba honesto sigue rojo mientras los cuatro interpretes declarados no cuadren con el manifiesto (hoy 0.16.2 / 0.7.0 / 0.16.1 / ausente). Ni un touch ni un .py vacio lo aprueban —el nombre tiene que estar en COMPROBADORES— y un stub que devuelva True lo caza la propia mutacion del tablero (`python scripts/aceptacion.py --verifica` marca 'no estaba ROJO de partida').",
        'construir: Revista de runtimes «quien-corre-que» — manifiesto interprete->paquete->version ejecutable'),
    'inv-test-hechos-que-caducan-barre': ('`C:/Users/Guille/proyectos/mcp_smart_context/venv/Scripts/python.exe -B -m pytest "tests/test_hechos_que_caducan.py::test_ninguna_afirmacion_sobre_un_DIRECTORIO_esta_caducada" -q -p no:cacheprovider` (exit 0), desde mcp_smart_context. Es la mas dura de las seis, porque nace roja por dos motivos independientes: hoy pytest sale 4 (el nodo no existe), y en cuanto se escriba de verdad saldra 1 hasta que se corrija promesa_gate.py:61 — el directorio Contexto/capa-normativa EXISTE, asi que el defecto que el nodo tiene que cazar esta ahi ahora mismo. Escribir el test no lo aprueba; solo lo aprueba arreglar el hecho.',
        'exprimir: test_hechos_que_caducan — barre rutas y versiones, pero no las afirmaciones sobre DIRECTORIOS'),
    'inv-test-hechos-que-caducan-barre': ('C:/Users/Guille/proyectos/mcp_smart_context/venv/Scripts/python.exe -c "import sys;sys.path.insert(0,r\'C:/Users/Guille/proyectos/mcp_smart_context/tests\');import test_hechos_que_caducan as t;sys.exit(0 if t._dir_muerto(\'Contexto/no_existe_xyz/\') and not t._dir_muerto(\'Contexto/capa-normativa/\') else 1)"   (HOY ROJO: `_dir_muerto` no existe, AttributeError. No lo aprueba un stub constante: tiene que decir True para la carpeta inexistente Y False para una que existe desde ayer, o sea mirar el disco. Nace roja aunque hoy no haya ningun puntero-a-carpeta muerto en el arbol, porque interroga al detector, no a la cosecha.)',
        'exprimir: test_hechos_que_caducan — barre rutas muertas y versiones falsas pero se le escapan las afirmaciones de existe'),
    'inv-capa-normativa-es-el-unico': ('Comprobador de COMPORTAMIENTO nuevo, colgado del tablero que ya existe: `python C:/Users/Guille/proyectos/capa-normativa/scripts/aceptacion.py --verifica guardia-de-commit`. Contrato: (1) resuelve la ruta EFECTIVA del hook con `git -C capa-normativa rev-parse --git-path hooks` (no mira .git/hooks a ciegas, que es como se colo el shim fantasma de eu); (2) exige que exista ahi un `pre-commit`; (3) monta un repo de pega bajo %TEMP% con `git init`, apunta su core.hooksPath a ese mismo pre-commit, prepara un fichero envenenado con un secreto de laboratorio y un .py que no parsea, e intenta `git commit` — y EXIGE exit != 0. Hoy sale ROJO en el paso (2) porque no hay pre-commit ninguno. Un `touch .git/hooks/pre-commit` o un fichero vacio pasan (2) pero fallan (3), que es donde esta el trabajo de verdad. Es el mismo patron de canario (entrada envenenada conocida -> el guardian DEBE gritar) que capa_normativa.vigilante.canario ya usa en produccion.',
        'arreglar: capa-normativa es el unico repo sin pre-commit — y es el que ALOJA al vigilante'),
    'inv-audit-settings-source-sh-no': ('Si se retira: `python -c "import json,os,sys; t=json.dumps(json.load(open(r\'C:/Users/Guille/.claude/settings.json\',encoding=\'utf-8\'))); sys.exit(1 if (\'audit_settings_source\' in t or os.path.exists(r\'C:/Users/Guille/.claude/hooks/audit_settings_source.sh\')) else 0)"` — hoy ROJO por las dos mitades (registrado Y presente en disco); solo pasa desregistrandolo y borrandolo. Si en vez de retirarlo se quiere conservar la capacidad, entonces la aceptacion es un CANARIO, no un diff: `python C:/Users/Guille/proyectos/capa-normativa/scripts/aceptacion.py --verifica canario-settings`, que copia el settings.json vigente a un sandbox de %TEMP%, le INYECTA un hook de laboratorio que el snapshot revisado no contiene, corre el guardian contra esa copia y EXIGE exit != 0 o el aviso por stderr. Hoy ROJO porque el guardian pregunta por la autoria y no por el contenido, asi que ante un settings envenenado se calla. Un diff contra el snapshot NO vale como aceptacion: hoy los dos ficheros son identicos y nacería verde.',
        'retirar: audit_settings_source.sh — no puede avisar nunca, por dos motivos independientes'),
    'inv-autohealth-monitor-py-con-guion': ("En vez de un `test ! -f` suelto (que arregla este caso y ninguno mas), un barredor de caducidades que hace cumplir la regla que el REGISTRO ya se dio a si mismo: `python C:/Users/Guille/proyectos/capa-normativa/scripts/aceptacion.py --verifica registro-sin-caducados`. Contrato: parsea REGISTRO.md, y por cada entrada con `CADUCA: <fecha>` anterior a hoy exige que su `ESTADO:` sea RETIRADO **y** que el artefacto que nombra ya no exista en disco. Hoy sale ROJO citando 'autohealth-monitor.py (con guion)': CADUCA 2026-08-19, ESTADO 'pendiente de decision', y el fichero sigue en ~/.claude/hooks. No se puede aprobar creando ficheros — solo borrando el fichero Y marcando la entrada—, y como se apoya en la fecha, se pone rojo el solo la proxima vez que caduque algo, sin que nadie tenga que acordarse.",
        'retirar: autohealth-monitor.py (con guion) — fichero de hook que no registra nadie'),
    'inv-registro-md-session-start-sh': ("`python C:/Users/Guille/proyectos/scripts/aceptacion.py censo-de-guardianes` — hoy ROJA porque C:/Users/Guille/proyectos/scripts/ NO EXISTE (verificado: Test-Path = False), y un fichero vacío tampoco la aprueba: el tablero contesta `desconocida: censo-de-guardianes` y sale 2. Solo pasa cuando el comprobador ENUMERE los guardianes de sus fuentes vivas (entradas de hook de ~/.claude/settings.json, repos con pre-commit, `Get-ScheduledTask` de TaskPath '\\', ficheros aceptacion.py) y exija una cabecera '## ' en REGISTRO.md por cada uno — hoy 14 contra 29.",
        'exprimir: REGISTRO.md + session_start.sh — el censo que existe pero no censa a los guardianes'),
    'inv-canario-py-aceptacion-py-verifica': ('`python C:/Users/Guille/proyectos/capa-normativa/scripts/aceptacion.py canario-de-los-hooks` — hoy ROJA: el nombre no existe en COMPROBADORES, el tablero imprime `desconocida:` y sale 2. Solo pasa cuando exista un comprobador que, para CADA una de las 10 entradas de hook de ~/.claude/settings.json, le entregue por stdin una carga envenenada conocida y exija que el hook grite (exit≠0 o mensaje de bloqueo), y que LANCE — no que salte en silencio — ante cualquier hook sin caso, replicando el contrato de CASOS. Un stub que devuelva True no la aprueba: `python scripts/aceptacion.py --verifica` la tumba con «no estaba ROJO de partida». Acción gemela y verificable: `canario-completo` debe desaparecer del tablero (hoy sale 0, medido).',
        'exprimir: canario.py + aceptacion.py --verifica — la prueba por mutación existe y cubre 4 detectores de ~29 guardianes'),
    'inv-capa-normativa-declarado-en-el': ('python -c "import re,glob,yaml,sys,pathlib;R=pathlib.Path(r\'C:\\\\Users\\\\Guille\\\\proyectos\\\\mcp_smart_context\');y=yaml.safe_load((R/\'projects_config.yaml\').read_text(encoding=\'utf-8\'));esp={p[\'name\'] for p in y[\'projects\'] if p.get(\'enabled\')};L=max(glob.glob(str(R/\'logs\'/\'context_watcher_master_*.log\')),key=lambda f:pathlib.Path(f).stat().st_mtime);seg=open(L,encoding=\'utf-8\',errors=\'ignore\').read().rsplit(\'=\'*80,1)[-1];w={m.strip() for m in re.findall(r\'Watching:\\\\s*(\\\\S.*)\',seg)};sys.exit(0 if len(w)>=len(esp) else 1)"  — EJECUTADO HOY: vigiladas=5, esperadas=6, EXIT=1 (ROJO). Solo pasa reiniciando el demonio, que reemite las lineas \'Watching:\'; ni un touch ni un fichero vacio lo aprueban porque cuenta rutas realmente vigiladas contra proyectos enabled del YAML.',
        'arreglar: capa_normativa declarado en el YAML pero fuera del vigilante'),
}


def _fabrica_inv(nombre, comando, resumen):
    """Corre el comando de aceptacion del inventario y lee su EXIT CODE.

    No opina sobre nada: pregunta por un exit code, que es la regla. El comando lo escribio el
    esceptico que verifico el hallazgo, no quien va a hacer el trabajo — esa separacion es lo
    que impide aprobar ablandando la prueba.
    """
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
    from capa_normativa.vigilante.arbol_propio import revisar_arbol_propio
    otras = {n: f for n, f in COMPROBADORES.items() if n != "sondas-miran-su-arbol"}
    hallazgos = revisar_arbol_propio(otras, RAIZ)
    if hallazgos:
        return False, (str(len(hallazgos)) + " sonda(s) juzgan otro arbol: "
                       + ", ".join(h.fichero for h in hallazgos))
    return True, "las " + str(len(otras)) + " sondas miran su propio arbol"


SIN_MUTACION = {
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
    "contexto-propio": [(str(DECISION), "decidido: no" + chr(10) + "motivo: stub" + chr(10))],
}
COMPROBADORES = {
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
    "canario-completo": canario_completo,
    "contexto-propio": contexto_propio,
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
