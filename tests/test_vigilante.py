"""Tests del vigilante, escritos con la disciplina F14 (decisión del usuario, 2026-08-08).

Regla que estos tests cumplen y que el resto del arnés del sistema NO cumplía:

  (a) cada detector se **rompe a propósito** y se comprueba que SALTA;
  (b) se hace `assert` de que la **mutación entró** — un test que pasa bajo una mutación que
      no ocurrió es un test que pasa por vacío, disfrazado de verificación;
  (c) se comprueba **comportamiento**, no la presencia de una cadena;
  (d) los casos rojos son **medidos**, no inventados: los tres falsos positivos de aquí
      salieron de la primera ejecución real del 2026-08-09.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from capa_normativa.vigilante import DETECTORES, revisar_punteros, revisar_sintaxis
from capa_normativa.vigilante.cli import ERROR, HALLAZGOS, LIMPIO, main

VIGILANTE_DIR = Path(__file__).resolve().parent.parent / "src" / "capa_normativa" / "vigilante"


# ───────────────────────── sintaxis ─────────────────────────

def test_el_detector_de_sintaxis_SALTA_con_un_fichero_roto(tmp_path: Path):
    roto = tmp_path / "roto.py"
    roto.write_text('print("hola")sii\n', encoding="utf-8")

    # (b) la mutación entró: el fichero existe y NO parsea de verdad.
    assert roto.exists(), "la mutación no se aplicó: el fichero no se creó"
    with pytest.raises(SyntaxError):
        ast.parse(roto.read_text(encoding="utf-8"))

    hallazgos = revisar_sintaxis(tmp_path)
    assert len(hallazgos) == 1, f"el detector no saltó: {hallazgos}"
    assert hallazgos[0].codigo == "SYN001"
    assert hallazgos[0].linea == 1


def test_un_BOM_no_es_un_error_de_sintaxis(tmp_path: Path):
    """CASO ROJO MEDIDO — 8 falsos positivos de 9 en la primera ejecución (2026-08-09).

    Leer con `utf-8` en vez de `utf-8-sig` hacía que el BOM llegara a `ast.parse` y este
    reportara «invalid non-printable character U+FEFF» sobre ficheros que Python compila
    perfectamente. Este test es la única cosa que impide que vuelva.
    """
    con_bom = tmp_path / "con_bom.py"
    con_bom.write_bytes(b"\xef\xbb\xbf" + b'x = 1\nprint(x)\n')

    # (b) la mutación entró: el BOM está DE VERDAD en los bytes.
    crudo = con_bom.read_bytes()
    assert crudo.startswith(b"\xef\xbb\xbf"), "la mutación no se aplicó: no hay BOM"
    # (c) comportamiento: y es Python válido, así que no debe haber hallazgo.
    ast.parse(crudo.decode("utf-8-sig"))

    assert revisar_sintaxis(tmp_path) == [], "falso positivo: un BOM no es un error de sintaxis"


def test_el_detector_de_sintaxis_ignora_lo_excluido(tmp_path: Path):
    (tmp_path / "venv" / "lib").mkdir(parents=True)
    roto = tmp_path / "venv" / "lib" / "roto.py"
    roto.write_text("def (\n", encoding="utf-8")
    assert roto.exists(), "la mutación no se aplicó"
    assert revisar_sintaxis(tmp_path) == [], "no debe mirar dentro de venv/"


# ───────────────────────── punteros ─────────────────────────

def _corpus(d: Path, nombre: str, texto: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    f = d / nombre
    f.write_text(texto, encoding="utf-8")
    return f


def test_el_detector_de_punteros_SALTA_con_un_puntero_colgante(tmp_path: Path):
    f = _corpus(tmp_path, "doc.md", "## 1.1 Existe\n\nVer §9.9 para el detalle.\n")

    # (b) la mutación entró: el texto contiene el puntero y NO la sección.
    contenido = f.read_text(encoding="utf-8")
    assert "§9.9" in contenido, "la mutación no se aplicó: falta el puntero"
    assert "## 9.9" not in contenido, "el caso no es válido: la sección existe"

    hallazgos = revisar_punteros(tmp_path)
    assert len(hallazgos) == 1, f"el detector no saltó: {hallazgos}"
    assert hallazgos[0].codigo == "PTR001"
    assert hallazgos[0].linea == 3


def test_un_puntero_que_resuelve_no_es_hallazgo(tmp_path: Path):
    _corpus(tmp_path, "doc.md", "## 1.1 Existe\n\nVer §1.1.\n")
    assert revisar_punteros(tmp_path) == []


def test_una_referencia_a_especificacion_no_es_un_puntero_colgante(tmp_path: Path):
    """CASO ROJO MEDIDO — era el único «hallazgo» de 229 referencias, y era falso.

    `§10.3.2.10` es una sección de la especificación DMN. El patrón capturaba `10.3` y lo
    buscaba como cabecera interna.
    """
    f = _corpus(tmp_path, "doc.md", "## 1.1 Algo\n\nLa sección era la correcta (§10.3.2.10).\n")
    assert "§10.3.2.10" in f.read_text(encoding="utf-8"), "la mutación no se aplicó"
    assert revisar_punteros(tmp_path) == [], "falso positivo: §10.3.2.10 no es un puntero interno"


def test_un_puntero_a_otro_corpus_declarado_no_es_colgante(tmp_path: Path):
    """CASO ROJO MEDIDO — 17 de 18 hallazgos de la primera corrida eran de esta clase."""
    aqui, otro = tmp_path / "aqui", tmp_path / "otro"
    _corpus(aqui, "a.md", "## 1.1 Aqui\n\nVer §5.50 del otro repo.\n")
    _corpus(otro, "b.md", "## 5.50 La seccion de verdad\n")

    assert revisar_punteros(aqui), "sin declarar el otro corpus DEBE salir colgante"
    assert revisar_punteros(aqui, tambien=[otro]) == [], "declarado el corpus, no es colgante"


def test_un_puntero_al_final_de_una_frase_SI_cuenta(tmp_path: Path):
    """REGRESIÓN — mi primer arreglo del FP de `§10.3.2.10` usaba un lookahead `(?![.\\d])` que
    también rechazaba `§9.9.` al final de una frase. Lo cazaron estos tests en su primera
    ejecución (2026-08-09). El discriminador correcto es «punto SEGUIDO DE DÍGITO»."""
    f = _corpus(tmp_path, "doc.md", "## 1.1 Algo\n\nEsto se explica en §9.9.\n")
    assert "§9.9.\n" in f.read_text(encoding="utf-8"), "la mutación no se aplicó"
    hallazgos = revisar_punteros(tmp_path)
    assert len(hallazgos) == 1, "un puntero seguido de punto final SÍ es un puntero"
    assert hallazgos[0].mensaje.startswith("§9.9 ")


def test_una_referencia_externa_en_mayusculas_no_es_colgante(tmp_path: Path):
    _corpus(tmp_path, "doc.md", "## 1.1 Algo\n\nSegun DMN §7.2 esto vale.\n")
    assert revisar_punteros(tmp_path) == []


def test_un_corpus_que_no_es_directorio_es_un_error(tmp_path: Path):
    f = tmp_path / "suelto.md"
    f.write_text("# nada\n", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        revisar_punteros(f)


# ───────────── contrato de salida y frontera de módulos ─────────────

def test_el_contrato_de_exit_codes(tmp_path: Path, capsys):
    _corpus(tmp_path, "doc.md", "## 1.1 Ok\n\nVer §1.1.\n")
    assert main([str(tmp_path), "--detector", "punteros"]) == LIMPIO

    _corpus(tmp_path, "malo.md", "Ver §9.9.\n")
    assert main([str(tmp_path), "--detector", "punteros"]) == HALLAZGOS

    assert main([str(tmp_path / "no_existe")]) == ERROR
    capsys.readouterr()


def test_los_codigos_de_hallazgo_son_estables(tmp_path: Path):
    """El trinquete cuenta por código. Si el código baila al reformular el mensaje, el
    trinquete deja de poder contar."""
    _corpus(tmp_path, "doc.md", "Ver §9.9.\n")
    (tmp_path / "roto.py").write_text("def (\n", encoding="utf-8")
    codigos = {h.codigo for h in revisar_punteros(tmp_path)} | {
        h.codigo for h in revisar_sintaxis(tmp_path)}
    assert codigos == {"PTR001", "SYN001"}


def test_todo_hallazgo_dice_que_hacer(tmp_path: Path):
    """El adoptante es un agente sin contexto: el mensaje ES la interfaz."""
    _corpus(tmp_path, "doc.md", "Ver §9.9.\n")
    (tmp_path / "roto.py").write_text("def (\n", encoding="utf-8")
    for h in revisar_punteros(tmp_path) + revisar_sintaxis(tmp_path):
        assert h.arreglo.strip(), f"{h.codigo} no dice qué hacer"
        assert len(h.arreglo) > 30, f"{h.codigo}: el arreglo es demasiado vago"


def _imports_de(p: Path) -> set[str]:
    nombres: set[str] = set()
    arbol = ast.parse(p.read_text(encoding="utf-8-sig"))
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            nombres.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            nombres.add(n.module)
    return nombres


def test_la_frontera_entre_modulos_se_mantiene():
    """La decisión de arquitectura del 2026-08-09 fue UN artefacto con DOS módulos, con la
    frontera donde el código ya la tenía. Una frontera que no se verifica es una frontera
    que deriva: esto la mecaniza."""
    for p in VIGILANTE_DIR.glob("*.py"):
        for nombre in _imports_de(p):
            assert "registry" not in nombre, (
                f"{p.name} importa {nombre!r}: el vigilante NO puede depender del registro")


def test_el_vigilante_no_usa_red_ni_LLM():
    """Ley 2 (2026-08-08): el detector continuo es determinista. Un LLM que vigila oscila, y
    un detector que oscila es otra respuesta viva más. Aquí se mecaniza en vez de confiarse.

    Precedente que lo justifica: `security_review.py` del sistema es un hook que parece un
    escáner de texto y es un `POST` a `/v1/chat/completions`.
    """
    prohibidos = {"socket", "requests", "urllib", "urllib.request", "http",
                  "http.client", "httpx", "aiohttp", "ssl", "ftplib", "telnetlib"}
    for p in VIGILANTE_DIR.glob("*.py"):
        malos = {n for n in _imports_de(p) if n in prohibidos or n.split(".")[0] in prohibidos}
        assert not malos, f"{p.name} importa {malos}: el vigilante no puede salir a la red"


def test_los_detectores_registrados_son_invocables():
    """El conjunto va escrito a mano a propósito: añadir un detector debe ser un acto
    consciente que aparece en el diff, no algo que entra sin que nadie lo note."""
    assert set(DETECTORES) == {"punteros", "secretos", "sintaxis"}
    for nombre, fn in DETECTORES.items():
        assert callable(fn), nombre


def test_ROJO_los_punteros_de_un_SUBDIRECTORIO_tambien_cuentan(tmp_path: Path):
    """FALSO NEGATIVO real, encontrado el 2026-08-11 por un agente que adoptó el paquete leyendo
    solo el README — no por estos tests, cuyos corpus eran todos de un nivel.

    `… docs --detector punteros` decía «limpio, 0 hallazgos» y exit 0 mientras
    `docs/fundamentos/` tenía 8 punteros colgantes. Un detector que da confianza falsa es peor
    que ninguno, y este la daba porque usaba `glob` en vez de `rglob`.
    """
    _corpus(tmp_path, "raiz.md", "## 1.1 Existe\n")
    _corpus(tmp_path / "hondo" / "mas_hondo", "perdido.md", "Ver §9.9 que no existe.\n")

    hallazgos = revisar_punteros(tmp_path)
    assert len(hallazgos) == 1, f"no baja a los subdirectorios: {hallazgos}"
    assert hallazgos[0].fichero == "hondo/mas_hondo/perdido.md", (
        "la ruta debe ser relativa al corpus: con recursion, el nombre base no localiza")


def test_una_cabecera_en_un_SUBDIRECTORIO_resuelve_un_puntero_de_la_raiz(tmp_path: Path):
    """La otra mitad de la recursión: si se leen los ficheros hondos, sus cabeceras también
    cuentan como destino. Si no, arreglar el falso negativo abriría falsos positivos."""
    _corpus(tmp_path, "raiz.md", "Ver §7.3 para el detalle.\n")
    _corpus(tmp_path / "sub", "destino.md", "## 7.3 La seccion, un nivel mas abajo\n")
    assert revisar_punteros(tmp_path) == [], "la cabeceras de subdirectorios deben contar"


def test_no_baja_a_node_modules_ni_a_venv(tmp_path: Path):
    _corpus(tmp_path, "ok.md", "## 1.1 Algo\n")
    _corpus(tmp_path / "node_modules" / "pkg", "ajeno.md", "Ver §9.9.\n")
    _corpus(tmp_path / "venv" / "lib", "ajeno2.md", "Ver §8.8.\n")
    assert revisar_punteros(tmp_path) == [], "no debe auditar dependencias ajenas"
