import logging
import os
from enum import Enum

from elasticsearch import Elasticsearch
from peek.errors import PeekError

_logger = logging.getLogger(__name__)


class NoopDeserializer:
    def __init__(self):
        pass

    def loads(self, s, *args, **kwargs):
        return s


noopDeserializer = NoopDeserializer()


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


class AuthType(Enum):
    USERPASS = 'USERPASS'
    APIKEY = 'APIKEY'
    TOKEN = 'TOKEN'
    SAML = 'SAML'
    OIDC = 'OIDC'
    KRB = 'KRB'
    PKI = 'PKI'


def connect(app, **options):
    final_options = {
        'hosts': 'localhost',
        'auth_type': AuthType.USERPASS,
        'username': None,
        'password': None,
        'api_key': None,
        'use_ssl': None,
        'verify_certs': False,
        'ca_certs': None,
        'client_cert': None,
        'client_key': None,
        'force_prompt': False,
        'no_prompt': False,
    }

    if 'auth_type' in options:
        options['auth_type'] = AuthType(options['auth_type'])
    final_options.update({k: v for k, v in options.items() if v is not None})

    if final_options['auth_type'] is AuthType.USERPASS:
        return _connect_userpass(app, **final_options)
    else:
        raise NotImplementedError(f'{final_options["auth_type"]}')


def _connect_userpass(app, **options):
    username = options.get('username')
    password = options.get('password')
    service_name = f'peek/{options["hosts"]}/userpass'

    if not username and password:
        raise PeekError(f'Username is required for userpass authentication')

    if options['force_prompt']:
        password = app.request_input(message='Please enter password: ', is_secret=True)

    if username and not password:
        password = os.environ.get('PEEK_PASSWORD', None)
        if not password:
            if app.config.as_bool('use_keyring'):
                password = _keyring(service_name, username)
                if not password:
                    if options['no_prompt']:
                        raise PeekError('Password is not found and password prompt is disabled')
                    password = app.request_input(message='Please enter password: ', is_secret=True)

            else:
                if options['no_prompt']:
                    raise PeekError('Password is not found and password prompt is disabled')
                password = app.request_input(message='Please enter password: ', is_secret=True)

    auth = f'{username}:{password}' if username and password else None

    if auth is not None and app.config.as_bool('use_keyring'):
        _keyring(service_name, username, password)

    return EsClient(
        hosts=options['hosts'],
        auth=auth,
        use_ssl=options['use_ssl'],
        verify_certs=options['verify_certs'],
        ca_certs=options['ca_certs'],
        client_cert=options['client_cert'],
        client_key=options['client_key'])


KEYRING = None


def _keyring(service_name, key, value=None):
    """
    When a None value is passed in, means getting value out of the keyring
    """
    global KEYRING
    if KEYRING is None:
        import importlib
        try:
            KEYRING = importlib.import_module("keyring")
        except ModuleNotFoundError as e:
            _logger.warning("import keyring failed: %r.", e)

    if KEYRING is not None:
        if value is None:
            return KEYRING.get_password(service_name, key)
        else:
            KEYRING.set_password(service_name, key, value)
