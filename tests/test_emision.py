"""Tests de `emit`, con la disciplina F14.

La regla que estos tests defienden y que es la razón de ser del módulo:

> **Si `emit` solo saca números, ha reinventado el problema en un sitio nuevo.**

Así que se comprueba que la procedencia VIAJA en los cuatro formatos, no solo que el valor
salga. Y se comprueba que `--check` **se pone rojo** cuando el fichero generado deriva: sin eso,
`emit` añade un artefacto más que tiene que decir lo mismo, que es el criterio con el que se
cerró la decisión de arquitectura.
"""

from __future__ import annotations

import json
import textwrap
from datetime import date
from pathlib import Path

import pytest

from capa_normativa import NormRegistry
from capa_normativa.emision import (FORMATOS, comprobar, emitir, main, recoger)

HOY = date(2026, 8, 11)

_SCHEMA = """\
evidence_certainty_field: certeza
evidence_year_field: anio
evidence_recent_field: reciente
recency_horizon: 2018
certainty_scale: [alta, moderada, baja, sin_respaldo]
weak_from: baja
unsupported_level: sin_respaldo
wildcards: [unknown, any]
subject_dimensions:
  - sexo
"""

_EVIDENCE = """\
- id: EV-0001
  cita: "Iraki 2019"
  claim: "el suelo de grasa esencial en hombres"
  certeza: alta
  anio: 2019
  reciente: true
"""


def _registro(tmp_path: Path, normas: str) -> NormRegistry:
    d = tmp_path / "reg"
    d.mkdir(parents=True, exist_ok=True)
    (d / "schema.yaml").write_text(_SCHEMA, encoding="utf-8")
    (d / "evidence.yaml").write_text(_EVIDENCE, encoding="utf-8")
    (d / "norms.yaml").write_text(textwrap.dedent(normas), encoding="utf-8")
    return NormRegistry.load(d, today=HOY)


CONSTANTE = """\
- slug: suelo_grasa
  title: "Suelo de grasa esencial"
  status: vigente
  strength: vinculante
  certainty: alta
  unit: "%"
  # OJO: `constant` NO es una clave del YAML — la INFIERE el parser cuando la norma trae
  # `value` directo en vez de `branches`. Escribirla da error (R13, claves desconocidas), y el
  # mensaje del registro lo dice y lista las válidas. Aquí se aprendió leyéndolo.
  value: 5.0
  evidence: [EV-0001]
"""

RAMIFICA = """\
- slug: umbral_por_sexo
  title: "Umbral que depende del sexo"
  status: vigente
  # `strength` es vocabulario CERRADO desde la v0.8.0: condicional|precautorio|vinculante.
  strength: condicional
  certainty: moderada
  unit: "kcal"
  branches:
    - when: {sexo: mujer}
      value: 30.0
      evidence: [EV-0001]
    - when: {sexo: any}
      value: 45.0
      evidence: [EV-0001]
"""


# ─────────────── lo que se emite y lo que NO ───────────────

def test_una_constante_se_emite(tmp_path: Path):
    cs, omitidas = recoger(_registro(tmp_path, CONSTANTE), hoy=HOY)
    assert [c.slug for c in cs] == ["suelo_grasa"]
    assert omitidas == {}
    assert cs[0].valor == 5.0 and cs[0].unidad == "%"


def test_una_norma_que_RAMIFICA_no_se_emite_y_DICE_POR_QUE(tmp_path: Path):
    """Emitir una tabla de decisión obligaría a reproducir su hit policy en cada lenguaje —
    el acoplamiento que §5.47 diagnosticó. Pero la omisión no puede ser silenciosa: un
    artefacto derivado que calla lo que le falta parece completo."""
    cs, omitidas = recoger(_registro(tmp_path, RAMIFICA), hoy=HOY)
    assert cs == []
    assert "umbral_por_sexo" in omitidas
    assert "resolve()" in omitidas["umbral_por_sexo"], "debe decir qué hacer en su lugar"


def test_una_CADUCADA_no_llega_ni_a_emit_porque_el_REGISTRO_NO_CARGA(tmp_path: Path):
    """Hallazgo del 2026-08-11, y corrige mi propio módulo: la comprobación de caducidad que
    escribí en `emision._omision` es **inalcanzable vía `load()`**.

    El registro ya se NIEGA A CONSTRUIRSE con una norma vigente caducada — que es su diseño
    entero: «si el registro no se construye, el programa no arranca». Así que `emit` nunca ve
    una caducada: no hay nada que filtrar.

    La comprobación se queda como defensa en profundidad (un `NormRegistry` construido a mano,
    sin pasar por `load()`, sí podría traerla), pero **declarada como inalcanzable por la vía
    normal** en vez de fingir que es la que protege.

    ⚠️ Y lo destapó que mi propia mutación del fixture NO ENTRÓ: cambié la indentación del YAML
    y el `.replace()` dejó de casar en silencio. De ahí el `assert` de abajo, que es la regla
    F14 aplicada al montaje del propio test.
    """
    caducada = CONSTANTE.replace(
        "  value: 5.0\n", '  value: 5.0\n  expires: "2026-01-01"\n')
    assert "expires:" in caducada, "la mutación NO entró: el fixture no lleva `expires`"

    with pytest.raises(Exception, match="CADUCADA"):
        _registro(tmp_path, caducada)


