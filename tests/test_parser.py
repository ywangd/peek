import pytest
from pygments.token import String, Whitespace, Comment, Literal, Name

from peek.ast import EsApiCallNode, ShellOutNode, EsApiCallInlinePayloadNode, EsApiCallFilePayloadNode
from peek.errors import PeekSyntaxError
from peek.lexers import CurlyLeft, CurlyRight, HttpMethod, FuncName, BlankLine, Let
from peek.parser import PeekParser, process_tokens, PeekToken, ParserEventType, find_last_stmt_token


@pytest.fixture
def parser():
    return PeekParser()


def test_process_tokens():
    tokens = [PeekToken(*t) for t in (
        (0, String.Double, '"'), (1, String.Double, 'str'), (4, String.Double, '"'),
        (5, CurlyLeft, '{'), (6, CurlyLeft, '{'), (7, Whitespace, '  '),
        (10, CurlyRight, '}'), (11, Whitespace, ' '), (12, CurlyRight, '}'),
        (13, String.Double, '"'), (14, String.Double, 'd'), (15, String.Double, '"'),
        (16, String.Single, "'"), (17, String.Single, 's'), (18, String.Single, "'"),
        (19, Comment.Single, "# comment")
    )]
    processed_tokens = process_tokens(tokens)
    assert processed_tokens == [
        (0, String.Double, '"str"'),
        (5, CurlyLeft, '{'), (6, CurlyLeft, '{'),
        (10, CurlyRight, '}'), (12, CurlyRight, '}'),
        (13, String.Double, '"d"'),
        (16, String.Single, "'s'"),
    ]


def test_find_last_stmt_token():
    tokens = [
        PeekToken(index=0, ttype=HttpMethod, value='get'),
        PeekToken(index=4, ttype=Literal, value='abc'),
        PeekToken(index=8, ttype=FuncName, value='ge')
    ]
    i = find_last_stmt_token(tokens)
    assert i == 2

    tokens = [
        PeekToken(index=0, ttype=FuncName, value='connect'),
        PeekToken(index=7, ttype=BlankLine, value='\n'),
        PeekToken(index=8, ttype=FuncName, value='session')
    ]
    i = find_last_stmt_token(tokens)
    assert i == 2

    tokens = [
        PeekToken(index=0, ttype=HttpMethod, value='get'),
        PeekToken(index=4, ttype=Literal, value='abc'),
        PeekToken(index=8, ttype=Let, value='let'),
        PeekToken(index=8, ttype=Name, value='foo'),
    ]
    i = find_last_stmt_token(tokens)
    assert i == 2


def test_parser_comment(parser):
    text = """// comment
"""
    nodes = parser.parse(text)
    assert len(nodes) == 0


def test_parser_shellout(parser):
    text = """!ls something another
"""
    nodes = parser.parse(text)
    assert len(nodes) == 1
    n = nodes[0]
    assert isinstance(n, ShellOutNode)
    assert n.command == 'ls something another'


def test_parser_single_es_api_call(parser):
    text = """get /abc
Head /my-index/_doc/1"""
    nodes = parser.parse(text)
    assert len(nodes) == 2
    n = nodes[0]
    assert isinstance(n, EsApiCallInlinePayloadNode)
    assert n.method == 'GET'
    assert n.path == '/abc'
    assert len(n.dict_nodes) == 0

    n = nodes[1]
    assert isinstance(n, EsApiCallInlinePayloadNode)
    assert n.method == 'HEAD'
    assert n.path == '/my-index/_doc/1'
    assert len(n.dict_nodes) == 0


def test_api_path_variable(parser):
    text = """get ("a" + "bc")"""
    nodes = parser.parse(text)
    assert len(nodes) == 1
    n = nodes[0]
    assert isinstance(n, EsApiCallNode)
    assert n.method == 'GET'
    assert str(n.path_node) == '("a" + "bc")'


def test_parser_multiple_simple_statements(parser):
    text = """get abc

post abc/_doc
{ "foo":
         "bar"
}

conn foo=bar  // comment
get abc
post xyz/_doc
{"index": "asfa"}
// comment
{"again": [{"ok": 1}]}
get xyz/_doc/1 // comment
session @info
get foo
"""
    nodes = parser.parse(text)
    assert len(nodes) == 8


def test_parser_normal_payload(parser):
    text = r"""// Comment
    pUt /somewhere //here
{
    "foo": "bar", // a comment
    "hello": 1.0,
    "world": [2.0, true, null, false], // more comment
    "nested": {
        "this is it": "orly?",
        "the end": [42, 'the', 'end', 'of', 'it']
    }
}"""
    nodes = parser.parse(text)
    assert len(nodes) == 1
    n = nodes[0]
    assert isinstance(n, EsApiCallNode)
    assert n.method == 'PUT'
    assert n.path == '/somewhere'
    assert str(n) == r"""pUt /somewhere {}
{"foo":"bar","hello":1.0,"world":[2.0,true,null,false],"nested":{"this is it":"orly?","the end":[42,'the','end','of','it']}}
"""


