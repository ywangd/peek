import pytest
from pygments.token import Token, Name, Whitespace

from peek.common import PeekToken
from peek.lexers import PeekLexer, UrlPathLexer, BinOp


@pytest.fixture
def peek_lexer():
    return PeekLexer()


@pytest.fixture
def payload_lexer():
    return PeekLexer(stack=('dict',))


def do_test(lexer, text, error_tokens=None, stack=('root',)):
    error_tokens = error_tokens or []
    tokens = []
    for t in lexer.get_tokens_unprocessed(text, stack=stack):
        print(t)
        tokens.append(t)
        if t[1] is Token.Error and error_tokens:
            assert t == error_tokens[0]
            error_tokens.pop(0)
            continue
        assert t[1] is not Token.Error, t
    return tokens


def test_numbers(payload_lexer):
    text = """{"numbers": [42, 4.2, 0.42, 42e+1, 4.2e-1, .42, -42, -4.2, -.42]}"""
    for t in payload_lexer.get_tokens_unprocessed(text):
        assert t[1] is not Token.Error, t


def test_es_api_calls(peek_lexer):
    do_test(peek_lexer, """get /some/path
{}

head my-index/_doc/1

get /another/path a=b c=d
{"foo": "bar"}
{"ok": [42]}

get /yet/another // comment
// this comment is ok
{ // inner comment
  "ok": // trailing comment again
    [ // something
      42, // here
    ],
}
{"some": "other"}
""")


def test_es_api_calls_2(peek_lexer):
    do_test(peek_lexer, """get abc

post abc/_doc
{ "foo":
         "bar"
}

conn foo=bar  // comment
get abc
""")


def test_es_api_call_path_variable(peek_lexer):
    do_test(peek_lexer, '''GET ("hello" + "world" + 1)''')


def test_es_api_call_payloads(peek_lexer):
    do_test(peek_lexer, """get abc
  // comment is ok
 { }
    // another comment is fine
  {}
// yet another one
{ }

get xyz
{}
{}
""")


def test_es_api_call_file(peek_lexer):
    do_test(peek_lexer, """get _abc
@file
""")


def test_func_calls(peek_lexer):
    do_test(peek_lexer, """conn 1
conn "a" foo=1 c=bar

f a b c // this is ok

t 1 2 3 foo=bar // comment

f1 @abc // symbol is fine

g 1 b=[3,4] x={
"a": // inner
 1} // ok""")


def test_continuous_statements(peek_lexer):
    do_test(peek_lexer, """get abc
get xyz
connect 1 2 3
put xyz/_doc
{}
post qwer/_doc
{
  "a": "b",
}""")


def test_invalid_000(peek_lexer):
    do_test(peek_lexer, """conn 1 2 3 foo=bar /""", error_tokens=[(19, Token.Error, '/')])
    do_test(peek_lexer, """get / /""", error_tokens=[(6, Token.Error, '/')])


def test_invalid_001(peek_lexer):
    do_test(peek_lexer, """get /abc

{}
""", error_tokens=[PeekToken(index=10, ttype=Token.Error, value='{'),
                   PeekToken(index=11, ttype=Token.Error, value='}')])


def test_es_api_and_func_calls(peek_lexer):
    do_test(peek_lexer, """ // begining comment
get / conn=1 // first api call

connection 1 // set conneciton to 1
get / // this is the same as the first api call

f a b c q=42

put /
{}

g 42""")


def test(peek_lexer):
    do_test(peek_lexer, """ // some comments to start the day
get /some/path with=1.2 option=foo another="bar" // trailing comment
{ "hello": ["world", 1, '1'], }

connect 1 foo="bar" ok=good

put /here
{ 'some more': "things to do" }
{ 'even more': { "nest": "here", } }
""")


def test_minimal(peek_lexer):
    do_test(peek_lexer, text="""c 1 a=b""")


def test_comment(peek_lexer):
    do_test(peek_lexer, text="""// comment
""")


def test_shellout(peek_lexer):
    do_test(peek_lexer, text="""!ls
""")


def test_func_call_connect(peek_lexer):
    do_test(peek_lexer, text="""connect hosts='https://localhost:9200' username='foo'""")


