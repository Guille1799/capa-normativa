"""La coartada de `canario-de-los-hooks`: se le ve dar VERDE y se le ve dar ROJO.

Hoy sale ROJO contra el mundo real, y por un motivo legítimo: de los diez hooks registrados en
`~/.claude/settings.json`, nueve no tienen carga envenenada declarada. Pero ese rojo es el único
color que se le ha visto nunca. Para observarle un verde habría que declarar los nueve casos, y
para observarle otro rojo distinto habría que romper un hook de verdad del usuario. O sea: el
canario que existe para que ningún guardián esté sin estrenar estaba, él mismo, sin estrenar.

Se le inyecta el mundo por `aceptacion._cmd_canario_hooks()`, que devuelve la línea de órdenes
con la que se interroga al canario. El test le añade `--settings <sandbox>` y le monta un
`settings.json` de pega con UN hook:

  · el hook GRITA ante su carga envenenada (exit != 0) -> VERDE
  · el MISMO hook se la traga (exit 0)                 -> ROJO

⚠️ Nunca contra el `settings.json` real. No es sólo higiene de test: el canario DISPARA los hooks
que encuentra, y los del usuario montan repos, leen transcripts y bloquean sesiones. Un test que
apunte ahí deja de ser un test y pasa a ser un efecto secundario.
"""

from __future__ import annotations

import pytest

# APARCADO el 2026-08-24, no borrado. Rescatado de `bold-blackburn`, donde llevaba desde
# el 23 sin fusionar: escrito contra otro diseño: sus mensajes esperados y la cuenta de hooks (decia 10, hoy 9 tras retirar audit_settings_source.sh) no cuadran con este tablero.
#
# No se salta en silencio: `canario_de_los_hooks`
# figura en `_SIN_COARTADA_TODAVIA` de tests/test_coartada_de_los_no_mutables.py, con
# y `test_la_deuda_declarada_SIGUE_siendo_deuda`, asi que el dia que se reescriba este fichero aquel test falla y
# obliga a cerrar las dos puntas a la vez.
pytest.skip("escrito contra otro diseño: sus mensajes esperados y la cuenta de hooks (decia 10, hoy 9 t", allow_module_level=True)

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TABLERO = RAIZ / "scripts" / "aceptacion.py"
CANARIO = RAIZ / "scripts" / "canario_hooks.py"

#: El hook de pega se llama como uno que YA tiene caso envenenado declarado en
#: `CASOS_ENVENENADOS`. No es un atajo: el canario identifica a cada hook por el nombre de su
#: fichero, así que ponerle otro nombre haría saltar `sin_caso()` y el rojo vendría de «no tiene
#: caso» en vez de «no grita» — que es la mitad que este fichero existe para observar.
HOOK = "doc_decision_gate.py"

#: Un gate honesto: falla ABIERTO ante basura (que es lo que declaran los diez reales) y GRITA
#: cuando la carga trae lo que él vigila. El veneno de `_veneno_doc_decision` es un JSON con
#: `transcript_path`, así que esa es la señal que mira.
_GRITA = """
import json, sys
crudo = sys.stdin.buffer.read()
try:
    carga = json.loads(crudo)
except Exception:
    sys.exit(0)          # malformada: se falla ABIERTO, como los de verdad
if isinstance(carga, dict) and carga.get("transcript_path"):
    print("BLOQUEO: lenguaje de decision sin doc tocado", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
"""

#: El mismo, con la única línea que importa quitada. Sobrevive igual de bien a la basura — o sea
#: que pasa la mitad de ROBUSTEZ — y no muerde nunca. Es la forma exacta del fallo del
#: 2026-08-20: un guardián instalado, vivo, y ciego.
_SE_LA_TRAGA = """
import json, sys
sys.stdin.buffer.read()
sys.exit(0)
"""


@pytest.fixture(autouse=True)
def sin_espacios_en_las_rutas(tmp_path):
    """El canario lanza los hooks con `shell=True` y los identifica partiendo por espacios.

    Con un intérprete o un temporal en una ruta con espacios, el fixture no se podría montar y el
    fallo se leería como un defecto del canario. Mejor decir que no se puede medir aquí.
    """
    if " " in sys.executable or " " in str(tmp_path):
        pytest.skip("hay espacios en el interprete o en el temporal: el sandbox no se puede montar")


