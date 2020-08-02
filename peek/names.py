import logging

from configobj import ConfigObj

from peek.connection import connect

_logger = logging.getLogger(__name__)


def func_config(app, **options):
    if not options:
        return app.config

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

    app.config.merge(ConfigObj(extra_config))


def func_connect(app, **options):
    app.add_es_client(connect(app, **options))


def func_connections(app, **options):
    lines = []
    for client in app.es_client_manager.clients():
        lines.append(('* ' if client == app.es_client_manager.current() else '  ') + str(client))
    return '\n'.join(lines)


NAMES = {
    'connect': func_connect,
    'config': func_config,
    'connections': func_connections,
}
