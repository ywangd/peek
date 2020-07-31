import pytest
from pygments.token import Token

from peek.lexers import PeekLexer, PayloadLexer


@pytest.fixture
def peek_lexer():
    return PeekLexer()


@pytest.fixture
def payload_lexer():
    return PayloadLexer()


def test_numbers(payload_lexer):
    text = """{"numbers": [42, 4.2, 0.42, 42e+1, 4.2e-1, .42, -42, -4.2, -.42]}"""
    for t in payload_lexer.get_tokens_unprocessed(text):
        assert t[1] is not Token.Error, t
