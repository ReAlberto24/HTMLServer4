from typing import Any
from collections.abc import MutableMapping
import os
from pathlib import Path
from colors import *
from quart import Request, Response, Websocket


# https://www.freecodecamp.org/news/how-to-flatten-a-dictionary-in-python-in-4-different-ways/
def flatten_dict(d: MutableMapping, parent_key: str = '', sep: str = '.') -> MutableMapping:
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def replace_variables(x: str, variables: dict[str, str] = None) -> str:
    """Given an x string, replaces the "variables" with the given values"""
    if variables is None:
        variables = {}
    for key, value in variables.items():
        x = x.replace(key, value)
    return x


class DynamicValue:
    """A value subjected to change in the configuration"""
    def __init__(self, v_type: Any, default: Any = Any, raise_error: bool = True):
        self.__type = v_type
        self.__default = default
        self.__raise_error = raise_error
        self.value = None

    class IncorrectType(Exception):
        def __init__(self, new_type: Any, _type: Any):
            super().__init__(f'Incorrect type "{new_type.__name__}", expected "{_type.__name__}"')

    def check_type(self, new_value: Any) -> Any:
        if isinstance(new_value, self.__type):
            self.__type = type(new_value)
            self.value = new_value
            return new_value
        elif self.__raise_error:
            raise self.IncorrectType(type(new_value), self.__type)
        return self.__default


def is_in_directory(root: str, path: str):
    """Checks if a file/directory is a subdirectory of another"""
    return os.path.abspath(path).startswith(os.path.abspath(root))


def resolve_directory_path(directory_path: str):
    """Resolves and sanitize the path"""
    return str(Path(directory_path).resolve())


def log_request(method: str = None,
                endpoint: str = None,
                return_code: int = None,
                raw_request: Request = None,
                raw_response: Response = None,
                custom_color: str = None) -> None:
    base_color = OPS.RESET

    if raw_request is not None:
        method = raw_request.method
        endpoint = raw_request.full_path if len(raw_request.args) > 0 else raw_request.path
        return_code = raw_response.status_code

    ext_return_code = f' - {return_code}'
    if return_code is None:
        ext_return_code = ''
        return_code = 0

    if 100 <= return_code <= 199:
        base_color = FC.WHITE
    if 200 <= return_code <= 299:
        base_color = FC.LIGHT_RED
    if 300 <= return_code <= 399:
        base_color = FC.LIGHT_MAGENTA
    if 400 <= return_code <= 499:
        base_color = FC.DARK_RED
    if 500 <= return_code <= 599:
        base_color = FC.DARK_CYAN

    if custom_color is not None:
        base_color = custom_color

    print(f'{base_color} {method: <7} - {endpoint}{ext_return_code} {OPS.RESET}')


class ServerInformation:
    def __init__(self, data: dict[str, Any]):
        for k, v in data.items():
            setattr(self, k, v)

    def get(self, item, default: None):
        try:
            return getattr(self, item)
        except (AttributeError, Exception):
            return default

    def __getitem__(self, item) -> Any:
        return getattr(self, item)


class WSWrapper(Websocket):
    pass

    async def broadcast(self) -> None:
        pass
