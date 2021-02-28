import json
import logging
import os
import ssl
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from queue import Queue
from threading import Thread
from typing import Any, Optional

from peek.connection import EsClient, RefreshingEsClient

_logger = logging.getLogger(__name__)


class _OidcExchange:
    callback_path = None


class CallbackHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        _logger.debug(f'Path is: {self.path}')
        _OidcExchange.callback_path.put(self.path)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Callback received, you can now close the browser tab.')

    def do_POST(self):
        pass

    def log_message(self, fmt: str, *args: Any) -> None:
        _logger.info("%s - - [%s] %s\n" %
                     (self.address_string(),
                      self.log_date_time_string(),
                      fmt % args))


def oidc_authenticate(es_client: EsClient, realm: str, callback_port: str, name: Optional[str]):
    _logger.info(f'OIDC authenticate for realm {realm!r} and callback port {callback_port!r}')
    prepare_response = _oidc_prepare(es_client, realm)
    httpd = _oidc_start_http_server(callback_port)
    print('Please use browser to complete authentication against the idP')
    webbrowser.open(prepare_response['redirect'])
    callback_path = _OidcExchange.callback_path.get()
    if isinstance(callback_path, bytes):
        callback_path = callback_path.decode('utf-8')
    try:
        httpd.shutdown()
        auth_response = _oidc_do_authenticate(es_client, realm, prepare_response['state'], prepare_response['nonce'],
                                              callback_path)
        return RefreshingEsClient(
            es_client,
            auth_response['username'],
            auth_response['access_token'],
            auth_response['refresh_token'],
            auth_response['expires_in'],
            name=name)
    finally:
        _OidcExchange.callback_path = None


def _oidc_prepare(es_client, realm: str):
    return es_client.perform_request(
        'POST',
        '/_security/oidc/prepare',
        json.dumps({
            'realm': realm,
        }),
        deserialize_it=True
    )


def _oidc_do_authenticate(es_client, realm: str, state: str, nonce: str, redirect_uri: str):
    response = es_client.perform_request(
        'POST',
        '/_security/oidc/authenticate',
        json.dumps({
            'realm': realm,
            'state': state,
            'nonce': nonce,
            'redirect_uri': redirect_uri,
        }),
        deserialize_it=True
    )
    return response


def _oidc_start_http_server(callback_port):
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    _OidcExchange.callback_path = Queue(maxsize=1)
    httpd = HTTPServer(('localhost', int(callback_port)), CallbackHTTPRequestHandler)
    keyfile = os.path.join(package_root, 'certs', 'key.pem')
    certfile = os.path.join(package_root, 'certs', 'cert.pem')
    httpd.socket = ssl.wrap_socket(
        httpd.socket,
        keyfile=keyfile,
        certfile=certfile,
        server_side=True)

    t = Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


class OidcAuthenticateFunc:
    def __call__(self, app, **options):
        realm = options.get('realm', 'oidc1')
        conn = options.get('conn', None)
        oidc_es_client = oidc_authenticate(
            app.es_client_manager.current if conn is None else app.es_client_manager.get_client(conn),
            realm,
            options.get('callback_port', '5601'),
            name=options.get('name', None),
        )
        app.es_client_manager.add(oidc_es_client)
        return json.dumps({'username': oidc_es_client.username, 'realm': 'realm'})

    @property
    def options(self):
        return {'realm': 'oidc1', 'callback_port': '5601', 'name': None, 'conn': None}

    @property
    def description(self):
        return 'Start OIDC authentication flow'
