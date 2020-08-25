from unittest.mock import MagicMock

import pytest
from configobj import ConfigObj

from peek.parser import PeekParser
from peek.vm import PeekVM


@pytest.fixture
def peek_vm():
    mock_app = MagicMock(name='PeekApp')

    vm = PeekVM(mock_app)
    mock_app.vm = vm
    mock_app.config = ConfigObj()
    vm.context['debug'] = MagicMock(return_value=None)
    mock_app.display.info = MagicMock(return_value=None)
    mock_app.display.error = MagicMock(return_value=None)
    es_client = MagicMock(name='EsClient')
    mock_app.es_client_manager.current = es_client
    mock_app.es_client_manager.get_client = MagicMock(return_value=es_client)
    es_client.perform_request = MagicMock(return_value='{"foo": [1, 2, 3, 4], "bar": {"hello": [42, "world"]}}')
    return vm


@pytest.fixture
def parser():
    return PeekParser()


def assert_called_with(vm, *args, **kwargs):
    vm.context['debug'].assert_called_with(vm.app, *args, **kwargs)


def test_peek_vm_data_types(peek_vm, parser):
    peek_vm.execute_node(parser.parse('debug "42" 42 true 4.2 [4, 2] {4:2} @a42 foo="bar"')[0])
    assert_called_with(peek_vm, '42', 42, True, 4.2, [4, 2], {4: 2}, **{'@': ['a42'], 'foo': 'bar'})


def test_peek_vm_expr(peek_vm, parser):
    peek_vm.execute_node(parser.parse('debug 1 + 2 * 3 + (5-1) {"a": 42}.@a [4, 2, 1].1 foo="a" + "b"')[0])
    assert_called_with(peek_vm, 11, 42, 2, **{'foo': 'ab'})


def test_peek_vm_es_api_call(peek_vm, parser):
    peek_vm.execute_node(parser.parse('GET /')[0])
    assert peek_vm.get_value('_') == {'foo': [1, 2, 3, 4], 'bar': {'hello': [42, 'world']}}
    peek_vm.execute_node(parser.parse('debug _."bar".@hello.1')[0])
    assert_called_with(peek_vm, 'world')


def test_peek_vm_let(peek_vm, parser):
    peek_vm.execute_node(parser.parse('let foo={"a": [3, 4, 5]} bar=["hello", 42] c="world"')[0])
    peek_vm.execute_node(parser.parse('debug foo bar c')[0])
    assert_called_with(peek_vm, {"a": [3, 4, 5]}, ["hello", 42], "world")
    peek_vm.execute_node(parser.parse('let foo.@a.1 = 42')[0])
    peek_vm.execute_node(parser.parse('debug foo')[0])
    assert_called_with(peek_vm, {"a": [3, 42, 5]})
