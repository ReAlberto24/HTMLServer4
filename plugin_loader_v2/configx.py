from types import ModuleType
import os
from utils import Importer

ROOT: str = os.path.dirname(os.path.abspath(__file__))
VERSION: float = 2.0

COMPATIBILITY: dict[float, ModuleType] = {
    1.0: Importer(os.path.join(ROOT, 'v1.py')).load()
}

print(COMPATIBILITY)
