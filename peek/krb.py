import json
import logging
import urllib

from peek.connection import EsClient, RefreshingEsClient
from peek.errors import PeekError

_logger = logging.getLogger(__name__)


def krb_authenticate(es_client: EsClient, service=None, username=None, name=None):
    _logger.debug(f'Connection with Kerberos: {service}')
    if service is None:
        raise PeekError('Service is required for kerberos authentication')
    import kerberos
    result, context = kerberos.authGSSClientInit(service, principal=username)
    kerberos.authGSSClientStep(context, '')
    ticket = kerberos.authGSSClientResponse(context)
    _logger.debug(f'Kerberos ticket: {ticket}')
    auth_response = es_client.perform_request(
        'POST',
        '/_security/oauth2/token',
        json.dumps({
            'grant_type': '_kerberos',
            'kerberos_ticket': ticket,
        }),
        deserialize_it=True)
    _logger.debug(f'Kerberos Token auth response: {auth_response}')

    return RefreshingEsClient(
        es_client,
        '_KRB',
        auth_response['access_token'],
        auth_response['refresh_token'],
        auth_response['expires_in'],
        name=name)


class KrbAuthenticateFunc:
    def __call__(self, app, **options):
        service = options.get('service', None)
        conn = options.get('conn', None)
        if service is None:
            if app.es_client_manager.current.hosts:
                host = urllib.parse.urlparse(app.es_client_manager.current.hosts.split(',')[0]).hostname
                service = f'HTTP@{host}'
            else:
                raise PeekError('Cannot infer service principal. Please specify explicitly')

        krb_es_client = krb_authenticate(
            app.es_client_manager.current if conn is None else app.es_client_manager.get_client(conn),
            service,
            options.get('username', None),
            options.get('name', None)
        )
        app.es_client_manager.add(krb_es_client)
        return app.es_client_manager.current.perform_request('GET', '/_security/_authenticate')

    @property
    def options(self):
        return {'service': '', 'username': '', 'name': None, 'conn': None}

    @property
    def description(self):
        return 'Start Kerberos authentication flow'
