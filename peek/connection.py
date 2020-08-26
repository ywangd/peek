import json
import logging
import os
from abc import ABCMeta, abstractmethod
from typing import List

from configobj import Section
from elasticsearch import Elasticsearch, AuthenticationException
from urllib3 import Timeout

from peek.errors import PeekError

_logger = logging.getLogger(__name__)


class NoopDeserializer:
    def __init__(self):
        pass

    def loads(self, s, *args, **kwargs):
        return s


noopDeserializer = NoopDeserializer()


class BaseClient(metaclass=ABCMeta):

    @abstractmethod
    def perform_request(self, method, path, payload=None, deserialize_it=False, **kwargs):
        pass


class EsClient(BaseClient):

    def __init__(self,
                 name=None,
                 hosts=None,
                 cloud_id=None,
                 username=None,
                 password=None,
                 use_ssl=False,
                 verify_certs=False,
                 assert_hostname=False,
                 ca_certs=None,
                 client_cert=None,
                 client_key=None,
                 api_key=None,
                 token=None,
                 headers=None,
                 **kwargs):

        self.name = name
        self.hosts = hosts
        self.cloud_id = cloud_id
        self.auth = f'{username}:{password}' if username and password else None
        self.use_ssl = use_ssl
        self.verify_certs = verify_certs
        self.assert_hostname = assert_hostname
        self.ca_certs = ca_certs
        self.client_cert = client_cert
        self.client_key = client_key
        self.api_key_id = api_key[0] if api_key else None
        self.token = token
        self.headers = dict(headers) if headers is not None else None
        if token:
            token_header = {'Authorization': f'Bearer {token}'}
            if headers:
                headers.update(token_header)
            else:
                headers = token_header

        self.es = Elasticsearch(
            hosts=self.hosts.split(',') if self.hosts else None,
            cloud_id=cloud_id,
            http_auth=self.auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            ca_certs=ca_certs,
            client_cert=client_cert,
            client_key=client_key,
            ssl_show_warn=False,
            timeout=Timeout(connect=None, read=None),
            api_key=api_key,
            headers=headers,
            ssl_assert_hostname=assert_hostname,
            **kwargs,
        )

    def perform_request(self, method, path, payload=None, deserialize_it=False, **kwargs):
        _logger.debug(f'Performing request: {method!r}, {path!r}, {payload!r}')
        deserializer = self.es.transport.deserializer
        try:
            if not deserialize_it:
                # Avoid deserializing the response since we parse it with the main loop for syntax highlighting
                self.es.transport.deserializer = noopDeserializer
            return self.es.transport.perform_request(method, path, body=payload, **kwargs)
        finally:
            if not deserialize_it:
                self.es.transport.deserializer = deserializer

    def info(self):
        if self.api_key_id:
            auth = f'ApiKey {self.api_key_id[:10]}...'
        elif self.token:
            auth = f'Token {self.token[:10]}...'
        elif self.auth:
            auth = f'Username {self.auth.split(":")[0]}'
        else:
            auth = None

        if self.headers:
            headers = list(self.headers.keys())
        else:
            headers = None

        return {
            'name': self.name,
            'hosts': self.hosts,
            'cloud_id': self.cloud_id,
            'auth': auth,
            'use_ssl': self.use_ssl,
            'verify_certs': self.verify_certs,
            'ca_certs': self.ca_certs,
            'client_cert': self.client_cert,
            'client_key': self.client_key,
            'headers': headers,
        }

    def __str__(self):
        if self.name:
            return f'{self.name}'

        hosts = []
        if self.hosts:
            for host in self.hosts.split(','):
                if host.startswith('https://') or host.startswith('http://'):
                    hosts.append(host)
                else:
                    hosts.append(('https://' if self.use_ssl else 'http://') + host)
        else:
            hosts.append(self.cloud_id)

        hosts = ','.join(hosts)
        if self.api_key_id:
            return f'K-{self.api_key_id[:10]} @ {hosts}'
        elif self.token:
            return f'T-{self.token[:10]} @ {hosts}'
        elif self.auth:
            username = self.auth.split(':')[0]
            return f'{username} @ {hosts}'
        else:
            return f'{hosts}'


