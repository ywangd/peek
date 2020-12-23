import os
from typing import Iterable
from unittest.mock import MagicMock

from configobj import ConfigObj
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
config = {
    'kibana_dir': kibana_dir,
    'load_api_specs': True,
    'build_extended_api_specs': True,
    'cache_extended_api_specs': False,
}
mock_app.config = ConfigObj(config)

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


def completions_has_no(cs: Iterable[Completion], *cc: Completion):
    if not os.path.exists(kibana_dir):
        return True
    actual = set((x.text, x.start_position) for x in cs)
    exclude = set((c.text, c.start_position) for c in cc)
    ret = actual.isdisjoint(exclude)
    if ret is False:
        print(f'actual: {actual!r} has overlap with {exclude!r}')
    return ret


def completions_equal(cs: Iterable[Completion], *cc: Completion):
    if not os.path.exists(kibana_dir):
        return True

    actual = set((x.text, x.start_position) for x in cs)
    expected = set((x.text, x.start_position) for x in cc)
    ret = len(actual.difference(expected)) == 0
    if ret is False:
        print(f'actual: {actual!r} is not equal to {expected!r}')
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
        get_completions(Document('hea')),
        Completion(text='HEAD', start_position=-3),
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
        Completion(text='hosts='),
        Completion(text='api_key='),
    )

    assert completions_has(
        get_completions(Document('''connect
session ''')),
        Completion(text='save='),
        Completion(text='load='),
        Completion(text='remove='),
        Completion(text='@clear'),
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
        Completion(text='name'),
        Completion(text='realm_name'),
    )

    assert completions_has(
        get_completions(Document('get _security/api_key?o')),
        Completion(text='owner', start_position=-1),
    )

    assert completions_has(
        get_completions(Document('get _security/api_key?owner=')),
        Completion(text='true'),
    )

    assert completions_has(
        get_completions(Document('post _security/api_key?refresh=')),
        Completion(text='wait_for'),
    )

    assert completions_has(
        get_completions(Document('''get _security/api_key
post token''')),
        Completion(text='_security/oauth2/token', start_position=-5),
    )


def test_complete_http_options():
    assert completions_has(
        get_completions(Document('get _search ')),
        Completion(text='conn='),
        Completion(text='runas='),
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


def test_complete_payload_value():
    assert completions_has(
        get_completions(Document('''post _security/api_key
{"role_descriptors": }''', 44)),
        Completion(text='{}'),
    )


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
        Completion(text="role_descriptors"),
    )

    assert completions_has(
        get_completions(Document('''POST _security/api_key?refresh=wait_for
{""}''', 42)),
        Completion(text="role_descriptors"),
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
        Completion(text="field_security"),
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
        Completion(text="scope"),
    )


