import io
import os
import random
from unittest.mock import patch, MagicMock

import pytest

from peek import __file__ as package_root
from peek.es_api_spec.spec_js import JsSpecParser, JsSpecEvaluator, build_js_specs

package_root = os.path.dirname(package_root)
kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_parse_specs():
    spec_parser = JsSpecParser(kibana_dir)
    spec_parser.parse()


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_eval_specs():
    spec_parser = JsSpecParser(kibana_dir)
    nodes = spec_parser.parse()
    spec_evaluator = JsSpecEvaluator()
    specs = spec_evaluator.visit(nodes)
    assert 'GLOBAL' in specs
    assert 'search' in specs
    assert 'put_mapping' in specs


def test_build_js_spec_will_respect_cache_config():
    kibana_dir = 'kibana_dir'
    mock_parser = MagicMock()
    mock_parser_cls = MagicMock(name='JsSpecParser', return_value=mock_parser)
    mock_evaluator = MagicMock(name='JsSpecEvaluator', return_value=MagicMock())
    cache_io = io.StringIO("source")
    use_cache_file = random.choice((True, False))
    cache_file_exists = random.choice((True, False))
    with patch('os.path.exists', MagicMock(return_value=cache_file_exists)), \
         patch('builtins.open', MagicMock(return_value=cache_io)), \
         patch('peek.es_api_spec.spec_js.JsSpecParser', mock_parser_cls), \
         patch('peek.es_api_spec.spec_js.JsSpecEvaluator', mock_evaluator):
        build_js_specs(kibana_dir, use_cache_file)

        if not use_cache_file:
            mock_parser_cls.assert_called_with(kibana_dir, source=None)
            mock_parser.parse.assert_called_once()
            mock_parser.save.assert_not_called()
        else:
            if cache_file_exists:
                mock_parser_cls.assert_called_with(kibana_dir, source='source')
                mock_parser.save.assert_not_called()
            else:
                mock_parser_cls.assert_called_with(kibana_dir, source=None)
                mock_parser.save.assert_called()


def test_parser_will_not_read_spec_files_when_source_is_provided():
    kibana_dir = None  # intentionally have it as None so if used will trip
    spec_parser = JsSpecParser(kibana_dir, source='let x = 42')
    nodes = spec_parser.parse()
    assert len(nodes) == 1