def test_parser_file_payload(parser):
    text = """get _abc
@some_file
"""
    nodes = parser.parse(text)
    assert len(nodes) == 1
    n = nodes[0]
    assert isinstance(n, EsApiCallFilePayloadNode)
    assert n.method == 'GET'
    assert n.path == '/_abc'
    assert str(n.file_node) == 'some_file'


def test_parser_string_escapes(parser):
    text = r"""geT out
{
    "'hello\tworld'": '"hello\tworld"',
    "foo\\\t\nbar": 'foo\\\t\nbar',
    "magic\\'\"": 'magic\\"\''
}"""
    nodes = parser.parse(text)
    assert len(nodes) == 1
    n = nodes[0]
    assert isinstance(n, EsApiCallNode)
    assert str(n) == r"""geT out {}
{"'hello\tworld'":'"hello\tworld"',"foo\\\t\nbar":'foo\\\t\nbar',"magic\\'\"":'magic\\"\''}
"""


def test_parser_tdqs(parser):
    text = r'''post /away
    {
        "'hello\tworld'": """"hello\t
world\"""",
        "foo\\\t\nbar": """foo\\
\t\nbar""",
        "magic\\'\"": """magic\\"\''"""
    }'''
    nodes = parser.parse(text)
    assert len(nodes) == 1
    n = nodes[0]
    assert isinstance(n, EsApiCallNode)
    assert str(n) == r'''post /away {}
{"'hello\tworld'":""""hello\t
world\"""","foo\\\t\nbar":"""foo\\
\t\nbar""","magic\\'\"":"""magic\\"\''"""}
'''


def test_parser_tsqs(parser):
    text = r"""delete it
{
        "'hello\tworld'": ''''hello\t
world\'''',
        "foo\\\t\nbar": '''foo\\
\t\nbar''',
        "magic\\'\"": '''magic\\"\'"'''
    }"""
    nodes = parser.parse(text)
    assert len(nodes) == 1
    n = nodes[0]
    assert isinstance(n, EsApiCallNode)
    assert str(n) == r"""delete it {}
{"'hello\tworld'":''''hello\t
world\'''',"foo\\\t\nbar":'''foo\\
\t\nbar''',"magic\\'\"":'''magic\\"\'"'''}
"""


def test_parser_bulk_index(parser):
    text = '''PUT _bulk
{ "index" : { "_index" : "test", "_id" : "1" } }
{ "field1" : "value1" }
{ "delete" : { "_index" : "test", "_id" : "2" } }
{ "create" : { "_index" : "test", "_id" : "3" } }
{ "field1" : "value3" }
{ "update" : {"_id" : "1", "_index" : "test"} }
{ "doc" : {"field2" : "value2"} }
'''
    nodes = parser.parse(text)
    print(nodes)
    assert len(nodes) == 1
    n = nodes[0]
    assert isinstance(n, EsApiCallNode)
    print(n)
    assert str(n) == r'''PUT _bulk {}
{"index":{"_index":"test","_id":"1"}}
{"field1":"value1"}
{"delete":{"_index":"test","_id":"2"}}
{"create":{"_index":"test","_id":"3"}}
{"field1":"value3"}
{"update":{"_id":"1","_index":"test"}}
{"doc":{"field2":"value2"}}
'''


def test_parser_invalid_missing_comma(parser):
    text = """get abc
{"a": 1 2,
 "b": 5 }"""
    with pytest.raises(PeekSyntaxError) as e:
        parser.parse(text)

    assert 'Syntax error at Line 2, Column 9' in str(e.value)

    text = """get abc
{"a": [ 3 4 ]}"""
    with pytest.raises(PeekSyntaxError) as e:
        parser.parse(text)

    assert 'Syntax error at Line 2, Column 11' in str(e.value)


def test_parser_incomplete(parser):
    text = """get
"""
    with pytest.raises(PeekSyntaxError) as e:
        parser.parse(text)

    assert 'Syntax error at Line 1, Column 4' in str(e.value)
    assert 'HTTP path must be either text literal or an expression enclosed by parenthesis' in str(e.value)


def test_parser_expr(parser):
    text = '''f 1 * 2 + (3 - 2) g(3)
'''
    nodes = parser.parse(text)
    assert 1 == len(nodes)
    assert str(nodes[0]) == "f [] [1 * 2 + (3 - 2),g [] [3] {}] {}\n"


