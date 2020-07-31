import pytest

from peek.lexers import PeekLexer


@pytest.fixture
def peek_lexer():
    return PeekLexer()


def test_incomplete_input(peek_lexer):
    text = """get
"""
    for t in peek_lexer.get_tokens_unprocessed(text):
        print(t)