def test_builtin_as_kv_value(peek_lexer):
    tokens = do_test(peek_lexer, text="""connect use_ssl=true""")
    assert tokens[-1][1] is Name.Builtin


def test_dot_notation(peek_lexer):
    tokens = [t for t in do_test(peek_lexer, text='''f a.1.2.5''') if (t.ttype is BinOp and t.value == '.')]
    assert 3 == len(tokens)


def test_expressions(peek_lexer):
    tokens = do_test(peek_lexer, text='''f kw=1 * (2 + (3 - foo)) / a.4.2."a key".(a + b.3).5."c" % 5.6 2+3/(a)
''')
    print(tokens)


def test_expressions_data_structure(peek_lexer):
    tokens = do_test(peek_lexer, text='''GET /
{
  "a": "foo" + a.3."ab".(foo*3),
  "b": 1 + 3 * (2 - 1)
}''')
    print(tokens)


def test_dict_keys(peek_lexer):
    tokens = do_test(peek_lexer, text='''f {
    "a": 4.2,
    "a" + b : "c",
    """a""" + c: 5,
}''')
    print(tokens)


def test_comment_inside_dict(peek_lexer):
    do_test(peek_lexer, text='''GET _search
{
  // comment
  "foo"  // comment
  // comment
  : // comment
  // comment
  "bar" // comment
  // comment
}''')


def test_operator_cannot_on_separate_line(peek_lexer):
    with pytest.raises(AssertionError) as e:
        do_test(peek_lexer, text='''f 1
+ 2''')

    assert "value='+'" in e.value.args[0]


def test_expression_pos_neg(peek_lexer):
    tokens = do_test(peek_lexer, text='''f -1 + -a + -(3 - -2)''')
    print(tokens)


def test_function_expr(peek_lexer):
    tokens = do_test(peek_lexer, text='''f 3 -f(a b=1 c="ok") "hello" 4.2 {"a": f(9 c=3) }''')
    print(tokens)


def test_symbol(peek_lexer):
    tokens = do_test(peek_lexer, text='''f a.@b.c.@d.1''')
    assert len([t for t in tokens if (t.ttype is BinOp and t.value == '.')]) == 4


def test_function_expr_chain(peek_lexer):
    do_test(peek_lexer, text='''f a.b.c().d.e().f.1.2 {}()''')


def test_for_stmt(peek_lexer):
    do_test(peek_lexer, text='''for i in [1,2,3] {
    do_something a b c d=1
    !shellout
    GET /api/path
    {}
    for j in [4,5,6] {
        nested_call
        GET /
        {}
        echo hello
    }
    another_call
    history
}''')


def test_whitespace_comma(peek_lexer):
    tokens = do_test(peek_lexer, text='''f a,b,c''')
    tokens = [t for t in tokens if t.ttype is not Whitespace]
    assert len(tokens) == 4

    tokens = do_test(peek_lexer, text='''f g(a,b,c)''')
    tokens = [t for t in tokens if t.ttype is not Whitespace]
    assert len(tokens) == 7


def test_payload_only(peek_lexer):
    text = '''
    // comment
    {'index': {'_index': 'index', '_id': '1'}} // trailing comment
    // another comment
{'category': 'click', 'tag': 1}
{'index': {'_index': 'index', '_id': '2'}}
{'category': 'click', 'tag': 2}'''
    do_test(peek_lexer, text, stack=('dict',))


@pytest.fixture
def url_path_lexer():
    return UrlPathLexer()


def test_url_path_empty(url_path_lexer):
    do_test(url_path_lexer, '')


def test_url_path_only(url_path_lexer):
    do_test(url_path_lexer, '/a/b/c')
    do_test(url_path_lexer, 'a/b/c/')
    do_test(url_path_lexer, '/a/b/c?')


def test_url_with_query(url_path_lexer):
    do_test(url_path_lexer, '/a/b/c?foo=bar&hello=42')
    do_test(url_path_lexer, '/a/b/c?foo=bar&name&pretty=')


def test_invalid_url(url_path_lexer):
    do_test(url_path_lexer, '/?=', error_tokens=[
        PeekToken(index=2, ttype=Token.Error, value='=')
    ])
