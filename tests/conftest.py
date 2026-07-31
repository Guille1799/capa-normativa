"""Los tests prueban ESTE repo, no la copia instalada.

Sin esto, `pytest` importa `capa_normativa` de site-packages si está instalado, así
que la suite mide una versión distinta de la que se está editando. Se vio en la v0.2.0:
cinco tests nuevos fallaron contra la 0.1.0 instalada. Fallar por el motivo equivocado
se detecta; el peligro real es el simétrico — **pasar** por el motivo equivocado, con el
código del repo roto y la copia instalada tapándolo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
