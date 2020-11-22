import os
from unittest.mock import MagicMock, patch, call

import pytest

from peek.connection import connect, EsClient, RefreshingEsClient, EsClientManager, DelegatingListener
from peek.errors import PeekError


def test_connect_default():
    mock_app = MagicMock(name='PeekApp')
    client = connect(mock_app)
    mock_app.input.assert_not_called()
    assert str(client) == 'http://localhost:9200'


def test_connect_will_prompt_password_when_no_password_is_found():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)

    client = connect(mock_app, **{
        'username': 'foo',
        'hosts': 'localhost:9201',
        'use_ssl': True,
    })
    mock_app.input.assert_called()
    assert str(client) == 'foo @ https://localhost:9201'


@patch.dict(os.environ, {'PEEK_PASSWORD': 'password'})
def test_connect_will_not_prompt_password_when_password_is_found_in_env():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)

    client = connect(mock_app, **{
        'username': 'foo',
        'name': 'my-connection'
    })

    mock_app.input.assert_not_called()
    assert str(client) == 'my-connection'


def test_connect_will_prompt_password_when_forced():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)

    connect(mock_app, **{
        'username': 'foo',
        'password': 'password',
        'force_prompt': True,
    })
    mock_app.input.assert_called()


def test_connect_will_fail_when_password_is_not_provided_and_prompt_is_not_allowed():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)

    with pytest.raises(PeekError) as e:
        connect(mock_app, **{
            'username': 'foo',
            'no_prompt': True,
        })
    assert 'Password is not found and password prompt is disabled' in str(e)


def test_connect_will_use_key_ring_when_configured():
    mock_keyring = MagicMock(return_value='password')
    with patch('peek.connection._keyring', mock_keyring):
        mock_app = MagicMock(name='PeekApp')
        mock_app.config.as_bool = MagicMock(return_value=True)

        connect(mock_app, **{
            'username': 'foo',
        })

    mock_keyring.assert_has_calls(
        [call('peek/localhost:9200/userpass', 'foo'),
         call('peek/localhost:9200/userpass', 'foo', 'password')])


def test_connect_has_highest_priority_for_api_key():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)

    client = connect(mock_app, **{
        'api_key': 'id:key',
        'token': 'some-token',
        'username': 'foo',
        'password': 'password',
    })

    assert str(client) == 'K-id @ http://localhost:9200'
    assert client.info()['auth'].startswith('ApiKey id')


def test_connect_has_second_priority_for_token():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)

    client = connect(mock_app, **{
        'token': 'some-token',
        'username': 'foo',
        'password': 'password',
    })

    assert str(client) == 'T-some-token @ http://localhost:9200'
    assert client.info()['auth'].startswith('Token some-token')


def test_connect_will_prefer_cloud_id():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)

    mock_es = MagicMock
    MockEs = MagicMock(return_value=mock_es)

    with patch('peek.connection.Elasticsearch', MockEs):
        client = connect(mock_app, **{
            'username': 'foo',
            'password': 'password',
            'cloud_id': 'my-cloud-id',
            'hosts': 'example.com:9200',
        })

    assert str(client) == 'foo @ my-cloud-id'
    assert client.hosts is None


def test_es_client_to_and_from_dict():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)
    client = connect(mock_app, **{
        'username': 'foo',
        'password': 'password',
        'hosts': 'example.com:9200',
        'use_ssl': True,
    })

    d = client.to_dict()
    assert d['password'] is None

    with patch.dict(os.environ, {'PEEK_PASSWORD': 'password'}):
        assert client.to_dict() == EsClient.from_dict(mock_app, d).to_dict()


def test_refreshing_es_client_to_and_from_dict():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)
    parent = connect(mock_app, **{
        'username': 'foo',
        'password': 'password',
        'hosts': 'example.com:9200',
        'use_ssl': True,
    })

    client = RefreshingEsClient(
        parent=parent,
        username='bar@example.com',
        access_token='access_token',
        refresh_token='refresh_token',
        expires_in=42,
        name='my-refreshing-client'
    )

    assert client.to_dict() == RefreshingEsClient.from_dict(client.to_dict()).to_dict()


