import json
import logging
import os
import ssl
import time
import urllib
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Any, Optional

from peek.connection import EsClient, RefreshingEsClient
from peek.errors import PeekError

_logger = logging.getLogger(__name__)


class _SamlExchange:
    callback_path = None


class CallbackHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        pass

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        _SamlExchange.callback_path = body
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Callback received, you can now close the browser tab.')

    def log_message(self, fmt: str, *args: Any) -> None:
        _logger.info("%s - - [%s] %s\n" %
                     (self.address_string(),
                      self.log_date_time_string(),
                      fmt % args))


def saml_authenticate(es_client: EsClient, realm: str, callback_port: str, name: Optional[str]):
    _logger.info(f'SAML authenticate for realm {realm!r} and callback port {callback_port!r}')
    prepare_response = _saml_prepare(es_client, realm)
    httpd = _saml_start_http_server(callback_port)
    print('Please use browser to complete authentication against the idP')
    webbrowser.open(prepare_response['redirect'])
    while _SamlExchange.callback_path is None:
        time.sleep(0.1)
    try:
        httpd.shutdown()
        query = urllib.parse.parse_qs(_SamlExchange.callback_path.decode())
        if 'SAMLResponse' not in query or len(query['SAMLResponse']) != 1:
            raise PeekError(f'Invalid saml callback response: {_SamlExchange.callback_path!r}')
        content = query['SAMLResponse'][0]
        auth_response = _saml_do_authenticate(es_client, realm, prepare_response['id'], content)
        return RefreshingEsClient(
            es_client,
            auth_response['username'],
            auth_response['access_token'],
            auth_response['refresh_token'],
            auth_response['expires_in'],
            name=name)
    finally:
        _SamlExchange.callback_path = None


def _saml_prepare(es_client, realm: str):
    return es_client.perform_request(
        'POST',
        '/_security/saml/prepare',
        json.dumps({
            'realm': realm,
        }),
        deserialize_it=True
    )


def _saml_do_authenticate(es_client, realm: str, _id: str, content: str):
    response = es_client.perform_request(
        'POST',
        '/_security/saml/authenticate',
        json.dumps({
            'realm': realm,
            'ids': [_id],
            'content': content,
        }),
        deserialize_it=True
    )
    return response


def _saml_start_http_server(callback_port):
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
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


class SamlAuthenticateFunc:
    def __call__(self, app, **options):
        realm = options.get('realm', 'saml1')
        conn = options.get('conn', None)
        saml_es_client = saml_authenticate(
            app.es_client_manager.current if conn is None else app.es_client_manager.get_client(conn),
            realm,
            options.get('callback_port', '5601'),
            name=options.get('name', None),
        )
        app.es_client_manager.add(saml_es_client)
        return json.dumps({'username': saml_es_client.username, 'realm': 'realm'})

    @property
    def options(self):
        return {'realm': 'saml1', 'callback_port': '5601', 'name': None, 'conn': None}

    @property
    def description(self):
        return 'Start SAML authentication flow'
