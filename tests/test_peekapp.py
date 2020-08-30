#!/usr/bin/env python

"""Tests for `peek` package."""
import json
import os
from unittest.mock import patch, MagicMock

import pytest
from configobj import ConfigObj

from peek.common import AUTO_SAVE_NAME
from peek.peekapp import PeekApp


def test_multiple_stmts(config_obj):
    mock_history = MagicMock()
    MockHistory = MagicMock(return_value=mock_history)

    def get_config(_, extra_config):
        config_obj.merge(ConfigObj(extra_config))
        return config_obj

    text = """get abc

post abc/_doc
{ "foo":
         "bar"
}

conn foo=bar
get abc
"""
    nodes = []
    with patch('peek.peekapp.get_config', get_config), patch('peek.peekapp.SqLiteHistory', MockHistory):
        peek = PeekApp(batch_mode=True, extra_config_options=('log_level=None', 'use_keyring=False'))
        peek.execute_node = lambda stmt: nodes.append(stmt)
        peek.process_input(text)

    for n in nodes:
        print(n)

    assert [str(n) for n in nodes] == [
        r'''get abc {}
''',
        r'''post abc/_doc {}
{"foo":"bar"}
''',
        r'''conn [] [] {foo:bar}
''',
        r'''get abc {}
''',
    ]


@patch('peek.peekapp.PromptSession', MagicMock())
def test_app_will_not_auto_load_session_by_default(config_obj):
    mock_history = MagicMock()
    MockHistory = MagicMock(return_value=mock_history)

    def get_config(_, extra_config):
        config_obj.merge(ConfigObj(extra_config))
        return config_obj

    with patch('peek.peekapp.get_config', get_config), patch('peek.peekapp.SqLiteHistory', MockHistory):
        PeekApp(extra_config_options=('log_level=None', 'use_keyring=False'))

    mock_history.load_session.assert_not_called()


@patch('peek.peekapp.PromptSession', MagicMock())
def test_app_will_not_auto_load_session_if_connection_is_specified_on_cli(config_obj):
    config_obj['auto_load_session'] = True
    mock_history = MagicMock()
    MockHistory = MagicMock(return_value=mock_history)

    def get_config(_, extra_config):
        config_obj.merge(ConfigObj(extra_config))
        return config_obj

    class MockCliNs:

        def __init__(self):
            self.username = 'foo'
            self.password = 'password'

    with patch('peek.peekapp.get_config', get_config), patch('peek.peekapp.SqLiteHistory', MockHistory):
        PeekApp(extra_config_options=('log_level=None', 'use_keyring=False'), cli_ns=MockCliNs())

    mock_history.load_session.assert_not_called()


@patch('peek.peekapp.PromptSession', MagicMock())
def test_app_will_not_auto_load_session_if_connection_is_specified_in_rcfile(config_obj):
    config_obj['auto_load_session'] = True
    mock_history = MagicMock()
    MockHistory = MagicMock(return_value=mock_history)

    def get_config(_, extra_config):
        config_obj.merge(ConfigObj({
            'connection': {
                'username': 'foo',
                'password': 'password',
            }
        }))
        config_obj.merge(ConfigObj(extra_config))
        return config_obj

    with patch('peek.peekapp.get_config', get_config), patch('peek.peekapp.SqLiteHistory', MockHistory):
        PeekApp(extra_config_options=('log_level=None', 'use_keyring=False'))

    mock_history.load_session.assert_not_called()


@patch('peek.peekapp.PromptSession', MagicMock())
def test_app_will_auto_load_session_if_nothing_is_overriding_it(config_obj):
    config_obj['auto_load_session'] = True
    mock_history = MagicMock()
    mock_history.load_session = MagicMock(return_value=json.dumps(
        {'_index_current': 0, '_clients': [{'username': 'foo', 'password': 'bar', 'hosts': 'localhost:9200'}]}))
    MockHistory = MagicMock(return_value=mock_history)

    def get_config(_, extra_config):
        config_obj.merge(ConfigObj(extra_config))
        return config_obj

    with patch('peek.peekapp.get_config', get_config), patch('peek.peekapp.SqLiteHistory', MockHistory):
        PeekApp(extra_config_options=('log_level=None', 'use_keyring=False'))

    mock_history.load_session.assert_called_with(AUTO_SAVE_NAME)


@patch('peek.peekapp.PromptSession', MagicMock())
def test_app_will_auto_save_session(config_obj):
    mock_history = MagicMock()
    MockHistory = MagicMock(return_value=mock_history)

    def get_config(_, extra_config):
        config_obj.merge(ConfigObj(extra_config))
        return config_obj

    with patch('peek.peekapp.get_config', get_config), patch('peek.peekapp.SqLiteHistory', MockHistory):
        app = PeekApp(extra_config_options=('log_level=None', 'use_keyring=False'))
        app.signal_exit()
        app.run()

    mock_history.save_session.assert_called_once()


@patch('peek.peekapp.PromptSession', MagicMock())
def test_app_will_not_auto_save_session_when_disabled(config_obj):
    config_obj['auto_save_session'] = False
    mock_history = MagicMock()
    MockHistory = MagicMock(return_value=mock_history)

    def get_config(_, extra_config):
        config_obj.merge(ConfigObj(extra_config))
        return config_obj

    with patch('peek.peekapp.get_config', get_config), patch('peek.peekapp.SqLiteHistory', MockHistory):
        app = PeekApp(extra_config_options=('log_level=None', 'use_keyring=False'))
        app.signal_exit()
        app.run()

    mock_history.save_session.assert_not_called()


@pytest.fixture
def config_obj():
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    package_config_file = os.path.join(package_root, 'peekrc')
    return ConfigObj(package_config_file)