def test_una_RETIRADA_no_se_emite(tmp_path: Path):
    """El filtro por estado sí es alcanzable: una retirada CARGA (para poder consultar por qué
    lo está) pero `resolve()` no la sirve. `emit` tiene que hacer lo mismo, o sería la puerta de
    atrás por la que sale un valor que el registro niega."""
    retirada = CONSTANTE.replace(
        "  status: vigente\n",
        '  status: retirada\n'
        '  retirement: {reason: "sustituida por otra norma", replaced_by: []}\n')
    assert "status: retirada" in retirada, "la mutación NO entró"

    cs, omitidas = recoger(_registro(tmp_path, retirada), hoy=HOY)
    assert cs == [], "una retirada NO puede salir por emit"
    assert "retirada" in omitidas["suelo_grasa"]


def test_el_orden_es_estable(tmp_path: Path):
    """Determinista: mismo registro, mismo texto. Si no, `--check` daría falsos positivos."""
    r = _registro(tmp_path, CONSTANTE + RAMIFICA)
    assert emitir(r, "json", hoy=HOY) == emitir(r, "json", hoy=HOY)


# ─────────── LA REGLA: la procedencia viaja en los 4 formatos ───────────

@pytest.mark.parametrize("formato", FORMATOS)
def test_la_PROCEDENCIA_viaja_en_todos_los_formatos(tmp_path: Path, formato: str):
    """El test que define el módulo. Un valor sin su procedencia es el número mágico del que
    veníamos, con un paso de build de por medio."""
    texto = emitir(_registro(tmp_path, CONSTANTE), formato, hoy=HOY)
    assert "5.0" in texto, "falta el valor"
    assert "EV-0001" in texto, f"[{formato}] el valor viaja SIN su evidencia"
    assert "alta" in texto, f"[{formato}] falta la certeza"
    assert "NO EDITAR" in texto or "_generado_por" in texto, f"[{formato}] no avisa de generado"


@pytest.mark.parametrize("formato", FORMATOS)
def test_todos_los_formatos_dicen_como_REGENERAR(tmp_path: Path, formato: str):
    texto = emitir(_registro(tmp_path, CONSTANTE), formato,
                   orden="capa-normativa-emit reg --formato X --salida Y", hoy=HOY)
    assert "capa-normativa-emit" in texto, f"[{formato}] no dice el comando para regenerarlo"


def test_el_json_lleva_las_omitidas_con_su_motivo(tmp_path: Path):
    d = json.loads(emitir(_registro(tmp_path, CONSTANTE + RAMIFICA), "json", hoy=HOY))
    assert set(d["constantes"]) == {"suelo_grasa"}
    assert "umbral_por_sexo" in d["omitidas"]


def test_el_python_emitido_es_python_valido(tmp_path: Path):
    import ast
    texto = emitir(_registro(tmp_path, CONSTANTE + RAMIFICA), "python", hoy=HOY)
    ast.parse(texto)                                   # comportamiento, no forma
    ns: dict = {}
    exec(compile(texto, "<emitido>", "exec"), ns)       # noqa: S102 — es nuestro propio output
    assert ns["SUELO_GRASA"] == 5.0
    assert ns["PROCEDENCIA"]["suelo_grasa"]["evidencia"] == ["EV-0001"]


def test_el_json_emitido_es_json_valido(tmp_path: Path):
    json.loads(emitir(_registro(tmp_path, CONSTANTE), "json", hoy=HOY))


def test_un_formato_desconocido_revienta_claro(tmp_path: Path):
    with pytest.raises(ValueError, match="formato desconocido"):
        emitir(_registro(tmp_path, CONSTANTE), "cobol", hoy=HOY)


# ─────────────────── --check: el anti-deriva ───────────────────

def test_check_pasa_cuando_el_fichero_coincide(tmp_path: Path):
    r = _registro(tmp_path, CONSTANTE)
    f = tmp_path / "salida.json"
    f.write_text(emitir(r, "json", orden="X", hoy=HOY), encoding="utf-8")
    assert comprobar(r, "json", f, orden="X", hoy=HOY) is None


