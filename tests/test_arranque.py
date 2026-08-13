"""`init` — tests. El primero es el único que no se puede relajar.

Un generador cuya salida no valida es PEOR que no tenerlo: la primera experiencia del adoptante
sería un error en un fichero que le acaba de dar el propio paquete, y a partir de ahí no sabe si el
problema es suyo o del ejemplo. Todo lo demás de este módulo es secundario frente a eso.
"""
from __future__ import annotations

import pytest

from capa_normativa import NormRegistry
from capa_normativa.arranque import ERROR, FICHEROS, LIMPIO, PROBLEMAS, generar, main
from capa_normativa.validacion import validar


# ── la propiedad que lo hace útil o inútil ──

def test_lo_generado_CARGA_tal_cual(tmp_path):
    """EL TEST QUE NO SE PUEDE RELAJAR. Si esto se pone rojo, `init` está entregando un registro
    roto a alguien que acaba de empezar — y no tendrá forma de saber que el error no es suyo."""
    generar(tmp_path)
    reg = NormRegistry.load(tmp_path)
    assert len(reg) == 2, "las dos formas (constante y ramificada) tienen que estar"


def test_lo_generado_PASA_validate(tmp_path):
    """La otra mitad: no basta con que cargue. `validate` comprueba además la coherencia entre
    certeza y evidencia, y las caducidades — y es lo primero que el propio `init` le dice al
    adoptante que ejecute, así que tiene que salir verde."""
    generar(tmp_path)
    inf = validar(tmp_path)
    assert inf.ok, f"el ejemplo que genera `init` no pasa `validate`: {inf.errores}"
    assert inf.total == 2


def test_lo_generado_RESUELVE_las_dos_formas(tmp_path):
    """Cargar no es suficiente: si la rama comodín estuviera mal, el registro cargaría igual y el
    ejemplo enseñaría una forma que no funciona."""
    generar(tmp_path)
    reg = NormRegistry.load(tmp_path)

    r = reg.resolve("ejemplo_umbral")
    assert r.value == 10.0 and r.evidence == ("EV-0001",)

    assert reg.resolve("ejemplo_por_grupo", grupo="especifico").value == 20.0
    assert reg.resolve("ejemplo_por_grupo", grupo="").value == 15.0, (
        "la rama COMODÍN no resuelve, y es la que enseña qué hacer con un sujeto desconocido")


def test_lo_que_init_le_dice_al_adoptante_que_haga_FUNCIONA(tmp_path, capsys):
    """`init` imprime tres líneas de ejemplo. Si no funcionaran, el primer paso del adoptante
    fallaría con el código que le acaba de dar el paquete — y eso es peor que no imprimir nada.

    Se comprueban los VALORES que promete la salida, no que la salida exista.
    """
    main([str(tmp_path)])
    salida = capsys.readouterr().out
    reg = NormRegistry.load(tmp_path)

    assert 'NORMS.resolve("ejemplo_umbral").value' in salida
    assert "# 10.0" in salida and reg.resolve("ejemplo_umbral").value == 10.0
    assert "# 15.0" in salida and reg.resolve("ejemplo_por_grupo", grupo="").value == 15.0
    assert "capa-normativa-validate" in salida, "no le dice cómo comprobarlo"


# ── no pisar el trabajo de nadie ──

