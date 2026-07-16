"""types_.py — Re-export alias para evitar colisión con el módulo built-in 'types'."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from project_types import (
    InventoryRecord,
    ExclusionRule,
    SystemLog,
    SugerenciaCorreccion,
    AppState,
)
