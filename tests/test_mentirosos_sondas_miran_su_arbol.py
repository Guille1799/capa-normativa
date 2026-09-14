"""MENTIROSOS de `sondas-miran-su-arbol`: siete sondas de pega que juzgan al vecino.

## Qué es un mentiroso

Una implementación **completa** de la cosa que el comprobador juzga —aquí, una sonda de tablero—
rota por **UNA sola razón**, con el test exigiendo que caiga **en SU caso**:

    assert not ok                 -> tiene que SUSPENDER
    assert pista in motivo        -> y por SU razón, no por otra

Cada mentiroso hace su trabajo entero y bien; lo único que le falla es **por qué puerta toca el
disco**. Por eso cada uno deja su huella en un fichero con nombre propio: así el test no comprueba
sólo que la sonda caiga, sino que el detector vio **esa** fuga y no otra.

## Qué protege

El 2026-08-22 tres sondas de `ponerse_wenorro` —escritas justamente para cazar fallos de
aislamiento— llevaban la ruta al checkout principal ESCRITA A MANO. El agente arreglaba su copia,
ellas abrían la de al lado, decían ROJO, y el bucle autónomo destruía trabajo correcto. **Sin
síntoma**: por la mañana el registro decía lo mismo que si el agente no hubiera hecho nada.

Y el detector OBSERVA en vez de leer el fuente, que es donde está su valor. Un lint que busque
rutas escritas no ve ninguna de las tres formas que ya han ocurrido en estos repos: `GIT_DIR`
secuestrando a los detectores, un paquete instalado y viejo tapando al fuente, y una ruta relativa
resuelta contra el directorio equivocado. En las tres, el fuente está limpio.

## Por qué las puertas se prueban una a una

`_PUERTAS` tiene veintitantas entradas porque **parchear `os.stat` no captura NADA en Windows**:
desde CPython 3.12 `os.path.exists` está escrito en C y no pasa por `os.stat`. O sea que la puerta
más usada de todas —preguntar si un fichero existe— fue invisible para la primera versión de esto.
Un mentiroso por puerta es lo que impide que esa ceguera vuelva sin que nadie se entere.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from capa_normativa.vigilante.arbol_propio import revisar_arbol_propio  # noqa: E402

#: Dos árboles HERMANOS de pega: el que se juzga y el de al lado. Se montan en el disco porque el
#: detector observa de verdad —abre, consulta, ejecuta— y un doble en memoria no probaría nada.
_RAIZ = Path(tempfile.mkdtemp(prefix="mentirosos-arbol-"))
PROPIO = _RAIZ / "capa-normativa"
HERMANO = _RAIZ / "cn-otro-worktree"


def _montar():
    for arbol in (PROPIO, HERMANO):
        (arbol / "scripts").mkdir(parents=True, exist_ok=True)
        (arbol / "PENDIENTES.md").write_text("- cola de " + arbol.name, encoding="utf-8")
        for fichero in ("leido-con-open.txt", "leido-con-pathlib.txt", "preguntado-si-existe.txt",
                        "ejecutado-por-argumento.txt", "leido-por-ruta-relativa.txt"):
            (arbol / fichero).write_text("contenido de " + arbol.name, encoding="utf-8")
        (arbol / "carpeta-listada").mkdir(exist_ok=True)
        (arbol / "desde-aqui").mkdir(exist_ok=True)


_montar()


@pytest.fixture(scope="module", autouse=True)
def _limpiar():
    yield
    shutil.rmtree(_RAIZ, ignore_errors=True)


def _fabrica(*, arbol_que_mira=None):
    """Una sonda de tablero de pega: lee la cola de SU árbol y dice si está vacía.

    Por defecto es la HONESTA — mira `PROPIO`. Pasarle `HERMANO` produce la mentira, y es la única:
    hace exactamente el mismo trabajo, sobre el árbol de al lado.
    """
    base = arbol_que_mira or PROPIO

    def sonda():
        texto = (base / "PENDIENTES.md").read_text(encoding="utf-8")
        return ("cola" in texto), "la cola de " + base.name

    return sonda


HONESTO = _fabrica()


def _sonda(fn):
    """El detector de verdad, con UNA sonda delante. `(aprueba, por qué no)`."""
    hallazgos = revisar_arbol_propio({"sonda-de-pega": fn}, PROPIO, hermanos=[HERMANO])
    return not hallazgos, " · ".join(h.mensaje for h in hallazgos)


# --- las siete puertas, una por mentiroso -------------------------------------------------------
#
# Todos hacen el MISMO trabajo honesto (leer la cola del árbol propio) y además tocan el árbol de
# al lado por una puerta distinta. Así la razón por la que caen es separable: si el detector se
# queda ciego a una puerta, sólo se apaga su mentiroso, y el fichero dice cuál.

def _honesto_primero():
    (PROPIO / "PENDIENTES.md").read_text(encoding="utf-8")


def _abre_con_open():
    _honesto_primero()
    with open(str(HERMANO / "leido-con-open.txt"), encoding="utf-8") as f:
        f.read()


def _lee_con_pathlib():
    _honesto_primero()
    (HERMANO / "leido-con-pathlib.txt").read_text(encoding="utf-8")


def _pregunta_si_existe():
    _honesto_primero()
    (HERMANO / "preguntado-si-existe.txt").exists()


def _lista_la_carpeta_del_vecino():
    _honesto_primero()
    list((HERMANO / "carpeta-listada").glob("*"))


def _corre_un_proceso_dentro_del_vecino():
    _honesto_primero()
    subprocess.run([sys.executable, "-c", "pass"], cwd=str(HERMANO / "desde-aqui"),
                   capture_output=True, timeout=120)


def _nombra_al_vecino_en_el_comando():
    _honesto_primero()
    subprocess.run([sys.executable, "-c", "pass", str(HERMANO / "ejecutado-por-argumento.txt")],
                   capture_output=True, timeout=120)


def _sale_del_arbol_por_una_ruta_relativa():
    """La forma sin ninguna ruta escrita: `..` y el nombre del vecino, resuelto contra el cwd."""
    _honesto_primero()
    relativa = os.path.join("..", HERMANO.name, "leido-por-ruta-relativa.txt")
    with open(relativa, encoding="utf-8") as f:
        f.read()


MENTIROSOS = {
    # La puerta clásica: `builtins.open` con una ruta absoluta al vecino.
    "abre_con_open": (_abre_con_open, "abrio", "leido-con-open.txt"),
    # `Path.read_text`, que es como se escribe hoy y NO pasa por `builtins.open` en 3.10.
    "lee_con_pathlib": (_lee_con_pathlib, "abrio", "leido-con-pathlib.txt"),
    # Preguntar si un fichero existe: la puerta más usada de todas, y la que estuvo ciega.
    "pregunta_si_existe": (_pregunta_si_existe, "consulto", "preguntado-si-existe.txt"),
    # Listar una carpeta del vecino no abre nada, y ya es juzgar otro árbol.
    "lista_la_carpeta_del_vecino": (_lista_la_carpeta_del_vecino, "consulto", "carpeta-listada"),
    # El `cwd`: la forma SILENCIOSA de acabar en otro árbol sin escribir ninguna ruta, y además
    # manda sobre cómo resuelven las relativas del comando.
    "corre_un_proceso_dentro_del_vecino": (_corre_un_proceso_dentro_del_vecino, "ejecuto",
                                           "desde-aqui"),
    # La ruta del vecino viaja en los argumentos del comando, no en el `cwd`.
    "nombra_al_vecino_en_el_comando": (_nombra_al_vecino_en_el_comando, "ejecuto",
                                       "ejecutado-por-argumento.txt"),
    # Ninguna ruta escrita en el fuente: `..` más el nombre del vecino. Un lint no ve esto.
    "sale_del_arbol_por_una_ruta_relativa": (_sale_del_arbol_por_una_ruta_relativa, "abrio",
                                             "leido-por-ruta-relativa.txt"),
}


def test_la_sonda_honesta_APRUEBA():
    """Mira su propio árbol y hace su trabajo. Sin esto, los mentirosos caerían gratis."""
    ok, motivo = _sonda(HONESTO)
    assert ok, motivo


@pytest.mark.parametrize("nombre", sorted(MENTIROSOS))
def test_cada_mentiroso_lo_caza_UNA_exigencia_distinta(nombre):
    fn, verbo, huella = MENTIROSOS[nombre]
    ok, motivo = _sonda(fn)
    assert not ok, nombre + " aprobo, y estaba juzgando el arbol de al lado"
    assert huella in motivo, nombre + " cae por otra fuga, no por la suya -> " + motivo
    assert verbo in motivo, nombre + " cae por la puerta equivocada -> " + motivo


def test_una_sonda_DECLARADA_puede_mirar_fuera():
    """La puerta de los auditores cruzados, y sin ella el guarda gritaría en falso para siempre.

    «Todos los repos tienen su pre-commit» toca los demás árboles porque ése ES su trabajo. Se
    declara con su motivo —igual que `SIN_MUTACION`— en vez de silenciarse a secas: una excepción
    escrita se revisa; una implícita se hereda. Y un guarda que grita en falso todos los días es un
    guarda que alguien acaba apagando.
    """
    hallazgos = revisar_arbol_propio(
        {"auditor-cruzado": _abre_con_open}, PROPIO, hermanos=[HERMANO],
        permitidos={"auditor-cruzado": "audita los N repos a la vez: mirar fuera es su trabajo"})
    assert not hallazgos, "una excepcion declarada no puede acusar: " + str(hallazgos)
