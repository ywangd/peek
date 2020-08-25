import os
from typing import Iterable
from unittest.mock import MagicMock

from prompt_toolkit.completion import CompleteEvent, Completion
from prompt_toolkit.document import Document
from pygments.token import Literal

from peek.common import PeekToken
from peek.completer import load_specs, PeekCompleter, find_beginning_token, matchable_specs
from peek.lexers import HttpMethod, FuncName, BlankLine
from peek.natives import EXPORTS

mock_app = MagicMock(name='PeekApp')
mock_app.vm.functions = {k: v for k, v in EXPORTS.items() if callable(v)}
mock_app.config.as_bool.return_value = True

completer = PeekCompleter(mock_app)


def equivalent_completions(c0: Completion, c1: Completion):
    return c0.text == c1.text and c0.start_position == c1.start_position


def completions_has(cs: Iterable[Completion], *cc: Completion):
    if not completer.specs:
        return True

    actual = set((x.text, x.start_position) for x in cs)
    expected = set((x.text, x.start_position) for x in cc)
    if len(expected) == 0:
        ret = len(actual) == 0
    else:
        ret = actual.issuperset(expected)
    if ret is False:
        print(f'actual: {actual!r} is not superset of {expected!r}')
    return ret


def get_completions(document: Document):
    return completer.get_completions(document, CompleteEvent(True))


def test_load_specs():
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')
    specs = load_specs(kibana_dir)
    # Skip the test if no specs are found
    if not specs:
        return

    # Make sure loading and merging work
    print(specs['indices.create']['data_autocomplete_rules'])
    print(specs['security.put_user']['data_autocomplete_rules'])

    next(matchable_specs('POST', ['_security', 'api_key'], specs))

    next(matchable_specs('POST', ['_security', 'oauth2', 'token'], specs,
                         required_field='data_autocomplete_rules'))


def test_find_beginning_token():
    tokens = [
        PeekToken(index=0, ttype=HttpMethod, value='get'),
        PeekToken(index=4, ttype=Literal, value='abc'),
        PeekToken(index=8, ttype=FuncName, value='ge')
    ]
    i, t = find_beginning_token(tokens)
    assert i == 2

    tokens = [
        PeekToken(index=0, ttype=FuncName, value='connect'),
        PeekToken(index=7, ttype=BlankLine, value='\n'),
        PeekToken(index=8, ttype=FuncName, value='session')
    ]
    i, t = find_beginning_token(tokens)
    assert i == 2


def test_complete_http_method_and_func_name():
    assert completions_has(
        get_completions(Document('po')),
        Completion(text='POST', start_position=-2),
    )

    assert completions_has(
        get_completions(Document('''get abc
ge''')),
        Completion(text='GET', start_position=-2),
    )

    assert completions_has(
        get_completions(Document('con')),
        Completion(text='config', start_position=-3),
        Completion(text='connect', start_position=-3),
    )

    assert completions_has(
        get_completions(Document('''config
sa''')),
        Completion(text='saml_authenticate', start_position=-2),
    )


def test_complete_func_option_name():
    assert completions_has(
        get_completions(Document('connect ')),
        Completion(text='hosts=', start_position=0),
        Completion(text='api_key=', start_position=0),
    )

    assert completions_has(
        get_completions(Document('''connect
session ''')),
        Completion(text='current=', start_position=0),
        Completion(text='remove=', start_position=0),
        Completion(text='@info', start_position=0),
    )


def test_complete_func_option_name_with_partial():
    assert completions_has(
        get_completions(Document('connect user')),
        Completion(text='username=', start_position=-4),
    )

    assert completions_has(
        get_completions(Document('''config
saml_authenticate r''')),
        Completion(text='realm=', start_position=-1),
    )

    assert completions_has(
        get_completions(Document('session @r')),
        Completion(text='@remove', start_position=-2),
    )


def test_complete_option_name_should_not_be_in_value_place():
    assert completions_has(
        get_completions(Document('''connect hosts='''))
    )

    assert completions_has(
        get_completions(Document('''connect hosts=h'''))
    )

    assert completions_has(
        get_completions(Document('''get _search runas='''))
    )

    assert completions_has(
        get_completions(Document('''get _search runas=r'''))
    )


def test_complete_http_path():
    assert completions_has(
        get_completions(Document('get _secapi')),
        Completion(text='_security/api_key', start_position=-7),
        Completion(text='_security/role_mapping', start_position=-7),
    )

    assert completions_has(
        get_completions(Document('get _security/api_key?')),
        Completion(text='name', start_position=0),
        Completion(text='realm_name', start_position=0),
    )

    assert completions_has(
        get_completions(Document('get _security/api_key?o')),
        Completion(text='owner', start_position=-1),
    )

    assert completions_has(
        get_completions(Document('get _security/api_key?owner=')),
        Completion(text='true', start_position=0),
    )

    assert completions_has(
        get_completions(Document('post _security/api_key?refresh=')),
        Completion(text='wait_for', start_position=0),
    )

    assert completions_has(
        get_completions(Document('''get _security/api_key
post token''')),
        Completion(text='_security/oauth2/token', start_position=-5),
    )


def test_complete_http_options():
    assert completions_has(
        get_completions(Document('get _search ')),
        Completion(text='conn=', start_position=0),
        Completion(text='runas=', start_position=0),
    )

    assert completions_has(
        get_completions(Document('get _search r')),
        Completion(text='runas=', start_position=-1),
    )

    assert completions_has(
        get_completions(Document('''get _search
get _cluster/health c''')),
        Completion(text='conn=', start_position=-1),
    )

    assert len(list(get_completions(Document('''post _security/api_key
{"role_descriptors": }''', 44)))) == 0


def test_not_complete_http_options():
    assert len(list(get_completions(Document('''POST _security/oauth2/token
''')))) == 0


def test_not_complete_http_path():
    assert completions_has(
        get_completions(Document('''get
''')))


def test_payload_completion_000():
    assert completions_has(
        get_completions(Document('''POST _security/api_key
{""}''', 25)),
        Completion(text="role_descriptors", start_position=0),
    )


def test_payload_completion_001():
    assert completions_has(
        get_completions(Document('''POST _security/api_key
{
  "role_descriptors": {
    "role_name": {
      "indices": [
        {""}
      ]
    }
  }
}''', 97)),
        Completion(text="field_security", start_position=0),
    )


def test_payload_completion_002():
    assert completions_has(
        get_completions(Document('''POST _security/api_key
{
  "role_descriptors": {
    "role_name": {
      "indices": [
        {"field_security": ""}
      ]
    }
  },
  "n"
}''', 141)),
        Completion(text="name", start_position=-1),
    )


def test_payload_completion_003():
    assert completions_has(
        get_completions(Document('''POST _security/api_key
{
  "role_descriptors": {
    "role_name": {
      "cluster": [],
      ""
    }
  }
}''', 97)),
        Completion(text="indices"),
    )


def test_payload_completion_004():
    assert completions_has(
        get_completions(Document('''POST _security/oauth2/token
{""}''', 30)),
        Completion(text="scope", start_position=0),
    )


def test_file_payload_completion():
    f = os.listdir('.')[0]
    assert completions_has(
        get_completions(Document('''get /
@''')),
        Completion(text=f, start_position=0)
    )