def test_file_payload_completion():
    f = os.listdir('.')[0]
    assert completions_has(
        get_completions(Document('''get /
@''')),
        Completion(text=f)
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


def test_payload_key_completion_will_not_appear_in_value_position():
    completions = list(get_completions(Document('''PUT _security/api_key
{
  "name":
}''', 33)))
    assert completions_has(
        completions,
        Completion('""')
    )
    assert completions_has_no(completions, Completion('name'))


def test_payload_key_completion_works_within_array():
    assert completions_has(
        get_completions(Document('''PUT _security/api_key
{"role_descriptors":{"role_name":{"indices":[{""}]}}}
''', 69)),
        Completion(text='names'),
        Completion(text='field_security'),
    )


def test_payload_key_completion_will_retry_with_global():
    assert completions_has(
        get_completions(Document('''GET _search
{
  "aggs": {
    "NAME": {
      ""
    }
  },
}''', 47)),
        Completion(text='adjacency_matrix'),
        Completion(text='diversified_sampler'),
    )


def test_payload_key_completion_will_work_inside_template():
    assert completions_has(
        get_completions(Document('''GET _search
{
  "script_fields": {
    ""
  }
}''', 40)),
        Completion(text='FIELD')
    )


def test_payload_key_completion_will_work_inside_template_but_not_override_existing_candidates():
    assert completions_equal(
        get_completions(Document('''GET _security/user/_has_privileges
{
  "application": {
    "app"
  },
}''', 64)),
        Completion(text='application', start_position=-3)
    )


def test_payload_key_completion_has_special_handling_for_empty_script_key():
    assert completions_has(
        get_completions(Document('''GET _search
{
  "script_fields": {
    "FIELD": {
      "script": {
        ""
      }
    }
  },
}
''', 77)),
        Completion('source'),
        Completion('id'),
        Completion('lang'),
        Completion('params'),
    )


def test_payload_key_completion_will_work_with_relative_scope_link():
    assert completions_has(
        get_completions(Document('''GET _search
{"query":{"bool":{"filter":[{"and":{"filters":[{
  ""
}]}}]}}}''', 64)),
        Completion(text='and'),
        Completion(text='bool'),
        Completion(text='exists'),
        Completion(text='ids'),
        Completion(text='limit'),
        Completion(text='geo_bounding_box'),
    )

    assert completions_has(
        get_completions(Document('''GET _search
{"query":{"span_near":{"clauses":[{
  ""
}],"slop":12,"in_order":false}}}
''', 51)),
        Completion(text='span_near'),
        Completion(text='span_first'),
        Completion(text='span_or'),
        Completion(text='span_containing'),
    )


def test_payload_value_completion_010():
    assert completions_has(
        get_completions(Document('''PUT _security/api_key
{
  "role_descriptors": {
    "role_name": \n},
}''', 64)),
        Completion(text='{}')
    )

    assert completions_has(
        get_completions(Document('''PUT _security/api_key
{
  "role_descriptors": {
    "role_name": \n},
}''', 65)),
        Completion(text='{}')
    )


def test_payload_value_completion_050():
    assert completions_has(
        get_completions(Document('''PUT _security/api_key
{
  "role_descriptors": {
    "role_name": {
      "indices":
    },
  },
}''', 83)),
        Completion(text='[{}]')
    )

    assert completions_has(
        get_completions(Document('''PUT _security/api_key
{
  "role_descriptors": {
    "role_name": {
      "indices": \n},
  },
}''', 84)),
        Completion(text='[{}]')
    )


def test_payload_value_completion_100():
    completions = list(get_completions(Document('''PUT my-index
{
  "mappings": {
    "properties": {
      "abc": {
        "type": "t",
        "doc_values": true,
        "similarity": "BM25",
        "term_vector": "",
        "copy_to": ["{field}"],
        "analyzer":
      }
    },
  },
}''', 84)))
    assert completions_has(
        completions,
        Completion(text='text', start_position=-1),
        Completion(text='byte', start_position=-1),
        Completion(text='integer', start_position=-1),
        Completion(text='float', start_position=-1),
    )
    assert completions_has_no(completions, Completion(text='keyword', start_position=-1))


def test_payload_value_completion_110():
    completions = list(get_completions(Document('''PUT my-index
{
  "mappings": {
    "properties": {
      "abc": {
        "type": "text",
        "doc_values": ,
        "similarity": "BM25",
        "term_vector": "",
        "copy_to": ["{field}"],
        "analyzer":
      }
    },
  },
}''', 112)))
    assert completions_has(
        completions,
        Completion(text='true'),
        Completion(text='false'),
    )

    completions = list(get_completions(Document('''PUT my-index
{
  "mappings": {
    "properties": {
      "abc": {
        "type": "text",
        "doc_values": t,
        "similarity": "BM25",
        "term_vector": "",
        "copy_to": ["{field}"],
        "analyzer":
      }
    },
  },
}''', 113)))
    assert completions_has(
        completions,
        Completion(text='true', start_position=-1),
    )
    assert completions_has_no(
        completions,
        Completion(text='false', start_position=-1),
    )


def test_payload_value_completion_120():
    completions = list(get_completions(Document('''PUT my-index
{
  "mappings": {
    "properties": {
      "abc": {
        "type": "text",
        "doc_values": false,
        "similarity": "BM25",
        "term_vector": "",
        "copy_to": ,
        "analyzer":
      }
    },
  },
}''', 195)))
    assert completions_has(
        completions,
        Completion(text='""'),
        Completion(text='["{field}"]'),
    )

    completions = list(get_completions(Document('''PUT my-index
{
  "mappings": {
    "properties": {
      "abc": {
        "type": "text",
        "doc_values": false,
        "similarity": "BM25",
        "term_vector": "",
        "copy_to": "",
        "analyzer":
      }
    },
  },
}''', 196)))
    assert completions_has(
        completions,
        Completion(text='{field}'),
    )


def test_payload_value_completion_130():
    completions = list(get_completions(Document('''PUT my-index
{
  "mappings": {
    "properties": {
      "abc": {
        "type": "text",
        "doc_values": false,
        "similarity": "BM25",
        "term_vector": "",
        "copy_to": "",
        "analyzer": ,
      }
    },
  },
}''', 219)))
    assert completions_has(
        completions,
        Completion(text='"standard"'),
    )

    completions = list(get_completions(Document('''PUT my-index
{
  "mappings": {
    "properties": {
      "abc": {
        "type": "text",
        "doc_values": false,
        "similarity": "BM25",
        "term_vector": "",
        "copy_to": "",
        "analyzer": "",
      }
    },
  },
}''', 220)))
    assert completions_has(
        completions,
        Completion(text='standard'),
    )


def test_field_placeholder():
    assert completions_has(get_completions(Document('''GET _search
{
  "query": {
    "match": {
      "a_field": {
        ""
      }
    },
  },
}''', 70)), Completion(text='type'), Completion(text='zero_terms_query'))
