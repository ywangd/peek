import os
import re

from peek.parser import PeekParser
from peek.visitors import FormattingVisitor

_CONST_SIMPLE_PATTERN = re.compile(r'^(export )?const (?P<name>\w+)[^=]* = (?P<rest>{[^;]*);?')
_CONST_COMPLEX_PATTERN = re.compile(r'^(export )?const (?P<name>\w+)[^=]* = '
                                    r'\(specService: SpecDefinitionsService\) => (?P<rest>{[^;]*);?')
_CONST_MULTI_PATTERN = re.compile(r'^(export )?const {(?P<names>[^}]*)} = (?P<value>.+);')
_RECORD_MEMBER_PATTERN = re.compile(r'(?P<assign>^\w+\.\w+ = {[^;]*);?')
_FUNCTION_PATTERN = re.compile(r'function \((?P<args>[^)]*)\) { *;?]')
_RETURN_PATTERN = re.compile(r'return (?P<value>.*)')


class SpecBuilder:

    def __init__(self, kibana_dir):
        self.kibana_dir = kibana_dir
        self.source = None
        self.nodes = []

    def build(self):
        self.source = self._extract_all()
        parser = PeekParser()
        self.nodes = parser.parse(self.source)
        return self.nodes

    def save(self, output_file):
        content = []
        for node in self.nodes:
            content.append(FormattingVisitor(pretty=True).visit(node))
        with open(output_file, 'w') as outs:
            outs.write('\n'.join(content))

    def _extract_all(self):
        spec_file_contents = load_ts_specs(self.kibana_dir)
        sources = []
        for file_name, file_content in spec_file_contents.items():
            sources.extend(self._extract_from_one_file(file_name, file_content))
        text = '\n'.join(sources)
        return text.replace("rules['*']", "rules.'*'")

    def _extract_from_one_file(self, file_name, file_content):
        sources = [f'// {file_name!r}']
        state = ''
        for line in file_content.splitlines():
            stripped = line.strip().replace('...', '"...": @')
            if state == 'comments':
                if stripped.startswith('*/'):
                    state = ''
                else:
                    continue
            elif state == 'import':
                if stripped.endswith(';'):
                    state = ''
                continue
            elif stripped.startswith('/*'):
                if not stripped.endswith('*/'):
                    state = 'comments'
                continue
            elif stripped == '' or stripped.startswith('// '):
                continue
            elif stripped.startswith('import '):
                if stripped.endswith(';'):
                    continue
                elif stripped.endswith('{'):
                    assert state == '', f'import within other state: {state!r}'
                    state = 'import'
                    continue
                else:
                    raise ValueError(f'Unrecognised import variant: {stripped!r}')
            elif self._try_speical_0001(sources, stripped):
                continue
            elif self._try_special_0002(sources, stripped):
                continue
            elif self._try_const_simple_pattern(sources, stripped):
                continue
            elif self._try_const_complex_pattern(sources, stripped):
                continue
            elif self._try_const_multi_pattern(sources, stripped):
                continue
            elif self._try_record_member_assignment(sources, stripped):
                continue
            elif self._try_spec_service(sources, stripped):
                continue
            elif self._try_function(sources, stripped):
                continue
            elif self._try_return(sources, stripped):
                continue
            elif stripped.startswith('export '):
                continue
            elif stripped == 'gap_policy,':
                sources.append('"gap_policy": gap_policy,')
            elif stripped.endswith(';'):
                sources.append(stripped[:-1])
            else:
                sources.append(stripped)
        return sources

    def _try_const_simple_pattern(self, sources, stripped):
        m = _CONST_SIMPLE_PATTERN.match(stripped)
        if m is not None:
            sources.append(f'let {m["name"]} = {m["rest"]}')
            return True
        else:
            return False

    def _try_const_complex_pattern(self, sources, stripped):
        m = _CONST_COMPLEX_PATTERN.match(stripped)
        if m is not None:
            sources.append(f'for {m["name"]} in [0] {m["rest"]}')
            return True
        else:
            return False

    def _try_const_multi_pattern(self, sources, stripped):
        m = _CONST_MULTI_PATTERN.match(stripped)
        if m is not None:
            for name in m['names'].split(','):
                sources.append(f'let {name.strip()} = {m["value"]}')
            return True
        else:
            return False

    def _try_record_member_assignment(self, sources, stripped):
        m = _RECORD_MEMBER_PATTERN.match(stripped)
        if m is not None:
            sources.append(f'let {m["assign"]}')
            return True
        else:
            return False

    def _try_spec_service(self, sources, stripped):
        if stripped.startswith('specService.'):
            sources.append(_trim_semicolon(stripped.replace('specService.', 'specService ', 1)))
            return True
        else:
            return False

    def _try_function(self, sources, stripped):
        if stripped == 'function (s) {':
            sources.append('{')
            return True
        else:
            return False

    def _try_return(self, sources, stripped):
        m = _RETURN_PATTERN.match(stripped)
        if m is not None:
            value = m["value"]
            if value.endswith(';'):
                value = value[:-1]
            sources.append(f'"return": """{value}"""')
            return True
        else:
            return False

    def _try_speical_0001(self, sources, stripped):
        if stripped == ''''*': { terms, histogram, date_histogram },''':
            sources.append('"*": { "terms": terms, "histogram": histogram, "date_histogram": date_histogram },')
            return True
        else:
            return False

    def _try_special_0002(self, sources, stripped):
        # TODO: filters.m is not handled
        if stripped == '''filters.m = filters.missing = {''':
            sources.append('let filters.missing = {')
            return True
        else:
            return False


def load_ts_specs(kibana_dir):
    oss_path = os.path.join(
        kibana_dir, 'src', 'plugins', 'console', 'server', 'lib', 'spec_definitions', 'js')
    xpack_path = os.path.join(
        kibana_dir, 'x-pack', 'plugins', 'console_extensions', 'server', 'lib', 'spec_definitions', 'js')

    spec_file_contents = _load_ts_specs(oss_path)
    spec_file_contents.update(_load_ts_specs(xpack_path))
    return spec_file_contents


def _load_ts_specs(base_dir):
    prefix = 'x-pack' if 'x-pack' in base_dir else 'oss'
    spec_file_contents = {}
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if not f.endswith('.ts'):
                continue
            if f == 'shared.ts':  # TODO: skip
                continue
            with open(os.path.join(root, f)) as ins:
                spec_file_contents[f'{prefix}/{f[:-3]}'] = ins.read()

    return spec_file_contents


def _trim_semicolon(line):
    return line[:-1] if line.endswith(';') else line
