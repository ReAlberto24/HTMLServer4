import os
from dataclasses import dataclass
from types import ModuleType
from typing import Any
import general
from yaml import safe_load
import io
import sys
import importlib.util
import contextlib
from colors import FC, OPS
from plugin_manager import Manager, ManagerError
from enum import Enum
from quart import Quart


def check_requirements_from_dict(data: dict) -> bool:
    required_attrs = ('plugin.name', 'plugin.version', 'plugin.main-file',
                      'plugin.id', 'loader.required-version', 'loader.preferred-version')
    # for key in flatten_dict(data).keys():
    #     if not (key in required_attrs):
    #         return False
    for required_attr in required_attrs:
        if not (required_attr in general.flatten_dict(data).keys()):
            return False
    flatten_data = general.flatten_dict(data)
    for attr in required_attrs:
        if flatten_data.get(attr) is None:
            return False
    return True


@dataclass
class PluginConfiguration:
    name: str
    version: float
    main_file: str
    id_: str
    loader_required: float
    loader_preferred: float

    def from_dict(self, data: dict):
        # if check_requirements_from_dict(data=data):
        flatten_data = general.flatten_dict(data)
        self.name = flatten_data.get('plugin.name')
        self.version = flatten_data.get('plugin.version')
        self.main_file = flatten_data.get('plugin.main-file')
        self.id_ = flatten_data.get('plugin.id')
        self.loader_required = flatten_data.get('loader.required-version')
        self.loader_preferred = flatten_data.get('loader.preferred-version')


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
    def __init__(self,
                 configuration: PluginConfiguration,
                 stdout_buffer: PrefixedStringIO):
        self.configuration: PluginConfiguration = configuration
        self.main_file: str = configuration.main_file
        self.stdout_buffer: PrefixedStringIO = stdout_buffer

        self.injected_attrs = []
        self.module: ModuleType = None
        self.manager: Manager = None

    def __repr__(self) -> str:
        return (f'{self.configuration.name} > {self.configuration.version} '
                f'(required loader: {self.configuration.loader_required})')

    def __str__(self) -> str:
        return self.__repr__()

    def inject_attr(self, attr: Any, attr_name: str) -> None:
        self.injected_attrs.append((attr, attr_name))

    def init(self) -> None:
        name = self.main_file.split(os.sep)[-1].split('.')[0]
        spec = importlib.util.spec_from_file_location(name, self.main_file)
        module = importlib.util.module_from_spec(spec)
        for attr, name in self.injected_attrs:
            setattr(module, name, attr)
        with contextlib.redirect_stdout(self.stdout_buffer):
            spec.loader.exec_module(module)
        self.module = module

    def load_manager(self) -> None:
        try:
            self.manager = self.module.manager
        except AttributeError:
            for value in self.module.__dict__.values():
                if isinstance(value, Manager):
                    self.manager = value
                    break
            else:
                raise ValueError(f'{self.configuration.name} : Manager Not Found')


class PluginError(Exception):
    def __init__(self, _type: str, message: str):
        self._type = _type
        self.message = message

    def __str__(self):
        return f'PluginError<{self._type}>: {self.message}'


class LoaderState:  # (Enum):
    base: int = 0
    load_plugins: int = 1
    init_plugins: int = 2
    loaded_managers: int = 3