class RefreshingEsClient(BaseClient):
    # TODO: Given a pair of access_token and refresh token, refresh to keep login

    def __init__(self,
                 parent: EsClient,
                 username,
                 access_token,
                 refresh_token,
                 expires_in,
                 name=None):

        self.parent = parent
        self.username = username
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.name = name
        self.delegate = self._build_delegate()

    def __getattr__(self, item):
        return getattr(self.delegate, item)

    def perform_request(self, method, path, payload=None, deserialize_it=False, **kwargs):
        try:
            return self.delegate.perform_request(method, path, payload, deserialize_it, **kwargs)
        except AuthenticationException as e:
            if e.status_code == 401:
                response = self.parent.perform_request(
                    'POST', '/_security/oauth2/token',
                    json.dumps({
                        'grant_type': 'refresh_token',
                        'refresh_token': self.refresh_token,
                    }),
                    deserialize_it=True)
                self.access_token = response['access_token']
                self.refresh_token = response['refresh_token']
                self.expires_in = response['expires_in']
                self._build_delegate()
                self.perform_request(method, path, payload, deserialize_it=deserialize_it, **kwargs)

    def info(self):
        info = self.delegate.info()
        info['username'] = self.username
        return info

    def __str__(self):
        if self.name:
            return f'{self.name}'
        else:
            return f'{self.username} @ {self.delegate}'

    def _build_delegate(self):
        return EsClient(
            name=self.name,
            hosts=self.parent.hosts,
            cloud_id=self.parent.cloud_id,
            use_ssl=self.parent.use_ssl,
            verify_certs=self.parent.verify_certs,
            ca_certs=self.parent.ca_certs,
            client_cert=self.parent.client_cert,
            client_key=self.parent.client_key,
            headers=self.parent.headers,
            token=self.access_token,
        )


class EsClientManager:

    def __init__(self):
        self._clients: List[EsClient] = []
        self._index_current = None

    def add(self, client):
        self._clients.append(client)
        self._index_current = len(self._clients) - 1
        # TODO: maintain size

    @property
    def current(self):
        if self._index_current is None:
            raise PeekError('No ES client is configured')
        if self._index_current < 0 or self._index_current >= len(self._clients):
            raise PeekError(f'Attempt to get ES client at invalid index [{self._index_current}]')
        return self._clients[self._index_current]

    def set_current(self, x):
        if isinstance(x, str):
            name = x
            self._index_current = self._clients.index(self.get_client(name))
        elif isinstance(x, int):
            if x < 0 or x >= len(self._clients):
                raise PeekError(f'Attempt to set ES client at invalid index [{x}]')
            self._index_current = x
        else:
            raise ValueError(f'Connection must be specified by either name or index, got {x!r}')

    def clients(self):
        return self._clients

    def get_client(self, x=None):
        if x is None:
            return self.current
        elif isinstance(x, str):
            name = x
            if not name:
                raise ValueError('Name cannot be empty')
            for c in self._clients:
                if c.name == name:
                    return c
            else:
                raise ValueError(f'No client with name: {name!r}')
        elif isinstance(x, int):
            if x < 0 or x >= len(self._clients):
                raise PeekError(f'Attempt to set ES client at invalid index [{x}]')
            return self._clients[x]
        else:
            raise ValueError(f'Connection must be specified by either name or index, got {x!r}')

    def remove_client(self, x=None):
        if x is None:
            self.remove_client(self._index_current)
        elif isinstance(x, str):
            idx = self._clients.index(self.get_client(x))
            self.remove_client(idx)
        elif isinstance(x, int):
            if len(self._clients) == 1:
                raise PeekError('Cannot delete the last connection')
            if x < 0 or x >= len(self._clients):
                raise PeekError(f'Attempt to remove ES client at invalid index [{x}]')
            self._clients.pop(x)
            if not self._clients:
                self._index_current = None
                return
            if x < self._index_current:
                self._index_current -= 1
            elif x == self._index_current:
                self._index_current = 0
        else:
            raise ValueError(f'Connection must be specified by either name or index, got {x!r}')

    def __str__(self):
        lines = []
        for i, client in enumerate(self.clients()):
            prefix = '*' if client == self.current else ' '
            index = f'[{i}]'
            lines.append(f'{prefix} {index:>4} {client}')
        return '\n'.join(lines)


