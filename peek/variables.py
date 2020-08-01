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


def func_conn(app, **options):
    app.add_es_client(connect(app, **options))


VARIABLES = {
    'connect': func_conn,
    'config': func_config,
}