def test_parser_dict_keys(parser):
    text = '''f {4: 2} {3 + 5: 2} {"a" + "b": c}'''
    nodes = parser.parse(text)
    assert str(nodes[0]) == 'f [] [{4:2},{3 + 5:2},{"a" + "b":c}] {}\n'


def test_implicit_variable(parser):
    text = '''f _."a".1'''
    nodes = parser.parse(text)
    assert str(nodes[0]) == 'f [] [_ . "a" . 1] {}\n'


def test_func_expr_chain(parser):
    text = '''f a.@b(1)'''
    nodes = parser.parse(text)
    assert str(nodes[0]) == 'f [] [a . b [] [1] {}] {}\n'


def test_payload_filename_with_whitespaces(parser):
    text = '''PUT _bulk
@file name with whitespaces.json'''
    nodes = parser.parse(text)
    assert len(nodes) == 1
    assert isinstance(nodes[0], EsApiCallFilePayloadNode)
    assert nodes[0].file_node.token.value == 'file name with whitespaces.json'


def test_payload_file(parser):
    text = '''{'index': {'_index': 'index', '_id': '1'}}
{'category': 'click', 'tag': 1}
{'index': {'_index': 'index', '_id': '2'}}
{'category': 'click', 'tag': 2}'''
    nodes = parser.parse(text, payload_only=True)
    assert len(nodes) == 4
    assert '\n'.join(str(n) for n in nodes) == '''{'index':{'_index':'index','_id':'1'}}
{'category':'click','tag':1}
{'index':{'_index':'index','_id':'2'}}
{'category':'click','tag':2}'''


def test_parser_events_000(parser):
    events = []
    parser.listeners = [lambda event: events.append(event)]

    text = '''GET _search conn=10'''

    parser.parse(text)
    assert len(events) == 10
    assert events[0].type is ParserEventType.ES_METHOD
    assert events[2].type is ParserEventType.ES_URL
    assert events[4].type is ParserEventType.ES_OPTION_NAME
    assert events[7].type is ParserEventType.BEFORE_ES_OPTION_VALUE
    assert events[9].type is ParserEventType.AFTER_ES_OPTION_VALUE
    tokens = [event.token for event in events if event.type is ParserEventType.AFTER_TOKEN]
    assert len(tokens) == 5


def test_parser_events_001(parser):
    events = []
    parser.listeners = [lambda event: events.append(event)]

    text = '''GET _search conn=10 headers={
    "foo":
'''
    with pytest.raises(PeekSyntaxError):
        parser.parse(text)
    assert len(events) == 19
    assert events[10].type is ParserEventType.ES_OPTION_NAME
    assert events[13].type is ParserEventType.BEFORE_ES_OPTION_VALUE
    tokens = [event.token for event in events if event.type is ParserEventType.AFTER_TOKEN]
    assert len(tokens) == 10


def test_parser_events_002(parser):
    events = []
    parser.listeners = [lambda event: events.append(event)]

    text = '''GET _search conn=10 headers={
    "foo": "bar"
}
{
   "hello
'''
    with pytest.raises(PeekSyntaxError):
        parser.parse(text)
    for event in events:
        print(event)
    assert len(events) == 28
    assert events[23].type is ParserEventType.BEFORE_ES_PAYLOAD_INLINE
    assert events[25].type is ParserEventType.BEFORE_DICT_KEY_EXPR
    tokens = [event.token for event in events if event.type is ParserEventType.AFTER_TOKEN]
    assert len(tokens) == 14


def test_parser_events_003(parser):
    events = []
    parser.listeners = [lambda event: events.append(event)]

    text = '''GET _search
{"foo": "bar"}
{"hello'''
    with pytest.raises(PeekSyntaxError):
        parser.parse(text)
    assert len(events) == 18
    assert events[4].type is ParserEventType.BEFORE_ES_PAYLOAD_INLINE
    assert events[14].type is ParserEventType.BEFORE_ES_PAYLOAD_INLINE
    tokens = [event.token for event in events if event.type is ParserEventType.AFTER_TOKEN]
    assert len(tokens) == 9


def test_parser_events_004(parser):
    events = []
    parser.listeners = [lambda event: events.append(event)]

    text = '''GET _search
    @a'''
    parser.parse(text)
    assert len(events) == 7
    assert events[4].type is ParserEventType.ES_PAYLOAD_FILE_AT
    tokens = [event.token for event in events if event.type is ParserEventType.AFTER_TOKEN]
    assert len(tokens) == 4


def test_allow_error_token(parser):
    text = 'GET _ ()'

    events = []
    parser.listeners = [lambda event: events.append(event)]

    with pytest.raises(PeekSyntaxError):
        parser.parse(text)
    assert len(events) == 0

    with pytest.raises(PeekSyntaxError):
        parser.parse(text, fail_fast_on_error_token=False)
    assert len(events) > 0
