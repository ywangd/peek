import os
from unittest.mock import MagicMock, call

import pytest
from configobj import ConfigObj

from peek.errors import PeekError
from peek.parser import PeekParser
from peek.vm import PeekVM, _maybe_encode_date_math


@pytest.fixture
def peek_vm():
    mock_app = MagicMock(name='PeekApp')

    vm = PeekVM(mock_app)
    mock_app.vm = vm
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    package_config_file = os.path.join(package_root, 'peekrc')

    mock_app.config = ConfigObj(package_config_file)
    mock_app.parser = PeekParser()
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


def test_str_and_number(peek_vm, parser):
    peek_vm.execute_node(parser.parse('debug "hello" + 42')[0])
    assert_called_with(peek_vm, 'hello42')


def test_peek_vm_func(peek_vm, parser):
    peek_vm.execute_node(parser.parse('debug echo(0 1 2)')[0])
    assert_called_with(peek_vm, '0 1 2')
    peek_vm.execute_node(parser.parse('debug [echo].0(0 1 2)')[0])
    assert_called_with(peek_vm, '0 1 2')
    peek_vm.execute_node(parser.parse('debug echo(42) + "hello"')[0])
    assert_called_with(peek_vm, '42hello')


def test_peek_vm_es_api_call(peek_vm, parser):
    peek_vm.execute_node(parser.parse('GET /')[0])
    peek_vm.app.display.info.assert_called_with(
        '{"foo": [1, 2, 3, 4], "bar": {"hello": [42, "world"]}}', header_text='')
    assert peek_vm.get_value('_') == {'foo': [1, 2, 3, 4], 'bar': {'hello': [42, 'world']}}
    peek_vm.execute_node(parser.parse('debug _."bar".@hello.1')[0])
    assert_called_with(peek_vm, 'world')
    peek_vm.execute_node(parser.parse('GET ("foo" + "/" + 42)')[0])
    peek_vm.app.es_client_manager.current.perform_request.assert_called_with('GET', '/foo/42', None, headers=None)
    peek_vm.execute_node(parser.parse('PUT /<my-index-{now/d}>')[0])
    peek_vm.app.es_client_manager.current.perform_request.assert_called_with('PUT', '/%3Cmy-index-%7Bnow%2Fd%7D%3E',
                                                                             None, headers=None)


def test_es_api_call_quiet(peek_vm, parser):
    peek_vm.execute_node(parser.parse('GET / quiet=true')[0])
    peek_vm.app.display.info.assert_not_called()
    assert peek_vm.get_value('_') == {'foo': [1, 2, 3, 4], 'bar': {'hello': [42, 'world']}}


def test_peek_vm_let(peek_vm, parser):
    peek_vm.execute_node(parser.parse('let foo={"a": [3, 4, 5]} bar=["hello", 42] c="world"')[0])
    peek_vm.execute_node(parser.parse('debug foo bar c')[0])
    assert_called_with(peek_vm, {"a": [3, 4, 5]}, ["hello", 42], "world")
    peek_vm.execute_node(parser.parse('let foo.@a.1 = 42')[0])
    peek_vm.execute_node(parser.parse('debug foo')[0])
    assert_called_with(peek_vm, {"a": [3, 42, 5]})


def test_invalid_let(peek_vm, parser):
    peek_vm.execute_node(parser.parse('let foo=[[1, 2], echo]')[0])
    with pytest.raises(PeekError) as e:
        peek_vm.execute_node(parser.parse('let foo.0."x" = 42')[0])
    assert "Invalid lhs for assignment: ['foo', 0, 'x']" in str(e.value)

    with pytest.raises(PeekError) as e:
        peek_vm.execute_node(parser.parse('let foo.1."x" = 42')[0])
    assert "Invalid lhs for assignment: ['foo', 1, 'x']" in str(e.value)


def test_for_in(peek_vm, parser):
    peek_vm.execute_node(parser.parse('''for x in [1, 2, 3] {
    let y = x
    debug x
}''')[0])

    assert peek_vm.get_value('y') == 3
    peek_vm.context['debug'].assert_has_calls(
        [call(peek_vm.app, 1), call(peek_vm.app, 2), call(peek_vm.app, 3)])


def test_payload_file(peek_vm, parser):
    peek_vm.execute_node(parser.parse('''let data = {
    "category": "click",
    "tags": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
}''')[0])

    payload_file = os.path.join(os.path.dirname(__file__), 'payload.json')

    peek_vm.execute_node(parser.parse('''PUT _bulk
@{}'''.format(payload_file))[0])

    peek_vm.app.es_client_manager.current.perform_request.assert_called_with(
        'PUT',
        '/_bulk',
        '{"index": {"_index": "index", "_id": "1"}}\n'
        '{"category": "click", "tag": 1}\n'
        '{"index": {"_index": "index", "_id": "2"}}\n'
        '{"category": "click", "tag": 2}\n'
        '{"index": {"_index": "index", "_id": "3"}}\n'
        '{"category": "click", "tag": 3}\n'
        '{"index": {"_index": "index", "_id": "4"}}\n'
        '{"category": "click", "tag": 4}\n'
        '{"index": {"_index": "index", "_id": "5"}}\n'
        '{"category": "click", "tag": 5}\n'
        '{"index": {"_index": "index", "_id": "6"}}\n'
        '{"category": "click", "tag": 6}\n'
        '{"index": {"_index": "index", "_id": "7"}}\n'
        '{"category": "click", "tag": 7}\n'
        '{"index": {"_index": "index", "_id": "8"}}\n'
        '{"category": "click", "tag": 8}\n'
        '{"index": {"_index": "index", "_id": "9"}}\n'
        '{"category": "click", "tag": 9}\n'
        '{"index": {"_index": "index", "_id": "10"}}\n'
        '{"category": "click", "tag": 10}\n',
        headers=None,
    )


def test_warning_header(peek_vm, parser):
    import elasticsearch
    if elasticsearch.__version__ < (7, 7, 0):
        return

    import warnings
    from elasticsearch.exceptions import ElasticsearchDeprecationWarning

    peek_vm.app.display.warn = MagicMock(return_value=None)
    es_client = peek_vm.app.es_client_manager.get_client()

    message = 'This is a warning message'

    def perform_request(*args, **kwargs):
        warnings.warn(message, ElasticsearchDeprecationWarning)

    es_client.perform_request = MagicMock(side_effect=perform_request)

    peek_vm.execute_node(parser.parse('GET /')[0])
    peek_vm.app.display.warn.assert_called_with(message)


def test_maybe_encode_date_math():
    assert _maybe_encode_date_math('/<my-index-{now/d}>') == '/%3Cmy-index-%7Bnow%2Fd%7D%3E'
    assert (_maybe_encode_date_math(
        '/<logstash-{now/d-2d}>,<logstash-{now/d-1d}>,<logstash-{now/d}>/_search') ==
            '/%3Clogstash-%7Bnow%2Fd-2d%7D%3E,%3Clogstash-%7Bnow%2Fd-1d%7D%3E,%3Clogstash-%7Bnow%2Fd%7D%3E/_search')
