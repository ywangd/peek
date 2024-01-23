import base64
import json
import logging
import os
from abc import ABCMeta, abstractmethod
from typing import List, Iterable

import elastic_transport.client_utils
from elastic_transport import Transport
from configobj import Section
from elastic_transport import NodeConfig
from elasticsearch import AuthenticationException

from peek.errors import PeekError

_logger = logging.getLogger(__name__)


class NoopDeserializer:
    def __init__(self, delegate):
        self._delegate = delegate

    def dumps(self, *args, **kwargs):
        return self._delegate.dumps(*args, **kwargs)

    def loads(self, s, *args, **kwargs):
        return s

    def get_serializer(self, *args, **kwargs):
        return self._delegate.get_serializer(*args, **kwargs)


class BaseClient(metaclass=ABCMeta):
    @abstractmethod
    def perform_request(self, method, path, payload=None, deserialize_it=False, **kwargs):
        pass


class EsClient(BaseClient):
    def __init__(
        self,
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
    ):
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
        self.api_key = api_key
        self.token = token
        self.assert_fingerprint = None  # TODO: fill this in
        self.ssl_show_warn = None  # TODO: fill this in as well

        self.headers = headers
        request_headers = {} if self.headers is None else dict(self.headers)

        # The order of authentication scheme is API key, token then basic auth.
        # We add them in reverse order so that later ones overwrite the earlier ones
        # TODO: use basic_auth_to_header utility method from the transport lib
        if self.auth:
            request_headers.update({'Authorization': 'Basic ' + base64.b64encode(self.auth.encode('utf-8')).decode()})

        if self.token:
            request_headers.update({'Authorization': f'Bearer {self.token}'})

        if self.api_key:
            request_headers.update(
                {'Authorization': 'ApiKey ' + base64.b64encode(':'.join(self.api_key).encode('utf-8')).decode()}
            )

        hosts = []
        if self.hosts:
            for host in self.hosts.split(','):
                if host.startswith('http://') or host.startswith('https://'):
                    hosts.append(host)
                else:
                    hosts.append(f'http://{host}')

        node_configs = []
        for host in hosts:
            node_config = elastic_transport.client_utils.url_to_node_config(host)
            replacements = {'headers': dict(node_config.headers)}
            replacements['headers'].update(request_headers)
            if node_config.scheme == 'https':
                if self.ca_certs:
                    replacements['ca_certs'] = self.ca_certs
                if self.client_cert:
                    replacements['client_cert'] = self.client_cert
                if self.client_key:
                    replacements['client_key'] = self.client_key
                if self.assert_hostname:
                    replacements['ssl_assert_hostname'] = self.assert_hostname
                if self.assert_fingerprint:
                    replacements['ssl_assert_fingerprint'] = self.assert_fingerprint
                if self.ssl_show_warn:
                    replacements['ssl_show_warn'] = self.ssl_show_warn

            node_configs.append(node_config.replace(**replacements))

        if self.cloud_id:
            cloud_id = elastic_transport.client_utils.parse_cloud_id(self.cloud_id)
            node_config = NodeConfig(
                scheme='https', host=cloud_id.es_address[0], port=cloud_id.es_address[1], http_compress=True
            )
            node_configs.append(node_config.replace(headers=request_headers))

        if not node_configs:
            raise ValueError('no node configurations found')

        # Timeout is handled at perform_request
        self.transport = Transport(node_configs, max_retries=0, retry_on_timeout=False)

    def perform_request(self, method, path, payload=None, deserialize_it=False, headers=None, **kwargs):
        _logger.debug(f'Performing request: {method!r}, {path!r}, {payload!r}')
        serializers = self.transport.serializers
        try:
            if not deserialize_it:
                # Avoid deserializing the response since we parse it with the main loop for syntax highlighting
                self.transport.serializers = NoopDeserializer(serializers)

            http_headers = elastic_transport.HttpHeaders(headers)

            if payload is not None and 'content-type' not in http_headers:
                http_headers['content-type'] = 'application/json'

            response = self.transport.perform_request(
                method, path, body=payload, request_timeout=None, headers=http_headers, **kwargs
            )
            # TODO: process meta
            return response.body.decode('utf-8')
        finally:
            if not deserialize_it:
                self.transport.serializers = serializers

    def info(self):
        if self.api_key:
            auth = f'ApiKey {self.api_key[0][:10]}...'
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

    def to_dict(self):
        return {
            'name': self.name,
            'hosts': self.hosts,
            'cloud_id': self.cloud_id,
            'username': self.auth.split(':')[0] if self.auth else None,
            'password': None,  # do not persist password
            'use_ssl': self.use_ssl,
            'verify_certs': self.verify_certs,
            'assert_hostname': self.assert_hostname,
            'ca_certs': self.ca_certs,
            'client_cert': self.client_cert,
            'client_key': self.client_key,
            'api_key': ':'.join(self.api_key) if self.api_key else None,
            'token': self.token,
            'headers': self.headers,
        }

    @staticmethod
    def from_dict(app, d):
        return connect(app, **d)

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
            hosts.append(self.cloud_id.split(':')[0] + "@Cloud")

        hosts = ','.join(hosts)
        if self.api_key:
            return f'K-{self.api_key[0][:10]} @ {hosts}'
        elif self.token:
            return f'T-{self.token[:10]} @ {hosts}'
        elif self.auth:
            username = self.auth.split(':')[0]
            return f'{username} @ {hosts}'
        else:
            return f'{hosts}'


