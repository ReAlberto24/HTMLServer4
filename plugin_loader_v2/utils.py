from typing import Union, Optional, Any
from types import ModuleType
import os
import importlib.util


# Mutable
class Importer:
    def __init__(self, file: Union[str, bytes, os.PathLike]):
        """
        Class used as dynamic importer
        :param file: Indicates what file is going to be imported
        """
        self.__file = file.decode() if isinstance(file, bytes) else file
        self.__injected: list[tuple[str, Any]] = []

    def inject_attr(self, attr: tuple[str, Any]) -> 'Importer':
        """
        Add a variable to the globals of the module before loading,

        <b>possibly unsafe</b>
        :param attr:
        :return:
        """
        self.__injected.append(attr)
        return self

    def load(self) -> ModuleType:
        name = self.__file.split(os.sep)[-1].split('.')[0]
        spec = importlib.util.spec_from_file_location(name, self.__file)
        module = importlib.util.module_from_spec(spec)
        for name, attr in self.__injected:
            setattr(module, name, attr)
        spec.loader.exec_module(module)
        return module
