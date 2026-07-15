"""types_.py — Re-export alias para evitar colisión con el módulo built-in 'types'."""
from types import SimpleNamespace

# Importar desde el archivo types.py del proyecto raíz
import importlib.util, os, sys

_spec = importlib.util.spec_from_file_location(
    "project_types",
    os.path.join(os.path.dirname(__file__), "..", "project_types.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

InventoryRecord = _mod.InventoryRecord
ExclusionRule = _mod.ExclusionRule
SystemLog = _mod.SystemLog
SugerenciaCorreccion = _mod.SugerenciaCorreccion
AppState = _mod.AppState
