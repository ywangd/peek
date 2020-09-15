import os
from typing import Iterable
from unittest.mock import MagicMock

from prompt_toolkit.completion import CompleteEvent, Completion
from prompt_toolkit.document import Document

from peek import __file__ as package_root
from peek.completer import PeekCompleter
from peek.natives import EXPORTS

package_root = os.path.dirname(package_root)
kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')

mock_app = MagicMock(name='PeekApp')
mock_app.vm.functions = {k: v for k, v in EXPORTS.items() if callable(v)}
mock_app.config.as_bool.return_value = True
mock_app.batch_mode = False
config = {'kibana_dir': None}
mock_app.config.__getitem__ = MagicMock(side_effect=lambda x: config.get(x))

completer = PeekCompleter(mock_app)


def equivalent_completions(c0: Completion, c1: Completion):
    return c0.text == c1.text and c0.start_position == c1.start_position


def completions_has(cs: Iterable[Completion], *cc: Completion):
    if not os.path.exists(kibana_dir):
        return True

    actual = set((x.text, x.start_position) for x in cs)
    expected = set((x.text, x.start_position) for x in cc)
    ret = actual.issuperset(expected)
    if ret is False:
        print(f'actual: {actual!r} is not superset of {expected!r}')
    return ret


def no_completion(cs: Iterable[Completion]):
    if not os.path.exists(kibana_dir):
        return True

    actual = set((x.text, x.start_position) for x in cs)
    ret = len(actual) == 0
    if ret is False:
        print(f'actual: {actual!r} is not empty')
    return ret


def get_completions(document: Document):
    return completer.get_completions(document, CompleteEvent(True))


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
        Completion(text='save=', start_position=0),
        Completion(text='load=', start_position=0),
        Completion(text='remove=', start_position=0),
        Completion(text='@clear', start_position=0),
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
        get_completions(Document('session @s')),
        Completion(text='@save', start_position=-2),
    )

    assert completions_has(
        get_completions(Document('connection @r')),
        Completion(text='@remove', start_position=-2)
    )


def test_complete_option_name_will_not_be_in_value_place():
    assert no_completion(
        get_completions(Document('''connect hosts='''))
    )

    assert no_completion(
        get_completions(Document('''connect hosts=h'''))
    )

    assert no_completion(
        get_completions(Document('''get _search runas='''))
    )

    assert no_completion(
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
    assert no_completion(
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


def test_option_completion_will_not_appear_inside_payload():
    assert no_completion(
        get_completions(Document('''GET /
{
c
}''', 9))
    )


def test_payload_completion_will_not_appear_inside_option_value():
    assert no_completion(
        get_completions(Document('''GET _search headers={ "" }
{
""
}''', 23))
    )


def test_payload_completion_will_not_appear_inside_multi_line_option_value():
    assert no_completion(
        get_completions(Document('''GET _search headers={
""
}
{
""
}''', 23))
    )
