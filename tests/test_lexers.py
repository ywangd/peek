import pytest
from pygments.token import Token

from peek.lexers import PeekLexer


@pytest.fixture
def peek_lexer():
    return PeekLexer()


@pytest.fixture
def payload_lexer():
    return PeekLexer(stack=('dict',))


def do_test(peek_lexer, text, error_tokens=None):
    error_tokens = error_tokens or []
    tokens = []
    for t in peek_lexer.get_tokens_unprocessed(text):
        print(t)
        tokens.append(t)
        if t[1] is Token.Error and error_tokens:
            assert t == error_tokens[0]
            error_tokens.pop(0)
            continue
        assert t[1] is not Token.Error


def test_numbers(payload_lexer):
    text = """{"numbers": [42, 4.2, 0.42, 42e+1, 4.2e-1, .42, -42, -4.2, -.42]}"""
    for t in payload_lexer.get_tokens_unprocessed(text):
        assert t[1] is not Token.Error, t


def test_es_api_calls(peek_lexer):
    do_test(peek_lexer, """get /some/path
{}

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


def test_func_calls(peek_lexer):
    do_test(peek_lexer, """conn 1
conn "a" foo=1 c=bar

f a b c // this is ok

t 1 2 3 foo=bar // comment

g 1 b=[3,4] x={
"a": // inner
 1} // ok""")


def test_invalid_000(peek_lexer):
    do_test(peek_lexer, """conn 1 2 3 foo=bar /""", error_tokens=[(19, Token.Error, '/')])
    do_test(peek_lexer, """get / /""", error_tokens=[(6, Token.Error, '/')])


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


def test_func_call_connect(peek_lexer):
    do_test(peek_lexer, text="""connect hosts='https://localhost:9200' username='foo'""")
