"""La última corrida de CI de cada repo público tiene que estar en verde.

## Por qué existe, medido el 2026-08-30

La CI de `capa-normativa` estuvo **ROJA desde el 2026-08-24 hasta el 2026-08-30**: seis días, diez
corridas fallidas seguidas. Nadie se enteró. Se descubrió por casualidad, al añadir Windows a la
matriz por un motivo distinto.

Y lo que fallaba no era grave —dos tests que sólo pasaban en Windows y uno atado a la máquina—.
**Lo grave era el silencio.**

## El patrón, que ya está documentado en otro sitio

Los tableros SÍ se leen: hay una ronda diaria y un aviso al arrancar cualquier sesión. La CI no
tenía ni una cosa ni la otra. Detectaba, y su resultado no llegaba a nadie — el mismo hueco entre
**detección** y **entrega** que recoge `docs/decisiones/QUE_INTERRUMPE_Y_QUE_ESPERA_2026-08-29.md`.

Este comprobador es el puente: mete el resultado de la CI en el sitio que sí se mira.

## Por qué sólo los PÚBLICOS

Son los que un reclutador puede abrir, y una insignia roja en el README es lo primero que se ve.
Los privados importan menos y la lista se deriva igual, así que ampliarlo es cambiar una constante.

## La trampa prohibida, en sus dos caras

Si no se puede preguntar a GitHub —falta `gh`, no hay red, no hay permisos— esto **jamás es
verde**. Y tampoco es rojo: un repo sin ningún workflow no tiene una CI rota, no tiene CI. Se
informa aparte, porque acusar a un repo de tener la CI roja cuando no la tiene es la misma mentira
al revés.

## Es el primero que estrena la tercera casilla, y por qué le tocaba a éste

Nació el 2026-08-30 diciendo *«no se pudo preguntar → ROJO»*, con el argumento de que no mirar
nunca puede leerse como aprobar. El argumento es bueno y sigue en pie; lo que estaba mal era el
sitio donde caía, porque metía en la misma casilla dos frases distintas: *«he mirado y la CI está
rota»* y *«no he podido mirar»*.

Ahora devuelve **MUDO** (`None`). Y eso resuelve algo que aquí no tenía solución: **este
comprobador no puede saber si el fallo es de un rato o permanente.** Que `gh` no conteste una vez
puede ser la red; que no conteste nunca es que no está instalado. Desde dentro se ven idénticos.

Con la casilla nueva no hace falta distinguirlos: se dice MUDO, y si es permanente **insistirá**
y la ronda lo convertirá en ROJO ella sola a los dos días con ronda. El tiempo decide lo que el
comprobador no puede — y mientras tanto el mudo está a la vista, con su motivo, no escondido.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

#: Se reutiliza la enumeración de repos públicos del comprobador del escaparate: si un día cambia
#: cómo se decide qué es público, tiene que cambiar en un solo sitio.
_spec = importlib.util.spec_from_file_location(
    "escaparate_para_ci", str(AQUI / "escaparate_con_guarda.py"))
_hermano = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hermano)

NoSePudoMirar = _hermano.NoSePudoMirar
publicos = _hermano.publicos

#: Conclusiones que NO son un fallo. `None` es una corrida en curso: aún no ha dicho nada.
_TOLERADAS = {"success", "neutral", "skipped", None, ""}


def _ultima_corrida(repo: Path) -> tuple[str | None, str]:
    """(conclusión, detalle) de la última corrida de CI, o (None, motivo) si no hay ninguna."""
    r = subprocess.run(
        ["gh", "run", "list", "--limit", "1", "--json",
         "conclusion,status,headBranch,createdAt,workflowName"],
        cwd=str(repo), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=180, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise NoSePudoMirar(f"gh no contesta en {repo.name}: {r.stderr.strip()[:90]}")
    try:
        filas = json.loads(r.stdout or "[]")
    except json.JSONDecodeError as e:
        raise NoSePudoMirar(f"respuesta de gh ilegible para {repo.name}: {e}") from e
    if not filas:
        return None, "sin ninguna corrida"
    f = filas[0]
    detalle = (f"{f.get('workflowName', '?')} · {str(f.get('createdAt', ''))[:10]} · "
               f"{f.get('headBranch', '?')}")
    if f.get("status") != "completed":
        return None, f"en curso ({detalle})"
    return f.get("conclusion"), detalle


def ci_de_los_publicos_en_verde() -> tuple[bool | None, str]:
    """VERDE / ROJO / MUDO (`None`). Ver el docstring del modulo: no poder mirar es MUDO."""
    try:
        pubs = publicos()
    except NoSePudoMirar as e:
        return None, f"no se pudo mirar ({e}). Eso NO es «las CI estan verdes»."
    except OSError as e:
        return None, (f"no se pudo ni enumerar los repos ({type(e).__name__}: {e}). "
                      "Eso NO es «las CI estan verdes»: es no haber podido mirar.")
    if not pubs:
        # Esto SI es rojo y no mudo: `gh` ha contestado, y ha contestado algo imposible. No es no
        # haber podido mirar — es haber mirado y ver algo que no cuadra.
        return False, "cero repos publicos detectados: sospechoso, no limpio"

    rojas, sin_ci, en_curso = [], [], []
    for repo in pubs:
        try:
            conclusion, detalle = _ultima_corrida(repo)
        except NoSePudoMirar as e:
            return None, f"no se pudo preguntar ({e}). Eso NO es «estan verdes»."
        except OSError as e:
            return None, (f"no se pudo lanzar gh ({type(e).__name__}: {e}). "
                          "Eso NO es «estan verdes».")
        if detalle == "sin ninguna corrida":
            sin_ci.append(repo.name)
        elif detalle.startswith("en curso"):
            en_curso.append(repo.name)
        elif conclusion not in _TOLERADAS:
            rojas.append(f"{repo.name} ({conclusion}, {detalle})")

    # Un repo SIN workflows no tiene la CI rota: no tiene CI. Se informa y no cuenta como fallo.
    cola = ""
    if sin_ci:
        cola = f" (aparte, sin poner rojo: {len(sin_ci)} sin ninguna corrida — {', '.join(sin_ci)})"
    if en_curso:
        cola += f" ({len(en_curso)} en curso ahora mismo, aun sin veredicto)"

    if rojas:
        return False, ("la ULTIMA corrida de CI esta ROJA en: " + "; ".join(rojas)
                       + ". Una CI roja que nadie lee deja de ser una CI" + cola)
    return True, (f"la ultima corrida de CI esta en verde en los {len(pubs) - len(sin_ci)} repos "
                  f"publicos que la tienen" + cola)


if __name__ == "__main__":
    ok, msg = ci_de_los_publicos_en_verde()
    # 3 = NO CONCLUYENTE, el mismo codigo que usa el tablero. Quien llame a este guion por
    # separado tiene que poder distinguir las tres cosas igual que las distingue el tablero.
    print(("MUDO: " if ok is None else "VERDE: " if ok else "ROJO: ") + msg)
    sys.exit(3 if ok is None else 0 if ok else 1)
