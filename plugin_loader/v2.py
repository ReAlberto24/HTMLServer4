import io
from utils import Importer
from typing import Union, Any, Optional, Type
import os
import sys
import yaml
from pathlib import Path
from types import ModuleType
from colors import *

from plugin_manager import Manager


CWD = os.getcwd()
SCHEMA = {
    'plugin': {
        '?name': str,
        '?version': float,
        'main-file': str,
        'id': str,
        '?inject-manager': bool,
    },
    'loader': {
        'required-version': float,
        'preferred-version': float,
    },
}


class PrefixedStringIO(io.StringIO):
    def __init__(self, prefix, *args, **kwargs):
        self.prefix = prefix
        self.added = False
        super().__init__(*args, **kwargs)

    def write(self, s):
        if not self.added:
            sys.__stdout__.write(self.prefix + s)
            self.added = True
        else:
            sys.__stdout__.write(s)
        if '\n' in s:
            self.added = False


class Plugin:
    def __init__(self, file: Union[str, bytes, os.PathLike]):
        self.__directory: str = file.decode() if isinstance(file, bytes) else file

        self.__main_file: Union[str, os.PathLike] = None
        self.__module: ModuleType = None

        self.__config: Plugin.Configuration = None
        self.__prefix_io: PrefixedStringIO = None

    class PluginError(Exception):
        pass

    class Configuration:
        def __init__(self, data: dict[str, Any]):
            self.__base_data = data
            # for k, v in data.items():
            #     setattr(self, k, v)

        def get(self, item, default: Any = None):
            try:
                return self.__base_data[item]
            except (AttributeError, Exception):
                return default

        def items(self) -> list[tuple[str, Any]]:
            return self.__base_data.items()

        def keys(self) -> list[str]:
            return self.__base_data.keys()

        def values(self) -> list[Any]:
            return self.__base_data.values()

        @staticmethod
        def __get_type(value: Union[dict, list, tuple, 'Plugin.Configuration']):
            if isinstance(value, (dict, Plugin.Configuration)):
                return {k: Plugin.Configuration.__get_type(v) for k, v in value.items()}
            elif isinstance(value, (list, tuple)):
                return [Plugin.Configuration.__get_type(v) for v in value]
            else:
                return type(value)

        @staticmethod
        def __tuple2list(data: Union[dict, list, tuple, 'Plugin.Configuration']):
            if isinstance(data, (dict, Plugin.Configuration)):
                return {k: Plugin.Configuration.__tuple2list(v) for k, v in data.items()}
            elif isinstance(data, (list, tuple)):
                if not any(map(lambda x: isinstance(x, tuple) or isinstance(x, list), data)):
                    return list(data)
                else:
                    return [Plugin.Configuration.__tuple2list(v) for v in data]
            else:
                return data

        @staticmethod
        def __verify_schema(data: Union[dict, list, tuple, 'Plugin.Configuration'],
                            schema: dict[str, Any]):
            """
            Verify if the data follows the schema, now supports optional keys.
            :param data: Data to verify.
            :param schema: Schema to verify against, with optional keys marked with '?'.
            :return: bool
            """
            if isinstance(data, dict) and isinstance(schema, dict):
                # Transform schema by handling optional keys and ensuring all required keys are present
                transformed_schema = {}
                for key, value_schema in schema.items():
                    if key.startswith('?'):
                        optional_key = key[1:]
                        if optional_key in data:
                            transformed_schema[optional_key] = value_schema
                    else:
                        if key not in data:
                            return False  # Missing required key
                        transformed_schema[key] = value_schema

                # Recursively verify each key in the transformed schema
                for key, value_schema in transformed_schema.items():
                    if not Plugin.Configuration.__verify_schema(data.get(key), value_schema):
                        return False

                return True
            elif isinstance(data, (list, tuple)) and isinstance(schema, (list, tuple)):
                # For lists and tuples, verify each element if the schema is a single-element list
                if len(schema) == 1:
                    value_schema = schema[0]
                    for item in data:
                        if not Plugin.Configuration.__verify_schema(item, value_schema):
                            return False
                    return True
                else:
                    return False  # Mismatch in the structure of lists/tuples
            else:
                # Direct comparison for non-container types
                return isinstance(data, schema) if isinstance(schema, type) else data == schema

        def verify_schema(self, schema: dict[str, Any]) -> bool:
            """
            Verify if the data follows the schema, now supports optional keys.
            :param schema: Schema to verify against, with optional keys marked with '?'.
            :return: bool
            """
            return self.__verify_schema(self.__base_data, schema)

        def __getitem__(self, item) -> Any:
            return self.__base_data[item]

        def __repr__(self) -> str:
            return repr(self.__base_data)

        def __str__(self) -> str:
            return str(self.__base_data)

    def init(self) -> None:
        """
        Loads the configuration of the plugin
        :return:
        """
        with open(os.path.join(self.__directory, 'plugin.yml'), 'r') as file:
            self.__config: Plugin.Configuration = Plugin.Configuration(yaml.safe_load(file))

        if not self.__config.verify_schema(SCHEMA):
            raise Plugin.PluginError('Configuration invalid schema')

        self.__prefix_io: PrefixedStringIO = PrefixedStringIO(
            f'Plugin<{FC.LIGHT_MAGENTA}{self.__config['plugin']['id']}{OPS.RESET}> '
        )
        self.__main_file: Union[str, os.PathLike] = os.path.join(self.__directory, self.__config['plugin']['main-file'])

    def __str__(self) -> str:
        return (f'Plugin({self.__config['plugin'].get('name', 'id:' + self.__config['plugin']['id'])}, '
                f'version: {self.__config.get('version', 'N/A')}, '
                f'required loader: {self.__config['loader']['required-version']})')

    def load(self) -> None:
        importer = Importer(self.__main_file)
        if self.__config['plugin'].get('inject-manager'):
            print(f'Injecting manager in {str(self)}')
            raise NotImplementedError()

        self.__module: ModuleType = importer.load()

    def get_manager(self) -> Manager:


if __name__ == '__main__':
    plugin = Plugin(Path(os.path.join(CWD, '..', 'plugins', 'v2_plugin')).resolve())
    plugin.init()
    plugin.load()
