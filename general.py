from typing import Any
from collections.abc import MutableMapping


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

    class IncorrectType(Exception):
        def __init__(self, new_type: Any, _type: Any):
            super().__init__(f'Incorrect type "{new_type.__name__}", expected "{_type.__name__}"')

    def check_type(self, new_value: Any) -> Any:
        if isinstance(new_value, self.__type):
            self.__type = type(new_value)
            return new_value
        elif self.__raise_error:
            raise self.IncorrectType(type(new_value), self.__type)
        return self.__default
