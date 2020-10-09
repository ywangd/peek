from typing import NamedTuple

from pygments.token import _TokenType

HTTP_METHODS = ['get', 'post', 'put', 'delete', 'head']
AUTO_SAVE_NAME = '__auto__'
DEFAULT_SAVE_NAME = '__default__'


class AlwaysNoneNameSpace:
    def __getattr__(self, name):
        return None


PeekToken = NamedTuple('PeekToken', [('index', int), ('ttype', _TokenType), ('value', str)])
NONE_NS = AlwaysNoneNameSpace()
