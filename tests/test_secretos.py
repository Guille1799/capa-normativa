"""Tests del escáner de secretos, con la disciplina F14.

⚠️ Nota de método: los secretos falsos de aquí se **construyen en tiempo de ejecución**
(`"gsk" + "_" + "A"*24`) y no se escriben como literales. Si estuvieran literales, el propio
escáner marcaría este fichero al correr sobre el paquete — y un test que obliga a silenciar
el detector para poder existir es un test que empuja a desactivarlo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from capa_normativa.vigilante import revisar_secretos
from capa_normativa.vigilante.secretos import PATRONES

REPO = Path(__file__).resolve().parent.parent

# Construidos, nunca literales. Ver la nota de arriba.
FALSO_GROQ = "gsk" + "_" + "A" * 24
FALSO_AWS = "AKIA" + "B" * 16
FALSO_ANTHROPIC = "sk-" + "ant-" + "C" * 24
FALSO_PRIVADA = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"


def _repo_git(tmp_path: Path, ficheros: dict[str, str]) -> Path:
    """Un repo git de verdad: el escáner pregunta a git, así que un tmp_path pelado no
    ejercitaría el camino real."""
    for nombre, contenido in ficheros.items():
        p = tmp_path / nombre
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenido, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


def test_SALTA_con_una_credencial_versionada(tmp_path: Path):
    repo = _repo_git(tmp_path, {"config.py": f'CLAVE = "{FALSO_GROQ}"\n'})

    # (b) la mutación entró: el fichero contiene la forma Y git lo conoce.
    assert FALSO_GROQ in (repo / "config.py").read_text(encoding="utf-8")
    versionados = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True,
                                 text=True).stdout
    assert "config.py" in versionados, "la mutación no se aplicó: git no lo ve"

    hallazgos = revisar_secretos(repo)
    assert len(hallazgos) == 1, f"el detector no saltó: {hallazgos}"
    assert hallazgos[0].codigo == "SEC001"
    assert hallazgos[0].linea == 1


def test_el_hallazgo_NUNCA_contiene_el_secreto(tmp_path: Path):
    """Un detector de fugas que imprime la fuga en su informe —que a su vez se commitea— es
    el mismo bug que persigue. Es el fallo real de 2026-06-26, invertido."""
    repo = _repo_git(tmp_path, {"c.py": f'K = "{FALSO_GROQ}"\n'})
    h = revisar_secretos(repo)[0]
    entero = f"{h.mensaje} {h.arreglo} {h.fichero} {h}"
    assert FALSO_GROQ not in entero, "el hallazgo filtra el secreto"
    # Ni truncado: ni los primeros 12 caracteres del cuerpo.
    assert FALSO_GROQ[4:16] not in entero, "el hallazgo filtra un trozo del secreto"


def test_nosec_SUPRIME_de_verdad(tmp_path: Path):
    """El hook anterior anunciaba `# nosec` en su mensaje y NO tenía código que lo leyera.
    Una vía de escape ficticia obliga a desactivar el detector entero al primer FP."""
    repo = _repo_git(tmp_path, {"fixture.py": f'FAKE = "{FALSO_GROQ}"  # nosec\n'})
    assert "# nosec" in (repo / "fixture.py").read_text(encoding="utf-8"), "no entró"
    assert revisar_secretos(repo) == [], "`# nosec` no suprime: la puerta es ficticia"


def test_nosec_solo_suprime_SU_linea(tmp_path: Path):
    repo = _repo_git(tmp_path, {
        "m.py": f'A = "{FALSO_GROQ}"  # nosec\nB = "{FALSO_AWS}"\n'})
    h = revisar_secretos(repo)
    assert len(h) == 1 and h[0].linea == 2, f"la supresión se desbordó de línea: {h}"


def test_escanea_TODO_lo_versionado_no_solo_codigo(tmp_path: Path):
    """La fuga real de 2026-06-26 vivía en un `.md` de un directorio de informes, y la
    redacción posterior no escaneó ese directorio."""
    repo = _repo_git(tmp_path, {
        "auditoria/runs/2026-01-01/informe.md": f"El token era {FALSO_GROQ} y falló.\n"})
    h = revisar_secretos(repo)
    assert len(h) == 1, "un informe versionado también es superficie de fuga"
    assert "informe.md" in h[0].fichero


def test_ROJO_un_secreto_en_github_workflows_SI_se_caza(tmp_path: Path):
    """`.git` como subcadena apagaba TODO `.github/`: `".git" in ".github/workflows/ci.yml"` es
    True, así que la exclusión pensada para el directorio interno de git se tragaba el de
    configuración de GitHub. El workflow de CI —donde vive una credencial en `env:`— nunca se
    abría y el escáner decía «limpio» sin haberlo mirado. Medido sobre el propio repo el
    2026-08-21: `.github/workflows/ci.yml` estaba versionado y quedaba fuera del barrido. La
    exclusión tiene que ser por COMPONENTE de ruta, no por subcadena."""
    repo = _repo_git(tmp_path, {
        ".github/workflows/ci.yml":
            f"jobs:\n  build:\n    env:\n      GROQ_API_KEY: {FALSO_GROQ}\n"})

    # (b) la mutación entró: el fichero contiene la forma Y git lo conoce.
    assert FALSO_GROQ in (repo / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    versionados = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True,
                                 text=True).stdout
    assert ".github/workflows/ci.yml" in versionados, "la mutación no se aplicó: git no lo ve"

    hallazgos = revisar_secretos(repo)
    assert len(hallazgos) == 1, f"un secreto en .github/workflows no se cazó: {hallazgos}"
    assert hallazgos[0].codigo == "SEC001"
    assert ".github/workflows/ci.yml" in hallazgos[0].fichero.replace("\\", "/")


def test_varios_patrones_distintos(tmp_path: Path):
    repo = _repo_git(tmp_path, {
        "a.py": f'x = "{FALSO_AWS}"\n',
        "b.env.example": f"ANTHROPIC={FALSO_ANTHROPIC}\n",
        "c.pem": f"{FALSO_PRIVADA}\nabc\n",
    })
    ficheros = {h.fichero for h in revisar_secretos(repo)}
    assert len(ficheros) == 3, f"faltan patrones: {ficheros}"


def test_una_linea_da_UN_hallazgo_aunque_casen_dos_patrones(tmp_path: Path):
    repo = _repo_git(tmp_path, {"m.py": f'x = "{FALSO_GROQ}" ; y = "{FALSO_AWS}"\n'})
    assert len(revisar_secretos(repo)) == 1, "N patrones sobre una línea es ruido, no señal"


def test_no_hay_falso_positivo_en_texto_normal(tmp_path: Path):
    """Precisión sobre cobertura: nada de heurísticas de entropía."""
    repo = _repo_git(tmp_path, {
        "doc.md": ("La clave se guarda en .env y nunca en el repo. sk- no es una clave, "
                   "gsk_ tampoco, y AKIA suelto menos.\n"),
        "code.py": 'password = os.environ["PW"]\nsecret_key = cfg.get("k")\n',
    })
    assert revisar_secretos(repo) == []


def test_ignora_binarios_y_venv(tmp_path: Path):
    repo = _repo_git(tmp_path, {"venv/lib/x.py": f'k="{FALSO_GROQ}"\n'})
    (repo / "img.png").write_bytes(b"\x89PNG\r\n" + FALSO_GROQ.encode())
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert revisar_secretos(repo) == []


def test_el_propio_paquete_no_tiene_fugas():
    """Autoescaneo: si este test falla, hay una credencial en este repo."""
    assert revisar_secretos(REPO) == []


def test_todos_los_patrones_son_regex_compilados():
    assert PATRONES, "sin patrones el detector es un no-op silencioso"
    for nombre, patron in PATRONES.items():
        assert hasattr(patron, "search"), nombre


def test_coge_el_formato_moderno_sk_proj(tmp_path: Path):
    """`sk-proj-…` lleva guiones dentro. El patrón anterior paraba en el primer guion y no
    veía ninguna clave de OpenAI emitida después del cambio de formato."""
    falso = "sk-" + "proj-" + "AbCd1234" + "_efGH-5678" + "ijKL90mn"
    repo = _repo_git(tmp_path, {"c.py": f'K = "{falso}"\n'})
    assert falso in (repo / "c.py").read_text(encoding="utf-8"), "la mutación no entró"
    assert len(revisar_secretos(repo)) == 1, "no ve el formato moderno de OpenAI"


def test_NO_salta_con_palabras_que_terminan_en_sk(tmp_path: Path):
    """La trampa que abre el guion: `task-`, `disk-`, `risk-` contienen un `sk-` seguido de
    20+ caracteres válidos. El `\\b` del patrón es lo único que separa ampliar cobertura de
    fabricar ruido, así que se verifica."""
    repo = _repo_git(tmp_path, {
        "a.py": "clase = 'task-management-controller-factory'\n",
        "b.py": "modo = 'disk-usage-monitoring-daemon'\n",
        "c.md": "El modelo `risk-adjusted-returns-estimator` no es una clave.\n",
    })
    assert revisar_secretos(repo) == [], "el guion en la clase abrió un falso positivo"


def test_patrones_nuevos_de_google_y_supabase(tmp_path: Path):
    falso_aiza = "AIza" + "B" * 35
    falso_aq = "AQ." + "Ab8" + "C" * 44
    falso_sb = "sb" + "_secret_" + "D" * 24
    repo = _repo_git(tmp_path, {
        "g1.env.example": f"GEMINI={falso_aiza}\n",
        "g2.md": f"clave: {falso_aq}\n",
        "s.py": f'K = "{falso_sb}"\n',
    })
    ficheros = {h.fichero for h in revisar_secretos(repo)}
    assert len(ficheros) == 3, f"falta algún patrón nuevo: {ficheros}"


def test_el_nombre_de_variable_SUPABASE_no_es_un_secreto(tmp_path: Path):
    """Guardia de regresión de una medición, no una opinión: `SUPABASE.{0,20}(key|KEY)` se
    propuso como patrón y se rechazó porque daba 35 aciertos y los 35 eran falsos. Si alguien
    lo vuelve a añadir, esto lo para."""
    repo = _repo_git(tmp_path, {
        ".env.example": "SUPABASE_URL=https://ejemplo.supabase.co\nSUPABASE_KEY=tu-clave-aqui\n",
        "cfg.py": 'SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]\n',
    })
    assert revisar_secretos(repo) == [], "el nombre de la variable no es la credencial"


def test_todo_hallazgo_dice_que_hacer(tmp_path: Path):
    repo = _repo_git(tmp_path, {"c.py": f'K = "{FALSO_GROQ}"\n'})
    for h in revisar_secretos(repo):
        assert "Rota" in h.arreglo or "rota" in h.arreglo, (
            "el arreglo debe empezar por rotar: la credencial está comprometida desde el "
            "primer commit, y borrarla del HEAD no la protege")
        assert len(h.arreglo) > 30