class RefreshingEsClient(BaseClient):
    def __init__(self, parent: EsClient, username, access_token, refresh_token, expires_in, name=None):
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
                    'POST',
                    '/_security/oauth2/token',
                    json.dumps(
                        {
                            'grant_type': 'refresh_token',
                            'refresh_token': self.refresh_token,
                        }
                    ),
                    deserialize_it=True,
                )
                self.access_token = response['access_token']
                self.refresh_token = response['refresh_token']
                self.expires_in = response['expires_in']
                self._build_delegate()
                self.perform_request(method, path, payload, deserialize_it=deserialize_it, **kwargs)

    def info(self):
        info = self.delegate.info()
        info['username'] = self.username
        return info

    def to_dict(self):
        return {
            'name': self.name,
            'username': self.username,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'expires_in': self.expires_in,
            'parent': self.parent,
        }

    @staticmethod
    def from_dict(d):
        return RefreshingEsClient(**d)

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


class DelegatingListener:
    def __init__(self, on_add=None, on_set=None, on_remove=None):
        self._on_add = on_add
        self._on_set = on_set
        self._on_remove = on_remove

    def on_add(self, m):
        return self._on_add(m) if self._on_add is not None else True

    def on_set(self, m):
        return self._on_set(m) if self._on_set is not None else True

    def on_remove(self, m, c):
        return self._on_remove(m, c) if self._on_remove is not None else True


class EsClientManager:
    def __init__(self, listeners: Iterable[DelegatingListener] = ()):
        self._clients: List[EsClient] = []
        self._index_current = None
        self.listeners = listeners

    def add(self, client):
        self._clients.append(client)
        self._index_current = len(self._clients) - 1
        # TODO: maintain size
        for listener in self.listeners:
            if listener.on_add(self) is False:
                break

    @property
    def index_current(self):
        return self._index_current

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
                raise PeekError(f'Attempt to set ES client at invalid index {x!r}')
            self._index_current = x
        else:
            raise ValueError(f'Connection must be specified by either name or index, got {x!r}')
        for listener in self.listeners:
            if listener.on_set(self) is False:
                break

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
            if x < 0 or x >= len(self._clients):
                raise PeekError(f'Attempt to remove ES client at invalid index [{x}]')
            removed = self._clients.pop(x)
            if not self._clients:
                self._index_current = None
                return
            if x < self._index_current:
                self._index_current -= 1
            elif x == self._index_current:
                self._index_current = 0
            for listener in self.listeners:
                if listener.on_remove(self, removed) is False:
                    break
        else:
            raise ValueError(f'Connection must be specified by either name or index, got {x!r}')

    def keep_client(self, x=None):
        """
        Keep the specified client, remove everything else
        """
        keep = self.get_client(x)
        self._index_current = 0
        self._clients = [keep]

    def move_current_to(self, idx: int):
        if not isinstance(idx, int):
            raise PeekError(f'Index must be integer, got {idx!r}')
        if 0 <= idx < len(self._clients):
            if idx == self._index_current:
                return
            self._clients.insert(idx, self._clients.pop(self._index_current))
            self._index_current = idx
        else:
            raise PeekError(f'Attempt to move ES client to an invalid index: {idx!r}')

    def to_dict(self):
        result = {
            '_index_current': self._index_current,
            '_clients': [],
        }
        for client in self._clients:
            d = client.to_dict()
            if isinstance(client, RefreshingEsClient):
                try:
                    d['parent'] = self._clients.index(d['parent'])
                except ValueError:
                    d['parent'] = d['parent'].to_dict()
            result['_clients'].append(d)
        return result

    @staticmethod
    def from_dict(app, d):
        m = EsClientManager()
        _clients = []
        for c in d['_clients']:
            if 'parent' in c:
                c = dict(c)  # avoid mutating argument
                if isinstance(c['parent'], int):
                    # Based on how clients are arranged, it is guaranteed that parent client must have
                    # an index less than the refreshing client
                    c['parent'] = _clients[c['parent']]
                else:
                    c['parent'] = EsClient.from_dict(app, c['parent'])
                client = RefreshingEsClient.from_dict(c)
            else:
                client = EsClient.from_dict(app, c)
            _clients.append(client)

        m._clients = _clients
        m._index_current = d['_index_current']
        return m

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
    'use_ssl': False,
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

    final_options.update(_maybe_configure_smart_connect(app, options))

    if final_options['cloud_id'] is not None:
        final_options['hosts'] = None

    if final_options['api_key']:
        return _connect_api_key(app, **final_options)
    elif final_options['token']:
        return _connect_token(app, **final_options)
    else:
        return _connect_userpass(app, **final_options)