DEFAULT_OPTIONS = {
    'name': None,
    'hosts': 'localhost:9200',
    'cloud_id': None,
    'username': None,
    'password': None,
    'api_key': None,
    'token': None,
    'use_ssl': None,
    'verify_certs': False,
    'assert_hostname': False,
    'ca_certs': None,
    'client_cert': None,
    'client_key': None,
    'headers': None,
    'force_prompt': False,
    'no_prompt': False,
}


def connect(app, **options):
    final_options = dict(DEFAULT_OPTIONS)

    if isinstance(app.config.get('connection'), Section):
        final_options.update({k: v for k, v in app.config.get('connection').dict().items() if v})

    # Override with provided options, including null values since it could be intentional
    final_options.update({k: v for k, v in options.items()})

    if final_options['cloud_id'] is not None:
        final_options['hosts'] = None

    if final_options['api_key']:
        return _connect_api_key(app, **final_options)
    elif final_options['token']:
        return _connect_token(app, **final_options)
    else:
        return _connect_userpass(app, **final_options)


def _connect_userpass(app, **options):
    username = options.get('username')
    password = options.get('password')
    if options['hosts']:
        service_name = f'peek/{options["hosts"]}/userpass'
    else:
        service_name = f'peek/{options["cloud_id"]}/userpass'

    if not username and password:
        raise PeekError('Username is required for userpass authentication')

    if options['force_prompt']:
        password = app.input(message='Please enter password: ', is_secret=True)

    if username and not password:
        password = os.environ.get('PEEK_PASSWORD', None)
        if not password:
            if app.config.as_bool('use_keyring'):
                password = _keyring(service_name, username)
                if not password:
                    if options['no_prompt']:
                        raise PeekError('Password is not found and password prompt is disabled')
                    password = app.input(message='Please enter password: ', is_secret=True)

            else:
                if options['no_prompt']:
                    raise PeekError('Password is not found and password prompt is disabled')
                password = app.input(message='Please enter password: ', is_secret=True)

    if username and password and app.config.as_bool('use_keyring'):
        _keyring(service_name, username, password)

    return EsClient(
        name=options['name'],
        hosts=options['hosts'],
        cloud_id=options['cloud_id'],
        username=username,
        password=password,
        use_ssl=options['use_ssl'],
        verify_certs=options['verify_certs'],
        assert_hostname=options['assert_hostname'],
        ca_certs=options['ca_certs'],
        client_cert=options['client_cert'],
        client_key=options['client_key'],
        headers=options['headers'],
    )


def _connect_api_key(app, **options):
    _logger.debug('Connecting with API key')
    return EsClient(
        name=options['name'],
        hosts=options['hosts'],
        cloud_id=options['cloud_id'],
        api_key=options['api_key'].split(':'),
        use_ssl=options['use_ssl'],
        verify_certs=options['verify_certs'],
        assert_hostname=options['assert_hostname'],
        ca_certs=options['ca_certs'],
        client_cert=options['client_cert'],
        client_key=options['client_key'],
        headers=options['headers'],
    )


def _connect_token(app, **options):
    _logger.debug('Connecting with token')
    return EsClient(
        name=options['name'],
        hosts=options['hosts'],
        cloud_id=options['cloud_id'],
        token=options['token'],
        use_ssl=options['use_ssl'],
        verify_certs=options['verify_certs'],
        assert_hostname=options['assert_hostname'],
        ca_certs=options['ca_certs'],
        client_cert=options['client_cert'],
        client_key=options['client_key'],
        headers=options['headers'],
    )


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


class ConnectFunc:
    def __call__(self, app, **options):
        app.es_client_manager.add(connect(app, **options))
        return str(app.es_client_manager)

    @property
    def options(self):
        return dict(DEFAULT_OPTIONS)
