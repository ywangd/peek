HTTP_METHODS = ('GET', 'POST', 'PUT', 'DELETE')


class AlwaysNoneNameSpace:
    def __getattr__(self, name):
        return None


NONE_NS = AlwaysNoneNameSpace()
