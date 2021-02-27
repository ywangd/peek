import json
import os
from unittest.mock import MagicMock, patch, call

import pytest
from configobj import ConfigObj

from peek.connection import ConnectFunc
from peek.natives import ConnectionFunc, SessionFunc
from peek.peekapp import PeekApp

mock_history = MagicMock()
MockHistory = MagicMock(return_value=mock_history)


@pytest.fixture
def peek_app():
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    package_config_file = os.path.join(package_root, 'peekrc')
    config_obj = ConfigObj(package_config_file)

    def get_config(_, extra_config):
        config_obj.merge(ConfigObj(extra_config))
        return config_obj

    class MockCliNs:

        def __init__(self):
            self.username = 'foo'
            self.password = 'password'
            self.zero_connection = False

    with patch('peek.peekapp.PromptSession', MagicMock()), \
         patch('peek.peekapp.get_config', get_config), \
         patch('peek.peekapp.SqLiteHistory', MockHistory):
        return PeekApp(extra_config_options=('log_level=None', 'use_keyring=False'), cli_ns=MockCliNs())


@patch.dict(os.environ, {'PEEK_PASSWORD': 'password'})
def test_connection_related_funcs(peek_app):
    connect_f = ConnectFunc()
    assert '*  [1] bar @ https://localhost:9200' in connect_f(
        peek_app, username='bar', password='password', use_ssl=True)
    assert '*  [2] K-id @ http://example.com:9200' in connect_f(
        peek_app, api_key='id:key', hosts='example.com:9200')
    assert '*  [3] token-auth' in connect_f(
        peek_app, token='access_token', name='token-auth')

    connection_f = ConnectionFunc()
    assert connection_f(peek_app) == '''   [0] foo @ http://localhost:9200
   [1] bar @ https://localhost:9200
   [2] K-id @ http://example.com:9200
*  [3] token-auth'''

    assert connection_f(peek_app, 1) == '''   [0] foo @ http://localhost:9200
*  [1] bar @ https://localhost:9200
   [2] K-id @ http://example.com:9200
   [3] token-auth'''

    session_f = SessionFunc()
    assert "Session save as: '__default__'" == session_f(peek_app, **{'@': ['save']})
    mock_history.save_session.assert_called_with('__default__', json.dumps(peek_app.es_client_manager.to_dict()))
    mock_history.load_session = MagicMock(return_value=json.dumps(peek_app.es_client_manager.to_dict()))

    assert connection_f(peek_app, rename='local-bar') == '''   [0] foo @ http://localhost:9200
*  [1] local-bar
   [2] K-id @ http://example.com:9200
   [3] token-auth'''

    assert connection_f(peek_app, **{'@': ['info']}) == {
        'name': 'local-bar', 'hosts': 'localhost:9200',
        'cloud_id': None, 'auth': 'Username bar', 'use_ssl': True,
        'verify_certs': False, 'ca_certs': None, 'client_cert': None,
        'client_key': None, 'headers': None}

    assert connection_f(peek_app, remove=0) == '''*  [0] local-bar
   [1] K-id @ http://example.com:9200
   [2] token-auth'''

    assert connection_f(peek_app, 'token-auth') == '''   [0] local-bar
   [1] K-id @ http://example.com:9200
*  [2] token-auth'''

    assert connection_f(peek_app, keep=1) == '''*  [0] K-id @ http://example.com:9200'''

    assert session_f(peek_app, **{'@': ['load']}) == '''   [0] foo @ http://localhost:9200
*  [1] bar @ https://localhost:9200
   [2] K-id @ http://example.com:9200
   [3] token-auth'''

    assert connection_f(peek_app, move=0) == '''*  [0] bar @ https://localhost:9200
   [1] foo @ http://localhost:9200
   [2] K-id @ http://example.com:9200
   [3] token-auth'''

    assert connection_f(peek_app, move=3) == '''   [0] foo @ http://localhost:9200
   [1] K-id @ http://example.com:9200
   [2] token-auth
*  [3] bar @ https://localhost:9200'''

    assert connection_f(peek_app, move=3) == '''   [0] foo @ http://localhost:9200
   [1] K-id @ http://example.com:9200
   [2] token-auth
*  [3] bar @ https://localhost:9200'''


