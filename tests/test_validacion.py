"""`validate` — tests. Su razón de ser es el AVISO de caducidad, así que ahí está el peso.

Y el primer test no es de laboratorio: reproduce lo que `validate` encontró en su PRIMERA corrida
contra el registro real de un inquilino —una rama que se declaraba más fiable que su propia fuente,
que habría impedido arrancar la app al actualizar el paquete— porque eso es exactamente para lo que
existe: enterarse SIN arrancar la aplicación.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from capa_normativa.validacion import ERROR, LIMPIO, PROBLEMAS, main, validar

HOY = date(2026, 8, 12)

SCHEMA = """\
certainty_scale: [alta, moderada, baja, muy_baja, sin_respaldo]
weak_from: baja
unsupported_level: sin_respaldo
wildcards: [unknown, any]
evidence_certainty_field: certeza
evidence_year_field: anio
evidence_recent_field: reciente
recency_horizon: 2018
subject_dimensions: [sex]
"""

EVIDENCIA = """\
- id: EV-1
  cita: "Fuente de prueba 2020"
  certeza: moderada
  anio: 2020
  reciente: true
"""


def _registro(tmp_path, norms: str, *, schema: str = SCHEMA, evidencia: str = EVIDENCIA):
    (tmp_path / "schema.yaml").write_text(schema, encoding="utf-8")
    (tmp_path / "evidence.yaml").write_text(evidencia, encoding="utf-8")
    (tmp_path / "norms.yaml").write_text(norms, encoding="utf-8")
    return tmp_path


def _norma(slug="umbral", *, certainty="moderada", expires="2027-12-31", extra=""):
    return (f"- slug: {slug}\n"
            f"  title: Norma de prueba\n"
            f"  status: vigente\n"
            f"  strength: condicional\n"
            f"  certainty: {certainty}\n"
            f"  unit: unidades\n"
            f"  value: 1.0\n"
            f"  evidence: [EV-1]\n"
            f"  semantics: umbral\n"
            f'  expires: "{expires}"\n'
            f"{extra}")


def _retirada(slug="vieja", *, expires):
    """Una norma RETIRADA con `expires` — el caso que puso rojo un gate real por un no-motivo."""
    return (f"- slug: {slug}\n"
            f"  title: Norma retirada de prueba\n"
            f"  status: retirada\n"
            f"  strength: condicional\n"
            f"  certainty: moderada\n"
            f"  unit: unidades\n"
            f"  value: 1.0\n"
            f"  evidence: [EV-1]\n"
            f"  semantics: umbral\n"
            f'  expires: "{expires}"\n'
            f"  retirement:\n"
            f'    date: "2026-01-01"\n'
            f"    reason: se retiró porque ya no se sostenía\n"
            f"    replaced_by: []\n")


# ── lo que da sentido al módulo: el aviso ANTES de que la app no arranque ──

def test_avisa_de_lo_que_va_a_CADUCAR_sin_que_sea_un_error(tmp_path):
    """LA RAZÓN DE SER DE `validate`.

    `registry.py:464`: una norma `vigente` cuya `expires` ya pasó hace que `load()` LANCE, o sea que
    la aplicación NO ARRANCA. El diseño es correcto —es la mitad «niégate a servir lo rancio» del
    modelo gettext— pero sin aviso previo es una mina: se manifiesta como un despliegue que falla
    un martes, sin relación aparente con nada que se haya tocado.

    Y caducar PRONTO no es un error todavía: si lo fuera, alguien apagaría el aviso. Verde con
    advertencia.
    """
    cerca = (HOY + timedelta(days=20)).isoformat()
    repo = _registro(tmp_path, _norma(expires=cerca))
    inf = validar(repo, hoy=HOY, avisa_en=60)

    assert inf.ok, "caducar pronto NO es un error: si lo fuera, alguien apagaría el aviso"
    assert [s for s, _, _ in inf.caducan_pronto] == ["umbral"]
    assert inf.caducan_pronto[0][2] == 20, "los días que faltan son la información útil"


def test_lo_que_caduca_LEJOS_no_ensucia_el_aviso(tmp_path):
    """Un aviso que sale siempre no avisa de nada — el mismo fallo que el detector que dispara
    para todo (SEM001, `_MIN`/`_MAX`)."""
    lejos = (HOY + timedelta(days=300)).isoformat()
    inf = validar(_registro(tmp_path, _norma(expires=lejos)), hoy=HOY, avisa_en=60)
    assert inf.ok and inf.caducan_pronto == []


def test_el_horizonte_del_aviso_se_puede_ampliar(tmp_path):
    a_120 = (HOY + timedelta(days=120)).isoformat()
    repo = _registro(tmp_path, _norma(expires=a_120))
    assert validar(repo, hoy=HOY, avisa_en=60).caducan_pronto == []
    assert len(validar(repo, hoy=HOY, avisa_en=180).caducan_pronto) == 1


def test_una_norma_YA_caducada_es_un_ERROR_porque_no_arrancaria(tmp_path):
    """Aquí sí: si ya venció, `load()` lanza y la app no arranca. `validate` tiene que decir lo
    MISMO que diría el arranque, no algo más suave."""
    ayer = (HOY - timedelta(days=1)).isoformat()
    inf = validar(_registro(tmp_path, _norma(expires=ayer)), hoy=HOY)
    assert not inf.ok
    assert any("CADUCADA" in e for e in inf.errores), inf.errores


# ── enumerar, que es la otra mitad ──

def test_ENUMERA_los_errores_por_norma_en_vez_de_parar_en_el_primero(tmp_path):
    """`load()` para en el primero porque su trabajo es no arrancar; esto enumera porque su trabajo
    es que alguien arregle un fichero. Siete errores en siete corridas son seis viajes de más."""
    ayer = (HOY - timedelta(days=1)).isoformat()
    dos = _norma("una", expires=ayer) + _norma("otra", expires=ayer)
    inf = validar(_registro(tmp_path, dos), hoy=HOY)
    assert not inf.ok
    assert len(inf.errores) >= 2, f"solo enumeró {len(inf.errores)}: {inf.errores}"
    assert any("una" in e for e in inf.errores) and any("otra" in e for e in inf.errores)


def test_un_ESQUEMA_roto_NO_se_enumera_y_es_deliberado(tmp_path):
    """Todo lo demás depende del esquema, así que seguir tras uno roto produciría una cascada de
    errores DERIVADOS que ocultaría el único que importa. Un error, el de verdad."""
    inf = validar(_registro(tmp_path, _norma(), schema="certainty_scale: [alta]\n"), hoy=HOY)
    assert not inf.ok
    assert len(inf.errores) == 1, f"cascada en vez de la causa: {inf.errores}"


def test_una_rama_mas_fiable_que_su_FUENTE_se_caza(tmp_path):
    """EL CASO REAL, no uno inventado.

    En su primera corrida contra el registro de un inquilino real, `validate` encontró una rama que
    declaraba `certainty: baja` citando evidencia `muy_baja` — o sea que se presentaba como más
    fiable que su única fuente. Habría impedido arrancar la app al actualizar el paquete, y se
    detectó SIN arrancarla, que es literalmente para lo que existe este módulo.
    """
    ev = EVIDENCIA + ("- id: EV-FLOJA\n  cita: \"Documento interno\"\n"
                      "  certeza: muy_baja\n  anio: 2026\n  reciente: true\n")
    n = _norma(certainty="moderada").replace("evidence: [EV-1]", "evidence: [EV-FLOJA]")
    inf = validar(_registro(tmp_path, n, evidencia=ev), hoy=HOY)
    assert not inf.ok
    assert any("muy_baja" in e for e in inf.errores), inf.errores


# ── el informe de salud y el contrato de salida ──

def test_cuando_carga_da_el_CENSO(tmp_path):
    # ⚠️ La primera versión de este test ponía la norma `b` en `certainty: alta` citando evidencia
    # `moderada`, y el registro la RECHAZÓ con razón (v0.14.0 comprueba la procedencia por RAMA).
    # El dato de prueba estaba mal, no el código — así que hace falta una fuente `alta` de verdad.
    ev = EVIDENCIA + (
        "- id: EV-FUERTE\n"
        '  cita: "Revisión sistemática 2021"\n'
        "  certeza: alta\n"
        "  anio: 2021\n"
        "  reciente: true\n")
    b = _norma("b", certainty="alta", expires="").replace(
        "evidence: [EV-1]", "evidence: [EV-FUERTE]")
    inf = validar(_registro(tmp_path, _norma("a") + b, evidencia=ev), hoy=HOY)
    assert inf.ok and inf.total == 2
    assert inf.por_estado == {"vigente": 2}
    assert inf.por_certeza == {"alta": 1, "moderada": 1}
    assert inf.sin_fecha == 1, "una certeza fuerte no está obligada a caducar, y hay que verlo"


def test_falta_un_fichero_lo_dice_por_su_NOMBRE(tmp_path):
    (tmp_path / "schema.yaml").write_text(SCHEMA, encoding="utf-8")
    inf = validar(tmp_path, hoy=HOY)
    assert not inf.ok
    assert any("evidence.yaml" in e for e in inf.errores)
    assert any("norms.yaml" in e for e in inf.errores), "los dos, no solo el primero"


def test_el_contrato_de_salida_es_0_1_2(tmp_path, capsys):
    """Mismo contrato que el vigilante y `emit`: «falló» y «encontró cosas» exigen reacciones
    opuestas, y el consumidor previsto es un agente sin contexto."""
    (tmp_path / "ok").mkdir()
    limpio = _registro(tmp_path / "ok", _norma())
    assert main([str(limpio)]) == LIMPIO

    (tmp_path / "roto").mkdir()
    roto = _registro(tmp_path / "roto", _norma(expires=(HOY - timedelta(days=900)).isoformat()))
    assert main([str(roto)]) == PROBLEMAS

    assert main([str(tmp_path / "no_existe")]) == ERROR


def test_falla_si_caduca_en_convierte_el_aviso_en_GATE(tmp_path, capsys):
    """Para CI: el aviso solo protege si alguien lo mira. Esto lo convierte en un gate ANTES de
    que la caducidad tire la aplicación — que es la diferencia entre un mecanismo y un post-it."""
    cerca = (date.today() + timedelta(days=15)).isoformat()
    repo = _registro(tmp_path, _norma(expires=cerca))
    assert main([str(repo)]) == LIMPIO, "sin el flag, un aviso NO es un fallo"
    assert main([str(repo), "--falla-si-caduca-en", "30"]) == PROBLEMAS
    assert main([str(repo), "--falla-si-caduca-en", "5"]) == LIMPIO, "fuera del plazo, no falla"


# ── el gate mira SOLO a las que EMITEN, y esto es lo que faltaba probar ──

def test_una_RETIRADA_vencida_se_reporta_pero_NO_falla_el_gate(tmp_path):
    """EL CASO REAL, y el hueco por el que se coló.

    El 2026-08-13, en un inquilino, `long_run_share_cap` (status `retirada`, sustituida por
    `long_run_share_diagnostic`) llevaba `expires` duplicando su `retirement.date`. Con eso,
    `--falla-si-caduca-en` ponía el gate ROJO por una norma que **no emite** y que por
    construcción no puede impedir que arranque nada.

    El defecto sobrevivió porque el test del gate solo probaba con normas VIGENTES. Y la pista
    estaba escrita: el propio informe la imprimía como «no emiten, así que no rompen» mientras el
    exit code decía lo contrario.

    Contrato: se REPORTA (la fecha muerta miente a quien lee el YAML) pero no decide.
    """
    ayer = (date.today() - timedelta(days=1)).isoformat()
    # La vigente se pone LEJOS a propósito: así la única candidata a disparar el gate es la
    # retirada, y un rojo solo puede venir del defecto. (La primera versión de este test dejó el
    # `expires` por defecto —2027-12-31— y con horizonte 3650 la vigente lo disparaba con toda
    # la razón: el dato de prueba estaba mal, no el código.)
    lejos = (date.today() + timedelta(days=400)).isoformat()
    repo = _registro(tmp_path, _norma(expires=lejos) + _retirada(expires=ayer))

    inf = validar(repo)
    assert inf.ok, "una retirada vencida no rompe el registro: ni siquiera se resuelve"
    assert [(s, e) for s, _, e in inf.caducadas_inertes] == [("vieja", "retirada")], (
        "se sigue reportando: el aviso es útil aunque no decida")
    assert inf.caducan_pronto == [], "una que no emite tampoco entra en el aviso de caducidad"

    assert main([str(repo), "--falla-si-caduca-en", "30"]) == LIMPIO, (
        "el gate existe para anticipar que la app NO ARRANQUE; una retirada no puede causar eso")


def test_una_RETIRADA_que_caduca_PRONTO_tampoco_entra_en_el_gate(tmp_path):
    """La misma rama, un día antes. Si solo se filtrara lo ya vencido, la retirada seguiría
    disparando el gate mientras su `expires` estuviera dentro del horizonte — el mismo no-motivo
    con otra fecha."""
    cerca = (date.today() + timedelta(days=10)).isoformat()
    repo = _registro(tmp_path, _norma() + _retirada(expires=cerca))

    inf = validar(repo, avisa_en=60)
    assert inf.caducan_pronto == [] and inf.caducadas_inertes == []
    assert main([str(repo), "--falla-si-caduca-en", "30"]) == LIMPIO


def test_una_VIGENTE_vencida_SI_falla_el_gate(tmp_path):
    """La otra mitad del contrato: quitar el falso rojo no puede quitar el rojo de verdad.

    Una `vigente` vencida ni siquiera llega al gate — `load()` lanza y sale por `errores`— pero
    lo que importa es el exit code, que es lo que lee CI, y tiene que seguir siendo 1."""
    ayer = (date.today() - timedelta(days=1)).isoformat()
    repo = _registro(tmp_path, _norma(expires=ayer))

    assert main([str(repo), "--falla-si-caduca-en", "30"]) == PROBLEMAS
    assert main([str(repo)]) == PROBLEMAS, "y sin el flag también: no arranca"


def test_dice_que_NO_hay_nada_por_caducar_en_vez_de_callar(tmp_path, capsys):
    """Una ausencia no distingue «no hay nada» de «no lo miré». Mismo principio que hizo que el
    triaje diga «CERO» y que `emit` liste sus omitidas con motivo."""
    lejos = (date.today() + timedelta(days=400)).isoformat()
    main([str(_registro(tmp_path, _norma(expires=lejos)))])
    salida = capsys.readouterr().out
    assert "nada caduca" in salida


def test_el_json_trae_lo_MISMO_que_la_salida_humana(tmp_path, capsys):
    """Dos superficies que se pretenden equivalentes divergen. Si el JSON omitiera la caducidad, un
    consumidor por máquina no vería justo lo que este módulo existe para decir."""
    import json
    cerca = (date.today() + timedelta(days=10)).isoformat()
    main([str(_registro(tmp_path, _norma(expires=cerca))), "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["ok"] is True and d["total"] == 1
    assert d["caducan_pronto"] and d["caducan_pronto"][0][0] == "umbral"
    assert set(d) >= {"ok", "errores", "total", "por_estado", "por_certeza",
                      "sin_expires", "caducadas_inertes", "caducan_pronto"}


def test_NO_reimplementa_la_validacion(tmp_path):
    """El riesgo real de este módulo: dos validadores que se pretenden equivalentes DIVERGEN, y
    entonces `validate` diría verde sobre un registro que no arranca — peor que no tenerlo.

    Se comprueba por AST que usa `NormRegistry.load` y el `_parse_norm` del registro, en vez de
    reglas propias."""
    import ast
    import inspect

    from capa_normativa import validacion

    fuente = inspect.getsource(validacion)
    arbol = ast.parse(fuente)
    # ⚠️ `from .registry import X` da `module="registry"` con `level=1` — NO ".registry". La
    # primera versión comparaba con el punto delante y no encontraba nada, así que el test pasaba
    # a decir «no reusa el validador» sobre un módulo que sí lo reusa. Un falso positivo por no
    # saber la forma del AST, en un test que existe para cazar falsos verdes.
    importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)
                  for a in n.names if n.module == "registry" and n.level == 1}
    # `_EMITEN` entra en la lista desde la v0.16.1: saber QUIÉN emite es lo que decide el gate,
    # y una copia local ("status == 'vigente'") sería justo la divergencia que este test vigila
    # — el día que el registro añadiera un estado que emite, el gate dejaría de mirarlo.
    assert {"NormRegistry", "_parse_norm", "Schema", "_EMITEN"} <= importados, (
        f"validacion.py dejó de reusar el validador del registro: importa {importados}")
    assert "NormRegistry.load(" in fuente, "ya no pasa por el camino real de arranque"
    # Y se busca por AST, no por texto: la primera versión buscaba `'status == "vigente"'` en el
    # FUENTE y la cazó... dentro del comentario que explica por qué no se hace eso. Los
    # comentarios no están en el AST, así que aquí solo salta una constante de verdad.
    literales = {n.value for n in ast.walk(arbol)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "vigente" not in literales, (
        "quién emite lo decide `_EMITEN` en el registro, no un literal aquí")


def test_un_registro_REAL_de_ejemplo_no_hace_falta_para_nada(tmp_path):
    """El módulo no trae datos propios: valida lo que le des. Si algún día necesitara un registro
    de ejemplo para funcionar, habría dejado de ser agnóstico."""
    with pytest.raises(SystemExit):
        main(["--ayuda-inexistente"])
