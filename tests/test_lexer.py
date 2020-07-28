import json

from pygments.token import Token, Whitespace, Comment, String

from peek.clients import merge_unprocessed_tokens, parse_for_payload, parse_for_method_and_path
from peek.lexers import PeekLexer, PayloadLexer, CurlyRight, CurlyLeft


def test_merge_tokens():
    tokens = [
        (0, String.Double, '"'), (1, String.Double, 'str'), (4, String.Double, '"'),
        (5, CurlyLeft, '{'), (6, CurlyLeft, '{'), (7, Whitespace, '  '),
        (10, CurlyRight, '}'), (11, Whitespace, ' '), (12, CurlyRight, '}'),
        (13, String.Double, '"'), (14, String.Double, 'd'), (15, String.Double, '"'),
        (16, String.Single, "'"), (17, String.Single, 's'), (18, String.Single, "'"),
    ]
    merged_tokens = merge_unprocessed_tokens(tokens)
    assert merged_tokens == [
        (0, String.Double, '"str"'),
        (5, CurlyLeft, '{'), (6, CurlyLeft, '{'),
        (10, CurlyRight, '}'), (12, CurlyRight, '}'),
        (13, String.Double, '"d"'),
        (16, String.Single, "'s'"),
    ]


def test_lexer_normal_payload():
    text = r"""{
    "foo": "bar", // a comment
    "hello": 1.0,
    "world": [2.0, true, null, false], // more comment
    "nested": {
        "this is it": "orly?",
        "the end": ['the', 'end', 'of', 'it']
    }
}"""
    payload = do_test_for_payload(text)
    assert (payload == '{ "foo" : "bar" , "hello" : 1.0 , '
                       '"world" : [ 2.0 , true , null , false ] , '
                       '"nested" : { "this is it" : "orly?" , "the end" : [ "the" , "end" , "of" , "it" ] } } \n')


def test_lexer_string_escapes():
    text = r"""{
    "'hello\tworld'": '"hello\tworld"',
    "foo\\\t\nbar": 'foo\\\t\nbar',
    "magic\\'\"": 'magic\\"\''
}"""
    payload = do_test_for_payload(text)
    assert (payload == """{ "'hello\\tworld'" : "\\"hello\\tworld\\"" , """
            + """"foo\\\\\\t\\nbar" : "foo\\\\\\t\\nbar" , """
            + """"magic\\\\'\\"" : "magic\\\\\\"'" } \n""")


def test_lexer_tdqs():
    text = r'''{
        "'hello\tworld'": """"hello\t
world\"""",
        "foo\\\t\nbar": """foo\\
\t\nbar""",
        "magic\\'\"": """magic\\"\''"""
    }'''
    payload = do_test_for_payload(text)
    assert (payload == """{ "'hello\\tworld'" : "\\"hello\\t\\nworld\\"" , """
            + """"foo\\\\\\t\\nbar" : "foo\\\\\\n\\t\\nbar" , """
            + """"magic\\\\'\\"" : "magic\\\\\\"''" } \n""")


def test_lexer_tsqs():
    text = r"""{
        "'hello\tworld'": ''''hello\t
world\'''',
        "foo\\\t\nbar": '''foo\\
\t\nbar''',
        "magic\\'\"": '''magic\\"\'"'''
    }"""
    payload = do_test_for_payload(text)
    assert (payload == """{ "'hello\\tworld'" : "'hello\\t\\nworld'" , """
            + """"foo\\\\\\t\\nbar" : "foo\\\\\\n\\t\\nbar" , """
            + """"magic\\\\'\\"" : "magic\\\\\\"'\\"" } \n""")


def test_lexer_bulk_index_payload():
    text = '''PUT _bulk
{ "index" : { "_index" : "test", "_id" : "1" } }
{ "field1" : "value1" }
{ "delete" : { "_index" : "test", "_id" : "2" } }
{ "create" : { "_index" : "test", "_id" : "3" } }
{ "field1" : "value3" }
{ "update" : {"_id" : "1", "_index" : "test"} }
{ "doc" : {"field2" : "value2"} }
'''
    lexer = PeekLexer()
    tokens = [t for t in lexer.get_tokens_unprocessed(text)]
    for t in tokens:
        assert t[1] is not Token.Error

    merged_tokens = merge_unprocessed_tokens(tokens)
    for t in merged_tokens:
        assert t[1] not in (Whitespace, Comment.Single), t

    method, path = parse_for_method_and_path(merged_tokens)
    assert method == 'PUT'
    assert path == '/_bulk'
    payload = parse_for_payload(merged_tokens[2:])
    try:
        for line in payload.splitlines():
            if line.strip():
                json.loads(line)
    except Exception as e:
        assert False, e


def test_lexer_command():
    lexer = PeekLexer()
    text = '''%command arg1 arg2 // comment abc'''
    tokens = [t for t in lexer.get_tokens(text)]

    for t in tokens:
        print(t)


def test_lexer_api_call():
    lexer = PeekLexer()
    text = '''// Comment
PUT /my-index/_doc/12345?pretty&flat_settings=false // here
{
    "foo":
        "bar",
    "number": 1.0,
    "bool": true,
    "null": null,
    "list": [42, false, null, "string", {"inner":"something"},]
}'''
    tokens = [t for t in lexer.get_tokens_unprocessed(text)]

    for t in tokens:
        print(t)


def do_test_for_payload(text):
    lexer = PayloadLexer()
    tokens = [t for t in lexer.get_tokens_unprocessed(text)]
    for t in tokens:
        assert t[1] is not Token.Error

    merged_tokens = merge_unprocessed_tokens(tokens)
    for t in merged_tokens:
        assert t[1] not in (Whitespace, Comment.Single), t

    payload = parse_for_payload(merged_tokens)
    try:
        for line in payload.splitlines():
            if line.strip():
                json.loads(line)
    except Exception as e:
        assert False, e
    return payload
