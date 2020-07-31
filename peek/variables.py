import logging

from configobj import ConfigObj
from elasticsearch import Elasticsearch

_logger = logging.getLogger(__name__)


class EsClient:

    def __init__(self,
                 hosts='localhost:9200',
                 auth=None,
                 use_ssl=False, verify_certs=False, ca_certs=None,
                 client_cert=None, client_key=None):
        self.es = Elasticsearch(
            hosts=hosts,
            http_auth=auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            ca_certs=ca_certs,
            client_cert=client_cert,
            client_key=client_key,
            ssl_show_warn=False,
        )

    def perform_request(self, method, path, payload):
        deserializer = self.es.transport.deserializer
        try:
            # Avoid deserializing the response since we parse it with the main loop for syntax highlighting
            self.es.transport.deserializer = noopDeserializer
            return self.es.transport.perform_request(method, path, body=payload)
        finally:
            self.es.transport.deserializer = deserializer


class NoopDeserializer:
    def __init__(self):
        pass

    def loads(self, s, *args, **kwargs):
        return s


noopDeserializer = NoopDeserializer()


def func_conn(vm, **options):
    final_options = {
        'hosts': 'localhost',
        'auth': None,
        'use_ssl': None,
        'verify_certs': False,
        'ca_certs': None,
        'client_cert': None,
        'client_key': None,
    }
    auth = options.get('auth')
    if not auth:
        username = options.get('username')
        password = options.get('password')
        if username and password:
            auth = f'{username}:{password}'
            options.pop('username')
            options.pop('password')
            options['auth'] = auth
    final_options.update(options)
    vm.set_es_client(EsClient(**final_options))


def func_config(vm, **options):
    if not options:
        return vm.config

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

    vm.config.merge(ConfigObj(extra_config))


VARIABLES = {
    'conn': func_conn,
    'config': func_config,
}
