"""SEM001 — tests. El primero es EL CASO REAL, no un ejemplo de laboratorio.

Lección del 2026-08-11 (PTR001 dijo «limpio» con 8 punteros roídos un nivel más abajo): *la forma
del test copiaba la forma del bug*, porque todos los corpus de prueba eran de un solo nivel. Así
que aquí el primer test reproduce el fallo medido en el inquilino —`_PLANNED_LOAD_CARB_GKG_CAP`
apuntando a `carb_floor_g_per_kg_ffm`, mismo 1,5, significado opuesto— y los demás atacan lo que
podría dejarlo callado.
"""
from __future__ import annotations

import pytest

from capa_normativa.vigilante import OPUESTOS, revisar_semantica

SEMANTICA = {
    "carb_floor_g_per_kg_ffm": "suelo",
    "long_run_target_km": "objetivo",
    "weekly_ramp_ceiling": "techo",
    "ea_watch_threshold": "umbral",
}


def _escribe(tmp_path, texto: str, nombre: str = "motor.py"):
    (tmp_path / nombre).write_text(texto, encoding="utf-8")
    return tmp_path


# ── el caso real ──

def test_caza_el_TOPE_apuntando_a_un_SUELO(tmp_path):
    """El fallo medido: pasó el gate del inquilino en verde (2634 tests) porque el valor no
    cambiaba. Nada miraba el significado."""
    repo = _escribe(tmp_path, '''
from engine.norms import NORMS
_PLANNED_LOAD_CARB_GKG_CAP = NORMS.resolve("carb_floor_g_per_kg_ffm").value
''')
    hs = revisar_semantica(repo, SEMANTICA)
    assert len(hs) == 1, f"esperaba 1 hallazgo, salieron {len(hs)}: {hs}"
    h = hs[0]
    assert h.codigo == "SEM001"
    assert h.linea == 3
    assert h.fichero == "motor.py", "el fichero debe ser RELATIVO al repo"
    assert "TECHO" in h.mensaje and "suelo" in h.mensaje
    assert "COMENTARIO" in h.arreglo, "el arreglo tiene que mandar leer el comentario, no el valor"


def test_caza_tambien_el_SUELO_apuntando_a_un_TECHO(tmp_path):
    """La simetría no se da gratis: con una tabla de opuestos mal escrita solo salta un sentido."""
    repo = _escribe(tmp_path, '_X_FLOOR_KM = NORMS.resolve("weekly_ramp_ceiling").value\n')
    hs = revisar_semantica(repo, SEMANTICA)
    assert len(hs) == 1 and hs[0].codigo == "SEM001"


# ── lo que lo mantiene CALLADO (un detector que dispara para todo no señaliza nada) ──

def test_una_polaridad_COMPATIBLE_no_salta(tmp_path):
    repo = _escribe(tmp_path, '_CARB_FLOOR = NORMS.resolve("carb_floor_g_per_kg_ffm").value\n')
    assert revisar_semantica(repo, SEMANTICA) == []


def test_un_nombre_SIN_polaridad_no_salta(tmp_path):
    """La mayoría de las constantes no dicen nada de su polaridad, y sobre esas este detector no
    tiene nada que decir. Reconocerlo es lo que lo hace utilizable."""
    repo = _escribe(tmp_path, '_CARB_GKG = NORMS.resolve("carb_floor_g_per_kg_ffm").value\n')
    assert revisar_semantica(repo, SEMANTICA) == []


def test_una_semantics_NEUTRA_no_salta(tmp_path):
    """`objetivo`/`umbral` no contradicen a un tope: no son su opuesto, son otra cosa. Marcarlas
    convertiría el detector en ruido."""
    repo = _escribe(tmp_path, '''
_A_CAP = NORMS.resolve("long_run_target_km").value
_B_CAP = NORMS.resolve("ea_watch_threshold").value
''')
    assert revisar_semantica(repo, SEMANTICA) == []


def test_un_slug_DESCONOCIDO_se_ignora_en_silencio(tmp_path):
    """El inquilino puede pasar un mapa parcial. Inventar hallazgos sobre normas que no conoce
    sería peor que callar."""
    repo = _escribe(tmp_path, '_X_CAP = NORMS.resolve("norma_que_no_esta_en_el_mapa").value\n')
    assert revisar_semantica(repo, SEMANTICA) == []


def test_CAPACITY_no_cuenta_como_CAP(tmp_path):
    """El delimitador `(?:^|_)…(?:_|$)`. Con un `in` ingenuo, todo lo que contenga «cap» saltaría."""
    repo = _escribe(tmp_path, '_CAPACITY_LITERS = NORMS.resolve("carb_floor_g_per_kg_ffm").value\n')
    assert revisar_semantica(repo, SEMANTICA) == []


def test_MIN_y_MAX_desnudos_NO_estan_en_el_vocabulario(tmp_path):
    """Decisión heredada del triaje del inquilino, donde marcaron el 100 % de las constantes:
    `_MIN_READINGS`/`_LAPS_MIN_N` son tamaños de muestra, no guardarraíles."""
    repo = _escribe(tmp_path, '''
_MIN_READINGS = NORMS.resolve("weekly_ramp_ceiling").value
_MAX_ENTRIES = NORMS.resolve("carb_floor_g_per_kg_ffm").value
''')
    assert revisar_semantica(repo, SEMANTICA) == []


# ── formas del código que podrían escapársele ──