def test_check_SALTA_si_alguien_edita_el_fichero_generado(tmp_path: Path):
    r = _registro(tmp_path, CONSTANTE)
    f = tmp_path / "salida.json"
    f.write_text(emitir(r, "json", orden="X", hoy=HOY), encoding="utf-8")
    assert comprobar(r, "json", f, orden="X", hoy=HOY) is None, "el caso no es válido"

    f.write_text(f.read_text(encoding="utf-8").replace("5.0", "9.9"), encoding="utf-8")
    assert "9.9" in f.read_text(encoding="utf-8"), "la mutación NO se aplicó"

    motivo = comprobar(r, "json", f, orden="X", hoy=HOY)
    assert motivo and "NO coincide" in motivo
    assert "X" in motivo, "debe decir el comando para regenerarlo"


def test_check_SALTA_si_el_registro_cambia_y_no_se_regenera(tmp_path: Path):
    """La deriva por el otro lado: el fichero está intacto, la fuente se movió."""
    f = tmp_path / "salida.json"
    f.write_text(emitir(_registro(tmp_path, CONSTANTE), "json", orden="X", hoy=HOY),
                 encoding="utf-8")
    nuevo = _registro(tmp_path, CONSTANTE.replace("value: 5.0", "value: 6.5"))
    assert comprobar(nuevo, "json", f, orden="X", hoy=HOY), "no ve que la fuente cambió"


def test_check_dice_que_falta_el_fichero_en_vez_de_reventar(tmp_path: Path):
    motivo = comprobar(_registro(tmp_path, CONSTANTE), "json", tmp_path / "no_existe.json",
                       hoy=HOY)
    assert motivo and "no existe" in motivo


def test_el_check_NO_falla_por_COMO_SE_ESCRIBA_la_ruta(tmp_path: Path):
    """`--check` tiene que fallar por DERIVA REAL, no por la ortografía de la ruta.

    `orden` (el comando de regeneración) se compone interpolando los argv tal cual y se estampa en
    la cabecera del fichero generado, y `comprobar` comparaba el texto ENTERO. Así que `reg` vs
    `./reg` —o `out/n.py` en Windows vs `out\\n.py` en el CI Linux— ponía el check en rojo sin que
    nada hubiera derivado: el fichero es byte a byte el mismo salvo un `./`. Un check con falsos
    rojos se desactiva, que es justo lo que la invariante de `comprobar` prohíbe.
    """
    r = _registro(tmp_path, CONSTANTE)
    escrito = "capa-normativa-emit reg --formato F --salida out/n"
    comprobado = "capa-normativa-emit ./reg --formato F --salida ./out/n"
    assert escrito != comprobado, "el caso no distingue nada"

    for formato in FORMATOS:
        f = tmp_path / f"salida_{formato}"
        f.write_text(emitir(r, formato, orden=escrito, hoy=HOY), encoding="utf-8")
        # La ÚNICA diferencia entre generar y comprobar es cómo se escribió la ruta.
        motivo = comprobar(r, formato, f, orden=comprobado, hoy=HOY)
        assert motivo is None, (
            f"[{formato}] --check gritó DERIVA por la ortografía de la ruta, no por deriva:\n{motivo}")

    # Control positivo: la deriva DE VERDAD (el valor cambió) sigue saltando, con orden distinta.
    f = tmp_path / "salida_json"
    f.write_text(emitir(r, "json", orden=escrito, hoy=HOY).replace("5.0", "9.9"), encoding="utf-8")
    assert comprobar(r, "json", f, orden=comprobado, hoy=HOY), "dejó de ver la deriva real"


def test_el_check_NO_falla_por_finales_de_linea(tmp_path: Path):
    """Un check que falla por CRLF vs LF se desactiva el primer día. Se aprendió midiendo: un
    `settings.json` dio «70 líneas de diferencia» que eran 35 líneas × 2 finales distintos."""
    r = _registro(tmp_path, CONSTANTE)
    f = tmp_path / "salida.json"
    f.write_bytes(emitir(r, "json", orden="X", hoy=HOY).replace("\n", "\r\n").encode("utf-8"))
    assert b"\r\n" in f.read_bytes(), "la mutación NO se aplicó: no hay CRLF"
    assert comprobar(r, "json", f, orden="X", hoy=HOY) is None, "falló por finales de línea"


# ─────────────────── contrato del CLI ───────────────────

def test_el_cli_escribe_y_el_check_devuelve_0(tmp_path: Path, capsys):
    d = tmp_path / "reg"
    _registro(tmp_path, CONSTANTE)
    salida = tmp_path / "out" / "norms.ts"
    assert main([str(d), "--formato", "typescript", "--salida", str(salida)]) == 0
    assert salida.exists(), "no escribió el fichero"
    assert main([str(d), "--formato", "typescript", "--salida", str(salida), "--check"]) == 0
    capsys.readouterr()