class Loader:
    def __init__(self,
                 plugin_directory: str = 'plugins',
                 raise_on_error: bool = False):
        self.directory = plugin_directory
        self.plugins: list[Plugin] = []
        self.plugin_loaded = LoaderState.base
        self.roe = raise_on_error
        self.exposed = {}
        self.longest_endpoint = 0
        self.longest_id = 0

    def load_plugins(self):
        for plugin in os.listdir(self.directory):
            plugin_path = os.path.join(self.directory, plugin)
            if not os.path.exists(os.path.join(plugin_path, 'plugin.yml')):
                if self.roe:
                    raise PluginError('Loader', f'Plugin "{plugin}" doesn\'t contain a "plugin.yml" file')
                print(str(PluginError('Loader', f'Plugin "{plugin}" doesn\'t contain a "plugin.yml" file')))
                continue
            with open(os.path.join(plugin_path, 'plugin.yml'), 'r') as _f_plugin_configuration:
                plugin_configuration = safe_load(_f_plugin_configuration)
            if check_requirements_from_dict(data=plugin_configuration):
                if not plugin_configuration.get('loader').get('enable-plugin', True):
                    # Plugin disabled
                    continue
                plugin_conf = PluginConfiguration(
                    name=None,
                    version=None,
                    main_file=None,
                    id_=None,
                    loader_required=None,
                    loader_preferred=None
                )
                plugin_conf.from_dict(data=plugin_configuration)
                # Fix for the damn main file
                plugin_conf.main_file = os.path.join(self.directory, plugin, plugin_conf.main_file)
            else:
                if self.roe:
                    raise PluginError('Loader', f'Plugin "{plugin}" configuration isn\'t complete')
                print(str(PluginError('Loader', f'Plugin "{plugin}" configuration isn\'t complete')))
                continue

            plg: Plugin = Plugin(
                configuration=plugin_conf,
                stdout_buffer=PrefixedStringIO(f'Plugin<{FC.LIGHT_MAGENTA}{plugin_conf.id_}{OPS.RESET}> ')
            )

            self.plugins.append(plg)
        self.plugin_loaded = LoaderState.load_plugins

    def init_plugins(self):
        if self.plugin_loaded < LoaderState.load_plugins:
            if self.roe:
                raise PluginError('Loader', f'Use .load_plugins() before')
            print(str(PluginError('Loader', f'Use .load_plugins() before')))
            return
        for plugin in self.plugins:
            plugin.init()
        self.plugin_loaded = LoaderState.init_plugins

    def load_managers(self):
        if self.plugin_loaded < LoaderState.init_plugins:
            if self.roe:
                raise PluginError('Loader', f'Use .init_plugins() before')
            print(str(PluginError('Loader', f'Use .init_plugins() before')))
            return
        for plugin in self.plugins:
            plugin.load_manager()
            # Another ID
            #   if plugin.manager.functions.get('on-manager-load') is not None:
            #       plugin.manager._call_id('on-manager-load')
        self.plugin_loaded = LoaderState.loaded_managers

        # new expose method
        for plugin in self.plugins:
            for name, (func, overrideable) in plugin.manager._exposed.items():
                if name in self.exposed and not overrideable:
                    raise SyntaxError(
                        f'Function "{name}" is already present, enable override ({plugin.configuration.name})')
                self.exposed[name] = func

        all_endpoints = [endpoint for plugin in self.plugins for endpoint in
                         (list(plugin.manager.endpoints.keys()) + list(plugin.manager.sockets.keys()))]
        self.longest_endpoint = len(max(all_endpoints, key=len)) if all_endpoints else 0

        all_ids = [plugin.configuration.id_ for plugin in self.plugins]
        self.longest_id = len(max(all_ids, key=len)) if all_ids else 0

    def call_id(self, id_, *args, **kwargs):
        if self.plugin_loaded < LoaderState.loaded_managers:
            if self.roe:
                raise PluginError('Loader', f'Use .init_plugins() before')
            print(str(PluginError('Loader', f'Use .init_plugins() before')))
            return
        for plugin in self.plugins:
            try:
                with contextlib.redirect_stdout(plugin.stdout_buffer):
                    retrn = plugin.manager.call_id(id_, *args, **kwargs)
                    if retrn is not None:
                        return retrn
            except ManagerError:
                # if e._type == 'FunctionNotFound':
                #     pass
                continue

    def get_exposed(self, function: str):
        if self.plugin_loaded < LoaderState.loaded_managers:
            if self.roe:
                raise PluginError('Loader', f'Use .init_plugins() before')
            print(str(PluginError('Loader', f'Use .init_plugins() before')))
            return
        if function not in self.exposed:
            if self.roe:
                raise PluginError('FunctionNotFound', f'The specified function "{function}" could not be found')
            print(str(PluginError('FunctionNotFound', f'The specified function "{function}" could not be found')))
            return
        return self.exposed[function]

    def run(self, function: str, *args, **kwargs) -> tuple[str, int] | None:
        if self.plugin_loaded < LoaderState.loaded_managers:
            if self.roe:
                raise PluginError('Loader', f'Use .init_plugins() before')
            print(str(PluginError('Loader', f'Use .init_plugins() before')))
            return
        if function not in self.exposed:
            if self.roe:
                raise PluginError('FunctionNotFound', f'The specified function "{function}" could not be found')
            print(str(PluginError('FunctionNotFound', f'The specified function "{function}" could not be found')))
            return
        return self.exposed[function](*args, **kwargs)

    def print_events(self):
        for plugin in self.plugins:
            print(f'{FC.LIGHT_MAGENTA}{plugin.configuration.id_}{OPS.RESET} events: ' +
                  ', '.join([f'{FC.DARK_YELLOW}{i}{OPS.RESET}' for i in plugin.manager.functions.keys()]))

    def load_endpoints(self, app: Quart, methods: list[str], error_handlers: list[int]) -> None:
        for plugin in self.plugins:
            with contextlib.redirect_stdout(plugin.stdout_buffer):
                plugin.manager.functions.get('plugin.loading.pre-endpoints', lambda: None)()

            for endpoint in plugin.manager.endpoints:
                new_function = general.create_endpoint_function(plugin, endpoint, self, error_handlers)
                doc = plugin.manager.endpoints[endpoint]['func'].__doc__ or 'No docs included'
                doc = doc.replace('\n', '\n         ')
                print(f'Adding endpoint       : {FC.DARK_YELLOW}{endpoint: <{self.longest_endpoint + 3}}{OPS.RESET} | '
                      f'{plugin.configuration.id_: <{self.longest_id + 3}} | {new_function.__name__}\n'
                      f' - lru cache enabled: {str(plugin.manager.endpoints[endpoint]['lru-cache']).lower()}\n'
                      f' - docs: {doc}')
                app.route(endpoint, methods=methods)(new_function)

            with contextlib.redirect_stdout(plugin.stdout_buffer):
                plugin.manager.functions.get('plugin.loading.post-endpoints', lambda: None)()

    def load_sockets(self, app: Quart) -> None:
        for plugin in self.plugins:
            with contextlib.redirect_stdout(plugin.stdout_buffer):
                plugin.manager.functions.get('plugin.loading.pre-sockets', lambda: None)()

            for socket in plugin.manager.sockets:
                new_function = general.create_socket_function(plugin, socket)
                doc = plugin.manager.sockets[socket].__doc__ or 'No docs included'
                doc = doc.replace('\n', '\n         ')
                print(f'Adding endpoint       : {FC.DARK_YELLOW}{socket: <{self.longest_endpoint + 3}}{OPS.RESET} | '
                      f'{plugin.configuration.id_: <{self.longest_id + 3}} | {new_function.__name__}\n - docs: {doc}')
                app.websocket(socket)(new_function)

            with contextlib.redirect_stdout(plugin.stdout_buffer):
                plugin.manager.functions.get('plugin.loading.post-sockets', lambda: None)()
