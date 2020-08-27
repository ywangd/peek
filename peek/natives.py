import logging

from configobj import ConfigObj

from peek.config import config_location
from peek.connection import ConnectFunc
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
                    _logger.warning(f'Config key [{key}] conflicts. '
                                    f'Value of [{key_component}] is not a [dict], '
                                    f'but [{type(child)}]')
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


class SessionFunc:

    def __call__(self, app, current=None, **options):
        for symbol in options.get('@', []):
            if symbol == 'info':
                return app.es_client_manager.current.info()
            elif symbol == 'remove':
                app.es_client_manager.remove_client(None)  # remove current client
            else:
                raise PeekError(f'Unknown sub-command: {symbol!r}')

        current = current if current is not None else options.get('current', None)
        if current is not None:
            app.es_client_manager.set_current(current)

        remove = options.get('remove', None)
        if remove is not None:
            app.es_client_manager.remove_client(remove)

        rename = options.get('rename', None)
        if rename:
            app.es_client_manager.current.name = str(rename)

        info = options.get('info', None)
        if info is not None:
            return app.es_client_manager.get_client(info).info()

        return str(app.es_client_manager)

    @property
    def options(self):
        return {'current': None, 'remove': None, 'rename': None, 'info': None,
                '@info': None, '@remove': None}

    @property
    def description(self):
        return 'List sessions and set current session'


class RunFunc:

    def __call__(self, app, file, **options):
        with open(file) as ins:
            app.process_input(ins.read(), echo=options.get('echo', True))

    @property
    def options(self):
        return {'echo': False}

    @property
    def description(self):
        return 'Load and execute external script'


class ResetFunc:

    def __call__(self, app, *args, **kwargs):
        app.reset()

    @property
    def description(self):
        return 'Reset state of the program'


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
        return 'View history and execute by history id'


class RangeFunc:

    def __call__(self, app, start, stop, step=1):
        return list(range(start, stop, step))

    @property
    def description(self):
        return 'Range over given start and stop (exclusive) and optionally a step'


class EchoFunc:

    def __call__(self, app, *args, **options):
        return ' '.join(str(arg) for arg in args)

    @property
    def description(self):
        return 'Print given items'


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
        return 'Capture session'


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


EXPORTS = {
    'connect': ConnectFunc(),
    'config': ConfigFunc(),
    'session': SessionFunc(),
    'run': RunFunc(),
    'history': HistoryFunc(),
    'echo': EchoFunc(),
    'range': RangeFunc(),
    'reset': ResetFunc(),
    'capture': CaptureFunc(),
    'help': HelpFunc(),
    'saml_authenticate': SamlAuthenticateFunc(),
    'oidc_authenticate': OidcAuthenticateFunc(),
    'krb_authenticate': KrbAuthenticateFunc(),
}