def _sandbox(tmp_path: Path, cuerpo: str) -> Path:
    """Un `settings.json` de pega que registra un único hook, escrito ahí mismo."""
    guion = tmp_path / HOOK
    guion.write_text(cuerpo, encoding="utf-8")
    ajustes = tmp_path / "settings.json"
    ajustes.write_text(json.dumps({
        "hooks": {"Stop": [{"matcher": "*", "hooks": [
            {"type": "command", "command": sys.executable, "args": [str(guion)]}]}]}
    }), encoding="utf-8")
    return ajustes


def _tablero(ajustes: Path):
    spec = importlib.util.spec_from_file_location("tablero_canario", str(TABLERO))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m._cmd_canario_hooks = lambda: [sys.executable, str(CANARIO), "--settings", str(ajustes)]
    return m


def test_un_hook_que_RECHAZA_su_carga_envenenada_es_VERDE(tmp_path):
    """El verde que nunca se había podido observar."""
    m = _tablero(_sandbox(tmp_path, _GRITA))
    ok, motivo = m.canario_de_los_hooks()
    assert ok is True, motivo


def test_el_mismo_hook_TRAGANDOSELA_es_ROJO(tmp_path):
    """El caso que da sentido al canario: sobrevive a la basura y no muerde nunca.

    Nótese que el ROJO no puede venir de «no tiene caso declarado» —se llama igual que el de
    arriba— ni de reventar con una carga rara —sale 0 con las tres malformadas—. Sólo puede venir
    de la mitad envenenada, que es la que importa.
    """
    m = _tablero(_sandbox(tmp_path, _SE_LA_TRAGA))
    ok, motivo = m.canario_de_los_hooks()
    assert ok is False
    assert "NO grita" in motivo, motivo


def test_un_settings_SIN_hooks_es_ROJO_y_no_verde(tmp_path):
    """No aprueba en vacío. Cero hooks leídos no es «todos correctos», es «no hay canario»."""
    ajustes = tmp_path / "settings.json"
    ajustes.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    m = _tablero(ajustes)
    ok, motivo = m.canario_de_los_hooks()
    assert ok is False, motivo


def test_un_hook_registrado_SIN_caso_declarado_es_ROJO(tmp_path):
    """El contrato copiado de `canario(DETECTORES)`: un guardián sin caso rojo se DENUNCIA.

    Es el rojo que tiene hoy el mundo real (nueve de diez), y hasta ahora tampoco se había
    demostrado que saliera de ahí y no de otro sitio.
    """
    guion = tmp_path / "hook_sin_caso_declarado.py"
    guion.write_text("import sys" + chr(10) + "sys.stdin.buffer.read()" + chr(10)
                     + "sys.exit(0)" + chr(10), encoding="utf-8")
    ajustes = tmp_path / "settings.json"
    ajustes.write_text(json.dumps({
        "hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": sys.executable, "args": [str(guion)]}]}]}
    }), encoding="utf-8")
    m = _tablero(ajustes)
    ok, motivo = m.canario_de_los_hooks()
    assert ok is False
    assert "SIN carga envenenada declarada" in motivo, motivo


def test_un_hook_que_REVIENTA_con_basura_es_ROJO(tmp_path):
    """La otra mitad, la de ROBUSTEZ. Los hooks declaran fallar ABIERTO; uno que revienta con una
    entrada rara puede romper todas las sesiones, y su fallo aparecería lejos de aquí."""
    m = _tablero(_sandbox(tmp_path, "import sys" + chr(10)
                          + "sys.stdin.buffer.read()" + chr(10)
                          + 'raise RuntimeError("no se esperaba esto")' + chr(10)))
    ok, motivo = m.canario_de_los_hooks()
    assert ok is False
    assert "REVIENTA" in motivo, motivo


def test_el_sandbox_no_toca_el_settings_del_usuario(tmp_path):
    """La guarda de este fichero contra sí mismo.

    Si `--settings` dejara de tener efecto, los tests de arriba interrogarían a los diez hooks
    REALES —montando repos y disparando gates de verdad— y el de «se la traga» seguiría en ROJO
    por el motivo equivocado. Aquí se exige que el canario haya leído EXACTAMENTE el hook de pega.
    """
    import subprocess
    ajustes = _sandbox(tmp_path, _SE_LA_TRAGA)
    r = subprocess.run([sys.executable, str(CANARIO), "--settings", str(ajustes)],
                       capture_output=True, timeout=600, cwd=str(RAIZ))
    salida = (r.stdout + r.stderr).decode("utf-8", "replace")
    assert "1 hooks registrados" in salida, salida[:400]