@patch.dict(os.environ, {'PEEK_PASSWORD': 'password'})
def test_es_client_manager():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)

    on_add = MagicMock()
    on_set = MagicMock()
    on_remove = MagicMock()
    listener_0 = DelegatingListener(on_add=on_add, on_set=on_set, on_remove=on_remove)
    listener_1 = DelegatingListener(on_add=on_add, on_set=lambda m: False)
    listener_2 = DelegatingListener(on_add=on_add, on_set=on_set, on_remove=on_remove)
    es_client_manager = EsClientManager(listeners=[listener_0, listener_1, listener_2])
    local_admin_0 = EsClient(name='local-admin', hosts='localhost:9200', username='admin', password='password')
    local_foo_1 = EsClient(name='local-foo', hosts='localhost:9200', username='foo', password='password')
    local_bar_saml_2 = RefreshingEsClient(parent=local_admin_0, username='bar@example.com', access_token='access_token',
                                          refresh_token='refresh_token', expires_in=42, name='local-bar-saml')
    remote_admin_3 = EsClient(name='remote-admin', hosts='example.com:9200', username='elastic', password='password')
    remote_oidc_4 = RefreshingEsClient(parent=EsClient(name='removed', hosts='example.com:9200'), username='dangling',
                                       access_token='access_token', refresh_token='refresh_token', expires_in=42,
                                       name='remote-dangling-oidc')

    es_client_manager.add(local_admin_0)
    on_add.assert_has_calls([call(es_client_manager), call(es_client_manager), call(es_client_manager)])
    es_client_manager.add(local_foo_1)
    es_client_manager.add(local_bar_saml_2)
    es_client_manager.add(remote_admin_3)
    es_client_manager.add(remote_oidc_4)

    assert remote_oidc_4 == es_client_manager.current

    es_client_manager.set_current(2)
    on_set.assert_has_calls([call(es_client_manager)])
    assert local_bar_saml_2 == es_client_manager.current

    es_client_manager.set_current('remote-admin')
    assert remote_admin_3 == es_client_manager.current

    assert local_foo_1 == es_client_manager.get_client(1)
    assert local_foo_1 == es_client_manager.get_client('local-foo')
    assert remote_admin_3 == es_client_manager.get_client(None)  # same as get current

    d = es_client_manager.to_dict()
    assert d == {'_index_current': 3, '_clients': [
        {'name': 'local-admin', 'hosts': 'localhost:9200', 'cloud_id': None, 'username': 'admin', 'password': None,
         'use_ssl': False, 'verify_certs': False, 'assert_hostname': False, 'ca_certs': None, 'client_cert': None,
         'client_key': None, 'api_key': None, 'token': None, 'headers': None},
        {'name': 'local-foo', 'hosts': 'localhost:9200', 'cloud_id': None, 'username': 'foo', 'password': None,
         'use_ssl': False, 'verify_certs': False, 'assert_hostname': False, 'ca_certs': None, 'client_cert': None,
         'client_key': None, 'api_key': None, 'token': None, 'headers': None},
        {'name': 'local-bar-saml', 'username': 'bar@example.com', 'access_token': 'access_token',
         'refresh_token': 'refresh_token', 'expires_in': 42, 'parent': 0},
        {'name': 'remote-admin', 'hosts': 'example.com:9200', 'cloud_id': None, 'username': 'elastic', 'password': None,
         'use_ssl': False, 'verify_certs': False, 'assert_hostname': False, 'ca_certs': None, 'client_cert': None,
         'client_key': None, 'api_key': None, 'token': None, 'headers': None},
        {'name': 'remote-dangling-oidc', 'username': 'dangling', 'access_token': 'access_token',
         'refresh_token': 'refresh_token', 'expires_in': 42,
         'parent': {'name': 'removed', 'hosts': 'example.com:9200', 'cloud_id': None, 'username': None,
                    'password': None, 'use_ssl': False, 'verify_certs': False, 'assert_hostname': False,
                    'ca_certs': None, 'client_cert': None, 'client_key': None, 'api_key': None, 'token': None,
                    'headers': None}}]}

    new_manager = EsClientManager.from_dict(mock_app, d)

    clients = new_manager.clients()
    assert len(clients) == 5
    assert clients.index(new_manager.current) == 3

    assert d == new_manager.to_dict()

    es_client_manager.move_current_to(1)
    assert es_client_manager.current == remote_admin_3
    assert es_client_manager.get_client(1) == remote_admin_3

    es_client_manager.move_current_to(4)
    assert es_client_manager.current == remote_admin_3
    assert es_client_manager.get_client(4) == remote_admin_3

    removed = es_client_manager.get_client(1)
    es_client_manager.remove_client(1)
    on_remove.assert_has_calls([call(es_client_manager, removed), call(es_client_manager, removed)])
