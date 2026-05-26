"""Helper to load a Model subclass from a .py file."""
import importlib.util
import inspect
import sys
from pathlib import Path

from echo_quant.exceptions import ValidationError
from echo_quant.model import Model

def load_model_from_file(path: Path) -> Model:
    """Import `path` and return the first Model subclass (instantiated)."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if not spec or not spec.loader:
        raise ValidationError(f"Could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)

    candidates = [
        cls for name, cls in inspect.getmembers(mod, inspect.isclass)
        if issubclass(cls, Model) and cls is not Model
    ]
    if not candidates:
        raise ValidationError(f"No Model subclass found in {path}")
    if len(candidates) > 1:
        names = ", ".join(c.__name__ for c in candidates)
        raise ValidationError(f"Multiple Model subclasses in {path}: {names}. Define only one.")
    return candidates[0]()
