import json
import os
from typing import Iterable

from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter
from prompt_toolkit.document import Document

_HTTP_METHOD_COMPLETER = WordCompleter(['GET', 'POST', 'PUT', 'DELETE'], ignore_case=True)


class PeekCompleter(Completer):

    def __init__(self):
        self.specs = load_rest_api_spec()

    def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        if '\n' in document.text:
            return []
        for c in document.text.lstrip():
            if c.isspace():
                return self._get_path(document, complete_event)
        else:
            return _HTTP_METHOD_COMPLETER.get_completions(document, complete_event)

    def _get_path(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
        fields = document.text.lstrip().split(maxsplit=1)
        if len(fields) != 2:
            return []
        method = fields[0].upper()
        path = fields[1].lstrip()
        ret = []
        # TODO: handle placeholder in path
        # TODO: complete parameters
        for name, spec in self.specs.items():
            for p in spec['url']['paths']:
                if method in p['methods']:
                    if p['path'].startswith(path) or p['path'].startswith(f'/{path}'):
                        ret.append(Completion(p['path'], start_position=-len(path)))
        return ret


def load_rest_api_spec():
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    spec_dir = os.path.join(package_root, 'rest-api-spec', 'api')
    spec_files = [f for f in os.listdir(spec_dir) if f.endswith('.json')]
    specs = {}
    for spec_file in spec_files:
        if spec_file == '_common.json':
            continue
        with open(os.path.join(spec_dir, spec_file)) as ins:
            specs.update(json.load(ins))
    return specs