def test_NO_sobreescribe_y_no_toca_NADA(tmp_path):
    """Todo-o-nada a propósito: dejar un registro medio sobrescrito es peor que no haber tocado
    nada, porque el adoptante se queda con una mezcla de su fichero y del ejemplo."""
    (tmp_path / "norms.yaml").write_text("- slug: lo_mio\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="No se ha tocado NADA"):
        generar(tmp_path)
    assert (tmp_path / "norms.yaml").read_text(encoding="utf-8") == "- slug: lo_mio\n"
    assert not (tmp_path / "schema.yaml").exists(), (
        "escribió los que no existían antes de darse cuenta: eso es medio sobrescrito")


def test_forzar_si_sobreescribe(tmp_path):
    (tmp_path / "norms.yaml").write_text("- slug: lo_mio\n", encoding="utf-8")
    generar(tmp_path, forzar=True)
    assert "ejemplo_umbral" in (tmp_path / "norms.yaml").read_text(encoding="utf-8")


def test_crea_el_directorio_si_no_existe(tmp_path):
    destino = tmp_path / "nuevo" / "norms"
    generar(destino)
    assert all((destino / f).exists() for f in FICHEROS)


def test_el_contrato_de_salida_es_0_1_2(tmp_path):
    assert main([str(tmp_path / "a")]) == LIMPIO
    assert main([str(tmp_path / "a")]) == PROBLEMAS, "la segunda vez ya existe: 1, no 0"
    assert main([str(tmp_path / "a"), "--forzar"]) == LIMPIO


# ── que el ejemplo siga ENSEÑANDO, que es la mitad de su valor ──

def test_el_ejemplo_ENSEÑA_las_dos_certezas_y_sus_consecuencias(tmp_path):
    """Con evidencia y sin evidencia son los dos casos que el adoptante va a escribir, y tienen
    reglas OPUESTAS: con fuente se cita y no se pone `provenance_note`; sin fuente es al revés.
    Un ejemplo que solo enseñara uno dejaría el otro a la adivinanza."""
    generar(tmp_path)
    norms = (tmp_path / "norms.yaml").read_text(encoding="utf-8")
    assert "evidence: [EV-0001]" in norms, "falta el caso CON fuente"
    assert "provenance_note:" in norms and "sin_respaldo" in norms, "falta el caso SIN fuente"

    reg = NormRegistry.load(tmp_path)
    con = reg.norma("ejemplo_umbral")
    sin = reg.norma("ejemplo_por_grupo")
    assert con.certainty != sin.certainty, "los dos ejemplos enseñan la misma certeza: sobra uno"
    assert sin.provenance_note, "el ejemplo sin fuente no explica de dónde sale el número"


def test_el_esquema_generado_AVISA_de_lo_que_hay_que_sustituir(tmp_path):
    """`subject_dimensions` es la lista cerrada que impide encadenar normas, y es lo PRIMERO que el
    adoptante tiene que cambiar por lo suyo. Si el ejemplo no lo dice, se queda con `grupo`."""
    generar(tmp_path)
    schema = (tmp_path / "schema.yaml").read_text(encoding="utf-8")
    assert "subject_dimensions" in schema
    assert "Sustituye" in schema or "sustituye" in schema, (
        "no le dice que estas dimensiones son de ejemplo")
    # Insensible a la caja: la propiedad es que lo EXPLIQUE, no cómo esté escrito. La primera
    # versión buscaba minúsculas y el texto lo dice en mayúsculas — un test que falla por el
    # formato de una frase no está comprobando la frase.
    assert "encadenar normas" in schema.lower(), (
        "no explica POR QUÉ la lista es cerrada, que es lo único que impide que alguien la abra")


def test_el_ejemplo_NO_trae_dominio_de_nadie(tmp_path):
    """El paquete es agnóstico. Meter aquí umbrales de nutrición o entrenamiento lo ataría a su
    primer inquilino, y el siguiente los borraría preguntándose si eran importantes."""
    generar(tmp_path)
    todo = " ".join((tmp_path / f).read_text(encoding="utf-8").lower() for f in FICHEROS)
    for palabra in ("proteina", "proteína", "carbohidrato", "kcal", "hrv", "vo2",
                    "deload", "entreno", "grasa"):
        assert palabra not in todo, f"el ejemplo trae dominio del primer inquilino: «{palabra}»"


def test_avisa_de_que_la_CADUCIDAD_tumba_la_app(tmp_path):
    """Es el mecanismo más sorprendente del paquete: cuando `expires` pasa, `load()` lanza y la
    aplicación NO ARRANCA. Si el ejemplo no lo dice donde se escribe la fecha, el adoptante lo
    descubre un martes por la mañana."""
    generar(tmp_path)
    norms = (tmp_path / "norms.yaml").read_text(encoding="utf-8")
    assert "expires" in norms
    assert "no arrancará" in norms or "NO ARRANCARÁ" in norms or "no arranca" in norms, (
        "el ejemplo no avisa de que una caducidad vencida impide arrancar")
    assert "capa-normativa-validate" in norms, (
        "no dice cómo enterarse ANTES, que es la mitad útil del aviso")
