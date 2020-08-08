import json
import logging
import os
import ssl
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Any

from peek.connection import EsClient, RefreshingEsClient

_logger = logging.getLogger(__name__)


class _OidcExchange:
    callback_path = None


class CallbackHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        _OidcExchange.callback_path = self.path
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


def oidc_authenticate(es_client: EsClient, realm: str, callback_port: str):
    _logger.info(f'OIDC authenticate for realm {realm!r} and callback port {callback_port!r}')
    prepare_response = _oidc_prepare(es_client, realm)
    httpd = _oidc_start_http_server(callback_port)
    print('Please use browser to complete authentication against the idP')
    webbrowser.open(prepare_response['redirect'])
    while _OidcExchange.callback_path is None:
        time.sleep(0.1)
    try:
        httpd.shutdown()
        auth_response = _oidc_do_authenticate(es_client, realm, prepare_response['state'], prepare_response['nonce'],
                                              _OidcExchange.callback_path)
        return _oidc_build_es_client(es_client, auth_response)
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


def _oidc_build_es_client(es_client, auth_response):
    return RefreshingEsClient(
        es_client,
        auth_response['username'],
        auth_response['access_token'],
        auth_response['refresh_token'],
        auth_response['expires_in'])


def _oidc_start_http_server(callback_port):
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
