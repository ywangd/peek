from peek.lexers import PeekLexer


def test_lexer_api_call():
    lexer = PeekLexer()
    text = '''PUT /my-index/_doc/12345?pretty&flat_settings=false
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


def test_lexer_command():
    lexer = PeekLexer()
    text = '''%command arg1 arg2 // comment abc'''
    tokens = [t for t in lexer.get_tokens(text)]

    for t in tokens:
        print(t)
