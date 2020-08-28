import os
from unittest.mock import MagicMock, patch, call

import pytest

from peek.connection import connect, EsClient, RefreshingEsClient
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
        'password': 'password,'
    })

    assert str(client) == 'K-id @ http://localhost:9200'
    assert client.info()['auth'].startswith('ApiKey id')


def test_connect_has_second_priority_for_token():
    mock_app = MagicMock(name='PeekApp')
    mock_app.config.as_bool = MagicMock(return_value=False)

    client = connect(mock_app, **{
        'token': 'some-token',
        'username': 'foo',
        'password': 'password,'
    })

    assert str(client) == 'T-some-token @ http://localhost:9200'
    assert client.info()['auth'].startswith('Token some-token')


def test_es_client_to_and_from_dict():
    mock_app = MagicMock(name='PeekApp')
    client = connect(mock_app, **{
        'username': 'foo',
        'password': 'password',
        'hosts': 'example.com:9200',
        'use_ssl': True,
    })

    d = client.to_dict()
    assert d['password'] is None
    d['password'] = 'password'
    assert client.to_dict() == EsClient.from_dict(d).to_dict()


def test_refreshing_es_client_to_and_from_dict():
    mock_app = MagicMock(name='PeekApp')
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