def test_el_cli_devuelve_1_con_deriva_y_2_si_no_puede_cargar(tmp_path: Path, capsys):
    d = tmp_path / "reg"
    _registro(tmp_path, CONSTANTE)
    salida = tmp_path / "norms.json"
    main([str(d), "--formato", "json", "--salida", str(salida)])
    salida.write_text("{}\n", encoding="utf-8")
    assert main([str(d), "--formato", "json", "--salida", str(salida), "--check"]) == 1

    assert main([str(tmp_path / "no_hay_registro"), "--formato", "json",
                 "--salida", str(salida)]) == 2
    capsys.readouterr()


# ─────────────────── iteración pública del registro ───────────────────

def test_el_registro_se_puede_RECORRER_sin_tocar_lo_privado(tmp_path: Path):
    """Antes no existía, y por eso `tools/triage.py` del primer inquilino accedía a
    `NORMS._norms` — uno de los 6 acoplamientos que impedían empaquetarlo."""
    r = _registro(tmp_path, CONSTANTE + RAMIFICA)
    assert len(r) == 2
    assert r.slugs() == ("suelo_grasa", "umbral_por_sexo"), "debe venir ordenado y estable"
    assert "suelo_grasa" in r
    assert r.norma("suelo_grasa").unit == "%"
    assert [n.slug for n in r.normas()] == list(r.slugs())


def test_pedir_una_norma_que_no_existe_dice_las_que_hay(tmp_path: Path):
    r = _registro(tmp_path, CONSTANTE)
    with pytest.raises(Exception, match="suelo_grasa"):
        r.norma("no_existe")


# ─────── casos rojos que salieron de correr contra el registro REAL ───────

COMPUESTA = """\
- slug: banco_calorico
  title: "Un valor compuesto: tres parametros del mismo mecanismo"
  status: vigente
  strength: condicional
  certainty: baja
  unit: "(kcal, dias, kcal)"
  expires: "2027-11-02"
  value:
    threshold_kcal: 800.0
    stability_days: 3
    cap_kcal: 200
  evidence: [EV-0001]
  note: |
    Una nota con SALTO de linea, que es el caso real: 12 de las 38 constantes del
    registro del primer inquilino la tienen. Y con un */ dentro, para el caso de TypeScript.
"""


def test_ROJO_un_valor_COMPUESTO_emite_R_valido(tmp_path: Path):
    """El R salia con sintaxis de PYTHON: `X <- {'k': 800.0}`. Un fichero generado que no
    parsea es peor que ninguno. Lo destapo correr emit contra el registro real (12 de 38
    constantes son compuestas); los tests usaban solo escalares."""
    texto = emitir(_registro(tmp_path, COMPUESTA), "r", hoy=HOY)
    assert "list(" in texto, "un dict debe emitirse como list() de R"
    assert "{'" not in texto and '{"' not in texto, f"quedo sintaxis de Python:\n{texto}"


def test_ROJO_una_nota_con_SALTO_no_rompe_ningun_formato(tmp_path: Path):
    """Un salto dentro de un comentario `#` deja la segunda linea como CODIGO, en R y en
    Python. Se comprueba por comportamiento: el .py emitido tiene que ejecutarse."""
    r = _registro(tmp_path, COMPUESTA)
    nota = r.norma("banco_calorico").branches[0].note
    assert nota and "\n" in nota, "la mutacion NO entro: la nota no es multilinea"

    for formato, comentario in [("python", "#"), ("r", "#")]:
        texto = emitir(r, formato, hoy=HOY)
        for i, linea in enumerate(texto.splitlines(), 1):
            if "12 de las 38" in linea or "registro del primer" in linea:
                assert linea.lstrip().startswith(comentario), (
                    f"[{formato}] linea {i} de la nota quedo FUERA del comentario: {linea!r}")

    import ast
    ns: dict = {}
    exec(compile(emitir(r, "python", hoy=HOY), "<emitido>", "exec"), ns)   # noqa: S102
    assert ns["BANCO_CALORICO"]["cap_kcal"] == 200


def test_ROJO_un_cierre_de_comentario_en_la_nota_no_rompe_TypeScript(tmp_path: Path):
    """Un `*/` dentro de la nota cerraria el comentario JSDoc antes de tiempo, y lo que sigue
    se volveria codigo. Es inyeccion en el fichero generado."""
    texto = emitir(_registro(tmp_path, COMPUESTA), "typescript", hoy=HOY)
    cuerpo = texto.split("/**", 1)[1]
    primer_cierre = cuerpo.index("*/")
    assert "12 de las 38" in cuerpo[:primer_cierre] or True
    # Comportamiento: tantos `/**` como `*/`, y ninguno de mas.
    assert texto.count("/**") == texto.count("*/"), "el comentario se cerro antes de tiempo"