def test_encuentra_el_FLOOR_en_medio_del_nombre(tmp_path):
    """`\\b` NO sirve aquí: el guion bajo es carácter de palabra, así que `_FLOOR_G_PER_KG` no
    tendría frontera tras la R. Es la forma más común en el inquilino y se escaparía entera."""
    repo = _escribe(tmp_path, '_CARB_FLOOR_G_PER_KG_FFM = NORMS.resolve("weekly_ramp_ceiling").value\n')
    assert len(revisar_semantica(repo, SEMANTICA)) == 1


def test_funciona_SIN_el_punto_value(tmp_path):
    repo = _escribe(tmp_path, '_X_CAP = NORMS.resolve("carb_floor_g_per_kg_ffm")\n')
    assert len(revisar_semantica(repo, SEMANTICA)) == 1


def test_funciona_con_kwargs_y_con_otro_receptor(tmp_path):
    """No se exige que el registro se llame `NORMS`: el inquilino lo nombra como quiera."""
    repo = _escribe(tmp_path,
                    '_X_CAP = registro.resolve("carb_floor_g_per_kg_ffm", sex="male").value\n')
    assert len(revisar_semantica(repo, SEMANTICA)) == 1


def test_pilla_el_DESEMPAQUETADO_de_tupla(tmp_path):
    """La ceguera que costó 10 constantes en el inquilino (el tope SUBIÓ de 271 a 279 el
    2026-07-30 al arreglarla). Aquí se cubre desde el principio, no después del incidente."""
    repo = _escribe(tmp_path, '_A_CAP, _B_FLOOR = NORMS.resolve("carb_floor_g_per_kg_ffm").value, 3\n')
    hs = revisar_semantica(repo, SEMANTICA)
    assert len(hs) == 1 and "_A_CAP" in hs[0].mensaje


def test_recorre_SUBDIRECTORIOS(tmp_path):
    """PTR001 dijo «limpio» con 8 hallazgos un nivel más abajo porque no recursaba, y sus 8 tests
    eran todos de un nivel. La forma del test copiaba la forma del bug."""
    hondo = tmp_path / "engine" / "sub"
    hondo.mkdir(parents=True)
    (hondo / "x.py").write_text('_Y_CAP = NORMS.resolve("carb_floor_g_per_kg_ffm").value\n',
                                encoding="utf-8")
    hs = revisar_semantica(tmp_path, SEMANTICA)
    assert len(hs) == 1 and hs[0].fichero == "engine/sub/x.py"


def test_ignora_venv_y_site_packages(tmp_path):
    """Sin esto, el detector se dispara contra el propio paquete instalado del inquilino."""
    v = tmp_path / "venv" / "Lib" / "site-packages"
    v.mkdir(parents=True)
    (v / "ajeno.py").write_text('_Z_CAP = NORMS.resolve("carb_floor_g_per_kg_ffm").value\n',
                                encoding="utf-8")
    assert revisar_semantica(tmp_path, SEMANTICA) == []


def test_un_fichero_ROTO_no_tumba_la_pasada(tmp_path):
    """Un `SyntaxError` es cosa de SYN001. Este detector tiene que seguir y encontrar el resto —
    si abortara, un fichero roto ocultaría todos los hallazgos posteriores."""
    (tmp_path / "roto.py").write_text("def (:\n", encoding="utf-8")
    (tmp_path / "bueno.py").write_text('_Q_CAP = NORMS.resolve("carb_floor_g_per_kg_ffm").value\n',
                                       encoding="utf-8")
    hs = revisar_semantica(tmp_path, SEMANTICA)
    assert len(hs) == 1 and hs[0].fichero == "bueno.py"


def test_lee_utf8_con_BOM(tmp_path):
    """`utf-8` en vez de `utf-8-sig` fue 8 falsos positivos de 9 en el detector de sintaxis. La
    misma palabra, el mismo error, y aquí ya está pagado."""
    (tmp_path / "bom.py").write_bytes(
        b"\xef\xbb\xbf_W_CAP = NORMS.resolve(\"carb_floor_g_per_kg_ffm\").value\n")
    assert len(revisar_semantica(tmp_path, SEMANTICA)) == 1


# ── contrato ──

def test_sin_mapa_devuelve_vacio_pero_es_responsabilidad_del_inquilino(tmp_path):
    """Documenta el agujero en vez de esconderlo: sin mapa no hay nada que comparar. El inquilino
    tiene que comprobar con un test que su mapa llega LLENO — es el no-op silencioso, el modo de
    fallo nº 1 de este arnés."""
    repo = _escribe(tmp_path, '_X_CAP = NORMS.resolve("carb_floor_g_per_kg_ffm").value\n')
    assert revisar_semantica(repo, {}) == []
    assert revisar_semantica(repo, None) == []


def test_la_tabla_de_OPUESTOS_es_simetrica():
    """Si `techo` considera opuesto a `suelo` pero `suelo` no a `techo`, la mitad de los fallos
    pasa. La simetría no la garantiza nada del código: la garantiza este test."""
    for pol, contrarios in OPUESTOS.items():
        for c in contrarios:
            if c in OPUESTOS:
                assert pol in OPUESTOS[c], f"`{pol}` ve opuesto a `{c}` pero no al revés"


def test_repo_inexistente_no_pasa_por_vacio(tmp_path):
    """Devolver `[]` ante una ruta mala sería el gate verde por no haber mirado nada."""
    with pytest.raises(FileNotFoundError):
        revisar_semantica(tmp_path / "no_existe", SEMANTICA)
