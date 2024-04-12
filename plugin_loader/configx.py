from types import ModuleType
import os
from .utils import Importer

ROOT: str = os.path.dirname(os.path.abspath(__file__))
VERSION: float = 2.0


class V1CompatibilityLayer:
    def __init__(self, module: ModuleType):
        self.__module = module


COMPATIBILITY: dict[float, ModuleType] = {
    1.0: V1CompatibilityLayer(Importer(os.path.join(ROOT, 'v1.py')).load()),
}