def _maybe_configure_smart_connect(app, options: dict):
    # Override with provided options, including null values since it could be intentional
    smart_options = {k: v for k, v in options.items()}
    # Attempt to configure smart connect based on the last HTTP response
    if len(options) == 0:
        try:
            last_response = app.vm.get_value('_')
            if 'id' in last_response and 'api_key' in last_response:
                _maybe_copy_current_client_options(app, smart_options)
                smart_options['api_key'] = f'{last_response["id"]}:{last_response["api_key"]}'
            elif 'access_token' in last_response:
                _maybe_copy_current_client_options(app, smart_options)
                smart_options['token'] = last_response['access_token']
            elif 'token' in last_response and 'value' in last_response['token']:
                _maybe_copy_current_client_options(app, smart_options)
                smart_options['token'] = last_response['token']['value']
            else:
                last_request = app.vm.get_value('__')
                urlpath = last_request['path']
                if last_request['method'] in ('POST', 'PUT') and (
                    urlpath.startswith('/_security/user/') or urlpath.startswith('/_xpack/security/user/')
                ):
                    if urlpath.startswith('/_security/user/'):
                        username = urlpath[len('/_security/user/') :]
                    else:
                        username = urlpath[len('/_xpack/security/user/') :]
                    payload = json.loads(last_request['payload'])
                    password = payload.get('password', None)
                    _maybe_copy_current_client_options(app, smart_options)
                    smart_options['username'] = username
                    smart_options['password'] = password

        except NameError:  # if _ does not exist, simply ignore and proceed
            pass

    return smart_options


def _maybe_copy_current_client_options(app, options: dict):
    if hasattr(app, 'es_client_manager') and len(app.es_client_manager.clients()) > 0:
        current_es_client = app.es_client_manager.current
        if current_es_client.cloud_id is not None:
            options['cloud_id'] = current_es_client.cloud_id
        else:
            options['hosts'] = current_es_client.hosts

        options['use_ssl'] = current_es_client.use_ssl
        options['verify_certs'] = current_es_client.verify_certs
        options['assert_hostname'] = current_es_client.assert_hostname
        options['ca_certs'] = current_es_client.ca_certs
        options['client_cert'] = current_es_client.client_cert
        options['client_key'] = current_es_client.client_key
        # not copy the headers


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
    api_key = options['api_key']
    if ':' not in api_key:
        api_key = base64.decodebytes(api_key.encode()).decode()

    if ':' not in api_key:
        raise ValueError('invalid api key credential format')

    return EsClient(
        name=options['name'],
        hosts=options['hosts'],
        cloud_id=options['cloud_id'],
        api_key=api_key.split(':'),
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
        test_connection = app.config.as_bool('test_connection')
        opt = options.pop('test', None)
        if opt is not None:
            test_connection = opt
        es_client = connect(app, **options)
        if test_connection:
            try:
                app.display.info(es_client.perform_request('GET', '/_security/_authenticate'))
            except Exception as e:
                app.display.error(e)
                return
        app.es_client_manager.add(es_client)
        return str(app.es_client_manager)

    @property
    def options(self):
        _options = dict(DEFAULT_OPTIONS)
        _options['test'] = None
        return _options

    @property
    def description(self):
        return 'Connect to an Elasticsearch cluster'
