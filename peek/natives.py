import json
import logging

from configobj import ConfigObj

from peek.common import DEFAULT_SAVE_NAME
from peek.config import config_location
from peek.connection import ConnectFunc, EsClientManager
from peek.errors import PeekError
from peek.krb import KrbAuthenticateFunc
from peek.oidc import OidcAuthenticateFunc
from peek.saml import SamlAuthenticateFunc

_logger = logging.getLogger(__name__)


class ConfigFunc:

    def __call__(self, app, **options):
        if not options:
            return {
                'location': config_location(),
                'config': app.config
            }

        extra_config = {}
        for key, value in options.items():
            parent = extra_config
            key_components = key.split('.')
            for key_component in key_components[:-1]:
                child = parent.get(key_component)
                if child is None:
                    parent[key_component] = {}
                elif not isinstance(child, dict):
                    _logger.warning(f'Config key {key!r} conflicts. '
                                    f'Value of {key_component!r} is not a dict, '
                                    f'but {type(child)!r}')
                    parent = None
                    break
                parent = parent[key_component]

            if isinstance(parent, dict):
                parent[key_components[-1]] = value

        # TODO: saner merge that does not change data type, e.g. from dict to primitive and vice versa
        app.config.merge(ConfigObj(extra_config))

    @property
    def description(self):
        return 'View and set config options'


class ConnectionFunc:

    def __call__(self, app, current=None, **options):
        options = consolidate_options(options, {
            'info': app.es_client_manager.index_current,
            'remove': app.es_client_manager.index_current,
            'keep': app.es_client_manager.index_current,
        })

        current = current if current is not None else options.get('current', None)
        if current is not None:
            app.es_client_manager.set_current(current)

        remove = options.get('remove', None)
        if remove is not None:
            app.es_client_manager.remove_client(remove)

        move = options.get('move', None)
        if move is not None:
            app.es_client_manager.move_current_to(move)

        keep = options.get('keep', None)
        if keep is not None:
            app.es_client_manager.keep_client(keep)

        rename = options.get('rename', None)
        if rename:
            app.es_client_manager.current.name = str(rename)

        info = options.get('info', None)
        if info is not None:
            return app.es_client_manager.get_client(info).info()

        return str(app.es_client_manager)

    @property
    def options(self):
        return {'current': None, 'remove': None, 'move': None, 'rename': None, 'info': None, 'keep': None,
                '@info': None, '@remove': None, '@keep': None}

    @property
    def description(self):
        return 'List connections and set current connection'


class SessionFunc:

    def __call__(self, app, **options):
        options = consolidate_options(options, {
            'load': DEFAULT_SAVE_NAME,
            'save': DEFAULT_SAVE_NAME,
            'clear': None,
        })

        if not options:
            return app.history.list_sessions()

        if 'load' in options:
            load = options.get('load')
            data = app.history.load_session(load)
            if data is None:
                raise PeekError(f'Session not found: {load!r}')
            else:
                app.es_client_manager = EsClientManager.from_dict(app, json.loads(data))
            return str(app.es_client_manager)

        elif 'save' in options:
            save = options.get('save')
            app.history.save_session(save, json.dumps(app.es_client_manager.to_dict()))
            return f'Session save as: {save!r}'

        elif 'remove' in options:
            remove = options.get('remove')
            if app.history.delete_session(remove):
                return f'Session removed: {remove!r}'
            else:
                raise PeekError(f'Session not found: {remove!r}')

        elif 'clear' in options:
            app.history.clear_sessions()
            return 'All sessions cleared'
        else:
            raise PeekError(f'Unknown options: {options}')

    @property
    def options(self):
        return {'save': None, 'load': None, 'remove': None,
                '@save': DEFAULT_SAVE_NAME, '@load': DEFAULT_SAVE_NAME, '@clear': None}

    @property
    def description(self):
        return 'Manage persisted sessions'


class RunFunc:

    def __call__(self, app, file, **options):
        with open(file) as ins:
            app.process_input(ins.read(), echo=options.get('echo', True))

    @property
    def options(self):
        return {'echo': True}

    @property
    def description(self):
        return 'Load and execute external script'


class HistoryFunc:

    def __call__(self, app, index=None, **options):
        if index is None:
            history = []
            for entry in app.history.load_recent(size=options.get('size', 100)):
                history.append(f'{entry[0]:>6} {entry[1]!r}')
            return '\n'.join(history)
        else:
            entry = app.history.get_entry(index)
            if entry is None:
                raise PeekError(f'History not found for index: {index}')
            app.process_input(entry[1])

    @property
    def options(self):
        return {'size': 100}

    @property
    def description(self):
        return 'View history and execute by history index'


class RangeFunc:

    def __call__(self, app, start, stop, step=1):
        return list(range(start, stop, step))

    @property
    def description(self):
        return 'Range over given start and stop (exclusive) with an optional step'


class EchoFunc:

    def __call__(self, app, *args, **options):
        content = ' '.join(str(arg) for arg in args)
        if 'file' in options:
            end = '\n'  # this does not make sense in interactive mode, so hardcode it for now
            with open(options.get('file'), 'a') as outs:
                outs.write(f'{content}{end}')
        else:
            return content

    @property
    def options(self):
        return {'file': None}

    @property
    def description(self):
        return 'Print given items, optionally appending to a file'


class CaptureFunc:

    def __call__(self, app, f=None, **options):
        directives = options.get('@')
        if not directives:
            return app.capture.status()

        # Only honor first directive
        directive = directives[0]
        if directive == 'start':
            return app.start_capture(f)

        elif directive == 'stop':
            return app.stop_capture()
        else:
            raise PeekError(f'Unknown capture directive: {directive}')

    @property
    def options(self):
        return {'@start': None, '@stop': None}

    @property
    def description(self):
        return 'Capture session IO into a file'


class ExitFunc:

    def __call__(self, app):
        if not app.batch_mode:
            app.signal_exit()

    @property
    def description(self):
        return 'Exit the current interactive session'


class HelpFunc:

    def __call__(self, app, func=None, **options):
        if func is None:
            return '\n'.join(k for k in app.vm.functions.keys())

        for k, v in app.vm.functions.items():
            if v == func:
                description = getattr(v, "description", None)
                header = k + (f' - {description}' if description else '')
                return f'{header}\n{getattr(func, "options", {})}'
        else:
            raise PeekError(f'No such function: {func}')

    @property
    def description(self):
        return 'List available functions and show help message of a function'


def consolidate_options(options, defaults):
    """
    Merge shorthanded @symbol into normal options kv pair with provided defaults
    """
    final_options = {k: v for k, v in options.items() if k != '@'}
    for symbol in options.get('@', []):
        if symbol not in defaults:
            raise PeekError(f'Unknown shorthanded flag: {symbol}')
        final_options[symbol] = defaults[symbol]
    return final_options


EXPORTS = {
    'connect': ConnectFunc(),
    'config': ConfigFunc(),
    'connection': ConnectionFunc(),
    'session': SessionFunc(),
    'run': RunFunc(),
    'history': HistoryFunc(),
    'echo': EchoFunc(),
    'range': RangeFunc(),
    'capture': CaptureFunc(),
    'exit': ExitFunc(),
    'help': HelpFunc(),
    'saml_authenticate': SamlAuthenticateFunc(),
    'oidc_authenticate': OidcAuthenticateFunc(),
    'krb_authenticate': KrbAuthenticateFunc(),
}
