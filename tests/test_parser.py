import json

import pytest
from pygments.token import String, Whitespace

from peek.errors import PeekSyntaxError
from peek.lexers import CurlyLeft, CurlyRight
from peek.parser import PeekParser, process_tokens, PeekToken


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
    )]
    merged_tokens = process_tokens(tokens)
    assert merged_tokens == [
        (0, String.Double, '"str"'),
        (5, CurlyLeft, '{'), (6, CurlyLeft, '{'),
        (10, CurlyRight, '}'), (12, CurlyRight, '}'),
        (13, String.Double, '"d"'),
        (16, String.Single, "'s'"),
    ]


def test_parser_single_es_api_call(parser):
    text = """get /abc"""
    stmts = parser.parse(text)
    assert len(stmts) == 1
    assert stmts[0].method == 'GET'
    assert stmts[0].path == '/abc'
    assert stmts[0].payload is None


def test_parser_multiple_simple_statements(parser):
    text = """get abc

post abc/_doc
{ "foo":
         "bar"
}

%conn foo=bar  // comment
get abc
"""
    stmts = parser.parse(text)
    assert len(stmts) == 4


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
    stmts = parser.parse(text)
    assert len(stmts) == 1
    assert (stmts[0].payload ==
            '{ "foo" : "bar" , "hello" : 1.0 , '
            '"world" : [ 2.0 , true , null , false ] , '
            '"nested" : { "this is it" : "orly?" , "the end" : [ 42 , "the" , "end" , "of" , "it" ] } }\n')


def test_parser_string_escapes(parser):
    text = r"""geT out
{
    "'hello\tworld'": '"hello\tworld"',
    "foo\\\t\nbar": 'foo\\\t\nbar',
    "magic\\'\"": 'magic\\"\''
}"""
    stmts = parser.parse(text)
    assert len(stmts) == 1
    assert (stmts[0].payload ==
            """{ "'hello\\tworld'" : "\\"hello\\tworld\\"" , """
            + """"foo\\\\\\t\\nbar" : "foo\\\\\\t\\nbar" , """
            + """"magic\\\\'\\"" : "magic\\\\\\"'" }\n""")


def test_parser_tdqs(parser):
    text = r'''post /away {
        "'hello\tworld'": """"hello\t
world\"""",
        "foo\\\t\nbar": """foo\\
\t\nbar""",
        "magic\\'\"": """magic\\"\''"""
    }'''
    stmts = parser.parse(text)
    assert len(stmts) == 1
    assert (stmts[0].payload ==
            """{ "'hello\\tworld'" : "\\"hello\\t\\nworld\\"" , """
            + """"foo\\\\\\t\\nbar" : "foo\\\\\\n\\t\\nbar" , """
            + """"magic\\\\'\\"" : "magic\\\\\\"''" }\n""")


def test_parser_tsqs(parser):
    text = r"""delete it
{
        "'hello\tworld'": ''''hello\t
world\'''',
        "foo\\\t\nbar": '''foo\\
\t\nbar''',
        "magic\\'\"": '''magic\\"\'"'''
    }"""
    stmts = parser.parse(text)
    assert len(stmts) == 1
    assert (stmts[0].payload ==
            """{ "'hello\\tworld'" : "'hello\\t\\nworld'" , """
            + """"foo\\\\\\t\\nbar" : "foo\\\\\\n\\t\\nbar" , """
            + """"magic\\\\'\\"" : "magic\\\\\\"'\\"" }\n""")


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
    stmts = parser.parse(text)
    print(stmts)
    assert len(stmts) == 1
    assert stmts[0].method == 'PUT'
    assert stmts[0].path == '/_bulk'
    try:
        for line in stmts[0].payload.splitlines():
            if line.strip():
                json.loads(line)
    except Exception as e:
        assert False, e


def test_parser_invalid(parser):
    text = """get abc
qrs"""

    with pytest.raises(PeekSyntaxError) as e:
        parser.parse(text)

    assert 'qrs' in str(e.value)


def test_parser_invalid_missing_comma(parser):
    text = """get abc
{"a": 1 2,
 "b": 5 }"""
    with pytest.raises(PeekSyntaxError) as e:
        parser.parse(text)

    assert 'Expect token of type Token.Punctuation.Curly.Right, got Token.Literal.Number.Integer' in str(e.value)

    text = """get abc
{"a": [ 3 4 ]}"""
    with pytest.raises(PeekSyntaxError) as e:
        parser.parse(text)

    assert 'Expect token of type Token.Punctuation.Bracket.Right, got Token.Literal.Number.Integer' in str(e.value)
