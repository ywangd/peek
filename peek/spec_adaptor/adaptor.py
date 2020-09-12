import os
import re

from peek.parser import PeekParser
from peek.visitors import FormattingVisitor

SIMPLE_SPEC_PATTERN = re.compile(r'^const (?P<name>\w+) = (?P<value>{.*});$', re.DOTALL)
COMPLEX_SPEC_PATTERN = re.compile(r'^const (?P<name>\w+) = '
                                  r'\(specService: SpecDefinitionsService\) => (?P<value>{.*});$', re.DOTALL)


class SpecManager:
    def __init__(self, kibana_dir):
        self.spec_extractor = SpecExtractor(kibana_dir)
        self.spec_builder = SpecBuilder()


class SpecBuilder:
    """
    Given the typescript source of a spec, construct a peek value object
    for the spec. This may require messing around the spec source code with
    regex to prepare it to be parsable as peek value object.
    Since TypeScript supports raw keys for object, when evaluating the value object,
    resolve all raw keys to its lexeme value.
    """

    def __init__(self):
        self.parser = PeekParser()
        self.formatting_visitor = FormattingVisitor(pretty=True)

    def build(self, spec_str):
        nodes = self._parse_for_nodes(spec_str)
        for node in nodes:
            self._evaluate_node(node)

    def _parse_for_nodes(self, spec_str: str):
        m = SIMPLE_SPEC_PATTERN.match(spec_str)
        if m is not None:
            return self._process_simple_spec(m)
        else:
            m = COMPLEX_SPEC_PATTERN.match(spec_str)
            if m is not None:
                return self._process_complex_spec(m)
            else:
                raise ValueError(f'Not a valid spec: {spec_str!r}')

    def _evaluate_node(self, node):
        print(self.formatting_visitor.visit(node))

    def _process_simple_spec(self, m):
        content = m['value'].replace('...', '@')
        return self.parser.parse(content, payload_only=True)

    def _process_complex_spec(self, m):
        return []


_CONST_SIMPLE_PATTERN = re.compile(r'^(export )?const (?P<name>\w+)[^=]* = (?P<rest>{[^;]*);?')
_CONST_COMPLEX_PATTERN = re.compile(r'^(export )?const (?P<name>\w+)[^=]* = '
                                    r'\(specService: SpecDefinitionsService\) => (?P<rest>{[^;]*);?')

_CONST_MULTI_PATTERN = re.compile(r'^(export )?const {(?P<names>[^}]*)} = (?P<value>.+);')
_RECORD_MEMBER_PATTERN = re.compile(r'(?P<assign>^\w+\.\w+ = {[^;]*);?')
_FUNCTION_PATTERN = re.compile(r'function \((?P<args>[^)]*)\) { *;?]')
_RETURN_PATTERN = re.compile(r'return (?P<value>.*)')


class SpecExtractor:

    def __init__(self, kibana_dir):
        self.kibana_dir = kibana_dir
        self.spec_file_contents = load_ts_specs(kibana_dir)
        self.last_found_in_file = None

    def extract_all(self):
        return self._process()

    def parse_all(self):
        parser = PeekParser()
        return parser.parse(self.extract_all())

    def _process(self):
        sources = []
        for file_name, file_content in self.spec_file_contents.items():
            sources.append(f'// {file_name!r}')
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

        text = '\n'.join(sources)
        return text.replace("rules['*']", "rules.'*'")

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
        m = _FUNCTION_PATTERN.match(stripped)
        if m is not None:
            sources.append(f'function {m["args"]} ' + '{')
            return True
        else:
            return False

    def _try_return(self, sources, stripped):
        m = _RETURN_PATTERN.match(stripped)
        if m is not None:
            value = m["value"]
            if value.endswith(';'):
                value = value[:-1]
            sources.append(f'"return": {value}')
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

    def extract(self, spec_name):
        spec_file_contents = dict(self.spec_file_contents)
        if self.last_found_in_file is not None:
            content = self._try_extract(spec_name, spec_file_contents.pop(self.last_found_in_file))
            if content is not None:
                return content.strip()

        for k, v in spec_file_contents.items():
            content = self._try_extract(spec_name, v)
            if content is not None:
                self.last_found_in_file = k
                return content.strip()

        raise ValueError(f'Spec not found for: {spec_name!r}')

    def _try_extract(self, spec_name, content):
        marker = f'const {spec_name} = '
        start_pos = content.find(marker)
        if start_pos == -1:
            return None

        # Find current line's indent level
        current_indent_level, pos = _find_indent_level(content, content[:start_pos].rfind('\n') + 1)
        # Every spec is multiline except const { terms, histogram, date_histogram } = rules['*'];
        pos = content.find('\n', start_pos)
        if pos == -1:
            raise ValueError(f'All TS spec should be multiline, got {content[start_pos:]!r}')

        # Match till the current indent level is matched
        while True:
            next_nl = content.find('\n', pos + 1)
            if next_nl == -1 or next_nl + 1 == len(content):
                return content[start_pos:]
            else:
                indent_level, pos = _find_indent_level(content, pos + 1)
                if indent_level == current_indent_level:
                    return content[start_pos:next_nl]
                else:
                    pos = next_nl


def _find_indent_level(content, pos):
    indent = 0
    while True:
        if content[pos] != ' ':
            break
        else:
            indent += 1
            pos += 1
    return indent, pos


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
