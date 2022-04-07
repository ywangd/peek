from abc import ABCMeta, abstractmethod


class ESApiCompleter(metaclass=ABCMeta):
    @abstractmethod
    def complete_url_path(self, document, complete_event, method, path_tokens):
        pass

    @abstractmethod
    def complete_query_param_name(self, document, complete_event, method, path_tokens):
        pass

    @abstractmethod
    def complete_query_param_value(self, document, complete_event, method, path_tokens):
        pass

    @abstractmethod
    def complete_payload(self, document, complete_event, method, path_tokens, payload_tokens):
        pass

    @abstractmethod
    def complete_payload_value(self, document, complete_event, method, path_tokens, payload_tokens, payload_events):
        pass


def can_match(ts, ps):
    """
    Test whether the input path (ts) can match the candidate path (ps).
    The rule is basically a placeholder can match any string other than
    the ones leading with underscore.
    """
    for t, p in zip(ts, ps):
        if t != p:
            if t.startswith('_'):
                return False
            if not (p.startswith('{') and p.endswith('}')):
                return False
    return True
