"""La coartada de `registro-sin-caducados`: se le ve DISCRIMINAR, no solo decir que no.

Está en `SIN_MUTACION`, y con razón: su rojo no sale de que falte un fichero, sale de comparar
la FECHA DE HOY contra las de `REGISTRO.md`. `--verifica` no puede fabricarle un artefacto que lo
ponga verde, así que hasta hoy nadie lo había visto cambiar de color. Un comprobador que nunca se
ha visto cambiar de color no está verificado: está sin estrenar, exactamente igual que los diez
hooks que vigila el canario.

Se le inyecta el mundo por `aceptacion.REGISTRO`, que es la constante donde vive el censo. Cuatro
casos, y **los dos del medio son los que prueban algo**:

  · caducada y sin `ESTADO: RETIRADO`  -> ROJO   (el caso que la norma persigue)
  · la MISMA, ya retirada              -> VERDE  ← discrimina por el estado
  · con fecha futura                   -> VERDE  ← discrimina por la fecha
  · sin fichero                        -> ROJO   (no aprueba en vacío)

Sin el segundo y el tercero, un comprobador que dijera ROJO SIEMPRE pasaría el primero y el
cuarto y parecería sano. Ese es justo el fallo que este fichero existe para hacer imposible.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TABLERO = RAIZ / "scripts" / "aceptacion.py"


def _tablero():
    spec = importlib.util.spec_from_file_location("tablero_registro", str(TABLERO))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _entrada(caduca: dt.date, estado: str | None = None) -> str:
    """Una entrada de REGISTRO.md con los campos que el comprobador lee.

    Se escribe con la MISMA forma que las de verdad —cabecera `## `, campos con guion— porque un
    fixture que se parece pero no cuadra prueba el parser de mentira, no el de verdad.
    """
    lineas = [
        "## Cosa de pega — montada para este test",
        "- QUE ES: una entrada inventada, no toca nada del sistema.",
        "- SENAL DE USO: ninguna, es de pega.",
        "- CADUCA: " + caduca.isoformat() + " -> si nadie la usa, se quita.",
    ]
    if estado is not None:
        lineas.append("- ESTADO: " + estado)
    return chr(10).join(lineas) + chr(10)


@pytest.fixture
def registro(tmp_path, monkeypatch):
    """Devuelve un escritor que deja un REGISTRO.md de pega y lo enchufa al comprobador."""
    reg = tmp_path / "REGISTRO.md"

    def escribir(cuerpo: str) -> None:
        reg.write_text("# REGISTRO — de pega" + chr(10) * 2 + cuerpo, encoding="utf-8")

    return reg, escribir, monkeypatch


def test_una_entrada_CADUCADA_sin_retirar_es_ROJO(registro):
    """El caso que la norma persigue: llegó la fecha y la cosa sigue puesta."""
    reg, escribir, monkeypatch = registro
    m = _tablero()
    escribir(_entrada(dt.date.today() - dt.timedelta(days=1)))
    monkeypatch.setattr(m, "REGISTRO", reg)
    ok, motivo = m.registro_sin_caducados()
    assert ok is False
    assert "vencidas sin retirar" in motivo


def test_la_MISMA_entrada_ya_RETIRADA_es_VERDE(registro):
    """Discrimina por el ESTADO, no por la fecha a secas.

    Es literalmente el fichero del test de arriba con una línea más. Si el comprobador siguiera
    rojo aquí, su rojo no significaría «hay trabajo pendiente» sino «hay una fecha antigua», y la
    norma se volvería incumplible: retirar la cosa no la bajaría del tablero.
    """
    reg, escribir, monkeypatch = registro
    m = _tablero()
    escribir(_entrada(dt.date.today() - dt.timedelta(days=1),
                      estado="**RETIRADO el 2026-08-23.** Se quitó al caducar, que es la norma."))
    monkeypatch.setattr(m, "REGISTRO", reg)
    ok, motivo = m.registro_sin_caducados()
    assert ok is True, motivo


def test_una_entrada_con_fecha_FUTURA_es_VERDE(registro):
    """Discrimina por la FECHA. Una cosa montada la semana pasada no está vencida hoy."""
    reg, escribir, monkeypatch = registro
    m = _tablero()
    escribir(_entrada(dt.date.today() + dt.timedelta(days=30)))
    monkeypatch.setattr(m, "REGISTRO", reg)
    ok, motivo = m.registro_sin_caducados()
    assert ok is True, motivo


def test_HOY_todavia_no_es_vencida(registro):
    """El borde exacto, que es donde se equivocan los comparadores.

    La norma dice «LLEGADA la fecha», y el comprobador la lee como `fecha >= hoy` sigue viva. Un
    `>` en vez de un `>=` adelantaría un día todos los vencimientos: rojos que nadie entiende y
    que no se pueden cerrar renovando a hoy.
    """
    reg, escribir, monkeypatch = registro
    m = _tablero()
    escribir(_entrada(dt.date.today()))
    monkeypatch.setattr(m, "REGISTRO", reg)
    ok, motivo = m.registro_sin_caducados()
    assert ok is True, motivo


def test_sin_fichero_es_ROJO_y_no_verde(registro):
    """Aprobar en vacío se lee como «todo al día», que es peor que no tener la promesa.

    Y no es hipotético: hoy mismo, desde un worktree, `REGISTRO.md` no existe en la ruta que el
    comprobador mira. Que eso salga ROJO y no VERDE es lo único que impide que un árbol de
    trabajo aislado dé por buena una norma que no ha llegado a leer.
    """
    reg, _escribir, monkeypatch = registro
    m = _tablero()
    monkeypatch.setattr(m, "REGISTRO", reg.parent / "no_existe" / "REGISTRO.md")
    ok, motivo = m.registro_sin_caducados()
    assert ok is False
    assert "no existe" in motivo


def test_varias_vencidas_se_nombran_todas(registro):
    """El rojo tiene que decir CUÁL, no cuántas: un contador no dice dónde mirar."""
    reg, escribir, monkeypatch = registro
    m = _tablero()
    ayer = dt.date.today() - dt.timedelta(days=1)
    escribir(_entrada(ayer) + chr(10)
             + _entrada(ayer).replace("Cosa de pega", "Otra cosa de pega"))
    monkeypatch.setattr(m, "REGISTRO", reg)
    ok, motivo = m.registro_sin_caducados()
    assert ok is False
    assert "2 entrada(s)" in motivo
    assert "Cosa de pega" in motivo and "Otra cosa" in motivo


def test_una_entrada_SIN_campo_CADUCA_no_se_inventa_un_vencimiento(registro):
    """No todas las cabeceras del fichero son entradas con fecha, y acusar a una sin `CADUCA:`
    sería un rojo incerrable: no hay fecha que renovar ni cosa que retirar."""
    reg, escribir, monkeypatch = registro
    m = _tablero()
    escribir("## Una seccion cualquiera" + chr(10) + "- QUE ES: prosa, sin fecha." + chr(10))
    monkeypatch.setattr(m, "REGISTRO", reg)
    ok, motivo = m.registro_sin_caducados()
    assert ok is True, motivo
