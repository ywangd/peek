from peek.lexers import PeekLexer


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

def test_lexer_bulk_index():
    lexer = PeekLexer()
    lexer.add_filter('tokenmerge')
    lexer.add_filter('raiseonerror', excclass=RuntimeError)
    text = '''POST _bulk
{ "index" : { "_index" : "test", "_id" : "1" } }
{ "field1" : "value1" }
{ "delete" : { "_index" : "test", "_id" : "2" } }
{ "create" : { "_index" : "test", "_id" : "3" } }
{ "field1" : "value3" }
{ "update" : {"_id" : "1", "_index" : "test"} }
{ "doc" : {"field2" : "value2"} }
'''
    tokens = [t for t in lexer.get_tokens(text)]

    for t in tokens:
        print(t)

def test_lexer_command():
    lexer = PeekLexer()
    text = '''%command arg1 arg2 // comment abc'''
    tokens = [t for t in lexer.get_tokens(text)]

    for t in tokens:
        print(t)
