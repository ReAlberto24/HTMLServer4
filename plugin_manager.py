import asyncio
from functools import wraps, partial
import functools
import warnings
import inspect
from typing import Callable

import general

warnings.simplefilter('once', DeprecationWarning)


def deprecated(old_function_name: str, new_function_name: str):
    """
    This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    """
    def decorator(func1):
        fmt1 = 'Call to deprecated function "{ofn}", use "{nfn}" instead.'

        @functools.wraps(func1)
        def new_func1(*args, **kwargs):
            warnings.warn(
                fmt1.format(ofn=old_function_name, nfn=new_function_name),
                category=DeprecationWarning,
                stacklevel=2
            )
            return func1(*args, **kwargs)
        return new_func1
    return decorator


class PluginManagerError(Exception):
    pass


class ManagerError(PluginManagerError):
    def __init__(self, _type: str, message: str):
        self._type = _type
        self.message = message

    def __str__(self):
        return f'ManagerError<{self._type}>: {self.message}'


class FunctionNotFound(ManagerError):
    def __init__(self, message: str):
        super().__init__('FunctionNotFound', message)


class FunctionNotAsync(ManagerError):
    def __init__(self, message: str):
        super().__init__('FunctionNotAsync', message)


class WrapperException(PluginManagerError):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f'WrapperException: {self.message}'


class ExclusiveReturn(WrapperException):
    def __init__(self, message: str, contents: ..., return_code: int):
        self.message = message
        self.contents = contents
        self.return_code = return_code

    def __str__(self):
        return f'ExclusiveReturn [{self.return_code}]: {self.message} '


class Manager:
    SERVER_INFORMATION: general.ServerInformation = general.ServerInformation({})

    def __init__(self):
        self._functions = {}
        self._endpoints = {}
        self._sockets = {}
        self._exposed = {}

    @staticmethod
    def sync_wrapper(func):
        @wraps(func)
        async def run(*args, **kwargs):
            loop = asyncio.get_event_loop()
            partial_func = partial(func, *args, **kwargs)
            return await loop.run_in_executor(None, partial_func)
        return run

    def websocket(self, endpoint: str):
        def decorator(func):
            # shit
            # if asyncio.iscoroutinefunction(func):
            #     self._sockets[endpoint] = func
            # else:
            #     warnings.warn(f'Function "{func.__name__}" is not async', SyntaxWarning)
            #     self._sockets[endpoint] = self.sync_wrapper(func)
            if not asyncio.iscoroutinefunction(func):
                raise SyntaxError(f'Function "{func.__name__}" is not async')
            if endpoint in self._sockets:
                raise SyntaxError(f'Endpoint "{endpoint}" is already linked to a function '
                                  f'({self._sockets[endpoint].__name__})')
            self._sockets[endpoint] = func

            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def route(self, endpoint: str, ):
                    # enable_cross_origin: bool = False,
                    # enable_lru_cache: bool = False):
        def decorator(func):
            if endpoint in self._endpoints:
                raise SyntaxError(f'Endpoint "{endpoint}" is already linked to a function '
                                  f'({self._endpoints[endpoint].__name__})')
            self._endpoints[endpoint] = {
                'func': func,
                'cross-origin': False,  # enable_cross_origin,
                'lru-cache': False,  # enable_lru_cache
            }

            def wrapper(*args, **kwargs) -> (..., int):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def on(self, event: str):
        def decorator(func):
            if event in self._functions:
                raise SyntaxError(f'Event "{event}" is already linked to a function '
                                  f'({self._functions[event].__name__})')
            self._functions[event] = func

            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def expose(self, override: bool | Callable = False, name: str = None):
        if inspect.isfunction(override):
            self._exposed[override.__name__] = (override, False)

            def wrapper(*args, **kwargs):
                return override(*args, **kwargs)
            return wrapper

        def decorator(func):
            if name is None:
                self._exposed[name] = (func, override)
            else:
                self._exposed[func.__name__] = (func, override)

            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    # Maintaining legacy HTMLServer3 plugin code
    def sock(self, endpoint: str):
        warnings.warn(
            f'Call to deprecated function "sock", use "websocket" instead',
            DeprecationWarning
        )
        return self.websocket(endpoint=endpoint)

    def wrap(self, event: str):
        warnings.warn(
            f'Call to deprecated function "wrap", use "on" instead',
            DeprecationWarning
        )
        return self.on(event=event)

    def endpoint(self, endpoint: str,
                       enable_cross_origin: bool = False,
                       enable_lru_cache: bool = False):
        warnings.warn(
            f'Call to deprecated function "endpoint", use "route" instead',
            DeprecationWarning
        )
        return self.route(endpoint=endpoint, enable_cross_origin=enable_cross_origin, enable_lru_cache=enable_lru_cache)

    # -

    def call_id(self, id_: str, *args, **kwargs):
        if self._functions.get(id_) is not None:
            return self._functions[id_](*args, **kwargs)
        else:
            raise FunctionNotFound('Cannot find the requested id_')

    def call_endpoint(self, endpoint: str, *args, **kwargs) -> tuple[str, int]:
        if self._endpoints.get(endpoint) is not None:
            return self._endpoints[endpoint]['func'](*args, **kwargs)
        else:
            raise FunctionNotFound('Cannot find the requested endpoint')

    def socket(self, endpoint: str, *args, **kwargs):
        if self._sockets.get(endpoint) is not None:
            return self._sockets[endpoint](*args, **kwargs)
        else:
            raise FunctionNotFound('Cannot find the requested endpoint')
