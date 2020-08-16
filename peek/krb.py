import json
import logging

from peek.connection import EsClient, RefreshingEsClient
from peek.errors import PeekError

_logger = logging.getLogger(__name__)


def krb_authenticate(es_client: EsClient, service=None, **options):
    _logger.debug(f'Connection with Kerberos: {service}')
    if service is None:
        raise PeekError(f'Service is required for kerberos authentication')
    import kerberos
    username = options.get('username', None)
    result, context = kerberos.authGSSClientInit(service, principal=username)
    result = kerberos.authGSSClientStep(context, '')
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
        auth_response['expires_in'])