def test_connect_with_failed_test_will_not_be_added(peek_app):
    peek_app.display = MagicMock()
    peek_app.display.error = MagicMock()
    mock_es = MagicMock()

    error = RuntimeError('Should fail')

    def mock_perform_request(*args, **kwargs):
        raise error

    mock_es.transport.perform_request = MagicMock(side_effect=mock_perform_request)
    MockEs = MagicMock(return_value=mock_es)
    with patch('peek.connection.Elasticsearch', MockEs):
        connect_f = ConnectFunc()
        assert connect_f(peek_app, username=None, test=True) is None
        peek_app.display.error.assert_called_with(error)
        assert str(peek_app.es_client_manager) == '*  [0] foo @ http://localhost:9200'


def test_echo(peek_app):
    echo_f = peek_app.vm.functions['echo']

    assert echo_f(peek_app, 0) == '0'
    assert echo_f(peek_app, 1) == '1'
    assert echo_f(peek_app, True) == 'true'
    assert echo_f(peek_app, False) == 'false'
    assert echo_f(peek_app, None) == 'null'
    assert echo_f(peek_app, 'hello') == '"hello"'
    assert echo_f(peek_app, echo_f) == '"<PeekFunction echo>"'
    assert echo_f(peek_app, {'foo': [True, False, None, 'bar', echo_f]}) == \
           '{"foo":[true,false,null,"bar","<PeekFunction echo>"]}'
    assert echo_f(peek_app, {}, [], 42) == '{} [] 42'


@patch.dict(os.environ, {'PEEK_PASSWORD': 'password'})
def test_reset(peek_app):
    old_vm = peek_app.vm
    peek_app.display.info = MagicMock()
    peek_app.completer.init_api_specs = MagicMock()

    peek_app.process_input('let foo = 42')
    assert peek_app.vm.get_value('foo') == 42

    peek_app.process_input('connection rename="c0"')
    peek_app.process_input('connect name="c1"')
    peek_app.process_input('connect name="c2"')
    assert len(peek_app.es_client_manager.clients()) == 3

    peek_app.process_input('reset')
    assert len(peek_app.es_client_manager.clients()) == 1
    assert str(peek_app.es_client_manager) == '*  [0] foo @ http://localhost:9200'
    assert peek_app.vm is not old_vm
    peek_app.completer.init_api_specs.assert_called_once()


def test_randint(peek_app):
    peek_app.display.info = MagicMock()
    peek_app.process_input('let foo = randint(1,2)')
    assert peek_app.vm.get_value('foo') == 1

    peek_app.process_input('let bar = randint(1,10)')
    assert 1 <= peek_app.vm.get_value('bar') < 10

    peek_app.process_input('let fiz = randint(10)')
    assert 0 <= peek_app.vm.get_value('bar') < 10

    peek_app.process_input('let fiz = randint()')
    assert 0 <= peek_app.vm.get_value('bar') < 100


def test_getenv(peek_app):
    peek_app.display.info = MagicMock()
    mock_os_getenv = MagicMock()
    with patch('os.getenv', mock_os_getenv):
        peek_app.process_input('let a = getenv("CODE")')
        peek_app.process_input('let b = getenv("FOO")')
    mock_os_getenv.assert_has_calls([call("CODE", ''), call("FOO", '')])


def test_version(peek_app):
    peek_app.display.info = MagicMock()
    peek_app.process_input('let v = version()')
    value = peek_app.vm.get_value('v')
    assert 'Peek' in value
    from peek import __version__
    assert f'v{__version__}' in value
    assert 'elasticsearch-py' in value
